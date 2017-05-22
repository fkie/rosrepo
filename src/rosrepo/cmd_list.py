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
import fnmatch
from .config import Config
from .cache import Cache
from .resolver import find_dependees
from .workspace import get_workspace_location, get_workspace_state
from .ui import msg, warning, escape, TableView, show_conflicts
from .util import iteritems, is_deprecated_package


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    if args.offline is None:
        args.offline = config.get("offline_mode", False)
        if args.offline:
            warning("offline mode. Run 'rosrepo config --online' to disable\n")
    config.set_default("default_build", [])
    config.set_default("pinned_build", [])
    ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline)
    default_depends, _, default_conflicts = find_dependees(config["default_build"], ws_state)
    pinned_depends, _, pinned_conflicts = find_dependees(config["pinned_build"], ws_state)
    z = default_conflicts.copy()
    z.update(pinned_conflicts)
    show_conflicts(z)
    conflicts = set(default_conflicts.keys()) | set(pinned_conflicts.keys())
    names = set()
    table = TableView("Package", "Status", "Location")

    def filter_table_entry(name, pkg_list, status, location):
        has_been_built = os.path.isfile(os.path.join(wsdir, "build", name, "Makefile"))
        in_workspace = hasattr(pkg_list[0], "workspace_path")
        in_pinned_set = name in config["pinned_build"]
        in_default_set = name in config["default_build"]
        in_dependee_set = name in default_depends or name in pinned_depends
        in_conflict_set = name in conflicts
        show = len(args.filter) == 0
        for flt in args.filter:
            if fnmatch.fnmatch(name, flt):
                show = True
                break
        if args.workspace_only and not in_workspace:
            show = False
        if args.built_only and not has_been_built:
            show = False
        if args.default_only and not in_default_set and not (args.dependees and name in default_depends):
            show = False
        if args.pinned_only and not in_pinned_set and not (args.dependees and name in pinned_depends):
            show = False
        if args.conflicts_only and not in_conflict_set:
            show = False
        if not args.all and not args.workspace_only and not args.filter and not has_been_built and not in_default_set and not in_pinned_set and not in_dependee_set:
            show = False
        if args.invert:
            show = not show
        if not show:
            return False
        for pkg in pkg_list:
            status.append(
                ("@!@{gf}W@|" if in_workspace else ".") +
                ("@!B@|" if has_been_built else ".") +
                ("@!@{yf}S@|" if in_default_set else ".") +
                ("@!@{yf}P@|" if in_pinned_set else ".") +
                ("@!@{bf}D@|" if not in_default_set and not in_pinned_set and in_dependee_set else ".") +
                ("@!@{rf}C@|" if in_conflict_set else ".") +
                ("@!@{rf}O@|" if is_deprecated_package(pkg.manifest) else ".")
            )
            if hasattr(pkg, "workspace_path"):
                head, tail = os.path.split(pkg.workspace_path)
                path = head + "/" if tail == name else pkg.workspace_path
                location.append("@{yf}" + escape(path))
            else:
                location.append(escape(pkg.project.website))
        return True
    for name, pkg_list in iteritems(ws_state.ws_packages):
        status = []
        location = []
        upstream = next((pkg.project for pkg in pkg_list if pkg.project is not None), None)
        if filter_table_entry(name, pkg_list, status, location):
            if name in ws_state.remote_packages:
                for pkg in ws_state.remote_packages[name]:
                    status.append("       *" if upstream == pkg.project else "")
                    location.append(escape(pkg.project.website))
            table.add_row("@{yf}" + escape(name), status, location)
            names.add(name)
    for name, pkg_list in iteritems(ws_state.remote_packages):
        if name not in ws_state.ws_packages:
            status = []
            location = []
            if filter_table_entry(name, pkg_list, status, location):
                table.add_row("@{yf}" + escape(name), status, location)
                names.add(name)
    if table.empty() and not args.autocomplete:
        if not ws_state.ws_packages and not ws_state.remote_packages:
            warning("no packages\n")
        else:
            warning("no packages matched your search filter\n")
        return 0
    if args.package_names or args.autocomplete:
        sys.stdout.write("\n".join(sorted(names)) + "\n")
    else:
        table.sort(0)
        table.write(sys.stdout)
        msg("\n"
            "@!@{gf}W@|=In Workspace   "
            "@!B@|=Built   "
            "@!@{yf}S@|=Default Set   "
            "@!@{yf}P@|=Pinned   "
            "@!@{bf}D@|=Dependee   "
            "@!@{rf}C@|=Conflict   "
            "@!@{rf}O@|=Deprecated   "
            "\n", indent=2, fd=sys.stdout
            )
        sys.stdout.write("\n")
    return 0
