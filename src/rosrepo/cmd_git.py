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
import shutil
from .workspace import get_workspace_location, get_workspace_state, find_catkin_packages
from .config import Config
from .cache import Cache
from .resolver import find_dependees, resolve_system_depends
from .ui import TableView, msg, warning, error, fatal, escape, show_conflicts, show_missing_system_depends
from .util import iteritems, path_has_prefix, makedirs, call_process
from git import Repo, GitCommandError


def is_ancestor(repo, ancestor_rev, rev):
    try:
        repo.git.merge_base(ancestor_rev, rev, is_ancestor=True)
    except GitCommandError as err:
        if err.status == 1:
            return False
        raise
    return True


def need_push(repo, remote_branch):
    return is_ancestor(repo, remote_branch, repo.head.reference) and not is_ancestor(repo, repo.head.reference, remote_branch)


def need_pull(repo, remote_branch):
    return not is_ancestor(repo, remote_branch, repo.head.reference) and is_ancestor(repo, repo.head.reference, remote_branch)


def get_origin(repo, project):
    for r in repo.remotes:
        for _, url in iteritems(project.url):
            if r.url == url:
                return r
    return None


def show_status(srcdir, packages, projects, other_git, ws_state, show_up_to_date=True, cache=None):
    def create_status(repo, master_branch, tracking_branch):
        status = []
        if repo.is_dirty(index=True, working_tree=True, untracked_files=True):
            status.append("@!@{yf}needs commit")
        is_local_branch = False
        if tracking_branch is None:
            if master_branch is not None:
                tracking_branch = master_branch
                is_local_branch = True
            else:
                status.append("@!@{rf}no remote")
        if tracking_branch is not None:
            if need_push(repo, tracking_branch):
                status.append("@!@{yf}needs push")
            elif need_pull(repo, tracking_branch):
                status.append("@!@{cf}needs pull")
            elif repo.head.reference.commit.binsha != tracking_branch.commit.binsha:
                status.append("@!@{yf}needs merge")
        if tracking_branch != master_branch and master_branch is not None:
            if repo.head.reference.commit.binsha != master_branch.commit.binsha:
                status.append("@!@{yf}other remote")
        if not status:
            if not show_up_to_date:
                return None
            status.append("@!@{gf}up-to-date")
        elif is_local_branch:
            status.append("@{yf}local branch")
        return status

    table = TableView("Package", "Path", "Status")

    found_packages = set()
    for project in projects:
        repo = Repo(os.path.join(srcdir, project.workspace_path))
        tracking_branch = repo.head.reference.tracking_branch()
        origin = get_origin(repo, project)
        master_branch = origin.refs[project.master_branch] if origin is not None else None
        ws_packages = find_catkin_packages(srcdir, project.workspace_path, cache=cache)
        found_packages |= set(ws_packages.keys())
        status = create_status(repo, master_branch, tracking_branch)
        if status is not None:
            for name, pkg_list in iteritems(ws_packages):
                if name not in packages:
                    continue
                path_list = []
                for pkg in pkg_list:
                    head, tail = os.path.split(pkg.workspace_path)
                    path_list.append(escape(head + "/" if tail == name else pkg.workspace_path))
                table.add_row(escape(name), path_list, status)

    for path in other_git:
        repo = Repo(os.path.join(srcdir, path))
        tracking_branch = repo.head.reference.tracking_branch()
        ws_packages = find_catkin_packages(srcdir, path, cache=cache)
        found_packages |= set(ws_packages.keys())
        status = create_status(repo, None, tracking_branch)
        if status is not None:
            for name, pkg_list in iteritems(ws_packages):
                if name not in packages:
                    continue
                path_list = []
                for pkg in pkg_list:
                    head, tail = os.path.split(pkg.workspace_path)
                    path_list.append(head + "/" if tail == name else pkg.workspace_path)
                table.add_row(name, path_list, status)
    missing = set(packages) - found_packages
    for name in missing:
        path_list = []
        if name in ws_state.ws_packages:
            for pkg in ws_state.ws_packages[name]:
                head, tail = os.path.split(pkg.workspace_path)
                path_list.append(escape(head + "/" if tail == name else pkg.workspace_path))
        table.add_row(escape(name), path_list, "no git")
    table.sort(0)
    table.write(sys.stdout)


def has_package_path(obj, paths):
    for path in paths:
        if path_has_prefix(path, obj.workspace_path if hasattr(obj, "workspace_path") else obj):
            return True
    return False


def update_projects(srcdir, packages, projects, other_git, ws_state, update_op, dry_run=False):
    for project in projects:
        repo = Repo(os.path.join(srcdir, project.workspace_path))
        master_remote = get_origin(repo, project)
        master_branch = master_remote.refs[project.master_branch] if master_remote is not None else None
        tracking_branch = repo.head.reference.tracking_branch()
        if tracking_branch is None:
            tracking_branch = master_branch
            tracking_remote = master_remote
        else:
            tracking_remote = repo.remote(tracking_branch.remote_name)
        try:
            if master_remote is not None:
                msg("@{cf}Fetching@|: %s\n" % escape(master_remote.url))
                if not dry_run:
                    master_remote.fetch()
            if tracking_remote is not None and master_remote != tracking_remote:
                msg("@{cf}Fetching@|: %s\n" % escape(tracking_remote.url))
                if not dry_run:
                    tracking_remote.fetch()
            if tracking_branch is not None:
                update_op(repo, project.workspace_path, master_remote, master_branch, tracking_remote, tracking_branch)
        except Exception as e:
            error("cannot update '%s': %s\n" % (escape(project.name), escape(str(e))))
    for path in other_git:
        repo = Repo(os.path.join(srcdir, path))
        tracking_branch = repo.head.reference.tracking_branch()
        if tracking_branch is not None:
            tracking_remote = repo.remote(tracking_branch.remote_name)
            try:
                msg("@{cf}Fetching@|: %s\n" % escape(tracking_remote.url))
                if not dry_run:
                    tracking_remote.fetch()
                update_op(repo, path, None, None, tracking_remote, tracking_branch)
            except Exception as e:
                error("cannot update '%s': %s\n" % (escape(path), escape(str(e))))
    show_status(srcdir, packages, projects, other_git, ws_state)


def pull_projects(srcdir, packages, projects, other_git, ws_state, dry_run=False):
    def do_pull(repo, path, master_remote, master_branch, tracking_remote, tracking_branch):
        if need_pull(repo, tracking_branch):
            invoke = ["git", "-C", os.path.join(srcdir, path), "merge", "--ff-only", str(tracking_branch)]
            if dry_run:
                msg("@{cf}Invoking@|: %s\n" % escape(" ".join(invoke)), indent_next=11)
            else:
                call_process(invoke)
    update_projects(srcdir, packages, projects, other_git, ws_state, do_pull, dry_run=dry_run)


def push_projects(srcdir, packages, projects, other_git, ws_state, dry_run=False):
    def do_push(repo, path, master_remote, master_branch, tracking_remote, tracking_branch):
        if need_push(repo, tracking_branch):
            invoke = ["git", "-C", os.path.join(srcdir, path), "push", str(tracking_remote), "%s:%s" % (str(repo.head.reference), str(tracking_branch.remote_head))]
            if dry_run:
                msg("@{cf}Invoking@|: %s\n" % escape(" ".join(invoke)), indent_next=11)
            else:
                call_process(invoke)

    update_projects(srcdir, packages, projects, other_git, ws_state, do_push, dry_run=dry_run)


def compute_git_subdir(srcdir, name):
    index = 1
    result = name
    while os.path.isdir(os.path.join(srcdir, result)):
        index += 1
        result = "%s-%d" % (name, index)
    return result


def clone_packages(srcdir, packages, ws_state, protocol="ssh", offline_mode=False, dry_run=False):
    need_cloning = [(n, p) for n, p in iteritems(packages) if n not in ws_state.ws_packages and p.project not in ws_state.ws_projects]
    if not need_cloning:
        return False
    msg("@{cf}The following packages have to be cloned from Gitlab@|:\n")
    msg(escape(", ".join(sorted(n for n, _ in need_cloning)) + "\n\n"), indent=4)
    if offline_mode:
        fatal("cannot clone projects in offline mode")
    projects = list(set(p.project for _, p in need_cloning))
    for project in projects:
        git_subdir = compute_git_subdir(srcdir, project.server_path)
        gitdir = os.path.join(srcdir, git_subdir)
        msg("@{cf}Cloning@|: %s\n" % escape(git_subdir))
        if protocol not in project.url:
            fatal("unsupported procotol type: %s\n" % protocol)
        invoke = ["git", "-C", srcdir, "clone", project.url[protocol], git_subdir]
        if not dry_run:
            makedirs(gitdir)
            if call_process(invoke) != 0:
                shutil.rmtree(gitdir, ignore_errors=True)
                fatal("failed to clone repository")
        else:
            msg("@{cf}Invoking@|: %s\n" % escape(" ".join(invoke)), indent_next=11)
        msg("\n")
    return True


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    srcdir = os.path.join(wsdir, "src")
    ws_state = get_workspace_state(wsdir, config, cache=cache, offline_mode=args.offline)
    if args.git_cmd == "commit":
        if args.package not in ws_state.ws_packages:
            fatal("package '%s' is not in workspace" % escape(args.package))
        invoke = ["git-cola", "--repo", os.path.join(srcdir, ws_state.ws_packages[args.package][0].workspace_path)]
        if args.dry_run:
            msg("@{cf}Invoking@|: %s\n" % escape(" ".join(invoke)), indent_next=11)
            return 0
        else:
            return call_process(invoke)
    if args.git_cmd == "clone":
        depends, system_depends, conflicts = find_dependees(args.packages, ws_state, auto_resolve=False)
        if conflicts:
            show_conflicts(conflicts)
            fatal("cannot resolve dependencies")
        if not clone_packages(srcdir, depends, ws_state, protocol=args.protocol, offline_mode=args.offline, dry_run=args.dry_run):
            warning("already in workspace\n")
        missing = resolve_system_depends(system_depends, missing_only=True)
        show_missing_system_depends(missing)
        return 0

    if args.packages:
        for p in args.packages:
            if p not in ws_state.ws_packages:
                fatal("package '%s' is not in workspace" % escape(p))
        if args.no_depends:
            packages = set(args.packages)
        else:
            packages, _, conflicts = find_dependees(args.packages, ws_state)
            show_conflicts(conflicts)
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
        show_status(srcdir, packages, projects, other_git, ws_state, show_up_to_date=not args.modified, cache=cache)
    if args.git_cmd == "pull":
        pull_projects(srcdir, packages, projects, other_git, ws_state, dry_run=args.dry_run)
    if args.git_cmd == "push":
        push_projects(srcdir, packages, projects, other_git, ws_state, dry_run=args.dry_run)
    return 0
