"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import os
import fcntl
import termios
import struct
from tempfile import mkstemp
from subprocess import Popen, PIPE


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


def makedirs(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def write_atomic(filepath, data, mode=0644, ignore_fail=False):
    try:
        fd, filepath_tmp = mkstemp(prefix=os.path.basename(filepath) + ".tmp.", dir=os.path.dirname(filepath))
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        try:
            os.rename(filepath_tmp, filepath)
        except OSError:
            try:
                os.unlink(filepath)
            except OSError:
                pass
            try:
                os.rename(filepath_tmp, filepath)
            except OSError:
                os.unlink(filepath_tmp)
                if not ignore_fail:
                    raise
    except (IOError, OSError):
        if not ignore_fail:
            raise


def get_terminal_size(fd):
    try:
        cr = struct.unpack('hh', fcntl.ioctl(fd.fileno(), termios.TIOCGWINSZ, '1234'))
    except (IOError, struct.error):
        raise OSError("Cannot determine terminal size")
    return int(cr[1]), int(cr[0])


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
        stdoutdata, stderrdata = p.communicate(input_data)
        return p.returncode, stdoutdata, stderrdata
    else:
        p.wait()
    return p.returncode
