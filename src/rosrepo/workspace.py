# coding=utf-8
#
# ROSREPO
# Manage ROS workspaces with multiple Gitlab repositories
#
# Author: Timo Röhling
#
# Copyright 2016 Fraunhofer FKIE
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#
import os
from catkin_pkg.package import parse_package, InvalidPackage, PACKAGE_MANIFEST_FILENAME
from .config import Config, ConfigError, Version
from .cache import Cache
from .gitlab import get_gitlab_projects, find_catkin_packages_from_gitlab_projects, find_cloned_gitlab_projects
from .util import path_has_prefix, iteritems, NamedTuple, is_deprecated_package
from .ui import msg, warning, fatal, escape
try:
    from scandir import walk as os_walk
except ImportError:
    from os import walk as os_walk


WORKSPACE_PACKAGE_CACHE_VERSION = 1


class Package(NamedTuple):
    __slots__ = ("manifest", "workspace_path", "project")


class WorkspaceState(NamedTuple):
    __slots__ = ("ws_packages", "remote_packages", "ros_root_packages", "ws_projects", "remote_projects", "other_git")


def is_ros_root(path):
    return os.path.isdir(os.path.join(path, "bin")) \
        and os.path.isdir(os.path.join(path, "etc")) \
        and os.path.isdir(os.path.join(path, "lib")) \
        and os.path.isdir(os.path.join(path, "share")) \
        and os.path.isfile(os.path.join(path, "env.sh")) \
        and os.path.isfile(os.path.join(path, ".catkin"))


def find_ros_root(override=None):
    if override is not None:
        if is_ros_root(override):
            return os.path.realpath(override)
        return None
    if "ROS_ROOT" in os.environ:
        rosrootdir = os.environ["ROS_ROOT"]
        if os.path.isdir(rosrootdir):
            rosdir = os.path.normpath(os.path.join(rosrootdir, os.pardir, os.pardir))
            if is_ros_root(rosdir):
                return os.path.realpath(rosdir)
    if "ROS_PACKAGE_PATH" in os.environ:
        candidates = os.environ["ROS_PACKAGE_PATH"].split(os.pathsep)
        candidates.reverse()
        for path in candidates:
            rosdir = os.path.normpath(os.path.join(path, os.pardir))
            if is_ros_root(rosdir):
                return os.path.realpath(rosdir)
    if os.path.islink("/opt/ros/current"):
        rosdir = os.path.join("/opt/ros", os.readlink("/opt/ros/current"))
        if is_ros_root(rosdir):
            return os.path.realpath(rosdir)
    return None


def is_workspace(path):
    return os.path.isfile(os.path.join(path, ".catkin_workspace"))


def detect_workspace_type(path):
    if not is_workspace(path):
        return -2, None
    isdir = os.path.isdir
    isfile = os.path.isfile
    join = os.path.join
    if not isdir(join(path, "src")):
        return -1, "there is no @{cf}src@| folder"
    if isfile(join(path, ".rosrepo", "config")):
        try:
            from . import __version__
            cfg = Config(path, read_only=True)
            this_version = Version(__version__)
            ws_version = Version(cfg["version"])
            if this_version.version[:2] < ws_version.version[:2]:
                return 4, cfg["version"]
            return 3, cfg["version"]
        except ConfigError as e:
            return -1, "the configuration is broken (%s)" % escape(str(e))
    if isdir(join(path, ".catkin_tools", "rosrepo")):
        return 2, "2.x"
    if isdir(join(path, ".catkin_tools", "profiles", "rosrepo")):
        return 2, "2.1.5+"
    if isdir(join(path, "repos")):
        if not isfile(join(path, "src", "CMakeLists.txt")):
            return -1, "it looks like a rosrepo 1.x workspace without @{cf}src/CMakeLists.txt@|"
        if not isfile(join(path, "src", "toplevel.cmake")):
            return -1, "it looks like a rosrepo 1.x workspace without @{cf}src/toplevel.cmake@|"
        return 1, "1.x"
    return 0, None


def find_workspace(override=None):
    if override is not None:
        if is_workspace(override):
            return os.path.realpath(override)
        return None
    wsdir = os.getcwd()
    while wsdir:
        if is_workspace(wsdir):
            return os.path.realpath(wsdir)
        if os.path.ismount(wsdir):
            break
        wsdir, tail = os.path.split(wsdir)
        if not tail:
            break
    if "ROS_PACKAGE_PATH" in os.environ:
        candidates = os.environ["ROS_PACKAGE_PATH"].split(os.pathsep)
        for path in candidates:
            wsdir = os.path.normpath(os.path.join(path, os.pardir))
            if is_workspace(wsdir):
                return os.path.realpath(wsdir)
    wsdir = os.path.join(os.path.expanduser("~"), "ros")
    if is_workspace(wsdir):
        return os.path.realpath(wsdir)
    return None


def find_catkin_packages(srcdir, subdir=None, cache=None, cache_id="workspace_packages"):
    cached_paths = {}
    cache_update = False
    if cache is not None:
        cached_paths = cache.get_object(cache_id, WORKSPACE_PACKAGE_CACHE_VERSION, cached_paths)
    package_paths = []
    base_path = srcdir if subdir is None else os.path.join(srcdir, subdir)
    for curdir, subdirs, files in os_walk(base_path, followlinks=True):
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
                cache_update = True
                manifest = parse_package(os.path.join(srcdir, path, PACKAGE_MANIFEST_FILENAME))
            if manifest.name not in result:
                result[manifest.name] = []
            result[manifest.name].append(Package(manifest=manifest, workspace_path=path))
            discovered_paths[path] = {"t": cur_ts, "m": manifest}
        except InvalidPackage as e:
            msg(str(e) + "\n")
            fatal("invalid package in workspace")
    if subdir is not None:
        for path, entry in iteritems(cached_paths):
            if not path_has_prefix(path, subdir):
                discovered_paths[path] = entry
    if cache is not None:
        if cache_update or len(cached_paths) != len(discovered_paths):
            cache.set_object(cache_id, WORKSPACE_PACKAGE_CACHE_VERSION, discovered_paths)
    return result


def get_workspace_location(override):
    from . import __version__
    wsdir = find_workspace(override)
    if wsdir is not None:
        wstype, wsversion = detect_workspace_type(wsdir)
        if wstype == 3:
            return wsdir
        msg("catkin workspace detected in @{cf}%s@|\n\n" % escape(wsdir))
        if wstype == -1:
            msg(
                "I found a catkin workspace, but %(error_msg)s\n\n"
                "You can delete any corrupted settings and reinitialize the "
                "workspace for rosrepo with the command\n\n"
                "    @!rosrepo init --reset %(path)s@|\n\n"
                % {"path": escape(wsdir), "error_msg": wsversion}
            )
        if wstype == 0:
            msg(
                "I found a catkin workspace, but it is not configured with rosrepo.\n\n"
                "If you wish to use rosrepo with this workspace, run the command\n\n"
                "    @!rosrepo init %(path)s@|\n\n"
                % {"path": escape(wsdir)}
            )
        if wstype == 4:
            msg(
                "This catkin workspace has been configured by a newer version of rosrepo, "
                "please upgrade to version @{cf}%(new_version)s@| or newer.\n\n"
                "If you want to revert the workspace back to this version (@{cf}%(old_version)s@|), "
                "you can reset all settings with\n\n"
                "    @!rosrepo init --reset %(path)s@|\n\n"
                "@!@{yf}WARNING@|: Please make a backup before doing this!\n\n"
                % {"path": escape(wsdir), "new_version": escape(wsversion), "old_version": __version__}
            )
        if wstype == 1 or wstype == 2:
            msg(
                "This catkin workspace has been configured by rosrepo @{cf}%(old_version)s@|, "
                "but you are currently running version @{cf}%(new_version)s@|\n\n"
                "If you wish to use the new version of rosrepo, you need to reinitialize the "
                "workspace with the command\n\n"
                "    @!rosrepo init %(path)s@|\n\n"
                % {"old_version": escape(wsversion), "new_version": __version__, "path": escape(wsdir)}
            )
        if override is None:
            msg(
                "If this is not the workspace location you were looking for, try "
                "the @{cf}--workspace@| option to override the automatic detection.\n\n"
            )
    else:
        if override is not None:
            msg(
                "There is no catkin workspace in %(path)s\n\n"
                "You can create a new workspace there by running\n\n"
                "    @!rosrepo init %(path)s@|\n\n"
                "If you are really sure that there is a workspace there already, "
                "it is possible that the marker file has been deleted by accident. "
                "In that case, the above command will restore your workspace.\n\n"
                % {"path": escape(override)}
            )
        else:
            msg(
                "I cannot find any catkin workspace.\n\n"
                "Please make sure that you have sourced the @{cf}setup.bash@| file of "
                "your workspace or use the @{cf}--workspace@| option to override the "
                "automatic detection. If you have never created a workspace yet, "
                "you can initialize one in your home directory with\n\n"
                "    @!rosrepo init %s/ros@|\n\n"
                % escape(os.path.expanduser("~"))
            )
    fatal("valid workspace location required\n")


def migrate_workspace(wsdir):
    import shutil
    import pickle
    wstype, wsversion = detect_workspace_type(wsdir)
    srcdir = os.path.join(wsdir, "src")
    if wstype == 1 or wstype == 2:
        builddir = os.path.join(wsdir, "build")
        develdir = os.path.join(wsdir, "devel")
        installdir = os.path.join(wsdir, "install")
        if os.path.isdir(builddir):
            shutil.rmtree(builddir)
        if os.path.isdir(develdir):
            shutil.rmtree(develdir)
        if os.path.isdir(installdir):
            shutil.rmtree(installdir)
        msg("Migrating workspace format @{cf}%s@|...\n" % escape(wsversion))
    if wstype == 1:
        repodir = os.path.normpath(os.path.join(wsdir, "repos"))
        metainfo = os.path.join(repodir, ".metainfo")
        toplevel_cmake = os.path.join(srcdir, "toplevel.cmake")
        cmakelists_txt = os.path.join(srcdir, "CMakeLists.txt")
        if os.path.exists(toplevel_cmake):
            os.unlink(toplevel_cmake)
        if os.path.exists(cmakelists_txt):
            os.unlink(cmakelists_txt)
        old_meta = {}
        if os.path.isfile(metainfo):
            import yaml
            try:
                with open(metainfo, "r") as f:
                    old_meta = yaml.safe_load(f)
            except Exception as e:
                warning("cannot migrate metadata: %s\n" % escape(str(e)))
        cfg = Config(wsdir)
        cfg["pinned_build"] = []
        cfg["default_build"] = []
        try:
            srcfiles = os.listdir(srcdir)
            for entry in srcfiles:
                path = os.path.join(srcdir, entry)
                if os.path.isdir(path):
                    if os.path.islink(path):
                        realpath = os.path.normpath(os.path.join(srcdir, os.readlink(path)))
                        if realpath.startswith(repodir):
                            if entry in old_meta:
                                if old_meta[entry]["pin"]:
                                    cfg["pinned_build"].append(entry)
                                elif not old_meta[entry]["auto"]:
                                    cfg["default_build"].append(entry)
                            os.unlink(path)
            if os.path.isfile(metainfo):
                os.unlink(metainfo)
            repofiles = os.listdir(repodir)
            for entry in repofiles:
                path = os.path.join(repodir, entry)
                shutil.move(path, srcdir)
            os.rmdir(repodir)
        except shutil.Error as e:
            fatal(escape(str(e)) + "\n")
        cfg.write()
    if wstype == 2:
        cfg = Config(wsdir)
        cfg["pinned_build"] = []
        cfg["default_build"] = []
        infodir = os.path.join(wsdir, ".rosrepo")
        infofile = os.path.join(infodir, "info")
        packages = {}
        if os.path.isfile(infofile):
            try:
                with open(infofile, "rb") as f:
                    packages = pickle.load(f)
                os.unlink(infofile)
            except Exception as e:
                warning("cannot migrate metadata: %s\n" % escape(str(e)))
        for name, info in iteritems(packages):
            if info.pinned:
                cfg["pinned_build"].append(name)
            elif info.selected:
                cfg["default_build"].append(name)
        cfg.write()
        try:
            os.unlink(os.path.join(wsdir, "setup.bash"))
        except OSError:
            pass
        shutil.rmtree(os.path.join(wsdir, ".catkin_tools", "rosrepo"), ignore_errors=True)
        shutil.rmtree(os.path.join(wsdir, ".catkin_tools", "profiles", "rosrepo"), ignore_errors=True)
        shutil.rmtree(os.path.join(wsdir, "build"), ignore_errors=True)
        shutil.rmtree(os.path.join(wsdir, "devel"), ignore_errors=True)
        shutil.rmtree(os.path.join(wsdir, "install"), ignore_errors=True)
        shutil.rmtree(os.path.join(wsdir, "logs"), ignore_errors=True)


WSFL_WS_PACKAGES = 1
WSFL_REMOTE_PACKAGES = 2
WSFL_WS_PROJECTS = 4
WSFL_REMOTE_PROJECTS = 8
WSFL_ROS_ROOT_PACKAGES = 16
WSFL_ALL = 31


def get_workspace_state(wsdir, config=None, cache=None, offline_mode=False, verbose=True, ws_state=None, flags=WSFL_ALL):
    if ws_state is None:
        ws_state = WorkspaceState()
    if config is None:
        config = Config(wsdir)
    if cache is None:
        cache = Cache(wsdir)
    link_projects = False
    if flags & WSFL_WS_PACKAGES:
        link_projects = True
        ws_state.ws_packages = find_catkin_packages(os.path.join(wsdir, "src"), cache=cache)
        for name, pkg_list in iteritems(ws_state.ws_packages):
            if len(pkg_list) > 1:
                msg("You have multiple versions of the package @{cf}%s@| in your workspace:\n\n" % escape(name))
                for pkg in pkg_list:
                    msg("     - @{cf}%s@|\n" % escape(os.path.join(wsdir, "src", pkg.workspace_path)))
                    if is_deprecated_package(pkg.manifest):
                        msg("       @{rf}(deprecated)@|\n")
                msg(
                    "\n"
                    "Please remove all but one of the versions or place a @{cf}CATKIN_IGNORE@| file "
                    "in their path to disable them.\n\n"
                )
                fatal("workspace has conflicting packages\n")
    if flags & WSFL_ROS_ROOT_PACKAGES:
        ros_rootdir = find_ros_root(config.get("ros_root", None))
        if ros_rootdir is not None:
            ws_state.ros_root_packages = find_catkin_packages(ros_rootdir, cache=cache, cache_id="ros_root_packages")
        else:
            ws_state.ros_root_packages = {}
    if flags & WSFL_REMOTE_PROJECTS:
        ws_state.remote_projects = get_gitlab_projects(wsdir, config, cache=cache, offline_mode=offline_mode, verbose=verbose)
    if flags & WSFL_WS_PROJECTS and ws_state.remote_projects is not None:
        link_projects = True
        ws_state.ws_projects, ws_state.other_git = find_cloned_gitlab_projects(ws_state.remote_projects, os.path.join(wsdir, "src"))
    if flags & WSFL_REMOTE_PACKAGES and ws_state.remote_projects is not None:
        ws_state.remote_packages = find_catkin_packages_from_gitlab_projects(ws_state.remote_projects)
    if link_projects and ws_state.ws_packages is not None and ws_state.ws_projects is not None:
        for _, pkg_list in iteritems(ws_state.ws_packages):
            for pkg in pkg_list:
                for prj in ws_state.ws_projects:
                    if path_has_prefix(pkg.workspace_path, prj.workspace_path):
                        pkg.project = prj
                        break
    return ws_state


def resolve_this(wsdir, ws_state):
    result = set()
    curdir = os.path.relpath(os.getcwd(), os.path.join(wsdir, "src"))
    for name, pkg_list in iteritems(ws_state.ws_packages):
        for pkg in pkg_list:
            if path_has_prefix(curdir, pkg.workspace_path):
                result.add(name)
    if not result:
        fatal("no package in this folder")
    return result
