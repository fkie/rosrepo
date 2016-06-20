"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import sys
from .util import UserError
from yaml import YAMLError
from pickle import PickleError


def add_common_options(parser):
    pass


def prepare_arguments(parser):
    from . import __version__
    parser.add_argument("--version", action="version", version="%s" % __version__)
    cmds = parser.add_subparsers(metavar="action", title="Actions", description="The following actions are available:")

    # init
    p = cmds.add_parser("init", help="initialize workspace")
    p.add_argument("-r", "--ros-root", help="override ROS installation path (default: autodetect)")
    p.add_argument("--reset", action="store_true", help="reset workspace and delete all metadata")
    p.add_argument("path", nargs="?", default=".", help="path to the new catkin workspace")
    from .cmd_init import run as init_func
    p.set_defaults(func=init_func)

    return parser


def run_rosrepo (args):
    try:
        if hasattr(args, "func"):
            return args.func(args)
        else:
            sys.stderr.write("Internal error: undefined command\n\n")
    except UserError as e:
        sys.stderr.write("%s\n\n" % str(e))
    except YAMLError as e:
        sys.stderr.write("YAML Error: %s\n\n" % str(e))
    except PickleError as e:
        sys.stderr.write("Pickle Error: %s\n\n" % str(e))
    except OSError as e:
        sys.stderr.write("OS Error: %s\n\n" % str(e))
    except IOError as e:
        sys.stderr.write("I/O Error: %s\n\n" % str(e))
    return 1


def main():
    import argparse
    parser = prepare_arguments(argparse.ArgumentParser())
    args = parser.parse_args()
    return run_rosrepo(args)


rosrepo_catkin_tools = dict(
    verb="rosrepo",
    description="Manages ROS workspaces with multiple Gitlab repositories",
    main=run_rosrepo,
    prepare_arguments=prepare_arguments
)
