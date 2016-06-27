"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import os
from shutil import rmtree
from .workspace import find_ros_root, is_workspace, migrate_workspace
from .util import makedirs, call_process, path_has_prefix
from .config import Config
from .ui import msg, fatal
from .common import DEFAULT_CMAKE_ARGS


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
    if args.ros_root:
        cfg.data["ros_root"] = ros_rootdir
    cfg.write()
    catkin_init = ["catkin", "config", "--workspace", wsdir, "--extend", ros_rootdir, "--cmake-args"] + DEFAULT_CMAKE_ARGS
    return call_process(catkin_init)
