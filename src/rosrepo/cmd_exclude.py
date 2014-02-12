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
from shutil import rmtree
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
  disabled = set([name for name,info in iteritems(packages) if not info.enabled])
  rdepends = common.resolve_rdepends(set(args.package), packages)
  rdepends = rdepends - disabled
  obsolete = common.resolve_obsolete(packages, rdepends) - rdepends
  if rdepends:
    sys.stdout.write("The following packages will be excluded from workspace:\n%s\n" % common.format_list(rdepends))
  if obsolete:
    sys.stdout.write("The following packages are no longer needed:\n%s\n" % common.format_list(obsolete))
    rdepends = rdepends | obsolete
  if args.clean:
    sys.stdout.write("Cleaning workspace...\n")
    builddir = os.path.join(wsdir, "build")
    if os.path.isdir(builddir): rmtree(builddir)
    develdir = os.path.join(wsdir, "devel")
    if os.path.isdir(develdir): rmtree(develdir)
  if not rdepends:
    sys.stdout.write("Nothing else to be done\n")
    sys.exit(0)
  srcdir = os.path.join(wsdir, "src")
  for name in rdepends:
    dest = os.path.join(srcdir, name)
    sys.stdout.write ("Excluding %s...\n" % name)
    packages[name].meta["auto"] = True
    try:
      os.unlink(dest)
    except OSError as err:
      sys.stderr.write ("Cannot unlink %s: %s\n" % ( dest, str(err)))
  common.save_metainfo(wsdir, packages)

