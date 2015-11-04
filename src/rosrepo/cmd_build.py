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
import sys
import os
import rosrepo.common as common
from subprocess import call
from .compat import iteritems


def run(args):
    wsdir = common.find_wsdir(args.workspace)
    if wsdir is None:
        sys.stderr.write ("cannot find suitable catkin workspace\n")
        sys.exit(1)
    includes = set([])
    excludes = set([])
    packages = common.find_packages(wsdir)
    pinned = set([name for name,info in iteritems(packages) if info.pinned])
    pinned = common.resolve_depends(pinned, packages)
    if args.all or args.package:
        if args.all:
            args.package = packages.keys()
        else:
            args.package = common.glob_package_names(args.package, packages)
        if not common.is_valid_selection(args.package, packages):
            sys.exit(1)
        selected = set(args.package)
        for name,info in iteritems(packages):
            if not info.pinned:
                info.selected = name in selected
        needed = common.resolve_depends(selected, packages)
        enabled = set([name for name,info in iteritems(packages) if info.active])
        includes = (pinned | needed) - enabled
        excludes = enabled - (needed | pinned)
    else:
        enabled = set([name for name,info in iteritems(packages) if info.active])
        disabled = set([name for name,info in iteritems(packages) if not info.active])
        includes = (pinned | common.resolve_depends(enabled, packages)) - enabled
        excludes = common.resolve_obsolete(packages) - includes - disabled
        for name,info in iteritems(packages):
            if not name in enabled: info.selected = False
    if includes:
        sys.stdout.write("The following packages need to be included:\n%s\n" % common.format_list(includes))
    if excludes:
        sys.stdout.write("The following packages are no longer needed:\n%s\n" % common.format_list(excludes))
    for name in includes:
        packages[name].active = True
    for name in excludes:
        packages[name].active = False
        packages[name].selected = False
    common.save_metainfo(wsdir, packages)
    if args.install:
        call(["catkin", "clean", "--workspace", wsdir, "--profile", "rosrepo", "--build"])
        call(["catkin", "config", "--workspace", wsdir, "--profile", "rosrepo", "--install"])
    if args.no_install:
        call(["catkin", "clean", "--workspace", wsdir, "--profile", "rosrepo", "--build", "--install"])
        call(["catkin", "config", "--workspace", wsdir, "--profile", "rosrepo", "--no-install"])
    if args.clean:
        sys.stdout.write("Cleaning workspace...\n")
        call(["catkin", "clean", "--workspace", wsdir, "--profile", "rosrepo", "--all"])
    catkin_invoke = ["catkin", "build", "--workspace", wsdir, "--profile", "rosrepo"]
    if args.verbose: catkin_invoke = catkin_invoke + ["--verbose"]
    if args.keep_going: catkin_invoke = catkin_invoke + ["--continue-on-failure"]
    if args.jobs: catkin_invoke = catkin_invoke + ["--jobs", args.jobs]
    catkin_invoke = catkin_invoke + [name for name,info in iteritems(packages) if info.active]
    if args.verbose: catkin_invoke = catkin_invoke + ["--make-args", "VERBOSE=ON", "--"]
    catkin_invoke = catkin_invoke + args.extra_args
    ret = call(catkin_invoke)
    if ret != 0: sys.exit(ret)

