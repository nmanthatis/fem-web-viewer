#!python
"""Cubit batch script: write the faceted surface of a saved solid, one facet file per surface,
plus a JSON that assigns every surface to a region. Geometry only: nothing is meshed and the
.cub5 is not saved.

Run from a work directory that holds job.json:
    coreform_cubit -batch -nographics -nojournal /path/to/solid_facets.py
job.json:
    {"cub5": ".../checkpoint_solid.cub5", "volume": "biv_wall_solid",
     "refs": ["lv_endo_ref", "rv_endo_ref", "trunk_inner_ref", "epi_ref"]}
Writes into the work directory: surf_<id>.facets (Cubit's `export facets` text format) and
surfaces.json. A surface goes to the reference volume whose boundary is closest to a point on it
(the idea of biventricular's label_surfaces.py, applied to geometry instead of the mesh).
"""
import json
import math
import os

import cubit

W = os.getcwd()
job = json.load(open(os.path.join(W, "job.json")))
cubit.cmd('open "%s"' % job["cub5"])
v = cubit.get_id_from_name(job["volume"])
if not v:
    raise SystemExit("volume %r not found" % job["volume"])
refs = {}
for name in job.get("refs", []):
    rid = cubit.get_id_from_name(name)
    if rid and rid != v:
        refs[name] = cubit.get_relatives("volume", rid, "surface")

out = {"volume": v, "refs_found": sorted(refs), "surfaces": []}
for s in cubit.get_relatives("volume", v, "surface"):
    p = cubit.surface(s).closest_point_trimmed(cubit.get_center_point("surface", s))
    best, bestd = "unassigned", 1e9
    for name, ss in refs.items():
        d = min(math.dist(cubit.surface(r).closest_point_trimmed(p), p) for r in ss)
        if d < bestd:
            best, bestd = name, d
    fn = os.path.join(W, "surf_%d.facets" % s)
    cubit.cmd('export facets "%s" surface %d overwrite' % (fn, s))
    out["surfaces"].append(dict(id=s, name=cubit.get_entity_name("surface", s), region=best,
                                dist=round(bestd, 4), planar=bool(cubit.surface(s).is_planar()), area=round(cubit.get_surface_area(s), 3),
                                facets=os.path.basename(fn)))
json.dump(out, open(os.path.join(W, "surfaces.json"), "w"), indent=1)
