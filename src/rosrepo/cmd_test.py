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
from .workspace import find_ros_root, get_workspace_location, get_workspace_state, resolve_this, WSFL_WS_PACKAGES
from .cmd_git import clone_packages
from .config import Config
from .cache import Cache
from .resolver import find_dependees, resolve_system_depends
from .ui import msg, warning, error, fatal, show_conflicts, show_missing_system_depends
from .util import call_process, PIPE, find_program
from shutil import copytree, rmtree
from tempfile import mkdtemp


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    if args.offline is None:
        args.offline = config.get("offline_mode", False)
        if args.offline:
            warning("offline mode. Run 'rosrepo config --online' to disable\n")
    ros_rootdir = find_ros_root(config.get("ros_root", None))
    if ros_rootdir is None:
        fatal("cannot detect ROS distribution. Have you sourced your setup.bash?\n")

    config.set_default("default_build", [])
    config.set_default("last_build", [])
    config.set_default("last_ros_root", ros_rootdir)

    if config["last_ros_root"] != ros_rootdir and not args.clean_all:
        msg(
            "You have changed your ROS distribution from "
            "@{cf}%(old_path)s@| to @{cf}%(new_path)s@|. Please run\n\n"
            "    @!rosrepo clean@|\n\n"
            "to remove all obsolete build artifacts and rebuild your workspace with "
            "the new ROS version.\n\n" % {"old_path": config["last_ros_root"], "new_path": ros_rootdir}
        )
        fatal("need to clean workspace")

    ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline)
    if args.last:
        args.packages = config["last_build"]
    if args.this:
        args.packages = resolve_this(wsdir, ws_state)
    if args.all:
        args.packages = ws_state.ws_packages.keys()
    if args.packages:
        test_set = set(args.packages)
        if test_set:
            msg("@{cf}You selected the following packages for testing@|:\n")
            msg(", ".join(sorted(list(test_set))) + "\n\n", indent=4)
    else:
        test_set = set(config["default_build"])
        if test_set:
            msg("@{cf}The following packages from the default build will be tested@|:\n")
            msg(", ".join(sorted(list(test_set))) + "\n\n", indent=4)

    if not test_set:
        fatal("no packages to test\n")

    build_packages, system_depends, conflicts = find_dependees(test_set, ws_state)
    show_conflicts(conflicts)
    if conflicts:
        fatal("cannot resolve dependencies\n")

    depend_set = set(build_packages.keys()) - test_set
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

    if args.clone:
        clone_packages(os.path.join(wsdir, "src"), build_packages, ws_state, config, protocol=args.protocol or config.get("git_default_transport", "ssh"), offline_mode=args.offline, dry_run=args.dry_run)
        ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline, ws_state=ws_state, flags=WSFL_WS_PACKAGES)
    build_packages, _, conflicts = find_dependees(test_set, ws_state)
    show_conflicts(conflicts)
    assert not conflicts
    missing_ws = [n for n in build_packages if n not in ws_state.ws_packages]
    if missing_ws and not args.dry_run:
        msg("@{cf}The following packages are missing from your workspace@|:\n")
        msg(", ".join(sorted(missing_ws)) + "\n\n", indent=4)
        fatal("missing build dependencies\n")

    if config["last_ros_root"] != ros_rootdir and not args.dry_run:
        invoke = ["catkin", "config", "--extend", ros_rootdir]
        call_process(invoke, stdout=PIPE, stderr=PIPE)
        config["last_ros_root"] = ros_rootdir
        config.write()

    if args.clean_all:
        invoke = ["catkin", "clean", "--workspace", wsdir, "--yes", "--all"]
        if args.dry_run:
            invoke += ["--dry-run"]
        call_process(invoke)
    elif args.clean:
        invoke = ["catkin", "clean", "--workspace", wsdir, "--yes"]
        if args.dry_run:
            invoke += ["--dry-run"]
        invoke += list(test_set)
        call_process(invoke)

    catkin_test = ["catkin", "build", "--workspace", wsdir]
    if args.dry_run:
        catkin_test += ["--dry-run"]
    if args.verbose:
        catkin_test += ["--verbose"]
    if args.no_status:
        catkin_test += ["--no-status"]
    if args.keep_going:
        catkin_test += ["--continue-on-failure"]

    if args.env_cache is None:
        args.env_cache = config.get("use_env_cache", True)
    if args.env_cache:
        catkin_test += ["--env-cache"]
    else:
        catkin_test += ["--no-env-cache"]

    if args.jobs:
        jobs = int(args.jobs)
        if jobs > 0:
            catkin_test += ["-j", str(args.jobs), "-p", str(args.jobs)]
        else:
            jobs = None
    elif "job_limit" in config:
        jobs = int(config["job_limit"])
        catkin_test += ["-j", str(config["job_limit"]), "-p", str(config["job_limit"])]
    else:
        jobs = None

    catkin_test += list(test_set)
    catkin_test += ["--catkin-make-args", "run_tests"]
    if args.verbose:
        catkin_test += ["--make-args", "VERBOSE=ON"]

    ret = call_process(catkin_test)
    catkin_test_results = find_program("catkin_test_results")

    if ret == 0 and catkin_test_results:
        tmpdir = mkdtemp()
        try:
            for pkg in test_set:
                resultdir = os.path.join(wsdir, "build", pkg, "test_results", pkg)
                if os.path.isdir(resultdir):
                    copytree(resultdir, os.path.join(tmpdir, pkg))
            ret = call_process([catkin_test_results, "--all", "--verbose", tmpdir])
        except Exception as e:
            error("cannot aggregate test statistics: %s\n" % str(e))
        finally:
            rmtree(tmpdir, ignore_errors=True)
    return ret
