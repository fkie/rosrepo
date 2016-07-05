# coding=utf-8
#
# ROSREPO
# Manage ROS workspaces with multiple Gitlab repositories
#
# Author: Timo Röhling
#
# Copyright 2016 Fraunhofer FKIE
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#
from .util import UserError
from yaml import YAMLError
from pickle import PickleError
from .ui import error


def add_common_options(parser):
    from argparse import SUPPRESS
    parser.add_argument("--autocomplete", action="store_true", help=SUPPRESS)
    g = parser.add_argument_group("common options")
    g.add_argument("-w", "--workspace", help="override workspace location (default: autodetect)")
    g.add_argument("--offline", "--offline-mode", action="store_true", help="assume no network connection; do not contact Gitlab servers")
    g.add_argument("--dry-run", action="store_true", help="do nothing and just print what would be done")


def prepare_arguments(parser):
    from . import __version__
    parser.add_argument("--version", action="version", version="%s" % __version__)
    cmds = parser.add_subparsers(metavar="ACTION", title="Actions", description="The following actions are available:", dest="command")

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
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("--set-ros-root", metavar="PATH", help="override ROS installation path")
    m.add_argument("--unset-ros-root", action="store_true", help="undo override for ROS installation path")
    g = p.add_argument_group("Gitlab options")
    g.add_argument("--set-gitlab-url", nargs=2, metavar=("LABEL", "URL"), help="add or change a Gitlab server named LABEL")
    g.add_argument("--get-gitlab-url", metavar="LABEL", help="show the Gitlab server named LABEL")
    g.add_argument("--unset-gitlab-url", metavar="LABEL", help="remove the Gitlab server named LABEL")
    g.add_argument("--show-gitlab-urls", action="store_true", help="show all configured Gitlab servers")
    g.add_argument("--gitlab-login", metavar="LABEL", help="acquire private token for the Gitlab server named LABEL")
    g.add_argument("--gitlab-logout", metavar="LABEL", help="delete private token for the Gitlab server named LABEL")
    g.add_argument("--private-token", metavar="TOKEN", help="set private token for Gitlab server access explicitly")
    g = p.add_argument_group("credential storage options")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--no-store-credentials", action="store_true", help="do not store private tokens in config")
    m.add_argument("--store-credentials", action="store_true", help="store private tokens in config (default)")
    g.add_argument("--remove-credentials", action="store_true", help="delete all stored credentials")
    g = p.add_argument_group("build options")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("-j", "--job-limit", type=int, help="limit number of concurrent build jobs (0 for unlimited)")
    m.add_argument("--no-job-limit", action="store_true", help="remove job limit (same as -j0)")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--install", action="store_true", help="run installation routine for packages")
    m.add_argument("--no-install", action="store_true", help="do not run installation routine for packages")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--set-compiler", help="override compiler to build packages")
    m.add_argument("--unset-compiler", action="store_true", help="reset compiler override")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--rosclipse", action="store_true", help="use rosclipse to update Eclipse project files")
    m.add_argument("--no-rosclipse", action="store_true", help="do not run rosclipse to create Eclipse project files")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--catkin-lint", action="store_true", help="use catkin_lint to check packages before build")
    m.add_argument("--no-catkin-lint", action="store_true", help="do not use catkin_lint to check packages before build")
    from .cmd_config import run as config_func
    p.set_defaults(func=config_func)

    # list
    p = cmds.add_parser("list", help="list packages in workspace")
    add_common_options(p)
    p.add_argument("-a", "--all", "--available", action="store_true", help="list all available packages")
    p.add_argument("-v", "--invert", action="store_true", help="invert the meaning of package selectors")
    p.add_argument("-n", "--package-names", action="store_true", help="only display the package names")
    g = p.add_argument_group("package selectors")
    g.add_argument("-S", "--default-only", action="store_true", help="list only packages in the default set")
    g.add_argument("-P", "--pinned-only", action="store_true", help="list only packages in the pinned set")
    g.add_argument("-B", "--built-only", action="store_true", help="list only packages which have been built in this workspace")
    g.add_argument("-C", "--conflicts-only", action="store_true", help="list only package which cannot be resolved as dependency")
    g.add_argument("-W", "--workspace-only", action="store_true", help="list only packages which are in the workspace")
    g.add_argument("-D", "--dependees", action="store_true", help="also list dependees for default and pinned set")
    from .cmd_list import run as list_func
    p.set_defaults(func=list_func)

    # bash
    p = cmds.add_parser("bash", help="internal command")
    add_common_options(p)
    p.add_argument("-t", "--terse", action="store_true", help="only print the value itself")
    p.add_argument("-e", "--export", action="store_true", help="prepend variable definition with export keyword")
    p.add_argument("var", nargs="*", help="environment variable is to be queried")
    from .cmd_bash import run as bash_func
    p.set_defaults(func=bash_func)

    # build
    p = cmds.add_parser("build", help="build packages in workspace")
    add_common_options(p)
    p.add_argument("-p", "--protocol", default="ssh", help="use PROTOCOL to clone missing packages from Gitlab (default: ssh)")
    g = p.add_argument_group("build options")
    g.add_argument("-c", "--clean", action="store_true", help="clean workspace")
    g.add_argument("-v", "--verbose", action="store_true", help="verbose build log")
    g.add_argument("-k", "--keep-going", action="store_true", help="continue as much as possible after errors")
    g.add_argument("-j", "--jobs", help="limit the number of simultaneous jobs")
    g.add_argument("--no-status", action="store_true", help="suppress status line")
    g.add_argument("-m", "--ignore-missing-depends", action="store_true", help="do not abort the build if system dependencies are missing")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--rosclipse", action="store_true", help="force rosclipse to update Eclipse project files")
    m.add_argument("--no-rosclipse", action="store_true", help="do not run rosclipse to create Eclipse project files")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--catkin-lint", action="store_true", help="force catkin_lint to check packages before build")
    m.add_argument("--no-catkin-lint", action="store_true", help="do not run catkin_lint to check packages before build")
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("--set-default", action="store_true", help="use selected packages as new default build set")
    m.add_argument("--set-pinned", action="store_true", help="use selected packages as new pinned build set, i.e. build them always")
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("-a", "--all", action="store_true", help="build all packages in the workspace")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to build")
    from .cmd_build import run as build_func
    p.set_defaults(func=build_func)

    # git
    p = cmds.add_parser("git", help="manage Git repositories")
    add_common_options(p)
    git_cmds = p.add_subparsers(metavar="COMMAND", title="Git commands", dest="git_cmd")
    # git clone
    q = git_cmds.add_parser("clone", help="clone packages from Gitlab repository")
    q.add_argument("-p", "--protocol", default="ssh", help="use PROTOCOL for remote access (default: ssh)")
    q.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to clone")
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
    # git commit
    q = git_cmds.add_parser("commit", help="commit local changes for a package")
    q.add_argument("package", metavar="PACKAGE", help="package to commit")
    from .cmd_git import run as git_func
    p.set_defaults(func=git_func)

    # clean
    p = cmds.add_parser("clean", help="clean workspace")
    add_common_options(p)
    from .cmd_clean import run as clean_func
    p.set_defaults(func=clean_func)

    # include
    from .buildset import run as buildset_func
    p = cmds.add_parser("include", help="add packages to default set or pinned set")
    add_common_options(p)
    p.add_argument("-l", "--list", action="store_true", help="list packages but do not change anything")
    p.add_argument("-p", "--protocol", default="ssh", help="use PROTOCOL to clone missing packages from Gitlab (default: ssh)")
    p.add_argument("--replace", action="store_true", help="replace the whole set (instead of adding to it)")
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("-P", "--pinned", action="store_true", help="add packages to pinned set")
    m.add_argument("-S", "--default", action="store_true", help="add packages to default set")
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("-a", "--all", action="store_true", help="select all packages in the workspace")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to exclude")
    p.set_defaults(func=buildset_func)

    # exclude
    p = cmds.add_parser("exclude", help="remove packages from default set or pinned set")
    add_common_options(p)
    p.add_argument("-l", "--list", action="store_true", help="list packages but do not change anything")
    p.add_argument("-p", "--protocol", default="ssh", help="use PROTOCOL to clone missing packages from Gitlab (default: ssh)")
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("-P", "--pinned", action="store_true", help="remove packages from pinned set")
    m.add_argument("-S", "--default", action="store_true", help="remove packages from default set")
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("-a", "--all", action="store_true", help="select all packages")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to exclude")
    p.set_defaults(func=buildset_func)

    return parser


def run_rosrepo(args):  # pragma: no cover
    try:
        if hasattr(args, "func"):
            return args.func(args)
        else:
            error("no command\n")
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


def main():  # pragma: no cover
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
