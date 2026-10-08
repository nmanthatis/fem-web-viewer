# fem_web_viewer — progress

## Rules
See CLAUDE.md: exported frames are always evenly spaced in solution time.

## Status (2026-10-08)
Working end to end locally: exporter (`exporter/export_case.py`) → `site/cases/*` → three.js
viewer (`site/viewer.html`) with timeline, colormaps, clip planes, encryption, gallery.
Published: https://github.com/nmanthatis/fem-web-viewer → live at https://nmanthatis.github.io/fem-web-viewer/
(public repo, Pages deployed by `.github/workflows/pages.yml` on every push to main).

## Published cases
- **Clip in RV** › `clip_rv4mmHg` — `biv_valve_pipeline/runs/01_clip_rv4mmHg` (model.*.vtk, 404 solver
  steps → 40 frames linear in time, 0–0.2455 s), stress + Lagrange strain (vm/trace/p1), parts
  0–6 named (part 7 = 97 non-surface cells, dropped). Encrypted; passphrase is the lab name code
  the user chose (not written here). Share link = viewer URL + `#k=<code>`.

## Test cases currently in site/cases
- `sphere_demo`, `sphere_demo_dec` — synthetic deforming sphere (from `test_data/`, gitignored;
  regenerate with the snippet in git history / ask Claude). Remove before publishing real work.
- `leaflet_frame40` — single frame from `valve_in_febio/viz`, encrypted with passphrase `testkey`.

## Next steps
- [x] First real case exported (2026-10-08, clip_rv4mmHg).
- [ ] Manifest (`cases.toml` + `build_all.py`) so re-exports are one command — offered, not yet requested.
- [x] GitHub repo + Pages (2026-10-08).
- [ ] Delete demo cases from `site/cases/` (and `index.json` entries) before sharing.
- [ ] Nice-to-haves: per-case camera presets, side-by-side comparison of two cases,
      vector glyphs, volume (not just surface) export, pause-on-hover frame tooltip.

## Headless check (no browser UI)
Chrome's `--screenshot` with `--virtual-time-budget` captures before WebCrypto/rAF finish.
A small DevTools-protocol driver that waits real time works:
`python3 cdp_shot.py <url> out.png <seconds>` (uses `websockets`; copy from the
2026-10-08 session scratchpad or rewrite: Page.navigate → wait → Page.captureScreenshot).
