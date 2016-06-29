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

import rosrepo.util as util

class UtilTest(unittest.TestCase):
    def test_path_has_prefix(self):
        self.assertTrue(util.path_has_prefix("abc", "abc"))
        self.assertTrue(util.path_has_prefix("/abc", "/abc"))
        self.assertFalse(util.path_has_prefix("abc", "/abc"))
        self.assertFalse(util.path_has_prefix("/abc", "abc"))
        self.assertFalse(util.path_has_prefix("abc", "a"))
        self.assertFalse(util.path_has_prefix("/abc", "/a"))
        self.assertTrue(util.path_has_prefix("abc/def", "abc"))
        self.assertTrue(util.path_has_prefix("/abc/def/ghi", "/abc/def"))
        self.assertFalse(util.path_has_prefix("/abc/efg", "/hij/klm"))
        self.assertFalse(util.path_has_prefix("abc/efg", "hij/klm"))

