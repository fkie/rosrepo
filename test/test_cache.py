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
import os
import shutil
import zlib
from tempfile import mkdtemp
try:
    import cPickle as pickle
except ImportError:
    import pickle
from rosrepo.cache import Cache, CacheFile
from rosrepo.util import NamedTuple


class NotACacheFile(NamedTuple):
    __slots__ = ("version", "obj", "extra")


class CacheTest(unittest.TestCase):

    def setUp(self):
        self.wsdir = mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.wsdir, ignore_errors=True)

    def test_storage(self):
        cache = Cache(self.wsdir)
        cache.set_object("test", 1, "Hello, World")
        self.assertEqual(cache.get_object("test", 1), "Hello, World")
        new_cache = Cache(self.wsdir)
        self.assertEqual(new_cache.get_object("test", 1), "Hello, World")
        self.assertEqual(cache.get_object("missing", 1), None)
        self.assertEqual(cache.get_object("missing", 1, "default"), "default")
        cache.reset_object("test")
        self.assertEqual(cache.get_object("test", 1), None)
        self.assertEqual(new_cache.get_object("test", 1), "Hello, World")
        new_cache = Cache(self.wsdir)
        self.assertEqual(new_cache.get_object("test", 1), None)

    def test_version_change(self):
        cache = Cache(self.wsdir)
        cache.set_object("test", 1, "data")
        self.assertEqual(cache.get_object("test", 1), "data")
        self.assertEqual(cache.get_object("test", 2), None)
        new_cache = Cache(self.wsdir)
        self.assertEqual(new_cache.get_object("test", 2), None)
        new_cache = Cache(self.wsdir)
        self.assertEqual(new_cache.get_object("test", 1), "data")

    def test_access_denied(self):
        cache = Cache(self.wsdir)
        cache.set_object("test", 1, "data")
        os.chmod(os.path.join(self.wsdir, ".rosrepo", "cache"), 0)
        cache.set_object("test", 1, "changed")
        self.assertEqual(cache.get_object("test", 1), "changed")
        cache.reset_object("test")
        self.assertEqual(cache.get_object("test", 1), None)
        os.chmod(os.path.join(self.wsdir, ".rosrepo", "cache"), 0o755)
        new_cache = Cache(self.wsdir)
        self.assertEqual(new_cache.get_object("test", 1), "data")
        
    def test_corruption(self):
        os.makedirs(os.path.join(self.wsdir, ".rosrepo", "cache"))
        with open(os.path.join(self.wsdir, ".rosrepo", "cache", "broken1"), "w") as f:
            f.write("GARBAGE")
        with open(os.path.join(self.wsdir, ".rosrepo", "cache", "broken2"), "wb") as f:
            data = NotACacheFile()
            data.version = 1
            data.obj = "fooled"
            f.write(zlib.compress(pickle.dumps(data, -1)))
        with open(os.path.join(self.wsdir, ".rosrepo", "cache", "valid"), "wb") as f:
            data = CacheFile()
            data.version = 1
            data.obj = "works"
            f.write(zlib.compress(pickle.dumps(data, -1)))
        cache = Cache(self.wsdir)
        self.assertEqual(cache.get_object("valid", 1), "works")
        self.assertEqual(cache.get_object("broken1", 1), None)
        self.assertEqual(cache.get_object("broken2", 1), None)
