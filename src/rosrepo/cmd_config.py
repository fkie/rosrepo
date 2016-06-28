"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import sys
from .workspace import find_ros_root, get_workspace_location
from .gitlab import find_available_gitlab_projects, acquire_gitlab_private_token
from .config import Config
from .cache import Cache
from .ui import TableView, fatal, escape
from .common import DEFAULT_CMAKE_ARGS, get_c_compiler, get_cxx_compiler
from .util import call_process


try:
    from urlparse import urlsplit, urlunsplit
except ImportError:
    from urllib.parse import urlsplit, urlunsplit


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)

    if args.show_gitlab_urls:
        servers = config.get("gitlab_servers", [])
        table = TableView("Label", "Gitlab URL", "Credentials")
        for srv in servers:
            table.add_row(escape(srv.get("label", "")), escape(srv.get("url", "")), "@{gf}yes" if srv.get("private_token", None) is not None else "@{rf}no")
        table.write(fd=sys.stdout)
        return 0

    need_clean = False

    if args.set_ros_root:
        need_clean = True
        if args.set_ros_root.lower() == "auto":
            if "ros_root" in config:
                del config["ros_root"]
        else:
            config["ros_root"] = args.set_ros_root

    if args.set_gitlab_url:
        label, url = args.set_gitlab_url[0], urlunsplit(urlsplit(args.set_gitlab_url[1]))
        if args.with_private_token:
            private_token = args.with_private_token
        elif args.without_private_token:
            private_token = None
        else:
            if args.offline:
                fatal("cannot acquire Gitlab private token in offline mode\n")
            private_token = acquire_gitlab_private_token(label, url)
        config.set_default("gitlab_servers", [])
        for srv in config["gitlab_servers"]:
            if srv.get("label", None) == label:
                srv["url"] = url
                if private_token is not None:
                    srv["private_token"] = private_token
                break
        else:
            srv = {"label": label, "url": url}
            if private_token is not None:
                srv["private_token"] = private_token
            config["gitlab_servers"].append(srv)
        find_available_gitlab_projects(label, url, private_token=private_token, cache=cache, cache_only=args.offline, verbose=True)
    if args.unset_gitlab_url:
        if "gitlab_servers" in config:
            config["gitlab_servers"] = [srv for srv in config["gitlab_servers"] if srv["label"] != args.unset_gitlab_url]

    if args.job_limit:
        if args.job_limit > 0:
            config["job_limit"] = args.job_limit
        else:
            del config["job_limit"]
    if args.no_job_limit and "job_limit" in config:
        del config["job_limit"]

    if args.install:
        config["install"] = True
    if args.no_install:
        config["install"] = False

    if args.set_compiler:
        cc = get_c_compiler(args.set_compiler)
        cxx = get_cxx_compiler(args.set_compiler)
        if cc and cxx:
            need_clean = need_clean or args.set_compiler != config.get("compiler", None)
            config["compiler"] = args.compiler
        else:
            fatal("unknown compiler")
    if args.unset_compiler and "compiler" in config:
        need_clean = True
        del config["compiler"]
    config.write()

    ros_rootdir = find_ros_root(config.get("ros_root", None))
    if ros_rootdir is None:
        fatal("cannot detect ROS distribution. Please source setup.bash or use --ros-root option\n")

    if need_clean:
        catkin_clean = ["catkin", "clean", "--workspace", wsdir, "--all", "--yes"]
        call_process(catkin_clean)

    catkin_config = ["catkin", "config", "--workspace", wsdir, "--extend", ros_rootdir]
    catkin_config += ["--install"] if config.get("install", False) else ["--no-install"]

    catkin_config += ["--cmake-args"] + DEFAULT_CMAKE_ARGS
    compiler = config.get("compiler", None)
    if compiler:
        cc = get_c_compiler(args.compiler)
        cxx = get_cxx_compiler(args.compiler)
        if cc and cxx:
            catkin_config += ["-DCMAKE_C_COMPILER=%s" % cc, "-DCMAKE_CXX_COMPILER=%s" % cxx]
    return call_process(catkin_config)
