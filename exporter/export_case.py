#!/usr/bin/env python3
"""Export a VTK time series (ParaView .pvd or a list of .vtu/.vtp/.vtk files) into a
compact web bundle for the three.js viewer in ../site.

Output: site/cases/<name>/meta.json + data.bin (or data.bin.enc with --encrypt).

data.bin (little endian, byte offsets recorded in meta.json["offsets"]):
    indices    uint32 [nTris*3]
    positions  float32 [nFrames, nVerts, 3]
    field_k    float32 [nFrames, nVerts]       (one block per exported field)

Usage examples:
    export_case.py runs/valve.pvd --name valve --title "Valve, uniform material"
    export_case.py "viz/frame_*.vtp" --name test --fields stress,displacement --decimate 0.5
    export_case.py runs/valve.pvd --name valve --frames 60 --encrypt
    export_case.py "runs/model.*.vtk" --name biv --parts 0,1,2,6 --part-names "6=RV wall" --group "Clip in RV"

Frames are resampled EVENLY IN SOLUTION TIME (project rule, see CLAUDE.md); pass
--raw-steps only when you really want the solver's adaptive steps.
"""
import argparse
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np
import pyvista as pv

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / "site"
SKIP_ARRAYS = {"vtkOriginalPointIds", "vtkOriginalCellIds", "Normals", "vtkGhostType"}
SIZE_WARN_MB = 50


# ---------------------------------------------------------------- loading
def load_frames(src: str):
    """Return (times, loader) where loader(i) -> pyvista dataset for frame i."""
    p = Path(src)
    if p.suffix.lower() == ".pvd":
        reader = pv.PVDReader(str(p))
        times = list(reader.time_values)

        def loader(i):
            reader.set_active_time_value(times[i])
            return _combine(reader.read())

        return times, loader

    files = sorted(glob.glob(src), key=_natural) if any(c in src for c in "*?[") else [src]
    if not files:
        sys.exit(f"no files match {src!r}")
    times = [_file_time(f, i) for i, f in enumerate(files)]
    return times, lambda i: _combine(pv.read(files[i]))


def _natural(path):
    """model.10.vtk sorts after model.9.vtk, not after model.1.vtk."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", path)]


def _file_time(path, fallback):
    """FEBio's legacy VTK export stores the solution time in the header title line ('time 0.1234')."""
    try:
        with open(path, "rb") as fh:
            fh.readline()
            m = re.match(rb"\s*time\s+([-+0-9.eE]+)", fh.readline())
            if m:
                return float(m.group(1))
    except OSError:
        pass
    return float(fallback)


def _combine(ds):
    if isinstance(ds, pv.MultiBlock):
        ds = ds.combine(merge_points=False)
    return ds


# ---------------------------------------------------------------- surface
def to_surface(ds, parts=None):
    """Triangulated outer surface with vtkOriginalPointIds/CellIds attached."""
    if parts is not None and "part_id" in ds.cell_data:
        keep = np.isin(np.asarray(ds.cell_data["part_id"]), parts)
        ds = ds.extract_cells(np.flatnonzero(keep))
    surf = ds.extract_surface(pass_pointid=True, pass_cellid=True, algorithm="dataset_surface")
    return surf.triangulate()


def pick_fields(surf, requested):
    names = {}
    for n in surf.point_data.keys():
        if n not in SKIP_ARRAYS:
            names[n] = "point"
    for n in surf.cell_data.keys():
        if n not in SKIP_ARRAYS and n not in names:
            names[n] = "cell"
    if requested:
        missing = [r for r in requested if r not in names]
        if missing:
            sys.exit(f"fields not found: {missing}. Available: {sorted(names)}")
        names = {r: names[r] for r in requested}
    return names


def field_arrays(surf, name, assoc, components):
    """Yield (export_name, 1-D float32 array per vertex) for one data array."""
    if assoc == "cell":
        # average cell values to the points of the surface
        tmp = pv.PolyData(surf.points, surf.faces)
        tmp.cell_data[name] = surf.cell_data[name]
        arr = np.asarray(tmp.cell_data_to_point_data().point_data[name])
    else:
        arr = np.asarray(surf.point_data[name])
    arr = arr.astype(np.float32)
    if arr.ndim == 1 or arr.shape[1] == 1:
        yield name, arr.reshape(-1)
        return
    if arr.shape[1] == 3:
        yield f"{name}|mag", np.linalg.norm(arr, axis=1)
        if components:
            for i, c in enumerate("xyz"):
                yield f"{name}|{c}", arr[:, i]
    elif arr.shape[1] in (6, 9):
        # symmetric tensor (xx yy zz xy yz xz) or full 3x3: export von Mises-like invariant + components
        if arr.shape[1] == 9:
            t = arr.reshape(-1, 3, 3)
            xx, yy, zz = t[:, 0, 0], t[:, 1, 1], t[:, 2, 2]
            xy, yz, xz = t[:, 0, 1], t[:, 1, 2], t[:, 0, 2]
        else:
            xx, yy, zz, xy, yz, xz = arr.T
        vm = np.sqrt(0.5 * ((xx - yy) ** 2 + (yy - zz) ** 2 + (zz - xx) ** 2) + 3 * (xy**2 + yz**2 + xz**2))
        yield f"{name}|vm", vm.astype(np.float32)
        yield f"{name}|trace", (xx + yy + zz).astype(np.float32)
        sym = np.empty((len(xx), 3, 3), np.float32)
        sym[:, 0, 0], sym[:, 1, 1], sym[:, 2, 2] = xx, yy, zz
        sym[:, 0, 1] = sym[:, 1, 0] = xy; sym[:, 1, 2] = sym[:, 2, 1] = yz; sym[:, 0, 2] = sym[:, 2, 0] = xz
        yield f"{name}|p1", np.linalg.eigvalsh(sym)[:, 2].astype(np.float32)  # max principal
        if components:
            for lab, comp in zip(("xx", "yy", "zz", "xy", "yz", "xz"), (xx, yy, zz, xy, yz, xz)):
                yield f"{name}|{lab}", comp.astype(np.float32)
    else:
        for i in range(arr.shape[1]):
            yield f"{name}|{i}", arr[:, i]


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help=".pvd file, a single file, or a quoted glob of per-frame files")
    ap.add_argument("--name", required=True, help="case id (folder name, url-safe)")
    ap.add_argument("--title", help="human title shown in the gallery (default: name)")
    ap.add_argument("--description", default="")
    ap.add_argument("--fields", help="comma-separated arrays to export (default: all)")
    ap.add_argument("--components", action="store_true", help="also export vector/tensor components")
    ap.add_argument("--decimate", type=float, default=0.0, help="fraction of triangles to remove, 0-1")
    ap.add_argument("--stride", type=int, default=1, help="keep every k-th solver frame (only with --raw-steps)")
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--frames", type=int, default=40,
                    help="number of output frames, evenly spaced in solution time (linear interpolation between solver steps)")
    ap.add_argument("--raw-steps", action="store_true",
                    help="export the solver's own (adaptive, non-uniform) steps instead of resampling linearly in time")
    ap.add_argument("--parts", help="comma-separated part_id values to keep (default: all)")
    ap.add_argument("--part-names", help="labels for parts, e.g. '0=anterior leaflet,6=RV wall'")
    ap.add_argument("--group", default="", help="gallery section this case is listed under")
    ap.add_argument("--encrypt", action="store_true", help="AES-GCM encrypt data.bin")
    ap.add_argument("--passphrase", help="use this passphrase instead of a random one")
    ap.add_argument("--site", default=str(SITE), help="site directory (default ../site)")
    ap.add_argument("--base-url", default="", help="public site URL, used only to print the share link")
    args = ap.parse_args()

    times, load = load_frames(args.src)
    if args.raw_steps or len(times) < 3:
        idx = list(range(0, len(times), args.stride))
        if args.max_frames:
            idx = idx[: args.max_frames]
        plan = [(i, i, 0.0, times[i]) for i in idx]  # (frame a, frame b, weight of b, time)
    else:
        # Project rule: output frames are uniform in solution time. Solver steps are adaptive
        # (dense where convergence is hard), so each output time is linearly interpolated
        # between the two bracketing steps.
        t = np.asarray(times, float)
        targets = np.linspace(t[0], t[-1], args.frames)
        plan = []
        for tt in targets:
            b = int(np.clip(np.searchsorted(t, tt, side="right"), 1, len(t) - 1))
            a = b - 1
            w = 0.0 if t[b] == t[a] else float((tt - t[a]) / (t[b] - t[a]))
            plan.append((a, b, w, float(tt)))
    print(f"{len(times)} solver frames found (t = {times[0]:g} .. {times[-1]:g}), exporting {len(plan)}"
          + ("" if args.raw_steps else " evenly spaced in time"))
    idx = [a for a, _, _, _ in plan]

    parts = [int(x) for x in args.parts.split(",")] if args.parts else None
    cache = {}

    def surface(i):
        if i not in cache:
            if len(cache) > 2:
                cache.pop(min(cache))
            cache[i] = to_surface(load(i), parts)
        return cache[i]

    # --- frame 0 defines topology ------------------------------------------
    surf0 = surface(plan[0][0])
    n_full = surf0.n_points
    fields = pick_fields(surf0, args.fields.split(",") if args.fields else None)
    fields.pop("part_id", None)
    print(f"surface: {n_full} points, {surf0.n_cells} triangles; fields: {fields}")

    if args.decimate > 0:
        dec = surf0.decimate_pro(args.decimate, preserve_topology=True)
        # decimate_pro keeps a subset of the original vertices -> map back by nearest point
        sel = np.asarray([surf0.find_closest_point(p) for p in dec.points], dtype=np.int64)
        faces = dec.faces.reshape(-1, 4)[:, 1:]
        tri_part = None
        print(f"decimated to {dec.n_points} points, {dec.n_cells} triangles")
    else:
        sel = np.arange(n_full)
        faces = surf0.faces.reshape(-1, 4)[:, 1:]
        tri_part = np.asarray(surf0.cell_data["part_id"]) if "part_id" in surf0.cell_data else None

    # triangles grouped by part so the viewer can toggle parts (three.js geometry groups)
    part_meta = []
    if tri_part is not None:
        order = np.argsort(tri_part, kind="stable")
        faces, tri_part = faces[order], tri_part[order]
        names = dict(kv.split("=", 1) for kv in args.part_names.split(",")) if args.part_names else {}
        for pid in np.unique(tri_part):
            where = np.flatnonzero(tri_part == pid)
            part_meta.append({"id": int(pid), "name": names.get(str(pid), f"part {pid}"),
                              "start": int(where[0]) * 3, "count": int(len(where)) * 3})
    n_verts = len(sel)
    indices = faces.astype(np.uint32).reshape(-1)

    # --- gather frames ------------------------------------------------------
    n_frames = len(plan)
    positions = np.empty((n_frames, n_verts, 3), np.float32)
    field_data = {}  # export name -> (n_frames, n_verts)
    sampled = {}  # solver frame -> (positions, {field: values}) already reduced to sel

    def sample(frame):
        if frame not in sampled:
            if len(sampled) > 2:
                sampled.pop(min(sampled))
            surf = surface(frame)
            if surf.n_points != n_full:
                sys.exit(f"frame {frame}: surface has {surf.n_points} points, expected {n_full} (topology changed?)")
            vals = {}
            for name, assoc in fields.items():
                for ename, arr in field_arrays(surf, name, assoc, args.components):
                    vals[ename] = arr[sel]
            sampled[frame] = (np.asarray(surf.points[sel], np.float32), vals)
        return sampled[frame]

    for fi, (a, b, w, _) in enumerate(plan):
        pa, va = sample(a)
        if w > 0:
            pb, vb = sample(b)
            positions[fi] = (1 - w) * pa + w * pb
            for ename in va:
                field_data.setdefault(ename, np.empty((n_frames, n_verts), np.float32))[fi] = (1 - w) * va[ename] + w * vb[ename]
        else:
            positions[fi] = pa
            for ename in va:
                field_data.setdefault(ename, np.empty((n_frames, n_verts), np.float32))[fi] = va[ename]
        print(f"\r  frame {fi + 1}/{n_frames}", end="", flush=True)
    print()

    # --- write bundle -------------------------------------------------------
    out = Path(args.site) / "cases" / args.name
    out.mkdir(parents=True, exist_ok=True)
    offsets, blobs, cursor = {}, [], 0

    def add(key, arr):
        nonlocal cursor
        b = np.ascontiguousarray(arr).tobytes()
        offsets[key] = [cursor, len(b)]
        blobs.append(b)
        cursor += len(b)

    add("indices", indices)
    add("positions", positions)
    field_meta = []
    for ename, arr in field_data.items():
        add(f"field:{ename}", arr)
        field_meta.append({
            "name": ename,
            "min": float(np.nanmin(arr)),
            "max": float(np.nanmax(arr)),
            "frameMin": [float(v) for v in np.nanmin(arr, axis=1)],
            "frameMax": [float(v) for v in np.nanmax(arr, axis=1)],
        })
    data = b"".join(blobs)

    lo, hi = positions.reshape(-1, 3).min(0), positions.reshape(-1, 3).max(0)
    meta = {
        "name": args.name,
        "title": args.title or args.name,
        "description": args.description,
        "nFrames": n_frames,
        "nVerts": n_verts,
        "nTris": len(indices) // 3,
        "times": [t for _, _, _, t in plan],
        "linearTime": not args.raw_steps,
        "parts": part_meta,
        "fields": field_meta,
        "bbox": [lo.tolist(), hi.tolist()],
        "offsets": offsets,
        "byteLength": len(data),
        "encrypted": bool(args.encrypt),
    }

    passphrase = None
    for stale in ("data.bin", "data.bin.enc"):
        (out / stale).unlink(missing_ok=True)
    if args.encrypt:
        sys.path.insert(0, str(HERE))
        import encrypt  # noqa: E402

        passphrase = args.passphrase or encrypt.new_passphrase()
        tmp = out / "data.bin"
        tmp.write_bytes(data)
        encrypt.encrypt_file(tmp, out / "data.bin.enc", passphrase)
        tmp.unlink()
    else:
        (out / "data.bin").write_bytes(data)
    (out / "meta.json").write_text(json.dumps(meta))

    # --- gallery index -------------------------------------------------------
    index_path = Path(args.site) / "cases" / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else []
    index = [c for c in index if c["name"] != args.name]
    index.append({
        "name": args.name,
        "title": meta["title"],
        "description": args.description,
        "group": args.group,
        "nFrames": n_frames,
        "nVerts": n_verts,
        "nTris": meta["nTris"],
        "fields": [f["name"] for f in field_meta],
        "encrypted": bool(args.encrypt),
        "sizeMB": round(len(data) / 1e6, 1),
    })
    index.sort(key=lambda c: (c.get("group", ""), c["title"].lower()))
    index_path.write_text(json.dumps(index, indent=1))

    mb = len(data) / 1e6
    print(f"wrote {out}  ({mb:.1f} MB, {n_frames} frames x {n_verts} verts, {len(field_meta)} fields)")
    if mb > SIZE_WARN_MB:
        print(f"WARNING: bundle > {SIZE_WARN_MB} MB; consider --decimate / --stride", file=sys.stderr)
    base = args.base_url.rstrip("/") or "http://localhost:8000"
    link = f"{base}/viewer.html?case={args.name}"
    if passphrase:
        link += f"#k={passphrase}"
        print(f"passphrase: {passphrase}   (keep it; it is not stored anywhere)")
    print(f"share link: {link}")


if __name__ == "__main__":
    main()
