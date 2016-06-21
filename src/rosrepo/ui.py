"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import os
import sys
from .workspace import find_workspace
from .util import UserError


def get_workspace_location(override):
    wsdir = find_workspace(override)
    if wsdir is None:
        wsdir = find_workspace(override, require_rosrepo=False)
        if wsdir is None:
            sys.stderr.write("I cannot find any catkin workspace. Please make sure that you\n")
            sys.stderr.write("have sourced the setup.bash file. You may need to run\n\n")
            sys.stderr.write("    rosrepo init %s/ros\n\n" % os.path.expanduser("~"))
            sys.stderr.write("to initialize the workspace.\n\n")
        else:
            sys.stderr.write("I found a catkin workspace, but it has not been configured for\n")
            sys.stderr.write("this version of rosrepo. Please run\n\n")
            sys.stderr.write("    rosrepo init %s\n\n" % wsdir)
            sys.stderr.write("to initialize the workspace.\n\n")
        raise UserError("Valid workspace location required")
    return wsdir


