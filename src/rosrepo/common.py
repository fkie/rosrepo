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
import yaml
from fnmatch import fnmatchcase
from copy import copy
from textwrap import fill
from catkin_pkg.packages import find_packages as find_catkin_packages
from .compat import iteritems

class PkgInfo:
  path = None
  enabled = False
  manifest = None
  meta = None
  repo = None

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
  return result

def resolve_depends(selected, packages):
  resolve = True
  depends = copy(selected)
  while resolve:
    resolve = False
    for name in list(depends):
      info = packages[name]
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
      for dep in info.manifest.buildtool_depends + info.manifest.build_depends + info.manifest.run_depends + info.manifest.test_depends:
        if dep.name in packages and dep.name in rdepends:
          rdepends.add(name)
          resolve = True
  return rdepends

def resolve_obsolete(packages, removed=None):
  manual = set([ name for name,info in iteritems(packages) if info.enabled and not info.meta["auto"] ])
  automatic = set([ name for name,info in iteritems(packages) if info.enabled and info.meta["auto"] ])
  if not removed is None:
    manual = manual - removed
  depends = resolve_depends(manual, packages)
  return automatic - depends

def find_packages(wsdir):
  reposdir = os.path.join(wsdir, "repos")
  srcdir = os.path.join(wsdir, "src")
  result = {}
  meta = {}
  metainfo = os.path.join(reposdir, ".metainfo")
  if os.path.isfile(metainfo):
    try:
      f = open(metainfo, "r")
      meta = yaml.safe_load(f)
      f.close()
    except:
      meta = {}
  try:
      packages = find_catkin_packages(reposdir, exclude_subspaces=True)
      for path, pkg in packages.items():
        parts = path.split(os.path.sep)
        linkpath = os.path.join(srcdir, pkg.name)
        pkgpath = os.path.join(reposdir, path)
        info = PkgInfo()
        if os.path.islink(linkpath) and os.path.realpath(linkpath) == os.path.realpath(pkgpath):
          info.enabled = True
        info.path = path
        info.manifest = pkg
        info.repo = parts[0]
        info.meta = {}
        info.meta["auto"] = not info.enabled
        if pkg.name in meta:
          info.meta.update(meta[pkg.name])
        result[pkg.name] = info
  except Exception as err:
      sys.stderr.write("Error: %s\n" % str(err))
      sys.exit(1)
  return result

def save_metainfo(wsdir, packages):
  metainfo = os.path.join(wsdir, "repos", ".metainfo")
  meta = {}
  for name,info in iteritems(packages):
    meta[name] = info.meta
  try:
    f = open(metainfo, "w")
    yaml.dump(meta, f)
    f.close()
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

def find_rosdir():
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
  return None

def _is_wsdir(path):
  if not os.path.isdir(os.path.join(path, "src")): return False
  if not os.path.isdir(os.path.join(path, "repos")): return False
  if not os.path.exists(os.path.join(path, "src", "CMakeLists.txt")): return False
  return True

def find_wsdir(override=None):
  if override is not None:
    if _is_wsdir(override): return override
    return None
  if _is_wsdir(os.getcwd()): return os.getcwd()
  if not "ROS_PACKAGE_PATH" in os.environ: return None
  candidates = os.environ["ROS_PACKAGE_PATH"].split(":")
  for path in candidates:
    path = os.path.normpath(os.path.join(path, ".."))
    if _is_wsdir(path): return path
  return None