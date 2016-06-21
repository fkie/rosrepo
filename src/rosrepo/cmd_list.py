"""
Copyright (c) 2016 Fraunhofer FKIE

"""
from .workspace import get_workspace_location


def run(args):
    wsdir = get_workspace_location(args.workspace)
