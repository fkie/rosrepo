#!/usr/bin/env python

import os
import sys
import shutil
import textwrap
from subprocess import call

from common import find_rosdir, find_ros_fkie

def run(args):
  wsdir = os.path.realpath(args.path)
  if (args.delete): shutil.rmtree(wsdir)
  srcdir = os.path.join(wsdir, "src")
  repodir = os.path.join(wsdir, "repos")
  builddir = os.path.join(wsdir, "build")
  develdir = os.path.join(wsdir, "devel")
  installdir = os.path.join(wsdir, "install")
  toplevel_cmake = os.path.join(srcdir, "toplevel.cmake")
  cmakelists_txt = os.path.join(srcdir, "CMakeLists.txt")
  rosdir = find_rosdir()
  if rosdir is None:
    sys.stderr.write("Cannot detect ROS installation\n")
    sys.exit(1)
  if not os.path.exists(srcdir): os.makedirs(srcdir)
  if not os.path.exists(repodir): os.makedirs(repodir)
  srcfiles = os.listdir(srcdir)
  try:
    for entry in srcfiles:
      path = os.path.join(srcdir, entry)
      if os.path.isdir(path):
        if os.path.islink(path):
          realpath = os.readlink(path)
          if not os.path.isabs(realpath): realpath = os.path.normpath(os.path.join(srcdir, realpath))
          if not realpath.startswith(repodir):
            sys.stdout.write("Moving '%s'...\n" % entry)
            shutil.move(path, repodir)
        else:
          sys.stdout.write("Moving '%s'...\n" % entry)
          shutil.move(path, repodir)
  except shutil.Error as e:
    sys.stderr.write("Error: %s" % str(e))
    sys.exit(1)
  if os.path.islink(toplevel_cmake): os.unlink(toplevel_cmake)
  if not os.path.exists(toplevel_cmake):
    os.symlink(os.path.join(rosdir, "share", "catkin", "cmake", "toplevel.cmake"), os.path.join(srcdir, "toplevel.cmake"))
  if os.path.islink(cmakelists_txt): os.unlink(cmakelists_txt)
  if not os.path.exists(cmakelists_txt):
    f = open(cmakelists_txt, "w")
    f.write(textwrap.dedent("""\
      cmake_minimum_required(VERSION 2.8.3)
      set(CMAKE_CXX_FLAGS_DEVEL "-Wall -Wextra -Wno-ignored-qualifiers -Wno-invalid-offsetof -Wno-unused-parameter -O3 -g" CACHE STRING "Devel build type CXX flags")
      set(CMAKE_C_FLAGS_DEVEL "-Wall -Wextra -Wno-unused-parameter -O3 -g" CACHE STRING "Devel build type C flags")
      set(CMAKE_SHARED_LINKER_FLAGS_DEVEL "-Wl,-z,defs" CACHE STRING "Devel build type shared library linker flags")
      set(CMAKE_EXE_LINKER_FLAGS_DEVEL "-Wl,-z,defs" CACHE STRING "Devel build type executable linker flags")

      if(NOT CMAKE_BUILD_TYPE)
          message(STATUS "Using default CMAKE_BUILD_TYPE=Devel")
          set(CMAKE_BUILD_TYPE Devel)
      endif(NOT CMAKE_BUILD_TYPE)

      if(EXISTS "${CMAKE_SOURCE_DIR}/blacklist.txt")
          file(STRINGS "${CMAKE_SOURCE_DIR}/blacklist.txt" _blacklisted)
          message(STATUS "Backlisted packages: ${_blacklisted}")
          set(CATKIN_BLACKLIST_PACKAGES "${_blacklisted}" CACHE STRING "Packages which are not to be built")
      endif(EXISTS "${CMAKE_SOURCE_DIR}/blacklist.txt")

      include(toplevel.cmake)
    """))
    f.close()
  if not os.path.exists(builddir):
    os.makedirs(builddir)
    os.chdir(builddir)
    ret = call([ "cmake", srcdir, "-DCATKIN_DEVEL_PREFIX=%s" % develdir, "-DCMAKE_INSTALL_PREFIX=%s" % installdir ])
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
      dest = os.path.join(repodir, "ros-fkie")
      if os.path.islink(dest): os.unlink(dest)
      if not os.path.exists(dest):
        sys.stdout.write ("Symlinking %s\n" % source)
        os.symlink (source, dest)
      else:
        sys.stdout.write ("Error: Will not symlink, %s already exists\n" % dest)
  sys.stdout.write(textwrap.dedent("""\

  Add the following lines to your .bashrc:
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
