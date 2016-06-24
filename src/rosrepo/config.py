"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import os
import yaml
from distutils.version import StrictVersion as Version
from .util import write_atomic, UserError
from . import __version__


class ConfigError(UserError):
    pass


class Config(object):
    def __init__(self, wsdir, read_only=False):
        self.config_dir = os.path.join(wsdir, ".rosrepo")
        self.config_file = os.path.join(self.config_dir, "config")
        self.read_only = read_only
        if os.path.isfile(self.config_file):
            with open(self.config_file, "r") as f:
                self._data = yaml.safe_load(f.read())
            if not isinstance(self._data, dict):
                raise ConfigError("Corrupted rosrepo configuration file")
            if "version" not in self._data:
                raise ConfigError("Corrupted rosrepo configuration file")
            current = Version(__version__)
            stored = Version(self._data["version"])
            if stored < current and not read_only:
                self.migrate(stored)
            if stored > current and not read_only:
                raise ConfigError("Workspace was configured by newer version of rosrepo")
        else:
            self._data = {"version": __version__}

    def write(self):
        if self.read_only:
            raise RuntimeError("Cannot write config file marked as read only")
        if not os.path.isdir(self.config_dir):
            os.makedirs(self.config_dir)
        write_atomic(self.config_file, yaml.safe_dump(self._data, default_flow_style=False))

    def _migrate(self, old_version):
        self._data["version"] = __version__

    def set_default(self, key, value):
        if key not in self._data:
            self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        if self.read_only:
            raise ValueError("Cannot change read-only configuration")
        self._data[key] = value

    def __iter__(self):
        return self._data.__iter__()

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data
