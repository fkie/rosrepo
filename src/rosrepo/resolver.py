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
from .util import is_deprecated_package, call_process, PIPE
import re


class Rosdep(object):

    def __init__(self):
        self.cached_installers = {}
        try:
            from rosdep2.lookup import RosdepLookup
            from rosdep2.rospkg_loader import DEFAULT_VIEW_KEY
            from rosdep2.sources_list import SourcesListLoader
            from rosdep2 import get_default_installer, create_default_installer_context
            sources_loader = SourcesListLoader.create_default()
            lookup = RosdepLookup.create_from_rospkg(sources_loader=sources_loader)
            self.view = lookup.get_rosdep_view(DEFAULT_VIEW_KEY)
            self.installer_ctx = create_default_installer_context()
            _, self.installer_keys, self.default_key, \
                self.os_name, self.os_version = get_default_installer(self.installer_ctx)
        except Exception as e:
            error("failed to initialize rosdep: %s" % str(e))
            self.view = None

    def __contains__(self, name):
        return self.view is not None and name in self.view.keys()

    def ok(self):
        return self.view is not None

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


def find_dependees(packages, ws_state, auto_resolve=False, ignore_missing=False):
    def try_resolve(queue, depends=None, system_depends=None, conflicts=None, score=None):
        if depends is None:
            depends = {}
        if system_depends is None:
            system_depends = set()
        if conflicts is None:
            conflicts = {}
        if score is None:
            score = 0
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
                if name in ws_state.ws_packages:
                    # If the package is in the workspace, we assume it's unique and take the first in the list
                    depends[name] = ws_state.ws_packages[name][0]
                    manifest = ws_state.ws_packages[name][0].manifest
                    if is_deprecated_package(manifest):
                        score -= 5  # Penalty for being deprecated
                    queue += [(root_depender, name, p.name) for p in manifest.buildtool_depends + manifest.build_depends + manifest.run_depends + manifest.test_depends]
                elif name in ws_state.remote_packages:
                    # Package is not in workspace, so we may have multiple sources
                    # to download it from. However, since each Gitlab project
                    # may contain multiple packages, we must verify that no other
                    # package conflicts with one that's already in the workspace
                    best_depends = depends
                    best_sysdep = system_depends
                    best_score = None  # no solution yet
                    candidates = []
                    resolver_msgs.append("is not in workspace (or disabled with @{cf}CATKIN_IGNORE@|)")
                    for pkg in ws_state.remote_packages[name]:
                        # Is the package project in the workspace already?
                        if pkg.project in ws_state.ws_projects:
                            resolver_msgs.append("not found in project @{cf}%s@| which is cloned in @{cf}%s/@| (maybe you need to @{cf}git pull@| the latest version)" % (escape(pkg.project.name), escape(pkg.project.workspace_path)))
                            continue  # Fail
                        # Check other packages in the same Gitlab project
                        for other in pkg.project.packages:
                            # Is the other package in the workspace already?
                            if other.manifest.name in ws_state.ws_packages:
                                resolver_msgs.append("cannot be cloned from @{cf}%s@| because package @{cf}%s@| is in the workspace already" % (escape(pkg.project.name), escape(other.manifest.name)))
                                break  # Fail
                            # If not, check if we already decided to download
                            # the package from another project
                            if other.manifest.name in depends:
                                # Is it the same project?
                                if other.project != pkg.project:
                                    resolver_msgs.append("cannot be cloned from @{cf}%s@| because it contains package @{cf}%s@| which will be cloned from @{cf}%s@|" % (escape(pkg.project.name), escape(other.manifest.name), escape(other.project.name)))
                                    break  # Fail
                        else:
                            # The chosen package does not create any conflicts
                            candidates.append(pkg)
                    if len(candidates) > 1 and not auto_resolve:
                        # If desired, let the user pick one
                        result = pick_dependency_resolution(name, candidates)
                        if result is not None:
                            candidates = [result]
                    local_conflicts = {}
                    for pkg in candidates:
                        depends[name] = pkg
                        manifest = pkg.manifest
                        candidate_queue = [(root_depender, name, p.name) for p in manifest.buildtool_depends + manifest.build_depends + manifest.run_depends + manifest.test_depends]
                        new_depends, new_sysdep, new_conflicts, new_score = try_resolve(candidate_queue, depends.copy(), system_depends.copy())
                        conflicts.update(new_conflicts)
                        local_conflicts.update(new_conflicts)
                        if not new_conflicts:
                            # We can build a consistent workspace with that
                            # If we have multiple choices, we pick the one with
                            # the smallest number of soft-conflicts
                            if is_deprecated_package(manifest):
                                new_score -= 250  # Huge penalty for being deprecated
                            if best_score is None or new_score > best_score:
                                best_score = new_score
                                best_depends = new_depends
                                best_sysdep = new_sysdep
                        # Try next available package
                        del depends[name]
                    if best_score is not None:
                        depends.update(best_depends)
                        system_depends |= best_sysdep
                        score -= 10  # Small penalty for required download
                    elif name in rosdep:
                        system_depends.add(name)
                        best_score = -1  # small penalty for relying on system package
                    else:
                        resolver_msgs.append("is not installable from a configured Gitlab server due to problems with " + ", ".join("@{cf}%s@|" % s for s in sorted(local_conflicts.keys())))
                        resolver_msgs.append("is not in rosdep database (or you have to run @{cf}rosdep update@|)")
                        conflicts[name] = resolver_msgs
                elif name in rosdep and depender is None:
                    resolver_msgs.append("is not in workspace (or disabled with @{cf}CATKIN_IGNORE@|)")
                    resolver_msgs.append("is not available from a configured Gitlab server")
                    conflicts[name] = resolver_msgs
                elif name in rosdep:
                    system_depends.add(name)
                else:
                    resolver_msgs.append("is not in workspace (or disabled with @{cf}CATKIN_IGNORE@|)")
                    resolver_msgs.append("is not available from a configured Gitlab server")
                    resolver_msgs.append("is not in rosdep database (or you have to run @{cf}rosdep update@|)")
                    if not ignore_missing:
                        conflicts[name] = resolver_msgs
        score -= 100 * len(system_depends - apt_installed(system_depends))  # Large penalty for uninstalled system dependency
        return depends, system_depends, conflicts, score
    rosdep = get_rosdep()
    queue = [(None, None, name) for name in packages]
    depends, system_depends, conflicts, _ = try_resolve(queue)
    return depends, system_depends, conflicts


def apt_installed(packages):
    valid_packages = [p for p in packages if re.match(r"^[A-Za-z0-9+._-]+$", p)]
    result = set()
    try:
        _, stdout, _ = call_process(["dpkg-query", "-f", "${Package}|${Status}\\n", "-W"] + valid_packages, stdout=PIPE, stderr=PIPE)
        for line in stdout.split("\n"):
            if "ok installed" in line:
                result.add(line.split("|", 1)[0])
    except OSError:
        error("cannot invoke dpkg-query to find installed system packages\n")
    return result


def resolve_system_depends(system_depends, missing_only=False):
    resolved = set()
    rosdep = get_rosdep()
    if not rosdep.ok():
        error("cannot resolve system dependencies without rosdep\n")
        return resolved
    for dep in system_depends:
        installer, resolved_deps = rosdep.resolve(dep)
        for d in resolved_deps:
            if installer == "apt":
                resolved.add(d)
            else:
                warning("unsupported installer '%s': ignoring package '%s'\n" % (installer, dep))
    if missing_only:
        resolved -= apt_installed(resolved)
    return resolved
