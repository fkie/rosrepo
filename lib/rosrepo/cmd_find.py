#!/usr/bin/env python

import sys
import os
from common import find_wsdir, find_packages

def run(args):
  wsdir = find_wsdir(args.workspace)
  reposdir = os.path.join(wsdir, "repos")
  if wsdir is None:
    sys.stderr.write ("cannot find suitable catkin workspace\n")
    sys.exit(1)
  packages = find_packages(wsdir)
  if packages.has_key(args.package):
    pass
  else:
    sys.stderr.write ("no such package: %s\n" % args.package)
    sys.exit(1)
  path = packages[args.package].path
  if args.relative:
    path = os.path.join("repos", path)
  else:
    path = os.path.join(reposdir, path)
  sys.stdout.write("%s\n" % path)
