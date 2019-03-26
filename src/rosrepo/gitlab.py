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
import requests
import sys
import os
import concurrent.futures
from pygit2 import Repository

try:
    from scandir import walk as os_walk
except ImportError:
    from os import walk as os_walk

from dateutil.parser import parse as date_parse
try:
    from urllib import quote as urlquote
except ImportError:
    from urllib.parse import quote as urlquote
from catkin_pkg.package import parse_package_string, InvalidPackage, PACKAGE_MANIFEST_FILENAME

try:
    from urlparse import urljoin, urlsplit
except ImportError:
    from urllib.parse import urljoin, urlsplit

from .ui import ask_personal_access_token, ask_username_and_password, msg, warning, error, fatal
from .util import iteritems, NamedTuple, yaml_dump


GITLAB_PACKAGE_CACHE_VERSION = 4


class GitlabServer(NamedTuple):
    __slots__ = ("projects", "last_modified")


class GitlabProject(NamedTuple):
    __slots__ = (
        "server", "name", "id", "website", "url", "packages",
        "last_modified", "workspace_path", "master_branch",
        "server_path"
    )

    def __cmp__(self, other):
        if not hasattr(other, "server") or not hasattr(other, "id"):
            return NotImplemented
        c = cmp(self.server, other.server)
        if c != 0:
            return c
        return cmp(self.id, other.id)


class GitlabPackage(NamedTuple):
    __slots__ = (
        "manifest", "project", "project_path", "manifest_blob", "manifest_xml"
    )


def url_to_cache_name(label, url):
    tmp = ["gitlab_projects"]
    if label is not None:
        tmp.append(urlquote(label, safe=""))
    if url is not None:
        _, tail = url.split("://", 1)
        tmp.append(urlquote(tail, safe=""))
    return "_".join(tmp)


def crawl_project_for_packages(session, url, project_id, path, depth, timeout):
    page_count = 1
    page_no = 1
    entries = []
    while page_no <= page_count:
        r = session.get(urljoin(url, "api/v4/projects/%s/repository/tree" % project_id), params={"path": path, "per_page": 100, "page": page_no})
        if r.status_code == 200:
            entries += r.json()
            page_count = int(r.headers.get("X-Total-Pages", 0))
        else:
            return []
        page_no += 1
    files = [e["name"] for e in entries if e["type"] == "blob"]
    dirs = [e["name"] for e in entries if e["type"] == "tree" and not e["name"].startswith(".")]
    if "CATKIN_IGNORE" in files:
        return []
    for e in entries:
        if e["type"] == "blob" and e["name"] == PACKAGE_MANIFEST_FILENAME:
            return [(path, e["id"])]
    if depth == 0:
        return []
    result = []
    for d in dirs:
        result += crawl_project_for_packages(session, url, project_id, os.path.join(path, d), depth - 1, timeout)
    return result


_cached_tokens = {}


def acquire_gitlab_private_token(label, url, credentials_callback=ask_username_and_password):
    global _cached_tokens
    if url in _cached_tokens:
        return _cached_tokens[url]
    retries = 3
    while retries > 0:
        retries -= 1
        login, passwd = credentials_callback("%s [%s]" % (label, url))
        r = requests.post(urljoin(url, "api/v4/session"), data={"login": login, "password": passwd})
        if r.status_code == 404:
            msg("This version of the Gitlab server will not create access tokens via API. "
                "You need to create a personal access token with @!api@| scope manually "
                "and pass it to resrepo with the --private-token option. Visit the following URL:\n\n@{cf}%s/profile/personal_access_tokens@|\n\n" % url)
            fatal("required feature unavailabe")
        if r.status_code == 401:
            msg("@!@{rf}Access denied@|\n", fd=sys.stderr)
            continue
        break
    r.raise_for_status()
    token = r.json()["private_token"]
    _cached_tokens[url] = token
    return token


_updated_urls = set()


def find_available_gitlab_projects(label, url, private_token=None, cache=None, timeout=None, crawl_depth=-1, cache_only=False, force_update=False, verbose=True):

    def update_project_list(page_no, s):
        r = s.get(urljoin(url, "api/v4/projects/?per_page=100&page=%d" % page_no), timeout=timeout)
        r.raise_for_status()
        return r.json()

    def update_single_project(yaml_p, s, server_cache):
        cached_p = next((q for q in server_cache.projects if q.id == yaml_p["id"]), None)
        p = GitlabProject(
            server=server_name,
            name=yaml_p["name_with_namespace"],
            id=yaml_p["id"],
            website=yaml_p["web_url"],
            url={"ssh": yaml_p["ssh_url_to_repo"], "http": yaml_p["http_url_to_repo"]},
            master_branch=yaml_p.get("default_branch", "master"),
            packages=None,
            last_modified=date_parse(yaml_p["last_activity_at"]),
            workspace_path=None,
            server_path=yaml_p["path_with_namespace"]
        )
        if not force_update and cached_p is not None and cached_p.last_modified == p.last_modified:
            p.packages = cached_p.packages
            for prj in p.packages:
                prj.project = p
        else:
            if verbose:
                msg("@{cf}Updating@|: %s\n" % p.website)
            manifests = crawl_project_for_packages(s, url, p.id, "", depth=crawl_depth, timeout=timeout)
            old_manifests = {}
            if cached_p is not None:
                for old_p in cached_p.packages:
                    old_manifests[old_p.manifest_blob] = old_p.manifest_xml
            p.packages = []
            for path, blob in manifests:
                if blob not in old_manifests:
                    r = s.get(urljoin(url, "api/v4/projects/%s/repository/blobs/%s/raw" % (p.id, blob)), timeout=timeout)
                    r.raise_for_status()
                    xml_data = r.content
                else:
                    xml_data = old_manifests[blob]
                filename = os.path.join(path, PACKAGE_MANIFEST_FILENAME)
                try:
                    manifest = parse_package_string(xml_data, filename)
                    if verbose:
                        msg("@{cf}Updated@|:  @{yf}%s@| [%s]\n" % (manifest.name, p.name))
                    p.packages.append(GitlabPackage(manifest=manifest, project=p, project_path=path, manifest_blob=blob, manifest_xml=xml_data))
                except InvalidPackage as e:
                    warning("invalid package manifest '%s': %s\n" % (filename, str(e)))
        return p

    global _updated_urls
    server_name = urlsplit(url)[1]
    cache_update = False
    if cache is not None:
        server_cache = cache.get_object(url_to_cache_name(label, url), GITLAB_PACKAGE_CACHE_VERSION, GitlabServer())
    else:
        server_cache = GitlabServer()
    if server_cache.projects is None:
        server_cache.projects = []
    if server_cache.last_modified is None:
        server_cache.last_modified = 0
    if not cache_only and url is not None and private_token is not None and url not in _updated_urls:
        projects = []
        try:
            with requests.Session() as s:
                s.headers.update({"PRIVATE-TOKEN": private_token})
                r = s.get(urljoin(url, "api/v4/projects/?per_page=1&page=1&order_by=last_activity_at&sort=desc"), timeout=timeout)
                r.raise_for_status()
                try:
                    total_packages = int(r.headers.get("X-Total-Pages", 0))
                    global_last_modified = r.json()[0]["last_activity_at"]
                except (KeyError, IndexError):
                    global_last_modified = 0
                except Exception:
                    raise IOError("unexpected reply from server: %s" % r.content)
                if force_update or global_last_modified != server_cache.last_modified:
                    msg("@{cf}Updating@|: %s\n" % url)
                    cache_update = True
                    server_cache.last_modified = global_last_modified
                    project_list = []
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        total_pages = int((total_packages + 99) / 100)
                        fs = []
                        for page_no in range(1, total_pages + 1):
                            fs.append(executor.submit(update_project_list, page_no, s))
                        for future in concurrent.futures.as_completed(fs, timeout=timeout):
                            project_list += future.result()
                        fs = []
                        for yaml_p in project_list:
                            fs.append(executor.submit(update_single_project, yaml_p, s, server_cache))
                        for future in concurrent.futures.as_completed(fs, timeout=timeout):
                            projects.append(future.result())
                else:
                    projects = server_cache.projects
                    cache_update = False
        except (IOError, concurrent.futures.TimeoutError) as e:
            error("cannot update from '%s': %s\n" % (url, e))
            projects = server_cache.projects
            cache_update = False
        if cache is not None:
            _updated_urls.add(url)
    else:
        projects = server_cache.projects
    if cache is not None:
        if cache_update or len(projects) != len(server_cache.projects):
            server_cache.projects = projects
            cache.set_object(url_to_cache_name(label, url), GITLAB_PACKAGE_CACHE_VERSION, server_cache)
    return projects


def find_catkin_packages_from_gitlab_projects(projects, result=None):
    if result is None:
        result = {}
    for prj in projects:
        for pkg in prj.packages:
            if pkg.manifest.name not in result:
                result[pkg.manifest.name] = []
            result[pkg.manifest.name].append(pkg)
    return result


def find_cloned_gitlab_projects(projects, srcdir, subdir=None):
    def repo_has_project_url(repo_urls, project):
        for _, url in iteritems(project.url):
            if url in repo_urls:
                return True
        return False
    base_path = srcdir if subdir is None else os.path.join(srcdir, subdir)
    result = []
    foreign = []
    for curdir, subdirs, files in os_walk(base_path, followlinks=True):
        if "CATKIN_IGNORE" in files:
            del subdirs[:]
        elif ".git" in subdirs:
            repo = Repository(os.path.join(curdir, ".git"))
            repo_urls = set()
            for r in repo.remotes:
                repo_urls.add(r.url)
            path = os.path.relpath(curdir, srcdir)
            for project in projects:
                if repo_has_project_url(repo_urls, project):
                    assert project.workspace_path is None or project.workspace_path == path
                    project.workspace_path = path
                    for p in project.packages:
                        p.project = project
                    result.append(project)
                    break
            else:
                foreign.append(os.path.relpath(curdir, srcdir))
            del subdirs[:]
        else:
            subdirs = [s for s in subdirs if not s.startswith(".")]
    return result, foreign


def get_gitlab_projects(wsdir, config, cache=None, offline_mode=False, force_update=False, verbose=True):
    if "gitlab_servers" not in config:
        return []
    gitlab_projects = []
    for gitlab_cfg in config["gitlab_servers"]:
        label = gitlab_cfg.get("label", None)
        url = gitlab_cfg.get("url", None)
        private_token = gitlab_cfg.get("private_token", None)
        if url is not None and private_token is None and not offline_mode:
            warning("not updating '%s': no personal access token configured\n" % url)
            msg("Please visit @{cf}%s/profile/personal_access_tokens@| to create your token and configure it with\n\n    @!rosrepo config --gitlab-login %s --private-token TOKEN@|\n\n" % (url, label))
            # private_token = ask_personal_access_token(url) or None
        gitlab_projects += find_available_gitlab_projects(label, url, private_token=private_token, cache=cache, cache_only=offline_mode, crawl_depth=gitlab_cfg.get("crawl_depth", config.get("gitlab_crawl_depth", 1)), force_update=force_update, verbose=verbose)
    return gitlab_projects


def make_gitlab_distfile(label, url, private_token=None, cache=None, timeout=None, verbose=True):
    projects = find_available_gitlab_projects(label, url, private_token=private_token, cache=cache, timeout=timeout, verbose=verbose)
    result = {}
    for prj in projects:
        packages = []
        for pkg in prj.packages:
            packages.append({
                "name": pkg.manifest.name,
                "project_path": pkg.project_path,
                "manifest": {"blob": pkg.manifest_blob, "xml": pkg.manifest_xml},
            })
        if prj.server not in result:
            result[prj.server] = []
        result[prj.server].append({
            "id": prj.id,
            "name": prj.name,
            "website": prj.website,
            "url": prj.url,
            "master_branch": prj.master_branch,
            "last_modified": prj.last_modified.isoformat(),
            "packages": packages,
        })
    return yaml_dump(result, default_flow_style=False)
