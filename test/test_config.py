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
from tempfile import mkdtemp

from rosrepo.config import Config, ConfigError
from rosrepo import __version__ as rosrepo_version

class ConfigTest(unittest.TestCase):

    def setUp(self):
        self.wsdir = mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.wsdir, ignore_errors=True)

    def test_storage(self):
        cfg = Config(self.wsdir)
        cfg["test"] = "value"
        cfg["unicode"] = u"ÄÖÜ"
        self.assertTrue("test" in cfg)
        self.assertFalse("missing" in cfg)
        self.assertEqual(sorted([k for k in cfg]), ["test", "unicode", "version"])
        self.assertEqual(len(cfg), 3)
        cfg.write()
        new_cfg = Config(self.wsdir)
        self.assertEqual(new_cfg.get("test"), "value")
        self.assertEqual(new_cfg.get("unicode"), u"ÄÖÜ")

    def test_corrupted(self):
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
        self.assertRaises(OSError, cfg.write)
        os.chmod(cfg_dir, 0o755)

    def test_version_mismatch(self):
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
        with open(cfg_file, "w") as f:
            f.write('version: "999.0"')
        self.assertRaises(ConfigError, lambda: Config(self.wsdir))

    def test_read_only(self):
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
