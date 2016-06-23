"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import re

COMPILER_LIST = [
    [r"gcc|gnu","gcc","g++"],
    [r"intel|icc|icpc","icc","icpc"],
    [r"clang","clang","clang++"],
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


def get_c_compiler(s):
    global COMPILER_LIST
    for compiler in COMPILER_LIST:
        m = re.match(r"^(.*)\b(?:%s)\b(.*)$" % compiler[0], s, re.IGNORECASE)
        if m is not None: return "%s%s%s" % (m.group(1), compiler[1], m.group(2))
    return None


def get_cxx_compiler(s):
    global COMPILER_LIST
    for compiler in COMPILER_LIST:
        m = re.match(r"^(.*)\b(?:%s)\b(.*)$" % compiler[0], s, re.IGNORECASE)
        if m is not None: return "%s%s%s" % (m.group(1), compiler[2], m.group(2))
    return None


# This class is only needed to migrate rosrepo 2.x pickles
class PkgInfo:
    path = None
    manifest = None
    active = False
    selected = False
    pinned = False
