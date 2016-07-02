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
import argparse
try:
    import mock
except ImportError:
    import unittest.mock as mock
import sys
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
from rosrepo.main import prepare_arguments, run_rosrepo as run_rosrepo_impl
from rosrepo.util import call_process as real_call_process


def create_fake_ros_root(rosdir):
    for subdir in ["bin", "etc", "include", "lib", "share"]:
        os.makedirs(os.path.join(rosdir, subdir))
    with open(os.path.join(rosdir, ".catkin"), "w") as f:
        pass
    with open(os.path.join(rosdir, "setup.sh"), "w") as f:
        f.write(
            "#!/bin/sh\n"
            "export ROS_PACKAGE_PATH=%(dir)s\n"
            "export CMAKE_PREFIX_PATH=%(dir)s\n"
            % {"dir": rosdir}
        )
    with open(os.path.join(rosdir, "env.sh"), "w") as f:
        f.write(
            "#!/bin/sh\n"
            ". '%(dir)s/setup.sh'\n"
            'exec "$@"\n'
            % {"dir": rosdir}
        )
    os.chmod(os.path.join(rosdir, "env.sh"), 0o755)


def create_package(wsdir, name, depends):
    pkgdir = os.path.join(wsdir, "src", name)
    if not os.path.isdir(pkgdir):
        os.makedirs(pkgdir)
    with open(os.path.join(pkgdir, "package.xml"), "w") as f:
        f.write(
            '<package format="2"><name>%s</name><version>0.0.0</version>'
            '<description>Mock package</description>'
            '<maintainer email="mock@example.com">Mister Mock</maintainer>'
            '<license>none</license>' % name
        )
        f.write(''.join(['<depend>%s</depend>' % dep for dep in depends]))
        f.write('</package>\n')


def call_process(*args, **kwargs):
    with open(os.devnull, "w") as devnull:
        if "stdout" not in kwargs:
            kwargs["stdout"] = devnull
        if "stderr" not in kwargs:
            kwargs["stderr"] = devnull
        return real_call_process(*args, **kwargs)


@mock.patch("rosrepo.cmd_config.call_process", call_process)
def run_rosrepo(*argv):
    parser = prepare_arguments(argparse.ArgumentParser())
    args = parser.parse_args(argv)
    stdout = StringIO()
    with mock.patch("sys.stdout", stdout):
        with mock.patch("sys.stderr", stdout):
            returncode =  run_rosrepo_impl(args)
    return returncode, stdout.getvalue()
