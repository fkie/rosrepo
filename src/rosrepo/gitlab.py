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
from .util import iteritems, NamedTuple


GITLAB_PACKAGE_CACHE_VERSION = 1

class GitlabProject(NamedTuple):
    __slots__ = ("server", "name", "id", "website", "url", "packages", "last_modified", "workspace_path")

class GitlabPackage(NamedTuple):
    __slots__ = ("manifest", "project", "project_path", "manifest_blob", "manifest_xml")


def url_to_cache_name(url):
    _, tail = url.split("://", 1)
    return "_".join(["gitlab_projects", urlquote(tail, safe="")])


def crawl_project_for_packages(session, url, project_id, path, depth, timeout):
    r = session.get(urljoin(url, "api/v3/projects/%s/repository/tree" % project_id), params={"path": path})
    if r.status_code == 200:
        entries = r.json()
        files = [e["name"] for e in entries if e["type"] == "blob"]
        dirs = [e["name"] for e in entries if e["type"] == "tree" and not e["name"].startswith(".")]
        if "CATKIN_IGNORE" in files: return []
        for e in entries:
            if e["type"] == "blob" and e["name"] == PACKAGE_MANIFEST_FILENAME:
                return [(path, e["id"])]
        if depth == 0: return []
        result = [] 
        for d in dirs:
            result += crawl_project_for_packages(session, url, project_id, os.path.join(path, d), depth - 1, timeout)
        return result
    return []


def acquire_gitlab_private_token(url):
    from getpass import getpass
    sys.stderr.write ("Authentication required for %s\n" % url)
    sys.stderr.flush()
    while True:
        login = raw_input("Username: ")
        if login == "": continue
        passwd = getpass("Password: ")
        if passwd == "":
            sys.stderr.write("Starting over\n\n") 
            continue
        r = requests.post(urljoin(url, "api/v3/session"), data={"login": login, "password": passwd})
        if r.status_code == 401:
            sys.stderr.write("Access denied\n")
            continue
        r.raise_for_status()
        break
    return r.json()["private_token"]


def find_available_gitlab_projects(url, private_token=None, cache=None, timeout=None, crawl_depth=-1, cache_only=False, verbose=True):
    server_name = urlsplit(url)[1]
    if cache is not None:
        cached_projects = cache.get_object(url_to_cache_name(url), GITLAB_PACKAGE_CACHE_VERSION, [])
    else:
        cached_projects = []
    if not cache_only and private_token is not None:
        projects = []
        try:
            with requests.Session() as s:
                if verbose: sys.stdout.write("Fetching: %s\n" % url)
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
                        if verbose: sys.stdout.write ("Fetching: %s\n" % p.website)
                        manifests = crawl_project_for_packages(s, url, p.id, "", depth=crawl_depth, timeout=timeout)
                        p.packages = []
                        for path, blob in manifests:
                            r = s.get(urljoin(url, "api/v3/projects/%s/repository/raw_blobs/%s"% (p.id, blob)), timeout=timeout)
                            r.raise_for_status()
                            filename = os.path.join(path, PACKAGE_MANIFEST_FILENAME)
                            xml_data = r.content
                            try:
                                manifest = parse_package_string(xml_data, filename)
                            except InvalidPackage as e:
                                sys.stdout.write("Ignoring %s: %s\n" % (filename, str(e)))
                                manifest = None
                            p.packages.append(GitlabPackage(manifest=manifest, project=p, project_path=path, manifest_blob=blob, manifest_xml=xml_data))
                    projects.append(p)
        except IOError as e:
            if verbose: sys.stdout.write("Error while updating from %s: %s\n" % (url, e))
            projects = cached_projects
    else:
        projects = cached_projects
    if cache is not None:
        cache.set_object(url_to_cache_name(url), GITLAB_PACKAGE_CACHE_VERSION, projects)
    return projects


def find_catkin_packages_from_gitlab_projects(projects, result=None):
    if result is None: result = {}
    for prj in projects:
        for pkg in prj.packages:
            if not pkg.manifest.name in result: result[pkg.manifest.name] = []
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
    for curdir, subdirs, _ in os.walk(base_path, followlinks=True):
        if ".git" in subdirs:
            repo = Repo(curdir)
            path = os.path.relpath(curdir, srcdir)
            for project in projects:
                if repo_has_project_url(repo, project):
                    assert project.workspace_path is None or project.workspace_path == path
                    project.workspace_path = path
                    result.append(project)
        subdirs = [s for s in subdirs if not s.startswith(".")]
    return result


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
        if not prj.server in result: result[prj.server] = []
        result[prj.server].append({
            "id": prj.id,
            "name": prj.name,
            "website": prj.website,
            "url": prj.url,
            "last_modified": prj.last_modified.isoformat(),
            "packages": packages,
        })
    return yaml.safe_dump(result, default_flow_style=False)

