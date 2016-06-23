"""
Copyright (c) 2016 Fraunhofer FKIE

"""
from .workspace import get_workspace_location
from .gitlab import find_available_gitlab_projects, acquire_gitlab_private_token
from .config import Config
from .cache import Cache
from .util import UserError

try:
    from urlparse import urlsplit, urlunsplit
except ImportError:
    from urllib.parse import urlsplit, urlunsplit

def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)
    if args.set_ros_root:
        if args.set_ros_root.lower() == "auto":
            if "ros_root" in config: del config["ros_root"]
        else:
            config["ros_root"] = args.set_ros_root
    if args.set_gitlab_url:
        label, url = args.set_gitlab_url[0], urlunsplit(urlsplit(args.set_gitlab_url[1]))
        if args.with_private_token:
            private_token = args.with_private_token
        elif args.without_private_token:
            private_token = None
        else:
            if args.offline: raise UserError("cannot acquire Gitlab private token in offline mode")
            private_token = acquire_gitlab_private_token("%s [%s]" % (label, url))
        config.set_default("gitlab_servers", [])
        for srv in config["gitlab_servers"]:
            if srv.get("label", None) == label:
                srv["url"] = url
                if private_token is not None:
                    srv["private_token"] = private_token
                break
        else:
            srv = {"label": label, "url": url}
            if private_token is not None: srv["private_token"] = private_token
            config["gitlab_servers"].append(srv)
        find_available_gitlab_projects(label, url, private_token=private_token, cache=cache, cache_only=args.offline, verbose=True)
    if args.unset_gitlab_url:
        if "gitlab_servers" in config:
            config["gitlab_servers"] = [srv for srv in config["gitlab_servers"] if srv["label"] != args.unset_gitlab_url]
    config.write()
