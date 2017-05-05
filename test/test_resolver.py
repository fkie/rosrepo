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
import unittest

import sys
sys.stderr = sys.stdout
import re
import os

try:
    from mock import patch
except ImportError:
    from unittest.mock import patch

import rosrepo.resolver as resolver
import rosrepo.workspace as ws
import rosrepo.gitlab as gl
import test.helper as helper
from catkin_pkg.package import Package as Manifest, Dependency


def fake_ws_package(project, name, version="0.0.0", depends=[]):
    m = Manifest(name, name=name, version=version, depends=[Dependency(d) for d in depends])
    return ws.Package(manifest=m, workspace_path=name, project=project)


def fake_gitlab_project(id, name, url):
    return gl.GitlabProject(name=name, website=url, packages=[], workspace_path=name, server="fake", id=id)


def fake_gitlab_package(project, name, version="0.0.0", depends=[]):
    m = Manifest(name, name=name, version=version, depends=[Dependency(d) for d in depends])
    pkg = gl.GitlabPackage(manifest=m, project=project)
    project.packages.append(pkg)
    return pkg


class ResolverTest(unittest.TestCase):

    def test_rosdep(self):
        """Test package resolution with rosdep"""
        with patch("rosrepo.resolver._rosdep_instance", None):
            rosdep = resolver.get_rosdep()
            if rosdep.ok():
                if "catkin" in rosdep:
                    _, pkg_list = rosdep.resolve("catkin")
                    can_resolve_catkin_to_system_depend = False
                    for pkg in pkg_list:
                        if re.match("^ros-[a-z]+-catkin$", pkg):
                            can_resolve_catkin_to_system_depend = True
                    self.assertTrue(can_resolve_catkin_to_system_depend)
                    # Check if caching works correctly
                    _, pkg_list_2 = rosdep.resolve("catkin")
                    self.assertEqual(pkg_list, pkg_list_2)
                self.assertRaises(KeyError, rosdep.resolve, "nonsense%%")

    def test_find_dependees(self):
        """Test dependee resolution from workspace state"""
        ws_state = ws.WorkspaceState()
        ws_state.ws_packages = {}
        ws_state.ws_projects = []
        ws_state.ros_root_packages = {}
        ws_state.remote_packages = {}
        ws_state.remote_projects = []
        p1 = fake_gitlab_project(1, "cloned_project_1", "http://fake/cloned_project_1")
        ws_state.ws_packages["alpha"] = [fake_ws_package(p1, "alpha", depends=["beta"])]
        ws_state.ws_packages["beta"] = [fake_ws_package(p1, "beta", depends=["gamma"])]
        ws_state.ros_root_packages["rho"] = [fake_ws_package(None, "rho")]
        ws_state.ros_root_packages["sigma"] = [fake_ws_package(None, "sigma", version="2.0.0")]
        ws_state.ros_root_packages["tau"] = [fake_ws_package(None, "tau", version="1.0.0")]
        ws_state.ros_root_packages["omega"] = [fake_ws_package(None, "omega", version="1.0.0")]
        ws_state.ws_projects.append(p1)
        p2 = fake_gitlab_project(2, "remote_project_2", "http://fake/remote_project_2")
        ws_state.remote_projects.append(p2)
        p3 = fake_gitlab_project(3, "remote_project_3", "http://fake/remote_proejct_3")
        ws_state.remote_projects.append(p3)
        p4 = fake_gitlab_project(4, "remote_project_4", "http://fake/remote_proejct_4")
        ws_state.remote_projects.append(p4)
        ws_state.remote_packages["alpha"] = [fake_gitlab_package(p1, "alpha", depends=["beta"]), fake_gitlab_package(p3, "alpha")]
        ws_state.remote_packages["beta"] = [fake_gitlab_package(p1, "beta")]
        ws_state.remote_packages["gamma"] = [fake_gitlab_package(p3, "gamma", version="2.0.0"), fake_gitlab_package(p2, "gamma", version="1.0.0")]
        ws_state.remote_packages["delta"] = [fake_gitlab_package(p3, "delta")]
        ws_state.remote_packages["epsilon"] = [fake_gitlab_package(p2, "epsilon", depends=["missing"])]
        ws_state.remote_packages["theta"] = [fake_gitlab_package(p2, "theta", version="1.0.0"), fake_gitlab_package(p4, "theta", version="2.0.0")]
        ws_state.remote_packages["iota"] = [fake_gitlab_package(p4, "iota", depends=["sigma"])]
        ws_state.remote_packages["kappa"] = [fake_gitlab_package(p4, "kappa", depends=["omega"])]
        ws_state.remote_packages["sigma"] = [fake_gitlab_package(p2, "sigma", version="1.0.0")]
        ws_state.remote_packages["tau"] = [fake_gitlab_package(p2, "tau", version="1.0.0")]
        ws_state.remote_packages["omega"] = [fake_gitlab_package(p2, "omega", version="2.0.0")]

        # Pick the correct version of gamma that does not create a conflict
        depends, system_depends, conflicts = resolver.find_dependees(["alpha"], ws_state, auto_resolve=True)
        self.assertEqual(sorted(list(depends)), ["alpha", "beta", "gamma"])
        self.assertEqual(depends["gamma"].manifest.version, "1.0.0")
        self.assertEqual(list(system_depends), [])
        self.assertEqual(list(conflicts), [])

        # Reject delta because it creates a clone conflict
        depends, system_depends, conflicts = resolver.find_dependees(["delta"], ws_state, auto_resolve=True)
        self.assertEqual(list(depends), [])
        self.assertEqual(list(system_depends), [])
        self.assertEqual(list(conflicts), ["delta"])

        # Complain about missing depend
        depends, system_depends, conflicts = resolver.find_dependees(["epsilon"], ws_state, auto_resolve=True)
        self.assertEqual(list(depends), ["epsilon"])
        self.assertEqual(list(system_depends), [])
        self.assertEqual(list(conflicts), ["missing"])

        # If two packages are cloneable, pick the newer version
        depends, system_depends, conflicts = resolver.find_dependees(["theta"], ws_state, auto_resolve=True)
        self.assertEqual(list(depends), ["theta"])
        self.assertEqual(list(system_depends), [])
        self.assertEqual(list(conflicts), [])
        self.assertEqual(depends["theta"].manifest.version, "2.0.0")

        # If the dependent gitlab package version is older than the ROS root package version, do not clone it
        depends, system_depends, conflicts = resolver.find_dependees(["iota"], ws_state, auto_resolve=True, force_workspace=True)
        self.assertEqual(list(depends), ["iota"])
        self.assertEqual(list(system_depends), ["sigma"])
        self.assertEqual(list(conflicts), [])

        # If the dependent gitlab package version is newer than the ROS root package version, clone the gitlab one
        depends, system_depends, conflicts = resolver.find_dependees(["kappa"], ws_state, auto_resolve=True, force_workspace=False)
        self.assertEqual(sorted(list(depends)), ["kappa", "omega"])
        self.assertEqual(list(system_depends), [])
        self.assertEqual(list(conflicts), [])
        self.assertEqual(depends["omega"].manifest.version, "2.0.0")

        # If gitlab package and ROS root package are both available, clone only if explicitly instructed
        depends, system_depends, conflicts = resolver.find_dependees(["tau"], ws_state, auto_resolve=True, force_workspace=False)
        self.assertEqual(list(depends), [])
        self.assertEqual(list(system_depends), ["tau"])
        self.assertEqual(list(conflicts), [])
        depends, system_depends, conflicts = resolver.find_dependees(["tau"], ws_state, auto_resolve=True, force_workspace=True)
        self.assertEqual(list(depends), ["tau"])
        self.assertEqual(list(system_depends), [])
        self.assertEqual(list(conflicts), [])

        # Properly ignore ROS root packages if so instructed
        depends, system_depends, conflicts = resolver.find_dependees(["rho"], ws_state, auto_resolve=True, force_workspace=False)
        self.assertEqual(list(depends), [])
        self.assertEqual(list(system_depends), ["rho"])
        self.assertEqual(list(conflicts), [])
        depends, system_depends, conflicts = resolver.find_dependees(["rho"], ws_state, auto_resolve=True, force_workspace=True)
        self.assertEqual(list(depends), [])
        self.assertEqual(list(system_depends), [])
        self.assertEqual(list(conflicts), ["rho"])

        # Shallow (non-recursive) depends
        depends, system_depends, conflicts = resolver.find_dependees(["alpha"], ws_state, auto_resolve=True, recursive=False, force_workspace=False)
        self.assertEqual(sorted(list(depends)), ["alpha", "beta"])

