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
  enabled = set([name for name,info in iteritems(packages) if info.enabled])
  needed = common.resolve_depends(enabled, packages)
  depends = common.resolve_depends(set(args.package), packages)
  depends = (depends | needed) - enabled
  dep_auto = depends - set(args.package)
  dep_manual = depends - dep_auto
  if dep_manual:
    sys.stdout.write("Manually including the following packages:\n%s\n" % common.format_list(dep_manual))
    for name in dep_manual: packages[name].meta["auto"] = False
  if dep_auto:
    sys.stdout.write("Automatically including to satisfy dependencies:\n%s\n" % common.format_list(dep_auto))
    for name in dep_auto: packages[name].meta["auto"] = True
  for name in args.package:
    if packages[name].meta["auto"] != args.mark_auto:
      sys.stdout.write("Marking %s as %s included\n" % (name, "automatically" if args.mark_auto else "manually"))
      packages[name].meta["auto"] = args.mark_auto
  common.save_metainfo(wsdir, packages)
  if args.clean:
    sys.stdout.write("Cleaning workspace...\n")
    builddir = os.path.join(wsdir, "build")
    if os.path.isdir(builddir): rmtree(builddir)
    develdir = os.path.join(wsdir, "devel")
    if os.path.isdir(develdir): rmtree(develdir)
  if not depends:
    sys.stdout.write("Nothing else to be done\n")
    sys.exit(0)
  reposdir = os.path.join(wsdir, "repos")
  srcdir = os.path.join(wsdir, "src")
  for name in depends:
    info = packages[name]
    source = os.path.relpath(os.path.join(reposdir, info.path), srcdir)
    dest = os.path.join(srcdir, name)
    sys.stdout.write ("Including %s from %s...\n" % ( name, info.repo ))
    try:
      os.symlink(source, dest)
    except OSError as err:
      sys.stderr.write ("Cannot create %s: %s\n" % ( dest, str(err)))

