# How to use the FEM viewer

Site: https://nmanthatis.github.io/fem-web-viewer/

## For collaborators (viewing)

1. Open the link you were sent. A link of the form
   `…/viewer.html?case=NAME#k=CODE` opens the case directly; the part after `#k=` is
   the access code and stays in your browser (it is never sent to GitHub).
2. If the link has no `#k=`, the page asks for the code. Type it exactly (case-sensitive).
3. Controls:
   - **Rotate** left-drag · **pan** right-drag or two-finger drag · **zoom** wheel / pinch
   - **Play/pause** Space or the ▶ button · **step** ← / → · **reset view** `r`
   - **Color by** picks the field; **Range** = all frames / current frame / custom
   - **Parts** checkboxes hide or show leaflets, clip, wall, etc.
   - **Clipping** sliders cut the model along X/Y/Z; *flip* changes the side kept
   - **Display**: wireframe, flat shading, axes · **Screenshot** saves a PNG with a
     transparent background
4. **Copy view** puts a link to exactly what you see (camera, field, colormap, range, frame,
   hidden parts, clip planes) on the clipboard, so you can show someone the same view.
   Keep `#k=CODE` at the end when you forward it.

Fields: `stress (von Mises)`, `stress (trace)`, `stress (p1)` = max principal stress;
`Lagrange_strain (p1)` = max principal Green-Lagrange strain (the one to use for strain),
plus its von Mises and trace variants.

## For the owner (adding a run, sharing)

Add a run (FEBio `model.*.vtk` series, 40 frames evenly spaced in time; drop `--encrypt --passphrase CODE`
for a public case, which is what both current cases are):

```bash
cd ~/doc/Phd/fem_web_viewer
source .venv/bin/activate
python3 exporter/export_case.py "/path/to/run/model.*.vtk" \
    --name clip_rv4mmHg --title "Clip, RV 4 mmHg" --group "Clip in RV" \
    --fields stress,Lagrange_strain \
    --parts 0,1,2,3,4,5,6 \
    --part-names "0=Posterior,1=Anterior,2=Septal,3=Clip-Base,4=Clip-Posterior,5=Clip-Septal,6=biv_wall" \
    --frames 40 --encrypt --passphrase CODE \
    --base-url https://nmanthatis.github.io/fem-web-viewer
./serve.sh            # check at http://localhost:8000, then
./publish.sh "add clip_rv4mmHg"
```

- FEBio discrete elements (chordae, springs) come out of the VTK export as 2-node cells with an
  unknown cell type; `--lines Chordae` exports them as rods (default radius 0.3 % of the bounding
  box, or `--line-radius 0.07` in model units; `lines.radius` in `meta.json`). Example:
  `--parts 0 --part-names "0=Leaflets" --lines Chordae --line-radius 0.07 --frames 100`.
- Runs of the same kind share a preset: `--preset echo_valve` loads `exporter/presets/echo_valve.json`
  (fields, parts, chordae rods, 100 frames, group `Echo valves/D-02-S-03-b`, colour defaults, and the
  **start pose** + **thumbnail pose** of the camera, relative to the bounding box so they fit every
  variant of the valve). Flags given on the command line still win. Add a new valve variant with
  `export_case.py "<run>/t00NN.*.vtk" --name echo_tv_<variant> --title "Belly chordae" --preset echo_valve`
  then `make_preview.py` and `publish.sh`.
- A group with a slash (`Echo valves/D-02-S-03-b`) becomes a section with a sub-heading in the gallery.
- To change a pose: orbit to the view you want, press **Copy view** in the viewer, and paste the link
  (it carries `cam=`, field, range and frame). Put the camera into the preset as `pos`/`target`/`up`
  (absolute) or convert to `dir`/`dist`/`target` fractions (relative, preferred). "Reset view" in the
  viewer returns to the case's start pose.
- Per-case view defaults: `--default-field "stress|p1" --default-cmap coolwarm --default-range 20,70`
  (stored as `defaults` in the case's `meta.json`, so they can also be edited there by hand;
  URL parameters still override them).
- `--group` is the heading on the gallery page; `--part-names` follows the `<Elements>`
  order in `model.feb`.
- Frames are always resampled to uniform Δt (project rule in CLAUDE.md). Never use
  `--raw-steps` for published cases.
- Keep each bundle under 50 MB: fewer fields, then `--decimate 0.5`, then fewer frames.
- Deploy takes about a minute after the push (`gh run list --limit 1` shows it).

Link previews (thumbnail + animation in WhatsApp / Slack / Teams / iMessage):

```bash
python3 exporter/make_preview.py echo_tv_D-02-S-03-b_t0032          # add --passphrase CODE for encrypted cases
./publish.sh "preview for echo_tv_D-02-S-03-b_t0032"
```

This renders `site/cases/NAME/preview.jpg` (static card image), `preview.gif` and `preview.mp4`
(the animation, ~50 frames, 800 px wide) and a share page `site/cases/NAME/index.html` with Open
Graph tags that forwards into the viewer. Share `https://nmanthatis.github.io/fem-web-viewer/cases/NAME/`
(plus `#k=CODE` for encrypted cases) instead of the viewer URL: chat apps show the thumbnail, the
browser lands in the viewer. Chat apps only ever show a *static* preview image; to show the motion,
attach `preview.gif` or `preview.mp4` to the message as well. The gallery shows the thumbnail and
plays the GIF on hover. Options: `--frames`, `--fps`, `--zoom`, `--view "field=...&cmap=...&hide=rods"`.
Re-run after every re-export, since the assets are rendered from the exported bundle.

Share a case:

- Encrypted case: send `https://nmanthatis.github.io/fem-web-viewer/viewer.html?case=NAME#k=CODE`
  through a private channel. Or send the link without `#k=` and give the code separately.
- Rotate a code: re-export with a new `--passphrase` and `./publish.sh`; old links stop
  working once the deploy finishes.
- Remove a case: delete `site/cases/NAME/` and its entry in `site/cases/index.json`, then
  `./publish.sh "remove NAME"`.
- Passphrases are never committed; keep them in your password manager.
