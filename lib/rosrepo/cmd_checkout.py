#!/usr/bin/env python

import sys
import os
import subprocess
from common import find_wsdir

def run(args):
  wsdir = find_wsdir(args.workspace)
  if wsdir is None:
    sys.stderr.write ("cannot find suitable catkin workspace\n")
    sys.exit(1)
  if (args.link):
    if not os.path.isdir(args.url):
      sys.stderr.write("not an existing checkout: %s\n" % args.url)
      sys.exit(1)
    folder = args.name if args.name is not None else os.path.basename(args.url)
    dest = os.path.join(wsdir, "repos", folder)
    if os.path.islink(dest): os.unlink(dest)
    if os.path.exists(dest):
      sys.stderr.write("target already exists and is not a symlink: %s\n" % dest)
      sys.exit(1)
    os.symlink(args.url, dest)
    sys.exit(0)
  if (args.git): cmd = [ "git", "clone", args.url ]
  if (args.svn): cmd = [ "svn", "checkout", args.url ]
  if (args.name): cmd.append(args.name)
  os.chdir(os.path.join(wsdir, "repos"))
  ret = subprocess.call(cmd)
  sys.exit(ret)
