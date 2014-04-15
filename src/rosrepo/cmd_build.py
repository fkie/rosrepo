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
  if args.all or args.package:
    if args.all: 
      args.package = packages.keys()
    else:
      args.package = common.glob_package_names(args.package, packages)
    if not common.is_valid_selection(args.package, packages):
      sys.exit(1)
    selected = set(args.package)
    for name,info in iteritems(packages):
      info.meta["auto"] = not name in selected
    needed = common.resolve_depends(selected, packages)
    enabled = set([name for name,info in iteritems(packages) if info.enabled])
    includes = needed - enabled
    excludes = enabled - needed
  else:
    enabled = set([name for name,info in iteritems(packages) if info.enabled])
    disabled = set([name for name,info in iteritems(packages) if not info.enabled])
    includes = common.resolve_depends(enabled, packages) - enabled
    excludes = common.resolve_obsolete(packages) - includes - disabled
    for name,info in iteritems(packages):
      if not name in enabled: info.meta["auto"] = True
  common.save_metainfo(wsdir, packages)
  if includes:
    sys.stdout.write("The following packages need to be included:\n%s\n" % common.format_list(includes))
  if excludes:
    sys.stdout.write("The following packages are no longer needed:\n%s\n" % common.format_list(excludes))
  reposdir = os.path.join(wsdir, "repos")
  srcdir = os.path.join(wsdir, "src")
  for name in includes:
    info = packages[name]
    source = os.path.relpath(os.path.join(reposdir, info.path), srcdir)
    dest = os.path.join(srcdir, name)
    sys.stdout.write ("Including %s from %s...\n" % ( name, info.repo ))
    try:
      if os.path.islink(dest): os.remove(dest)
      os.symlink(source, dest)
    except OSError as err:
      sys.stderr.write ("Cannot create %s: %s\n" % ( dest, str(err)))
      sys.exit(1)
  for name in excludes:
    dest = os.path.join(srcdir, name)
    sys.stdout.write ("Excluding %s...\n" % name)
    try:
      os.unlink(dest)
    except OSError as err:
      sys.stderr.write ("Cannot unlink %s: %s\n" % ( dest, str(err)))
      sys.exit(1)
  if args.clean or args.clang or args.gcc:
    sys.stdout.write("Cleaning workspace...\n")
    builddir = os.path.join(wsdir, "build")
    if os.path.isdir(builddir): rmtree(builddir)
    develdir = os.path.join(wsdir, "devel")
    if os.path.isdir(develdir): rmtree(develdir)
  os.chdir(wsdir)
  catkin_invoke = [ "catkin_make" ]
  if args.clang: catkin_invoke = catkin_invoke + [ "-DCMAKE_C_COMPILER=clang", "-DCMAKE_CXX_COMPILER=clang++" ]
  if args.gcc: catkin_invoke = catkin_invoke + [ "-DCMAKE_C_COMPILER=gcc", "-DCMAKE_CXX_COMPILER=g++" ]
  catkin_invoke = catkin_invoke + args.extra_args
  sys.stdout.write(" ".join(catkin_invoke) + "\n")
  call(catkin_invoke)

