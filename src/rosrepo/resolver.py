"""
Copyright (c) 2016 Fraunhofer FKIE

"""


class Rosdep(object): # pragma: no cover

    def __init__(self, view=None):
        self.view = view

    def is_ros(self, name):
        if self.view is None: return False
        try:
            return self.view.lookup(name).data["_is_ros"]
        except KeyError:
            return False

    def has_key(self, name):
        if self.view is None: return False
        return name in self.view.keys()

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


def find_dependees(packages, ws_avail, gitlab_avail):
    rosdep = get_rosdep()
    depends = set()
    missing = set()
    queue = [name for name in packages]
    while len(queue) > 0:
        name = queue.pop()
        if not name in depends:
            if name in ws_avail:
                depends.add(name)
                manifest = ws_avail[name][0].manifest
                queue += [p.name for p in manifest.buildtool_depends + manifest.build_depends + manifest.run_depends + manifest.test_depends]
            elif name in gitlab_avail:
                depends.add(name)
                manifest = gitlab_avail[name][0].manifest
                queue += [p.name for p in manifest.buildtool_depends + manifest.build_depends + manifest.run_depends + manifest.test_depends]
            elif not rosdep.has_key(name):
                missing.add(name)
    return depends, missing
