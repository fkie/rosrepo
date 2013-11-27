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
import common
import shutil
import textwrap
from common import find_rosdir

def run(args):
  wsdir = common.find_wsdir(args.workspace)
  if wsdir is None:
    sys.stderr.write ("cannot find suitable catkin workspace\n")
    sys.exit(1)
  rosdir = find_rosdir()
  if rosdir is None:
    sys.stderr.write("Cannot detect ROS installation\n")
    sys.exit(1)
  srcdir = os.path.join(wsdir, "src")
  repodir = os.path.join(wsdir, "repos")
  packages = common.find_packages(wsdir)
  enabled = set([name for name,info in packages.iteritems() if info.enabled])
  for name in enabled:
    dest = os.path.join(srcdir, name)
    try:
      os.unlink(dest)
    except OSError as err:
      sys.stderr.write ("Cannot unlink %s: %s\n" % ( dest, str(err)))
  try:
    os.unlink(os.path.join(repodir, ".metainfo"))
  except OSError:
    pass
  repofiles = os.listdir(repodir)
  try:
    for entry in repofiles:
      path = os.path.join(repodir, entry)
      if entry == "CMakeLists.txt" or entry == "toplevel.cmake":
        sys.stdout.write("Deleting `%s' from `repos'...\n" % entry)
        os.unlink(path)
      else:
        sys.stdout.write("Moving `%s' from `repos' to `src'...\n" % entry)
        shutil.move(path, srcdir)
  except (shutil.Error, OSError) as e:
    sys.stderr.write("Error: %s" % str(e))
    sys.exit(1)
  try:
    os.rmdir(repodir)
  except OSError as err:
    sys.stderr.write ("Not removing `repos': %s" % str(err))
  sys.stdout.write(textwrap.dedent("""\

  Make sure you have the following lines in your .bashrc:
  --8<-------
  source %(rosdir)s/setup.bash
  source %(wsdir)s/devel/setup.bash
  -->8-------

  Compile the catkin workspace with the following commands:
  --8<-------
  cd %(wsdir)s
  catkin_make -k
  -->8-------

  """ % { "rosdir" : rosdir, "wsdir" : wsdir }))
