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
from .resolver import find_dependers, find_dependees
from .config import Config
from .cache import Cache
from .ui import warning, error, TableView, escape
import sys


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

    table = TableView("Package", "Depends On", "Used By")
    for pkg in args.packages:
        if pkg not in ws_state.ws_packages and pkg not in ws_state.remote_packages and pkg not in ws_state.ros_root_packages:
            rdepends, system_rdepends = find_dependers([pkg], ws_state)
            dependers = []
            for dep in sorted(list(rdepends)):
                if dep in ws_state.ws_packages:
                    dependers.append("@{gf}%s@|" % escape(dep))
                else:
                    dependers.append("@{yf}%s@|" % escape(dep))
            for dep in sorted(list(system_rdepends)):
                dependers.append(escape(dep))
            table.add_row("@{rf}%s@|" % escape(pkg), "", dependers)
        else:
            rdepends, system_rdepends = find_dependers([pkg], ws_state)
            depends, system_depends, conflicts = find_dependees([pkg], ws_state, auto_resolve=True)
            dependers = []
            for dep in sorted(list(rdepends)):
                if dep in ws_state.ws_packages:
                    dependers.append("@{gf}%s@|" % escape(dep))
                else:
                    dependers.append("@{yf}%s@|" % escape(dep))
            for dep in sorted(list(system_rdepends)):
                dependers.append(escape(dep))
            dependees = []
            for dep in sorted(depends.keys()):
                if dep != pkg:
                    if dep in ws_state.ws_packages:
                        dependees.append("@{gf}%s@|" % escape(dep))
                    else:
                        dependees.append("@{yf}%s@|" % escape(dep))
            for dep in sorted(system_depends):
                if dep != pkg:
                    dependees.append(escape(dep))
            for dep in sorted(conflicts.keys()):
                if dep != pkg:
                    dependees.append("@{rf}%s@|" % escape(dep))
            table.add_row("@{cf}%s@|" % escape(pkg), dependees, dependers)
    table.sort(0)
    table.write(sys.stdout)
    sys.stdout.write("\n")
    return 0
