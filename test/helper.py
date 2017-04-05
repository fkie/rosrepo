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
from rosrepo.util import call_process as real_call_process, PIPE

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


def create_package(wsdir, name, depends, deprecated=False):
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
        f.write('<export>')
        if deprecated:
            if isinstance(deprecated, str):
                f.write('<deprecated>%s</deprecated>' % deprecated)
            else:
                f.write('<deprecated/>')
        f.write('</export>')
        f.write('</package>\n')


def call_process(*args, **kwargs):
    redirected = False
    if "stdout" not in kwargs and "stderr" not in kwargs:
        kwargs["stdout"] = PIPE
        kwargs["stderr"] = PIPE
        redirected = True
    exitcode, stdout, stderr = real_call_process(*args, **kwargs)
    if redirected:
        sys.stdout.write(stdout)
        sys.stderr.write(stderr)
        return exitcode
    return exitcode, stdout, stderr


failing_programs = []


def no_call_process(args, **kwargs):
    global failing_programs
    exitcode = 1 if args[0] in failing_programs else 0
    return (exitcode, "", "") if kwargs.get("stdin") == PIPE or kwargs.get("stdout") == PIPE or kwargs.get("stderr") == PIPE else exitcode


def find_program(arg):
    return arg


def fake_acquire_user_token(label, url):
    return "usertoken"


class FakeRosdep(object):

    def __contains__(self, key):
        return "system" in key

    def resolve(self, key):
        if "system" in key:
            return "apt", [key]
        else:
            raise KeyError()

    def ok(self):
        return True


class FakeResponse(object):
    def __init__(self, _status_code):
        self.status_code = _status_code


class FakeSystemPackageManager(object):

    @property
    def installer_cmd(self):
        return "apt-get install"

    @property
    def installer(self):
        return "apt"

    @property
    def installed_packages(self):
        return set(["installed-system"])


def fake_requests_get(*args, **kwargs):
    return FakeResponse(401)


@mock.patch("rosrepo.resolver._rosdep_instance", FakeRosdep())
@mock.patch("rosrepo.resolver._system_package_manager", FakeSystemPackageManager())
@mock.patch("rosrepo.cmd_build.call_process", no_call_process)
@mock.patch("rosrepo.cmd_build.find_program", find_program)
@mock.patch("requests.get", fake_requests_get)
@mock.patch("rosrepo.cmd_config.acquire_gitlab_private_token", fake_acquire_user_token)
@mock.patch("rosrepo.cmd_config.call_process", call_process)
@mock.patch("rosrepo.cmd_clean.call_process", call_process)
@mock.patch("rosrepo.util._cached_terminal_size", (80,24))
def run_rosrepo(*argv):
    parser = prepare_arguments(argparse.ArgumentParser())
    args = parser.parse_args(argv)
    stdout = StringIO()
    with mock.patch("sys.stdout", stdout):
        with mock.patch("sys.stderr", stdout):
            returncode =  run_rosrepo_impl(args)
    return returncode, stdout.getvalue()
