# fem_web_viewer — progress

## Rules
See CLAUDE.md: exported frames are always evenly spaced in solution time.

## Status (2026-10-16)
Both cases are public (no encryption) with link previews; share `…/cases/NAME/` links in chats.
Session 2026-10-15/16 added: chordae rods, per-case view defaults (`defaults` in meta.json,
`--default-*` exporter flags), cache-busting in `publish.sh` (stamps local JS/CSS on every publish),
`make_preview.py`. Nothing pending from the user.

## Status (2026-10-15)
Link previews: `exporter/make_preview.py NAME` renders preview.jpg/gif/mp4 + an OG share page
`site/cases/NAME/index.html` (headless Chrome via DevTools protocol, viewer `ui=0&zoom=` params and
`window.fem.setFrame` hook). Share `…/cases/NAME/` for a thumbnail in chats. Done for the echo TV case.
Viewer now draws FEBio discrete elements (chordae) as instanced cylinder rods (`--lines` in the
exporter; rod radius fixed per case in meta.json; `hide=rods` URL param). Second real case published.

## Status (2026-10-08)
Working end to end locally: exporter (`exporter/export_case.py`) → `site/cases/*` → three.js
viewer (`site/viewer.html`) with timeline, colormaps, clip planes, encryption, gallery.
Published: https://github.com/nmanthatis/fem-web-viewer → live at https://nmanthatis.github.io/fem-web-viewer/
(public repo, Pages deployed by `.github/workflows/pages.yml` on every push to main).

Usage notes for collaborators and for adding/sharing runs: `USAGE.md` (added 2026-10-12).

## Published cases
- **Clip in RV** › `clip_rv4mmHg` — `biv_valve_pipeline/runs/01_clip_rv4mmHg` (model.*.vtk, 404 solver
  steps → 40 frames linear in time, 0–0.2455 s), stress + Lagrange strain (vm/trace/p1), parts
  0–6 named (part 7 = 97 non-surface cells, dropped). Re-exported **unencrypted** on 2026-10-16 at the
  user's request (from `vtk_by_time/`, now 65 solver files); default view stress vm 0–80 kPa; preview assets rendered.

- **Echo valves** › `echo_tv_D-02-S-03-b_t0032` —
  `valve_in_febio/runs/echo_tv_realvalves/chordae_D-02-S-03-b/mech_cusp_pm/pareto_search/rerun_t0032_allframes`
  (t0032.*.vtk, 2017 steps → 100 frames linear in time, 0–0.1 s, 20 mmHg ramp 0–0.05 s then hold).
  Leaflets (part 0, quads) + 49 chordae as gray rods r = 0.07 mm; fields displacement, stress,
  Lagrange strain, shell thickness. 8.9 MB, **not encrypted** (user's choice). Matches the user's
  ParaView macro (warp by displacement, quads only, smooth normals).

## Test cases
Demo cases (`sphere_demo*`, `leaflet_frame40`) were removed from `site/cases` on 2026-10-13; the
synthetic sphere generator is in git history if a test case is needed again.

## Next steps
- [x] First real case exported (2026-10-08, clip_rv4mmHg).
- [ ] Manifest (`cases.toml` + `build_all.py`) so re-exports are one command — offered, not yet requested.
- [x] GitHub repo + Pages (2026-10-08).
- [x] Delete demo cases from `site/cases/` (2026-10-13).
- [ ] Encryption path is untested since both cases went public; `make_preview.py --passphrase` exists but
      has not been exercised on a real encrypted case.
- [ ] Nice-to-haves: per-case camera presets, side-by-side comparison of two cases,
      vector glyphs, volume (not just surface) export, pause-on-hover frame tooltip.

## Headless check (no browser UI)
Chrome's `--screenshot` with `--virtual-time-budget` captures before WebCrypto/rAF finish.
`exporter/make_preview.py` contains a reusable DevTools-protocol driver (`Chrome` class: navigate,
`js()`, `shot()`); the viewer exposes `window.fem.setFrame` and the `ui=0`, `zoom=`, `autoplay=0`
URL params for it. For a one-off screenshot of any URL the older `cdp_shot.py` pattern
(Page.navigate → wait real seconds → Page.captureScreenshot) is the same code minus the frame loop.
Run with plain `python3`, not `python3 -I` (websockets lives in user site-packages).
