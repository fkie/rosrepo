# coding=utf-8
#
# ROSREPO
# Manage ROS workspaces with multiple Gitlab repositories
#
# Author: Timo Röhling
#
# Copyright (c) 2016 Fraunhofer FKIE
#
#
import unittest

import sys
sys.stderr = sys.stdout
import re

import helper
try:
    from mock import patch
except ImportError:
    from unittest.mock import patch

import rosrepo.resolver as resolver


class ResolverTest(unittest.TestCase):

    def test_apt_installed(self):
        self.assertEqual(
            resolver.apt_installed(["bash", "nonsense%%"]),
            set(["bash"])
        )

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
