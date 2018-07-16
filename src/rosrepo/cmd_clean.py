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
from .workspace import get_workspace_location, get_workspace_state, resolve_this, find_ros_root
from .config import Config
from .cache import Cache
from .ui import msg, warning, fatal, show_conflicts
from .util import call_process, PIPE
from .resolver import find_dependees
import os
try:
    from os import scandir
except ImportError:
    from scandir import scandir


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    ros_rootdir = find_ros_root(config.get("ros_root", None))
    if ros_rootdir is None:
        fatal("cannot detect ROS distribution. Have you sourced your setup.bash?\n")

    if args.this:
        if args.offline is None:
            args.offline = config.get("offline_mode", False)
            if args.offline:
                warning("offline mode. Run 'rosrepo config --online' to disable\n")
        ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline)
        args.packages = resolve_this(wsdir, ws_state)
    elif args.vanished or args.unused:
        if args.offline is None:
            args.offline = config.get("offline_mode", False)
            if args.offline:
                warning("offline mode. Run 'rosrepo config --online' to disable\n")
        ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline)
        args.packages = []
        for d in scandir(os.path.join(wsdir, "build")):
            if d.is_dir() and d.name not in ws_state.ws_packages and not d.name == "catkin_tools_prebuild":
                args.packages.append(d.name)
        if args.unused:
            depends, _, conflicts = find_dependees(config["pinned_build"] + config["default_build"], ws_state, ignore_missing=True)
            show_conflicts(conflicts)
            if conflicts:
                fatal("cannot resolve dependencies\n")
            unused_packages = set(ws_state.ws_packages) - set(depends.keys())
            args.packages += [p for p in unused_packages if os.path.isdir(os.path.join(wsdir, "build", p))]
        if not args.packages:
            msg("Nothing to clean\n")
            return 0

    if not args.dry_run:
        invoke = ["catkin", "config", "--extend", ros_rootdir]
        call_process(invoke, stdout=PIPE, stderr=PIPE)
        config["last_ros_root"] = ros_rootdir
        config.write()

    catkin_clean = ["catkin", "clean", "--workspace", wsdir, "--yes"]
    if args.dry_run:
        catkin_clean.append("--dry-run")
    catkin_clean += args.packages or ["--all"]
    return call_process(catkin_clean)
