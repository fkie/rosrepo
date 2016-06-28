"""
Copyright (c) 2016 Fraunhofer FKIE

"""
from .ui import pick_dependency_resolution, msg, warning, error, escape


class Rosdep(object):

    def __init__(self, view=None):
        self.view = view

    def is_ros(self, name):
        if self.view is None:
            return False
        try:
            return self.view.lookup(name).data["_is_ros"]
        except KeyError:
            return False

    def __contains__(self, name):
        if self.view is None:
            return False
        return name in self.view.keys()

    def __getitem__(self, name):
        if self.view is None:
            raise KeyError("No such package")
        return self.view.lookup(name)

    def ok(self):
        return self.view is not None


def get_rosdep():
    try:
        from rosdep2.lookup import RosdepLookup
        from rosdep2.rospkg_loader import DEFAULT_VIEW_KEY
        from rosdep2.sources_list import SourcesListLoader
        sources_loader = SourcesListLoader.create_default()
        lookup = RosdepLookup.create_from_rospkg(sources_loader=sources_loader)
        return Rosdep(view=lookup.get_rosdep_view(DEFAULT_VIEW_KEY))
    except ImportError:
        return Rosdep(view=None)


def show_fallback(fallback):
    for name in sorted(fallback.keys()):
        warning("using system package '%s'\n" % escape(name))
        for reason in fallback[name]:
            msg("   - %s\n" % reason, indent_next=5)


def show_conflicts(conflicts):
    for name in sorted(conflicts.keys()):
        error("cannot use package '%s'\n" % escape(name))
        for reason in conflicts[name]:
            msg("   - %s\n" % reason, indent_next=5)


def find_dependees(packages, ws_state, auto_resolve=False):
    def try_resolve(queue, depends, fallback, conflicts):
        if depends is None:
            depends = {}
        if fallback is None:
            fallback = {}
        if conflicts is None:
            conflicts = {}
        while len(queue) > 0:
            root_depender, depender, name = queue.pop()
            if name not in depends and name not in conflicts and name not in fallback:
                resolver_msgs = []
                if root_depender is not None and root_depender != depender:
                    resolver_msgs.append("is needed to resolve dependencies of package @{cf}%s@|" % escape(root_depender))
                if depender is not None:
                    resolver_msgs.append("is dependee of package @{cf}%s@|" % escape(depender))
                if name in ws_state.ws_packages:
                    # If the package is in the workspace, we assume it's unique and take the first in the list
                    depends[name] = ws_state.ws_packages[name][0]
                    manifest = ws_state.ws_packages[name][0].manifest
                    queue += [(root_depender, name, p.name) for p in manifest.buildtool_depends + manifest.build_depends + manifest.run_depends + manifest.test_depends]
                elif name in ws_state.gitlab_packages:
                    # Package is not in workspace, so we may have multiple sources
                    # to download it from. However, since each Gitlab project
                    # may contain multiple packages, we must verify that no other
                    # package conflicts with one that's already in the workspace
                    can_resolve = False
                    best_depends = depends
                    best_fallback = fallback
                    candidates = []
                    resolver_msgs.append("is not in workspace (or disabled with @{cf}CATKIN_IGNORE@|)")
                    for pkg in ws_state.gitlab_packages[name]:
                        # Is the package project in the workspace already?
                        if pkg.project in ws_state.ws_projects:
                            resolver_msgs.append("cannot be cloned from @{cf}%s@| because that repository is cloned in @{cf}%s/@| already" % (escape(pkg.project.name), escape(pkg.project.workspace_path)))
                            continue  # Fail
                        # Check other packages in the same Gitlab project
                        for other in pkg.project.packages:
                            # Is the other package in the workspace already?
                            if other.manifest.name in ws_state.ws_packages:
                                resolver_msgs.append("cannot be cloned from @{cf}%s@| because package @{cf}%s@| is in the workspace already" % (escape(pkg.project.name), escape(other.manifest.name)))
                                break  # Fail
                            # If not, check if we already decided to download
                            # the package from another project
                            if other.manifest.name in depends:
                                # Is it the same project?
                                if other.project != pkg.project:
                                    resolver_msgs.append("cannot be cloned from @{cf}%s@| because it contains package @{cf}%s@| which will be cloned from @{cf}%s@|" % (escape(pkg.project.name), escape(other.manifest.name), escape(other.project.name)))
                                    break  # Fail
                        else:
                            # The chosen package does not create any conflicts
                            candidates.append(pkg)
                    if len(candidates) > 1 and not auto_resolve:
                        # If desired, let the user pick one
                        result = pick_dependency_resolution(name, candidates)
                        if result is not None:
                            candidates = [result]
                    for pkg in candidates:
                        old_queue = list(queue)
                        depends[name] = pkg
                        manifest = pkg.manifest
                        queue += [(root_depender, name, p.name) for p in manifest.buildtool_depends + manifest.build_depends + manifest.run_depends + manifest.test_depends]
                        new_depends, new_fallback, new_conflicts = try_resolve(queue, depends.copy(), fallback.copy(), None)
                        conflicts.update(new_conflicts)
                        if not new_conflicts:
                            # We can build a consistent workspace with that
                            # If we have multiple choices, we pick the one with
                            # the smallest number of soft-conflicts
                            if not can_resolve or len(new_fallback) < len(best_fallback):
                                can_resolve = True
                                best_depends = new_depends
                                best_fallback = new_fallback
                        # Try next available package
                        queue = old_queue
                        del depends[name]
                    if can_resolve:
                        depends = best_depends
                        fallback = best_fallback
                    elif name in rosdep:
                        fallback[name] = resolver_msgs
                    else:
                        resolver_msgs.append("is not installable as system package")
                        conflicts[name] = resolver_msgs
                    return depends, fallback, conflicts
                elif name not in rosdep:
                    resolver_msgs.append("is not in workspace (or disabled with @{cf}CATKIN_IGNORE@|)")
                    resolver_msgs.append("is not available from any Gitlab project")
                    resolver_msgs.append("is not installable as system package")
                    conflicts[name] = resolver_msgs
        return depends, fallback, conflicts
    rosdep = get_rosdep()
    queue = [(None, None, name) for name in packages]
    depends, fallback, conflicts = try_resolve(queue, None, None, None)
    return depends, fallback, conflicts
