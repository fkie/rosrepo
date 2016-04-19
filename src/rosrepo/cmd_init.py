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
import os
import sys
import shutil
import textwrap

from .common import find_rosdir, find_ros_fkie, save_metainfo, PkgInfo, DEFAULT_CMAKE_ARGS, get_c_compiler, get_cxx_compiler, call_process

def run(args):
    wsdir = os.path.realpath(args.path)
    if (args.delete): shutil.rmtree(wsdir)
    srcdir = os.path.join(wsdir, "src")
    rosdir = find_rosdir(args.roshome)
    if rosdir is None:
        sys.stderr.write("Cannot detect ROS installation\n")
        sys.exit(1)
    repodir = os.path.join(wsdir, "repos")
    if os.path.realpath(os.path.expanduser("~")) == wsdir:
        sys.stderr.write("You are trying to convert your home directory into a ROS workspace.\nThis is almost certainly not what you want.\n")
        sys.exit(1)
    if not os.path.exists(srcdir): os.makedirs(srcdir)
    if os.path.isdir(repodir):
        metainfo = os.path.join(repodir, ".metainfo")
        builddir = os.path.join(wsdir, "build")
        develdir = os.path.join(wsdir, "devel")
        installdir = os.path.join(wsdir, "install")
        toplevel_cmake = os.path.join(srcdir, "toplevel.cmake")
        cmakelists_txt = os.path.join(srcdir, "CMakeLists.txt")
        sys.stdout.write("Updating workspace to new layout...\n")
        if os.path.exists(toplevel_cmake): os.unlink(toplevel_cmake)
        if os.path.exists(cmakelists_txt): os.unlink(cmakelists_txt)
        if os.path.isdir(builddir): shutil.rmtree(builddir)
        if os.path.isdir(develdir): shutil.rmtree(develdir)
        if os.path.isdir(installdir): shutil.rmtree(installdir)
        old_meta = {}
        new_meta = {}
        if os.path.isfile(metainfo):
            import yaml
            try:
                with open(metainfo, "r") as f:
                    old_meta = yaml.safe_load(f)
            except:
                pass
        try:
            srcfiles = os.listdir(srcdir)
            for entry in srcfiles:
                path = os.path.join(srcdir, entry)
                if os.path.isdir(path):
                    if os.path.islink(path):
                        realpath = os.readlink(path)
                        if not os.path.isabs(realpath): realpath = os.path.normpath(os.path.join(srcdir, realpath))
                        if realpath.startswith(repodir):
                            info = PkgInfo()
                            info.active = True
                            if entry in old_meta:
                                if not old_meta[entry]["auto"]:
                                    info.selected = True
                                    sys.stdout.write("Marking %s as manually included\n" % entry)
                                else:
                                    sys.stdout.write("Marking %s as automatically included\n" % entry)
                                if old_meta[entry]["pin"]:
                                    info.pinned = True
                                    sys.stdout.write("Marking %s as pinned\n" % entry)
                            new_meta[entry] = info
                            os.unlink(path)
            if os.path.isfile(metainfo): os.unlink(metainfo)
            repofiles = os.listdir(repodir)
            for entry in repofiles:
                path = os.path.join(repodir, entry)
                sys.stdout.write("Moving `%s' from `repos' to `src'...\n" % entry)
                shutil.move(path, srcdir)
            os.rmdir(repodir)
        except shutil.Error as e:
            sys.stderr.write("Error: %s" % str(e))
            sys.exit(1)
        save_metainfo(wsdir, new_meta)
    with open(os.path.join(wsdir, ".catkin_workspace"), "w") as f:
        f.write("# This file currently only serves to mark the location of a catkin workspace for tool integration\n")
    with open(os.path.join(wsdir, "setup.bash"), "w") as f:
        f.write(textwrap.dedent("""\
        # workspace configuration
        # source this file from your ~/.bashrc
        [ -r "%(rosdir)s/setup.bash" ] && source "%(rosdir)s/setup.bash"
        [ -r "%(wsdir)s/devel/setup.bash" ] && source "%(wsdir)s/devel/setup.bash"
        eval "$(rosrepo bash -w "%(wsdir)s" -e)"
        """ % { "rosdir" : rosdir, "wsdir" : wsdir }))
    catkin_config = ["catkin", "config", "--workspace", wsdir, "--profile", "rosrepo",
                     "--init", "--extend", rosdir
    ]
    if args.jobs:
        catkin_config = catkin_config + ["--jobs", args.jobs]
    if args.install:
        catkin_config = catkin_config + ["--install"]
    if args.no_install:
        catkin_config = catkin_config + ["--no-install"]

    catkin_config = catkin_config + ["--cmake-args"] + DEFAULT_CMAKE_ARGS
    if args.compiler:
        cc = get_c_compiler(args.compiler)
        cxx = get_cxx_compiler(args.compiler)
        if cc is not None:
            catkin_config = catkin_config + ["-DCMAKE_C_COMPILER=%s" % cc]
        if cxx is not None:
            catkin_config = catkin_config + ["-DCMAKE_CXX_COMPILER=%s" % cxx]
    catkin_config = catkin_config + ["--"] + args.extra_args
    ret = call_process(catkin_config)
    if ret != 0: sys.exit(ret)
    if args.autolink:
        sys.stdout.write("Searching for ROS-FKIE checkout\n")
        ros_fkie_dirs = find_ros_fkie()
        if len(ros_fkie_dirs) == 0:
            sys.stdout.write("Warning: no ROS-FKIE checkout found\n")
        else:
            if len(ros_fkie_dirs) > 1:
                sys.stdout.write("Warning: multiple ROS-FKIE checkouts found, using first\n")
                for d in ros_fkie_dirs:
                    sys.stdout.write ("  -- %s\n" % d)
            source = ros_fkie_dirs[0]
            dest = os.path.join(srcdir, "ros-fkie")
            if os.path.islink(dest): os.unlink(dest)
            if not os.path.exists(dest):
                sys.stdout.write ("Symlinking %s\n" % source)
                os.symlink (source, dest)
            else:
                sys.stdout.write ("Error: Will not symlink, %s already exists\n" % dest)
    sys.stdout.write(textwrap.dedent("""\

    Make sure you have the following line in your .bashrc:
    --8<-------
    source %(wsdir)s/setup.bash
    -->8-------

    * Add packages to the working set with `rosrepo include'
    * Remove packages from the working set with `rosrepo exclude'
    * Build the working set with `rosrepo build'

    """ % { "rosdir" : rosdir, "wsdir" : wsdir }))

