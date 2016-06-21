"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import os
import sys
from subprocess import call as call_program
from shutil import rmtree
from .workspace import find_ros_root, is_workspace, migrate_workspace
from .util import makedirs, UserError
from .config import Config


def run(args):
    wsdir = os.path.normpath(args.path)
    if os.path.isdir(wsdir) and os.path.realpath(wsdir) == os.path.realpath(os.path.expanduser("~")):
        raise UserError("I'm not turning your $HOME directory into a catkin workspace")
    ros_rootdir = find_ros_root(args.ros_root)
    if ros_rootdir is None:
        raise UserError("Cannot detect ROS distribution. Please source setup.bash or use --ros-root option.")
    if is_workspace(wsdir):
        if args.reset:
            sys.stdout.write("Resetting workspace\n")
            rmtree(os.path.join(wsdir, ".rosrepo"), ignore_errors=True)
            rmtree(os.path.join(wsdir, ".catkin_tools"), ignore_errors=True)
            rmtree(os.path.join(wsdir, "build"), ignore_errors=True)
            rmtree(os.path.join(wsdir, "build_isolated"), ignore_errors=True)
            rmtree(os.path.join(wsdir, "devel"), ignore_errors=True)
            rmtree(os.path.join(wsdir, "devel_isolated"), ignore_errors=True)
            rmtree(os.path.join(wsdir, "install"), ignore_errors=True)
            rmtree(os.path.join(wsdir, "logs"), ignore_errors=True)
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
    if args.ros_root: cfg.data["ros_root"] = ros_rootdir
    cfg.write()
    catkin_init = ["catkin", "config", "--workspace", wsdir, "--extend", ros_rootdir]
    return call_program(catkin_init)
