#!/usr/bin/env python3
"""Add FEBio discrete elements (chordae) as rods to an already exported case, from the run's model.feb.

For cases whose VTK frames no longer exist (so export_case.py --lines cannot be re-run). The result is the
same bundle layout export_case.py writes with --lines: rod ends that coincide with a surface vertex of
frame 0 (the reference state) use that vertex; the other ends are appended as extra vertices with NaN
fields. Appended ends must belong to a node set with a zero-displacement BC in the deck (e.g. fixed
papillary tips), since their motion is not in the bundle; they are then held at their deck coordinates.

    add_lines_from_feb.py clip_rv4mmHg runs/01_clip_rv4mmHg/model.feb --set Chordae --fixed-set PapillaryNodes \
        --radius 0.07

Unencrypted cases only. Re-run make_preview.py afterwards.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

SITE = Path(__file__).resolve().parent.parent / "site"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case")
    ap.add_argument("feb")
    ap.add_argument("--set", default="Chordae", help="DiscreteSet name in model.feb")
    ap.add_argument("--label", default="Chordae", help="rod label shown in the viewer")
    ap.add_argument("--fixed-set", default="PapillaryNodes",
                    help="node set (zero displacement in the deck) allowed for rod ends that are not surface vertices")
    ap.add_argument("--radius", type=float, default=0.07)
    ap.add_argument("--tol", type=float, default=1e-3, help="max distance (model units) end node -> surface vertex")
    args = ap.parse_args()

    out = SITE / "cases" / args.case
    meta = json.loads((out / "meta.json").read_text())
    if meta.get("encrypted"):
        sys.exit("encrypted case: not supported")
    if meta.get("lines"):
        sys.exit("case already has rods")
    data = (out / "data.bin").read_bytes()

    def blob(key, dt):
        o, n = meta["offsets"][key]
        return np.frombuffer(data[o:o + n], dt)

    nF, nV = meta["nFrames"], meta["nVerts"]
    indices = blob("indices", np.uint32)
    pos = blob("positions", np.float32).reshape(nF, nV, 3)
    fields = {k[6:]: blob(k, np.float32).reshape(nF, nV) for k in meta["offsets"] if k.startswith("field:")}

    feb = Path(args.feb).read_text()
    coords = {int(i): np.array([float(v) for v in xyz.split(",")])
              for i, xyz in re.findall(r'<node id="(\d+)">([^<]+)</node>', feb)}
    m = re.search(rf'<DiscreteSet name="{re.escape(args.set)}">(.*?)</DiscreteSet>', feb, re.S)
    if not m:
        sys.exit(f"DiscreteSet {args.set} not found")
    pairs = np.array([[int(a), int(b)] for a, b in re.findall(r"<delem>\s*(\d+)\s*,\s*(\d+)\s*</delem>", m.group(1))])
    m = re.search(rf'<NodeSet name="{re.escape(args.fixed_set)}">(.*?)</NodeSet>', feb, re.S)
    fixed = {int(x) for x in re.findall(r"\d+", m.group(1))} if m else set()
    if not re.search(rf'node_set="{re.escape(args.fixed_set)}"\s+type="zero displacement"', feb):
        fixed = set()
    print(f"{len(pairs)} discrete elements in {args.set}; {len(fixed)} nodes in fixed set {args.fixed_set}")

    tree = cKDTree(pos[0])
    lookup, extra = {}, []
    for nid in sorted(set(pairs.reshape(-1).tolist())):
        d, k = tree.query(coords[nid])
        if d <= args.tol:
            lookup[nid] = int(k)
        elif nid in fixed:
            lookup[nid] = nV + len(extra)
            extra.append(nid)
        else:
            sys.exit(f"node {nid}: {d:.4f} from the nearest surface vertex and not in a fixed set")
    line_pairs = np.vectorize(lookup.get)(pairs).astype(np.uint32)
    print(f"rods: {len(line_pairs)} segments, {len(lookup) - len(extra)} ends on surface vertices, "
          f"{len(extra)} appended fixed ends")

    xp = np.array([coords[n] for n in extra], np.float32)
    pos2 = np.concatenate([pos, np.broadcast_to(xp, (nF, len(extra), 3))], axis=1)
    pad = np.full((nF, len(extra)), np.nan, np.float32)

    offsets, blobs, cursor = {}, [], 0

    def add(key, arr):
        nonlocal cursor
        b = np.ascontiguousarray(arr).tobytes()
        offsets[key] = [cursor, len(b)]
        blobs.append(b)
        cursor += len(b)

    add("indices", indices)
    add("positions", pos2)
    add("lines", line_pairs.reshape(-1))
    for f in meta["fields"]:
        add(f"field:{f['name']}", np.concatenate([fields[f["name"]], pad], axis=1))
    new = b"".join(blobs)
    lo, hi = pos2.reshape(-1, 3).min(0), pos2.reshape(-1, 3).max(0)
    meta.update(nVerts=nV + len(extra), lines={"name": args.label, "count": int(len(line_pairs)), "radius": args.radius},
                bbox=[lo.tolist(), hi.tolist()], offsets=offsets, byteLength=len(new))
    (out / "data.bin").write_bytes(new)
    (out / "meta.json").write_text(json.dumps(meta))

    index_path = SITE / "cases" / "index.json"
    index = json.loads(index_path.read_text())
    for c in index:
        if c["name"] == args.case:
            c.update(nVerts=meta["nVerts"], sizeMB=round(len(new) / 1e6, 1))
    index_path.write_text(json.dumps(index, indent=1))
    print(f"wrote {out} ({len(new) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
