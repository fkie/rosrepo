#!/usr/bin/env python
# coding=utf-8

from distutils.core import setup
import sys
sys.path.insert(0, "lib")
from rosrepo import __version__ as rosrepo_version

setup(
  name          = "rosrepo",
  description   = "Repository management tool for ROS-FKIE",
  author        = "Timo Röhling",
  author_email  = "timo.roehling@fkie.fraunhofer.de",
  packages      = [ "rosrepo" ],
  package_dir   = { "" : "lib" },
  scripts       = [ "rosrepo" ],
  version       = rosrepo_version,
  requires      = [ "catkin_pkg" ]
)

