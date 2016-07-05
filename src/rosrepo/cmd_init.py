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
import re
from shutil import rmtree
from .workspace import find_ros_root, is_workspace, migrate_workspace
from .util import makedirs, path_has_prefix
from .config import Config
from .ui import msg, fatal
from .cmd_config import run as config_run


class FakeArgs:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getattr__(self, name):
        return self.__dict__.get(name, None)


def run(args):
    wsdir = os.path.normpath(args.path)
    if os.path.isdir(wsdir):
        if os.path.realpath(wsdir) == os.path.realpath(os.path.expanduser("~")):
            fatal("I'm not turning your $HOME directory into a catkin workspace\n")
        if path_has_prefix(os.path.realpath(wsdir), os.path.realpath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))):
            fatal("I'm not turning your rosrepo source folder into a catkin workspace\n")
    ros_rootdir = find_ros_root(args.ros_root)
    if ros_rootdir is None:
        fatal("cannot detect ROS distribution. Please source setup.bash or use --ros-root option\n")
    if is_workspace(wsdir):
        if args.reset:
            msg("Resetting workspace\n")
            rmtree(os.path.join(wsdir, ".rosrepo"), ignore_errors=True)
            rmtree(os.path.join(wsdir, ".catkin_tools"), ignore_errors=True)
            for fn in os.listdir(wsdir):
                if re.match(r"(build|devel|install|logs)($|_)", fn, re.IGNORECASE):
                    rmtree(os.path.join(wsdir, fn), ignore_errors=True)
            try:
                os.unlink(os.path.join(wsdir, "src", "CMakeLists.txt"))
            except OSError:
                pass
            try:
                os.unlink(os.path.join(wsdir, "src", "toplevel.cmake"))
            except OSError:
                pass
        else:
            migrate_workspace(wsdir)
    makedirs(wsdir)
    with open(os.path.join(wsdir, ".catkin_workspace"), "w") as f:
        f.write("# This file currently only serves to mark the location of a catkin workspace for tool integration\n")
    makedirs(os.path.join(wsdir, "src"))
    cfg = Config(wsdir)
    cfg.write()
    return config_run(FakeArgs(workspace=wsdir, set_ros_root=args.ros_root))
