# encoding=utf8
"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import sys
from .config import Config
from .cache import Cache
from .resolver import find_depends
from .workspace import get_workspace_location, get_workspace_state
from .ui import msg, warning, error, TableView
from .util import iteritems


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    if not args.all and not args.build and not args.pinned:
        args.build = True
    config.set_default("default_build", [])
    config.set_default("pinned_build", [])
    ws_avail, gitlab_avail = get_workspace_state(wsdir, config, cache, offline_mode=args.offline)
    build_depends, _ = find_depends(config["default_build"], ws_avail, gitlab_avail)
    pinned_depends, _ = find_depends(config["pinned_build"], ws_avail, gitlab_avail)
    names = set()
    table = TableView("Package", "Status", "Location")
    for name, pkg_list in iteritems(ws_avail):
        if len(pkg_list) > 1:
            error("multiple versions of package '%s' in the workspace" % name)
        status = []
        location = []
        upstream = None
        for pkg in pkg_list:
            in_pinned_set = name in config["pinned_build"]
            in_build_set = name in config["default_build"]
            in_depend_set = name in build_depends or name in pinned_depends
            if upstream is None and pkg.project is not None: upstream = pkg.project
            if args.build and not in_build_set and not in_pinned_set and not in_depend_set: break
            if args.pinned and not in_pinned_set and not name in pinned_depends: break
            status.append(
                "W" + \
                ("I" if in_build_set else ".") + \
                ("A" if not in_build_set and not in_pinned_set and in_depend_set else ".") + \
                ("P" if in_pinned_set else ".") + \
                "."
            )
            location.append(pkg.workspace_path +"/")
        else:
            if name in gitlab_avail:
                for pkg in gitlab_avail[name]:
                    status.append("     U" if upstream == pkg.project else "")
                    location.append(pkg.project.website)
            table.add_row(name, status, location)
            names.add(name)
    if args.all:
        for name, pkg_list in iteritems(gitlab_avail):
            if name in ws_avail: continue
            for pkg in pkg_list:
                status = "...." + ("M" if name in build_depends | pinned_depends else ".")
                location = pkg.project.website
                table.add_row(name, status, location)
                names.add(name)
    if args.name_only:
        sys.stdout.write("\n".join(sorted(names))+"\n")
    else:
        table.sort(0)
        table.write(sys.stdout)
        msg("\n"
            "@!W@|=In Workspace   "
            "@!I@|=Included   "
            "@!A@|=Auto-Included   "
            "@!P@|=Pinned (always built)   "
            "@!U@|=Upstream   "
            "@!M@|=Missing   "
            "\n", initial_indent="  ", subsequent_indent="  "
            )
        sys.stdout.write("\n")

