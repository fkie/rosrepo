#!/usr/bin/env python

import sys
import os
import common
from shutil import rmtree
from subprocess import call

def run(args):
  wsdir = common.find_wsdir(args.workspace)
  if wsdir is None:
    sys.stderr.write ("cannot find suitable catkin workspace\n")
    sys.exit(1)
  includes = set([])
  excludes = set([])
  packages = common.find_packages(wsdir)
  if args.all or args.package:
    if args.all: args.package = packages.keys()
    if not common.is_valid_selection(args.package, packages):
      sys.exit(1)
    selected = set(args.package)
    for name,info in packages.iteritems():
      info.meta["auto"] = not name in selected
    needed = common.resolve_depends(selected, packages)
    enabled = set([name for name,info in packages.iteritems() if info.enabled])
    includes = needed - enabled
    excludes = enabled - needed
  else:
    enabled = set([name for name,info in packages.iteritems() if info.enabled])
    disabled = set([name for name,info in packages.iteritems() if not info.enabled])
    includes = common.resolve_depends(enabled, packages) - enabled
    excludes = common.resolve_obsolete(packages) - includes - disabled
    for name,info in packages.iteritems():
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
  if args.clean or args.cc or args.cxx:
    sys.stdout.write("Cleaning workspace...\n")
    builddir = os.path.join(wsdir, "build")
    if os.path.isdir(builddir): rmtree(builddir)
    develdir = os.path.join(wsdir, "devel")
    if os.path.isdir(develdir): rmtree(develdir)
  os.chdir(wsdir)
  catkin_invoke = [ "catkin_make", "-k"]
  if args.cc: catkin_invoke = catkin_invoke + [ "-DCMAKE_C_COMPILER=%s" % args.cc ]
  if args.cxx: catkin_invoke = catkin_invoke + [ "-DCMAKE_CXX_COMPILER=%s" % args.cxx ]
  sys.stdout.write(" ".join(catkin_invoke) + "\n")
  call(catkin_invoke)

