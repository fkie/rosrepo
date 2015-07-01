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
import rosrepo.common as common

def print_var (key, value, terse, export):
    sys.stdout.write("%s\n" % value if terse else "%s%s=%s\n" % ("export " if export else "", key, value))

def run(args):
    wsdir = common.find_wsdir(args.workspace)
    if wsdir is None:
        sys.stderr.write ("cannot find suitable catkin workspace\n")
        sys.exit(1)
    if not args.var: args.var = ["ROS_WORKSPACE","ROS_PACKAGE_PATH"]
    for key in args.var:
        if key == "ROS_WORKSPACE":
            print_var(key, wsdir, args.terse, args.export)
        elif key == "ROS_PACKAGE_PATH":
            has_srcdir = False
            srcdir = os.path.join(wsdir, "src")
            path = os.environ["ROS_PACKAGE_PATH"] if "ROS_PACKAGE_PATH" in os.environ else ""
            new_path = []
            for path in path.split(os.pathsep):
                if os.path.commonprefix([path, srcdir]) == srcdir:
                    if not has_srcdir:
                        has_srcdir = True
                        new_path.append(srcdir)
                else:
                    new_path.append(path)
            if not has_srcdir:
                new_path.insert(0, srcdir)
            print_var(key, os.pathsep.join(new_path), args.terse, args.export)
        else:
            if key in os.environ:
                print_var(key, os.environ[key], args.terse, args.export)
            else:
                if not args.terse: sys.stdout.write ("# variable %s is not set\n" % key)
