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
from .ui import pick_dependency_resolution, warning, error, escape
from .util import is_deprecated_package, call_process, PIPE, iteritems
from distutils.version import LooseVersion as ManifestVersion
import platform
import gc


class DummyRospkg(object):
    def list(self):
        return []


class Rosdep(object):

    def __init__(self):
        self.cached_installers = {}
        gc.disable()
        try:
            import sys
            from . import dummy_pkg_resources
            sys.modules["pkg_resources"] = dummy_pkg_resources
            from rosdep2.lookup import RosdepLookup
            from rosdep2.rospkg_loader import DEFAULT_VIEW_KEY
            from rosdep2 import get_default_installer, create_default_installer_context
            self.lookup = RosdepLookup.create_from_rospkg(rospack=DummyRospkg(), rosstack=DummyRospkg())
            self.view = self.lookup.get_rosdep_view(DEFAULT_VIEW_KEY)
            self.installer_ctx = create_default_installer_context()
            _, self.installer_keys, self.default_key, \
                self.os_name, self.os_version = get_default_installer(self.installer_ctx)
        except Exception as e:
            error("failed to initialize rosdep: %s" % str(e))
            self.view = None
        gc.enable()

    def __contains__(self, name):
        return self.view is not None and name in self.view.keys()

    def ok(self):
        return self.view is not None

    def reverse_depends(self, dep):
        result = self.lookup.get_resources_that_need(dep)
        return set(result)

    def depends(self, dep):
        result = self.lookup.get_rosdeps(dep, implicit=False)
        return set(result)

    def resolve(self, dep):
        d = self.view.lookup(dep)
        rule_installer, rule = \
            d.get_rule_for_platform(self.os_name, self.os_version, self.installer_keys, self.default_key)
        if rule_installer in self.cached_installers:
            installer = self.cached_installers[rule_installer]
        else:
            installer = self.installer_ctx.get_installer(rule_installer)
            self.cached_installers[rule_installer] = installer
        resolved = installer.resolve(rule)
        return rule_installer, resolved


_rosdep_instance = None


def get_rosdep():
    global _rosdep_instance
    if _rosdep_instance is None:
        _rosdep_instance = Rosdep()
    return _rosdep_instance


def find_dependers(packages, ws_state):
    depends = set()
    system_depends = set()
    query_set = set(packages)
    # rosdep = get_rosdep()
    # for pkg in packages:
    #     system_depends |= rosdep.reverse_depends(pkg)
    for name, pkg_list in iteritems(ws_state.ws_packages):
        for pkg in pkg_list:
            manifest = pkg.manifest
            pkg_depends = set([p.name for p in manifest.buildtool_depends + manifest.build_depends + manifest.run_depends + manifest.test_depends])
            if query_set & pkg_depends:
                depends.add(name)
    for name, pkg_list in iteritems(ws_state.remote_packages):
        for pkg in pkg_list:
            manifest = pkg.manifest
            pkg_depends = set([p.name for p in manifest.buildtool_depends + manifest.build_depends + manifest.run_depends + manifest.test_depends])
            if query_set & pkg_depends:
                depends.add(name)
    system_depends -= depends
    return depends, system_depends


def find_dependees(packages, ws_state, auto_resolve=False, ignore_missing=False, recursive=True, force_workspace=True):
    P_REMOTE = 1
    P_WS = 2
    P_ROS_ROOT = 3

    def find_package_candidates(name, ws_state, resolver_msgs):
        # Returns a list of packages which satisfy the given dependency
        if name in ws_state.ws_packages:
            # If the package is in the workspace, it will be used unconditionally
            return [(ws_state.ws_packages[name][0], P_WS)]
        result = []
        if name in ws_state.ros_root_packages:
            result.append((ws_state.ros_root_packages[name][0], P_ROS_ROOT))
        if name in ws_state.remote_packages:
            remotes = ws_state.remote_packages[name]
            if len(remotes) > 1 and not auto_resolve:
                # If desired, let the user pick one
                desired = pick_dependency_resolution(name, remotes)
                if desired is not None:
                    remotes = [desired]
            for pkg in remotes:
                result.append((pkg, P_REMOTE))
        return sorted(result, key=lambda x: (ManifestVersion(x[0].manifest.version), x[1]), reverse=True)

    def try_resolve(queue, depends=None, system_depends=None, conflicts=None):
        if depends is None:
            depends = {}
        if system_depends is None:
            system_depends = set()
        if conflicts is None:
            conflicts = {}
        while len(queue) > 0:
            root_depender, depender, name = queue.pop()
            if name not in depends and name not in conflicts and name not in system_depends:
                resolver_msgs = []
                if root_depender is not None and root_depender != depender:
                    resolver_msgs.append("is needed to resolve dependencies of package @{cf}%s@|" % escape(root_depender))
                if depender is not None:
                    resolver_msgs.append("is dependee of package @{cf}%s@|" % escape(depender))
                if root_depender is None:
                    root_depender = name
                candidates = find_package_candidates(name, ws_state, resolver_msgs)
                for pkg, source in candidates:
                    if source not in [P_WS, P_REMOTE] and depender is None and force_workspace:
                        continue  # Ignore other sources if primary depender should be a workspace package
                    if source == P_REMOTE:
                        if pkg.project in ws_state.ws_projects:
                            resolver_msgs.append("missing from @{cf}%s/@| (maybe you need to @{cf}git pull@|?)" % escape(pkg.project.workspace_path))
                            continue  # Fail, try next
                        # Check all other packages in the same project for conflicts
                        ok = True
                        for other in pkg.project.packages:
                            # Is the other package in the workspace already?
                            if other.manifest.name in ws_state.ws_packages:
                                resolver_msgs.append("cannot be cloned from @{cf}%s@| because package @{cf}%s@| is in the workspace already" % (escape(pkg.project.name), escape(other.manifest.name)))
                                ok = False
                                break  # Fail
                            # If not, check if we already decided to download
                            # the package from another project
                            if other.manifest.name in depends:
                                # Is it the same project?
                                if other.project != pkg.project:
                                    resolver_msgs.append("cannot be cloned from @{cf}%s@| because it contains package @{cf}%s@| which will be cloned from @{cf}%s@|" % (escape(pkg.project.name), escape(other.manifest.name), escape(other.project.name)))
                                    ok = False
                                    break  # Fail
                        if not ok:
                            continue  # Fail, try next
                    # If we got to this point, the package can be used to resolve the dependency
                    if source in [P_WS, P_REMOTE]:
                        depends[name] = pkg
                        if recursive or depender is None:
                            recursive_depends = pkg.manifest.buildtool_depends + pkg.manifest.build_depends + pkg.manifest.run_depends + pkg.manifest.test_depends
                            queue += [(root_depender, name, p.name) for p in recursive_depends]
                    else:
                        system_depends.add(name)
                    break  # Success, do not check more candidates
                else:
                    if not candidates:
                        resolver_msgs.append("no such package available")
                    else:
                        resolver_msgs.append("not in workspace and cannot be cloned from Gitlab")
                    # No candidate matched, but maybe we got lucky and it's a known system dependency
                    # However, if it is requested explicitly, we won't use system dependencies
                    if depender is not None and name in get_rosdep():
                        system_depends.add(name)
                    else:
                        # We cannot resolve this
                        # If the package is unknown, i.e. does not have any installation candidates,
                        # we may choose to ignore it, if so instructed
                        if candidates or not ignore_missing:
                            conflicts[name] = resolver_msgs
        return depends, system_depends, conflicts
    queue = [(None, None, name) for name in packages]
    depends, system_depends, conflicts = try_resolve(queue)
    return depends, system_depends, conflicts


class SystemPackageManager(object):

    def __init__(self):
        self._system = platform.system()
        self._installed_packages = None
        if self._system == "Linux":
            self._installer = "apt"
            self._installer_cmd = "sudo apt install"
        elif self._system == "Darwin":
            self._installer = "homebrew"
            self._installer_cmd = "brew install"
        else:
            self._installer = None
            self._installer_cmd = None

    @property
    def installer(self):
        return self._installer

    @property
    def installer_cmd(self):
        return self._installer_cmd

    @property
    def installed_packages(self):
        if self._installed_packages is None:
            self._populate_installed_packages()
        return self._installed_packages

    def _populate_installed_packages(self):
        self._installed_packages = set()
        if self._system == "Linux":
            try:
                _, stdout, _ = call_process(["dpkg-query", "-f", "${Package}|${Status}\\n", "-W"], stdout=PIPE, stderr=PIPE)
                for line in stdout.split("\n"):
                    if "ok installed" in line:
                        pkg = line.split("|", 1)[0]
                        self._installed_packages.add(pkg)
            except OSError:
                error("cannot invoke dpkg-query to find installed system packages")
        elif self._system == "Darwin":
            try:
                _, stdout, _ = call_process(["brew", "list"], stdout=PIPE, stderr=PIPE)
                for pkg in stdout.split("\n"):
                    if pkg:
                        self._installed_packages.add(pkg)
            except OSError:
                error("cannot invoke brew to find installed system packages")


_system_package_manager = None


def get_system_package_manager():
    global _system_package_manager
    if _system_package_manager is None:
        _system_package_manager = SystemPackageManager()
    return _system_package_manager


_resolve_warn_once = False


def resolve_system_depends(ws_state, system_depends, missing_only=False):
    global _resolve_warn_once
    resolved = set()
    if get_system_package_manager().installer is None:
        if not _resolve_warn_once:
            error("cannot resolve system dependencies for this system\n")
            _resolve_warn_once = True
        return set()
    for dep in system_depends:
        if dep not in ws_state.ros_root_packages:  # This deals with ROS source installs
            rosdep = get_rosdep()
            if not rosdep.ok():
                if not _resolve_warn_once:
                    error("cannot resolve system dependencies without rosdep\n")
                    _resolve_warn_once = True
                return set()
            try:
                from rosdep2.lookup import ResolutionError
            except ImportError:
                class ResolutionError(Exception):
                    pass
            try:
                installer, resolved_deps = rosdep.resolve(dep)
                for d in resolved_deps:
                    if installer == get_system_package_manager().installer:
                        if hasattr(d, "package"):
                            resolved.add(d.package)
                        else:
                            resolved.add(d)
                    else:
                        warning("unsupported installer '%s': ignoring package '%s'\n" % (installer, dep))
            except ResolutionError:
                warning("cannot resolve system package: ignoring package '%s'\n" % dep)
    if missing_only:
        resolved -= get_system_package_manager().installed_packages
    return resolved
