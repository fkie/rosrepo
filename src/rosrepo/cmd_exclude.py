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
    broken = set([name for name,info in iteritems(packages) if info.active and info.path is None])
    pinned = set([name for name,info in iteritems(packages) if info.pinned]) - broken
    if args.all:
        if pinned:
            sys.stdout.write("The following packages remain pinned:\n%s\n" % common.format_list(pinned))
        args.package = set(packages.keys()) - pinned
    else:
        args.package = common.glob_package_names(args.package, packages)
    if not common.is_valid_selection(args.package, packages):
        sys.exit(1)
    if broken:
        sys.stdout.write("The following BROKEN packages will be excluded by default:\n%s\n" % common.format_list(broken))
        args.package = args.package | broken
    unpin = pinned & args.package
    if unpin:
        sys.stdout.write("The following packages will be unpinned from workspace:\n%s\n" % common.format_list(unpin))
    pinned = pinned - args.package
    pinned_depends = common.resolve_depends(pinned, packages)
    disabled = set([name for name,info in iteritems(packages) if not info.active])
    rdepends = common.resolve_rdepends(args.package, packages)
    rdepends = rdepends - disabled - pinned_depends
    obsolete = common.resolve_obsolete(packages, rdepends) - rdepends - pinned_depends
    if rdepends - broken:
        sys.stdout.write("The following packages will be excluded from workspace:\n%s\n" % common.format_list(rdepends - broken))
    if obsolete:
        sys.stdout.write("The following packages are no longer needed:\n%s\n" % common.format_list(obsolete))
        rdepends = rdepends | obsolete
    if args.clean:
        sys.stdout.write("Cleaning workspace...\n")
        call(["catkin", "clean", "--workspace", wsdir, "--profile", "rosrepo", "--all"])
    if not rdepends:
        sys.stdout.write("Nothing else to be done\n")
        sys.exit(0)
    for name in rdepends:
        packages[name].selected = False
        packages[name].active = False
        packages[name].pinned = False
    common.save_metainfo(wsdir, packages)
