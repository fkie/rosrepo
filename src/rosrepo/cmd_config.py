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
from .compat import iteritems
from .common import find_wsdir, DEFAULT_CMAKE_ARGS, get_c_compiler, get_cxx_compiler, call_process


def run(args):
    wsdir = find_wsdir(args.workspace)
    if wsdir is None:
        sys.stderr.write ("cannot find suitable catkin workspace\n")
        sys.exit(1)
    catkin_config = ["catkin", "config", "--workspace", wsdir, "--profile", "rosrepo"]
    if args.jobs:
        catkin_config = catkin_config + ["--jobs", args.jobs]
    if args.install:
        call_process(["catkin", "clean", "--workspace", wsdir, "--profile", "rosrepo", "--build", "--yes"])
        catkin_config = catkin_config + ["--install"]
    if args.no_install:
        call_process(["catkin", "clean", "--workspace", wsdir, "--profile", "rosrepo", "--build", "--install", "--yes"])
        catkin_config = catkin_config + ["--no-install"]
    if args.compiler:
        call_process(["catkin", "clean", "--workspace", wsdir, "--profile", "rosrepo", "--build", "--yes"])
        catkin_config = catkin_config + ["--cmake-args"] + DEFAULT_CMAKE_ARGS
        cc = get_c_compiler(args.compiler)
        cxx = get_cxx_compiler(args.compiler)
        if cc is not None:
            catkin_config = catkin_config + ["-DCMAKE_C_COMPILER=%s" % cc]
        if cxx is not None:
            catkin_config = catkin_config + ["-DCMAKE_CXX_COMPILER=%s" % cxx]
        catkin_config = catkin_config + ["--"]
    catkin_config = catkin_config + args.extra_args
    ret = call_process(catkin_config)
    if ret != 0: sys.exit(ret)

