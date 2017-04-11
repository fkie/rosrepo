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

import sys
sys.stderr = sys.stdout
import os
import shutil
from tempfile import mkdtemp
from distutils.version import StrictVersion

from rosrepo.config import Config, ConfigError
from rosrepo import __version__ as rosrepo_version

class ConfigTest(unittest.TestCase):

    def setUp(self):
        self.wsdir = mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.wsdir, ignore_errors=True)

    def test_storage(self):
        """Test configuration storage and retrieval"""
        cfg = Config(self.wsdir)
        cfg.set_default("default", "value")
        cfg["test"] = "value"
        cfg["unicode"] = u"ÄÖÜ"
        cfg.set_default("test", "wrong_value")
        self.assertEqual(cfg.get("test"), "value")
        self.assertTrue("test" in cfg)
        self.assertFalse("missing" in cfg)
        self.assertTrue("default" in cfg)
        del cfg["default"]
        self.assertTrue("default" not in cfg)
        self.assertEqual(sorted([k for k in cfg]), ["test", "unicode", "version"])
        self.assertEqual(len(cfg), 3)
        cfg.write()
        new_cfg = Config(self.wsdir)
        self.assertEqual(new_cfg.get("test"), "value")
        self.assertEqual(new_cfg.get("unicode"), u"ÄÖÜ")

    def test_corrupted(self):
        """Test handling of corrupted configuration files"""
        cfg_dir = os.path.join(self.wsdir, ".rosrepo")
        os.makedirs(cfg_dir)
        cfg_file = os.path.join(cfg_dir, "config")
        with open(cfg_file, "w") as f:
            f.write("[1,2,3]")
        self.assertRaises(ConfigError, lambda: Config(self.wsdir))
        with open(cfg_file, "w") as f:
            f.write(":[::] GARBAGE")
        self.assertRaises(ConfigError, lambda: Config(self.wsdir))
        with open(cfg_file, "w") as f:
            f.write("no_version: yes")
        self.assertRaises(ConfigError, lambda: Config(self.wsdir))
        with open(cfg_file, "w") as f:
            f.write("version: invalid")
        self.assertRaises(ConfigError, lambda: Config(self.wsdir))
        with open(cfg_file, "w") as f:
            f.write("version: 123")
        self.assertRaises(ConfigError, lambda: Config(self.wsdir))
        with open(cfg_file, "w") as f:
            f.write("version: %s" % rosrepo_version)
        cfg = Config(self.wsdir)
        os.chmod(cfg_file, 0)
        self.assertRaises(ConfigError, lambda: Config(self.wsdir))
        os.chmod(cfg_file, 0o644)
        os.chmod(cfg_dir, 0)
        self.assertRaises(ConfigError, cfg.write)
        os.chmod(cfg_dir, 0o755)

    def test_version_mismatch(self):
        """Test handling of configuration files from different rosrepo versions"""
        os.makedirs(os.path.join(self.wsdir, ".rosrepo"))
        cfg_file = os.path.join(self.wsdir, ".rosrepo", "config")
        with open(cfg_file, "w") as f:
            f.write("version: %s" % rosrepo_version)
        cfg = Config(self.wsdir)
        self.assertEqual(cfg.get("version"), rosrepo_version)
        with open(cfg_file, "w") as f:
            f.write("version: 3.0.0a0")
        cfg = Config(self.wsdir)
        self.assertEqual(cfg.get("version"), rosrepo_version)
        # revisions may change without affecting config compatibility
        v = StrictVersion(rosrepo_version)
        v.version = tuple([v.version[0], v.version[1], v.version[2] + 1])
        with open(cfg_file, "w") as f:
            f.write('version: "%s"' % str(v))
        cfg = Config(self.wsdir)
        self.assertEqual(cfg.get("version"), str(v))
        # major or minor version number change means incompatible configurations
        v.version = tuple([v.version[0], v.version[1] + 1, 0])
        with open(cfg_file, "w") as f:
            f.write('version: "%s"' % str(v))
        self.assertRaises(ConfigError, lambda: Config(self.wsdir))
        v.version = tuple([v.version[0] + 1, 0, 0])
        with open(cfg_file, "w") as f:
            f.write('version: "%s"' % str(v))
        self.assertRaises(ConfigError, lambda: Config(self.wsdir))

    def test_read_only(self):
        """Test if read-only configurations are actually immutable"""
        def helper1():
            cfg["test"] = "new_value"
        def helper2():
            del cfg["test"]
        cfg = Config(self.wsdir)
        cfg["test"] = "value"
        cfg.write()
        cfg = Config(self.wsdir, read_only=True)
        self.assertEqual(cfg["test"], "value")
        self.assertEqual(cfg.get("missing"), None)
        self.assertRaises(ConfigError, cfg.write)
        self.assertRaises(ConfigError, cfg.set_default, "answer", 42)
        self.assertRaises(ConfigError, helper1)
        self.assertRaises(ConfigError, helper2)
