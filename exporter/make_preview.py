#!/usr/bin/env python3
"""Render link-preview assets for an exported case with headless Chrome:

    site/cases/<name>/preview.jpg   static Open Graph image (last frame, 1200x675)
    site/cases/<name>/preview.gif   animation to paste/attach in a chat (800 px wide)
    site/cases/<name>/preview.mp4   same animation, much smaller (needs ffmpeg)
    site/cases/<name>/index.html    share page: OG tags + redirect into viewer.html?case=<name>

Share  <base-url>/cases/<name>/  instead of the viewer URL: chat apps show the thumbnail, the
browser is forwarded to the viewer (query and #k=... fragment are kept).

Usage:
    make_preview.py <name> [--frames 40] [--size 960x540] [--fps 12] [--base-url URL]
                           [--zoom 1.3] [--view "field=stress|p1&cmap=coolwarm"]

Needs google-chrome, pillow and websockets (pip) in the user site-packages; ffmpeg is optional.
Encrypted cases: pass --passphrase so the renderer can open them (the assets themselves are
public, so keep the preview camera angle / field uninformative if that matters).
"""
import argparse
import asyncio
import base64
import io
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets
from PIL import Image

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / "site"
DEFAULT_BASE = "https://nmanthatis.github.io/fem-web-viewer"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Chrome:
    def __init__(self, width, height):
        self.port = free_port()
        self.tmp = tempfile.mkdtemp(prefix="cdp-")
        self.proc = subprocess.Popen(
            ["google-chrome", "--headless=new", "--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
             f"--window-size={width},{height}", "--hide-scrollbars", f"--remote-debugging-port={self.port}",
             f"--user-data-dir={self.tmp}", "--disk-cache-size=1", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json"))
                break
            except Exception:
                time.sleep(0.1)
        else:
            sys.exit("chrome did not start")
        self.ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]
        self.n = 0

    async def __aenter__(self):
        self.ws = await websockets.connect(self.ws_url, max_size=2**30)
        return self

    async def __aexit__(self, *a):
        await self.ws.close()
        self.proc.terminate()
        shutil.rmtree(self.tmp, ignore_errors=True)

    async def call(self, method, **params):
        self.n += 1
        await self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    async def js(self, expr):
        r = await self.call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description", str(r["exceptionDetails"])))
        return r.get("result", {}).get("value")

    async def shot(self):
        r = await self.call("Page.captureScreenshot", format="png")
        return Image.open(io.BytesIO(base64.b64decode(r["data"]))).convert("RGB")


async def render(args, url, n_frames):
    want = min(args.frames, n_frames) if args.frames else n_frames
    idx = sorted({round(i * (n_frames - 1) / max(want - 1, 1)) for i in range(want)})
    frames = []
    async with Chrome(*args.size) as c:
        await c.call("Page.enable")
        # the window size includes Chrome's toolbar: force the viewport itself
        await c.call("Emulation.setDeviceMetricsOverride", width=args.size[0], height=args.size[1], deviceScaleFactor=1, mobile=False)
        await c.call("Page.navigate", url=url)
        for _ in range(300):  # wait until the viewer has built the scene
            if await c.js("!!(window.fem && document.getElementById('overlay').style.display === 'none')"):
                break
            await asyncio.sleep(0.1)
        else:
            sys.exit("viewer did not finish loading (wrong passphrase? open the url in a browser to check): " + url)
        for k, i in enumerate(idx):
            await c.js(f"fem.setFrame({i}); new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            frames.append(await c.shot())
            print(f"\r  frame {k + 1}/{len(idx)}", end="", flush=True)
        print()
    return frames


def write_share_page(out, meta, base, has_mp4, size, vsize):
    name, title = meta["name"], meta["title"]
    desc = (meta.get("description") or "Interactive FEM animation").replace('"', "&quot;")
    page_url = f"{base}/cases/{name}/"
    video = (f'<meta property="og:video" content="{base}/cases/{name}/preview.mp4">\n'
             f'<meta property="og:video:secure_url" content="{base}/cases/{name}/preview.mp4">\n'
             f'<meta property="og:video:type" content="video/mp4">\n'
             f'<meta property="og:video:width" content="{vsize[0]}">\n<meta property="og:video:height" content="{vsize[1]}">\n') if has_mp4 else ""
    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} – FEM Viewer</title>
<meta name="description" content="{desc}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="FEM Viewer">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{page_url}">
<meta property="og:image" content="{base}/cases/{name}/preview.jpg">
<meta property="og:image:type" content="image/jpeg">
<meta property="og:image:width" content="{size[0]}">
<meta property="og:image:height" content="{size[1]}">
{video}<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{base}/cases/{name}/preview.jpg">
<script>
  // Forward into the viewer, keeping any ?field=...&frame=... options and the #k=CODE fragment.
  var q = location.search ? '&' + location.search.slice(1) : '';
  location.replace('../../viewer.html?case={name}' + q + location.hash);
</script>
<style>body{{font-family:system-ui,sans-serif;background:#1b1e26;color:#e6e8ee;margin:0;padding:24px;text-align:center}}img{{max-width:100%;border-radius:8px}}a{{color:#5aa9ff}}</style>
</head>
<body>
<h1>{title}</h1>
<p><a href="../../viewer.html?case={name}">Open the interactive viewer</a></p>
<img src="preview.gif" alt="{title} animation">
</body>
</html>
'''
    (out / "index.html").write_text(html)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="case id (folder under site/cases)")
    ap.add_argument("--frames", type=int, default=40, help="frames in the GIF/MP4 (evenly picked; 0 = all)")
    ap.add_argument("--size", default="1200x675", help="render size WxH (= the OG image size)")
    ap.add_argument("--gif-width", type=int, default=800, help="GIF/MP4 are downscaled to this width")
    ap.add_argument("--fps", type=float, default=12)
    ap.add_argument("--zoom", type=float, default=1.3, help="camera closer than the viewer's default by this factor")
    ap.add_argument("--view", default="", help="extra viewer URL params, e.g. 'field=stress|p1&cmap=coolwarm&hide=rods'")
    ap.add_argument("--passphrase", help="for encrypted cases")
    ap.add_argument("--base-url", default=DEFAULT_BASE, help="public site URL for the absolute OG links")
    ap.add_argument("--site", default=str(SITE))
    args = ap.parse_args()
    args.size = tuple(int(v) for v in args.size.lower().split("x"))

    site = Path(args.site)
    out = site / "cases" / args.name
    meta = json.loads((out / "meta.json").read_text())
    base = args.base_url.rstrip("/")

    port = free_port()
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(site)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(0.5)
        url = f"http://127.0.0.1:{port}/viewer.html?case={args.name}&autoplay=0&ui=0&zoom={args.zoom:g}"
        if args.view:
            url += "&" + args.view.lstrip("&?")
        if args.passphrase:
            url += "#k=" + args.passphrase
        print(f"rendering {meta['nFrames']} frames of {args.name} at {args.size[0]}x{args.size[1]}")
        frames = asyncio.run(render(args, url, meta["nFrames"]))
    finally:
        server.terminate()

    # static OG image: last frame (WhatsApp/Slack/Teams/iMessage all accept jpeg)
    frames[-1].save(out / "preview.jpg", quality=86, optimize=True)

    if args.gif_width and args.gif_width < args.size[0]:
        h = round(args.size[1] * args.gif_width / args.size[0])
        frames = [f.resize((args.gif_width, h), Image.LANCZOS) for f in frames]
    dur = int(round(1000 / args.fps))
    pal = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    pal[0].save(out / "preview.gif", save_all=True, append_images=pal[1:], duration=dur, loop=0, optimize=True)

    has_mp4 = False
    if shutil.which("ffmpeg"):
        with tempfile.TemporaryDirectory() as td:
            for k, f in enumerate(frames):
                f.save(Path(td) / f"{k:04d}.png")
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(args.fps), "-i", str(Path(td) / "%04d.png"),
                                "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
                                "-movflags", "+faststart", str(out / "preview.mp4")])
            has_mp4 = r.returncode == 0
    else:
        print("ffmpeg not found: no preview.mp4", file=sys.stderr)

    write_share_page(out, meta, base, has_mp4, args.size, frames[0].size)

    index_path = site / "cases" / "index.json"
    index = json.loads(index_path.read_text())
    for c in index:
        if c["name"] == args.name:
            c["preview"] = True
    index_path.write_text(json.dumps(index, indent=1))

    for f in ("preview.jpg", "preview.gif", "preview.mp4", "index.html"):
        if (out / f).exists():
            print(f"  {f:12s} {(out / f).stat().st_size / 1e6:5.2f} MB")
    print(f"share link with preview: {base}/cases/{args.name}/" + (f"#k={args.passphrase}" if args.passphrase else ""))


if __name__ == "__main__":
    main()
