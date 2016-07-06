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
from .workspace import find_ros_root, get_workspace_location, get_workspace_state, WSFL_WS_PACKAGES
from .cmd_git import clone_packages
from .resolver import find_dependees, resolve_system_depends
from .config import Config
from .cache import Cache
from .ui import msg, fatal, show_conflicts, show_missing_system_depends
from .util import call_process, find_program, iteritems, getmtime, PIPE
from functools import reduce


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    ros_rootdir = find_ros_root(config.get("ros_root", None))
    if ros_rootdir is None:
        fatal("cannot detect ROS distribution. Have your sourced your setup.bash?\n")

    config.set_default("default_build", [])
    config.set_default("pinned_build", [])
    ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline)
    if args.all:
        args.packages = ws_state.ws_packages.keys()
    if args.set_default:
        if args.packages:
            msg("@{cf}Replacing default build set with@|:\n")
            msg(", ".join(sorted(args.packages)) + "\n\n", indent=4)
        else:
            fatal("no packages given for new default build\n")
        config["default_build"] = sorted(args.packages)
    if args.set_pinned:
        if args.packages:
            msg("@{cf}Replacing pinned build set with@|:\n")
            msg(", ".join(sorted(args.packages)) + "\n\n", indent=4)
        else:
            fatal("no packages given to be pinned")
        config["pinned_build"] = sorted(args.packages)
    srcdir = os.path.join(wsdir, "src")
    pinned_set = set(config["pinned_build"])
    if args.packages:
        build_set = set(args.packages)
        if build_set:
            msg("@{cf}You selected the following packages to be built@|:\n")
            msg(", ".join(sorted(list(build_set))) + "\n\n", indent=4)
    else:
        build_set = set(config["default_build"])
        if build_set:
            msg("@{cf}The following packages are included in the default build@|:\n")
            msg(", ".join(sorted(list(build_set))) + "\n\n", indent=4)
    if pinned_set - build_set:
        if build_set:
            msg("@{cf}The following pinned packages will also be built@|:\n")
        else:
            msg("@{cf}The following pinned packages will be built@|:\n")
        msg(", ".join(sorted(list(pinned_set - build_set))) + "\n\n", indent=4)
    build_set |= pinned_set
    if not build_set:
        fatal("no packages to build")
    build_packages, system_depends, conflicts = find_dependees(build_set, ws_state)
    show_conflicts(conflicts)
    if conflicts:
        fatal("cannot resolve dependencies")
    if not args.dry_run:
        config.write()

    depend_set = set(build_packages.keys()) - build_set
    if depend_set:
        msg("@{cf}The following additional packages are needed to satisfy all dependencies@|:\n")
        msg(", ".join(sorted(depend_set)) + "\n\n", indent=4)

    if system_depends:
        msg("@{cf}The following system packages are needed to satisfy all dependencies@|:\n")
        msg(", ".join(sorted(system_depends)) + "\n\n", indent=4)
    missing = resolve_system_depends(system_depends, missing_only=True)
    show_missing_system_depends(missing)
    if missing and not args.ignore_missing_depends:
        fatal("missing system packages (use -m/--ignore-missing-depends) to build anyway)")

    clone_packages(srcdir, build_packages, ws_state, protocol=args.protocol, offline_mode=args.offline, dry_run=args.dry_run)
    ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline, ws_state=ws_state, flags=WSFL_WS_PACKAGES)
    build_packages, _, conflicts = find_dependees(build_set, ws_state)
    show_conflicts(conflicts)
    assert not conflicts

    if args.clean:
        invoke = ["catkin", "clean", "--workspace", wsdir, "--all", "--yes"]
        if args.dry_run:
            invoke += ["--dry-run"]
        call_process(invoke)

    catkin_lint = find_program("catkin_lint")
    if catkin_lint and (args.catkin_lint or config.get("use_catkin_lint", True)) and not args.no_catkin_lint:
        catkin_lint = [catkin_lint, "--package-path", srcdir]
        if args.offline:
            catkin_lint += ["--offline"]
        catkin_lint += reduce(lambda x, y: x + y, (["--pkg", pkg] for pkg in build_packages.keys()))
        ret = call_process(catkin_lint)
        if ret != 0 and not args.dry_run:
            fatal("catkin_lint reported errors")

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
        catkin_build += ["-j", str(args.jobs), "-p", str(args.jobs)]
    elif "job_limit" in config:
        catkin_build += ["-j", str(config["job_limit"]), "-p", str(config["job_limit"])]

    catkin_build += build_packages.keys()

    if args.verbose:
        catkin_build += ["--make-args", "VERBOSE=ON", "--"]

    ret = call_process(catkin_build)

    rosclipse = find_program("rosclipse")
    if rosclipse is not None and (args.rosclipse or config.get("use_rosclipse", True)) and not args.no_rosclipse:
        eclipse_ok, _, _ = call_process([rosclipse, "-d"], stdout=PIPE, stderr=PIPE)
        if eclipse_ok == 0:
            for name, pkg in iteritems(build_packages):
                if not pkg.manifest.is_metapackage() and hasattr(pkg, "workspace_path") and pkg.workspace_path is not None:
                    pkgdir = os.path.join(wsdir, "src", pkg.workspace_path)
                    p_time = max(getmtime(os.path.join(pkgdir, "CMakeLists.txt")), getmtime(os.path.join(pkgdir, "package.xml")))
                    e_time = min(getmtime(os.path.join(pkgdir, ".project")), getmtime(os.path.join(pkgdir, ".cproject")), getmtime(os.path.join(pkgdir, ".settings", "language.settings.xml")))
                    if e_time < p_time or args.rosclipse:
                        msg("@{cf}Updating rosclipse project files@|: %s\n" % name)
                        if not args.dry_run:
                            call_process([rosclipse, name])
    return ret
