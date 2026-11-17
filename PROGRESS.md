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
  97 non-surface cells, dropped), 33.9 MB. Default view: stress vm, viridis, 0–80 kPa; start + thumbnail pose = atrial view down the tied
  annulus (absolute camera in meta.json: valve z axis, up = valve +y rotated by the 82° rz of
  `coupling.json`, annulus centroid = ring_centroid_raw + translation). Was encrypted
  until 2026-10-16 (re-exported plain at the user's request).
- **Clip in RV** › `septal_clip_rv4mmHg_midplane` ("Septal-aligned valve + clip in BiV, RV 4 mmHg") —
  `biv_valve_pipeline/runs/03_septal_clip_rv4mmHg_midplane/vtk_by_time/model.*.vtk` (51 solver files → 40 frames,
  0–0.224 s, where the run ends), valve at ann_rz 140.7° (septal leaflet on the septum) on the septal-aligned 3 mm wall,
  roller plane at mid height. Same fields, parts and default view as `clip_rv4mmHg`; atrial start pose with up rotated
  by 140.7°. 33.8 MB, preview rendered. 2026-11-10.
- **Echo valves / D-02-S-03-b** › `echo_tv_D-02-S-03-b_t0032` ("Baseline chordae (t0032)") —
  `valve_in_febio/runs/echo_tv_realvalves/chordae_D-02-S-03-b/mech_cusp_pm/pareto_search/rerun_t0032_allframes`
  (2017 steps → 100 frames, 0–0.1 s; 20 mmHg ramp 0–0.05 s then hold). Leaflets (part 0) + 49 chordae
  as gray rods r = 0.07 mm; displacement, stress, Lagrange strain, shell thickness; 8.9 MB. Default
  view: stress p1, coolwarm, 20–70 kPa. Matches the user's ParaView macro (warp by displacement,
  quads only, smooth normals).

- **Echo valves / D-02-S-03-b** › `echo_tv_D-02-S-03-b_belly_col0PM4_clamped_p23` ("Belly chordae + PM4, clamped
  annulus, 23 mmHg (identification valve)") — `stiffness_from_image/runs/pm_viewer_echo_clamped_p23_x0`
  (12 solver frames at 0.01 s -> 100 frames; uniform neo-Hookean G 29.5 kPa, t 0.6725 mm, 82 chordae rods). 2026-11-04.
- **Echo valves / D-03-S-02** › `echo_tv_D-03-S-02_t0043` ("Rule-based chordae, Pareto trial 43 (closes)") —
  `stiffness_from_image/runs/pm_viewer_echo_D-03-S-02_t43` (12 frames -> 100; 49 chordae; 20 mmHg). 2026-11-04.
- **Echo valves / D-07-S-01** › `echo_tv_D-07-S-01_t0046` ("Rule-based chordae, Pareto trial 46 (does not close)") —
  `stiffness_from_image/runs/pm_viewer_echo_D-07-S-01_t46` (11 frames -> 100; 47 chordae; 20 mmHg). 2026-11-04.
- **BiV walls from the OCS valves** (2026-11-13; published public, no passphrase, at the user's request): three static
  cases, solid geometry only (no mesh), one frame, no fields; parts LV endocardium / RV endocardium / pulmonary trunk
  lumen / outer wall, annulus as a rod ring (r 0.25 mm). Source = each build's `checkpoint_solid.cub5` (wall solid
  after all booleans, before the annulus imprint) in `biventricular/biv/biv_v2/output/runs/`:
  `biv_wall_ocs12_diseased` <- `2026-10-08_1117_diseased-septal-singletool-3mm` (the approved 3 mm wall);
  `biv_wall_ocs13` <- `2026-11-13_1405_wavetest-ocs13-flat1.0` (wedge floor 1.0, healthy-size RVOT placement);
  `biv_wall_ocs14` <- `2026-11-11_1656_ocs14-var-diseasedseptal-lv32.0` (wedge floor 0.8, OCS12-diseased RVOT
  placement; the 1650 build with the healthy-size placement lost the trunk). OCS13/OCS14 solids do not mesh yet.
  New tooling: `exporter/cubit_solid_to_vtu.py` runs `exporter/cubit/solid_facets.py` in Cubit batch to tessellate
  each surface and assign it to the nearest of the build's *_ref volumes (flat cut faces and the wedge outer skin go
  to the outer wall), and writes a .vtu with part_id + optional annulus line cells; then `export_case.py X.vtu
  --parts 0,1,2,3 --lines Annulus --line-parts 9 --line-radius 0.25 --default-field none`, then
  `exporter/annulus_camera.py NAME` (start + thumbnail pose straight down the annulus best-fit-plane normal from the
  atrial (+z) side, frame centred on the projected model and fitted to 16:9; user's choice 2026-11-13) and
  `make_preview.py NAME --frames 1`.
- **Common orientation (2026-11-13, user):** every BiV case, walls and clip-in-RV runs alike, opens and previews with
  the septal leaflet's centre (arc midpoint between its commissures, `geom_core.septal_alignment_rz`) at the top of
  the screen, looking down the annulus from the atrial side. Septal-aligned builds (both OCS12 septal cases, OCS13,
  OCS14) have the septal midpoint at 180 deg about the annulus centroid -> `--up-vec=-1,0,0`; `clip_rv4mmHg` (ann_rz
  82) has it at 121.29 deg -> `--up-vec=-0.5194,0.8545,0`. Walls: `annulus_camera.py NAME --up-vec=...`. Clip cases
  have no ring rods, so the OCS12 annulus (`pins/valve_diseased_deck/00_VALVE.inp` Annular_Nodes) is placed with each
  run's `coupling.json` (Rz about ring_centroid_raw, then + translation) and passed as `--ring-json`; they then get
  the same framing as the walls (centred on the whole model, fitted to 16:9). Pass the vector with `=` (a leading
  minus is read as a flag otherwise). All five previews re-rendered. (`--keep-pose` exists to rotate only screen-up.) Annulus rings: `rv_wedge_rings.build_rv_wedge_rings(...)['inner'][3]` with each run's
  params.json knobs.
- **Echo valves / D-03-S-02** › `echo_tv_D-03-S-02_t0043_fan5_L3` ("Fan chordae (5 branches, 3 mm), trial 43") —
  `stiffness_from_image/runs/fan_D-03-S-02/L3` (12 frames -> 100; 49 trunks + 245 branches = 294 rods; 20 mmHg). 2026-11-05.
  All three: same `echo_valve` preset and default view as the baseline case; previews rendered.

- **PMs on the RV endocardium (tips fixed in space)** › `pm_ocs13_pm3split_rv4mmHg` (run 23), `pm_ocs14_pmsnap_rv4mmHg`
  (run 24), `pm_ocs14_pm3free_rv4mmHg` (run 25) from `biv_valve_pipeline/runs/2x_*` (51 frames -> 40, chordae as rods 0.07,
  stress + Lagrange strain, public). Septal-up atrial pose via `annulus_camera.py --ring-json` (valve AnnularNodes from the
  deck) `--up-vec=-1,0,0`; previews rendered. 2026-11-16 (user request).

- **Clip release (standalone OCS14)** › `clip_release_ocs14_damp1` — `biv_valve_pipeline/runs/44_ocs14_inplace_round3_js/w0.2_damp1`
  (60 solver files -> 40 frames, t 0-0.374), the furthest in-step release run (springs to ground, log k ramp from 1e4 at t 0.26,
  damper c 1, ERROR at 0.377). Parts 0-5 named (Ground body and chordae cells dropped; chordae as rods 0.07). Stress 0-80 kPa
  (as clip_rv4mmHg). Atrial pose with the septal leaflet up via `annulus_camera.py --ring-json` (deck AnnularNodes)
  `--up-vec=0.6239,0.7814,0.0156`. 2026-11-17 (user request).

- **Clip in RV: chordae added, "saw-teeth" diagnosed** (2026-11-17, user request) — `clip_rv4mmHg` (run 01) and
  `septal_clip_rv4mmHg_midplane` (run 03) now show the 97 chordae as rods (r 0.07). Their VTK frames
  (`vtk_by_time/model.*.vtk`) are no longer on disk, so they could not be re-exported: the rods were added to the
  published bundles with the new `exporter/add_lines_from_feb.py` (DiscreteSet `Chordae` from each run's `model.feb`;
  the 97 leaflet ends match leaflet surface vertices of frame 0 to 5e-5 mm, the 7 tips of `PapillaryNodes` (zero
  displacement in the deck) are appended at their deck coordinates). Same layout as `export_case.py --lines`; camera,
  title, description, group, parts and colour defaults unchanged; previews re-rendered. The **saw-teeth** along the
  annulus are not chordae and are not an export error: they are the old 3 mm diseased wall's own mesh (part 6), whose
  384 imprinted annulus nodes are fanned to the coarse wall nodes by sliver triangles (median edge ratio 7 vs 1.1
  elsewhere) and carry 15-22 kPa against ~1 kPa on the rest of the wall, so each fan renders as a light tooth. Visible
  in a wall-only render, absent in a leaflet-only render; the OCS13/OCS14 walls (edge ratio 1.7) do not show them.
  The rods do not remove them; options left to the user (hide the wall, a separate wall colour range, or a remeshed
  wall annulus band).
- **PMs on the RV endocardium (lowered tips, fixed in space)** › `pm_ocs12_lowered_fixed` (run 54, deck of run 06,
  tips of run 51 r3), `pm_ocs13_lowered_fixed` (run 55, deck of run 23, tips of run 52 r3), `pm_ocs14_lowered_fixed`
  (run 56, deck of run 25, tips of run 53 r1) from `biv_valve_pipeline/runs/5x_*_lowerpm_fixed` (50/51/51 frames -> 40;
  run 54's last frame is t 0.098). Same recipe as runs 23-25: stress + Lagrange strain, parts 0-3 (P/A/S leaflets,
  BiV wall), chordae rods 0.07 (97/84/65), septal-up atrial pose (`annulus_camera.py --ring-json` deck AnnularNodes
  `--up-vec=-1,0,0`, checked for all three), previews rendered. Rod ends checked: leaflet ends on leaflet vertices,
  tip ends at the deck PapillaryNodes at t 0 and at `pm_fixed_lowered.json` to_xyz from t 0.02 (5e-5 mm). Leaflet
  pressure 3.06 kPa for OCS12 (run 06 deck), 5.666 kPa for OCS13/14. The OCS12 case uses the same old diseased wall,
  so it shows the same annulus saw-teeth. 2026-11-17 (user request).

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
