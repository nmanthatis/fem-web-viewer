# fem_web_viewer — progress

## What it is
A static website for sharing interactive 3D animations of FEM results. A Python exporter
(`exporter/export_case.py`) turns a VTK time series (FEBio `model.*.vtk`, ParaView `.pvd`, …) into a
compact binary bundle under `site/cases/<name>/`; a three.js page (`site/viewer.html`) plays it in the
browser with orbit/zoom, a timeline, scalar colormaps, clip planes, part toggles and screenshots.
Published from the public repo https://github.com/nmanthatis/fem-web-viewer to
https://nmanthatis.github.io/fem-web-viewer/ (GitHub Actions deploys Pages on every push to main).
Day-to-day instructions are in `USAGE.md`; the full reference is `README.md`.

## Rules
See `CLAUDE.md`: exported frames are always evenly spaced in solution time (never `--raw-steps` for
published cases); FEBio VTK files are reference coordinates + `displacement`, warped by the exporter.
FEBio runs use mm / kPa / mN / s / kg, so all stress fields are in kPa.

## What works (as of 2026-10-16)
- Presets: `--preset echo_valve` (`exporter/presets/echo_valve.json`) gives every echo-valve variant the
  same fields, parts, chordae rods, 100 frames, group `Echo valves/D-02-S-03-b`, colour defaults and
  two camera poses relative to the bounding box: **start pose** = atrial (surgeon's) view centred on
  the annulus, **thumbnail pose** = the same atrial view (user's choice; a ventricular oblique was tried first). "Reset view"
  returns to the start pose; `make_preview.py` renders from the thumbnail pose (`pose=thumb`).
- Viewer "Copy view" button → link with `cam=` (9 numbers), field, cmap, `range=`, frame, hidden
  parts, clip planes. Gallery groups nest with `/` (section + sub-heading).
- Export: linear-time resampling (`--frames N`), part filtering and naming, tensor invariants
  (vm / trace / p1), decimation, AES-GCM encryption (`--encrypt`), FEBio discrete elements (chordae)
  as rods (`--lines Chordae --line-radius r`), per-case view defaults
  (`--default-field/--default-cmap/--default-range`, stored as `defaults` in `meta.json`).
- Viewer: everything above plus instanced-cylinder rods, URL state (field, cmap, clip planes, hidden
  parts incl. `hide=rods`, frame, `zoom=`, `ui=0`), transparent-background PNG screenshots,
  light/dark theme.
- Link previews: `exporter/make_preview.py <name>` renders `preview.jpg` (Open Graph card),
  `preview.gif` + `preview.mp4` (animation, 800 px) and a share page `site/cases/<name>/index.html`
  that carries the OG tags and forwards into the viewer. Share `…/cases/<name>/` in chats; attach the
  GIF/MP4 for motion (chat apps only show static cards). Gallery cards show the thumbnail, GIF on hover.
- `publish.sh` stamps local JS/CSS references with a version on every publish (fixed a stale-cache
  "Could not load case" error on 2026-10-15).

## Published cases (both public, no passphrase)
- **Clip in RV** › `clip_rv4mmHg` — `biv_valve_pipeline/runs/01_clip_rv4mmHg/vtk_by_time/model.*.vtk`
  (65 solver files → 40 frames, 0–0.2455 s), stress + Lagrange strain, parts 0–6 named (part 7 =
  97 non-surface cells, dropped), 33.9 MB. Default view: stress vm, viridis, 0–80 kPa. Was encrypted
  until 2026-10-16 (re-exported plain at the user's request).
- **Echo valves / D-02-S-03-b** › `echo_tv_D-02-S-03-b_t0032` ("Baseline chordae (t0032)") —
  `valve_in_febio/runs/echo_tv_realvalves/chordae_D-02-S-03-b/mech_cusp_pm/pareto_search/rerun_t0032_allframes`
  (2017 steps → 100 frames, 0–0.1 s; 20 mmHg ramp 0–0.05 s then hold). Leaflets (part 0) + 49 chordae
  as gray rods r = 0.07 mm; displacement, stress, Lagrange strain, shell thickness; 8.9 MB. Default
  view: stress p1, coolwarm, 20–70 kPa. Matches the user's ParaView macro (warp by displacement,
  quads only, smooth normals).

## Tried / set aside
- Demo cases (`sphere_demo*`, `leaflet_frame40`) removed from the site on 2026-10-13; their synthetic
  input frames moved to `archive/test_data/` on 2026-10-16 (generator only in git history).
- Chrome `--screenshot --virtual-time-budget` for headless checks: captures before WebCrypto/rAF
  finish. Replaced by the DevTools-protocol driver now inside `make_preview.py` (`Chrome` class;
  `window.fem.setFrame` hook in the viewer). Run with plain `python3`, not `-I`.
- Black chordae rods: invisible on the dark theme; settled on gray.
- The Claude-in-Chrome extension was not connected in these sessions; headless Chrome covered it.

## Status and next step
The user is starting a long run of a chordae variant ("belly chordae") of valve D-02-S-03-b with many
frames. When it finishes:
`export_case.py "<run>/t00NN.*.vtk" --name echo_tv_D-02-S-03-b_<variant> --title "Belly chordae (t00NN)" --preset echo_valve`
→ `make_preview.py <name>` → `publish.sh`. It lands next to the baseline under Echo valves / D-02-S-03-b
with the same poses and colour range. The poses were chosen by Claude on 2026-10-16; the user may
refine them with "Copy view" (then edit the preset and the existing case's `meta.json`).
(Manifest idea: a `cases.toml` manifest + `build_all.py` would make re-exports one command, offered
but not requested). Open nice-to-haves: per-case camera presets, side-by-side comparison, vector
glyphs, volume export. The encryption path is untested since both cases went public
(`make_preview.py --passphrase` exists but has not been exercised on a real encrypted case).
