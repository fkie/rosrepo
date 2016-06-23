# encoding=utf8
"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import os
import sys
from .config import Config
from .cache import Cache
from .resolver import find_dependees
from .workspace import get_workspace_location, get_workspace_state
from .ui import msg, warning, error, TableView
from .util import iteritems


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    config.set_default("default_build", [])
    config.set_default("pinned_build", [])
    ws_avail, gitlab_avail = get_workspace_state(wsdir, config, cache, offline_mode=args.offline)
    default_depends, default_missing = find_dependees(config["default_build"], ws_avail, gitlab_avail)
    pinned_depends, pinned_missing = find_dependees(config["pinned_build"], ws_avail, gitlab_avail)
    for name in default_missing | pinned_missing:
        warning("cannot resolve depend '%s'" % name)
    names = set()
    table = TableView("Package", "Status", "Location")
    def filter_table_entry(name, pkg_list, status, location):
        if len(pkg_list) == 0: return False
        has_been_built = os.path.isfile(os.path.join(wsdir, "build", name, "Makefile"))
        in_workspace = hasattr(pkg_list[0], "workspace_path")
        in_pinned_set = name in config["pinned_build"]
        in_default_set = name in config["default_build"]
        in_dependee_set = name in default_depends or name in pinned_depends
        show = True
        if args.workspace_only and not in_workspace: show = False
        if args.built_only and not has_been_built: show = False
        if args.default_set_only and not in_default_set and not (args.dependees and name in default_depends): show = False
        if args.pinned_set_only and not in_pinned_set and not (args.dependees and name in pinned_depends): show = False
        if not args.all and not args.workspace_only and not has_been_built and not in_default_set and not in_pinned_set and not in_dependee_set: show = False
        if args.invert: show = not show
        if not show: return False
        for pkg in pkg_list:
            status.append(
                ("W" if in_workspace else ".") + \
                ("B" if has_been_built else ".") + \
                ("S" if in_default_set else ".") + \
                ("P" if in_pinned_set else ".") + \
                ("D" if not in_default_set and not in_pinned_set and in_dependee_set else ".")
            )
            if hasattr(pkg, "workspace_path"):
                location.append(pkg.workspace_path +"/")
            else:
                location.append(pkg.project.website)
        return True
    for name, pkg_list in iteritems(ws_avail):
        if len(pkg_list) > 1:
            error("multiple versions of package '%s' in the workspace" % name)
        status = []
        location = []
        upstream = next((pkg.project for pkg in pkg_list if pkg.project is not None), None)
        if filter_table_entry(name, pkg_list, status, location):
            if name in gitlab_avail:
                for pkg in gitlab_avail[name]:
                    status.append("     U" if upstream == pkg.project else "")
                    location.append(pkg.project.website)
            table.add_row(name, status, location)
            names.add(name)
    for name, pkg_list in iteritems(gitlab_avail):
        if name in ws_avail: continue
        status = []
        location = []
        if filter_table_entry(name, pkg_list, status, location):
            table.add_row(name, status, location)
            names.add(name)
    if table.empty():
        warning("no packages matched your search filter")
        return 0
    if args.package_names:
        sys.stdout.write("\n".join(sorted(names))+"\n")
    else:
        table.sort(0)
        table.write(sys.stdout)
        msg("\n"
            "@!W@|=In Workspace   "
            "@!B@|=Built   "
            "@!S@|=Default Set   "
            "@!D@|=Dependee   "
            "@!P@|=Pinned   "
            "@!U@|=Upstream   "
            "\n", indent_first=2, indent_next=2
            )
        sys.stdout.write("\n")
    return 0
