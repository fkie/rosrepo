#!/usr/bin/env python

import sys
import os
import common
from shutil import rmtree

def run(args):
  wsdir = common.find_wsdir(args.workspace)
  if wsdir is None:
    sys.stderr.write ("cannot find suitable catkin workspace\n")
    sys.exit(1)
  packages = common.find_packages(wsdir)
  if args.all: args.package = packages.keys()
  if not common.is_valid_selection(args.package, packages):
    sys.exit(1)
  enabled = set([name for name,info in packages.iteritems() if info.enabled])
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

