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
import fcntl
import termios
import struct
import multiprocessing
import signal
from tempfile import mkstemp
from subprocess import Popen, PIPE

from yaml import load as yaml_load_impl, dump as yaml_dump_impl, YAMLError
try:
    from yaml import CSafeLoader as SafeLoader, CSafeDumper as SafeDumper
except ImportError:
    from yaml import SafeLoader, SafeDumper


def yaml_load(stream, Loader=SafeLoader):
    return yaml_load_impl(stream, Loader=Loader)


def yaml_dump(data, stream=None, Dumper=SafeDumper, **kwargs):
    return yaml_dump_impl(data, stream=stream, Dumper=Dumper, **kwargs)


class NamedTuple(object):
    __slots__ = ()

    def __init__(self, *args, **kwargs):
        slots = self.__slots__
        for k in slots:
            setattr(self, k, kwargs.get(k))
        if args:
            for k, v in zip(slots, args):
                setattr(self, k, v)

    def __str__(self):
        clsname = self.__class__.__name__
        values = ", ".join("%s=%r" % (k, getattr(self, k)) for k in self.__slots__)
        return "%s(%s)" % (clsname, values)
    __repr__ = __str__

    def __getitem__(self, item):
        return getattr(self, self.__slots__[item])

    def __setitem__(self, item, value):
        return setattr(self, self.__slots__[item], value)

    def __len__(self):
        return len(self.__slots__)


try:
    iteritems = dict.iteritems
except AttributeError:
    iteritems = dict.items


class UserError(RuntimeError):
    pass


def is_deprecated_package(manifest):
    deprecated = next((e for e in manifest.exports if e.tagname == "deprecated"), None)
    return deprecated is not None


def deprecated_package_info(manifest):
    deprecated = next((e for e in manifest.exports if e.tagname == "deprecated"), None)
    return deprecated.content if deprecated is not None else None


def path_has_prefix(path, prefix):
    p = os.path.normpath(path)
    q = os.path.normpath(prefix)
    if p == q:
        return True
    head, tail = os.path.split(p)
    while tail != "":
        if head == q:
            return True
        head, tail = os.path.split(head)
    return False


def has_package_path(obj, paths):
    for path in paths:
        if path_has_prefix(path, obj.workspace_path if hasattr(obj, "workspace_path") else obj):
            return True
    return False


def env_path_list_contains(path_list, path):
    if path_list not in os.environ:
        return False
    paths = os.environ[path_list].split(os.pathsep)
    return path in paths


def makedirs(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def write_atomic(filepath, data, mode=0o644, ignore_fail=False):
    try:
        fd, filepath_tmp = mkstemp(prefix=os.path.basename(filepath) + ".tmp.", dir=os.path.dirname(filepath))
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.rename(filepath_tmp, filepath)
    except (IOError, OSError):
        if not ignore_fail:
            raise


def isatty(fd):
    return hasattr(fd, "isatty") and fd.isatty()


_cached_terminal_size = None


def get_terminal_size():
    global _cached_terminal_size
    if _cached_terminal_size is not None:
        return _cached_terminal_size
    try:
        with open(os.ctermid(), "rb") as f:
            cr = struct.unpack('hh', fcntl.ioctl(f.fileno(), termios.TIOCGWINSZ, '1234'))
    except (IOError, struct.error):
        raise OSError("Cannot determine terminal size")
    _cached_terminal_size = int(cr[1]), int(cr[0])
    return _cached_terminal_size


def find_program(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            fpath = path.strip('"')
            candidate = os.path.join(fpath, fname)
            if is_exe(candidate):
                return candidate
    return None


def getmtime(path):
    return os.path.getmtime(path) if os.path.exists(path) else 0


def call_process(args, bufsize=0, stdin=None, stdout=None, stderr=None, cwd=None, env=None, input_data=None):
    p = Popen(args, bufsize=bufsize, stdin=stdin, stdout=stdout, stderr=stderr, cwd=cwd, env=env)
    if stdin == PIPE or stdout == PIPE or stderr == PIPE:
        stdoutdata, stderrdata = p.communicate(input_data.encode("UTF-8") if input_data else None)
        return p.returncode, stdoutdata.decode("UTF-8") if stdoutdata is not None else None, stderrdata.decode("UTF-8") if stderrdata is not None else None
    else:
        p.wait()
    return p.returncode


def create_multiprocess_manager():
    return multiprocessing.Manager()


def _worker_init(worker_init, worker_init_args):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if worker_init is not None:
        worker_init(*worker_init_args)


def run_multiprocess_workers(worker, workload, worker_init=None, worker_init_args=(), jobs=None, timeout=None):
    if not workload:
        return []
    if timeout is None:
        timeout = 999999999  # Workaround for KeyboardInterrupt
    pool = multiprocessing.Pool(processes=jobs, initializer=_worker_init, initargs=(worker_init, worker_init_args))
    try:
        result_obj = pool.map_async(worker, workload)
        pool.close()
        result = result_obj.get(timeout=timeout)
        return result
    except:
        pool.terminate()
        raise
    finally:
        pool.join()
