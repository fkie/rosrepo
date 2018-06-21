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
import fastentrypoints
from setuptools import setup, __version__ as setuptools_version
import os
import sys

srcdir = os.path.normpath(os.path.join(os.path.dirname(__file__), "src"))
if os.path.isfile(os.path.join(srcdir, "rosrepo", "__init__.py")) and os.path.isfile(os.path.join(srcdir, "rosrepo", "main.py")):
    sys.path.insert(0, srcdir)
else:
    sys.stderr.write("This script is supposed to run from the rosrepo source tree")
    sys.exit(1)

from rosrepo import __version__ as rosrepo_version

install_requires = ["catkin_pkg", "catkin_tools", "python-dateutil", "pygit2", "requests", "rosdep", "pyyaml"]
extras_require = {}
# The following code is a somewhat barbaric attempt to get conditional
# dependencies that works on setuptools versions before 18.0 as well:
if int(setuptools_version.split(".", 1)[0]) < 18:
    if sys.version_info[0] < 3:
        install_requires.append("futures")
    if sys.version_info[:2] < (3, 5):
        install_requires.append("scandir")
    # Unfortunately, the fake conditional dependencies do not work with
    # the caching mechanism of bdist_wheel, so if you want to create wheels,
    # use at least setuptools version 18
    assert "bdist_wheel" not in sys.argv
else:
    # We have a reasonably modern setuptools version
    from distutils.version import StrictVersion as Version
    if Version(setuptools_version) >= Version("36.2"):
        # Starting with setuptools 36.2, we can do proper conditional
        # dependencies "PEP 508 style", the way God intended
        install_requires.append("futures ; python_version<'3'")
        install_requires.append("scandir ; python_version<'3.5'")
    else:
        # No proper conditional dependencies, but we can resort to some
        # trickery and get the job done nevertheless
        extras_require[":python_version<'3'"] = ["futures"]
        extras_require[":python_version<'3.5'"] = ["scandir"]

setup(
    name         = "rosrepo",
    description  = "Manage ROS workspaces with multiple Gitlab repositories",
    author       = "Timo Röhling",
    author_email = "timo.roehling@fkie.fraunhofer.de",
    license      = "Apache Software License",
    keywords     = ["catkin", "ROS", "Git"],
    packages     = ["rosrepo"],
    package_dir  = {"": "src"},
    data_files   = [("share/bash-completion/completions", ["bash/rosrepo"])],
    version      = rosrepo_version,
    install_requires = install_requires,
    extras_require = extras_require,
    test_suite   = "nose.collector",
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
