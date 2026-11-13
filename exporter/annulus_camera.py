#!/usr/bin/env python3
"""Set a case's start pose and thumbnail pose to look straight down the normal of its rod ring.

The ring is the case's rods (export_case.py --lines, e.g. the valve annulus). The camera looks
along the normal of the ring's best-fit plane, from the side the normal points to (+z side by
default), centred on the model as projected onto the ring plane, at a distance that fits every
vertex in the viewer's 40-degree field of view at --aspect. Screen-up is a global axis projected into the plane.

    python3 exporter/annulus_camera.py biv_wall_ocs13 [--up y | --up-vec=-1,0,0] [--side +z] [--margin 1.08]
    python3 exporter/annulus_camera.py clip_rv4mmHg --keep-pose --up-vec=-0.5194,0.8545,0   # only rotate screen-up
    python3 exporter/make_preview.py biv_wall_ocs13 --frames 1     # re-render the preview

Writes defaults.camera and defaults.thumbCamera (absolute pos/target/up) into meta.json.
Encrypted cases are not supported (data.bin is read directly).
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np

SITE = Path(__file__).resolve().parent.parent / "site"
FOV_DEG = 40.0  # site/js/viewer.js PerspectiveCamera


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name")
    ap.add_argument("--up", default="y", choices=["x", "y", "z", "-x", "-y", "-z"],
                    help="global axis that points up on screen (projected into the ring plane)")
    ap.add_argument("--up-vec", help="screen-up as a vector 'x,y,z' (projected into the view plane); overrides --up. "
                         "E.g. the septal leaflet's arc-midpoint direction, to put the septal leaflet at the top")
    ap.add_argument("--keep-pose", action="store_true",
                    help="keep the case's current camera pos/target and only replace its screen-up (for cases "
                         "without a rod ring, e.g. the clip-in-RV runs)")
    ap.add_argument("--ring-json", help="JSON list of [x, y, z] ring points in the case's coordinates, for cases "
                         "without rods (e.g. the valve annulus of a clip-in-RV run, placed with its coupling.json)")
    ap.add_argument("--side", default="+z", help="look from the side of the ring this axis points to")
    ap.add_argument("--margin", type=float, default=1.08, help="extra distance factor around the fitted model")
    ap.add_argument("--aspect", type=float, default=16 / 9, help="viewport width/height to fit (preview: 1200x675)")
    ap.add_argument("--site", default=str(SITE))
    a = ap.parse_args()

    case = Path(a.site) / "cases" / a.name
    meta = json.loads((case / "meta.json").read_text())
    if a.keep_pose:
        if not a.up_vec:
            raise SystemExit("--keep-pose needs --up-vec")
        for key in ("camera", "thumbCamera"):
            cam = meta.get("defaults", {}).get(key)
            if not cam:
                raise SystemExit(f"case has no defaults.{key} to keep")
            view = np.subtract(cam["target"], cam["pos"]); view /= np.linalg.norm(view)
            u = np.asarray([float(x) for x in a.up_vec.split(",")]); u = u - (u @ view) * view
            cam["up"] = [round(float(x), 4) for x in u / np.linalg.norm(u)]
            print(f"{a.name}: {key} up -> {cam['up']} (pos/target kept)")
        (case / "meta.json").write_text(json.dumps(meta, indent=1))
        return
    if meta.get("encrypted"):
        raise SystemExit("encrypted case: not supported")
    buf = (case / "data.bin").read_bytes()
    o = meta["offsets"]
    nv = meta["nVerts"]
    pos = np.frombuffer(buf, np.float32, nv * 3, o["positions"][0]).reshape(nv, 3).astype(float)  # frame 0
    if a.ring_json:
        ring = np.asarray(json.loads(Path(a.ring_json).read_text()), float)
    elif meta.get("lines"):
        seg = np.frombuffer(buf, np.uint32, o["lines"][1] // 4, o["lines"][0]).reshape(-1, 2)
        ring = pos[np.unique(seg)]
    else:
        raise SystemExit("case has no rods (export with --lines) to define the ring; pass --ring-json")

    c = ring.mean(axis=0)
    n = np.linalg.svd(ring - c)[2][2]
    ax = {"x": 0, "y": 1, "z": 2}
    side = np.zeros(3); side[ax[a.side[-1]]] = -1.0 if a.side.startswith("-") else 1.0
    if n @ side < 0:
        n = -n
    up = np.zeros(3); up[ax[a.up[-1]]] = -1.0 if a.up.startswith("-") else 1.0
    if a.up_vec:
        up = np.asarray([float(x) for x in a.up_vec.split(",")])
    up = up - (up @ n) * n
    if np.linalg.norm(up) < 1e-6:
        raise SystemExit(f"--up {a.up} is parallel to the ring normal; pick another axis")
    up /= np.linalg.norm(up)
    right = np.cross(n, up)

    # Look straight down the normal, but centre the frame on the whole model as projected onto the
    # ring plane (the ring sits off to one side of a BiV), and fit it to a --aspect viewport.
    d = pos - c
    u, r = d @ up, d @ right
    c = c + 0.5 * (u.max() + u.min()) * up + 0.5 * (r.max() + r.min()) * right
    d = pos - c
    half_v = math.tan(math.radians(FOV_DEG / 2))
    half_h = half_v * a.aspect
    front = d @ n  # height of each vertex towards the camera
    dist = a.margin * max(np.max(np.abs(d @ up) / half_v + front), np.max(np.abs(d @ right) / half_h + front))

    cam = {"pos": [round(float(x), 3) for x in c + dist * n],
           "target": [round(float(x), 3) for x in c],
           "up": [round(float(x), 4) for x in up]}
    meta.setdefault("defaults", {})
    meta["defaults"]["camera"] = cam
    meta["defaults"]["thumbCamera"] = cam
    (case / "meta.json").write_text(json.dumps(meta, indent=1))
    tilt = math.degrees(math.acos(min(1.0, abs(n[2]))))
    print(f"{a.name}: ring {len(ring)} pts, target {np.round(c, 2).tolist()}, normal {np.round(n, 4).tolist()} "
          f"({tilt:.1f} deg from z), distance {dist:.1f}")


if __name__ == "__main__":
    main()
