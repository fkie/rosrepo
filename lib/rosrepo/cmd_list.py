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
