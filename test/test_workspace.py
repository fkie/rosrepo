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
        self.wsdir = mkdtemp()
        helper.create_fake_ros_root(self.ros_root_dir)
        helper.create_package(self.wsdir, "alpha", ["beta", "gamma"])
        helper.create_package(self.wsdir, "beta", ["delta"])
        helper.create_package(self.wsdir, "gamma", [])
        helper.create_package(self.wsdir, "delta", [])
        helper.create_package(self.wsdir, "epsilon", ["broken"])
        helper.create_package(self.wsdir, "broken", ["missing"])
        os.environ = {"PATH": "/usr/bin:/bin"}  # rosdep2 dies without PATH variable

    def tearDown(self):
        shutil.rmtree(self.wsdir, ignore_errors=True)
        shutil.rmtree(self.ros_root_dir, ignore_errors=True)
        self.ros_root_dir = None
        self.wsdir = None

    def get_config_value(self, key, default=None):
        cfg = Config(self.wsdir, read_only=True)
        return cfg.get(key, default)

    def test_bash(self):
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir),
            (0, "")
        )
        self.assertEqual(
            helper.run_rosrepo("bash", "-w", self.wsdir, "ROS_WORKSPACE", "ROS_PACKAGE_PATH", "PATH", "UNKNOWN"),
            (0, "ROS_WORKSPACE=%(wsdir)s\nROS_PACKAGE_PATH=%(wsdir)s/src\nPATH=%(env_path)s\n# variable UNKNOWN is not set\n" % {"wsdir": self.wsdir, "env_path": os.environ["PATH"]})
        )
        os.environ["ROS_PACKAGE_PATH"] = os.pathsep.join(["/before"] + ["%s/src/%s" % (self.wsdir, d) for d in ["alpha", "beta", "gamma"]] + ["/after"])
        self.assertEqual(
            helper.run_rosrepo("bash", "-w", self.wsdir),
            (0, "ROS_WORKSPACE=%(wsdir)s\nROS_PACKAGE_PATH=/before%(sep)s%(wsdir)s/src%(sep)s/after\n" % {"wsdir": self.wsdir, "sep": os.pathsep})
        )

    def test_clean(self):
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir),
            (0, "")
        )
        os.makedirs(os.path.join(self.wsdir, "build"))
        self.assertEqual(
            helper.run_rosrepo("clean", "-w", self.wsdir, "--dry-run"),
            (0, "")
        )
        self.assertTrue(os.path.isdir(os.path.join(self.wsdir, "build")))
        self.assertEqual(
            helper.run_rosrepo("clean", "-w", self.wsdir),
            (0, "")
        )
        self.assertFalse(os.path.isdir(os.path.join(self.wsdir, "build")))
        
    def test_upgrade_from_version_1(self):
        os.rename(os.path.join(self.wsdir, "src"), os.path.join(self.wsdir, "repos"))
        os.makedirs(os.path.join(self.wsdir, "src"))
        with open(os.path.join(self.wsdir, "src", "CMakeLists.txt"), "w"):
            pass
        with open(os.path.join(self.wsdir, "src", "toplevel.cmake"), "w"):
            pass
        with open(os.path.join(self.wsdir, ".catkin_workspace"), "w"):
            pass
        os.symlink(os.path.join("..", "repos", "alpha"), os.path.join(self.wsdir, "src", "alpha"))
        os.symlink(os.path.join("..", "repos", "beta"), os.path.join(self.wsdir, "src", "beta"))
        os.symlink(os.path.join("..", "repos", "gamma"), os.path.join(self.wsdir, "src", "gamma"))
        os.symlink(os.path.join("..", "repos", "delta"), os.path.join(self.wsdir, "src", "delta"))
        with open(os.path.join(self.wsdir, "repos", ".metainfo"), "w") as f:
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
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir),
            (0, "")
        )
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.wsdir, "-n"),
            (0, "alpha\nbeta\ndelta\ngamma\n")
        )
        self.assertEqual(self.get_config_value("default_build"), ["alpha"])
        self.assertEqual(self.get_config_value("pinned_build"), ["beta"])

    def test_upgrade_from_version_2(self):
        with open(os.path.join(self.wsdir, ".catkin_workspace"), "w"):
            pass
        os.makedirs(os.path.join(self.wsdir, ".catkin_tools", "profiles", "rosrepo"))
        os.makedirs(os.path.join(self.wsdir, ".rosrepo"))
        from rosrepo.common import PkgInfo
        with open(os.path.join(self.wsdir, ".rosrepo", "info"), "wb") as f:
            metadata = {}
            metadata["alpha"] = PkgInfo()
            metadata["beta"] = PkgInfo()
            metadata["alpha"].selected = True
            metadata["beta"].selected = True
            metadata["beta"].pinned = True
            f.write(pickle.dumps(metadata))
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir),
            (0, "")
        )
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.wsdir, "-n"),
            (0, "alpha\nbeta\ndelta\ngamma\n")
        )
        self.assertEqual(self.get_config_value("default_build"), ["alpha"])
        self.assertEqual(self.get_config_value("pinned_build"), ["beta"])

    def test_different_config_version(self):
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir),
            (0, "")
        )
        self.assertEqual(
            helper.run_rosrepo("include", "-w", self.wsdir, "alpha"),
            (0, "")
        )
        cfg = Config(self.wsdir)
        cfg["version"] = "3.0.0a0"
        cfg.write()
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.wsdir, "-n"),
            (0, "alpha\nbeta\ndelta\ngamma\n")
        )
        from rosrepo import __version__ as rosrepo_version
        self.assertEqual(self.get_config_value("version"), rosrepo_version)
        cfg = Config(self.wsdir)
        cfg["version"] = "999.0"
        cfg.write()
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.wsdir, "-n")[0],
            1
        )

    def test_corrupted_config(self):
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir),
            (0, "")
        )
        cfg = Config(self.wsdir)
        del cfg["version"]
        cfg.write()
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.wsdir, "-n")[0],
            1
        )
        with open(os.path.join(self.wsdir, ".rosrepo", "config"), "w") as f:
            f.write("#+?($!'$")
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.wsdir, "-n")[0],
            1
        )

    def test_buildset(self):
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir),
            (0, "")
        )
        self.assertEqual(
            helper.run_rosrepo("include", "-w", self.wsdir, "--dry-run", "alpha"),
            (0, "")
        )
        self.assertEqual(self.get_config_value("default_build", []), [])
        self.assertEqual(
            helper.run_rosrepo("include", "-w", self.wsdir, "alpha"),
            (0, "")
        )
        self.assertEqual(self.get_config_value("default_build"), ["alpha"])
        self.assertEqual(self.get_config_value("pinned_build"), [])
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.wsdir, "-n"),
            (0, "alpha\nbeta\ndelta\ngamma\n")
        )
        self.assertEqual(
            helper.run_rosrepo("include", "-w", self.wsdir, "--pinned", "beta"),
            (0, "")
        )
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.wsdir, "-n"),
            (0, "alpha\nbeta\ndelta\ngamma\n")
        )
        self.assertEqual(self.get_config_value("pinned_build"), ["beta"])
        self.assertEqual(
            helper.run_rosrepo("exclude", "-w", self.wsdir, "-a"),
            (0, "")
        )
        self.assertEqual(self.get_config_value("default_build"), [])
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.wsdir, "-n"),
            (0, "beta\ndelta\n")
        )
        self.assertEqual(
            helper.run_rosrepo("include", "-w", self.wsdir, "--default", "beta"),
            (0, "")
        )
        self.assertEqual(
            helper.run_rosrepo("exclude", "-w", self.wsdir, "--pinned", "beta"),
            (0, "")
        )
        self.assertEqual(self.get_config_value("default_build"), ["beta"])
        self.assertEqual(self.get_config_value("pinned_build"), [])
        self.assertEqual(
            helper.run_rosrepo("include", "-w", self.wsdir, "--pinned", "epsilon")[0],
            1
        )
        self.assertEqual(
            helper.run_rosrepo("include", "-w", self.wsdir, "--default", "epsilon")[0],
            1
        )
        self.assertEqual(
            helper.run_rosrepo("include", "-w", self.wsdir, "--default", "--all")[0],
            1
        )
        self.assertEqual(self.get_config_value("default_build"), ["beta"])
        self.assertEqual(self.get_config_value("pinned_build"), [])
        self.assertEqual(
            helper.run_rosrepo("init", "--reset", "-r", self.ros_root_dir, self.wsdir),
            (0, "")
        )
        self.assertEqual(self.get_config_value("default_build", []), [])
        self.assertEqual(self.get_config_value("pinned_build", []), [])

    def test_config(self):
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir),
            (0, "")
        )
        #######################
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--job-limit", "16")[0],
            0
        )
        self.assertEqual(self.get_config_value("job_limit"), 16)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--job-limit", "0")[0],
            0
        )
        self.assertEqual(self.get_config_value("job_limit"), None)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--job-limit", "8")[0],
            0
        )
        self.assertEqual(self.get_config_value("job_limit"), 8)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--no-job-limit")[0],
            0
        )
        self.assertEqual(self.get_config_value("job_limit"), None)
        #######################
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--install")[0],
            0
        )
        self.assertEqual(self.get_config_value("install"), True)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--no-install")[0],
            0
        )
        self.assertEqual(self.get_config_value("install"), False)
        #######################
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--set-compiler", "clang")[0],
            0
        )
        self.assertEqual(self.get_config_value("compiler"), "clang")
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--set-compiler", "does_not_exist")[0],
            1
        )
        self.assertEqual(self.get_config_value("compiler"), "clang")
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--unset-compiler")[0],
            0
        )
        self.assertEqual(self.get_config_value("compiler"), None)
        #######################
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost", "--store-credentials")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost", "private_token": "usertoken"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost", "--private-token", "t0ps3cr3t", "--store-credentials")[0],
            0
        )
        self.assertEqual(self.get_config_value("store_credentials"), True)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--no-store-credentials")[0],
            0
        )
        self.assertEqual(self.get_config_value("store_credentials"), False)
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost", "private_token": "t0ps3cr3t"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost", "--private-token", "t0ps3cr3t")[0],
            0
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost", "private_token": "t0ps3cr3t"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--get-gitlab-url", "does_not_exist"),
            (0, "\n")
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--get-gitlab-url", "Test"),
            (0, "http://localhost\n")
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--show-gitlab-urls", "--autocomplete"),
            (0, "Test\n")
        )
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--show-gitlab-urls")
        self.assertEqual(exitcode, 0)
        self.assertIn("Test", stdout)
        self.assertIn("http://localhost", stdout)
        self.assertIn("yes", stdout)

        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--gitlab-logout", "does_not_exist")[0],
            1
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--gitlab-logout", "Test")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost", "--private-token", "t0ps3cr3t")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--unset-gitlab-url", "Test")[0],
            0
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--show-gitlab-urls", "--autocomplete"),
            (0, "\n")
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost", "--private-token", "t0ps3cr3t")[0],
            0
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--gitlab-login", "Test", "--private-token", "t0ps3cr3t")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost", "--private-token", "t0ps3cr3t", "--store-credentials")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost", "private_token": "t0ps3cr3t"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--remove-credentials")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--gitlab-login", "Test", "--private-token", "t0ps3cr3t")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost", "private_token": "t0ps3cr3t"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--gitlab-login", "Test")[0],
            0
        )
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost", "private_token": "usertoken"}])
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--offline", "--set-gitlab-url", "Test", "http://localhost")[0],
            1
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--offline", "--gitlab-login", "Test")[0],
            1
        )
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--unset-gitlab-url", "Test")[0],
            0
        )
        cfg = Config(self.wsdir)
        cfg["gitlab_servers"] = [{"label": "NoURL"}]
        cfg.write()
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--gitlab-login", "NoURL")[0],
            1
        )        
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--gitlab-login", "does_not_exist")[0],
            1
        )        
        #######################
        self.assertEqual(self.get_config_value("ros_root"), self.ros_root_dir)
        helper.run_rosrepo("config", "-w", self.wsdir, "--unset-ros-root")
        self.assertEqual(self.get_config_value("ros_root"), None)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--set-ros-root", self.ros_root_dir)[0],
            0
        )
        self.assertEqual(self.get_config_value("ros_root"), self.ros_root_dir)
        #######################
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--no-catkin-lint")[0],
            0
        )
        self.assertEqual(self.get_config_value("use_catkin_lint"), False)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--catkin-lint")[0],
            0
        )
        self.assertEqual(self.get_config_value("use_catkin_lint"), True)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--no-catkin-lint")[0],
            0
        )
        self.assertEqual(self.get_config_value("use_catkin_lint"), False)
        #######################
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--no-rosclipse")[0],
            0
        )
        self.assertEqual(self.get_config_value("use_rosclipse"), False)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--rosclipse")[0],
            0
        )
        self.assertEqual(self.get_config_value("use_rosclipse"), True)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--no-rosclipse")[0],
            0
        )
        self.assertEqual(self.get_config_value("use_rosclipse"), False)

    def test_init_failures(self):
        self.assertEqual(
            helper.run_rosrepo("init", self.wsdir)[0],
            1
        )
        os.environ["HOME"] = self.wsdir
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir)[0],
            1
        )
        self.assertEqual(
            helper.run_rosrepo("init", "-r", self.ros_root_dir, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))[0],
            1
        )
