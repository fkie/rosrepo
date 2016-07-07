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
import sys
from getpass import getpass
import re
try:
    from itertools import izip_longest as zip_longest
except ImportError:
    from itertools import zip_longest
from .util import isatty, get_terminal_size, UserError
from .terminal_color import fmt as color_fmt


_ansi_escape = re.compile(r"\x1b[^m]*m")


def remove_ansi(text):
    global _ansi_escape
    return _ansi_escape.sub("", text)


def printed_len(text):
    global _ansi_escape
    i = 0
    result = []
    matches = _ansi_escape.finditer(text)
    for m in matches:
        result += list(range(i, m.start()))
        i = m.end()
    result += list(range(i, len(text)))
    return result


def slice_ansi_text(text, chunk_size, fill=" ", pad=True):
    ll = printed_len(text)
    initial_ansi = text[:ll[0]] if ll else ""
    excess = len(ll) % chunk_size
    if pad and excess > 0:
        padded_text = text + fill[0] * (chunk_size - excess)
    else:
        padded_text = text
    return list(initial_ansi + padded_text[ll[i]:ll[chunk_size + i] if chunk_size + i < len(ll) else len(padded_text)] for i in range(0, len(ll), chunk_size))


def pad_ansi_text(text, width, truncate=True, fill=" "):
    l = printed_len(text)
    length = len(l)
    if width < length:
        return text[:l[width]] if truncate else text
    return text + fill[0] * (width - length)


def wrap_ansi_text(text, width, indent=0, indent_first=None, indent_next=None, suffix=""):
    if width is None:
        return text
    if indent_first is None:
        indent_first = indent
    if indent_next is None:
        indent_next = indent
    result = []
    chunks = text.split("\n")
    sl = len(suffix)
    skip_blank = False
    for chunk in chunks:
        count = indent_first
        line = []
        empty_paragraph = True
        if indent_first > 0:
            line.append(" " * (indent_first - 1))
        for word in chunk.split(" "):
            l = len(remove_ansi(word))
            if l != 0 or not skip_blank:
                if l != 0:
                    skip_blank = False
                    empty_paragraph = False
                if count + l <= width - sl:
                    line.append(word)
                    count += l + 1
                else:
                    result.append(" ".join(line))
                    line = []
                    count = indent_next
                    if indent_next > 0:
                        line.append(" " * (indent_next - 1))
                    if l == 0:
                        skip_blank = True
                    else:
                        line.append(word)
                        count += l + 1
        result.append("" if skip_blank or empty_paragraph else " ".join(line))
    return (suffix + "\n").join(result)


def reformat_paragraphs(text):
    paragraphs = re.split("[\r|\n]+\s*[\r|\n]+", text.strip())
    result = []
    for p in paragraphs:
        lines = [l.strip() for l in p.split("\n")]
        result.append(" ".join(lines))
    return "\n\n".join(result)


def escape(msg):
    return msg.replace("@", "@@")


def msg(text, max_width=None, use_color=None, wrap=True, fd=None, **wrap_args):
    from .terminal_color import ansi
    if fd is None:
        fd = sys.stderr
    if use_color is None:
        use_color = isatty(fd)
    ansi_text = color_fmt(text, use_color=use_color)
    if wrap:
        try:
            if max_width is None:
                max_width, _ = get_terminal_size()
        except OSError:
            pass
    fd.write(wrap_ansi_text(ansi_text, max_width, **wrap_args) + (ansi('reset') if use_color else ""))


def fatal(text):
    raise UserError(text)


def error(text, use_color=None):
    prog = "rosrepo"
    msg("@!@{rf}%s: error: %s" % (prog, text), indent_next=len(prog) + 9)


def warning(text, use_color=None):
    prog = "rosrepo"
    msg("@!@{yf}%s: warning: %s" % (prog, text), use_color=use_color, indent_next=len(prog) + 11)


def readline(prompt, fd=None):
    if fd is None:
        fd = sys.stderr
    fd.write(prompt)
    fd.flush()
    return sys.stdin.readline().rstrip("\r\n")


def get_credentials(domain):
    if not isatty(sys.stdin):
        fatal("Need TTY to query credentials\n")
    if isatty(sys.stderr):
        fd = sys.stderr
    elif isatty(sys.stdout):
        fd = sys.stdout
    else:
        fatal("Need TTY to query credentials\n")
    msg("\n@!Authentication required for @{cf}%s\n" % domain, fd=fd)
    while True:
        login = readline("Username: ", fd=fd)
        if login == "":
            continue
        passwd = getpass("Password: ")
        if passwd == "":
            msg("Starting over\n\n", fd=fd)
            continue
        return login, passwd


def pick_dependency_resolution(package_name, pkg_list):
    if not isatty(sys.stdin):
        return None
    if isatty(sys.stderr):
        fd = sys.stderr
    elif isatty(sys.stdout):
        fd = sys.stdout
    else:
        return None
    result = None
    while result is None:
        msg("\n@!Dependency resolution for @{cf}%s@|\n" % package_name, fd=fd)
        msg(
            "The package is not in your workspace and can be cloned from "
            "multiple Git repositories. Please pick the one you want:\n\n", fd=fd
        )
        for i in range(len(pkg_list)):
            msg("%3d. %s\n" % (i + 1, pkg_list[i].project.website), fd=fd)
        msg("%3d. %s\n\n" % (0, "Choose automatically"), fd=fd)
        try:
            s = int(readline("--> ", fd_out=fd))
            if s == 0:
                return None
            result = pkg_list[s - 1]
        except (ValueError, IndexError):
            msg("@!@{rf}Invalid choice@|\n\n", fd=fd)
    return result


def show_conflicts(conflicts):
    for name in sorted(conflicts.keys()):
        error("cannot use package '%s'\n" % escape(name))
        for reason in conflicts[name]:
            msg("   - %s\n" % reason, indent_next=5)


def show_missing_system_depends(missing):
    if missing:
        msg(
            "You need to install additional resources on this computer to satisfy all dependencies. "
            "Please run the following command:\n\n"
        )
        msg("@!sudo apt-get install " + " ".join(sorted(list(missing))), indent_first=4, indent_next=25, suffix=" \\")
        msg("\n\n")


class TableView(object):
    def __init__(self, *args, **kwargs):
        self.columns = args
        self.expand = kwargs.get("expand", False)
        if not self.columns:
            self.width = [1, 1]
        else:
            self.width = [max(1, len(remove_ansi(color_fmt(c)))) for c in self.columns]
        self.rows = []

    def add_row(self, *args):
        row = [r if isinstance(r, list) or isinstance(r, tuple) else (r,) for r in args]
        row = [r if isinstance(r, tuple) or len(r) > 0 else [""] for r in row]  # Handle special case with empty lists
        assert len(row) == len(self.width)
        self.rows.append(row)
        self.width = [max(w, *(len(remove_ansi(color_fmt(r))) for r in rs)) for w, rs in zip(self.width, row)]

    def add_separator(self):
        self.rows.append(None)

    def empty(self):
        return len(self.rows) == 0

    def sort(self, column_index):
        self.rows.sort(key=lambda x: x[column_index])

    def write(self, fd=None, use_color=None):
        width = self.width
        actual_width = sum(width) + 3 * len(width) - 1
        try:
            total_width = get_terminal_size()[0]
        except OSError:
            total_width = None
        if fd is None:
            fd = sys.stdout
        if use_color is None:
            use_color = isatty(fd)
        if total_width is not None:
            if self.expand and actual_width < total_width:
                width[-1] += total_width - actual_width
                actual_width = total_width
            while actual_width > total_width:
                max_width = max(width)
                if max_width == 1:
                    break
                for i in range(len(width)):
                    if width[i] == max_width:
                        width[i] -= 1
                        actual_width -= 1
                        break
        if self.columns:
            fmt = color_fmt(" " + " @{pf}|@| ".join(["%s"] * len(width)) + "\n", use_color=use_color)
            sep = color_fmt("@{pf}-" + "-+-".join(["-" * w for w in width]) + "-\n", use_color=use_color)
            fd.write(sep)
            fd.write(fmt % tuple(pad_ansi_text(color_fmt("@!%s" % c, use_color=use_color), w) for c, w in zip(self.columns, width)))
        else:
            fmt = " %s   %s\n"
            sep = color_fmt("@{pf}" + ("-" * actual_width) + "@|\n", use_color=use_color)
        fd.write(sep)
        for row in self.rows:
            if row is None:
                fd.write(sep)
                continue
            for line in zip_longest(*row, fillvalue=""):
                chunks = (slice_ansi_text(color_fmt(r, use_color=use_color), w) for r, w in zip(line, width))
                for chunk in zip_longest(*chunks):
                    fd.write(fmt % tuple(r if r is not None else " " * w for r, w in zip(chunk, width)))
        fd.write(sep)
