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

import os
import sys
sys.stderr = sys.stdout

try:
    from mock import patch
except ImportError:
    from unittest.mock import patch

import rosrepo.util as util

class TestTuple(util.NamedTuple):
    __slots__ = ("first", "second")

class UtilTest(unittest.TestCase):
    def test_path_has_prefix(self):
        """Test path_has_prefix() function"""
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
        """Test NamedTuple class"""
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

    def test_find_program(self):
        """Test find_program() function"""
        with patch("os.path.isfile", lambda x : "exist" in x):
            with patch("os.access", lambda x, y: "bin" in x):
                with patch("os.environ", {"PATH": os.pathsep.join(["/missing", "/existing/stuff", "/existing/bin"])}):
                    self.assertEqual(
                        util.find_program("/exists-but-not-in-path/binary"),
                        "/exists-but-not-in-path/binary"
                    )
                    self.assertEqual(
                        util.find_program("/missing-path/binary"),
                        None
                    )
                    self.assertEqual(
                        util.find_program("/existing/not-executable"),
                        None
                    )
                    self.assertEqual(
                        util.find_program("stuff"),
                        "/existing/bin/stuff"
                    )
                with patch("os.environ", {"PATH": "/existing/stuff"}):
                    self.assertEqual(
                        util.find_program("stuff"),
                        None
                    )
    
    def test_call_process(self):
        """Test call_process() function"""
        exitcode = util.call_process(["/bin/true"])
        self.assertEqual(exitcode, 0)
        exitcode = util.call_process(["/bin/false"])
        self.assertEqual(exitcode, 1)
        exitcode, stdout, stderr = util.call_process(["/bin/sh", "-c", "read var; echo $var; echo>&2 stderr"], stdin=util.PIPE, stdout=util.PIPE, stderr=util.PIPE, input_data="stdout\n")
        self.assertIn("stdout", stdout)
        self.assertIn("stderr", stderr)

    def test_terminal_size(self):
        """Test get_terminal_size() function"""
        with patch("os.ctermid", lambda: os.devnull):
            util._cached_terminal_size = None
            self.assertRaises(OSError, util.get_terminal_size)
