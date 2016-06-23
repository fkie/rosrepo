"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import os
import sys
from .workspace import get_workspace_location
from .util import path_has_prefix

def print_var (key, value, terse, export):
    sys.stdout.write("%s\n" % value if terse else "%s%s=%s\n" % ("export " if export else "", key, value))

def run(args):
    wsdir = get_workspace_location(args.workspace)
    if not args.var: args.var = ["ROS_WORKSPACE","ROS_PACKAGE_PATH"]
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
                else:
                    new_path.append(path)
            if not has_srcdir:
                new_path.insert(0, srcdir)
            print_var(key, os.pathsep.join(new_path), args.terse, args.export)
        else:
            if key in os.environ:
                print_var(key, os.environ[key], args.terse, args.export)
            else:
                if not args.terse: sys.stdout.write ("# variable %s is not set\n" % key)
