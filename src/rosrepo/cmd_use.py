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
    packages = common.find_packages(wsdir)
    if args.all:
        args.package = packages.keys()
    else:
        args.package = common.glob_package_names(args.package, packages)
    if not common.is_valid_selection(args.package, packages):
        sys.exit(1)
    if not args.package:
        sys.stdout.write ("no packages specified. working set remains unchanged\n")
        sys.exit(0)
    selected = set(args.package)
    for name,info in iteritems(packages):
        if not info.pinned:
            info.selected = name in selected
    pinned = set([name for name,info in iteritems(packages) if info.pinned])
    pinned = common.resolve_depends(pinned, packages)
    needed = common.resolve_depends(selected, packages)
    enabled = set([name for name,info in iteritems(packages) if info.active])
    includes = (pinned | needed) - enabled
    excludes = enabled - (needed | pinned)
    common.save_metainfo(wsdir, packages)
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
    if args.clean:
        sys.stdout.write("Cleaning workspace...\n")
        call(["catkin", "clean", "--workspace", wsdir, "--profile", "rosrepo", "--all"])
