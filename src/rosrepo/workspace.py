"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import os
from .config import Config
from .cache import Cache
from .gitlab import find_available_gitlab_projects, find_catkin_packages_from_gitlab_projects, find_cloned_gitlab_projects
from .util import path_has_prefix, iteritems, NamedTuple

WORKSPACE_PACKAGE_CACHE_VERSION = 1


class Package(NamedTuple):
    __slots__ = ("manifest", "workspace_path", "project")


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


def is_workspace(path, require_rosrepo=True):
    if not os.path.isfile(os.path.join(path, ".catkin_workspace")): return False
    if not require_rosrepo: return True
    if not os.path.isfile(os.path.join(path, ".rosrepo", "config")): return False
    if not os.path.isdir(os.path.join(path, "src")): return False
    return True


def find_workspace(override=None, require_rosrepo=True):
    if override is not None:
        if is_workspace(override, require_rosrepo): return os.path.realpath(override)
        return None
    if "ROS_PACKAGE_PATH" in os.environ:
        candidates = os.environ["ROS_PACKAGE_PATH"].split(os.pathsep)
        for path in candidates:
            wsdir = os.path.normpath(os.path.join(path, os.pardir))
            if is_workspace(wsdir, require_rosrepo): return os.path.realpath(wsdir)
    wsdir = os.path.join(os.path.expanduser("~"), "ros")
    if is_workspace(wsdir, require_rosrepo): return os.path.realpath(wsdir)
    return None


def find_catkin_packages(srcdir, subdir=None, cache=None):
    from catkin_pkg.package import parse_package, InvalidPackage, PACKAGE_MANIFEST_FILENAME
    cached_paths = {}
    if cache is not None:
        cached_paths = cache.get_object("workspace_packages", WORKSPACE_PACKAGE_CACHE_VERSION, cached_paths)
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
            if not manifest.name in result: result[manifest.name] = []
            result[manifest.name].append(Package(manifest=manifest, workspace_path=path))
            discovered_paths[path] = {"t": cur_ts, "m": manifest}
        except InvalidPackage:
            pass
    if subdir is not None:
        for path, entry in iteritems(cached_paths):
            if not path_has_prefix(path, subdir):
                discovered_paths[path] = entry
    if cache is not None:
        cache.set_object("workspace_packages", WORKSPACE_PACKAGE_CACHE_VERSION, discovered_paths)
    return result


def get_workspace_state(wsdir, config=None, cache=None, offline_mode=False, verbose=True):
    if config is None: config = Config(wsdir)
    if cache is None: cache = Cache(wsdir)
    pkg_avail = find_catkin_packages(os.path.join(wsdir, "src"), cache=cache)
    gitlab_projects = []
    if "gitlab_servers" in config.data:
        for gitlab_cfg in config.data["gitlab_servers"]:
            if not "url" in gitlab_cfg: continue
            gitlab_projects += find_available_gitlab_projects(gitlab_cfg["url"], private_token=gitlab_cfg.get("private_token", None), cache=cache, cache_only=offline_mode, verbose=verbose)
    gitlab_avail = find_catkin_packages_from_gitlab_projects(gitlab_projects)
    cloned_projects = find_cloned_gitlab_projects(gitlab_projects, os.path.join(wsdir, "src"))
    for _, pkg in iteritems(pkg_avail):
        for prj in cloned_projects:
            if path_has_prefix(pkg.workspace_path, prj.workspace_path):
                pkg.project = prj
    return pkg_avail, gitlab_avail
