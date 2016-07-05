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
from .workspace import get_workspace_location
from .util import path_has_prefix


def print_var(key, value, terse, export):
    sys.stdout.write("%s\n" % value if terse else "%s%s=%s\n" % ("export " if export else "", key, value))


def run(args):
    wsdir = get_workspace_location(args.workspace)
    if not args.var:
        args.var = ["ROS_WORKSPACE", "ROS_PACKAGE_PATH"]
    for key in args.var:
        if key == "ROS_WORKSPACE":
            print_var(key, wsdir, args.terse, args.export)
        elif key == "ROS_PACKAGE_PATH":
            has_srcdir = False
            srcdir = os.path.join(wsdir, "src")
            path = os.environ["ROS_PACKAGE_PATH"] if "ROS_PACKAGE_PATH" in os.environ else ""
            new_path = []
            for path in path.split(os.pathsep):
                if path_has_prefix(path, srcdir):
                    if not has_srcdir:
                        has_srcdir = True
                        new_path.append(srcdir)
                elif path:
                    new_path.append(path)
            if not has_srcdir:
                new_path.insert(0, srcdir)
            print_var(key, os.pathsep.join(new_path), args.terse, args.export)
        else:
            if key in os.environ:
                print_var(key, os.environ[key], args.terse, args.export)
            else:
                if not args.terse:
                    sys.stdout.write("# variable %s is not set\n" % key)
    return 0
