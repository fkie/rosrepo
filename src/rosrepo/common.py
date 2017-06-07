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
import re
import os
from .util import makedirs


COMPILER_LIST = [
    [r"gcc|gnu", "gcc", "g++"],
    [r"intel|icc|icpc", "icc", "icpc"],
    [r"clang", "clang", "clang++"],
]


DEFAULT_CMAKE_ARGS = [
    "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
    "-DCMAKE_CXX_FLAGS=-Wall -Wextra -Wno-ignored-qualifiers -Wno-invalid-offsetof -Wno-unused-parameter -fno-omit-frame-pointer",
    "-DCMAKE_CXX_FLAGS_RELWITHDEBINFO=-O2 -g",
    "-DCMAKE_C_FLAGS=-Wall -Wextra -Wno-unused-parameter -fno-omit-frame-pointer",
    "-DCMAKE_C_FLAGS_RELWITHDEBINFO=-O2 -g",
    "-DCMAKE_SHARED_LINKER_FLAGS=-Wl,-z,defs",
    "-DCMAKE_EXE_LINKER_FLAGS=-Wl,-z,defs"
]

DEFAULT_GIT_IGNORE = set([
    "*.egg-info/",
    "__pycache__/",
    ".project",
    ".cproject",
    ".pydevproject",
    ".settings/",
    "CATKIN_IGNORE",
    ".catkin_tools/",
    ".rosrepo/",
    ".catkin_workspace",
    ".catkin",
    ".coverage",
    ".*.swp",
    "*~",
    "*.bak",
    "*.orig",
    "*.py[cdo]",
    "*.o",
    "lib*.a",
    "lib*.so",
    "lib*.so.*",
    "*.bag",
])


def update_default_git_ignore():
    config_home = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    gitconfig_dir = os.path.join(config_home, "git")
    gitignore_file = os.path.join(gitconfig_dir, "ignore")
    gitignore = set()
    try:
        with open(gitignore_file, "r") as f:
            gitignore = set([e for e in f.read().split("\n") if e])
    except IOError:
        pass
    if not DEFAULT_GIT_IGNORE.issubset(gitignore):
        gitignore |= set(DEFAULT_GIT_IGNORE)
        try:
            makedirs(gitconfig_dir)
            with open(gitignore_file, "w") as f:
                f.write("\n".join(sorted(list(gitignore))))
        except (OSError, IOError):
            pass


def get_c_compiler(s):
    global COMPILER_LIST
    for compiler in COMPILER_LIST:
        m = re.match(r"^(.*)\b(?:%s)\b(.*)$" % compiler[0], s, re.IGNORECASE)
        if m is not None:
            return "%s%s%s" % (m.group(1), compiler[1], m.group(2))
    return None


def get_cxx_compiler(s):
    global COMPILER_LIST
    for compiler in COMPILER_LIST:
        m = re.match(r"^(.*)\b(?:%s)\b(.*)$" % compiler[0], s, re.IGNORECASE)
        if m is not None:
            return "%s%s%s" % (m.group(1), compiler[2], m.group(2))
    return None


# This class is only needed to migrate rosrepo 2.x pickles
class PkgInfo:
    path = None
    manifest = None
    active = False
    selected = False
    pinned = False
