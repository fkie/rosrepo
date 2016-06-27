"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import sys
from .util import UserError
from yaml import YAMLError
from pickle import PickleError
from .ui import error


def add_common_options(parser):
    g = parser.add_argument_group("common options")
    g.add_argument("-w", "--workspace", help="override workspace location (default: autodetect)")
    g.add_argument("--offline", "--offline-mode", action="store_true", help="assume no network connection; do not contact Gitlab servers")


def prepare_arguments(parser):
    from . import __version__
    parser.add_argument("--version", action="version", version="%s" % __version__)
    cmds = parser.add_subparsers(metavar="ACTION", title="Actions", description="The following actions are available:")

    # init
    p = cmds.add_parser("init", help="initialize workspace")
    p.add_argument("-r", "--ros-root", help="override ROS installation path (default: autodetect)")
    p.add_argument("--reset", action="store_true", help="reset workspace and delete all metadata")
    p.add_argument("path", nargs="?", default=".", help="path to the new catkin workspace")
    from .cmd_init import run as init_func
    p.set_defaults(func=init_func)

    # config
    p = cmds.add_parser("config", help="configuration settings")
    add_common_options(p)
    p.add_argument("--set-ros-root", metavar="PATH", help="override ROS installation path (default: autodetect)")
    g = p.add_argument_group("Gitlab options")
    g.add_argument("--set-gitlab-url", nargs=2, metavar=("LABEL", "URL"), help="add or change a Gitlab server named LABEL")
    g.add_argument("--unset-gitlab-url", metavar="LABEL", help="remove the Gitlab server named LABEL")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--login-for-private-token", action="store_true", help="login with username and password to acquire the account's private token (default)")
    m.add_argument("--with-private-token", metavar="TOKEN", help="specify private token for Gitlab server access")
    m.add_argument("--without-private-token", action="store_true", help="do not store authentication token at all")
    from .cmd_config import run as config_func
    p.set_defaults(func=config_func)

    # list
    p = cmds.add_parser("list", help="list packages in workspace")
    add_common_options(p)
    p.add_argument("-a", "--all", "--available", action="store_true", help="list all available packages")
    p.add_argument("-v", "--invert", action="store_true", help="invert the meaning of package selectors")
    p.add_argument("-n", "--package-names", action="store_true", help="only display the package names")
    g = p.add_argument_group("package selectors")
    g.add_argument("-S", "--default-set-only", action="store_true", help="list only packages in the default set")
    g.add_argument("-P", "--pinned-set-only", action="store_true", help="list only packages in the pinned set")
    g.add_argument("-B", "--built-only", action="store_true", help="list only packages which have been built in this workspace")
    g.add_argument("-W", "--workspace-only", action="store_true", help="list only packages which are in the workspace")
    g.add_argument("-D", "--dependees", action="store_true", help="also list dependees for default and pinned set")
    from .cmd_list import run as list_func
    p.set_defaults(func=list_func)

    # bash
    p = cmds.add_parser("bash", help="print environment variables")
    add_common_options(p)
    p.add_argument("-t", "--terse", action="store_true", help="only print the value itself")
    p.add_argument("-e", "--export", action="store_true", help="prepend variable definition with export keyword")
    p.add_argument("var", nargs="*", help="environment variable is to be queried")
    from .cmd_bash import run as bash_func
    p.set_defaults(func=bash_func)

    # git
    p = cmds.add_parser("git", help="manage Git repositories")
    add_common_options(p)
    git_cmds = p.add_subparsers(metavar="COMMAND", title="Git commands", dest="git_cmd")
    # git status
    q = git_cmds.add_parser("status", help="show status of Git repositories")
    q.add_argument("-m", "--modified", action="store_true", help="only show packages which are not up-to-date")
    q.add_argument("--no-depends", action="store_true", help="do not include dependent packages")
    q.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="only show selected packages")
    # git push
    q = git_cmds.add_parser("push", help="push commits to upstream repository")
    q.add_argument("--no-depends", action="store_true", help="do not push dependent packages")
    q.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to push")
    # git pull
    q = git_cmds.add_parser("pull", help="pull commits from upstream repository")
    q.add_argument("--no-depends", action="store_true", help="do not pull dependent packages")
    q.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to pull")
    from .cmd_git import run as git_func
    p.set_defaults(func=git_func)

    return parser


def run_rosrepo(args):
    try:
        if hasattr(args, "func"):
            return args.func(args)
        else:
            error("internal error: undefined command\n", fd=sys.stderr)
    except UserError as e:
        error("%s\n" % str(e))
    except YAMLError as e:
        error("YAML: %s\n\n" % str(e))
    except PickleError as e:
        error("Pickle: %s\n\n" % str(e))
    except OSError as e:
        error("OS: %s\n\n" % str(e))
    except IOError as e:
        error("IO: %s\n\n" % str(e))
    except KeyboardInterrupt:
        error("interrupted by user\n")
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
