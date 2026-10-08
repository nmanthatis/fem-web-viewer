# fem_web_viewer — project rules

## Hard rule: runs are always linear in time
Every exported case must have frames **evenly spaced in solution time** (uniform Δt),
never the solver's raw adaptive steps. FEBio writes dense output where convergence is
hard and sparse elsewhere, so raw steps make animations slow down and speed up for
numerical rather than physical reasons. `exporter/export_case.py` does this by default
(`--frames N`, linear interpolation between bracketing steps). Do **not** pass
`--raw-steps` for anything that is published; if a user insists, say the rule first.

## FEBio VTK files are reference coordinates + displacement
FEBio's `model.N.vtk` export keeps the undeformed node positions in `POINTS` for every
frame and stores the motion in the point array `displacement`. The exporter warps points
by that array automatically (`--warp-by auto`); it skips warping only when `POINTS`
already move between frames (ParaView-saved series). If a case "doesn't deform", check
this first.

## Other conventions
- Frame time comes from the `.pvd` or from the legacy-VTK title line (`time 0.1234`).
- Keep bundles < 50 MB (decimate / fewer fields / fewer frames, in that order of preference).
- Sensitive runs are exported with `--encrypt`; passphrases are never committed.
- After exporting, `./publish.sh "<message>"`; update PROGRESS.md with what was published.
