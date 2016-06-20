"""
Copyright (c) 2016 Fraunhofer FKIE

"""
import requests
import sys
import os
import yaml
from urllib import quote as urlquote
from catkin_pkg.package import parse_package_string, InvalidPackage, PACKAGE_MANIFEST_FILENAME
try:
    from urlparse import urljoin, urlsplit, urlunsplit
except ImportError:
    from urllib.parse import urljoin, urlsplit, urlunsplit
from .util import iteritems


def url_to_cache_name(url):
    _, tail = url.split("://", 1)
    return "_".join(["remote_packages", urlquote(tail, safe="")])


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


def find_gitlab_packages(remote_uri, auth_token=None, cache=None, timeout=None, crawl_depth=-1, download=False):
    url = urlunsplit(urlsplit(remote_uri))
    if cache is not None:
        cached_projects = cache.get_object(url_to_cache_name(url), 1, {})
    else:
        cached_projects = {}
    if download:
        projects = {}
        try:
            with requests.Session() as s:
                s.headers.update({"PRIVATE-TOKEN": auth_token})
                r = s.get(urljoin(url, "api/v3/projects"), timeout=timeout)
                r.raise_for_status()
                project_list = r.json()
                for p in project_list:
                    project_id = p["id"]
                    web_url = p["web_url"]
                    cur_ts = p["last_activity_at"]
                    old_ts = cached_projects[project_id]["t"] if project_id in cached_projects else ""
                    if cur_ts == old_ts:
                        packages = cached_projects[project_id]["packages"]
                        sys.stdout.write ("Cached: %s\n" % web_url)
                    else:
                        sys.stdout.write ("Reading: %s\n" % web_url)
                        manifests = crawl_project_for_packages(s, url, project_id, "", depth=crawl_depth, timeout=timeout)
                        packages = []
                        for path, blob in manifests:
                            r = s.get(urljoin(url, "api/v3/projects/%s/repository/raw_blobs/%s"% (project_id, blob)), timeout=timeout)
                            r.raise_for_status()
                            filename = os.path.join(path, PACKAGE_MANIFEST_FILENAME)
                            xml_data = r.content
                            try:
                                manifest = parse_package_string(xml_data, filename)
                            except InvalidPackage as e:
                                sys.stdout.write("Ignoring %s: %s\n" % (filename, str(e)))
                                manifest = None
                            packages.append((path, blob, manifest))
                    projects[p["id"]] = {
                        "website": web_url,
                        "url": {"ssh": p["ssh_url_to_repo"], "http": p["http_url_to_repo"]},
                        "packages": packages,
                        "t": p["last_activity_at"],
                    }
        except IOError as e:
            sys.stderr.write("Error while updating from %s: %s\n" % (url, e))
            projects = cached_projects
    else:
        projects = cached_projects
    result = {}
    for p_id, info in iteritems(projects):
        packages_names = [m.name for _,_,m in info["packages"]]
        for path, blob, manifest in info["packages"]:
            if not manifest.name in result: result[manifest.name] = []
            result[manifest.name].append({
                "server": url,
                "website": info["website"],
                "project": p_id,
                "url": info["url"],
                "path": path,
                "blob": blob,
                "manifest": manifest,
                "siblings": [n for n in packages_names if n != manifest.name],
                "t": info["t"],
            })
    if cache is not None:
        cache.set_object(url_to_cache_name(url), 1, projects)
    return result


def make_gitlab_distfile(remote_uri, auth_token=None, cache=None, timeout=None):
    packages = find_gitlab_packages(remote_uri, auth_token=auth_token, cache=cache, timeout=timeout, download=True)
    tmp = {}
    server = None
    with requests.Session() as s:
        s.headers.update({"PRIVATE-TOKEN": auth_token})
        for package_name, repo_list in iteritems(packages):
            for info in repo_list:
                if server is None: server = info["server"]
                assert server == info["server"]
                if not info["project"] in tmp:
                    tmp[info["project"]] = {"id": info["project"], "website": info["website"], "url": info["url"], "last_modified": info["t"], "packages": []}
                r = s.get(urljoin(server, "api/v3/projects/%s/repository/raw_blobs/%s"% (info["project"], info["blob"])), timeout=timeout)
                r.raise_for_status()
                tmp[info["project"]]["packages"].append({"name": package_name, "path": info["path"], "manifest": {"blob": info["blob"], "xml": r.content}})
    result = {server: []}
    for p in sorted(tmp.keys()):
        result[server].append(tmp[p])
    return yaml.safe_dump(result, default_flow_style=False)
