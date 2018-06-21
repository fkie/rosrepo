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
from .workspace import get_workspace_location, get_workspace_state
from .config import Config
from .cache import Cache
from .ui import warning
from .util import has_package_path


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    if args.offline is None and not args.autocomplete:
        args.offline = config.get("offline_mode", False)
        if args.offline:
            warning("offline mode. Run 'rosrepo config --online' to disable\n")
    srcdir = os.path.join(wsdir, "src")
    ws_state = get_workspace_state(wsdir, config, cache=cache, offline_mode=args.offline or args.autocomplete)
    ret_value = 0
    for name in args.packages:
        if name in ws_state.ws_packages:
            path = ws_state.ws_packages[name][0].workspace_path
            git_path = None
            for p in ws_state.ws_projects:
                if has_package_path(p, [path]):
                    git_path = os.path.join(srcdir, p.workspace_path)
                    break
            else:
                for p in ws_state.other_git:
                    if has_package_path(p, [path]):
                        git_path = os.path.join(srcdir, p)
                        break
            if args.git:
                print(git_path or "")
            else:
                print(os.path.join(srcdir, path))
        else:
            ret_value = 1
            print("")
    return ret_value
