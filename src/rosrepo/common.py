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
import pickle
import re
from fnmatch import fnmatchcase
from copy import copy
from textwrap import fill
from catkin_pkg.packages import find_packages as find_catkin_packages
from .compat import iteritems

COMPILER_LIST = [
    [r"gcc|gnu","gcc","g++"],
    [r"intel|icc|icpc","icc","icpc"],
    [r"clang","clang","clang++"],
]

DEFAULT_CMAKE_ARGS = [
     "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
     "-DCMAKE_CXX_FLAGS=-Wall -Wextra -Wno-ignored-qualifiers -Wno-invalid-offsetof -Wno-unused-parameter -fno-omit-frame-pointer",
     "-DCMAKE_CXX_FLAGS_RELWITHDEBINFO=-O3 -g",
     "-DCMAKE_C_FLAGS=-Wall -Wextra -Wno-unused-parameter -fno-omit-frame-pointer",
     "-DCMAKE_C_FLAGS_RELWITHDEBINFO=-O3 -g",
     "-DCMAKE_SHARED_LINKER_FLAGS=-Wl,-z,defs",
     "-DCMAKE_EXE_LINKER_FLAGS=-Wl,-z,defs"
]

class PkgInfo:
    path = None
    manifest = None
    active = False
    selected = False
    pinned = False

def format_list(packages):
    return fill(", ".join(sorted(list(packages))), initial_indent="    ", subsequent_indent="    ")

def glob_package_names(globs, packages):
    selected = set([])
    for g in globs:
        found = False
        for pkg in packages.keys():
            if fnmatchcase(pkg, g):
                selected.add(pkg)
                found = True
        if not found: selected.add(g)
    return selected

def is_valid_selection(selected, packages):
    result = True
    for name in selected:
        if not name in packages:
            sys.stderr.write("Unknown package: %s\n" % name)
            result = False
        elif packages[name].path is None:
            sys.stderr.write("Package is not available: %s\n" % name)
    return result

def resolve_depends(selected, packages):
    resolve = True
    depends = copy(selected)
    while resolve:
        resolve = False
        for name in list(depends):
            info = packages[name]
            if info.manifest is None:
                continue
            for dep in info.manifest.buildtool_depends + info.manifest.build_depends + info.manifest.run_depends + info.manifest.test_depends:
                if dep.name in packages and not dep.name in depends:
                    depends.add(dep.name)
                    resolve = True
    return depends

def resolve_rdepends(selected, packages):
    resolve = True
    rdepends = copy(selected)
    while resolve:
        resolve = False
        for name,info in iteritems(packages):
            if name in rdepends: continue
            if info.manifest is None:
                continue
            for dep in info.manifest.buildtool_depends + info.manifest.build_depends + info.manifest.run_depends + info.manifest.test_depends:
                if dep.name in packages and dep.name in rdepends:
                    rdepends.add(name)
                    resolve = True
    return rdepends

def resolve_obsolete(packages, removed=None):
    manual = set([name for name,info in iteritems(packages) if info.active and info.selected])
    automatic = set([name for name,info in iteritems(packages) if info.active and not info.selected])
    if not removed is None:
        manual = manual - removed
    depends = resolve_depends(manual, packages)
    return automatic - depends

def find_packages(wsdir):
    found = set([])
    result = load_metainfo(wsdir)
    srcdir = os.path.join(wsdir, "src")
    try:
        packages = find_catkin_packages(srcdir, exclude_subspaces=True)
        for path, pkg in packages.items():
            if not pkg.name in result:
                result[pkg.name] = PkgInfo()
            info = result[pkg.name]
            info.path = path
            info.manifest = pkg
            found.add(pkg.name)
        for name,info in iteritems(result):
            if name not in found: info.path = None
    except Exception as err:
        sys.stderr.write("Error: %s\n" % str(err))
        sys.exit(1)
    return result

def load_metainfo(wsdir):
    infodir = os.path.join(wsdir, ".rosrepo")
    infofile = os.path.join(infodir, "info")
    packages = {}
    if os.path.isfile(infofile):
        try:
            with open(infofile, "r") as f:
                packages = pickle.load(f)
        except:
            pass
    return packages

def save_metainfo(wsdir, packages):
    infodir = os.path.join(wsdir, ".rosrepo")
    infofile = os.path.join(infodir, "info")
    obsolete = [name for name,info in iteritems(packages) if not info.active and not info.selected and info.path is None]
    for key in obsolete: del packages[key]
    try:
        if not os.path.isdir(infodir): os.mkdir(infodir)
        with open(infofile, "w") as f:
            pickle.dump(packages, f, -1)
    except OSError as e:
        sys.stderr.write("cannot write meta info: %s\n" % str(e))

def find_ros_fkie():
    result = []
    for root, dirs, files in os.walk(os.path.expanduser("~")):
        if "CATKIN_IGNORE" in files:
            del dirs[:]
        elif ".svn" in dirs or ".git" in dirs:
            if "core_fkie" in dirs:
                result.append(root)
                del dirs[:]
        for name in list(dirs):
            if name.startswith("."): dirs.remove(name)
        dirs.sort()
    return result

def _is_rosdir(path):
    if not os.path.isdir(os.path.join(path, "bin")): return False
    if not os.path.isdir(os.path.join(path, "etc")): return False
    if not os.path.isdir(os.path.join(path, "include")): return False
    if not os.path.isdir(os.path.join(path, "lib")): return False
    if not os.path.isdir(os.path.join(path, "share")): return False
    if not os.path.isfile(os.path.join(path, "setup.sh")): return False
    return True

def find_rosdir(override=None):
    if override is not None:
        if os.path.islink(override):
            override = os.path.join(os.path.dirname(override), os.readlink(override))
        if _is_rosdir(override): return override
        return None
    if "ROS_ROOT" in os.environ:
        rosrootdir = os.environ["ROS_ROOT"]
        if os.path.isdir(rosrootdir):
            rosdir = os.path.normpath(os.path.join(rosrootdir, "..", ".."))
            if _is_rosdir(rosdir): return rosdir
    if "ROS_PACKAGE_PATH" in os.environ:
        candidates = os.environ["ROS_PACKAGE_PATH"].split(":")
        candidates.reverse()
        for path in candidates:
            rosdir = os.path.normpath(os.path.join(path, ".."))
            if _is_rosdir(rosdir): return rosdir
    if os.path.islink("/opt/ros/current"):
        rosdir = os.path.join("/opt/ros", os.readlink("/opt/ros/current"))
        if _is_rosdir(rosdir): return rosdir
    return None

_obsolete_warn_once = True

def _is_wsdir(path):
    if not os.path.isdir(os.path.join(path, "src")): return False
    if os.path.isdir(os.path.join(path, "repos")):
        global _obsolete_warn_once
        if _obsolete_warn_once:
            sys.stderr.write("obsolete workspace layout detected\nplease re-run `rosrepo init %s'\n" % path)
            _obsolete_warn_once = False
        return False
    if not os.path.isdir(os.path.join(path, ".catkin_tools", "rosrepo")): return False
    return os.path.isfile(os.path.join(path, ".catkin_workspace"))

def find_wsdir(override=None):
    if override is not None:
        if _is_wsdir(override): return override
        return None
    if _is_wsdir(os.getcwd()): return os.getcwd()
    if not "ROS_PACKAGE_PATH" in os.environ: return None
    candidates = os.environ["ROS_PACKAGE_PATH"].split(":")
    for path in candidates:
        head, tail = os.path.split(path)
        while head != "/" and head != "" and tail != "src":
            head, tail = os.path.split(head)
        if tail != "src": continue
        if _is_wsdir(head): return head
    return None

def get_c_compiler(s):
    global COMPILER_LIST
    for compiler in COMPILER_LIST:
        m = re.match(r"^(.*)\b(?:%s)\b(.*)$" % compiler[0], s, re.IGNORECASE)
        if m is not None: return "%s%s%s" % (m.group(1), compiler[1], m.group(2))
    return None

def get_cxx_compiler(s):
    global COMPILER_LIST
    for compiler in COMPILER_LIST:
        m = re.match(r"^(.*)\b(?:%s)\b(.*)$" % compiler[0], s, re.IGNORECASE)
        if m is not None: return "%s%s%s" % (m.group(1), compiler[2], m.group(2))
    return None

def find_program(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            fpath = path.strip('"')
            candidate = os.path.join(fpath, program)
            if is_exe(candidate):
                return candidate
    return None

def getmtime(path):
    return os.path.getmtime(path) if os.path.exists(path) else 0

