"""
Copyright (c) 2016 Fraunhofer FKIE

"""
from .workspace import get_workspace_location
from .util import call_process


def run(args):
    wsdir = get_workspace_location(args.workspace)
    catkin_clean = ["catkin", "clean", "--workspace", wsdir, "--all", "--yes"]
    if args.dry_run:
        catkin_clean.append("--dry-run")
    return call_process(catkin_clean)
