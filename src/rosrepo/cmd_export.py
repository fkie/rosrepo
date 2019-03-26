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
from .workspace import get_workspace_location, get_workspace_state, resolve_this
from .cache import Cache
from .config import Config
from .resolver import find_dependees
from .ui import warning, fatal, show_conflicts
from .cmd_git import has_package_path, get_head_branch
from .util import iteritems, yaml_dump
from pygit2 import Repository
import os


def compute_git_subdir(name, used_paths):
    index = 1
    result = name
    while result in used_paths:
        index += 1
        result = "%s-%d" % (name, index)
    used_paths.add(result)
    return result


def get_current_remote(path):
    repo = Repository(os.path.join(path, ".git"))
    if not repo.remotes:
        warning("no remote found for Git repository in %s\n" % path)
        return None, None
    head_branch = get_head_branch(repo)
    tracking_branch = head_branch.upstream if head_branch else None
    remote_name = tracking_branch.remote_name if tracking_branch else None
    remote = repo.remotes[remote_name] if remote_name else repo.remotes[0]
    url = remote.url
    version = None
    if tracking_branch:
        b = tracking_branch.branch_name
        if b.startswith(remote_name + "/"):
            b = b[len(remote_name) + 1:]
            version = b
    return url, version


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    if args.offline is None:
        args.offline = config.get("offline_mode", False)
        if args.offline:
            warning("offline mode. Run 'rosrepo config --online' to disable\n")
    ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline)
    if args.this:
        args.packages = resolve_this(wsdir, ws_state)
    if args.all:
        args.packages = ws_state.ws_packages.keys()
    if not args.packages:
        args.packages = config.get("default_build", []) + config.get("pinned_build", [])
    protocol = args.protocol or config.get("git_default_transport", "ssh")
    depends, _, conflicts = find_dependees(args.packages, ws_state)
    show_conflicts(conflicts)
    if conflicts:
        fatal("cannot resolve dependencies\n")

    paths = set()
    remote_projects = set()
    for name, pkg in iteritems(depends):
        if hasattr(pkg, "workspace_path") and pkg.workspace_path is not None:
            paths.add(pkg.workspace_path)
        elif name in ws_state.remote_packages:
            remote_projects.add(pkg.project)
    ws_projects = set([p for p in ws_state.ws_projects if has_package_path(p, paths)])
    other_git = set([g for g in ws_state.other_git if has_package_path(g, paths)])
    yaml = []
    for prj in ws_projects:
        url, version = get_current_remote(os.path.join(wsdir, "src", prj.workspace_path))
        if args.protocol:
            url = prj.url[args.protocol]
        packages = {}
        for p in prj.packages:
            if p.manifest.name in depends.keys():
                packages[p.manifest.name] = p.project_path or "."
        meta = {"packages": packages}
        d = {"local-name": prj.workspace_path, "uri": url, "meta": meta}
        if version:
            d["version"] = version
        yaml.append({"git": d})
    for p in other_git:
        url, version = get_current_remote(os.path.join(wsdir, "src", p))
        d = {"local-name": p, "uri": url}
        if version:
            d["version"] = version
        yaml.append({"git": d})
    for prj in remote_projects:
        packages = {}
        for p in prj.packages:
            if p.manifest.name in depends.keys():
                packages[p.manifest.name] = p.project_path or "."
        meta = {"packages": packages}
        d = {"local-name": compute_git_subdir(prj.server_path, paths), "uri": prj.url[protocol], "version": prj.master_branch, "meta": meta}
        yaml.append({"git": d})
    if yaml:
        args.output.write(yaml_dump(yaml, encoding="UTF-8", default_flow_style=False))
