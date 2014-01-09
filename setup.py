#!/usr/bin/env python
# coding=utf-8

from distutils.core import setup
import sys
sys.path.insert(0, "lib")
from rosrepo import __version__ as rosrepo_version

setup(
  name          = "rosrepo",
  description   = "ROS Repository Management Tool",
  author        = "Timo Röhling",
  author_email  = "timo.roehling@fkie.fraunhofer.de",
  license       = "BSD",
  keywords      = "catkin,ROS",
  packages      = [ "rosrepo" ],
  package_dir   = { "" : "lib" },
  scripts       = [ "rosrepo" ],
  version       = rosrepo_version,
  requires      = [ "catkin_pkg", "yaml" ],
  classifiers   = [
                    "Development Status :: 4 - Beta",
                    "Intended Audience :: Developers",
                    "License :: OSI Approved :: BSD License",
                    "Topic :: Software Development :: Build Tools",
                    "Programming Language :: Python",
                    "Programming Language :: Python :: 3"
                  ]
)

