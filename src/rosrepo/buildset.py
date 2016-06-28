"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import os
from .workspace import get_workspace_location, get_workspace_state
from .cache import Cache
from .config import Config
from .ui import msg, fatal
from .resolver import find_dependees, show_conflicts, show_fallback
from .cmd_git import clone_packages


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    config.set_default("default_build", [])
    config.set_default("pinned_build", [])
    set_name = "pinned_build" if args.pin else "default_build"
    ws_state = get_workspace_state(wsdir, config, cache, offline_mode=args.offline)
    if args.all:
        args.packages = ws_state.ws_packages.keys()
        if args.command == "exclude":
            config[set_name] = []

    if args.list:
        selected = set(config.get(set_name, []))
    else:
        selected = set(args.packages)
        if args.command == "include":
            if not args.replace:
                selected |= set(config.get(set_name, []))
        if args.command == "exclude":
            selected = set(config.get(set_name, [])) - selected

    if args.pin:
        if args.list:
            msg("@{cf}The following packages are pinned and will always be built@|:\n")
        else:
            msg("@{cf}The following packages are going to be pinned, so they will always be built@|:\n")
    else:
        if args.list:
            msg("@{cf}The following packages are built by default@|:\n")
        else:
            msg("@{cf}The following packages are going to be built by default from now on@|:\n")
    if selected:
        msg(", ".join(sorted(list(selected))) + "\n\n", indent_first=4, indent_next=4)
    else:
        msg("(none)\n\n", indent_first=4, indent_next=4)

    depends, fallback, conflicts = find_dependees(selected, ws_state)
    show_fallback(fallback)
    show_conflicts(conflicts)
    if conflicts:
        if not args.list:
            fatal("cannot resolve dependencies")
        else:
            return 0

    depend_set = set(depends.keys()) - selected
    if depend_set:
        msg("@{cf}The following additional packages are needed to satisfy all dependencies@|:\n")
        msg(", ".join(sorted(depend_set)) + "\n\n", indent_first=4, indent_next=4)

    clone_packages(os.path.join(wsdir, "src"), depends, ws_state, protocol=args.protocol, dry_run=args.dry_run, list_only=args.list)

    if args.list:
        return 0

    config[set_name] = sorted(list(selected))
    config.write()
