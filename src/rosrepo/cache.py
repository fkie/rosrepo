"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import os
import pickle
from .util import write_atomic, makedirs


class CacheFile(object):
    def __init__(self, version, obj=None):
        self.version = version
        self.obj = obj


class Cache(object):

    def __init__(self, wsdir):
        self.cache_dir = os.path.join(wsdir, ".rosrepo", "cache")

    def get_object(self, name, version, default=None):
        try:
            with open(os.path.join(self.cache_dir, name), "r") as f:
                cache_file = pickle.loads(f.read())
        except (IOError, pickle.PickleError):
            return default
        if not isinstance(cache_file, CacheFile):
            return default
        if cache_file.version != version:
            return default
        return cache_file.obj

    def set_object(self, name, version, obj):
        cache_file = CacheFile(version, obj)
        makedirs(self.cache_dir)
        filepath = os.path.join(self.cache_dir, name)
        write_atomic(filepath, pickle.dumps(cache_file, -1), ignore_fail=True)

    def reset_object(self, name):
        try:
            os.unlink(os.path.join(self.cache_dir, name))
        except OSError:
            pass
