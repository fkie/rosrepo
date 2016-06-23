"""
Copyright (c) 2016 Fraunhofer FKIE

"""

def find_depends(packages, ws_avail, gitlab_avail):
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
            else:
                missing.add(name)
    return depends, missing
