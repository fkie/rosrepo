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
from .workspace import find_ros_root, get_workspace_location, get_workspace_state, WSFL_WS_PACKAGES
from .cmd_git import clone_packages
from .resolver import find_dependees, show_fallback, show_conflicts
from .config import Config
from .cache import Cache
from .ui import msg, fatal, escape
from .util import call_process, find_program, iteritems, getmtime, PIPE


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    config.set_default("default_build", [])
    config.set_default("pinned_build", [])
    ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline)
    if args.all:
        args.packages = ws_state.ws_packages.keys()
    if args.set_default:
        if args.packages:
            msg("@{cf}Replacing default build set with@|:\n")
            msg(", ".join(sorted(args.packages)) + "\n\n", indent_first=4, indent_next=4)
        else:
            fatal("No packages given for new default build")
        config["default_build"] = sorted(args.packages)
    if args.set_pinned:
        if args.packages:
            msg("@{cf}Replacing pinned build set with@|:\n")
            msg(", ".join(sorted(args.packages)) + "\n\n", indent_first=4, indent_next=4)
        else:
            fatal("No packages given to be pinned")
        config["pinned_build"] = sorted(args.packages)
    srcdir = os.path.join(wsdir, "src")
    pinned_set = set(config["pinned_build"])
    if args.packages:
        build_set = set(args.packages)
        if build_set:
            msg("@{cf}You selected the following packages to be built@|:\n")
            msg(", ".join(sorted(list(build_set))) + "\n\n", indent_first=4, indent_next=4)
    else:
        build_set = set(config["default_build"])
        if build_set:
            msg("@{cf}The following packages are included in the default build@|:\n")
            msg(", ".join(sorted(list(build_set))) + "\n\n", indent_first=4, indent_next=4)
    if pinned_set - build_set:
        if build_set:
            msg("@{cf}The following pinned packages will also be built@|:\n")
        else:
            msg("@{cf}The following pinned packages will be built@|:\n")
        msg(", ".join(sorted(list(pinned_set - build_set))) + "\n\n", indent_first=4, indent_next=4)
    build_set |= pinned_set
    if not build_set:
        fatal("no packages to build")
    build_packages, fallback, conflicts = find_dependees(build_set, ws_state)
    show_fallback(fallback)
    show_conflicts(conflicts)
    if conflicts:
        fatal("cannot resolve dependencies")

    if not args.dry_run:
        config.write()

    depend_set = set(build_packages.keys()) - build_set
    if depend_set:
        msg("@{cf}The following additional packages are needed to satisfy all dependencies@|:\n")
        msg(", ".join(sorted(depend_set)) + "\n\n", indent_first=4, indent_next=4)
    clone_packages(srcdir, build_packages, ws_state, protocol=args.protocol, offline_mode=args.offline, dry_run=args.dry_run)
    ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline, ws_state=ws_state, flags=WSFL_WS_PACKAGES)
    build_packages, fallback, conflicts = find_dependees(build_set, ws_state)
    show_fallback(fallback)
    show_conflicts(conflicts)
    assert not conflicts

    if args.clean:
        invoke = ["catkin", "clean", "--workspace", wsdir, "--all", "--yes"]
        if args.dry_run:
            msg("@{cf}Invoking@|: %s\n" % escape(" ".join(invoke)), indent_next=11)
        else:
            call_process(invoke)

    catkin_build = ["catkin", "build", "--workspace", wsdir]
    if args.dry_run:
        catkin_build += ["--dry-run"]
    if args.verbose:
        catkin_build += ["--verbose"]
    if args.no_status:
        catkin_build += ["--no-status"]
    if args.keep_going:
        catkin_build += ["--continue-on-failure"]

    if args.jobs:
        catkin_build += ["--jobs", args.jobs]
    elif "job_limit" in config:
        catkin_build += ["--jobs", config["job_limit"]]

    catkin_build += build_packages.keys()

    if args.verbose:
        catkin_build += ["--make-args", "VERBOSE=ON", "--"]

    ret = call_process(catkin_build)

    rosclipse = find_program("rosclipse")
    if rosclipse is not None and (args.force_rosclipse or config.get("use_rosclipse", True)) and not args.no_rosclipse:
        eclipse_ok, _, _ = call_process([rosclipse, "-d"], stdout=PIPE, stderr=PIPE)
        if eclipse_ok == 0:
            for name, pkg in iteritems(build_packages):
                if not pkg.manifest.is_metapackage() and hasattr(pkg, "workspace_path") and pkg.workspace_path is not None:
                    pkgdir = os.path.join(wsdir, "src", pkg.workspace_path)
                    p_time = max(getmtime(os.path.join(pkgdir, "CMakeLists.txt")), getmtime(os.path.join(pkgdir, "package.xml")))
                    e_time = min(getmtime(os.path.join(pkgdir, ".project")), getmtime(os.path.join(pkgdir, ".cproject")), getmtime(os.path.join(pkgdir, ".settings", "language.settings.xml")))
                    if e_time < p_time or args.force_rosclipse:
                        msg("@{cf}Updating project files for '%s'@|\n" % name)
                        if not args.dry_run:
                            call_process([rosclipse, name])
    return ret
