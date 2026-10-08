# fem_web_viewer

Share interactive 3D animations of FEM results (FEBio, Abaqus, anything ParaView can
open) as a static website. No server: a Python exporter turns a VTK time series into a
compact binary bundle, and a three.js page renders it in the browser with orbit/zoom,
a scrubbable timeline, scalar-field colormaps, clip planes and optional encryption.

```
exporter/export_case.py   VTK series -> site/cases/<name>/{meta.json, data.bin[.enc]}
exporter/encrypt.py       AES-GCM encryption helper (mirrored by site/js/crypto.js)
site/                     the published website (index.html gallery + viewer.html)
publish.sh                commit site/cases and push (GitHub Actions deploys Pages)
serve.sh                  local preview on http://localhost:8000
```

## 1. Export a time series from ParaView

Open your result (`.xplt`, `.odb` via the Abaqus reader, `.vtk`, ...), apply any filters
you want baked in (e.g. Extract Surface, Clip, Threshold), select the pipeline object, then

*File → Save Data…* → choose **PVD (`.pvd`)**, tick **Write all timesteps as a file series**,
pick *Point Data / Cell Data* arrays you want to keep. ParaView writes `name.pvd` plus
`name/name_0.vtu …`.

Alternatives: a glob of per-frame files works too (`"runs/frame_*.vtu"`), as does a
single file for a static result.

## 2. Build the web bundle

```bash
python3 exporter/export_case.py runs/valve.pvd --name valve_uniform \
    --title "Valve, uniform material" --description "mesh v3, 0.4 s cycle" \
    --fields stress,displacement --decimate 0.5 --stride 2 --encrypt
```

| flag | meaning |
|---|---|
| `--fields a,b` | arrays to export (default: all point+cell arrays). Vectors → magnitude, symmetric tensors → von Mises + trace; add `--components` for x/y/z or xx…xz |
| `--decimate 0.5` | remove 50 % of surface triangles (keeps original vertices, so all frames stay consistent) |
| `--stride 2` / `--max-frames N` | keep every 2nd frame / cap the frame count |
| `--encrypt [--passphrase ...]` | AES-GCM-encrypt the data; a random passphrase is printed once |
| `--base-url https://nmanthatis.github.io/fem-web-viewer` | makes the printed share link correct |

Only the **outer surface** is exported (the viewer is a surface renderer); clip planes
show the hollow inside. Topology must be constant across frames (always true for
Lagrangian FEM). Keep bundles under ~50 MB — the exporter warns otherwise; use
`--decimate`, `--stride`, or fewer `--fields`.

Check locally: `./serve.sh` → http://localhost:8000.

## 3. Publish

First time: `gh repo create fem-web-viewer --public --source . --push`, then in the
GitHub repo settings → Pages → Source = **GitHub Actions**. Every later push to `main`
(e.g. `./publish.sh "add valve case"`) redeploys. Site URL:
`https://<user>.github.io/fem-web-viewer/`.

## Sharing & privacy

- Unencrypted cases are public to anyone with the link.
- `--encrypt` cases are stored encrypted; the viewer decrypts in the browser with the
  passphrase from the URL fragment (`viewer.html?case=valve#k=PASS`). Fragments are
  never sent to the server, so GitHub never sees the key. Without `#k=` the page asks
  for the passphrase. Send the link through a private channel; anyone with it can view.
- If your GitHub org has Team/Enterprise, you can instead make the repo private and
  enable Pages access control — then encryption is optional.

Useful URL parameters: `&field=stress|vm&cmap=coolwarm&frame=12&clipX=0.4&clipZ=-0.5&autoplay=0`
(negative clip = flipped side). Copy the browser URL to share a specific view.

## Viewer controls

Drag rotate (trackball, no pole limit) · right-drag/two-finger pan · wheel/pinch zoom ·
Space play/pause · ←/→ step · `r` reset view. Panel: field + colormap + range (all frames /
current frame / custom), X/Y/Z clip planes, wireframe, flat shading, axes, screenshot (PNG).
Light/dark theme follows the toggle on the gallery page.

## Development notes

- Bundle layout is documented at the top of `exporter/export_case.py`; `meta.json`
  holds byte offsets so the viewer creates typed-array views without copying.
- three.js is loaded from jsDelivr via an import map (`site/viewer.html`), pinned version.
- To check the site headlessly without a browser UI, see the CDP snippet in PROGRESS.md.
