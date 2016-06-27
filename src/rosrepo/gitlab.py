"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import requests
import sys
import os
import yaml
from dateutil.parser import parse as date_parse
from git import Repo
from urllib import quote as urlquote
from catkin_pkg.package import parse_package_string, InvalidPackage, PACKAGE_MANIFEST_FILENAME

try:
    from urlparse import urljoin, urlsplit
except ImportError:
    from urllib.parse import urljoin, urlsplit

from .ui import get_credentials, msg, warning, error
from .util import iteritems, NamedTuple


GITLAB_PACKAGE_CACHE_VERSION = 1


class GitlabProject(NamedTuple):
    __slots__ = (
        "server", "name", "id", "website", "url", "packages",
        "last_modified", "workspace_path"
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
    r = session.get(urljoin(url, "api/v3/projects/%s/repository/tree" % project_id), params={"path": path})
    if r.status_code == 200:
        entries = r.json()
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
    return []


_cached_tokens = {}


def acquire_gitlab_private_token(label, url, credentials_callback=get_credentials):
    global _cached_tokens
    if url in _cached_tokens:
        return _cached_tokens[url]
    retries = 3
    while retries > 0:
        retries -= 1
        login, passwd = credentials_callback("%s [%s]" % (label, url))
        r = requests.post(urljoin(url, "api/v3/session"), data={"login": login, "password": passwd})
        if r.status_code == 401:
            msg("@!@{rf}Access denied@!\n", fd=sys.stderr)
            continue
        break
    r.raise_for_status()
    token = r.json()["private_token"]
    _cached_tokens[url] = token
    return token


_updated_urls = set()


def find_available_gitlab_projects(label, url, private_token=None, cache=None, timeout=None, crawl_depth=-1, cache_only=False, verbose=True):
    server_name = urlsplit(url)[1]
    if cache is not None:
        cached_projects = cache.get_object(url_to_cache_name(label, url), GITLAB_PACKAGE_CACHE_VERSION, [])
    else:
        cached_projects = []
    if not cache_only and url is not None and private_token is not None and url not in _updated_urls:
        projects = []
        try:
            with requests.Session() as s:
                s.headers.update({"PRIVATE-TOKEN": private_token})
                r = s.get(urljoin(url, "api/v3/projects"), timeout=timeout)
                r.raise_for_status()
                project_list = r.json()
                for yaml_p in project_list:
                    cached_p = next((q for q in cached_projects if q.id == yaml_p["id"]), None)
                    p = GitlabProject(
                        server=server_name,
                        name=yaml_p["name_with_namespace"],
                        id=yaml_p["id"],
                        website=yaml_p["web_url"],
                        url={"ssh": yaml_p["ssh_url_to_repo"], "http": yaml_p["http_url_to_repo"]},
                        packages=None,
                        last_modified=date_parse(yaml_p["last_activity_at"]),
                        workspace_path=None
                    )
                    if cached_p is not None and cached_p.last_modified == p.last_modified:
                        p.packages = cached_p.packages
                    else:
                        if verbose:
                            sys.stdout.write("Fetching: %s\n" % p.website)
                        manifests = crawl_project_for_packages(s, url, p.id, "", depth=crawl_depth, timeout=timeout)
                        p.packages = []
                        for path, blob in manifests:
                            r = s.get(urljoin(url, "api/v3/projects/%s/repository/raw_blobs/%s" % (p.id, blob)), timeout=timeout)
                            r.raise_for_status()
                            filename = os.path.join(path, PACKAGE_MANIFEST_FILENAME)
                            xml_data = r.content
                            try:
                                manifest = parse_package_string(xml_data, filename)
                            except InvalidPackage as e:
                                warning("'%s' hosts invalid package '%s': %s\n" % (p.website, filename, str(e)))
                                manifest = None
                            p.packages.append(GitlabPackage(manifest=manifest, project=p, project_path=path, manifest_blob=blob, manifest_xml=xml_data))
                    projects.append(p)
        except IOError as e:
            error("cannot update from %s: %s\n" % (url, e))
            projects = cached_projects
        if cache is not None:
            _updated_urls.add(url)
    else:
        projects = cached_projects
    if cache is not None:
        cache.set_object(url_to_cache_name(label, url), GITLAB_PACKAGE_CACHE_VERSION, projects)
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
    def repo_has_project_url(repo, project):
        for r in repo.remotes:
            for _, url in iteritems(project.url):
                if r.url == url:
                    return True
        return False
    base_path = srcdir if subdir is None else os.path.join(srcdir, subdir)
    result = []
    foreign = []
    for curdir, subdirs, _ in os.walk(base_path, followlinks=True):
        if ".git" in subdirs:
            repo = Repo(curdir)
            path = os.path.relpath(curdir, srcdir)
            for project in projects:
                if repo_has_project_url(repo, project):
                    assert project.workspace_path is None or project.workspace_path == path
                    project.workspace_path = path
                    result.append(project)
                    break
            else:
                foreign.append(os.path.relpath(curdir, srcdir))
            del subdirs[:]
        else:
            subdirs = [s for s in subdirs if not s.startswith(".")]
    return result, foreign


def get_gitlab_projects(wsdir, config, cache=None, offline_mode=False, verbose=True):
    gitlab_projects = []
    if "gitlab_servers" in config:
        for gitlab_cfg in config["gitlab_servers"]:
            label = gitlab_cfg.get("label", None)
            url = gitlab_cfg.get("url", None)
            private_token = gitlab_cfg.get("private_token", None)
            if url is not None and private_token is None:
                private_token = acquire_gitlab_private_token(label, url)
            gitlab_projects += find_available_gitlab_projects(label, url, private_token=private_token, cache=cache, cache_only=offline_mode, verbose=verbose)
    return gitlab_projects


def make_gitlab_distfile(url, private_token=None, cache=None, timeout=None, verbose=True):
    projects = find_available_gitlab_projects(url, private_token=private_token, cache=cache, timeout=timeout, verbose=verbose)
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
            "last_modified": prj.last_modified.isoformat(),
            "packages": packages,
        })
    return yaml.safe_dump(result, default_flow_style=False)
