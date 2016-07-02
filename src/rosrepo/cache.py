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
            if self.preloaded[name].version == version:
                return self.preloaded[name].obj
            return default
        try:
            with open(os.path.join(self.cache_dir, name), "rb") as f:
                cache_file = pickle.loads(zlib.decompress(f.read()))
        except:
            return default
        if not isinstance(cache_file, CacheFile):
            return default
        self.preloaded[name] = cache_file
        if cache_file.version != version:
            return default
        return cache_file.obj

    def set_object(self, name, version, obj):
        cache_file = CacheFile(version=version, obj=obj)
        makedirs(self.cache_dir)
        filepath = os.path.join(self.cache_dir, name)
        write_atomic(filepath, zlib.compress(pickle.dumps(cache_file, -1)), ignore_fail=True)
        self.preloaded[name] = cache_file

    def reset_object(self, name):
        if name in self.preloaded:
            del self.preloaded[name]
        try:
            os.unlink(os.path.join(self.cache_dir, name))
        except OSError:
            pass
