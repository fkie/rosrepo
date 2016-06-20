"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import os
import yaml
from distutils.version import StrictVersion as Version
from .util import write_atomic, UserError
from . import __version__


class Config(object):
    def __init__(self, wsdir):
        self.config_dir = os.path.join(wsdir, ".rosrepo")
        self.config_file = os.path.join(self.config_dir, "config")
        if os.path.isfile(self.config_file):
            with open(self.config_file, "r") as f:
                self.data = yaml.safe_load(f.read())
            if not isinstance(self.data, dict):
                raise UserError("Corrupted rosrepo configuration file")
        else:
            self.data = {"version": __version__}
        current = Version(__version__)
        stored = Version(self.data["version"])
        if stored < current:
            self.migrate(stored)
            self.write()
        if stored > current:
            raise UserError("Workspace was configured by newer version of rosrepo")

    def migrate(self, old_version):
        self.data["version"] = __version__

    def write(self):
        if not os.path.isdir(self.config_dir):
            os.makedirs(self.config_dir)
        write_atomic(self.config_file, yaml.safe_dump(self.data, default_flow_style=False))
