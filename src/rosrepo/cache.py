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
import os
try:
    import cPickle as pickle
except ImportError:
    import pickle
import zlib
from .util import write_atomic, makedirs, NamedTuple


class CacheFile(NamedTuple):
    __slots__ = ("version", "obj")


class Cache(object):

    def __init__(self, wsdir):
        self.cache_dir = os.path.join(wsdir, ".rosrepo", "cache")
        self.preloaded = {}

    def get_object(self, name, version, default=None):
        if name in self.preloaded:
            return self.preloaded[name]
        try:
            with open(os.path.join(self.cache_dir, name), "r") as f:
                cache_file = pickle.loads(zlib.decompress(f.read()))
        except (IOError, pickle.PickleError):
            return default
        if not isinstance(cache_file, CacheFile):
            return default
        if cache_file.version != version:
            return default
        self.preloaded[name] = cache_file.obj
        return cache_file.obj

    def set_object(self, name, version, obj):
        cache_file = CacheFile(version=version, obj=obj)
        makedirs(self.cache_dir)
        filepath = os.path.join(self.cache_dir, name)
        write_atomic(filepath, zlib.compress(pickle.dumps(cache_file, -1)), ignore_fail=True)
        self.preloaded[name] = obj

    def reset_object(self, name):
        try:
            os.unlink(os.path.join(self.cache_dir, name))
            if name in self.preloaded:
                del self.preloaded[name]
        except OSError:
            pass
