#!/usr/bin/env python3
"""Capture the screenshot matrix for a visual diff.

Not part of `build.py`: this needs Playwright and a Chromium build, and the
point of the generator is that it needs nothing. Run it by hand before and
after a visual change and compare the two directories.

    export LD_LIBRARY_PATH=$HOME/miniconda3/envs/investing/lib
    ~/miniconda3/envs/investing/bin/python tools/shots.py --out /tmp/shots/after

`channel="chromium"` and LD_LIBRARY_PATH are both required on this box: the
default headless path uses chrome-headless-shell, which cannot find libnss3
and friends. They ship inside the conda env, which is what the env var points at.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import sys
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import _not_found_handler  # noqa: E402 - serve misses the way Pages does
PORT = 8911

PAGES = {
    "home": "index.html",
    "builds": "projects.html",
    "writing": "blog.html",
    "404": "404.html",
    "post-qubo": "posts/2026-08-13-qubo-portfolio-selection.html",
    "post-streamlit": "posts/2026-08-13-sixty-streamlit-pages.html",
    "post-guard": "posts/2026-08-13-a-scanner-for-my-own-repos.html",
    "post-currency": "posts/2026-08-13-currency-is-a-data-model.html",
    "post-backtest": "posts/2026-08-13-every-backtest-number-was-wrong.html",
}
VIEWPORTS = {"desktop": (1440, 900), "mobile": (390, 844)}
STRIP = {"desktop": 900, "mobile": 1000}


_Quiet = functools.partial(_not_found_handler(), directory=str(ROOT))


def serve(port: int = PORT) -> http.server.ThreadingHTTPServer:
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), _Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def strips(path: Path, height: int) -> int:
    """Slice a tall capture into readable viewport-sized pieces."""
    try:
        from PIL import Image
    except ImportError:
        return 0
    img = Image.open(path)
    w, h = img.size
    out = path.parent / "strips"
    out.mkdir(exist_ok=True)
    n = 0
    for top in range(0, h, height):
        box = (0, top, w, min(top + height, h))
        if box[3] - box[1] < 80:
            continue
        img.crop(box).save(out / f"{path.stem.replace('--full', '')}--s{n:02d}.png")
        n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="directory to write PNGs into")
    ap.add_argument("--no-strips", action="store_true", help="skip slicing full-page captures")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    srv = serve()
    base = f"http://127.0.0.1:{PORT}/"
    written = 0
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, channel="chromium", args=["--no-sandbox"], env={**os.environ}
            )
            for theme in ("dark", "light"):
                for vp, (w, h) in VIEWPORTS.items():
                    ctx = browser.new_context(
                        viewport={"width": w, "height": h}, device_scale_factor=1, reduced_motion="reduce"
                    )
                    ctx.add_init_script(f"try{{localStorage.setItem('theme','{theme}')}}catch(e){{}}")
                    page = ctx.new_page()
                    for name, path in PAGES.items():
                        page.goto(base + path, wait_until="networkidle")
                        page.wait_for_timeout(250)
                        full = out / f"{name}--{theme}--{vp}--full.png"
                        page.screenshot(path=str(full), full_page=True)
                        page.screenshot(path=str(out / f"{name}--{theme}--{vp}--fold.png"))
                        written += 2
                        if not args.no_strips:
                            strips(full, STRIP[vp])
                    if vp == "mobile":
                        page.goto(base + "index.html", wait_until="networkidle")
                        page.click("#nav-burger")
                        page.wait_for_timeout(400)
                        page.screenshot(path=str(out / f"home--{theme}--mobile--navopen.png"))
                        written += 1
                    ctx.close()
            browser.close()
    finally:
        srv.shutdown()
    print(f"wrote {written} captures to {out}")


if __name__ == "__main__":
    main()
