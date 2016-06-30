# coding=utf-8
#
# ROSREPO
# Manage ROS workspaces with multiple Gitlab repositories
#
# Author: Timo Röhling
#
# Copyright (c) 2016 Fraunhofer FKIE
#
#
import sys
from .workspace import find_ros_root, get_workspace_location
from .gitlab import find_available_gitlab_projects, acquire_gitlab_private_token
from .config import Config
from .cache import Cache
from .ui import TableView, msg, fatal, escape
from .common import DEFAULT_CMAKE_ARGS, get_c_compiler, get_cxx_compiler
from .util import call_process


try:
    from urlparse import urlsplit, urlunsplit
except ImportError:
    from urllib.parse import urlsplit, urlunsplit


def show_config(config):
    table = TableView(expand=True)
    srv_list = []
    for srv in config.get("gitlab_servers", []):
        label = srv.get("label", None)
        url = srv.get("url", None)
        if label and url:
            srv_list.append("@{yf}%s: %s" % (escape(label), escape(url)))
        elif label:
            srv_list.append("@{yf}%s" % escape(label))
        elif url:
            srv_list.append("@{yf}%s" % escape(url))
    table.add_row("@{cf}Gitlab Servers:", srv_list)
    if "store_credentials" in config:
        table.add_row("@{cf}Store Credentials:", "@{yf}" + ("Yes" if config["store_credentials"] else "No"))
    table.add_separator()
    if "ros_root" in config:
        table.add_row("@{cf}Override ROS Path:", "@{yf}" + escape(config["ros_root"]))
    if "compiler" in config:
        table.add_row("@{cf}Compiler:", "@{yf}" + escape(config["compiler"]))
    jobs = config.get("job_limit", None)
    table.add_row("@{cf}Parallel Build Jobs:", "@{yf}" + ("%d" % jobs if jobs is not None else "Unlimited"))
    if "install" in config:
        table.add_row("@{cf}Install:", "@{yf}" + ("Yes" if config["install"] else "No"))
    table.add_row("@{cf}Run catkin_lint Before Build:", "@{yf}" + ("Yes" if config["use_catkin_lint"] else "No"))
    table.add_row("@{cf}Run rosclipse After Build:", "@{yf}" + ("Yes" if config["use_rosclipse"] else "No"))
    table.add_separator()
    table.add_row("@{cf}Pinned Packages:", ["@{yf}" + escape(s) for s in config.get("pinned_build", [])])
    table.add_row("@{cf}Default Build:", ["@{yf}" + escape(s) for s in config.get("default_build", [])])
    table.write()


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)
    cache = Cache(wsdir)

    if args.get_gitlab_url:
        servers = config.get("gitlab_servers", [])
        sys.stdout.write("\n".join([s.get("url", "") for s in servers if s.get("label", "") == args.get_gitlab_url]) + "\n")
        return 0
    if args.show_gitlab_urls:
        servers = config.get("gitlab_servers", [])
        if args.autocomplete:
            sys.stdout.write("\n".join([s.get("label", "") for s in servers]) + "\n")
            return 0
        table = TableView("Label", "Gitlab URL", "Credentials")
        for srv in servers:
            table.add_row(escape(srv.get("label", "")), escape(srv.get("url", "")), "@{gf}yes" if srv.get("private_token", None) is not None else "@{rf}no")
        table.write(fd=sys.stdout)
        return 0

    need_clean = False

    if args.set_ros_root:
        old_ros_root = find_ros_root(config.get("ros_root", None))
        new_ros_root = find_ros_root(args.set_ros_root)
        need_clean = old_ros_root != new_ros_root
        config["ros_root"] = args.set_ros_root
    if args.unset_ros_root:
        old_ros_root = find_ros_root(config.get("ros_root", None))
        new_ros_root = find_ros_root(None)
        need_clean = old_ros_root != new_ros_root
        del config["ros_root"]

    config.set_default("store_credentials", True)
    if args.store_credentials:
        config["store_credentials"] = True
    if args.no_store_credentials:
        config["store_credentials"] = False

    if args.gitlab_logout:
        config.set_default("gitlab_servers", [])
        for srv in config["gitlab_servers"]:
            if srv.get("label", None) == args.gitlab_logout:
                if "private_token" in srv:
                    del srv["private_token"]
                    msg("Private token removed\n")
                break
        else:
            fatal("no such Gitlab server")
    if args.remove_credentials:
        config.set_default("gitlab_servers", [])
        for srv in config["gitlab_servers"]:
            if "private_token" in srv:
                del srv["private_token"]
        msg("All Gitlab private tokens removed")
    if args.gitlab_login:
        config.set_default("gitlab_servers", [])
        for srv in config["gitlab_servers"]:
            label = srv.get("label", None)
            if label == args.gitlab_login:
                url = srv.get("url", None)
                if url is None:
                    fatal("cannot acquire token for Gitlab server without URL")
                if args.private_token:
                    private_token = args.private_token
                elif args.no_private_token:
                    private_token = None
                else:
                    if args.offline:
                        fatal("cannot acquire Gitlab private token in offline mode\n")
                    private_token = acquire_gitlab_private_token(label, url)
                srv["private_token"] = private_token
                break
        else:
            fatal("no such Gitlab server")
    if args.set_gitlab_url:
        label, url = args.set_gitlab_url[0], urlunsplit(urlsplit(args.set_gitlab_url[1]))
        if args.private_token:
            private_token = args.private_token
        elif args.no_private_token or not config["store_credentials"]:
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
        config.set_default("gitlab_servers", [])
        config["gitlab_servers"] = [srv for srv in config["gitlab_servers"] if srv["label"] != args.unset_gitlab_url]

    if args.job_limit:
        if args.job_limit > 0:
            config["job_limit"] = args.job_limit
        else:
            del config["job_limit"]
    if args.no_job_limit:
        del config["job_limit"]

    config.set_default("install", False)
    if args.install:
        need_clean = need_clean or not config["install"]
        config["install"] = True
    if args.no_install:
        need_clean = need_clean or config["install"]
        config["install"] = False

    if args.set_compiler:
        cc = get_c_compiler(args.set_compiler)
        cxx = get_cxx_compiler(args.set_compiler)
        if cc and cxx:
            need_clean = need_clean or args.set_compiler != config.get("compiler", None)
            config["compiler"] = args.set_compiler
        else:
            fatal("unknown compiler")
    if args.unset_compiler and "compiler" in config:
        need_clean = True
        del config["compiler"]

    config.set_default("use_rosclipse", True)
    if args.rosclipse:
        config["use_rosclipse"] = True
    if args.no_rosclipse:
        config["use_rosclipse"] = False

    config.set_default("use_catkin_lint", True)
    if args.catkin_lint:
        config["use_catkin_lint"] = True
    if args.no_catkin_lint:
        config["use_catkin_lint"] = False

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
        cc = get_c_compiler(compiler)
        cxx = get_cxx_compiler(compiler)
        if cc and cxx:
            catkin_config += ["-DCMAKE_C_COMPILER=%s" % cc, "-DCMAKE_CXX_COMPILER=%s" % cxx]
    ret = call_process(catkin_config)
    show_config(config)
    return ret
