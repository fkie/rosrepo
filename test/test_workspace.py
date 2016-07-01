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
import os
import shutil
import helper
import yaml
import pickle
from tempfile import mkdtemp
from rosrepo.config import Config
import sys
sys.stderr = sys.stdout


class WorkspaceTest(unittest.TestCase):

    def setUp(self):
        self.ros_root_dir = mkdtemp()
        self.workspace_dir = mkdtemp()
        helper.create_fake_ros_root(self.ros_root_dir)
        helper.create_package(self.workspace_dir, "alpha", ["beta", "gamma"])
        helper.create_package(self.workspace_dir, "beta", ["delta"])
        helper.create_package(self.workspace_dir, "gamma", [])
        helper.create_package(self.workspace_dir, "delta", [])
        helper.create_package(self.workspace_dir, "epsilon", ["broken"])
        helper.create_package(self.workspace_dir, "broken", ["missing"])
        os.environ = {"PATH": "/usr/bin:/bin"}  # rosdep2 dies without PATH variable

    def tearDown(self):
        shutil.rmtree(self.workspace_dir, ignore_errors=True)
        shutil.rmtree(self.ros_root_dir, ignore_errors=True)
        self.ros_root_dir = None
        self.workspace_dir = None

    def get_config_value(self, key, default=None):
        cfg = Config(self.workspace_dir, read_only=True)
        return cfg.get(key, default)

    def test_bash(self):
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.workspace_dir),
            (0, "")
        )
        self.assertEqual(
            helper.run_rosrepo("bash", "-w", self.workspace_dir, "ROS_WORKSPACE", "ROS_PACKAGE_PATH", "PATH", "UNKNOWN"),
            (0, "ROS_WORKSPACE=%(wsdir)s\nROS_PACKAGE_PATH=%(wsdir)s/src\nPATH=%(env_path)s\n# variable UNKNOWN is not set\n" % {"wsdir": self.workspace_dir, "env_path": os.environ["PATH"]})
        )
    def test_upgrade_from_version_1(self):
        os.rename(os.path.join(self.workspace_dir, "src"), os.path.join(self.workspace_dir, "repos"))
        os.makedirs(os.path.join(self.workspace_dir, "src"))
        with open(os.path.join(self.workspace_dir, "src", "CMakeLists.txt"), "w"):
            pass
        with open(os.path.join(self.workspace_dir, "src", "toplevel.cmake"), "w"):
            pass
        with open(os.path.join(self.workspace_dir, ".catkin_workspace"), "w"):
            pass
        os.symlink(os.path.join("..", "repos", "alpha"), os.path.join(self.workspace_dir, "src", "alpha"))
        os.symlink(os.path.join("..", "repos", "beta"), os.path.join(self.workspace_dir, "src", "beta"))
        os.symlink(os.path.join("..", "repos", "gamma"), os.path.join(self.workspace_dir, "src", "gamma"))
        os.symlink(os.path.join("..", "repos", "delta"), os.path.join(self.workspace_dir, "src", "delta"))
        with open(os.path.join(self.workspace_dir, "repos", ".metainfo"), "w") as f:
            f.write(yaml.safe_dump(
                {
                 "alpha": {"auto": False, "pin": False},
                 "beta": {"auto": False, "pin": True},
                 "gamma": {"auto": True, "pin": False},
                 "delta": {"auto": True, "pin": False},
                },
                default_flow_style=False
            ))
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.workspace_dir),
            (0, "")
        )
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.workspace_dir, "-n"),
            (0, "alpha\nbeta\ndelta\ngamma\n")
        )
        self.assertEqual(self.get_config_value("default_build"), ["alpha"])
        self.assertEqual(self.get_config_value("pinned_build"), ["beta"])

    def test_upgrade_from_version_2(self):
        with open(os.path.join(self.workspace_dir, ".catkin_workspace"), "w"):
            pass
        os.makedirs(os.path.join(self.workspace_dir, ".catkin_tools", "profiles", "rosrepo"))
        os.makedirs(os.path.join(self.workspace_dir, ".rosrepo"))
        from rosrepo.common import PkgInfo
        with open(os.path.join(self.workspace_dir, ".rosrepo", "info"), "w") as f:
            metadata = {}
            metadata["alpha"] = PkgInfo()
            metadata["beta"] = PkgInfo()
            metadata["alpha"].selected = True
            metadata["beta"].selected = True
            metadata["beta"].pinned = True
            f.write(pickle.dumps(metadata))
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.workspace_dir),
            (0, "")
        )
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.workspace_dir, "-n"),
            (0, "alpha\nbeta\ndelta\ngamma\n")
        )
        self.assertEqual(self.get_config_value("default_build"), ["alpha"])
        self.assertEqual(self.get_config_value("pinned_build"), ["beta"])

    def test_different_config_version(self):
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.workspace_dir),
            (0, "")
        )
        self.assertEqual(
            helper.run_rosrepo("include", "-w", self.workspace_dir, "alpha"),
            (0, "")
        )
        cfg = Config(self.workspace_dir)
        cfg["version"] = "3.0.0a0"
        cfg.write()
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.workspace_dir, "-n"),
            (0, "alpha\nbeta\ndelta\ngamma\n")
        )
        from rosrepo import __version__ as rosrepo_version
        self.assertEqual(self.get_config_value("version"), rosrepo_version)
        cfg = Config(self.workspace_dir)
        cfg["version"] = "999.0"
        cfg.write()
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.workspace_dir, "-n")[0],
            1
        )

    def test_corrupted_config(self):
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.workspace_dir),
            (0, "")
        )
        cfg = Config(self.workspace_dir)
        del cfg["version"]
        cfg.write()
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.workspace_dir, "-n")[0],
            1
        )
        with open(os.path.join(self.workspace_dir, ".rosrepo", "config"), "w") as f:
            f.write("#+?($!'$")
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.workspace_dir, "-n")[0],
            1
        )

    def test_buildset(self):
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.workspace_dir),
            (0, "")
        )
        self.assertEqual(
            helper.run_rosrepo("include", "-w", self.workspace_dir, "alpha"),
            (0, "")
        )
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.workspace_dir, "-n"),
            (0, "alpha\nbeta\ndelta\ngamma\n")
        )
        self.assertEqual(self.get_config_value("default_build"), ["alpha"])
        self.assertEqual(self.get_config_value("pinned_build"), [])
        self.assertEqual(
            helper.run_rosrepo("include", "-w", self.workspace_dir, "--pinned", "beta"),
            (0, "")
        )
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.workspace_dir, "-n"),
            (0, "alpha\nbeta\ndelta\ngamma\n")
        )
        self.assertEqual(self.get_config_value("pinned_build"), ["beta"])
        self.assertEqual(
            helper.run_rosrepo("exclude", "-w", self.workspace_dir, "-a"),
            (0, "")
        )
        self.assertEqual(self.get_config_value("default_build"), [])
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.workspace_dir, "-n"),
            (0, "beta\ndelta\n")
        )
        self.assertEqual(
            helper.run_rosrepo("include", "-w", self.workspace_dir, "--default", "beta"),
            (0, "")
        )
        self.assertEqual(
            helper.run_rosrepo("exclude", "-w", self.workspace_dir, "--pinned", "beta"),
            (0, "")
        )
        self.assertEqual(self.get_config_value("default_build"), ["beta"])
        self.assertEqual(self.get_config_value("pinned_build"), [])
        self.assertEqual(
            helper.run_rosrepo("include", "-w", self.workspace_dir, "--pinned", "epsilon")[0],
            1
        )
        self.assertEqual(
            helper.run_rosrepo("include", "-w", self.workspace_dir, "--default", "epsilon")[0],
            1
        )
        self.assertEqual(
            helper.run_rosrepo("include", "-w", self.workspace_dir, "--default", "--all")[0],
            1
        )
        self.assertEqual(self.get_config_value("default_build"), ["beta"])
        self.assertEqual(self.get_config_value("pinned_build"), [])
        self.assertEqual(
            helper.run_rosrepo("init", "--reset", "-r", self.ros_root_dir, self.workspace_dir),
            (0, "")
        )
        self.assertEqual(self.get_config_value("default_build", []), [])
        self.assertEqual(self.get_config_value("pinned_build", []), [])

    def test_config(self):
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.workspace_dir),
            (0, "")
        )
        #######################
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--job-limit", "16")[0],
            0
        )
        self.assertEqual(self.get_config_value("job_limit"), 16)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--job-limit", "0")[0],
            0
        )
        self.assertEqual(self.get_config_value("job_limit"), None)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--job-limit", "8")[0],
            0
        )
        self.assertEqual(self.get_config_value("job_limit"), 8)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--no-job-limit")[0],
            0
        )
        self.assertEqual(self.get_config_value("job_limit"), None)
        #######################
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--install")[0],
            0
        )
        self.assertEqual(self.get_config_value("install"), True)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--no-install")[0],
            0
        )
        self.assertEqual(self.get_config_value("install"), False)
        #######################
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--set-compiler", "clang")[0],
            0
        )
        self.assertEqual(self.get_config_value("compiler"), "clang")
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--set-compiler", "does_not_exist")[0],
            1
        )
        self.assertEqual(self.get_config_value("compiler"), "clang")
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--unset-compiler")[0],
            0
        )
        self.assertEqual(self.get_config_value("compiler"), None)
        #######################
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--set-gitlab-url", "Test", "http://localhost", "--private-token", "t0ps3cr3t", "--store-credentials")[0],
            0
        )
        self.assertEqual(self.get_config_value("store_credentials"), True)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--no-store-credentials")[0],
            0
        )
        self.assertEqual(self.get_config_value("store_credentials"), False)
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost", "private_token": "t0ps3cr3t"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--set-gitlab-url", "Test", "http://localhost", "--private-token", "t0ps3cr3t")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost", "private_token": "t0ps3cr3t"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--get-gitlab-url", "does_not_exist"),
            (0, "\n")
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--get-gitlab-url", "Test"),
            (0, "http://localhost\n")
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--show-gitlab-urls", "--autocomplete"),
            (0, "Test\n")
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--gitlab-logout", "does_not_exist")[0],
            1
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--gitlab-logout", "Test")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--set-gitlab-url", "Test", "http://localhost", "--private-token", "t0ps3cr3t")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--unset-gitlab-url", "Test")[0],
            0
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--show-gitlab-urls", "--autocomplete"),
            (0, "\n")
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--set-gitlab-url", "Test", "http://localhost", "--private-token", "t0ps3cr3t")[0],
            0
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--gitlab-login", "Test", "--private-token", "t0ps3cr3t")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--set-gitlab-url", "Test", "http://localhost", "--private-token", "t0ps3cr3t", "--store-credentials")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost", "private_token": "t0ps3cr3t"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--remove-credentials")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--gitlab-login", "Test", "--private-token", "t0ps3cr3t")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost", "private_token": "t0ps3cr3t"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--offline", "--set-gitlab-url", "Test", "http://localhost")[0],
            1
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--offline", "--gitlab-login", "Test")[0],
            1
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--unset-gitlab-url", "Test")[0],
            0
        )
        #######################
        self.assertEqual(self.get_config_value("ros_root"), self.ros_root_dir)
        helper.run_rosrepo("config", "-w", self.workspace_dir, "--unset-ros-root")
        self.assertEqual(self.get_config_value("ros_root"), None)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--set-ros-root", self.ros_root_dir)[0],
            0
        )
        self.assertEqual(self.get_config_value("ros_root"), self.ros_root_dir)
        #######################
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--no-catkin-lint")[0],
            0
        )
        self.assertEqual(self.get_config_value("use_catkin_lint"), False)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--catkin-lint")[0],
            0
        )
        self.assertEqual(self.get_config_value("use_catkin_lint"), True)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--no-catkin-lint")[0],
            0
        )
        self.assertEqual(self.get_config_value("use_catkin_lint"), False)
        #######################
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--no-rosclipse")[0],
            0
        )
        self.assertEqual(self.get_config_value("use_rosclipse"), False)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--rosclipse")[0],
            0
        )
        self.assertEqual(self.get_config_value("use_rosclipse"), True)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.workspace_dir, "--no-rosclipse")[0],
            0
        )
        self.assertEqual(self.get_config_value("use_rosclipse"), False)

