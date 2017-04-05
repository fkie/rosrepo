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
from .workspace import get_workspace_location, get_workspace_state, resolve_this
from .config import Config
from .cache import Cache
from .ui import msg
from .util import call_process
import os
try:
    from os import scandir
except ImportError:
    from scandir import scandir


def run(args):
    wsdir = get_workspace_location(args.workspace)
    if args.this:
        config = Config(wsdir)
        cache = Cache(wsdir)
        ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline)
        args.packages = resolve_this(wsdir, ws_state)
    elif args.vanished:
        config = Config(wsdir)
        cache = Cache(wsdir)
        ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline)
        args.packages = []
        for d in scandir(os.path.join(wsdir, "build")):
            if d.is_dir() and d.name not in ws_state.ws_packages and not d.name == "catkin_tools_prebuild":
                args.packages.append(d.name)
        if not args.packages:
            msg("Nothing to clean\n")
            return 0

    catkin_clean = ["catkin", "clean", "--workspace", wsdir, "--yes"]
    if args.dry_run:
        catkin_clean.append("--dry-run")
    catkin_clean += args.packages or ["--all"]
    return call_process(catkin_clean)
