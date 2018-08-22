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
import requests
import platform
try:
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urljoin
from .workspace import find_ros_root, get_workspace_location
from .gitlab import acquire_gitlab_private_token, get_gitlab_projects
from .cache import Cache
from .config import Config
from .ui import TableView, msg, warning, fatal, escape
from .common import DEFAULT_CMAKE_ARGS, update_default_git_ignore, get_c_compiler, get_cxx_compiler
from .util import call_process


try:
    from urlparse import urlsplit, urlunsplit
except ImportError:
    from urllib.parse import urlsplit, urlunsplit


def show_config(config):
    table = TableView(expand=True)
    srv_list = []
    for srv in config.get("gitlab_servers", []):
        label = srv.get("label", "")
        url = srv.get("url", "")
        srv_list.append("@{yf}%s%s" % (escape(label) + ": " if label else "", escape(url)))
    table.add_row("@{cf}Gitlab Servers:", srv_list)
    if "store_credentials" in config:
        table.add_row("@{cf}Store Credentials:", "@{yf}" + ("Yes" if config["store_credentials"] else "No"))
    if "git_default_transport" in config:
        table.add_row("@{cf}Default Transport:", "@{yf}%s" % config["git_default_transport"])
    if "gitlab_crawl_depth" in config:
        table.add_row("@{cf}Crawl Depth:", "@{yf}%s" % config["gitlab_crawl_depth"])
    table.add_separator()
    if "ros_root" in config:
        table.add_row("@{cf}Override ROS Path:", "@{yf}" + escape(config["ros_root"]))
    if "compiler" in config:
        table.add_row("@{cf}Compiler:", "@{yf}" + escape(config["compiler"]))
    jobs = config.get("job_limit", None)
    table.add_row("@{cf}Parallel Build Jobs:", "@{yf}" + ("%d" % jobs if jobs is not None else "Unlimited"))
    if "install" in config:
        table.add_row("@{cf}Install:", "@{yf}" + ("Yes" if config["install"] else "No"))
    table.add_row("@{cf}Run catkin_lint:", "@{yf}" + ("Yes" if config["use_catkin_lint"] else "No"))
    table.add_row("@{cf}Skip catkin_lint:", ["@{yf}" + escape(s) for s in config.get("skip_catkin_lint", [])])
    table.add_row("@{cf}Run rosclipse:", "@{yf}" + ("Yes" if config["use_rosclipse"] else "No"))
    table.add_row("@{cf}Offline Mode:", "@{yf}" + ("Yes" if config.get("offline_mode", False) else "No"))
    table.add_separator()
    table.add_row("@{cf}Pinned Packages:", ["@{yf}" + escape(s) for s in config.get("pinned_build", [])])
    table.add_row("@{cf}Default Build:", ["@{yf}" + escape(s) for s in config.get("default_build", [])])
    table.write()


def run(args):
    wsdir = get_workspace_location(args.workspace)
    config = Config(wsdir)

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
        old_ros_root = find_ros_root(config.get("ros_root"))
        new_ros_root = find_ros_root(args.set_ros_root)
        need_clean = old_ros_root != new_ros_root
        config["ros_root"] = args.set_ros_root
    if args.unset_ros_root:
        old_ros_root = find_ros_root(config.get("ros_root"))
        new_ros_root = find_ros_root(None)
        need_clean = old_ros_root != new_ros_root
        del config["ros_root"]

    if args.offline is not None:
        config["offline_mode"] = args.offline
    else:
        args.offline = config.get("offline_mode", False)

    config.set_default("store_credentials", True)
    if args.store_credentials is not None:
        config["store_credentials"] = args.store_credentials

    if args.gitlab_logout:
        config.set_default("gitlab_servers", [])
        for srv in config["gitlab_servers"]:
            if srv.get("label", None) == args.gitlab_logout:
                if "private_token" in srv:
                    del srv["private_token"]
                    msg("Private token removed\n")
                break
        else:
            fatal("no such Gitlab server\n")
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
                    fatal("cannot acquire token for Gitlab server without URL\n")
                if args.private_token:
                    private_token = args.private_token
                else:
                    private_token = None
                    if "private_token" in srv:
                        private_token = srv["private_token"]
                        if not args.offline:
                            r = requests.get(urljoin(url, "api/v4/projects"), headers={"PRIVATE-TOKEN": private_token})
                            if r.status_code == 401:
                                private_token = None
                            else:
                                msg("stored Gitlab private token is valid\n")
                        else:
                            warning("cannot verify Gitlab private token in offline mode\n")
                    if private_token is None:
                        if args.offline:
                            fatal("cannot acquire Gitlab private token in offline mode\n")
                        private_token = acquire_gitlab_private_token(label, url)
                if config["store_credentials"]:
                    srv["private_token"] = private_token
                else:
                    warning("credential storage has been disabled")
                break
        else:
            fatal("no such Gitlab server\n")
    if args.set_gitlab_url:
        label, url = args.set_gitlab_url[0], urlunsplit(urlsplit(args.set_gitlab_url[1]))
        if args.private_token:
            private_token = args.private_token
        else:
            private_token = None
        config.set_default("gitlab_servers", [])
        for srv in config["gitlab_servers"]:
            if srv.get("label", None) == label:
                srv["url"] = url
                if config["store_credentials"]:
                    if private_token is None and "private_token" in srv:
                        private_token = srv["private_token"]
                        if not args.offline:
                            r = requests.get(urljoin(url, "api/v4/projects"), headers={"PRIVATE-TOKEN": private_token})
                            if r.status_code == 401:
                                private_token = None
                            else:
                                msg("stored Gitlab private token is valid\n")
                        else:
                            warning("cannot verify Gitlab private token in offline mode\n")
                    if private_token is None:
                        if args.offline:
                            fatal("cannot acquire Gitlab private token in offline mode\n")
                        private_token = acquire_gitlab_private_token(label, url)
                    srv["private_token"] = private_token
                break
        else:
            srv = {"label": label, "url": url}
            if config["store_credentials"]:
                if private_token is None:
                    if args.offline:
                        fatal("cannot acquire Gitlab private token in offline mode\n")
                    private_token = acquire_gitlab_private_token(label, url)
                srv["private_token"] = private_token
            config["gitlab_servers"].append(srv)
    if args.unset_gitlab_url:
        config.set_default("gitlab_servers", [])
        config["gitlab_servers"] = [srv for srv in config["gitlab_servers"] if srv["label"] != args.unset_gitlab_url]

    if args.job_limit is not None:
        if args.job_limit > 0:
            config["job_limit"] = args.job_limit
        else:
            del config["job_limit"]

    config.set_default("install", False)
    if args.install is not None:
        need_clean = need_clean or config["install"] != args.install
        config["install"] = args.install

    if args.set_compiler:
        cc = get_c_compiler(args.set_compiler)
        cxx = get_cxx_compiler(args.set_compiler)
        if cc and cxx:
            need_clean = need_clean or args.set_compiler != config.get("compiler", None)
            config["compiler"] = args.set_compiler
        else:
            fatal("unknown compiler\n")
    if args.unset_compiler and "compiler" in config:
        need_clean = True
        del config["compiler"]

    config.set_default("use_rosclipse", True)
    if args.rosclipse is not None:
        config["use_rosclipse"] = args.rosclipse

    config.set_default("use_catkin_lint", True)
    if args.catkin_lint is not None:
        config["use_catkin_lint"] = args.catkin_lint

    config.set_default("skip_catkin_lint", [])
    if args.skip_catkin_lint:
        for pkg in args.skip_catkin_lint:
            if pkg not in config["skip_catkin_lint"]:
                config["skip_catkin_lint"].append(pkg)
    if args.no_skip_catkin_lint:
        for pkg in args.no_skip_catkin_lint:
            config["skip_catkin_lint"].remove(pkg)
    config["skip_catkin_lint"].sort()

    config.set_default("use_env_cache", True)
    if args.env_cache is not None:
        config["use_env_cache"] = args.env_cache

    config.set_default("gitlab_crawl_depth", 1)
    if args.set_gitlab_crawl_depth is not None:
        if args.offline:
            fatal("cannot reset crawl depth in offline mode")
        config["gitlab_crawl_depth"] = args.set_gitlab_crawl_depth

    config.set_default("git_default_transport", "ssh")
    if args.protocol:
        config["git_default_transport"] = args.protocol.lower()

    config.write()
    update_default_git_ignore()

    if args.set_gitlab_crawl_depth is not None or args.force_gitlab_update:
        if args.offline:
            fatal("cannot update Gitlab package list in offline mode")
        cache = Cache(wsdir)
        get_gitlab_projects(wsdir, config, cache, force_update=True, verbose=True)

    ros_rootdir = find_ros_root(config.get("ros_root"))
    if ros_rootdir is None:
        fatal("cannot detect ROS distribution. Please source setup.bash or use --ros-root option\n")
    if ros_rootdir != config.get("last_ros_root", None):
        need_clean = True

    catkin_config = ["catkin", "config", "--workspace", wsdir, "--extend", ros_rootdir]
    catkin_config += ["--install"] if config.get("install", False) else ["--no-install"]

    catkin_config += ["--cmake-args"] + DEFAULT_CMAKE_ARGS
    system = platform.system()
    if system in ["Linux", "Darwin"]:
        catkin_config += [
            "-DCMAKE_CXX_FLAGS=-Wall -Wextra -Wno-ignored-qualifiers -Wno-invalid-offsetof -Wno-unused-parameter -fno-omit-frame-pointer",
            "-DCMAKE_CXX_FLAGS_RELWITHDEBINFO=-O2 -g",
            "-DCMAKE_C_FLAGS=-Wall -Wextra -Wno-unused-parameter -fno-omit-frame-pointer",
            "-DCMAKE_C_FLAGS_RELWITHDEBINFO=-O2 -g",
        ]
    if system == "Linux":
        catkin_config += [
            "-DCMAKE_SHARED_LINKER_FLAGS=-Wl,-z,defs",
            "-DCMAKE_EXE_LINKER_FLAGS=-Wl,-z,defs"
        ]
    compiler = config.get("compiler", None)
    if compiler:
        cc = get_c_compiler(compiler)
        cxx = get_cxx_compiler(compiler)
        if cc and cxx:
            catkin_config += ["-DCMAKE_C_COMPILER=%s" % cc, "-DCMAKE_CXX_COMPILER=%s" % cxx]
    ret = call_process(catkin_config)

    if need_clean:
        catkin_clean = ["catkin", "clean", "--workspace", wsdir, "--all", "--yes"]
        call_process(catkin_clean)
        config["last_ros_root"] = ros_rootdir
        config.write()

    show_config(config)
    return ret
