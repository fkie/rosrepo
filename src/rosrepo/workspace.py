"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import os
import sys
from catkin_pkg.package import parse_package, InvalidPackage, PACKAGE_MANIFEST_FILENAME
from .config import Config, ConfigError, Version
from .cache import Cache
from .gitlab import find_available_gitlab_projects, find_catkin_packages_from_gitlab_projects, find_cloned_gitlab_projects, acquire_gitlab_private_token
from .util import path_has_prefix, iteritems, NamedTuple, UserError
from .ui import msg, warning


WORKSPACE_PACKAGE_CACHE_VERSION = 1


class Package(NamedTuple):
    __slots__ = ("manifest", "workspace_path", "project")


def is_ros_root(path):
    if not os.path.isdir(os.path.join(path, "bin")):
        return False
    if not os.path.isdir(os.path.join(path, "etc")):
        return False
    if not os.path.isdir(os.path.join(path, "include")):
        return False
    if not os.path.isdir(os.path.join(path, "lib")):
        return False
    if not os.path.isdir(os.path.join(path, "share")):
        return False
    if not os.path.isfile(os.path.join(path, "setup.sh")):
        return False
    return True


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
        return -1, None
    if isfile(join(path, ".rosrepo", "config")):
        try:
            from . import __version__
            cfg = Config(path, True)
            this_version = Version(__version__)
            ws_version = Version(cfg["version"])
            if this_version < ws_version:
                return 4, cfg["version"]
            return 3, cfg["version"]
        except ConfigError:
            return -1, None
    if isdir(join(path, ".catkin_tools", "rosrepo")):
        return 2, "2.x"
    if isdir(join(path, ".catkin_tools", "profiles", "rosrepo")):
        return 2, "2.1.5+"
    if isdir(join(path, "repos")):
        if not isfile(join(path, "src", "CMakeLists.txt")):
            return -1, None
        if not isfile(join(path, "src", "toplevel.cmake")):
            return -1, None
        return 1, "1.x"
    return 0, None


def find_workspace(override=None):
    if override is not None:
        if is_workspace(override):
            return os.path.realpath(override)
        return None
    wsdir = os.getcwd()
    if is_workspace(wsdir):
        return os.path.realpath(wsdir)
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


def find_catkin_packages(srcdir, subdir=None, cache=None):
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
                manifest = parse_package(os.path.join(srcdir, path, PACKAGE_MANIFEST_FILENAME))
            if manifest.name not in result:
                result[manifest.name] = []
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


def get_workspace_location(override):
    wsdir = find_workspace(override)
    if wsdir is not None:
        wstype, wsversion = detect_workspace_type(wsdir)
        if wstype == 3:
            return wsdir
        msg("catkin workspace detected in @{cf}%s@|\n\n" % wsdir, fd=sys.stderr)
        if wstype == -1:
            msg(
                "I found a catkin workspace, but it seems to be broken.\n\n"
                "You can delete any corrupted settings and reinitialize the "
                "workspace for rosrepo with the command\n\n"
                "    @!rosrepo init --reset %(path)s@|\n\n"
                % {"path": wsdir}, fd=sys.stderr
            )
        if wstype == 0:
            msg(
                "I found a catkin workspace, but it is not configured with rosrepo.\n\n"
                "If you wish to use rosrepo with this workspace, run the command\n\n"
                "    @!rosrepo init %(path)s@|\n\n"
                % {"path": wsdir}, fd=sys.stderr
            )
        if wstype == 4:
            msg(
                "This catkin workspace has been configured by a newer version of rosrepo.\n\n"
                "Please upgrade rosrepo to at least version @{cf}%(new_version)s@|\n\n"
                % {"new_version": wsversion}, fd=sys.stderr
            )
        if wstype == 1 or wstype == 2:
            from . import __version__
            msg(
                "This catkin workspace has been configured by rosrepo @{cf}%(old_version)s@|, "
                "but you are currently running version @{cf}%(new_version)s@|\n\n"
                "If you wish to use the new version of rosrepo, you need to reinitialize the "
                "workspace with the command\n\n"
                "    @!rosrepo init %(path)s@|\n\n"
                % {"old_version": wsversion, "new_version": __version__, "path": wsdir}, fd=sys.stderr
            )
        if override is None:
            msg(
                "If this is not the workspace location you were looking for, try "
                "the @{cf}--workspace@| option to override the automatic detection.\n\n",
                fd=sys.stderr
            )
    else:
        if override is not None:
            msg(
                "There is no catkin workspace in %(path)s\n\n"
                "You can create a new workspace there by running\n\n"
                "    rosrepo init %(path)s\n\n"
                "If you are really sure that there is a workspace there already, "
                "it is possible that the marker file has been deleted by accident. "
                "In that case, the above command will restore your workspace.\n\n"
                % {"path": override}, fd=sys.stderr
            )
        else:
            msg(
                "I cannot find any catkin workspace.\n\n"
                "Please make sure that you have sourced the @{cf}setup.bash@| file of "
                "your workspace or use the @{cf}--workspace@| option to override the "
                "automatic detection. If you have never created a workspace yet, "
                "you can initialize one in your home directory with\n\n"
                "    @!rosrepo init %s/ros@|\n\n"
                % os.path.expanduser("~"), fd=sys.stderr
            )
    raise UserError("valid workspace location required")


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
        msg("Migrating workspace format @{cf}%s@|...\n" % wsversion)
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
                warning("cannot migrate metadata: %s\n" % str(e))
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
            sys.stderr.write("Error: %s" % str(e))
            sys.exit(1)
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
                with open(infofile, "r") as f:
                    packages = pickle.load(f)
                os.unlink(infofile)
            except Exception as e:
                warning("cannot migrate metadata: %s\n" % str(e))
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


def get_workspace_state(wsdir, config=None, cache=None, offline_mode=False, verbose=True):
    if config is None:
        config = Config(wsdir)
    if cache is None:
        cache = Cache(wsdir)
    ws_avail = find_catkin_packages(os.path.join(wsdir, "src"), cache=cache)
    gitlab_projects = []
    if "gitlab_servers" in config:
        for gitlab_cfg in config["gitlab_servers"]:
            label = gitlab_cfg.get("label", None)
            url = gitlab_cfg.get("url", None)
            private_token = gitlab_cfg.get("private_token", None)
            if url is not None and private_token is None:
                private_token = acquire_gitlab_private_token("%s [%s]" % (label, url))
            gitlab_projects += find_available_gitlab_projects(label, url, private_token=private_token, cache=cache, cache_only=offline_mode, verbose=verbose)
    cloned_projects = find_cloned_gitlab_projects(gitlab_projects, os.path.join(wsdir, "src"))
    gitlab_avail = find_catkin_packages_from_gitlab_projects(gitlab_projects)
    for _, pkg_list in iteritems(ws_avail):
        for pkg in pkg_list:
            for prj in cloned_projects:
                if path_has_prefix(pkg.workspace_path, prj.workspace_path):
                    pkg.project = prj
    return ws_avail, gitlab_avail
