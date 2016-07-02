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

import rosrepo.util as util

class TestTuple(util.NamedTuple):
    __slots__ = ("first", "second")

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

    def test_named_tuple(self):
        t = TestTuple(1, 2)
        self.assertEqual(len(t), 2)
        self.assertEqual(t.first, 1)
        self.assertEqual(t[0], 1)
        self.assertEqual(t.second, 2)
        self.assertEqual(t[1], 2)
        self.assertEqual(str(t), "TestTuple(first=1, second=2)")
        self.assertEqual([d for d in t], [1, 2])        
        t = TestTuple(first=3, second=4)
        self.assertEqual(t.first, 3)
        self.assertEqual(t.second, 4)
        t.first = 5
        self.assertEqual(t.first, 5)
        t[1] = 6
        self.assertEqual(t.second, 6)
