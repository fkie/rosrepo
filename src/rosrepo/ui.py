"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import sys
from getpass import getpass
import textwrap
from itertools import chain
from .util import get_terminal_size
from .terminal_color import fmt as color_fmt

terminal_width = {}
try:
    terminal_width[sys.stdout.fileno()] = get_terminal_size(sys.stdout)
except OSError:
    terminal_width[sys.stdout.fileno()] = None
try:
    terminal_width[sys.stderr.fileno()] = get_terminal_size(sys.stderr)
except OSError:
    terminal_width[sys.stderr.fileno()] = None


def msg(text, max_width=None, wrap=True, fd=sys.stdout, initial_indent="", subsequent_indent=""):
    lines = text.split("\n")
    if wrap:
        try:
            if max_width is None:
                max_width, _ = terminal_width.get(fd.fileno(), get_terminal_size(fd))
        except OSError:
            pass
        if max_width is not None:
            lines = [textwrap.fill(line, width=max_width, initial_indent=initial_indent, subsequent_indent=subsequent_indent) for line in lines]
    fd.write(color_fmt("\n".join(lines), use_color=fd.isatty()))


def error(text):
    msg ("@!@{rf}%s: error: %s\n" % (sys.argv[0], text), fd=sys.stderr, subsequent_indent=" " * (len(sys.argv[0]) + 9))


def warning(text):
    msg ("@!@{yf}%s: warning: %s\n" % (sys.argv[0], text), fd=sys.stderr, subsequent_indent=" " * (len(sys.argv[0]) + 11))


def get_credentials(domain):
    msg("@!Authentication required for @{cf}%s\n" % domain, fd=sys.stderr)
    while True:
        login = raw_input("Username: ")
        if login == "": continue
        passwd = getpass("Password: ")
        if passwd == "":
            msg("Starting over\n\n")
            continue
        return login, passwd


class TableView(object):
    def __init__(self, *args):
        self.columns = args
        self.width = [len(c) for c in self.columns]
        self.rows = []

    def add_row(self, *args):
        row = [r if isinstance(r, list) or isinstance(r,tuple) else (r,) for r in args]
        self.rows.append(row)
        self.width = [max(w, *(len(r) for r in rs)) for w,rs in zip(self.width, row)]

    def empty(self):
        return len(self.rows) == 0

    def sort(self, column_index):
        self.rows.sort(key=lambda x: x[column_index])

    def _chunk(self, text, width):
        return tuple(text[i:width+i] for i in range(0, len(text), width))

    def write(self, fd=sys.stdout):
        width = self.width
        actual_width = sum(width) + 3 * len(width) - 1
        use_color = fd.isatty()
        if fd.isatty():
            try:
                total_width = terminal_width.get(fd.fileno(), get_terminal_size(fd))[0] - 1
            except OSError:
                total_width = 79
        else:
            total_width = None
        if total_width is not None:
            while actual_width > total_width:
                max_width = max(width)
                width = [min(max_width - 1, w) for w in width]
                actual_width = sum(width) + 3 * len(width) + 1
        fmt = " "+" @{pf}|@| ".join(["%%s%%-%ds%%s" % w for w in (width)]) + "\n"
        sep = "@{pf}-" + "-+-".join(["-" * w for w in width]) + "-\n"
        fd.write(color_fmt(sep, use_color=use_color))
        fd.write(color_fmt(fmt % tuple(chain(*(("@!", r[:w], "@|") for r, w in zip(self.columns, width)))), use_color=use_color))
        fd.write(color_fmt(sep, use_color=use_color))
        for row in self.rows:
            for line in map(None, *row):
                chunks = (self._chunk(r if r is not None else "", w) for r,w in zip(line, width))
                for chunk in map(None, *chunks):
                    fd.write(color_fmt(fmt % tuple(chain(*(("", r[:w] if r is not None else "", "") for r, w in zip(chunk, width)))), use_color=use_color))
        fd.write(color_fmt(sep, use_color=use_color))
