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
from setuptools import setup
import os
import sys

srcdir = os.path.normpath(os.path.join(os.path.dirname(__file__), "src"))
if os.path.isfile(os.path.join(srcdir, "rosrepo", "__init__.py")) and os.path.isfile(os.path.join(srcdir, "rosrepo", "main.py")):
    sys.path.insert(0, srcdir)
else:
    sys.stderr.write("This script is supposed to run from the rosrepo source tree")
    sys.exit(1)

from rosrepo import __version__ as rosrepo_version

setup(
    name         = "rosrepo",
    description  = "Manage ROS workspaces with multiple Gitlab repositories",
    author       = "Timo Röhling",
    author_email = "timo.roehling@fkie.fraunhofer.de",
    license      = "none",
    keywords     = ["catkin", "ROS", "Git"],
    packages     = ["rosrepo"],
    package_dir  = {"": "src"},
    data_files   = [("/etc/bash_completion.d", ["bash/rosrepo"])],
    version      = rosrepo_version,
    requires     = ["catkin_pkg", "dateutil", "git", "requests", "rosdep2", "yaml"],
    entry_points = {
        "console_scripts": ["rosrepo = rosrepo.main:main"]
    },
    classifiers  = [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Version Control",
        "Programming Language :: Python",
    ]
)
