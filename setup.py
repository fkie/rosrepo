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
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Version Control",
        "Programming Language :: Python",
    ]
)
