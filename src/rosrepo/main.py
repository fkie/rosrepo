#!/usr/bin/env python
"""
Copyright (c) 2013 Fraunhofer FKIE

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

 * Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
 * Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
from . import __version__
from . import *
import sys

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="version", version="%s" % __version__)
    subparsers = parser.add_subparsers(metavar="command")

    p = subparsers.add_parser("init", help="initialize workspace")
    p.add_argument("-r", "--roshome", help="override ROS installation path (default: autodetect)")
    p.add_argument("-a", "--autolink", action="store_true", help="search for and symlink to ROS-FKIE checkout")
    p.add_argument("-j", "--jobs", help="limit the number of simultaneous jobs")
    p.add_argument("--compiler", help="force a specific compiler")
    p.add_argument("--delete", action="store_true", help="delete workspace path if it exists")
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument("--install", action="store_true", help="install packages to install space")
    g.add_argument("--no-install", action="store_true", help="do not install packages to install space")
    p.add_argument("path", nargs="?", default=".", help="path to the new catkin workspace")
    p.set_defaults(func=cmd_init.run)

    p = subparsers.add_parser("config", help="configure workspace")
    p.add_argument("-w", "--workspace", help="set catkin workspace path")
    p.add_argument("-j", "--jobs", help="limit the number of simultaneous jobs")
    p.add_argument("--compiler", help="force a specific compiler")
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument("--install", action="store_true", help="install packages to install space")
    g.add_argument("--no-install", action="store_true", help="do not install packages to install space")
    p.set_defaults(func=cmd_config.run)

    p = subparsers.add_parser("checkout", help="add repository to workspace")
    p.add_argument("-w", "--workspace", help="set catkin workspace path")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--git", action="store_true", help="use Git")
    g.add_argument("--svn", action="store_true", help="use Subversion")
    g.add_argument("--link", action="store_true", help="symlink existing checkout")
    p.add_argument("url", help="repository url")
    p.add_argument("name", nargs="?", help="repository name")
    p.set_defaults(func=cmd_checkout.run)

    p = subparsers.add_parser("list", help="list packages in working set")
    p.add_argument("-w", "--workspace", help="set catkin workspace path")
    p.add_argument("-n", "--name-only", action="store_true", help="list package names only")
    p.add_argument("-a", "--all", action="store_true", help="list all available packages")
    p.add_argument("-m", "--manual", action="store_true", help="list manually included packages only")
    p.add_argument("-x", "--excluded", action="store_true", help="list excluded packages only")
    p.add_argument("-b", "--broken", action="store_true", help="list broken packages only")
    p.add_argument("glob", nargs="?", help="package name glob")
    p.set_defaults(func=cmd_list.run)

    p = subparsers.add_parser("find", help="show path of available package")
    p.add_argument("-w", "--workspace", help="set catkin workspace path")
    p.add_argument("--relative", action="store_true", help="make path relative to catkin workspace")
    p.add_argument("package", help="package name to look for")
    p.set_defaults(func=cmd_find.run)

    p = subparsers.add_parser("use", help="select new working set")
    p.add_argument("-w", "--workspace", help="set catkin workspace path")
    p.add_argument("-a", "--all", action="store_true", help="include all available packages")
    p.add_argument("-c", "--clean", action="store_true", help="clean workspace")
    p.add_argument("package", nargs="*", help="package name to include")
    p.set_defaults(func=cmd_use.run)

    p = subparsers.add_parser("include", help="add packages to working set")
    p.add_argument("-w", "--workspace", help="set catkin workspace path")
    p.add_argument("-a", "--all", action="store_true", help="include all available packages")
    p.add_argument("-c", "--clean", action="store_true", help="clean workspace")
    p.add_argument("--mark-auto", action="store_true", help="mark package as automatic dependency")
    p.add_argument("--pin", action="store_true", help="pin package as implicitly included")
    p.add_argument("package", nargs="*", help="package name to include")
    p.set_defaults(func=cmd_include.run)

    p = subparsers.add_parser("exclude", help="remove packages from working set")
    p.add_argument("-w", "--workspace", help="set catkin workspace path")
    p.add_argument("-a", "--all", action="store_true", help="exclude all available packages")
    p.add_argument("-c", "--clean", action="store_true", help="clean workspace")
    p.add_argument("package", nargs="*", help="package name to exclude")
    p.set_defaults(func=cmd_exclude.run)

    p = subparsers.add_parser("build", help="build packages in working set")
    p.add_argument("-w", "--workspace", help="set catkin workspace path")
    p.add_argument("-a", "--all", action="store_true", help="add all available packages to working set")
    p.add_argument("-c", "--clean", action="store_true", help="clean workspace")
    p.add_argument("-v", "--verbose", action="store_true", help="verbose build log")
    p.add_argument("-k", "--keep-going", action="store_true", help="continue as much as possible after errors")
    p.add_argument("-j", "--jobs", help="limit the number of simultaneous jobs")
    p.add_argument("--no-status", action="store_true", help="suppress status line")
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument("--install", action="store_true", help="install packages to install space")
    g.add_argument("--no-install", action="store_true", help="do not install packages to install space")
    p.add_argument("package", nargs="*", help="replace working set with listed packages")
    p.set_defaults(func=cmd_build.run)

    p = subparsers.add_parser("uninit", help="uninitialize workspace (restore standard catkin layout)")
    p.add_argument("-w", "--workspace", help="set catkin workspace path")
    p.set_defaults(func=cmd_uninit.run)

    p = subparsers.add_parser("bash", help="print environment variables")
    p.add_argument("-w", "--workspace", help="set catkin workspace path")
    p.add_argument("-t", "--terse", action="store_true", help="only print the value itself")
    p.add_argument("-e", "--export", action="store_true", help="prepend variable definition with export keyword")
    p.add_argument("var", nargs="*", help="environment variable is to be queried")
    p.set_defaults(func=cmd_bash.run)

    raw_args = sys.argv[1:]
    extra_args = []
    if "--" in raw_args:
        k = raw_args.index("--")
        extra_args = raw_args[k+1:]
        raw_args = raw_args[:k]
    args = parser.parse_args(raw_args)
    args.extra_args = extra_args
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
