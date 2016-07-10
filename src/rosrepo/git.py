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
    from itertools import imap as map
except ImportError:
    pass


class GitError(RuntimeError):
    def __init__(self, msg, exitcode=None):
        super(GitError, self).__init__(msg)
        self._exitcode = exitcode

    @property
    def status(self):
        return self._exitcode


class GitCommand(object):

    _local_args = ("stdin", "on_fail", "simulate")

    def __init__(self, args):
        self._args = args

    def __getattr__(self, name):
        return GitCommand(self._args + [name.replace("_", "-")])

    def __call__(self, *args, **kwargs):
        invoke = self._args
        for key, value in iteritems(kwargs):
            if value is not None and key not in GitCommand._local_args:
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
        return GitCommand(["git", "-C", self._wsdir, name.replace("_", "-")])


class GitObject(object):

    def __init__(self, repo, ref):
        self._repo = repo
        self._ref = ref

    def __str__(self):
        return self._ref

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self._repo, self._ref)

    def __eq__(self, other):
        return self._repo == other._repo and self._ref == other._ref

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self._ref.__hash__()

    @property
    def repo(self):
        return self._repo

    @property
    def ref_name(self):
        return self._ref

    def _resolve_ref(self, ref):
        try:
            stdout = self.repo.git.rev_parse(ref, verify=True)
            return stdout.strip() or None
        except GitError:
            return None

    def _find_ref(self, name, scope=None):
        try:
            stdout = self.repo.git.show_ref(name)
            data = (s.split(" ", 1)[-1].strip() for s in stdout.split("\n"))
            for r in data:
                if scope is None or r.startswith(scope):
                    return r
        except GitError:
            pass
        return None

    def _iter_ref(self, flt, cls):
        stdout = self.repo.git.show_ref()
        data = (s.split(" ", 1)[-1].strip() for s in stdout.split("\n"))
        result = set()
        for r in data:
            ok, value = flt(r)
            if ok:
                result.add(value)
        return map(cls, result)


class RootReference(GitObject):

    def __init__(self, repo):
        super(RootReference, self).__init__(repo, "refs")
        self._branches = Branches(self.repo)
        self._tags = Tags(self._repo)
        self._remotes = Remotes(self.repo)

    @property
    def heads(self):
        return self._branches

    @property
    def tags(self):
        return self._tags

    @property
    def remotes(self):
        return self._remotes

    def _from_ref(self, name):
        if name == "":
            return self
        if "/" in name:
            head, tail = name.split("/", 1)
        else:
            head, tail = name, ""
        if head == "heads":
            return self._branches._from_ref(tail)
        if head == "tags":
            return self._tags._from_ref(tail)
        if head == "remotes":
            return self._remotes._from_ref(tail)
        return None


class ReferenceCollection(GitObject):

    def __init__(self, repo, ref, cls):
        super(ReferenceCollection, self).__init__(repo, ref)
        self._cls = cls

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._repo)

    def __getattr__(self, name):
        return self._cls(name)

    def __getitem__(self, name):
        return self.__getattr__(name)

    def __delitem__(self, name):
        return self.__delattr__(name)

    def __contains__(self, item):
        return self._find_ref(item.ref_name if hasattr(item, "ref_name") else str(item), scope=self._ref + "/") is not None

    def __iter__(self):
        return self._iter_ref(
            flt=lambda x: (x.startswith(self._ref + "/"), x[len(self._ref) + 1:]),
            cls=self._cls
        )

    def _from_ref(self, name):
        if name == "":
            return self
        return self._cls(name)


class Branches(ReferenceCollection):

    def __init__(self, repo):
        super(Branches, self).__init__(repo, "refs/heads", lambda x: BranchReference(repo, x))

    def __delattr__(self, name):
        self.repo.git.branch(name, delete=True)

    def new(self, name, *args, **kwargs):
        self.repo.git.branch(name, *args, **kwargs)
        return self._cls(name)


class Tags(ReferenceCollection):

    def __init__(self, repo):
        super(Tags, self).__init__(repo, "refs/tags", lambda x: TagReference(repo, x))

    def __delattr__(self, name):
        self.repo.git.tag(name, delete=True)

    def new(self, name, *args, **kwargs):
        self.repo.git.tag(name, *args, **kwargs)
        return self._cls(name)


class Remotes(ReferenceCollection):

    def __init__(self, repo):
        super(Remotes, self).__init__(repo, "refs/remotes", lambda x: Remote(repo, x))

    def __iter__(self):
        remote_names = (r.strip() for r in self.repo.git.remote().split("\n") if r)
        return map(self._cls, remote_names)

    def __contains__(self, name):
        remote_names = (r.strip() for r in self.repo.git.remote().split("\n") if r)
        return name in remote_names

    def __delattr__(self, name):
        self.repo.git.remote.remove(name)

    def new(self, name, url, *args, **kwargs):
        self.repo.git.remote.add(name, url, *args, **kwargs)
        return self._cls(name)

    def _from_ref(self, name):
        if name == "":
            return self
        if "/" in name:
            head, tail = name.split("/", 1)
        else:
            head, tail = name, ""
        return self._cls(head)._from_ref(tail)


class Remote(ReferenceCollection):

    def __init__(self, repo, name):
        super(Remote, self).__init__(repo, "refs/remotes/" + name, lambda x: RemoteReference(repo, self, x))
        self._name = name

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self._repo, self._name)

    def __str__(self):
        return self._name

    def __bool__(self):
        try:
            self.repo.git.remote.get_url(self._name)
            return True
        except GitError:
            return False

    def __nonzero__(self):
        return self.__bool__()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, new_name):
        self.repo.git.remote.rename(self._name, new_name)
        self._name = new_name

    @property
    def url(self):
        return self.repo.git.remote.get_url(self._name).strip()

    @url.setter
    def url(self, value):
        self.repo.git.remote.set_url(self._name, value)

    @property
    def push_url(self):
        return self.repo.git.remote.get_url(self._name, push=True).strip()

    @push_url.setter
    def push_url(self, value):
        self.repo.git.remote.set_url(self._name, value, push=True)

    def fetch(self, *args, **kwargs):
        self.repo.git.fetch(self._name, *args, **kwargs)

    def delete(self):
        self.repo.git.remote.remove(self._name)


class Reference(GitObject):

    def __bool__(self):
        return self._resolve_ref(self._ref) is not None

    def __nonzero__(self):
        return self.__bool__()

    def is_ancestor(self, other):
        try:
            self.repo.git.merge_base(self.commit, other.commit, is_ancestor=True)
            return True
        except GitError as e:
            if e.status == 1:
                return False
            raise

    def merge_base(self, other):
        return Reference(self.repo, self.repo.git.merge_base(self.commit, other.commit).strip())

    @property
    def tag(self):
        return GitObject(self.repo, self.repo.git.rev_parse(self._ref + "^{tag}", verify=True, on_fail="%r does not refer to a tag object" % self._ref).strip())

    @property
    def commit(self):
        return GitObject(self.repo, self.repo.git.rev_parse(self._ref + "^{commit}", verify=True, on_fail="%r does not refer to a commit object" % self._ref).strip())

    @property
    def tree(self):
        return GitObject(self.repo, self.repo.git.rev_parse(self._ref + "^{tree}", verify=True, on_fail="%r does not refer to a tree object" % self._ref).strip())


class RemoteReference(Reference):

    def __init__(self, repo, remote, name):
        super(RemoteReference, self).__init__(repo, "refs/remotes/" + remote.name + "/" + name)
        self._remote = remote
        self._name = name

    def __str__(self):
        return "%s/%s" % (self._remote.name, self._name)

    @property
    def remote_name(self):
        return self._remote.name

    @property
    def branch_name(self):
        return self._name

    @property
    def name(self):
        return self._remote.name + "/" + self._name

    @property
    def remote(self):
        return self._remote


class TagReference(Reference):

    def __init__(self, repo, name):
        super(TagReference, self).__init__(repo, "refs/tags/" + name)
        self._name = name

    def __str__(self):
        return self._name

    @property
    def name(self):
        return self._name

    tag_name = name

    @property
    def reference(self):
        return Reference(self.repo, self.repo.git.rev_parse(self._ref + "^{}", verify=True, on_fail="%r is not a valid reference" % self._ref).strip())

    @reference.setter
    def reference(self, value):
        self.repo.git.tag(self.name, value, force=True)

    def delete(self):
        self.repo.git.tag(self.name, delete=True)


class BranchReference(Reference):

    def __init__(self, repo, name):
        super(BranchReference, self).__init__(repo, "refs/heads/" + name)
        self._name = name

    def __str__(self):
        return self._name

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if self._name != value:
            self.repo.git.branch(self._name, value, move=True)
            self._ref = "refs/heads/" + value
            self._name = value

    branch_name = name

    @property
    def tracking_branch(self):
        try:
            tb = self.repo.git.rev_parse(self._name + "@{u}", verify=True, symbolic_full_name=True).strip()
            return self.repo.from_ref(tb)
        except GitError:
            return None

    @tracking_branch.setter
    def tracking_branch(self, value):
        self.repo.git.branch(self._name, set_upstream_to=value)

    def checkout(self, *args, **kwargs):
        self.repo.git.checkout(self._name, *args, **kwargs)

    def delete(self, *args, **kwargs):
        self.repo.git.branch(self._name, delete=True, *args, **kwargs)


class SymbolicReference(Reference):

    def __init__(self, repo, name):
        super(SymbolicReference, self).__init__(repo, name)
        self._name = name

    @property
    def name(self):
        return self._name

    @property
    def reference(self):
        ref = self.repo.git.symbolic_ref(self._name, on_fail="%r is not a symbolic reference" % self._name).strip()
        return self.repo.from_ref(ref) or Reference(self.repo, ref)


class Repo(object):

    def __init__(self, wsdir):
        self._wsdir = wsdir
        self._git = Git(wsdir)
        self._refs = RootReference(self)

    def __repr__(self):
        return "Repo(%r)" % self._wsdir

    def __eq__(self, other):
        return self._wsdir == other._wsdir

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self._wsdir.__hash__()

    def __bool__(self):
        try:
            self.git.show_ref()
            return True
        except GitError:
            return False

    def __nonzero__(self):
        return self.__bool__()

    @property
    def git(self):
        return self._git

    @property
    def refs(self):
        return self._refs

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
        return self.refs.heads

    @property
    def tags(self):
        return self.refs.tags

    @property
    def remotes(self):
        return self.refs.remotes

    def remote(self, name):
        return self.refs.remotes[name]

    def is_dirty(self):
        stdout = self.git.status(porcelain=True).strip()
        return stdout != ""

    def from_ref(self, name):
        if name == "HEAD":
            return self.head
        if name == "ORIG_HEAD":
            return self.orig_head
        if name == "FETCH_HEAD":
            return self.fetch_head
        if "/" in name:
            name, tail = name.split("/", 1)
        else:
            tail = ""
        if name == "refs":
            return self.refs._from_ref(tail)
        return None
