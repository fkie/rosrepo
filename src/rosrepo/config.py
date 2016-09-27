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
import os
import yaml
from distutils.version import StrictVersion as Version
from .util import write_atomic, UserError, makedirs
from . import __version__


class ConfigError(UserError):
    pass


class Config(object):
    def __init__(self, wsdir, read_only=False):
        self.config_dir = os.path.join(wsdir, ".rosrepo")
        self.config_file = os.path.join(self.config_dir, "config")
        self.read_only = read_only
        if os.path.isfile(self.config_file):
            try:
                with open(self.config_file, "rb") as f:
                    self._data = yaml.safe_load(f)
            except (OSError, IOError, yaml.YAMLError):
                raise ConfigError("unreadable configuration file")
            if not isinstance(self._data, dict):
                raise ConfigError("invalid configuration file")
            if "version" not in self._data:
                raise ConfigError("missing configuration version number")
            current = Version(__version__)
            try:
                stored = Version(self._data["version"])
            except (TypeError, ValueError):
                raise ConfigError("invalid configuration version number")
            if stored < current and not read_only:
                self._migrate(stored)
            if stored > current and not read_only:
                raise ConfigError("workspace was configured by newer version of rosrepo")
        else:
            self._data = {"version": __version__}

    def write(self):
        if self.read_only:
            raise ConfigError("cannot write config file marked as read only")
        makedirs(self.config_dir)
        write_atomic(self.config_file, yaml.safe_dump(self._data, encoding="UTF-8", default_flow_style=False))

    def _migrate(self, old_version):
        if old_version <= Version("3.0.25"):
            if "crawl_depth" in self._data:
                self._data["gitlab_crawl_depth"] = self._data["crawl_depth"]
                del self._data["crawl_depth"]
        self._data["version"] = __version__
        self.write()

    def set_default(self, key, value):
        if self.read_only:
            raise ConfigError("cannot change read-only configuration")
        if key not in self._data:
            self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        if self.read_only:
            raise ConfigError("cannot change read-only configuration")
        self._data[key] = value

    def __delitem__(self, key):
        if self.read_only:
            raise ConfigError("cannot change read-only configuration")
        if key in self._data:
            del self._data[key]

    def __iter__(self):
        return self._data.__iter__()

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data
