"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import sys
from getpass import getpass
import re
from .util import get_terminal_size, UserError
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


def isatty(fd):
    return hasattr(fd, "isatty") and fd.isatty()


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
    if ll:
        ll[0] = 0  # Do not skip initial ANSI for this
    excess = len(ll) % chunk_size
    if pad and excess > 0:
        padded_text = text + fill[0] * (chunk_size - excess)
    else:
        padded_text = text
    return list(padded_text[ll[i]:ll[chunk_size + i] if chunk_size + i < len(ll) else len(padded_text)] for i in range(0, len(ll), chunk_size))


def pad_ansi_text(text, width, truncate=True, fill=" "):
    l = printed_len(text)
    length = len(l)
    if width < length:
        return text[:l[width]] if truncate else text
    return text + fill[0] * (width - length)


def wrap_ansi_text(text, width, indent_first=0, indent_next=0):
    if width is None:
        return text
    result = []
    chunks = text.split("\n")
    skip_blank = False
    for chunk in chunks:
        count = indent_first
        line = []
        if indent_first > 0:
            line.append(" " * (indent_first - 1))
        for word in chunk.split(" "):
            l = len(remove_ansi(word))
            if l == 0 and skip_blank:
                continue
            if l != 0:
                skip_blank = False
            if count + l < width:
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
        result.append(" ".join(line))
    return "\n".join(result)


def escape(msg):
    return msg.replace("@", "@@")


def msg(text, max_width=None, use_color=None, wrap=True, fd=sys.stdout, indent_first=0, indent_next=0):
    from .terminal_color import _ansi
    ansi_text = color_fmt(text, use_color=isatty(fd) if use_color is None else use_color)
    if wrap:
        try:
            if max_width is None:
                max_width, _ = terminal_width.get(fd.fileno(), get_terminal_size(fd))
        except OSError:
            pass
    fd.write(wrap_ansi_text(ansi_text, max_width, indent_first, indent_next) + (_ansi['reset'] if use_color else ""))


def fatal(text):
    raise UserError(text)


def error(text, use_color=None):
    msg("@!@{rf}%s: error: %s" % (sys.argv[0], text), fd=sys.stderr, indent_next=len(sys.argv[0]) + 9)


def warning(text, use_color=None):
    msg("@!@{yf}%s: warning: %s" % (sys.argv[0], text), use_color=use_color, fd=sys.stderr, indent_next=len(sys.argv[0]) + 11)


def get_credentials(domain):
    msg("@!Authentication required for @{cf}%s\n" % domain, fd=sys.stderr)
    while True:
        login = raw_input("Username: ")
        if login == "":
            continue
        passwd = getpass("Password: ")
        if passwd == "":
            msg("Starting over\n\n")
            continue
        return login, passwd


class TableView(object):
    def __init__(self, *args):
        self.columns = args
        self.width = [max(1, len(remove_ansi(color_fmt(c)))) for c in self.columns]
        self.rows = []

    def add_row(self, *args):
        row = [r if isinstance(r, list) or isinstance(r, tuple) else (r,) for r in args]
        self.rows.append(row)
        self.width = [max(w, *(len(remove_ansi(color_fmt(r))) for r in rs)) for w, rs in zip(self.width, row)]

    def empty(self):
        return len(self.rows) == 0

    def sort(self, column_index):
        self.rows.sort(key=lambda x: x[column_index])

    def write(self, fd=sys.stdout):
        width = self.width
        actual_width = sum(width) + 3 * len(width) - 1
        if isatty(fd):
            use_color = True
            try:
                total_width = terminal_width.get(fd.fileno(), get_terminal_size(fd))[0] - 1
            except OSError:
                total_width = 79
        else:
            use_color = False
            total_width = None
        if total_width is not None:
            while actual_width > total_width:
                max_width = max(width)
                width = [min(max_width - 1, w) for w in width]
                actual_width = sum(width) + 3 * len(width) + 1
        fmt = color_fmt(" " + " @{pf}|@| ".join(["%s"] * len(width)) + "\n", use_color=use_color)
        sep = color_fmt("@{pf}-" + "-+-".join(["-" * w for w in width]) + "-\n", use_color=use_color)
        fd.write(sep)
        fd.write(fmt % tuple(pad_ansi_text(color_fmt("@!%s" % c, use_color=use_color), w) for c, w in zip(self.columns, width)))
        fd.write(sep)
        for row in self.rows:
            for line in map(None, *row):
                chunks = (slice_ansi_text(color_fmt(r, use_color=use_color) if r is not None else "", w) for r, w in zip(line, width))
                for chunk in map(None, *chunks):
                    fd.write(fmt % tuple(r if r is not None else " " * w for r, w in zip(chunk, width)))
        fd.write(sep)
