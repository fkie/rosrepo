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
#
import os
import sys
import re
import shutil
from .workspace import get_workspace_location, get_workspace_state, find_catkin_packages, resolve_this
from .config import Config
from .cache import Cache
from .resolver import find_dependees, resolve_system_depends
from .ui import TableView, msg, warning, error, fatal, escape, \
                show_conflicts, show_missing_system_depends, \
                textify, LARROW, RARROW, FF_LARROW, FF_RARROW
from .util import iteritems, path_has_prefix, has_package_path, call_process, PIPE, \
                create_multiprocess_manager, run_multiprocess_workers
from pygit2 import clone_repository, Repository, \
                RemoteCallbacks, KeypairFromAgent, UserPass, \
                GIT_CREDTYPE_SSH_KEY, GIT_CREDTYPE_USERPASS_PLAINTEXT, \
                GIT_STATUS_CURRENT, GIT_STATUS_IGNORED, GIT_BRANCH_LOCAL, \
                GIT_BRANCH_REMOTE, GitError, \
                features as pygit2_features, GIT_FEATURE_HTTPS, GIT_FEATURE_SSH

from functools import partial
try:
    from urlparse import urlsplit
except ImportError:
    from urllib.parse import urlsplit


def need_push(repo, local_branch, remote_branch=None):
    if local_branch is None:
        return False
    if remote_branch is None:
        remote_branch = local_branch.upstream
    if remote_branch is None:
        return False
    return local_branch.target != remote_branch.target and is_ancestor(repo, remote_branch, local_branch)


def need_pull(repo, local_branch, remote_branch=None):
    if local_branch is None:
        return False
    if remote_branch is None:
        remote_branch = local_branch.upstream
    if remote_branch is None:
        return False
    return local_branch.target != remote_branch.target and is_ancestor(repo, local_branch, remote_branch)


def is_up_to_date(repo, local_branch, remote_branch=None):
    if local_branch is None:
        return False
    if remote_branch is None:
        remote_branch = local_branch.upstream
    if remote_branch is None:
        return False
    return local_branch.target == remote_branch.target


def get_head_branch(repo):
    try:
        return repo.lookup_branch(repo.head.shorthand, GIT_BRANCH_LOCAL)
    except (ValueError, GitError):
        return None


def get_origin(repo, project):
    for r in repo.remotes:
        for _, url in iteritems(project.url):
            if r.url == url:
                return r
    return None


def get_remote_branch_name(branch):
    _, name = branch.shorthand.split("/", 1)
    return name


def has_pending_merge(repo):
    try:
        repo.lookup_reference("MERGE_HEAD")
        return True
    except KeyError:
        return False


def is_ancestor(repo, maybe_ancestor, branch):
    try:
        return repo.merge_base(maybe_ancestor.target, branch.target) == maybe_ancestor.target
    except ValueError:
        return False


class AuthorizationFailed(RuntimeError):
    pass


class GitRemoteCallback(RemoteCallbacks):

    def __init__(self, config):
        self.config = config
        self.urls = {}

    def get_private_token(self, url):
        for gitlab_cfg in self.config.get("gitlab_servers", []):
            url_prefix = gitlab_cfg.get("url", None)
            private_token = gitlab_cfg.get("private_token", None)
            if url.startswith(url_prefix):
                return private_token
        return None

    def save_working_credentials(self, query, username, credential):
        global credential_dict
        credential_dict[query] = (username, credential)

    def record_permanent_failure(self, query, reason):
        global credential_dict
        credential_dict[query] = (None, AuthorizationFailed(reason))
        raise AuthorizationFailed(reason)

    def get_cached_credentials(self, query):
        global credential_dict
        username, credential = credential_dict.get(query, (None, None))
        if type(credential) == AuthorizationFailed:
            raise credential
        return username, credential

    def credentials(self, url, username_from_url, allowed_types):
        global credential_lock
        credential_lock.acquire()
        msg("@{cf}Fetching@|: %s\n" % escape(textify(url)))
        try:
            if url not in self.urls:
                retry = 0
            else:
                retry = self.urls[url]
            u = urlsplit(url)
            query = "protocol=%s\nhost=%s\n" % (u[0], u[1])
            while True:
                retry += 1
                self.urls[url] = retry
                if retry == 1:
                    if allowed_types & GIT_CREDTYPE_SSH_KEY:
                        return KeypairFromAgent(username_from_url)
                    if allowed_types & GIT_CREDTYPE_USERPASS_PLAINTEXT:
                        private_token = self.get_private_token(url)
                        if private_token:
                            return UserPass("rosrepo", private_token)
                if retry == 2:
                    if allowed_types & GIT_CREDTYPE_SSH_KEY:
                        self.record_permanent_failure(query, "SSH agent has no acceptable key")
                    if allowed_types & GIT_CREDTYPE_USERPASS_PLAINTEXT:
                        username, password = self.get_cached_credentials(query)
                        if username is None:
                            exitcode, stdout, _ = call_process(["git", "credential", "fill"], input_data=query, stdin=PIPE, stdout=PIPE)
                            if exitcode != 0:
                                self.record_permanent_failure(query, "git credential helper failed")
                            for line in stdout.split("\n"):
                                if "=" in line:
                                    key, value = line.split("=", 1)
                                    if key == "username":
                                        username = value
                                    if key == "password":
                                        password = value
                            if username is not None and password is not None:
                                exitcode, stdout, _ = call_process(["git", "credential", "approve"], input_data=stdout, stdin=PIPE, stdout=PIPE)
                        if username is not None and password is not None:
                            self.save_working_credentials(query, username, password)
                            return UserPass(username, password)
                if retry == 3:
                    if allowed_types & GIT_CREDTYPE_USERPASS_PLAINTEXT:
                        exitcode, stdout, _ = call_process(["git", "credential", "reject"], input_data=query, stdin=PIPE, stdout=PIPE)
                        self.record_permanent_failure(query, "invalid username or password")
                if retry > 3:
                    self.record_permanent_failure(query, "cannot handle requested authorization credentials")
        finally:
            credential_lock.release()


def show_status(srcdir, packages, projects, other_git, ws_state, show_up_to_date=True, cache=None):
    def create_upstream_status(repo, head_branch, master_branch, master_remote_branch, tracking_branch):
        status = []
        if not repo.head_is_detached and not has_pending_merge(repo):
            if tracking_branch is not None:
                if master_remote_branch is not None:
                    if tracking_branch.remote_name != master_remote_branch.remote_name:
                        status.append("@!@{rf}remote '%s'" % tracking_branch.remote_name)
                if need_push(repo, head_branch):
                    status.append("@!@{yf}needs push")
                elif need_pull(repo, head_branch):
                    status.append("@!@{cf}needs pull")
                elif not is_up_to_date(repo, head_branch):
                    status.append("@!@{yf}needs pull -M")
            else:
                if head_branch:
                    status.append("@!on branch '%s'" % repo.head.shorthand)
                else:
                    status.append("empty branch")
                if master_remote_branch is None:
                    status.append("@!@{rf}no remote")
                elif master_branch is None:
                    status.append("@!@{rf}untracked remote")
                if is_up_to_date(repo, master_branch) or need_push(repo, master_branch):
                    if need_pull(repo, head_branch, master_branch):
                        status.append("@!@{cf}needs pull -L")
                    else:
                        if not is_ancestor(repo, master_branch, head_branch):
                            status.append("@!@{yf}needs merge --from-master")
                        if not is_up_to_date(repo, head_branch, master_branch):
                            status.append("@!@{yf}needs merge --to-master")
            if master_branch is not None and master_remote_branch is not None and (tracking_branch is None or tracking_branch.name != master_remote_branch.name):
                if need_push(repo, master_branch):
                    status.append("@!@{yf}%s needs push" % master_branch.shorthand)
                elif need_pull(repo, master_branch):
                    status.append("@!@{cf}%s needs pull" % master_branch.shorthand)
                elif not is_up_to_date(repo, master_branch):
                    status.append("@!@{yf}%s needs merge" % master_branch.shorthand)
        return status

    def create_local_status(repo, upstream_status, is_dirty):
        status = []
        if repo.head_is_detached:
            status.append("@!@{rf}detached HEAD")
            return status
        if has_pending_merge(repo):
            if repo.index.conflicts:
                status.append("@!@{rf}merge conflicts")
            else:
                status.append("@!@{yf}merged, needs commit")
            return status
        if is_dirty:
            status.append("@!@{yf}needs commit")
        status += upstream_status
        if not status:
            if not show_up_to_date:
                return None
            status.append("@!@{gf}up-to-date")
        return status

    table = TableView("Package", "Path", "Status")

    found_packages = set()
    for project in projects:
        repo = Repository(os.path.join(srcdir, project.workspace_path, ".git"))
        dirty_files = [a for a, b in iteritems(repo.status()) if b != GIT_STATUS_IGNORED and b != GIT_STATUS_CURRENT]
        head_branch = get_head_branch(repo)
        tracking_branch = head_branch.upstream if head_branch else None
        master_remote = get_origin(repo, project)
        if master_remote is not None:
            master_remote_branch = repo.lookup_branch("%s/%s" % (master_remote.name, project.master_branch), GIT_BRANCH_REMOTE)
            master_branch = None
            if master_remote_branch is not None:
                for name in repo.listall_branches(GIT_BRANCH_LOCAL):
                    b = repo.lookup_branch(name, GIT_BRANCH_LOCAL)
                    if b.upstream and b.upstream.branch_name == master_remote_branch.branch_name:
                        master_branch = b
                        break
        else:
            master_remote_branch = None
            master_branch = None
        ws_packages = find_catkin_packages(srcdir, project.workspace_path, cache=cache)
        found_packages |= set(ws_packages.keys())
        upstream_status = create_upstream_status(repo, head_branch, master_branch, master_remote_branch, tracking_branch)
        for name, pkg_list in iteritems(ws_packages):
            if name not in packages:
                continue
            for pkg in pkg_list:
                is_dirty = False
                local_path = os.path.relpath(pkg.workspace_path, project.workspace_path)
                if dirty_files and local_path == ".":
                    is_dirty = True
                else:
                    for fpath in dirty_files:
                        if path_has_prefix(fpath, local_path):
                            is_dirty = True
                            break
                status = create_local_status(repo, upstream_status, is_dirty)
                if status is not None:
                    head, tail = os.path.split(pkg.workspace_path)
                    pkg_path = escape(head + "/" if tail == name else pkg.workspace_path)
                    table.add_row(escape(name), pkg_path, status)

    for path in other_git:
        repo = Repository(os.path.join(srcdir, path, ".git"))
        dirty_files = [a for a, b in iteritems(repo.status()) if b != GIT_STATUS_IGNORED and b != GIT_STATUS_CURRENT]
        head_branch = get_head_branch(repo)
        tracking_branch = head_branch.upstream if head_branch else None
        ws_packages = find_catkin_packages(srcdir, path, cache=cache)
        found_packages |= set(ws_packages.keys())
        upstream_status = create_upstream_status(repo, head_branch, None, None, tracking_branch)
        for name, pkg_list in iteritems(ws_packages):
            if name not in packages:
                continue
            for pkg in pkg_list:
                is_dirty = False
                local_path = os.path.relpath(pkg.workspace_path, path)
                if dirty_files and local_path == ".":
                    is_dirty = True
                else:
                    for fpath in dirty_files:
                        if path_has_prefix(fpath, local_path):
                            is_dirty = True
                            break
                status = create_local_status(repo, upstream_status, is_dirty)
                if status is not None:
                    head, tail = os.path.split(pkg.workspace_path)
                    pkg_path = escape(head + "/" if tail == name else pkg.workspace_path)
                    table.add_row(escape(name), pkg_path, status)

    missing = set(packages) - found_packages
    for name in missing:
        path_list = []
        status = "no git"
        if name in ws_state.ws_packages:
            for pkg in ws_state.ws_packages[name]:
                if not os.path.isdir(os.path.join(srcdir, pkg.workspace_path)):
                    status = "@{rf}deleted"
                head, tail = os.path.split(pkg.workspace_path)
                path_list.append(escape(head + "/" if tail == name else pkg.workspace_path))
        table.add_row(escape(name), path_list, status)
    if table.empty():
        if found_packages:
            msg("Everything is @!@{gf}up-to-date@|.\n")
        else:
            warning("no Git repositories\n")
    else:
        table.sort(0)
        table.write(sys.stdout)


def show_diff(srcdir, packages, projects, other_git, diff_staged=False, diff_upstream=False, cache=None):
    extra_args = []
    if diff_staged:
        extra_args.append("--cached")
    if diff_upstream:
        extra_args += ["@{upstream}", "HEAD"]
    for project in projects:
        ws_packages = find_catkin_packages(srcdir, project.workspace_path, cache=cache)
        if set(ws_packages.keys()) <= packages:
            call_process(["git", "-C", os.path.join(srcdir, project.workspace_path), "--no-pager", "diff", "--src-prefix=a/%s/" % project.workspace_path, "--dst-prefix=b/%s/" % project.workspace_path] + extra_args)
        else:
            for name, pkg_list in iteritems(ws_packages):
                if name not in packages:
                    continue
                for pkg in pkg_list:
                    call_process(["git", "-C", os.path.join(srcdir, pkg.workspace_path), "--no-pager", "diff", "--relative", "--src-prefix=a/%s/" % pkg.workspace_path, "--dst-prefix=b/%s/" % pkg.workspace_path] + extra_args)
    for path in other_git:
        ws_packages = find_catkin_packages(srcdir, path, cache=cache)
        if set(ws_packages.keys()) <= packages:
            call_process(["git", "-C", os.path.join(srcdir, path), "--no-pager", "diff", "--src-prefix=a/%s/" % path, "--dst-prefix=b/%s/" % path] + extra_args)
        else:
            for name, pkg_list in iteritems(ws_packages):
                if name not in packages:
                    continue
                for pkg in pkg_list:
                    call_process(["git", "-C", os.path.join(srcdir, pkg.workspace_path), "--no-pager", "diff", "--relative", "--src-prefix=a/%s/" % pkg.workspace_path, "--dst-prefix=b/%s/" % pkg.workspace_path] + extra_args)


def lookup_branches(repo, project):
    master_branch = None
    if project is not None:
        master_remote = get_origin(repo, project)
        if master_remote is not None:
            master_remote_branch = repo.lookup_branch("%s/%s" % (master_remote.name, project.master_branch), GIT_BRANCH_REMOTE)
            for name in repo.listall_branches(GIT_BRANCH_LOCAL):
                b = repo.lookup_branch(name, GIT_BRANCH_LOCAL)
                if b.upstream and b.upstream.branch_name == master_remote_branch.branch_name:
                    master_branch = b
                    break
    head_branch = get_head_branch(repo)
    tracking_branch = head_branch.upstream if head_branch else None
    return head_branch, master_branch, tracking_branch


def fetch_project(srcdir, project, git_remote_callback, fetch_remote, dry_run):
    try:
        repo = Repository(os.path.join(srcdir, project.workspace_path, ".git"))
        master_remote = get_origin(repo, project)
        head_branch = get_head_branch(repo)
        tracking_branch = head_branch.upstream if head_branch else None
        tracking_remote = repo.remotes[tracking_branch.remote_name] if tracking_branch is not None else None
        if fetch_remote and master_remote is not None:
            if not dry_run:
                master_remote.fetch(callbacks=git_remote_callback)
            else:
                msg("@{cf}Fetching@|: %s\n" % escape(textify(master_remote.url)))
        if fetch_remote and tracking_remote is not None and (master_remote is None or master_remote.name != tracking_remote.name):
            if not dry_run:
                tracking_remote.fetch(callbacks=git_remote_callback)
            else:
                msg("@{cf}Fetching@|: %s\n" % escape(textify(tracking_remote.url)))
        return ""
    except (GitError, AuthorizationFailed) as e:
        return str(e)


def fetch_other_git(srcdir, path, git_remote_callback, fetch_remote, dry_run):
    try:
        repo = Repository(os.path.join(srcdir, path, ".git"))
        head_branch = get_head_branch(repo)
        tracking_branch = head_branch.upstream if head_branch else None
        if fetch_remote and tracking_branch is not None:
            tracking_remote = repo.remotes[tracking_branch.remote_name]
            if not dry_run:
                tracking_remote.fetch(callbacks=git_remote_callback)
            else:
                msg("@{cf}Fetching@|: %s\n" % escape(textify(tracking_remote.url)))
        return ""
    except (GitError, AuthorizationFailed) as e:
        return str(e)


def fetch_worker(srcdir, git_remote_callback, fetch_remote, dry_run, part):
    project, path = part[0], part[1]
    if project is not None:
        result = fetch_project(srcdir, project, git_remote_callback, fetch_remote, dry_run)
    else:
        result = fetch_other_git(srcdir, path, git_remote_callback, fetch_remote, dry_run)
    return project, path, result


def fetch_worker_init(L, d):
    global credential_lock
    global credential_dict
    credential_lock = L
    credential_dict = d


def update_projects(srcdir, packages, projects, other_git, ws_state, config, update_op, jobs, dry_run=False, action="update", fetch_remote=True):
    if (pygit2_features & GIT_FEATURE_HTTPS) == 0:
        warning("your libgit2 has no built-in HTTPS support\n")
    if (pygit2_features & GIT_FEATURE_SSH) == 0:
        warning("your libgit2 has no built-in SSH support\n")
    git_remote_callback = GitRemoteCallback(config)
    manager = create_multiprocess_manager()
    L = manager.Lock()
    d = manager.dict()
    workload = [(project, project.workspace_path) for project in projects] + [(None, path) for path in other_git]
    result = run_multiprocess_workers(partial(fetch_worker, srcdir, git_remote_callback, fetch_remote, dry_run), workload, worker_init=fetch_worker_init, worker_init_args=(L, d), jobs=jobs, timeout=900)
    done = 0
    errors = 0
    for r in result:
        project, path, e = r
        try:
            if not e:
                repo = Repository(os.path.join(srcdir, path, ".git"))
                head_branch, master_branch, tracking_branch = lookup_branches(repo, project)
                if update_op(repo, path, head_branch, master_branch, tracking_branch):
                    done += 1
            else:
                error("cannot fetch remotes for '%s': %s\n" % (escape(path), escape(str(e))))
                errors += 1
        except Exception as e:
            error("cannot %s '%s': %s\n" % (action, escape(path), escape(str(e))))
            errors += 1
    if done:
        report = ("%s completed successfully for" % action.title()) if not dry_run else ("Dry-run: %s would have been executed for" % action)
        if done == 1:
            msg("@!%s one repository@|\n" % report)
        else:
            msg("@!%s %d repositories@|\n" % (report, done))
    if errors:
        if errors == 1:
            warning("an error has occurred\n")
        else:
            warning("%d errors have occurred\n" % errors)


def pull_projects(srcdir, packages, projects, other_git, ws_state, config, jobs, update_local=False, merge=False, dry_run=False):
    def do_pull(repo, path, head_branch, master_branch, tracking_branch):
        if has_pending_merge(repo):
            raise Exception("unfinished merge detected")
        if head_branch is None:
            return False
        result = False
        if tracking_branch is not None:
            if need_pull(repo, head_branch, tracking_branch):
                msg("@{cf}Fast-Forwarding@|: %s (@{cf}%s@| %s @{cf}%s@|)\n" % (escape(path), escape(head_branch.shorthand), FF_LARROW, escape(tracking_branch.shorthand)))
                result = True
                if not dry_run:
                    exitcode = call_process(["git", "-C", os.path.join(srcdir, path), "merge", "--ff-only", tracking_branch.shorthand])
                    if exitcode != 0:
                        raise Exception("fast-forward merge of %s failed" % tracking_branch.shorthand)
                head_branch = get_head_branch(repo)
            elif head_branch.target != tracking_branch.target and merge:
                msg("@{cf}Merging@|: %s (@{cf}%s@| %s @{cf}%s@|)\n" % (escape(path), escape(head_branch.shorthand), LARROW, escape(tracking_branch.shorthand)))
                result = True
                if not dry_run:
                    robust_merge(repo, os.path.join(srcdir, path), tracking_branch, "Merge changes from %s into %s" % (tracking_branch.shorthand, head_branch.shorthand))
                head_branch = get_head_branch(repo)
        if master_branch is not None:
            if head_branch.name != master_branch.name and need_pull(repo, master_branch):
                msg("@{cf}Fast-Forwarding@|: %s (@{cf}%s@| %s @{cf}%s@|)\n" % (escape(path), escape(master_branch.shorthand), FF_LARROW, escape(master_branch.upstream.shorthand)))
                result = True
                master_branch.set_target(master_branch.upstream.target)
            if update_local and (is_up_to_date(repo, master_branch) or need_push(repo, master_branch)) and need_pull(repo, head_branch, master_branch):
                msg("@{cf}Fast-Forwarding@|: %s (@{cf}%s@| %s @{cf}%s@|)\n" % (escape(path), escape(head_branch.shorthand), FF_LARROW, escape(master_branch.shorthand)))
                result = True
                exitcode = call_process(["git", "-C", os.path.join(srcdir, path), "merge", "--ff-only", master_branch.shorthand])
                if exitcode != 0:
                    raise Exception("fast-forward merge of %s failed" % master_branch.shorthand)
        return result

    update_projects(srcdir, packages, projects, other_git, ws_state, config, do_pull, dry_run=dry_run, action="pull", jobs=jobs)


def push_projects(srcdir, packages, projects, other_git, ws_state, config, jobs, fetch_remote=True, dry_run=False):
    def do_push(repo, path, head_branch, master_branch, tracking_branch):
        if has_pending_merge(repo):
            raise Exception("unfinished merge detected")
        if head_branch is None:
            raise Exception("detached head detected")
        result = False
        if tracking_branch is not None and need_push(repo, head_branch, tracking_branch):
            msg("@{cf}Pushing@|: %s (@{cf}%s@| %s @{cf}%s@|)\n" % (escape(path), escape(head_branch.shorthand), RARROW, escape(tracking_branch.shorthand)))
            result = True
            if not dry_run:
                exitcode = call_process(["git", "-C", os.path.join(srcdir, path), "push", tracking_branch.remote_name, "%s:%s" % (head_branch.shorthand, get_remote_branch_name(tracking_branch))])
                if exitcode != 0:
                    raise Exception("push to %s failed" % tracking_branch.shorthand)
        if master_branch is not None and repo.head.name != master_branch.name and need_push(repo, master_branch):
            msg("@{cf}Pushing@|: %s (@{cf}%s@| %s @{cf}%s@|)\n" % (escape(path), escape(head_branch.shorthand), RARROW, escape(master_branch.shorthand)))
            result = True
            if not dry_run:
                exitcode = call_process(["git", "-C", os.path.join(srcdir, path), "push", master_branch.remote_name, "%s:%s" % (head_branch.shorthand, get_remote_branch_name(master_branch))])
                if exitcode != 0:
                    raise Exception("push to %s failed" % master_branch.shorthand)
        return result

    update_projects(srcdir, packages, projects, other_git, ws_state, config, do_push, dry_run=dry_run, fetch_remote=fetch_remote, action="push", jobs=jobs)


def commit_projects(srcdir, packages, projects, other_git, ws_state, config, dry_run=False):
    def do_commit(repo, path, head_branch, master_branch, tracking_branch):
        if repo.index.conflicts:
            raise Exception("unresolved merge conflicts")
        dirty_files = [a for a, b in iteritems(repo.status()) if b != GIT_STATUS_IGNORED and b != GIT_STATUS_CURRENT]
        if dirty_files:
            msg("@{cf}Commit@|: %s\n" % path)
            if not dry_run:
                if os.environ.get("DISPLAY", "") != "":
                    call_process(["git-cola", "--repo", os.path.join(srcdir, path)])
                else:
                    call_process(["git", "-C", os.path.join(srcdir, path), "commit", "--interactive"])
            return True
        return False

    update_projects(srcdir, packages, projects, other_git, ws_state, config, do_commit, dry_run=dry_run, fetch_remote=False, action="commit", jobs=1)


def robust_merge(repo, path, merged_branch, message):
    exitcode = call_process(["git", "-C", path, "merge", "--no-commit", merged_branch.shorthand, "-m", message])
    repo.index.read()
    if repo.index.conflicts:
        exitcode = call_process(["git", "-C", path, "mergetool"])
        if exitcode != 0:
            raise Exception("merge failed")
        repo.index.read()
        if repo.index.conflicts:
            raise Exception("merge incomplete")
    elif exitcode != 0:
        raise Exception("merge failed")
    exitcode = call_process(["git", "-C", path, "commit", "-m", message])
    if exitcode != 0:
        raise Exception("merge commit failed")
    repo.index.read()


def merge_projects(srcdir, packages, projects, other_git, ws_state, config, args):
    def do_merge(repo, path, head_branch, master_branch, tracking_branch):
        git_cmd = ["git", "-C", os.path.join(srcdir, path)]
        if args.abort:
            if has_pending_merge(repo) and not args.dry_run:
                call_process(git_cmd + ["merge", "--abort"])
                return True
            return False
        if args.resolve:
            if has_pending_merge(repo) and not args.dry_run:
                call_process(git_cmd + ["mergetool"])
                return True
            return False
        if has_pending_merge(repo):
            raise Exception("unfinished previous merge")
        if master_branch is None:
            return False
        if repo.head.target == master_branch.target:
            return False
        if tracking_branch is not None:
            if tracking_branch.remote_name != master_branch.upstream.remote_name:
                raise Exception("will not merge with foreign tracking branch")
        if master_branch.target != master_branch.upstream.target and not need_push(repo, master_branch):
            raise Exception("will not merge with outdated master branch")
        result = False
        if (args.from_master or args.sync) and not is_ancestor(repo, master_branch, head_branch):
            msg("@{cf}Merging@|: %s (@{cf}%s@| %s @{cf}%s@|)\n" % (escape(path), escape(head_branch.shorthand), LARROW, escape(master_branch.shorthand)))
            result = True
            if not args.dry_run:
                robust_merge(repo, os.path.join(srcdir, path), master_branch, "Merge changes from %s into %s" % (master_branch.shorthand, head_branch.shorthand))
        if (args.to_master or args.sync) and not is_ancestor(repo, head_branch, master_branch):
            dirty_files = [a for a, b in iteritems(repo.status()) if b != GIT_STATUS_IGNORED and b != GIT_STATUS_CURRENT]
            if dirty_files:
                raise Exception("uncomitted changes in current branch")
            active_branch = head_branch.shorthand
            result = True
            if not args.dry_run:
                exitcode = call_process(git_cmd + ["checkout", master_branch.shorthand])
                if exitcode != 0:
                    raise Exception("failed to switch to '%s' branch" % master_branch.shorthand)
            if is_ancestor(repo, master_branch, head_branch):
                msg("@{cf}Fast-Forwarding@|: %s (@{cf}%s@| %s @{cf}%s@|)\n" % (escape(path), escape(head_branch.shorthand), FF_RARROW, escape(master_branch.shorthand)))
                result = True
                if not args.dry_run:
                    exitcode = call_process(git_cmd + ["merge", "--ff-only", active_branch])
                    if exitcode != 0:
                        call_process(git_cmd + ["checkout", active_branch])
                        raise Exception("fast-forward merge of %s failed" % tracking_branch.shorthand)
            else:
                msg("@{cf}Merging@|: %s (@{cf}%s@| %s @{cf}%s@|)\n" % (escape(path), escape(head_branch.shorthand), RARROW, escape(master_branch.shorthand)))
                result = True
                if not args.dry_run:
                    try:
                        robust_merge(repo, os.path.join(srcdir, path), head_branch, "Merge changes from %s into %s" % (active_branch, master_branch.shorthand))
                    except Exception:
                        msg("@!Aborting failed merge attempt\n")
                        call_process(git_cmd + ["merge", "--abort"])
            if not args.dry_run:
                exitcode = call_process(git_cmd + ["checkout", active_branch])
                if exitcode != 0:
                    raise Exception("failed to switch back to '%s' branch" % active_branch)
        return result

    if (args.from_master or args.to_master or args.sync) and not args.packages:
        fatal("you must explicitly list packages for merge operations")
    action = "merge"
    if args.abort:
        action = "abort merge"
    if args.resolve:
        action = "resolve merge"
    update_projects(srcdir, packages, projects, other_git, ws_state, config, do_merge, dry_run=args.dry_run, action=action, fetch_remote=not args.abort and not args.resolve, jobs=args.jobs)


def compute_git_subdir(srcdir, name, new_paths):
    index = 1
    result = name
    while result in new_paths or os.path.isdir(os.path.join(srcdir, result)):
        index += 1
        result = "%s-%d" % (name, index)
    new_paths.add(result)
    return result


def clone_worker(git_remote_callback, protocol, dry_run, part):
    project, path = part[0], part[1]
    try:
        if not dry_run:
            clone_repository(project.url[protocol], path, callbacks=git_remote_callback)
        else:
            msg("@{cf}Fetching@|: %s\n" % escape(textify(project.url[protocol])))
    except (GitError, AuthorizationFailed) as e:
        shutil.rmtree(path, ignore_errors=True)
        return project, str(e)
    return project, ""


def clone_packages(srcdir, packages, ws_state, config, jobs=5, protocol="ssh", offline_mode=False, dry_run=False):
    global credential_lock
    global credential_dict
    need_cloning = [(n, p) for n, p in iteritems(packages) if n not in ws_state.ws_packages and p.project not in ws_state.ws_projects]
    if not need_cloning:
        return False
    msg("@{cf}The following packages have to be cloned from Gitlab@|:\n")
    msg(escape(", ".join(sorted(n for n, _ in need_cloning)) + "\n\n"), indent=4)
    if offline_mode:
        fatal("cannot clone projects in offline mode\n")
    git_remote_callback = GitRemoteCallback(config)
    manager = create_multiprocess_manager()
    L = manager.Lock()
    d = manager.dict()
    projects = set([p.project for _, p in need_cloning])
    new_paths = set()
    workload = [(p, os.path.join(srcdir, compute_git_subdir(srcdir, p.server_path, new_paths))) for p in projects]
    result = run_multiprocess_workers(partial(clone_worker, git_remote_callback, protocol, dry_run), workload, worker_init=fetch_worker_init, worker_init_args=(L, d), jobs=jobs, timeout=900)
    errors = 0
    success = 0
    for r in result:
        project, e = r
        if e:
            error("failed to clone '%s': %s\n" % (textify(project.name), e))
            errors += 1
        else:
            success += 1
    if errors > 0:
        fatal("cloning failed")
    report = "Successfully cloned" if not dry_run else "Dry-run: would have cloned"
    if success == 1:
        msg("@!%s one repository@|\n" % report)
    elif success > 1:
        msg("@!%s %d repositories@|\n" % (report, success))
    return True


def remote_projects(srcdir, packages, projects, other_git, ws_state, args):
    if args.move_host:
        old_host, new_host = args.move_host
        for path in [project.workspace_path for project in projects] + other_git:
            repo = Repository(os.path.join(srcdir, path, ".git"))
            for remote in repo.remotes:
                old_url = remote.url
                new_url = re.sub("([/@])%s([/:])" % old_host.replace(".", "\\."), "\\1%s\\2" % new_host, old_url)
                if old_url != new_url:
                    msg("@{cf}Updating@|: %s %s %s\n" % (textify(old_url), RARROW, textify(new_url)), indent_next=10)
                    if not args.dry_run:
                        remote.url = new_url
    if args.protocol:
        for project in projects:
            repo = Repository(os.path.join(srcdir, project.workspace_path, ".git"))
            master_remote = get_origin(repo, project)
            old_url = master_remote.url
            new_url = project.url.get(args.protocol, old_url)
            if old_url != new_url:
                msg("@{cf}Updating@|: %s %s %s\n" % (textify(old_url), RARROW, textify(new_url)), indent_next=10)
                if not args.dry_run:
                    repo.remotes.set_url(master_remote.name, new_url)


def git_gc(srcdir, packages, projects, other_git, ws_state, args):
    for path in [project.workspace_path for project in projects] + other_git:
        msg("@{cf}Running@|: @!git -C %s gc@|\n" % path)
        call_process(["git", "-C", os.path.join(srcdir, path), "gc"])


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    if args.offline is None:
        args.offline = config.get("offline_mode", False)
        if args.offline:
            warning("offline mode. Run 'rosrepo config --online' to disable\n")
    srcdir = os.path.join(wsdir, "src")
    ws_state = get_workspace_state(wsdir, config, cache=cache, offline_mode=args.offline)
    if args.git_cmd == "clone":
        if args.all:
            args.packages = set(ws_state.ws_packages.keys() + ws_state.remote_packages.keys())
        if not args.packages:
            fatal("no packages specified")
        depends, system_depends, conflicts = find_dependees(args.packages, ws_state, auto_resolve=False, force_workspace=True, ignore_missing=args.ignore_missing_depends)
        if conflicts:
            show_conflicts(conflicts)
            fatal("cannot resolve dependencies\n")
        if not args.with_depends:
            depends = {n: p for n, p in iteritems(depends) if n in args.packages}
        if not clone_packages(srcdir, depends, ws_state, config, jobs=args.jobs, protocol=args.protocol or config.get("git_default_transport", "ssh"), offline_mode=args.offline, dry_run=args.dry_run):
            warning("already in workspace\n")
        missing = resolve_system_depends(ws_state, system_depends, missing_only=True)
        show_missing_system_depends(missing)
        return 0

    if args.this:
        args.packages = resolve_this(wsdir, ws_state)
    if args.packages:
        for p in args.packages:
            if p not in ws_state.ws_packages:
                fatal("package '%s' is not in workspace\n" % escape(p))
        if args.with_depends:
            packages, _, conflicts = find_dependees(args.packages, ws_state)
            show_conflicts(conflicts)
        else:
            packages = set(args.packages)
        if args.git_cmd == "status":
            args.all = True
        paths = []
        for name in packages:
            paths += [p.workspace_path for p in ws_state.ws_packages[name]]
        projects = [p for p in ws_state.ws_projects if has_package_path(p, paths)]
        other_git = [g for g in ws_state.other_git if has_package_path(g, paths)]
    else:
        packages = set(ws_state.ws_packages.keys())
        projects = ws_state.ws_projects
        other_git = ws_state.other_git
    if args.git_cmd == "status":
        show_status(srcdir, packages, projects, other_git, ws_state, show_up_to_date=args.all, cache=cache)
    if args.git_cmd == "gc":
        git_gc(srcdir, packages, projects, other_git, ws_state, args=args)
    if args.git_cmd == "diff":
        show_diff(srcdir, packages, projects, other_git, diff_staged=args.staged, diff_upstream=args.upstream, cache=cache)
    if args.git_cmd == "pull":
        pull_projects(srcdir, packages, projects, other_git, ws_state, config, jobs=args.jobs, update_local=args.update_local, merge=args.merge, dry_run=args.dry_run)
        show_status(srcdir, packages, projects, other_git, ws_state, show_up_to_date=False)
    if args.git_cmd == "push":
        push_projects(srcdir, packages, projects, other_git, ws_state, config, jobs=args.jobs, dry_run=args.dry_run)
        show_status(srcdir, packages, projects, other_git, ws_state, show_up_to_date=False)
    if args.git_cmd == "merge":
        merge_projects(srcdir, packages, projects, other_git, ws_state, config, args=args)
        show_status(srcdir, packages, projects, other_git, ws_state, show_up_to_date=False)
    if args.git_cmd == "commit":
        if args.push:
            pull_projects(srcdir, packages, projects, other_git, ws_state, config, jobs=args.jobs, dry_run=args.dry_run)
        commit_projects(srcdir, packages, projects, other_git, ws_state, config, dry_run=args.dry_run)
        if args.push:
            push_projects(srcdir, packages, projects, other_git, ws_state, config, jobs=args.jobs, fetch_remote=False, dry_run=args.dry_run)
        show_status(srcdir, packages, projects, other_git, ws_state, show_up_to_date=False)
    if args.git_cmd == "remote":
        remote_projects(srcdir, packages, projects, other_git, ws_state, args=args)
    return 0
