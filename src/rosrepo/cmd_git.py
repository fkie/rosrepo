"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import os
import sys
from .workspace import get_workspace_location
from .config import Config
from .cache import Cache
from .gitlab import get_gitlab_projects, find_cloned_gitlab_projects
from .ui import TableView
from .util import iteritems
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


def show_status(args, srcdir, projects, other_git):
    def create_status(repo, origin, remote_branch, warn_remote=False):
        status = []
        if repo.is_dirty(index=True, working_tree=True, untracked_files=True):
            status.append("@!@{yf}uncommitted changes")
        if remote_branch is not None:
            if repo.remote(remote_branch.remote_name) != origin:
                status.append("@!@{rf}invalid upstream")
            if need_push(repo, remote_branch):
                status.append("@!@{yf}need push")
            elif need_pull(repo, remote_branch):
                status.append("@!@{cf}need pull")
            elif repo.head.reference.commit.binsha != remote_branch.commit.binsha:
                status.append("@!@{yf}need merge")
        elif warn_remote:
                status.append("@!@{rf}untracked branch")
        if not status:
            status.append("@!@{gf}up-to-date")
        return status

    table = TableView("Path", "Project", "Status")

    for project in projects:
        repo = Repo(os.path.join(srcdir, project.workspace_path))
        remote_branch = repo.head.reference.tracking_branch()
        origin = get_origin(repo, project)
        if remote_branch is not None:
            remote = repo.remote(remote_branch.remote_name)
            if not args.offline:
                remote.fetch()
                if origin != remote:
                    origin.fetch()
        status = create_status(repo, origin, remote_branch, warn_remote=True)
        if status is not None:
            table.add_row(project.workspace_path, project.name, status)

    for path in other_git:
        repo = Repo(os.path.join(srcdir, path))
        remote_branch = repo.head.reference.tracking_branch()
        if remote_branch is not None:
            remote = repo.remote(remote_branch.remote_name)
            if not args.offline:
                remote.fetch()
        status = create_status(repo, remote, remote_branch)
        if status is not None:
            table.add_row(path, "-", status)
    table.sort(0)
    table.write(sys.stdout)


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    srcdir = os.path.join(wsdir, "src")
    gitlab_projects = get_gitlab_projects(wsdir, config, cache=cache, offline_mode=args.offline)
    projects, other_git = find_cloned_gitlab_projects(gitlab_projects, srcdir)
    if args.git_cmd == "status":
        show_status(args, srcdir, projects, other_git)
