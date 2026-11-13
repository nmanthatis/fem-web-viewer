#!/usr/bin/env python3
"""Turn a solid saved in a Cubit .cub5 into a static .vtu for export_case.py (no mesh needed).

Cubit tessellates the solid's surfaces (exporter/cubit/solid_facets.py, run in batch); every
surface is assigned to a region by the nearest reference volume saved alongside it, and each
region becomes one part_id. An optional closed curve (e.g. the valve annulus) is added as 2-node
line cells under its own part_id, for export_case.py --lines.

    python3 exporter/cubit_solid_to_vtu.py RUN/checkpoint_solid.cub5 --out work/ocs13.vtu \
        --annulus-json annulus.json
    python3 exporter/export_case.py work/ocs13.vtu --name ... --parts 0,1,2,3 \
        --part-names "0=LV endo,1=RV endo,2=Trunk lumen,3=Outer wall" --lines Annulus --line-parts 9

The defaults fit biventricular's checkpoint_solid.cub5 (volume biv_wall_solid and the four
*_ref volumes that label_surfaces.py uses).
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pyvista as pv

HERE = Path(__file__).resolve().parent
REGIONS = {"lv_endo_ref": 0, "rv_endo_ref": 1, "trunk_inner_ref": 2, "epi_ref": 3}
ANNULUS_PART = 9


def read_facets(path):
    """Cubit `export facets` text: n_vertices, 'i x y z' lines, n_triangles, 'i a b c' lines."""
    lines = Path(path).read_text().split("\n")
    n = int(lines[0])
    pts = np.array([l.split()[1:4] for l in lines[1:n + 1]], float)
    k = int(lines[n + 1])
    tri = np.array([l.split()[1:4] for l in lines[n + 2:n + 2 + k]], np.int64)
    return pts, tri - tri.min()  # 0- or 1-based depending on the Cubit version


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cub5")
    ap.add_argument("--out", required=True, help="output .vtu")
    ap.add_argument("--volume", default="biv_wall_solid")
    ap.add_argument("--annulus-json", help="JSON list of [x, y, z] points of a closed curve, added as line cells")
    ap.add_argument("--cubit", default="coreform_cubit")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as w:
        job = {"cub5": str(Path(args.cub5).resolve()), "volume": args.volume, "refs": list(REGIONS)}
        Path(w, "job.json").write_text(json.dumps(job))
        r = subprocess.run([args.cubit, "-batch", "-nographics", "-nojournal", str(HERE / "cubit" / "solid_facets.py")],
                           cwd=w, capture_output=True, text=True)
        if not Path(w, "surfaces.json").exists():
            raise SystemExit("Cubit did not write surfaces.json:\n" + r.stdout[-3000:] + r.stderr[-2000:])
        info = json.loads(Path(w, "surfaces.json").read_text())
        pts_all, cells, ctype, part = [], [], [], []
        off = 0
        for s in info["surfaces"]:
            p, t = read_facets(Path(w, s["facets"]))
            # the wedge outer skin ends on the annulus ridge, where the RV endo is equally close
            region = "epi_ref" if s["name"].startswith("wedge_outer_side") else s["region"]
            # flat cut faces (LV top, trunk top) are outer wall, not lumen, even if a lumen is nearest
            if s.get("planar") and region in ("lv_endo_ref", "trunk_inner_ref"):
                region = "epi_ref"
            pid = REGIONS.get(region, 3)
            pts_all.append(p)
            for a, b, c in t + off:
                cells += [3, a, b, c]
            ctype += [pv.CellType.TRIANGLE] * len(t)
            part += [pid] * len(t)
            off += len(p)
            print(f"  surface {s['id']:4d} {s['name'][:24]:24s} -> {region:16s} {len(t):6d} tris")

    if args.annulus_json:
        a = np.asarray(json.loads(Path(args.annulus_json).read_text()), float)
        pts_all.append(a)
        n = len(a)
        for i in range(n):
            cells += [2, off + i, off + (i + 1) % n]
        ctype += [pv.CellType.LINE] * n
        part += [ANNULUS_PART] * n
        off += n

    grid = pv.UnstructuredGrid(np.asarray(cells, np.int64), np.asarray(ctype, np.uint8), np.vstack(pts_all))
    grid.cell_data["part_id"] = np.asarray(part, np.int32)
    # Surfaces keep their own copies of shared edge vertices on purpose: the viewer's smooth
    # normals then stop at the CAD edges, so creases (rim, trunk root) stay sharp.
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    grid.save(args.out)
    counts = {int(k): int(v) for k, v in zip(*np.unique(part, return_counts=True))}
    print(f"wrote {args.out}: {grid.n_points} points, cells per part {counts}")


if __name__ == "__main__":
    main()
