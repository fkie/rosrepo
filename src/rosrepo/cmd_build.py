"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import os
from .workspace import get_workspace_location, get_workspace_state
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
    if args.set_default:
        if args.packages:
            msg("@{cf}Replacing default build set with@|:\n")
            msg(", ".join(sorted(args.packages)) + "\n\n", indent_first=4, indent_next=4)
        else:
            msg("@{cf}Clearing default build set@|\n\n")
        config["default_build"] = sorted(args.packages)
        config.write()
    if args.set_pinned:
        if args.packages:
            msg("@{cf}Replacing pinned build set with@|:\n")
            msg(", ".join(sorted(args.packages)) + "\n\n", indent_first=4, indent_next=4)
        else:
            msg("@{cf}Clearing pinned build set@|\n\n")
        config["pinned_build"] = sorted(args.packages)
        config.write()
    srcdir = os.path.join(wsdir, "src")
    build_set = set(config["pinned_build"])
    if args.packages:
        build_set |= set(args.packages)
    else:
        build_set |= set(config["default_build"])
    if not build_set:
        fatal("no package to build")
    msg("@{cf}The following packages will be built@|:\n")
    msg(", ".join(sorted(list(build_set))) + "\n\n", indent_first=4, indent_next=4)
    build_packages, fallback, conflicts = find_dependees(build_set, ws_state)
    show_fallback(fallback)
    show_conflicts(conflicts)
    if conflicts:
        fatal("cannot resolve dependencies")
    depend_set = set(build_packages.keys()) - build_set
    if depend_set:
        msg("@{cf}The following additional packages are needed to satisfy all dependencies@|:\n")
        msg(", ".join(sorted(depend_set)) + "\n\n", indent_first=4, indent_next=4)
    clone_packages(srcdir, build_packages, ws_state, protocol=args.protocol)

    catkin_build = ["catkin", "build", "--workspace", wsdir]
    catkin_build += build_packages.keys()
    if args.dry_run:
        msg("@{cf}Invoking@|: %s\n" % escape(" ".join(catkin_build)), indent_next=11)
        ret = 0
    else:
        ret = call_process(catkin_build)
    rosclipse = find_program("rosclipse")
    if rosclipse is not None and (args.force_rosclipse or config.get("use_rosclipse", True)) and not args.no_rosclipse:
        eclipse_ok, _, _ = call_process([rosclipse, "-d"], stdout=PIPE, stderr=PIPE)
        if eclipse_ok == 0:
            for name, pkg in iteritems(build_packages):
                if not pkg.manifest.is_metapackage():
                    pkgdir = os.path.join(wsdir, "src", pkg.workspace_path)
                    p_time = max(getmtime(os.path.join(pkgdir, "CMakeLists.txt")), getmtime(os.path.join(pkgdir, "package.xml")))
                    e_time = min(getmtime(os.path.join(pkgdir, ".project")), getmtime(os.path.join(pkgdir, ".cproject")), getmtime(os.path.join(pkgdir, ".settings", "language.settings.xml")))
                    if e_time < p_time or args.force_rosclipse:
                        msg("@{cf}Updating project files for '%s'@|\n" % name)
                        if not args.dry_run:
                            call_process([rosclipse, name])
    return ret
