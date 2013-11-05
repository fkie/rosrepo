#!/usr/bin/env python

import sys
from common import find_wsdir, find_packages

def run(args):
  wsdir = find_wsdir(args.workspace)
  if wsdir is None:
    sys.stderr.write ("cannot find suitable catkin workspace\n")
    sys.exit(1)
  packages = find_packages(wsdir)
  listing = []
  plen = 7
  rlen = 10
  for name, info in packages.items():
    if plen < len(name): plen = len(name)
    if rlen < len(info.repo): rlen = len(info.repo)
    if info.enabled:
      status = "B"
      if info.meta["auto"]: status = status + "A"
    else:
      status = "-"
    listing.append([ name, status, info.repo ])
  if plen > 52: plen = 52
  if plen + rlen > 72: rlen = 62 - plen
  fmt = "%%-%ds  %%-%ds  %%-6s\n" % (plen, rlen)
  if not args.name_only:
    sys.stdout.write(fmt % ( "Package", "Repository", "Status" ))
    sys.stdout.write(fmt % ( "-------", "----------", "------" ))
  listing.sort()
  for name, status, repo in listing:
    if not args.all:
      if status == "-": continue
      if args.manual and "A" in status: continue
    if args.name_only:
      sys.stdout.write("%s\n" % name)
    else:
      sys.stdout.write(fmt % (name[:plen], repo[:rlen], status))
  if not args.name_only: sys.stdout.write("\n")
