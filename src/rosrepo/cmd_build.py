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
import multiprocessing
from .workspace import find_ros_root, get_workspace_location, get_workspace_state, resolve_this, WSFL_WS_PACKAGES
from .cmd_git import clone_packages
from .resolver import find_dependees, resolve_system_depends
from .config import Config
from .cache import Cache
from .ui import msg, warning, fatal, show_conflicts, show_missing_system_depends
from .util import call_process, find_program, iteritems, getmtime, PIPE, env_path_list_contains
from functools import reduce


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    ros_rootdir = find_ros_root(config.get("ros_root", None))
    if ros_rootdir is None:
        fatal("cannot detect ROS distribution. Have you sourced your setup.bash?\n")

    config.set_default("default_build", [])
    config.set_default("pinned_build", [])
    config.set_default("last_build", [])
    ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline)
    if args.last:
        args.packages = config["last_build"]
    if args.this:
        args.packages = resolve_this(wsdir, ws_state)
    if args.all:
        args.packages = ws_state.ws_packages.keys()
    if args.rebuild:
        args.packages = [pkg for pkg in ws_state.ws_packages.keys() if os.path.isfile(os.path.join(wsdir, "build", pkg, "Makefile"))]
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
            fatal("no packages given to be pinned\n")
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
    config["last_build"] = list(build_set)
    clean_set = build_set.copy()
    build_set |= pinned_set
    if not build_set:
        fatal("no packages to build\n")
    build_packages, system_depends, conflicts = find_dependees(build_set, ws_state)
    show_conflicts(conflicts)
    if conflicts:
        fatal("cannot resolve dependencies\n")
    clean_packages, _, _ = find_dependees(clean_set, ws_state, auto_resolve=True, ignore_missing=True)
    clean_packages = set(clean_packages.keys()) & set(ws_state.ws_packages.keys())
    if not args.dry_run:
        config.write()

    depend_set = set(build_packages.keys()) - build_set
    if depend_set:
        msg("@{cf}The following additional packages are needed to satisfy dependencies@|:\n")
        msg(", ".join(sorted(depend_set)) + "\n\n", indent=4)

    if system_depends:
        msg("@{cf}The following system packages are needed to satisfy dependencies@|:\n")
        msg(", ".join(sorted(system_depends)) + "\n\n", indent=4)
    missing = resolve_system_depends(ws_state, system_depends, missing_only=True)
    show_missing_system_depends(missing)
    if missing and not args.ignore_missing_depends:
        fatal("missing system packages (use -m/--ignore-missing-depends) to build anyway)\n")

    clone_packages(srcdir, build_packages, ws_state, protocol=args.protocol or config.get("git_default_transport", "ssh"), offline_mode=args.offline, dry_run=args.dry_run)
    ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline, ws_state=ws_state, flags=WSFL_WS_PACKAGES)
    build_packages, _, conflicts = find_dependees(build_set, ws_state)
    show_conflicts(conflicts)
    assert not conflicts

    if args.clean_all:
        invoke = ["catkin", "clean", "--workspace", wsdir, "--yes", "--all"]
        if args.dry_run:
            invoke += ["--dry-run"]
        call_process(invoke)
    elif args.clean:
        invoke = ["catkin", "clean", "--workspace", wsdir, "--yes"]
        if args.dry_run:
            invoke += ["--dry-run"]
        invoke += list(clean_packages)
        call_process(invoke)

    catkin_lint = find_program("catkin_lint")
    if catkin_lint and (args.catkin_lint or config.get("use_catkin_lint", True)) and not args.no_catkin_lint:
        catkin_lint = [catkin_lint, "--package-path", srcdir]
        if args.offline:
            catkin_lint += ["--offline"]
        catkin_lint += reduce(lambda x, y: x + y, (["--pkg", pkg] for pkg in build_packages.keys()))
        msg("@{cf}Running catkin_lint@|\n")
        ret = call_process(catkin_lint)
        if ret != 0 and not args.dry_run:
            fatal("catkin_lint reported errors\n")

    catkin_build = ["catkin", "build", "--workspace", wsdir]
    if args.dry_run:
        catkin_build += ["--dry-run"]
    if args.verbose:
        catkin_build += ["--verbose"]
    if args.no_status:
        catkin_build += ["--no-status"]
    if args.keep_going:
        catkin_build += ["--continue-on-failure"]

    if (args.env_cache or config.get("use_env_cache", True)) and not args.no_env_cache:
        catkin_build += ["--env-cache"]
    else:
        catkin_build += ["--no-env-cache"]

    if args.jobs:
        jobs = int(args.jobs)
        catkin_build += ["-j", str(args.jobs), "-p", str(args.jobs)]
    elif "job_limit" in config:
        jobs = int(config["job_limit"])
        catkin_build += ["-j", str(config["job_limit"]), "-p", str(config["job_limit"])]
    else:
        jobs = None

    catkin_build += build_packages.keys()

    if args.verbose:
        catkin_build += ["--make-args", "VERBOSE=ON", "--"]

    ret = call_process(catkin_build)

    rosclipse = find_program("rosclipse")
    if rosclipse is not None and (args.rosclipse or config.get("use_rosclipse", True)) and not args.no_rosclipse:
        eclipse_ok, _, _ = call_process([rosclipse, "-d"], stdout=PIPE, stderr=PIPE)
        if eclipse_ok == 0:
            workload = []
            for name, pkg in iteritems(build_packages):
                if not pkg.manifest.is_metapackage() and hasattr(pkg, "workspace_path") and pkg.workspace_path is not None:
                    pkgdir = os.path.join(wsdir, "src", pkg.workspace_path)
                    p_time = max(getmtime(os.path.join(pkgdir, "CMakeLists.txt")), getmtime(os.path.join(pkgdir, "package.xml")))
                    e_time = getmtime(os.path.join(pkgdir, ".project"))
                    if e_time < p_time or args.rosclipse:
                        workload.append((rosclipse, name, args.dry_run))
            if workload:
                pool = multiprocessing.Pool(processes=jobs)
                try:
                    pool.map_async(update_rosclipse, workload)
                    pool.close()
                except multiprocessing.TimeoutError:
                    pool.terminate()
                    fatal("timeout")
                except KeyboardInterrupt:
                    pool.terminate()
                    raise
                except Exception:
                    pool.terminate()
                    raise
                finally:
                    pool.join()
    if not env_path_list_contains("PATH", os.path.join(wsdir, "devel", "bin")):
        warning("%s is not in PATH\n" % os.path.join(wsdir, "devel", "bin"))
        msg("You probably need to source @{cf}%s@| again (or close and re-open your terminal)\n\n" % os.path.join(wsdir, "devel", "setup.bash"))
    if not env_path_list_contains("ROS_PACKAGE_PATH", os.path.join(wsdir, "src")):
        for name, pkg in iteritems(build_packages):
            if not pkg.manifest.is_metapackage() and hasattr(pkg, "workspace_path") and pkg.workspace_path is not None:
                pkgdir = os.path.join(wsdir, "src", pkg.workspace_path)
                if not env_path_list_contains("ROS_PACKAGE_PATH", pkgdir):
                    warning("%s is not in ROS_PACKAGE_PATH\n" % pkgdir)
                    msg("You probably need to source @{cf}%s@| again (or close and re-open your terminal)\n\n" % os.path.join(wsdir, "devel", "setup.bash"))
    return ret


def update_rosclipse(part):
    rosclipse, name, dry_run = part[0], part[1], part[2]
    msg("@{cf}Updating rosclipse project files@|: %s\n" % name)
    if not dry_run:
        call_process([rosclipse, name])
