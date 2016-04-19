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
from .common import find_wsdir, call_process

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
        dest = os.path.join(wsdir, "src", folder)
        if os.path.islink(dest): os.unlink(dest)
        if os.path.exists(dest):
            sys.stderr.write("target already exists and is not a symlink: %s\n" % dest)
            sys.exit(1)
        os.symlink(args.url, dest)
        sys.exit(0)
    if (args.git): cmd = [ "git", "clone", args.url ]
    if (args.svn): cmd = [ "svn", "checkout", args.url ]
    if (args.name): cmd.append(args.name)
    os.chdir(os.path.join(wsdir, "src"))
    ret = call_process(cmd)
    sys.exit(ret)
