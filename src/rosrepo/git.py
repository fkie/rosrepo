# coding=utf-8
#
# ROSREPO
# Manage ROS workspaces with multiple Gitlab repositories
#
# Author: Timo Röhling
#
# Copyright 2016 Fraunhofer FKIE
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from .util import call_process, PIPE, iteritems
try:
    from itertools import ifilter as filter, imap as map
except ImportError:
    pass


class GitError(RuntimeError):
    def __init__(self, msg, exitcode=None):
        super(GitError, self).__init__(msg)
        self._exitcode = exitcode

    @property
    def status(self):
        return self._exitcode


class GitCommandProxy(object):

    _local_args = ("stdin", "on_fail", "simulate")

    def __init__(self, args):
        self._args = args

    def __getattr__(self, name):
        return GitCommandProxy(self._args + [name.replace("_", "-")])

    def __call__(self, *args, **kwargs):
        invoke = self._args
        for key, value in iteritems(kwargs):
            if key not in GitCommandProxy._local_args:
                param = ("--" if len(key) > 1 else "-") + ("no-" if isinstance(value, bool) and not value else "") + key.replace("_", "-")
                invoke.append(param)
                if not isinstance(value, bool):
                    invoke.append(str(value))
        invoke += [str(a) for a in args]
        simulate = kwargs.get("simulate", False)
        if simulate:
            print(" ".join(invoke))
            return ""
        else:
            exitcode, stdout, stderr = call_process(invoke, stdin=PIPE, stdout=PIPE, stderr=PIPE, input_data=kwargs.get("stdin", None))
        if exitcode != 0:
            on_fail = kwargs.get("on_fail", None)
            if on_fail:
                raise GitError(on_fail, exitcode)
            else:
                raise GitError(stderr.split("\n", 1)[0], exitcode)
        return stdout


class Git(object):

    def __init__(self, wsdir):
        self._wsdir = wsdir

    def __getattr__(self, name):
        return GitCommandProxy(["git", "-C", self._wsdir, name.replace("_", "-")])


class Reference(object):

    def __init__(self, repo, name):
        self._repo = repo
        self._name = name
        self._resolved_name = None

    def __str__(self):
        return self.name

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self._repo, self._name)

    def __eq__(self, other):
        if self._repo == other._repo:
            return self._resolve_name() == other._resolve_name()
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self._resolve_name().__hash__()

    def __iter__(self):
        return self._repo._iter_refs(self._name + "/")

    def __contains__(self, item):
        return self.repo._contains_ref(self._name + "/", str(item))

    def __bool__(self):
        try:
            self._resolve_name()
            return True
        except GitError:
            return False

    def __nonzero__(self):
        return self.__bool__()

    def __getattr__(self, name):
        return self._repo._make_ref(self._name + "/" + name)

    def __delattr__(self, name):
        victim_deleter = self.__getattr__(name).delete
        if hasattr(victim_deleter, "__call__"):
            victim_deleter()

    def __getitem__(self, name):
        return self.__getattr__(name)

    def __delitem__(self, name):
        self.__delattr__(name)

    def is_ancestor(self, other):
        try:
            self._repo.git.merge_base(self.full_name, other.full_name, is_ancestor=True)
            return True
        except GitError as e:
            if e.status == 1:
                return False
            raise

    @property
    def full_name(self):
        return self._resolve_name()

    @property
    def name(self):
        return self.full_name.split("/", 2)[-1]

    def points_at(self, other):
        return self.commit_ish == other.commit_ish

    def merge_base(self, other):
        return self._repo._make_ref(self._repo.git.merge_base(self.full_name, other.full_name).strip())

    def new(self, name, *args, **kwargs):
        if self._name == "refs/remotes":
            return RemoteCollection(self._repo).new(name, *args, **kwargs)
        if self._name == "refs/heads":
            self._repo.git.branch(name, *args, **kwargs)
            return BranchReference(self._repo, name)
        if self._name == "refs/tags":
            self._repo.git.tag(name, *args, **kwargs)
            return TagReference(self._repo, name)
        raise GitError("%r cannot be created" % (self._name + "/" + name))

    @property
    def commit_ish(self):
        return self._repo.git.rev_parse("%s^{commit}" % self._name, verify=True, on_fail="%r is not a commit object" % self._name).strip()

    @property
    def tree_ish(self):
        return self._repo.git.rev_parse("%s^{tree}" % self._name, verify=True, on_fail="%r is not a commit object" % self._name).strip()

    @property
    def repo(self):
        return self._repo

    def _resolve_name(self):
        if self._resolved_name is None:
            self._resolved_name = self._repo.git.rev_parse(self._name, verify=True, symbolic_full_name=True, on_fail="%r is not a valid reference" % self._name).strip()
            if self._resolved_name == "":
                self._resolved_name = self._name
        return self._resolved_name

    def _invalidate(self):
        self._resolved_name = None


class RemoteReference(Reference):

    @property
    def remote_name(self):
        return self._resolve_name().split("/", 3)[2]

    @property
    def branch_name(self):
        return self._resolve_name().split("/", 3)[3]

    @property
    def remote(self):
        return Remote(self._repo, self.remote_name)


class TagReference(Reference):

    @property
    def reference(self):
        return self._repo._make_ref(self._repo.git.rev_parse("%s^{}" % self.name, verify=True).strip())

    @reference.setter
    def reference(self, value):
        self._repo.git.tag(self.name, value, force=True)

    def delete(self):
        self._repo.git.tag(self.name, delete=True)
        self._invalidate()


class BranchReference(Reference):

    @property
    def branch_name(self):
        return self._resolve_name().split("/", 2)[-1]

    @branch_name.setter
    def branch_name(self, value):
        if self.name != value:
            self._repo.git.branch(self.name, value, move=True)
            self._name = "refs/heads/%s" % value
            self._invalidate()

    @property
    def tracking_branch(self):
        try:
            return self._repo._make_ref(self._repo.git.rev_parse("%s@{u}" % self.name, verify=True, symbolic_full_name=True).strip())
        except GitError:
            return None

    @tracking_branch.setter
    def tracking_branch(self, value):
        self._repo.git.branch(self.name, set_upstream_to=value)

    def checkout(self):
        self._repo.git.checkout(self.name)

    def delete(self):
        self._repo.git.branch(self.name, delete=True)
        self._invalidate()

    def force_delete(self):
        self._repo.git.branch(self.name, delete=True, force=True)
        self._invalidate()


class SymbolicReference(Reference):

    def __getattr__(self, name):
        raise AttributeError("no such attribute: %s" % name)

    @property
    def name(self):
        return self._name

    @property
    def reference(self):
        return self._repo._make_ref(self._resolve_name())

    def _resolve_name(self):
        return self._repo.git.symbolic_ref(str(self._name), on_fail="%r is not a symbolic reference" % self._name).strip()


class Remote(object):
    def __init__(self, repo, name):
        self._repo = repo
        self._name = name

    def __str__(self):
        return self._name

    def __repr__(self):
        return "Remote(%r, %r)" % (self._repo, self._name)

    def __getattr__(self, name):
        return RemoteReference(self._repo, "refs/remotes/" + self._name + "/" + str(name))

    def __getitem__(self, name):
        return self.__getattr__(name)

    def __eq__(self, other):
        if self._repo == other._repo:
            return self._name == other._name
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self._name.__hash__()

    def __iter__(self):
        return self._repo._iter_refs("refs/remotes/" + self._name + "/")

    def __contains__(self, item):
        return self.repo._contains_ref("refs/remotes/" + self._name + "/", str(item))

    def __bool__(self):
        return self._repo._has_refs("refs/remotes/" + self._name + "/")

    def __nonzero__(self):
        return self.__bool__()

    @property
    def url(self):
        return self._repo.git.remote.get_url(self._name).strip()

    @url.setter
    def url(self, value):
        self._repo.git.remote.set_url(self._name, value)

    @property
    def push_url(self):
        return self._repo.git.remote.get_url(self._name, push=True).strip()

    @push_url.setter
    def push_url(self, value):
        self._repo.git.remote.set_url(self._name, value, push=True)

    def fetch(self, *args, **kwargs):
        self._repo.git.fetch(self._name, *args, **kwargs)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._repo.git.remote.rename(self._name, value)
        self._name = value

    @property
    def repo(self):
        return self._repo

    def delete(self):
        self._repo.git.remote.remove(self._name)


class RemoteCollection(object):
    def __init__(self, repo):
        self._repo = repo

    def __getattr__(self, name):
        return Remote(self._repo, name)

    def __delattr__(self, name):
        self._repo.git.remote.remove(name)

    def __getitem__(self, name):
        return self.__getattr__(name)

    def __delitem__(self, name):
        self.__delattr__(name)

    def __contains__(self, item):
        return str(item) in self._get_all_remotes()

    def __iter__(self):
        return map(self._make_remote, self._get_all_remotes())

    def new(self, name, *args, **kwargs):
        self._repo.git.remote.add(name, *args, **kwargs)
        return Remote(self._repo, name)

    def _get_all_remotes(self):
        stdout = self._repo._git.show_ref()
        found = set()
        for line in stdout.split("\n"):
            ref_name = line.split(" ", 1)[-1]
            if ref_name.startswith("refs/remotes/"):
                remote_name = ref_name.split("/", 3)[2]
                if remote_name not in found:
                    found.add(remote_name)
        return found

    def _make_remote(self, name):
        return Remote(self._repo, name)


class Repo(object):

    def __init__(self, wsdir):
        self._wsdir = wsdir
        self._git = Git(wsdir)

    def __repr__(self):
        return "Repo(%r)" % self._wsdir

    def __eq__(self, other):
        return self._wsdir == other._wsdir

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self._wsdir.__hash__()

    def __bool__(self):
        return self._has_refs()

    def __nonzero__(self):
        return self.__bool__()

    @property
    def git(self):
        return self._git

    @property
    def refs(self):
        return Reference(self, "refs")

    @property
    def head(self):
        return SymbolicReference(self, "HEAD")

    @property
    def orig_head(self):
        return SymbolicReference(self, "ORIG_HEAD")

    @property
    def fetch_head(self):
        return SymbolicReference(self, "FETCH_HEAD")

    @property
    def heads(self):
        return Reference(self, "refs/heads")

    @property
    def tags(self):
        return Reference(self, "refs/tags")

    @property
    def remotes(self):
        return RemoteCollection(self)

    def remote(self, name):
        return Remote(self, name)

    def is_dirty(self):
        stdout = self.git.status(porcelain=True).strip()
        return stdout != ""

    def _make_ref(self, name):
        if name.startswith("refs/remotes/"):
            return RemoteReference(self, name)
        if name.startswith("refs/tags/"):
            return TagReference(self, name)
        if name.startswith("refs/heads/"):
            return BranchReference(self, name)
        return Reference(self, name)

    def _iter_refs(self, ref_filter):
        def f(ref_name):
            return ref_filter is None or ref_name.startswith(ref_filter)
        stdout = self._git.show_ref()
        data = (s.split(" ", 1)[-1].strip() for s in stdout.split("\n"))
        return map(self._make_ref, filter(f, data))

    def _contains_ref(self, ref_filter, name):
        try:
            stdout = self._git.show_ref(name)
            for line in stdout.split("\n"):
                ref_name = line.split(" ", 1)[-1].strip()
                if ref_filter is None or ref_name.startswith(ref_filter):
                    return True
        except GitError:
            pass
        return False

    def _has_refs(self, ref_filter=None):
        try:
            stdout = self._git.show_ref()
            for line in stdout.split("\n"):
                ref_name = line.split(" ", 1)[-1].strip()
                if ref_filter is None or ref_name.startswith(ref_filter):
                    return True
        except GitError:
            pass
        return False
