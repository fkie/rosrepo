"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import os
from .util import path_has_prefix, iteritems


def is_ros_root(path):
    if not os.path.isdir(os.path.join(path, "bin")): return False
    if not os.path.isdir(os.path.join(path, "etc")): return False
    if not os.path.isdir(os.path.join(path, "include")): return False
    if not os.path.isdir(os.path.join(path, "lib")): return False
    if not os.path.isdir(os.path.join(path, "share")): return False
    if not os.path.isfile(os.path.join(path, "setup.sh")): return False
    return True


def find_ros_root(override=None):
    if override is not None:
        if is_ros_root(override): return os.path.realpath(override)
        return None
    if "ROS_ROOT" in os.environ:
        rosrootdir = os.environ["ROS_ROOT"]
        if os.path.isdir(rosrootdir):
            rosdir = os.path.normpath(os.path.join(rosrootdir, os.pardir, os.pardir))
            if is_ros_root(rosdir): return os.path.realpath(rosdir)
    if "ROS_PACKAGE_PATH" in os.environ:
        candidates = os.environ["ROS_PACKAGE_PATH"].split(os.pathsep)
        candidates.reverse()
        for path in candidates:
            rosdir = os.path.normpath(os.path.join(path, os.pardir))
            if is_ros_root(rosdir): return os.path.realpath(rosdir)
    if os.path.islink("/opt/ros/current"):
        rosdir = os.path.join("/opt/ros", os.readlink("/opt/ros/current"))
        if is_ros_root(rosdir): return os.path.realpath(rosdir)
    return None


def is_catkin_workspace(path):
    return os.path.isfile(os.path.join(path, ".catkin_workspace"))


def is_rosrepo_workspace(path):
    if not os.path.isfile(os.path.join(path, ".catkin_workspace")): return False
    if not os.path.isfile(os.path.join(path, ".rosrepo", "config")): return False
    if not os.path.isdir(os.path.join(path, "src")): return False
    return True


def find_workspace(override=None):
    if override is not None:
        if is_catkin_workspace(override): return os.path.realpath(override)
        return None
    if "ROS_PACKAGE_PATH" in os.environ:
        candidates = os.environ["ROS_PACKAGE_PATH"].split(os.pathsep)
        for path in candidates:
            wsdir = os.path.normpath(os.path.join(path, os.pardir))
            if is_catkin_workspace(wsdir): return os.path.realpath(wsdir)
    wsdir = os.path.join(os.path.expanduser("~"), "ros")
    if is_catkin_workspace(wsdir): return os.path.realpath(wsdir)
    return None


def find_catkin_packages(srcdir, subdir=None, cache=None):
    from catkin_pkg.package import parse_package, InvalidPackage, PACKAGE_MANIFEST_FILENAME
    cached_paths = {}
    if cache is not None:
        cached_paths = cache.get_object("local_packages", 1, cached_paths)
    package_paths = []
    base_path = srcdir if subdir is None else os.path.join(srcdir, subdir)
    for curdir, subdirs, files in os.walk(base_path, followlinks=True):
        if "CATKIN_IGNORE" in files:
            del subdirs[:]
            continue
        if PACKAGE_MANIFEST_FILENAME in files:
            package_paths.append(os.path.relpath(curdir, srcdir))
            del subdirs[:]
            continue
        subdirs = [d for d in subdirs if not d.startswith(".")]
    result = {}
    discovered_paths = {}
    for path in package_paths:
        try:
            cur_ts = os.path.getmtime(os.path.join(srcdir, path, PACKAGE_MANIFEST_FILENAME))
            manifest = None
            if path in cached_paths:
                old_ts = cached_paths[path]["t"]
                if old_ts == cur_ts:
                    manifest = cached_paths[path]["m"]
            if manifest is None:
                manifest = parse_package(os.path.join (srcdir, path, PACKAGE_MANIFEST_FILENAME))
            if not manifest.name in result:
                result[manifest.name] = []
            result[manifest.name].append((path, manifest))
            discovered_paths[path] = {"t": cur_ts, "m": manifest}
        except InvalidPackage:
            pass
    if subdir is not None:
        for path, entry in iteritems(cached_paths):
            if path_has_prefix(path, subdir):
                discovered_paths[path] = entry
    if cache is not None:
        cache.set_object("local_packages", 1, discovered_paths)
