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
  disabled = set([name for name,info in packages.iteritems() if not info.enabled])
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

