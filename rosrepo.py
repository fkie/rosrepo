#!/usr/bin/env python
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
import sys
import os

# Run from source tree
srcdir = os.path.normpath(os.path.join(os.path.dirname(__file__), "src"))
if os.path.isfile(os.path.join(srcdir, "rosrepo", "__init__.py")) and os.path.isfile(os.path.join(srcdir, "rosrepo", "main.py")):
    sys.path.insert(0, srcdir)
else:
    sys.stderr.write("This script is supposed to run from the rosrepo source tree")
    sys.exit(1)


from rosrepo.main import main

if __name__ == "__main__":
    sys.exit(main())
