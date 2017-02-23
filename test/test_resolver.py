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
import test.helper as helper

class ResolverTest(unittest.TestCase):

    def test_rosdep(self):
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
