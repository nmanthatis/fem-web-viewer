import * as THREE from 'three';
import { TrackballControls } from 'three/addons/controls/TrackballControls.js';
import { COLORMAPS, buildLUT, drawLegend, fmt } from './colormaps.js?v=20261016174359';
import { decryptBundle, keyFromFragment } from './crypto.js?v=20261016174359';

const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const caseName = params.get('case');

// ------------------------------------------------------------------ state
const S = {
  meta: null, indices: null, positions: null, fields: {},
  frame: 0, playing: false, acc: 0, lastT: 0,
  field: 'none', cmap: 'viridis', lut: buildLUT('viridis'), rangeMode: 'global',
  clip: { X: { on: false, flip: false, v: 0.5 }, Y: { on: false, flip: false, v: 0.5 }, Z: { on: false, flip: false, v: 0.5 } },
};

// ------------------------------------------------------------------ three.js setup
const canvas = $('canvas');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.localClippingEnabled = true;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, 1, 0.01, 1e5);
// Trackball = free rotation in any direction (no pole limit)
const controls = new TrackballControls(camera, canvas);
controls.rotateSpeed = 3.0; controls.zoomSpeed = 1.2; controls.panSpeed = 0.8; controls.dynamicDampingFactor = 0.15;
scene.add(new THREE.HemisphereLight(0xffffff, 0x667799, 0.9));
const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(0.5, 0.8, 1); camera.add(key);
scene.add(camera);

const planes = {
  X: new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0),
  Y: new THREE.Plane(new THREE.Vector3(0, -1, 0), 0),
  Z: new THREE.Plane(new THREE.Vector3(0, 0, -1), 0),
};
const material = new THREE.MeshStandardMaterial({ vertexColors: true, side: THREE.DoubleSide, roughness: 0.55, metalness: 0.05, clippingPlanes: [] });
const wireMat = new THREE.MeshBasicMaterial({ wireframe: true, color: 0x222222, transparent: true, opacity: 0.35, clippingPlanes: [] });
let geometry, mesh, wire, axes, rods;
// rods (chordae etc.): instanced unit cylinders, one per 2-node segment, re-posed every frame
const rodMat = new THREE.MeshStandardMaterial({ color: 0x8a8a8a, roughness: 0.5, metalness: 0.05, clippingPlanes: [] });

function applySceneTheme() {
  const css = getComputedStyle(document.documentElement);
  scene.background = new THREE.Color(css.getPropertyValue('--scene').trim());
  const light = document.documentElement.dataset.theme === 'light';
  wireMat.color.set(light ? 0x222222 : 0xdddddd);
}
applySceneTheme();

function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== w * renderer.getPixelRatio() || canvas.height !== h * renderer.getPixelRatio()) {
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); controls.handleResize();
  }
}

// ------------------------------------------------------------------ loading
async function fetchWithProgress(url, onProgress) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  const total = +res.headers.get('content-length') || 0;
  const reader = res.body.getReader(); const chunks = []; let got = 0;
  for (;;) {
    const { done, value } = await reader.read(); if (done) break;
    chunks.push(value); got += value.length; onProgress(total ? got / total : 0, got);
  }
  const out = new Uint8Array(got); let o = 0;
  for (const c of chunks) { out.set(c, o); o += c.length; }
  return out.buffer;
}

function askPassphrase(msg) {
  return new Promise(resolve => {
    const f = $('keyForm'); f.style.display = 'flex'; $('ovMsg').innerHTML = msg ? `<span class="error">${msg}</span>` : '';
    $('ovTitle').innerHTML = `<b>${S.meta.title}</b>`; $('keyInput').focus();
    f.onsubmit = e => { e.preventDefault(); f.style.display = 'none'; resolve($('keyInput').value); };
  });
}

async function load() {
  if (!caseName) throw new Error('No case given. Open a case from the <a href="index.html">gallery</a>.');
  const base = `cases/${encodeURIComponent(caseName)}/`;
  const mres = await fetch(base + 'meta.json', { cache: 'no-store' });
  if (!mres.ok) throw new Error(`Case "${caseName}" not found.`);
  S.meta = await mres.json();
  document.title = `${S.meta.title} – FEM Viewer`;
  $('ovTitle').innerHTML = `<b>${S.meta.title}</b>`;
  let buf = await fetchWithProgress(base + (S.meta.encrypted ? 'data.bin.enc' : 'data.bin'), (p, got) => {
    $('ovBar').style.width = `${Math.round(p * 100)}%`; $('ovMsg').textContent = `${(got / 1e6).toFixed(1)} MB`;
  });
  if (S.meta.encrypted) {
    let pass = keyFromFragment(), msg = '';
    for (;;) {
      if (pass === null) pass = await askPassphrase(msg);
      $('ovMsg').textContent = 'Decrypting…';
      try { buf = await decryptBundle(buf, pass); break; }
      catch (e) { msg = e.message === 'wrong passphrase' ? 'Wrong passphrase, try again.' : e.message; pass = null; }
    }
  }
  const o = S.meta.offsets;
  S.indices = new Uint32Array(buf, o.indices[0], o.indices[1] / 4);
  S.positions = new Float32Array(buf, o.positions[0], o.positions[1] / 4);
  for (const f of S.meta.fields) {
    const k = `field:${f.name}`; S.fields[f.name] = new Float32Array(buf, o[k][0], o[k][1] / 4);
  }
  if (o.lines) S.lines = new Uint32Array(buf, o.lines[0], o.lines[1] / 4);
}

// ------------------------------------------------------------------ scene build
function build() {
  const m = S.meta, n = m.nVerts;
  geometry = new THREE.BufferGeometry();
  geometry.setIndex(new THREE.BufferAttribute(S.indices, 1));
  geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
  // one geometry group per part so parts can be hidden individually (material.visible per group)
  const parts = m.parts && m.parts.length ? m.parts : [{ id: 0, name: 'mesh', start: 0, count: S.indices.length }];
  const mats = [], wmats = [];
  parts.forEach((p, k) => { geometry.addGroup(p.start, p.count, k); mats.push(material.clone()); wmats.push(wireMat.clone()); });
  S.partMats = mats; S.wireMats = wmats;
  mesh = new THREE.Mesh(geometry, mats); mesh.frustumCulled = false; scene.add(mesh);
  wire = new THREE.Mesh(geometry, wmats); wire.frustumCulled = false; wire.visible = false; scene.add(wire);
  if (m.lines && S.lines && m.lines.count) {
    S.rodRadius = m.lines.radius;
    rods = new THREE.InstancedMesh(new THREE.CylinderGeometry(1, 1, 1, 8, 1), rodMat, m.lines.count);
    rods.frustumCulled = false; scene.add(rods);
  }

  const [lo, hi] = m.bbox;
  const size = Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
  axes = new THREE.AxesHelper(size * 0.5); axes.visible = false; axes.position.set(lo[0], lo[1], lo[2]); scene.add(axes);
  camera.near = size / 1000; camera.far = size * 100; camera.updateProjectionMatrix();
  resetView();
  setFrame(0);
}

function resetView() {
  const d = S.meta.defaults;
  applyCamera((d && d.camera) || { dir: [0.7, 0.5, 1], up: [0, 1, 0], dist: 1.4 });
}

// Camera pose. Relative form (works for any run of the same kind of model): dir = viewing direction
// from the target towards the camera, dist = distance in bounding-box diagonals, target = fractions of
// the bounding box (default centre). Absolute form: pos, target, up in model coordinates.
function applyCamera(c) {
  const [lo, hi] = S.meta.bbox;
  const size = Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
  if (c.pos) {
    camera.position.fromArray(c.pos); controls.target.fromArray(c.target || [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2]);
  } else {
    const f = c.target || [0.5, 0.5, 0.5];
    controls.target.set(lo[0] + f[0] * (hi[0] - lo[0]), lo[1] + f[1] * (hi[1] - lo[1]), lo[2] + f[2] * (hi[2] - lo[2]));
    camera.position.copy(controls.target).add(new THREE.Vector3().fromArray(c.dir).normalize().multiplyScalar(size * (c.dist || 1.4)));
  }
  camera.up.fromArray(c.up || [0, 1, 0]).normalize(); controls.update();
}

// URL of the current view (case, field, colormap, range, frame, camera, hidden parts, clip planes)
function viewUrl() {
  const u = new URL(location.href); const q = u.searchParams; q.set('case', caseName);
  q.set('field', S.field); q.set('cmap', S.cmap);
  if (S.rangeMode === 'custom') q.set('range', `${$('rmin').value},${$('rmax').value}`); else q.delete('range');
  q.set('frame', S.frame); q.set('autoplay', '0');
  const r = v => +v.toPrecision(5);
  q.set('cam', [...camera.position.toArray(), ...controls.target.toArray(), ...camera.up.toArray()].map(r).join(','));
  const hide = (S.meta.parts || []).filter((p, k) => S.partMats[k] && !S.partMats[k].visible).map(p => p.id);
  if (rods && !rods.visible) hide.push('rods');
  if (hide.length) q.set('hide', hide.join(',')); else q.delete('hide');
  for (const ax of ['X', 'Y', 'Z']) { const c = S.clip[ax]; if (c.on) q.set('clip' + ax, (c.flip ? -c.v : c.v).toFixed(3)); else q.delete('clip' + ax); }
  u.search = q.toString();
  return u.href;
}

function setFrame(i) {
  const m = S.meta; i = ((i % m.nFrames) + m.nFrames) % m.nFrames; S.frame = i;
  const n3 = m.nVerts * 3;
  geometry.attributes.position.array.set(S.positions.subarray(i * n3, (i + 1) * n3));
  geometry.attributes.position.needsUpdate = true;
  geometry.computeVertexNormals();
  poseRods();
  colorize();
  $('frame').value = i;
  const t = m.times[i];
  $('tlabel').textContent = `${i + 1}/${m.nFrames}  t=${fmt(t)}`;
}

const _a = new THREE.Vector3(), _b = new THREE.Vector3(), _q = new THREE.Quaternion(), _m = new THREE.Matrix4(), _s = new THREE.Vector3(), _up = new THREE.Vector3(0, 1, 0);
function poseRods() {
  if (!rods) return;
  const P = geometry.attributes.position.array, L = S.lines, r = S.rodRadius;
  for (let k = 0; k < rods.count; k++) {
    const i = L[2 * k] * 3, j = L[2 * k + 1] * 3;
    _a.set(P[i], P[i + 1], P[i + 2]); _b.set(P[j], P[j + 1], P[j + 2]);
    const len = _a.distanceTo(_b);
    _b.sub(_a).normalize(); _q.setFromUnitVectors(_up, _b);
    _a.addScaledVector(_b, len / 2); _s.set(r, len, r);
    _m.compose(_a, _q, _s); rods.setMatrixAt(k, _m);
  }
  rods.instanceMatrix.needsUpdate = true;
}

function currentRange() {
  const f = S.meta.fields.find(f => f.name === S.field);
  if (S.rangeMode === 'frame') return [f.frameMin[S.frame], f.frameMax[S.frame]];
  if (S.rangeMode === 'custom') {
    const a = parseFloat($('rmin').value), b = parseFloat($('rmax').value);
    return [isFinite(a) ? a : f.min, isFinite(b) ? b : f.max];
  }
  return [f.min, f.max];
}

function colorize() {
  const col = geometry.attributes.color.array, n = S.meta.nVerts;
  if (S.field === 'none' || !S.fields[S.field]) {
    const light = document.documentElement.dataset.theme === 'light';
    col.fill(light ? 0.72 : 0.78);
    $('legend').style.display = 'none';
  } else {
    const vals = S.fields[S.field].subarray(S.frame * n, (S.frame + 1) * n);
    const [lo, hi] = currentRange(); const inv = hi > lo ? 1 / (hi - lo) : 0; const lut = S.lut;
    for (let k = 0; k < n; k++) {
      let x = (vals[k] - lo) * inv; x = x < 0 ? 0 : x > 1 ? 1 : x; if (x !== x) x = 0;
      const j = Math.round(x * 255) * 3;
      col[k * 3] = lut[j]; col[k * 3 + 1] = lut[j + 1]; col[k * 3 + 2] = lut[j + 2];
    }
    $('legend').style.display = ''; $('legendName').textContent = prettyField(S.field);
    $('legendMin').textContent = fmt(lo); $('legendMid').textContent = fmt((lo + hi) / 2); $('legendMax').textContent = fmt(hi);
  }
  geometry.attributes.color.needsUpdate = true;
}

const SUFFIX = { mag: 'magnitude', vm: 'von Mises', trace: 'trace' };
const prettyField = f => { const [n, c] = f.split('|'); return c ? `${n} (${SUFFIX[c] || c})` : n; };

// ------------------------------------------------------------------ clipping
function updateClipping() {
  const [lo, hi] = S.meta.bbox; const active = [];
  ['X', 'Y', 'Z'].forEach((ax, k) => {
    const c = S.clip[ax], p = planes[ax];
    if (!c.on) return;
    const pos = lo[k] + c.v * (hi[k] - lo[k]);
    const sign = c.flip ? 1 : -1;
    p.normal.set(0, 0, 0); p.normal.setComponent(k, sign); p.constant = -sign * pos;
    active.push(p);
  });
  for (const mm of [...(S.partMats || []), ...(S.wireMats || [])]) mm.clippingPlanes = active;
  rodMat.clippingPlanes = active;
}

// ------------------------------------------------------------------ UI wiring
function wireUI() {
  const m = S.meta;
  $('title').textContent = m.title; $('desc').textContent = m.description || '';
  $('stats').textContent = `${m.nFrames} frames · ${m.nVerts.toLocaleString()} vertices · ${m.nTris.toLocaleString()} triangles`
    + (rods ? ` · ${rods.count} ${m.lines.name.toLowerCase()}` : '');
  $('frame').max = m.nFrames - 1;
  if (m.nFrames < 2) { $('timeline').style.display = 'none'; document.querySelector('.viewer').classList.add('static'); }

  const fs = $('field');
  fs.innerHTML = '<option value="none">— solid —</option>' + m.fields.map(f => `<option value="${f.name}">${prettyField(f.name)}</option>`).join('');
  if (m.fields.length) { fs.value = m.fields[0].name; S.field = fs.value; }
  fs.onchange = () => { S.field = fs.value; syncCustom(); colorize(); };
  const cm = $('cmap'); cm.innerHTML = COLORMAPS.map(c => `<option>${c}</option>`).join('');
  cm.onchange = () => { S.cmap = cm.value; S.lut = buildLUT(S.cmap); drawLegend($('legendBar'), S.cmap); colorize(); };
  drawLegend($('legendBar'), S.cmap);
  $('rangeMode').onchange = e => { S.rangeMode = e.target.value; $('customRange').style.display = S.rangeMode === 'custom' ? '' : 'none'; syncCustom(); colorize(); };
  const syncCustom = () => { const f = m.fields.find(f => f.name === S.field); if (f && S.rangeMode === 'custom' && !$('rmin').value) { $('rmin').value = f.min; $('rmax').value = f.max; } };
  $('rmin').oninput = $('rmax').oninput = colorize;

  for (const ax of ['X', 'Y', 'Z']) {
    $('clip' + ax).onchange = e => { S.clip[ax].on = e.target.checked; updateClipping(); };
    $('clip' + ax + 'v').oninput = e => { S.clip[ax].v = +e.target.value; if (!S.clip[ax].on) { S.clip[ax].on = true; $('clip' + ax).checked = true; } updateClipping(); };
    $('clip' + ax + 'f').onclick = () => { S.clip[ax].flip = !S.clip[ax].flip; updateClipping(); };
  }

  $('wire').onchange = e => wire.visible = e.target.checked;
  $('flat').onchange = e => { for (const mm of S.partMats) { mm.flatShading = e.target.checked; mm.needsUpdate = true; } };
  const partsBox = $('parts');
  if (m.parts && (m.parts.length > 1 || rods)) {
    $('partsSection').style.display = '';
    m.parts.forEach((p, k) => {
      const lab = document.createElement('label');
      lab.innerHTML = `<input type="checkbox" checked> ${p.name}`;
      lab.querySelector('input').onchange = e => { S.partMats[k].visible = e.target.checked; S.wireMats[k].visible = e.target.checked; };
      partsBox.appendChild(lab);
    });
  }
  if (rods) {
    $('partsSection').style.display = '';
    const lab = document.createElement('label');
    lab.innerHTML = `<input type="checkbox" checked> ${m.lines.name}`;
    lab.querySelector('input').onchange = e => rods.visible = e.target.checked;
    partsBox.appendChild(lab);
  }
  $('axes').onchange = e => axes.visible = e.target.checked;
  $('reset').onclick = resetView;
  $('copyview').onclick = async () => {
    const url = viewUrl(); const b = $('copyview');
    try { await navigator.clipboard.writeText(url); b.textContent = 'Copied!'; } catch (e) { prompt('Copy this link', url); }
    setTimeout(() => { b.textContent = 'Copy view'; }, 1500);
  };
  $('shot').onclick = () => {
    // render once with a transparent background so the PNG can be dropped onto slides/figures
    const bg = scene.background; scene.background = null; renderer.setClearColor(0x000000, 0);
    renderer.render(scene, camera);
    const a = document.createElement('a'); a.download = `${m.name}_frame${S.frame + 1}.png`; a.href = canvas.toDataURL('image/png'); a.click();
    scene.background = bg; renderer.setClearColor(0x000000, 1);
  };

  $('frame').oninput = e => { setPlaying(false); setFrame(+e.target.value); };
  $('play').onclick = () => setPlaying(!S.playing);
  $('prev').onclick = () => { setPlaying(false); setFrame(S.frame - 1); };
  $('next').onclick = () => { setPlaying(false); setFrame(S.frame + 1); };
  window.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    if (e.code === 'Space') { e.preventDefault(); setPlaying(!S.playing); }
    else if (e.key === 'ArrowRight') { setPlaying(false); setFrame(S.frame + 1); }
    else if (e.key === 'ArrowLeft') { setPlaying(false); setFrame(S.frame - 1); }
    else if (e.key === 'r') resetView();
  });

  const panel = $('panel'), tog = $('toggle-panel');
  $('close-panel').onclick = () => { panel.classList.add('hidden'); tog.classList.add('show'); };
  tog.onclick = () => { panel.classList.remove('hidden'); tog.classList.remove('show'); };
  if (innerWidth < 700) $('close-panel').onclick();
}

// Per-case defaults from meta.json ("defaults": {field, cmap, range:[lo,hi]}); URL params still override
function applyDefaults() {
  const d = S.meta.defaults; if (!d) return;
  if (d.field && (d.field === 'none' || S.fields[d.field])) { S.field = d.field; $('field').value = d.field; }
  if (d.cmap && COLORMAPS.includes(d.cmap)) { S.cmap = d.cmap; S.lut = buildLUT(d.cmap); $('cmap').value = d.cmap; drawLegend($('legendBar'), d.cmap); }
  if (Array.isArray(d.range) && d.range.length === 2) {
    S.rangeMode = 'custom'; $('rangeMode').value = 'custom'; $('customRange').style.display = '';
    $('rmin').value = d.range[0]; $('rmax').value = d.range[1];
  }
}

// Optional URL params: &field=pressure&cmap=jet&frame=5&clipX=0.4&clipY=-0.6 (negative = flipped)
function applyUrlParams() {
  const f = params.get('field'); if (f && (f === 'none' || S.fields[f])) { S.field = f; $('field').value = f; }
  const c = params.get('cmap'); if (c && COLORMAPS.includes(c)) { S.cmap = c; S.lut = buildLUT(c); $('cmap').value = c; drawLegend($('legendBar'), c); }
  for (const ax of ['X', 'Y', 'Z']) {
    const v = parseFloat(params.get('clip' + ax)); if (!isFinite(v)) continue;
    S.clip[ax] = { on: true, flip: v < 0, v: Math.abs(v) }; $('clip' + ax).checked = true; $('clip' + ax + 'v').value = Math.abs(v);
  }
  updateClipping();
  const hideRaw = (params.get('hide') || '').split(',').filter(Boolean);
  if (rods && hideRaw.includes('rods')) { rods.visible = false; const cbs = $('parts').querySelectorAll('input'); cbs[cbs.length - 1].checked = false; }
  const hide = hideRaw.map(Number);
  if (hide.length && S.meta.parts) S.meta.parts.forEach((p, k) => {
    if (hide.includes(p.id)) { S.partMats[k].visible = S.wireMats[k].visible = false; const cb = $('parts').querySelectorAll('input')[k]; if (cb) cb.checked = false; }
  });
  const fr = parseInt(params.get('frame')); if (isFinite(fr)) setFrame(fr);
  const rg = (params.get('range') || '').split(',').map(Number);
  if (rg.length === 2 && rg.every(isFinite)) { S.rangeMode = 'custom'; $('rangeMode').value = 'custom'; $('customRange').style.display = ''; $('rmin').value = rg[0]; $('rmax').value = rg[1]; }
  const d = S.meta.defaults || {};
  if (params.get('pose') === 'thumb' && d.thumbCamera) applyCamera(d.thumbCamera);  // make_preview.py
  const cam = (params.get('cam') || '').split(',').map(Number);
  if (cam.length === 9 && cam.every(isFinite)) applyCamera({ pos: cam.slice(0, 3), target: cam.slice(3, 6), up: cam.slice(6, 9) });
  const z = parseFloat(params.get('zoom'));  // &zoom=2 = camera twice as close (used by make_preview.py)
  if (z > 0) { camera.position.sub(controls.target).multiplyScalar(1 / z).add(controls.target); controls.update(); }
}

function setPlaying(p) {
  S.playing = p && S.meta.nFrames > 1; S.acc = 0;
  $('play').textContent = S.playing ? '❚❚' : '▶';
}

// ------------------------------------------------------------------ loop
function animate(t) {
  requestAnimationFrame(animate);
  resize();
  const dt = Math.min((t - S.lastT) / 1000, 0.1); S.lastT = t;
  if (S.playing) {
    S.acc += dt; const period = 1 / (+$('fps').value || 12);
    if (S.acc >= period) { const steps = Math.floor(S.acc / period); S.acc -= steps * period; setFrame(S.frame + steps); }
  }
  controls.update();
  renderer.render(scene, camera);
}

// ------------------------------------------------------------------ go
(async () => {
  try {
    await load();
    build(); wireUI(); applyDefaults(); applyUrlParams();
    if (S.field !== 'none') colorize();
    if (params.get('ui') === '0') document.querySelector('.viewer').classList.add('noui');  // headless preview rendering
    window.fem = { setFrame, meta: S.meta };  // hook for exporter/make_preview.py
    $('overlay').style.display = 'none';
    requestAnimationFrame(t => { S.lastT = t; animate(t); });
    if (params.get('autoplay') !== '0') setPlaying(true);
  } catch (e) {
    console.error(e);
    $('ovTitle').innerHTML = '<b>Could not load case</b>'; $('ovBar').parentElement.style.display = 'none';
    $('ovMsg').innerHTML = `<span class="error">${e.message}</span>`;
  }
})();
