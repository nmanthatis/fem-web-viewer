// Small colormap library: each map is a list of RGB stops in [0,1]; sample() interpolates.
const STOPS = {
  viridis: [[0.267,0.005,0.329],[0.283,0.141,0.458],[0.254,0.265,0.530],[0.207,0.372,0.553],[0.164,0.471,0.558],[0.128,0.567,0.551],[0.135,0.659,0.518],[0.267,0.749,0.441],[0.478,0.821,0.318],[0.741,0.873,0.150],[0.993,0.906,0.144]],
  coolwarm: [[0.230,0.299,0.754],[0.406,0.537,0.934],[0.602,0.731,0.999],[0.788,0.846,0.939],[0.865,0.865,0.865],[0.967,0.783,0.700],[0.947,0.604,0.502],[0.846,0.360,0.306],[0.706,0.016,0.150]],
  jet: [[0,0,0.5],[0,0,1],[0,0.5,1],[0,1,1],[0.5,1,0.5],[1,1,0],[1,0.5,0],[1,0,0],[0.5,0,0]],
  plasma: [[0.050,0.030,0.528],[0.294,0.012,0.631],[0.492,0.012,0.658],[0.665,0.138,0.586],[0.798,0.280,0.470],[0.902,0.425,0.357],[0.973,0.585,0.252],[0.993,0.771,0.155],[0.940,0.975,0.131]],
  grey: [[0.1,0.1,0.1],[0.95,0.95,0.95]],
};

export const COLORMAPS = Object.keys(STOPS);

/** Build a 256-entry Float32 LUT (r,g,b per entry). */
export function buildLUT(name, n = 256) {
  const stops = STOPS[name] || STOPS.viridis;
  const lut = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const x = (i / (n - 1)) * (stops.length - 1);
    const k = Math.min(Math.floor(x), stops.length - 2);
    const f = x - k;
    for (let c = 0; c < 3; c++) lut[i * 3 + c] = stops[k][c] * (1 - f) + stops[k + 1][c] * f;
  }
  return lut;
}

/** Draw a horizontal colorbar into a canvas. */
export function drawLegend(canvas, name) {
  const ctx = canvas.getContext('2d');
  const lut = buildLUT(name);
  const w = canvas.width, h = canvas.height;
  const img = ctx.createImageData(w, h);
  for (let x = 0; x < w; x++) {
    const i = Math.floor((x / (w - 1)) * 255) * 3;
    for (let y = 0; y < h; y++) {
      const p = (y * w + x) * 4;
      img.data[p] = lut[i] * 255; img.data[p + 1] = lut[i + 1] * 255; img.data[p + 2] = lut[i + 2] * 255; img.data[p + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
}

export function fmt(v) {
  if (v === 0) return '0';
  const a = Math.abs(v);
  if (a >= 1e4 || a < 1e-2) return v.toExponential(2);
  return v.toPrecision(3);
}
