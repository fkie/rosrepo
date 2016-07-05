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
        helper.create_package(self.wsdir, "alpha", ["beta", "gamma", "installed-system"])
        helper.create_package(self.wsdir, "beta", ["delta"])
        helper.create_package(self.wsdir, "gamma", [])
        helper.create_package(self.wsdir, "delta", [])
        helper.create_package(self.wsdir, "epsilon", ["broken"])
        helper.create_package(self.wsdir, "broken", ["missing"])
        helper.create_package(self.wsdir, "incomplete", ["missing-system"])
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
        exitcode, stdout = helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir)
        self.assertEqual(exitcode, 0)
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
        exitcode, stdout = helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir)
        self.assertEqual(exitcode, 0)
        os.makedirs(os.path.join(self.wsdir, "build"))
        exitcode, stdout = helper.run_rosrepo("clean", "-w", self.wsdir, "--dry-run")
        self.assertEqual(exitcode, 0)
        self.assertTrue(os.path.isdir(os.path.join(self.wsdir, "build")))
        exitcode, stdout = helper.run_rosrepo("clean", "-w", self.wsdir)
        self.assertEqual(exitcode, 0)
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
        exitcode, stdout = helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir)
        self.assertEqual(exitcode, 0)
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
        exitcode, stdout = helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir)
        self.assertEqual(exitcode, 0)
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.wsdir, "-n"),
            (0, "alpha\nbeta\ndelta\ngamma\n")
        )
        self.assertEqual(self.get_config_value("default_build"), ["alpha"])
        self.assertEqual(self.get_config_value("pinned_build"), ["beta"])

    def test_different_config_version(self):
        exitcode, stdout = helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir)
        self.assertEqual(exitcode, 0)
        exitcode, stdout = helper.run_rosrepo("include", "-w", self.wsdir, "alpha")
        self.assertEqual(exitcode, 0)
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
        exitcode, stdout = helper.run_rosrepo("list", "-w", self.wsdir, "-n")
        self.assertEqual(exitcode, 1)
        self.assertIn("newer version", stdout)

    def test_buildset(self):
        exitcode, stdout = helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir)
        self.assertEqual(exitcode, 0)
        exitcode, stdout = helper.run_rosrepo("include", "-w", self.wsdir, "--dry-run", "alpha")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("default_build", []), [])
        exitcode, stdout = helper.run_rosrepo("include", "-w", self.wsdir, "alpha")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("default_build"), ["alpha"])
        self.assertEqual(self.get_config_value("pinned_build"), [])
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.wsdir, "-n"),
            (0, "alpha\nbeta\ndelta\ngamma\n")
        )
        exitcode, stdout = helper.run_rosrepo("include", "-w", self.wsdir, "--pinned", "beta")
        self.assertEqual(exitcode, 0)
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.wsdir, "-n"),
            (0, "alpha\nbeta\ndelta\ngamma\n")
        )
        self.assertEqual(self.get_config_value("pinned_build"), ["beta"])
        exitcode, stdout = helper.run_rosrepo("exclude", "-w", self.wsdir, "-a")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("default_build"), [])
        self.assertEqual(
            helper.run_rosrepo("list", "-w", self.wsdir, "-n"),
            (0, "beta\ndelta\n")
        )
        exitcode, stdout = helper.run_rosrepo("include", "-w", self.wsdir, "--default", "beta")
        self.assertEqual(exitcode, 0)
        exitcode, stdout = helper.run_rosrepo("exclude", "-w", self.wsdir, "--pinned", "beta")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("default_build"), ["beta"])
        self.assertEqual(self.get_config_value("pinned_build"), [])
        exitcode, stdout = helper.run_rosrepo("include", "-w", self.wsdir, "--pinned", "epsilon")
        self.assertEqual(exitcode, 1)
        self.assertIn("cannot resolve dependencies", stdout)
        exitcode, stdout = helper.run_rosrepo("include", "-w", self.wsdir, "--default", "epsilon")
        self.assertEqual(exitcode, 1)
        self.assertIn("cannot resolve dependencies", stdout)
        exitcode, stdout = helper.run_rosrepo("include", "-w", self.wsdir, "--default", "--all")
        self.assertEqual(exitcode, 1)
        self.assertIn("cannot resolve dependencies", stdout)
        self.assertEqual(self.get_config_value("default_build"), ["beta"])
        self.assertEqual(self.get_config_value("pinned_build"), [])
        exitcode, stdout = helper.run_rosrepo("include", "-w", self.wsdir, "--default", "incomplete")
        self.assertEqual(exitcode, 0)
        self.assertIn("apt-get install", stdout)
        os.makedirs(os.path.join(self.wsdir, "build"))
        exitcode, stdout = helper.run_rosrepo("init", "--reset", "-r", self.ros_root_dir, self.wsdir)
        self.assertEqual(exitcode, 0)
        self.assertFalse(os.path.isdir(os.path.join(self.wsdir, "build")))
        self.assertEqual(self.get_config_value("default_build", []), [])
        self.assertEqual(self.get_config_value("pinned_build", []), [])

    def test_build(self):
        exitcode, stdout = helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir)
        self.assertEqual(exitcode, 0)
        exitcode, stdout = helper.run_rosrepo("build", "-w", self.wsdir, "--dry-run")
        self.assertEqual(exitcode, 1)
        self.assertIn("no packages to build", stdout)
        helper.failing_programs = ["catkin_lint"]
        exitcode, stdout = helper.run_rosrepo("build", "-w", self.wsdir, "--dry-run", "alpha")
        self.assertEqual(exitcode, 0)
        self.assertIn("alpha", stdout)
        self.assertIn("beta", stdout)
        self.assertIn("gamma", stdout)
        self.assertIn("delta", stdout)        
        exitcode, stdout = helper.run_rosrepo("build", "-w", self.wsdir, "alpha")
        self.assertEqual(exitcode, 1)
        self.assertIn("catkin_lint reported errors", stdout)
        helper.failing_programs = []        
        exitcode, stdout = helper.run_rosrepo("build", "-w", self.wsdir, "--all")
        self.assertEqual(exitcode, 1)
        self.assertIn("cannot resolve dependencies", stdout)        
        exitcode, stdout = helper.run_rosrepo("build", "-w", self.wsdir, "--set-default")
        self.assertEqual(exitcode, 1)
        self.assertIn("no packages given", stdout)        
        exitcode, stdout = helper.run_rosrepo("build", "-w", self.wsdir, "--set-default", "alpha")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("default_build", []), ["alpha"])
        exitcode, stdout = helper.run_rosrepo("build", "-w", self.wsdir, "--set-pinned")
        self.assertEqual(exitcode, 1)
        self.assertIn("no packages given", stdout)        
        exitcode, stdout = helper.run_rosrepo("build", "-w", self.wsdir, "--set-pinned", "beta")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("pinned_build", []), ["beta"])
        exitcode, stdout = helper.run_rosrepo("build", "-w", self.wsdir)
        self.assertEqual(exitcode, 0)
        self.assertIn("alpha", stdout)
        self.assertIn("beta", stdout)
        self.assertIn("gamma", stdout)
        self.assertIn("delta", stdout)        
        exitcode, stdout = helper.run_rosrepo("exclude", "-w", self.wsdir, "--all")
        self.assertEqual(exitcode, 0)
        exitcode, stdout = helper.run_rosrepo("build", "-w", self.wsdir)
        self.assertEqual(exitcode, 0)
        self.assertNotIn("alpha", stdout)
        self.assertNotIn("gamma", stdout)
        self.assertIn("beta", stdout)
        self.assertIn("delta", stdout)
        exitcode, stdout = helper.run_rosrepo("build", "-w", self.wsdir, "incomplete")
        self.assertEqual(exitcode, 1)
        self.assertIn("missing system package", stdout)
        exitcode, stdout = helper.run_rosrepo("build", "-w", self.wsdir, "--clean")
        self.assertEqual(exitcode, 0)
        exitcode, stdout = helper.run_rosrepo("build", "-w", self.wsdir, "--clean", "--dry-run", "--offline", "--verbose", "--no-status", "--keep-going", "-j2")
        self.assertEqual(exitcode, 0)

    def test_list(self):
        exitcode, stdout = helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir)
        self.assertEqual(exitcode, 0)
        exitcode, stdout = helper.run_rosrepo("include", "-w", self.wsdir, "alpha")
        self.assertEqual(exitcode, 0)
        exitcode, stdout = helper.run_rosrepo("include", "-w", self.wsdir, "--pinned", "beta")
        self.assertEqual(exitcode, 0)
        exitcode, stdout = helper.run_rosrepo("list", "-w", self.wsdir)
        self.assertEqual(exitcode, 0)
        self.assertIn("alpha", stdout)
        self.assertIn("beta", stdout)
        self.assertIn("gamma", stdout)
        self.assertIn("delta", stdout)
        self.assertNotIn("epsilon", stdout)
        exitcode, stdout = helper.run_rosrepo("list", "-w", self.wsdir, "-BC")
        self.assertEqual(exitcode, 0)
        self.assertIn("search filter", stdout)
        exitcode, stdout = helper.run_rosrepo("list", "-w", self.wsdir, "-S")
        self.assertEqual(exitcode, 0)
        self.assertIn("alpha", stdout)
        self.assertNotIn("beta", stdout)
        exitcode, stdout = helper.run_rosrepo("list", "-w", self.wsdir, "-P")
        self.assertEqual(exitcode, 0)
        self.assertNotIn("alpha", stdout)
        self.assertIn("beta", stdout)
        self.assertNotIn("delta", stdout)
        exitcode, stdout = helper.run_rosrepo("list", "-w", self.wsdir, "-Pv")
        self.assertEqual(exitcode, 0)
        self.assertIn("alpha", stdout)
        self.assertNotIn("beta", stdout)
        self.assertIn("delta", stdout)
        exitcode, stdout = helper.run_rosrepo("list", "-w", self.wsdir, "-PD")
        self.assertEqual(exitcode, 0)
        self.assertNotIn("alpha", stdout)
        self.assertIn("beta", stdout)
        self.assertIn("delta", stdout)
        exitcode, stdout = helper.run_rosrepo("list", "-w", self.wsdir, "-W")
        self.assertIn("alpha", stdout)
        self.assertIn("beta", stdout)
        self.assertIn("epsilon", stdout)

    def test_config(self):
        exitcode, stdout = helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir)
        self.assertEqual(exitcode, 0)
        #######################
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--job-limit", "16")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("job_limit"), 16)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--job-limit", "0")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("job_limit"), None)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--job-limit", "8")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("job_limit"), 8)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--no-job-limit")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("job_limit"), None)
        #######################
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--install")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("install"), True)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--no-install")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("install"), False)
        #######################
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--set-compiler", "clang")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("compiler"), "clang")
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--set-compiler", "does_not_exist")
        self.assertEqual(exitcode, 1)
        self.assertIn("unknown compiler", stdout)
        self.assertEqual(self.get_config_value("compiler"), "clang")
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--unset-compiler")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("compiler"), None)
        #######################
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost", "--store-credentials")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost", "private_token": "usertoken"}])
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost", "--private-token", "t0ps3cr3t", "--store-credentials")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("store_credentials"), True)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--no-store-credentials")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("store_credentials"), False)
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost", "private_token": "t0ps3cr3t"}])
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost", "--private-token", "t0ps3cr3t")
        self.assertEqual(exitcode, 0)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost")
        self.assertEqual(exitcode, 0)
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

        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--gitlab-logout", "does_not_exist")
        self.assertEqual(exitcode, 1)
        self.assertIn("no such Gitlab server", stdout)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--gitlab-logout", "Test")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost"}])
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost", "--private-token", "t0ps3cr3t")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost"}])
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost"}])
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--unset-gitlab-url", "Test")
        self.assertEqual(exitcode, 0)
        self.assertEqual(
            helper.run_rosrepo("config", "-w", self.wsdir, "--show-gitlab-urls", "--autocomplete"),
            (0, "\n")
        )
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost", "--private-token", "t0ps3cr3t")
        self.assertEqual(exitcode, 0)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--gitlab-login", "Test", "--private-token", "t0ps3cr3t")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost"}])
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--set-gitlab-url", "Test", "http://localhost", "--private-token", "t0ps3cr3t", "--store-credentials")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost", "private_token": "t0ps3cr3t"}])
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--remove-credentials")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost"}])
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--gitlab-login", "Test", "--private-token", "t0ps3cr3t")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost", "private_token": "t0ps3cr3t"}])
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--gitlab-login", "Test")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("gitlab_servers"), [{"label": "Test", "url": "http://localhost", "private_token": "usertoken"}])
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--offline", "--set-gitlab-url", "Test", "http://localhost")
        self.assertEqual(exitcode, 1)
        self.assertIn("cannot acquire Gitlab private token in offline mode", stdout)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--offline", "--gitlab-login", "Test")
        self.assertEqual(exitcode, 1)
        self.assertIn("cannot acquire Gitlab private token in offline mode", stdout)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--unset-gitlab-url", "Test")
        self.assertEqual(exitcode, 0)
        cfg = Config(self.wsdir)
        cfg["gitlab_servers"] = [{"label": "NoURL"}]
        cfg.write()
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--gitlab-login", "NoURL")
        self.assertEqual(exitcode, 1)
        self.assertIn("cannot acquire token for Gitlab server without URL", stdout)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--gitlab-login", "does_not_exist")
        self.assertEqual(exitcode, 1)
        self.assertIn("no such Gitlab server", stdout)
        #######################
        self.assertEqual(self.get_config_value("ros_root"), self.ros_root_dir)
        helper.run_rosrepo("config", "-w", self.wsdir, "--unset-ros-root")
        self.assertEqual(self.get_config_value("ros_root"), None)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--set-ros-root", self.ros_root_dir)
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("ros_root"), self.ros_root_dir)
        #######################
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--no-catkin-lint")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("use_catkin_lint"), False)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--catkin-lint")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("use_catkin_lint"), True)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--no-catkin-lint")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("use_catkin_lint"), False)
        #######################
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--no-rosclipse")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("use_rosclipse"), False)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--rosclipse")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("use_rosclipse"), True)
        exitcode, stdout = helper.run_rosrepo("config", "-w", self.wsdir, "--no-rosclipse")
        self.assertEqual(exitcode, 0)
        self.assertEqual(self.get_config_value("use_rosclipse"), False)

    def test_init_failures(self):
        os.environ["HOME"] = self.wsdir
        exitcode, stdout = helper.run_rosrepo("init", "-r", self.ros_root_dir, self.wsdir)
        self.assertEqual(exitcode, 1)
        self.assertIn("$HOME", stdout)
        exitcode, stdout = helper.run_rosrepo("init", "-r", self.ros_root_dir, os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir)))
        self.assertEqual(exitcode, 1)
        self.assertIn("rosrepo source folder", stdout)
