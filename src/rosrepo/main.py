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
from .util import UserError, YAMLError
from pickle import PickleError
from .ui import error
from pygit2 import GitError
import sys
import traceback


CMD_INIT = 1
CMD_CONFIG = 2
CMD_LIST = 3
CMD_BASH = 4
CMD_BUILD = 5
CMD_GIT = 6
CMD_CLEAN = 7
CMD_INCLUDE_EXCLUDE = 8
CMD_DEPEND = 9
CMD_EXPORT = 10
CMD_FIND = 11
CMD_TEST = 12


def add_common_options(parser):
    from argparse import SUPPRESS
    parser.add_argument("--autocomplete", action="store_true", help=SUPPRESS)
    g = parser.add_argument_group("common options")
    g.add_argument("-w", "--workspace", help="override workspace location (default: autodetect)")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--offline", "--offline-mode", action="store_true", default=None, help="assume no network connection; do not contact Gitlab servers")
    m.add_argument("--no-offline", "--no-offline-mode", "--online", action="store_false", dest="offline", help="assume network connection; fetch updates from Gitlab servers (default)")
    g.add_argument("--dry-run", action="store_true", help="do nothing and just print what would be done")


def prepare_arguments(parser):
    from . import __version__
    from argparse import SUPPRESS, FileType
    parser.add_argument("--version", action="version", version="%s" % __version__)
    parser.add_argument("--stacktrace", action="store_true", help=SUPPRESS)
    parser.add_argument("--dry-run", action="store_true", help=SUPPRESS)
    cmds = parser.add_subparsers(metavar="ACTION", title="Actions", description="The following actions are available:", dest="command")

    # init
    p = cmds.add_parser("init", help="initialize workspace")
    p.add_argument("-r", "--ros-root", help="override ROS installation path (default: autodetect)")
    p.add_argument("--reset", action="store_true", help="reset workspace and delete all metadata")
    p.add_argument("path", metavar="PATH", nargs="?", default=".", help="path to the new catkin workspace")
    p.set_defaults(func=CMD_INIT)

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
    g.add_argument("--private-token", metavar="TOKEN", help="set private token for Gitlab server access explicitly (can be used with --set-gitlab-url and --gitlab-login)")
    g.add_argument("--set-gitlab-crawl-depth", metavar="DEPTH", type=int, help="set the tree depth limit for the Gitlab project crawler (default: 1)")
    g.add_argument("--force-gitlab-update", action="store_true", help="search Gitlab servers for available packages")
    g.add_argument("--protocol", help="set default protocol for accessing Git repositories")
    g = p.add_argument_group("credential storage options")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--store-credentials", action="store_true", default=None, help="store private tokens in config (default)")
    m.add_argument("--no-store-credentials", action="store_false", dest="store_credentials", help="do not store private tokens in config")
    g.add_argument("--remove-credentials", action="store_true", help="delete all stored credentials")
    g = p.add_argument_group("build options")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("-j", "--job-limit", type=int, default=None, help="limit number of concurrent build jobs (0 for unlimited)")
    m.add_argument("--no-job-limit", action="store_const", dest="job_limit", const=0, help="remove job limit (same as -j0)")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--install", action="store_true", default=None, help="run installation routine for packages")
    m.add_argument("--no-install", action="store_false", dest="install", help="do not run installation routine for packages")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--set-compiler", metavar="COMPILER", help="override compiler to build packages")
    m.add_argument("--unset-compiler", action="store_true", help="reset compiler override")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--rosclipse", action="store_true", default=None, help="use rosclipse to update Eclipse project files")
    m.add_argument("--no-rosclipse", action="store_false", dest="rosclipse", help="do not run rosclipse to create Eclipse project files")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--catkin-lint", action="store_true", default=None, help="use catkin_lint to check packages before build")
    m.add_argument("--no-catkin-lint", action="store_false", dest="catkin_lint", help="do not use catkin_lint to check packages before build")
    g.add_argument("--skip-catkin-lint", metavar="PACKAGE", action="append", default=[], help="skip catkin_lint for the named packages")
    g.add_argument("--no-skip-catkin-lint", metavar="PACKAGE", action="append", default=[], help="do not skip catkin_lint for the named packages")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--env-cache", action="store_true", default=None, help="cache build environment settings to build workspace faster")
    m.add_argument("--no-env-cache", action="store_false", dest="env_cache", help="do not cache build environment settings")
    p.set_defaults(func=CMD_CONFIG)

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
    p.add_argument("filter", metavar="FILTER", default=[], nargs="*", help="name filter (with unix shell globs allowed)")
    p.set_defaults(func=CMD_LIST)

    # bash
    p = cmds.add_parser("bash", help="internal command")
    add_common_options(p)
    p.add_argument("-t", "--terse", action="store_true", help="only print the value itself")
    p.add_argument("-e", "--export", action="store_true", help="prepend variable definition with export keyword")
    p.add_argument("var", nargs="*", help="environment variable is to be queried")
    p.set_defaults(func=CMD_BASH)

    # build
    p = cmds.add_parser("build", help="build packages in workspace")
    add_common_options(p)
    p.add_argument("-p", "--protocol", help="use PROTOCOL to clone missing packages from Gitlab (default: ssh)")
    g = p.add_argument_group("build options")
    g.add_argument("-c", "--clean", action="store_true", help="remove build artifacts of selected packages first")
    g.add_argument("--clean-all", action="store_true", help="clean the whole workspace before building")
    g.add_argument("-v", "--verbose", action="store_true", help="verbose build log")
    g.add_argument("-k", "--keep-going", action="store_true", help="continue as much as possible after errors")
    g.add_argument("-j", "--jobs", help="limit the number of simultaneous jobs")
    g.add_argument("--no-status", action="store_true", help="suppress status line")
    g.add_argument("-m", "--ignore-missing-depends", action="store_true", help="do not abort the build if system dependencies are missing")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--clone", action="store_true", default=True, help="clone missing dependencies (default)")
    m.add_argument("--no-clone", action="store_false", dest="clone", help="do not clone missing dependencies")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--rosclipse", action="store_true", default=None, help="force rosclipse to update Eclipse project files")
    m.add_argument("--no-rosclipse", action="store_false", dest="rosclipse", help="do not run rosclipse to create Eclipse project files")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--catkin-lint", action="store_true", default=None, help="force catkin_lint to check packages before build")
    m.add_argument("--no-catkin-lint", action="store_false", dest="catkin_lint", help="do not run catkin_lint to check packages before build")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--env-cache", action="store_true", default=None, help="cache build environment settings to build workspace faster")
    m.add_argument("--no-env-cache", action="store_false", dest="env_cache", help="do not cache build environment settings")
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("--set-default", action="store_true", help="use selected packages as new default build set")
    m.add_argument("--set-pinned", action="store_true", help="use selected packages as new pinned build set, i.e. build them always")
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("-a", "--all", action="store_true", help="build all packages in the workspace")
    m.add_argument("-l", "--last", action="store_true", help="build the same packages as the last time")
    g.add_argument("--rebuild", action="store_true", help="rebuild all built packages in the workspace")
    m.add_argument("--this", action="store_true", help="build package in the current working directory")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to build")
    p.set_defaults(func=CMD_BUILD)

    # git
    p = cmds.add_parser("git", help="manage Git repositories")
    add_common_options(p)
    git_cmds = p.add_subparsers(metavar="COMMAND", title="Git commands", dest="git_cmd")
    # git clone
    q = git_cmds.add_parser("clone", help="clone packages from Gitlab repository")
    q.add_argument("--dry-run", action="store_true", help=SUPPRESS)
    q.add_argument("-j", "--jobs", type=int, default=5, help="set the number of parallel connections")
    q.add_argument("-p", "--protocol", help="use PROTOCOL for remote access")
    q.add_argument("-m", "--ignore-missing-depends", action="store_true", help="clone packages even if dependencies are missing")
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--with-depends", action="store_true", default=True, help="also clone missing dependencies (default)")
    m.add_argument("--without-depends", action="store_false", dest="with_depends", help="do not clone missing dependencies")
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("-a", "--all", action="store_true", help="clone EVERYTHING. It's your bandwidth and disk space after all.")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to clone")
    # git status
    q = git_cmds.add_parser("status", help="show status of Git repositories")
    q.add_argument("--dry-run", action="store_true", help=SUPPRESS)
    q.add_argument("-a", "--all", action="store_true", help="show packages even if they are up-to-date")
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--with-depends", action="store_true", default=False, help="also show status for dependencies")
    m.add_argument("--without-depends", action="store_false", dest="with_depends", help="do not show status for dependencies (default)")
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--this", action="store_true", help="show status of package in the current working directory")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="only show selected packages")
    # git diff
    q = git_cmds.add_parser("diff", help="show changes in Git repositories")
    q.add_argument("--dry-run", action="store_true", help=SUPPRESS)
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--staged", action="store_true", help="compare staged index instead of workspace")
    m.add_argument("--upstream", action="store_true", help="show changes which have not been pushed to upstream")
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--with-depends", action="store_true", default=False, help="also show diff for dependencies")
    m.add_argument("--without-depends", action="store_false", dest="with_depends", help="do not show diff for dependencies (default)")
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--this", action="store_true", help="show status of package in the current working directory")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="only show selected packages")
    # git push
    q = git_cmds.add_parser("push", help="push commits to upstream repository")
    q.add_argument("--dry-run", action="store_true", help=SUPPRESS)
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--with-depends", action="store_true", default=False, help="also push dependencies")
    m.add_argument("--without-depends", action="store_false", dest="with_depends", help="do not push dependencies (default)")
    q.add_argument("-j", "--jobs", type=int, default=5, help="set the number of parallel connections")
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--this", action="store_true", help="push package in the current working directory")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to push")
    # git pull
    q = git_cmds.add_parser("pull", help="pull commits from upstream repository")
    q.add_argument("--dry-run", action="store_true", help=SUPPRESS)
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--with-depends", action="store_true", default=False, help="also pull dependencies")
    m.add_argument("--without-depends", action="store_false", dest="with_depends", help="do not pull dependencies (default)")
    q.add_argument("-j", "--jobs", type=int, default=5, help="set the number of parallel connections")
    q.add_argument("-L", "--update-local", action="store_true", help="also act on local branches (which are not tracking)")
    q.add_argument("-M", "--merge", action="store_true", help="merge changes if branches have diverged")
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--this", action="store_true", help="pull package in the current working directory")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to pull")
    # git merge
    q = git_cmds.add_parser("merge", help="merge local branches with upstream")
    q.add_argument("--dry-run", action="store_true", help=SUPPRESS)
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--with-depends", action="store_true", default=False, help="also merge dependencies")
    m.add_argument("--without-depends", action="store_false", dest="with_depends", help="do not merge dependencies (default)")
    q.add_argument("-j", "--jobs", type=int, default=5, help="set the number of parallel connections")
    g = q.add_argument_group("possible merge types")
    m = g.add_mutually_exclusive_group(required=True)
    m.add_argument("--from-master", action="store_true", help="merge changes from master into active branch, leaving master unchanged")
    m.add_argument("--to-master", action="store_true", help="merge changes from the active branch into master, leaving the active branch unchanged")
    m.add_argument("--sync", action="store_true", help="sync all changes from active branch and master, updating both")
    m.add_argument("--resolve", action="store_true", help="resolve merge conflicts with git-mergetool")
    m.add_argument("--abort", action="store_true", help="abort an unfinished merge")
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--this", action="store_true", help="merge package in the current working directory")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to merge")
    # git commit
    q = git_cmds.add_parser("commit", help="commit local changes for a package")
    q.add_argument("--dry-run", action="store_true", help=SUPPRESS)
    q.add_argument("--push", action="store_true", help="push new commits to upstream server")
    q.add_argument("-j", "--jobs", type=int, default=5, help="set the number of parallel connections")
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--with-depends", action="store_true", default=False, help="also commit dependencies")
    m.add_argument("--without-depends", action="store_false", dest="with_depends", help="do not commit dependencies (default)")
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--this", action="store_true", help="commit package in the current working directory")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to commit")
    # git remote
    q = git_cmds.add_parser("remote", help="change upstream settings for Git projects")
    q.add_argument("--dry-run", action="store_true", help=SUPPRESS)
    q.add_argument("--with-depends", action="store_true", help="also include dependent packages")
    q.add_argument("-p", "--protocol", help="switch protocol for remote URLs")
    q.add_argument("--move-host", metavar=("OLD_HOST", "NEW_HOST"), nargs=2, help="change host name for all remote URLs after a server move")
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--this", action="store_true", help="modify package in the current working directory")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select affected packages")
    # git gc
    q = git_cmds.add_parser("gc", help="run Git maintenance tasks")
    q.add_argument("--dry-run", action="store_true", help=SUPPRESS)
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--with-depends", action="store_true", default=False, help="also perform maintenance for dependencies")
    m.add_argument("--without-depends", action="store_false", dest="with_depends", help="do not perform maintenance for dependencies (default)")
    m = q.add_mutually_exclusive_group(required=False)
    m.add_argument("--this", action="store_true", help="show status of package in the current working directory")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="only show selected packages")
    #
    p.set_defaults(func=CMD_GIT)

    # clean
    p = cmds.add_parser("clean", help="clean workspace")
    add_common_options(p)
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("--this", action="store_true", help="clean package in the current working directory")
    m.add_argument("--vanished", action="store_true", help="clean build artifacts for packages which are no longer in the workspace")
    m.add_argument("--unused", action="store_true", help="clean build artifacts for packages which are neither pinned nor built by default (implies --vanished)")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to clean (default: all)")
    p.set_defaults(func=CMD_CLEAN)

    # include
    p = cmds.add_parser("include", help="add packages to default set or pinned set")
    add_common_options(p)
    p.add_argument("-l", "--list", action="store_true", help="list packages but do not change anything")
    p.add_argument("-p", "--protocol", help="use PROTOCOL to clone missing packages from Gitlab")
    p.add_argument("--replace", action="store_true", help="replace the whole set (instead of adding to it)")
    p.add_argument("--delete-unused", action="store_true", help="delete unused projects from workspace (DANGEROUS)")
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("-P", "--pinned", action="store_true", help="add packages to pinned set")
    m.add_argument("-S", "--default", action="store_true", help="add packages to default set")
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("-a", "--all", action="store_true", help="select all packages in the workspace")
    m.add_argument("--last", action="store_true", help="select packages from the last build")
    m.add_argument("--this", action="store_true", help="select packages in the current working directory")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to include")
    p.set_defaults(func=CMD_INCLUDE_EXCLUDE)

    # exclude
    p = cmds.add_parser("exclude", help="remove packages from default set or pinned set")
    add_common_options(p)
    p.add_argument("-l", "--list", action="store_true", help="list packages but do not change anything")
    p.add_argument("-p", "--protocol", help="use PROTOCOL to clone missing packages from Gitlab (default: ssh)")
    p.add_argument("--delete-unused", action="store_true", help="delete unused projects from workspace (DANGEROUS)")
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("-P", "--pinned", action="store_true", help="remove packages from pinned set")
    m.add_argument("-S", "--default", action="store_true", help="remove packages from default set")
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("-a", "--all", action="store_true", help="select all packages")
    m.add_argument("--last", action="store_true", help="select packages from the last build")
    m.add_argument("--this", action="store_true", help="select packages in the current working directory")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to exclude")
    p.set_defaults(func=CMD_INCLUDE_EXCLUDE)

    # depend
    p = cmds.add_parser("depend", help="show package dependencies")
    add_common_options(p)
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("--this", action="store_true", help="select packages in the current working directory")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select affected packages")
    p.set_defaults(func=CMD_DEPEND)

    # export
    p = cmds.add_parser("export", help="export workspace packages to rosinstall files")
    add_common_options(p)
    p.add_argument("-o", "--output", metavar="FILE", type=FileType("w"), default=sys.stdout, help="write rosinstall information to FILE")
    p.add_argument("-p", "--protocol", help="use PROTOCOL in the Git URLs (default: ssh)")
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("-a", "--all", action="store_true", help="select all packages")
    m.add_argument("--this", action="store_true", help="select package in the current working directory")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to export")
    p.set_defaults(func=CMD_EXPORT)

    # find
    p = cmds.add_parser("find", help="find packages and Git repositories")
    add_common_options(p)
    p.add_argument("--git", action="store_true", help="show Git repository location")
    p.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to find")
    p.set_defaults(func=CMD_FIND)

    # test
    p = cmds.add_parser("test", help="run unit tests on packages")
    add_common_options(p)
    p.add_argument("-p", "--protocol", help="use PROTOCOL to clone missing packages from Gitlab (default: ssh)")
    g = p.add_argument_group("build options")
    g.add_argument("-c", "--clean", action="store_true", help="remove build artifacts of selected packages first")
    g.add_argument("--clean-all", action="store_true", help="clean the whole workspace before testing")
    g.add_argument("-v", "--verbose", action="store_true", help="verbose build log")
    g.add_argument("-k", "--keep-going", action="store_true", help="continue as much as possible after errors")
    g.add_argument("-j", "--jobs", help="limit the number of simultaneous jobs")
    g.add_argument("--no-status", action="store_true", help="suppress status line")
    g.add_argument("-m", "--ignore-missing-depends", action="store_true", help="do not abort the test if system dependencies are missing")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--clone", action="store_true", default=True, help="clone missing dependencies (default)")
    m.add_argument("--no-clone", action="store_false", dest="clone", help="do not clone missing dependencies")
    m = g.add_mutually_exclusive_group(required=False)
    m.add_argument("--env-cache", action="store_true", default=None, help="cache build environment settings to build workspace faster")
    m.add_argument("--no-env-cache", action="store_false", dest="env_cache", help="do not cache build environment settings")
    m = p.add_mutually_exclusive_group(required=False)
    m.add_argument("-a", "--all", action="store_true", help="test all packages in the workspace")
    m.add_argument("-l", "--last", action="store_true", help="test the packages that were most recently built")
    m.add_argument("--this", action="store_true", help="test package in the current working directory")
    m.add_argument("packages", metavar="PACKAGE", default=[], nargs="*", help="select packages to test")
    p.set_defaults(func=CMD_TEST)

    return parser


def run_rosrepo(args):  # pragma: no cover
    try:
        if hasattr(args, "func"):
            if args.func == CMD_BASH:
                import rosrepo.cmd_bash
                return rosrepo.cmd_bash.run(args)
            if args.func == CMD_BUILD:
                import rosrepo.cmd_build
                return rosrepo.cmd_build.run(args)
            if args.func == CMD_INCLUDE_EXCLUDE:
                import rosrepo.cmd_include_exclude
                return rosrepo.cmd_include_exclude.run(args)
            if args.func == CMD_CLEAN:
                import rosrepo.cmd_clean
                return rosrepo.cmd_clean.run(args)
            if args.func == CMD_CONFIG:
                import rosrepo.cmd_config
                return rosrepo.cmd_config.run(args)
            if args.func == CMD_DEPEND:
                import rosrepo.cmd_depend
                return rosrepo.cmd_depend.run(args)
            if args.func == CMD_GIT:
                import rosrepo.cmd_git
                return rosrepo.cmd_git.run(args)
            if args.func == CMD_INIT:
                import rosrepo.cmd_init
                return rosrepo.cmd_init.run(args)
            if args.func == CMD_LIST:
                import rosrepo.cmd_list
                return rosrepo.cmd_list.run(args)
            if args.func == CMD_EXPORT:
                import rosrepo.cmd_export
                return rosrepo.cmd_export.run(args)
            if args.func == CMD_FIND:
                import rosrepo.cmd_find
                return rosrepo.cmd_find.run(args)
            if args.func == CMD_TEST:
                import rosrepo.cmd_test
                return rosrepo.cmd_test.run(args)
        error("no command\n")
    except UserError as e:
        if args.stacktrace:
            traceback.print_exc()
        error("%s\n" % str(e))
    except YAMLError as e:
        if args.stacktrace:
            traceback.print_exc()
        error("YAML: %s\n\n" % str(e))
    except PickleError as e:
        if args.stacktrace:
            traceback.print_exc()
        error("Pickle: %s\n\n" % str(e))
    except OSError as e:
        if args.stacktrace:
            traceback.print_exc()
        error("OS: %s\n\n" % str(e))
    except IOError as e:
        if args.stacktrace:
            traceback.print_exc()
        error("IO: %s\n\n" % str(e))
    except GitError as e:
        if args.stacktrace:
            traceback.print_exc()
        error("git: %s\n\n" % str(e))
    except KeyboardInterrupt:
        if args.stacktrace:
            traceback.print_exc()
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
