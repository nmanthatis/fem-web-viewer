# fem_web_viewer — progress

## Rules
See CLAUDE.md: exported frames are always evenly spaced in solution time.

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
  0–6 named (part 7 = 97 non-surface cells, dropped). Encrypted; passphrase is the lab name code
  the user chose (not written here). Share link = viewer URL + `#k=<code>`.

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
- [ ] Nice-to-haves: per-case camera presets, side-by-side comparison of two cases,
      vector glyphs, volume (not just surface) export, pause-on-hover frame tooltip.

## Headless check (no browser UI)
Chrome's `--screenshot` with `--virtual-time-budget` captures before WebCrypto/rAF finish.
A small DevTools-protocol driver that waits real time works:
`python3 cdp_shot.py <url> out.png <seconds>` (uses `websockets`; copy from the
2026-10-08 session scratchpad or rewrite: Page.navigate → wait → Page.captureScreenshot).
