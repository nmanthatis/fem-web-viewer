import * as THREE from 'three';
import { TrackballControls } from 'three/addons/controls/TrackballControls.js';
import { COLORMAPS, buildLUT, drawLegend, fmt } from './colormaps.js';
import { decryptBundle, keyFromFragment } from './crypto.js';

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
let geometry, mesh, wire, axes;

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
}

// ------------------------------------------------------------------ scene build
function build() {
  const m = S.meta, n = m.nVerts;
  geometry = new THREE.BufferGeometry();
  geometry.setIndex(new THREE.BufferAttribute(S.indices, 1));
  geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
  mesh = new THREE.Mesh(geometry, material); mesh.frustumCulled = false; scene.add(mesh);
  wire = new THREE.Mesh(geometry, wireMat); wire.frustumCulled = false; wire.visible = false; scene.add(wire);

  const [lo, hi] = m.bbox;
  const size = Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
  axes = new THREE.AxesHelper(size * 0.5); axes.visible = false; axes.position.set(lo[0], lo[1], lo[2]); scene.add(axes);
  camera.near = size / 1000; camera.far = size * 100; camera.updateProjectionMatrix();
  resetView();
  setFrame(0);
}

function resetView() {
  const [lo, hi] = S.meta.bbox;
  const c = new THREE.Vector3((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2);
  const size = Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
  camera.position.copy(c).add(new THREE.Vector3(0.7, 0.5, 1).normalize().multiplyScalar(size * 1.4));
  camera.up.set(0, 1, 0); controls.target.copy(c); controls.update();
}

function setFrame(i) {
  const m = S.meta; i = ((i % m.nFrames) + m.nFrames) % m.nFrames; S.frame = i;
  const n3 = m.nVerts * 3;
  geometry.attributes.position.array.set(S.positions.subarray(i * n3, (i + 1) * n3));
  geometry.attributes.position.needsUpdate = true;
  geometry.computeVertexNormals();
  colorize();
  $('frame').value = i;
  const t = m.times[i];
  $('tlabel').textContent = `${i + 1}/${m.nFrames}  t=${fmt(t)}`;
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
  material.clippingPlanes = active; wireMat.clippingPlanes = active;
}

// ------------------------------------------------------------------ UI wiring
function wireUI() {
  const m = S.meta;
  $('title').textContent = m.title; $('desc').textContent = m.description || '';
  $('stats').textContent = `${m.nFrames} frames · ${m.nVerts.toLocaleString()} vertices · ${m.nTris.toLocaleString()} triangles`;
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
  $('flat').onchange = e => { material.flatShading = e.target.checked; material.needsUpdate = true; };
  $('axes').onchange = e => axes.visible = e.target.checked;
  $('reset').onclick = resetView;
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

// Optional URL params: &field=pressure&cmap=jet&frame=5&clipX=0.4&clipY=-0.6 (negative = flipped)
function applyUrlParams() {
  const f = params.get('field'); if (f && (f === 'none' || S.fields[f])) { S.field = f; $('field').value = f; }
  const c = params.get('cmap'); if (c && COLORMAPS.includes(c)) { S.cmap = c; S.lut = buildLUT(c); $('cmap').value = c; drawLegend($('legendBar'), c); }
  for (const ax of ['X', 'Y', 'Z']) {
    const v = parseFloat(params.get('clip' + ax)); if (!isFinite(v)) continue;
    S.clip[ax] = { on: true, flip: v < 0, v: Math.abs(v) }; $('clip' + ax).checked = true; $('clip' + ax + 'v').value = Math.abs(v);
  }
  updateClipping();
  const fr = parseInt(params.get('frame')); if (isFinite(fr)) setFrame(fr);
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
    build(); wireUI(); applyUrlParams();
    if (S.field !== 'none') colorize();
    $('overlay').style.display = 'none';
    requestAnimationFrame(t => { S.lastT = t; animate(t); });
    if (params.get('autoplay') !== '0') setPlaying(true);
  } catch (e) {
    console.error(e);
    $('ovTitle').innerHTML = '<b>Could not load case</b>'; $('ovBar').parentElement.style.display = 'none';
    $('ovMsg').innerHTML = `<span class="error">${e.message}</span>`;
  }
})();
