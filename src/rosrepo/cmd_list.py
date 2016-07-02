# coding=utf-8
#
# ROSREPO
# Manage ROS workspaces with multiple Gitlab repositories
#
# Author: Timo Röhling
#
# Copyright (c) 2016 Fraunhofer FKIE
#
#
import os
import sys
from .config import Config
from .cache import Cache
from .resolver import find_dependees, show_conflicts, show_fallback
from .workspace import get_workspace_location, get_workspace_state
from .ui import msg, warning, error, escape, TableView
from .util import iteritems


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    config.set_default("default_build", [])
    config.set_default("pinned_build", [])
    ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline)
    default_depends, default_fallback, default_conflicts = find_dependees(config["default_build"], ws_state)
    pinned_depends, pinned_fallback, pinned_conflicts = find_dependees(config["pinned_build"], ws_state)
    z = default_fallback.copy()
    z.update(pinned_fallback)
    show_fallback(z)
    z = default_conflicts.copy()
    z.update(pinned_conflicts)
    show_conflicts(z)
    conflicts = set(default_conflicts.keys()) | set(pinned_conflicts.keys()) | set(default_fallback.keys()) | set(pinned_fallback.keys())
    names = set()
    table = TableView("Package", "Status", "Location")

    def filter_table_entry(name, pkg_list, status, location):
        if len(pkg_list) == 0:
            return False
        has_been_built = os.path.isfile(os.path.join(wsdir, "build", name, "Makefile"))
        in_workspace = hasattr(pkg_list[0], "workspace_path")
        in_pinned_set = name in config["pinned_build"]
        in_default_set = name in config["default_build"]
        in_dependee_set = name in default_depends or name in pinned_depends
        in_conflict_set = name in conflicts
        show = True
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
        if not args.all and not args.workspace_only and not has_been_built and not in_default_set and not in_pinned_set and not in_dependee_set:
            show = False
        if args.invert:
            show = not show
        if not show:
            return False
        for pkg in pkg_list:
            status.append(
                ("@!@{gf}W@|" if in_workspace else ".") +
                ("@!@{gf}B@|" if has_been_built else ".") +
                ("@!S@|" if in_default_set else ".") +
                ("@!P@|" if in_pinned_set else ".") +
                ("@!@{bf}D@|" if not in_default_set and not in_pinned_set and in_dependee_set else ".") +
                ("@!@{rf}C@|" if in_conflict_set else ".")
            )
            if hasattr(pkg, "workspace_path"):
                head, tail = os.path.split(pkg.workspace_path)
                path = head + "/" if tail == name else pkg.workspace_path
                location.append("@{yf}" + escape(path))
            else:
                location.append(escape(pkg.project.website))
        return True
    for name, pkg_list in iteritems(ws_state.ws_packages):
        if len(pkg_list) > 1:
            error("multiple versions of package '%s' in the workspace" % escape(name))
        status = []
        location = []
        upstream = next((pkg.project for pkg in pkg_list if pkg.project is not None), None)
        if filter_table_entry(name, pkg_list, status, location):
            if name in ws_state.remote_packages:
                for pkg in ws_state.remote_packages[name]:
                    status.append("      *" if upstream == pkg.project else "")
                    location.append(escape(pkg.project.website))
            table.add_row("@{yf}" + escape(name), status, location)
            names.add(name)
    for name, pkg_list in iteritems(ws_state.remote_packages):
        if name in ws_state.ws_packages:
            continue
        status = []
        location = []
        if filter_table_entry(name, pkg_list, status, location):
            table.add_row("@{yf}" + escape(name), status, location)
            names.add(name)
    if table.empty() and not args.autocomplete:
        warning("no packages matched your search filter\n")
        return 0
    if args.package_names or args.autocomplete:
        sys.stdout.write("\n".join(sorted(names)) + "\n")
    else:
        table.sort(0)
        table.write(sys.stdout)
        msg("\n"
            "@!@{gf}W@|=In Workspace   "
            "@!@{gf}B@|=Built   "
            "@!S@|=Default Set   "
            "@!P@|=Pinned   "
            "@!@{bf}D@|=Dependee   "
            "@!@{rf}C@|=Conflict   "
            "\n", indent_first=2, indent_next=2, fd=sys.stdout
            )
        sys.stdout.write("\n")
    return 0
