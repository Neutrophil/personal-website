#!/usr/bin/env python3
"""Measure the things `build.py --check` cannot see, and fail if they regress.

`--check` reasons about the sources: tokens, links, frontmatter, and contrast
between flat hex pairs. It has no browser, so it cannot know what a colour
becomes after alpha compositing, how small an SVG label ends up once the figure
is scaled, how much of a code block is clipped off-screen, or whether the page
is still readable when a script fails to load. This does, by driving Chromium.

    export LD_LIBRARY_PATH=$HOME/miniconda3/envs/investing/lib
    ~/miniconda3/envs/investing/bin/python tools/audit.py

Exits non-zero on any failure, so it can gate a commit the same way --check does.
"""

from __future__ import annotations

import http.server
import json
import re
import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8912

PAGES = {
    "home": "index.html",
    "builds": "projects.html",
    "writing": "blog.html",
    "404": "404.html",
    "post": "posts/2026-08-13-qubo-portfolio-selection.html",
}

# Text that carries meaning and must survive compositing, opacity and small size.
TEXT_SELECTORS = [
    "body", ".hero__lede", ".prose p", ".tags li", ".chip", ".chip__n", ".codeblock code",
    ".codeblock__name", ".diagram figcaption", ".callout p", ".spec__k", ".spec__v",
    ".build__note", ".groupnote", ".pindex__tag", ".postcard__meta", ".post__meta",
    ".facts__title", ".facts__row dd", ".timeline__date", ".footer__meta", ".section__lede",
    ".pub p", ".postnav__title", ".codeblock__copy", ".nav__links a", ".eyebrow", ".section__num",
]

MIN_DIAGRAM_LABEL_PX = 10.0
MIN_TARGET_PX = 24  # WCAG 2.2 AA minimum for a pointer target

# Colour parsing has to understand both legacy rgb()/rgba() (0-255) and the
# color(srgb r g b / a) form Chromium returns for color-mix(), whose channels
# are 0-1. Reading the second as the first is how an earlier pass invented a
# contrast failure that did not exist.
JS_CONTRAST = r"""(sels) => {
  const parse = (c) => {
    if (!c || c === 'transparent') return {r:0,g:0,b:0,a:0};
    const nums = (c.match(/-?[\d.]+(?:e-?\d+)?/g) || []).map(Number);
    if (c.startsWith('color(')) {
      const [r,g,b] = nums.slice(0,3).map(v => v * 255);
      return {r, g, b, a: nums.length > 3 ? nums[3] : 1};
    }
    return {r: nums[0]||0, g: nums[1]||0, b: nums[2]||0, a: nums.length > 3 ? nums[3] : 1};
  };
  const over = (fg, bg) => ({r: fg.r*fg.a + bg.r*(1-fg.a), g: fg.g*fg.a + bg.g*(1-fg.a), b: fg.b*fg.a + bg.b*(1-fg.a), a: 1});
  const lum = (c) => { const f = v => { v /= 255; return v <= 0.04045 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); };
                       return 0.2126*f(c.r) + 0.7152*f(c.g) + 0.0722*f(c.b); };
  const bgOf = (el) => {
    const stack = []; let n = el;
    while (n && n !== document.documentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c.a > 0) stack.push(c);
      if (c.a === 1) break;
      n = n.parentElement;
    }
    let out = parse(getComputedStyle(document.body).backgroundColor);
    if (out.a < 1) out = {r:255,g:255,b:255,a:1};
    for (let i = stack.length - 1; i >= 0; i--) out = over(stack[i], out);
    return out;
  };
  const opacityOf = (el) => { let o = 1, n = el;
    while (n && n !== document.documentElement) { o *= parseFloat(getComputedStyle(n).opacity) || 1; n = n.parentElement; }
    return o; };
  return sels.map(sel => {
    const el = document.querySelector(sel);
    if (!el) return {sel, missing: true};
    const cs = getComputedStyle(el);
    const bg = bgOf(el);
    let fg = parse(cs.color);
    const o = opacityOf(el);
    if (o < 1) fg = {...fg, a: fg.a * o};
    const l1 = lum(over(fg, bg)), l2 = lum(bg);
    const hi = Math.max(l1,l2), lo = Math.min(l1,l2);
    const size = parseFloat(cs.fontSize), weight = parseInt(cs.fontWeight, 10) || 400;
    return {sel, size, weight, opacity: +o.toFixed(2),
            large: size >= 24 || (size >= 18.66 && weight >= 700),
            ratio: +(((hi + 0.05) / (lo + 0.05)).toFixed(2))};
  });
}"""

JS_PAGE = r"""() => {
  const vw = document.documentElement.clientWidth;
  const diagrams = [...document.querySelectorAll('.diagram svg')].map(svg => {
    const vb = svg.viewBox.baseVal;
    const scale = svg.getBoundingClientRect().width / (vb.width || 1);
    const sizes = [...svg.querySelectorAll('text')].map(t => parseFloat(getComputedStyle(t).fontSize) * scale);
    return {viewBox: vb.width, scale: +scale.toFixed(2), smallest: sizes.length ? +Math.min(...sizes).toFixed(1) : null};
  });
  /* WCAG 2.2 exempts a target that sits inside a sentence, which is most of the
     links in prose and in the footer row. Those are reported as advice, not as
     failures; anything that presents itself as a control is held to 24px. */
  const targets = [...document.querySelectorAll('a, button')].map(el => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {label: (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 30),
            w: Math.round(r.width), h: Math.round(r.height),
            inline: cs.display === 'inline'};
  }).filter(t => t.w > 0);
  const scrollers = [...document.querySelectorAll('pre, .diagram__scroll, .tablewrap')].map(el => ({
    kind: el.className || el.tagName.toLowerCase(),
    clipped: Math.max(0, Math.round(el.scrollWidth - el.clientWidth)),
    cued: getComputedStyle(el).backgroundImage !== 'none',
  }));
  return {
    pageOverflow: Math.max(0, document.documentElement.scrollWidth - vw),
    ariaCurrent: document.querySelectorAll('[aria-current="page"]').length,
    themeColor: document.querySelectorAll('meta[name="theme-color"]').length,
    diagrams, targets, scrollers,
    docHeight: document.documentElement.scrollHeight,
  };
}"""


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def log_message(self, *a):
        pass


def main() -> int:
    from playwright.sync_api import sync_playwright

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), _Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{PORT}/"
    problems: list[str] = []
    notes: list[str] = []
    small_inline: set[str] = set()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, channel="chromium", args=["--no-sandbox"], env={**os.environ}
            )

            for theme in ("dark", "light"):
                for width in (1440, 390):
                    ctx = browser.new_context(
                        viewport={"width": width, "height": 900}, reduced_motion="reduce"
                    )
                    ctx.add_init_script(
                        f"try{{localStorage.setItem('theme','{theme}')}}catch(e){{}}"
                    )
                    page = ctx.new_page()
                    for name, path in PAGES.items():
                        page.goto(base + path, wait_until="networkidle")
                        where = f"{name}/{theme}/{width}"

                        for row in page.evaluate(JS_CONTRAST, TEXT_SELECTORS):
                            if row.get("missing"):
                                continue
                            need = 3.0 if row["large"] else 4.5
                            if row["ratio"] < need:
                                problems.append(
                                    f"{where}: {row['sel']} is {row['ratio']}:1 at "
                                    f"{row['size']:.0f}px, below {need}:1"
                                )

                        facts = page.evaluate(JS_PAGE)
                        if facts["pageOverflow"] > 0:
                            problems.append(f"{where}: page scrolls {facts['pageOverflow']}px sideways")
                        if facts["ariaCurrent"] > 1:
                            problems.append(f"{where}: {facts['ariaCurrent']} elements marked as the current page")
                        if facts["themeColor"] == 0:
                            problems.append(f"{where}: no theme-color meta tag")
                        for d in facts["diagrams"]:
                            if d["smallest"] is not None and d["smallest"] < MIN_DIAGRAM_LABEL_PX:
                                problems.append(
                                    f"{where}: diagram label renders at {d['smallest']}px "
                                    f"(viewBox {d['viewBox']:.0f} at {d['scale']} scale)"
                                )
                        for t in facts["targets"]:
                            if t["h"] >= MIN_TARGET_PX and t["w"] >= MIN_TARGET_PX:
                                continue
                            if t["inline"]:
                                small_inline.add(f"{t['label']} ({t['w']}x{t['h']})")
                            else:
                                problems.append(f"{where}: control {t['w']}x{t['h']}px — {t['label']!r}")
                        for s in facts["scrollers"]:
                            if s["clipped"] > 0 and not s["cued"]:
                                problems.append(
                                    f"{where}: {s['kind']} hides {s['clipped']}px with no scroll cue"
                                )
                        notes.append(f"{where}: {facts['docHeight']}px tall")
                    ctx.close()

            # The page must survive its own JavaScript going missing.
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()
            page.route("**/js/main.js", lambda route: route.abort())
            page.goto(base + "index.html", wait_until="domcontentloaded")
            page.wait_for_timeout(400)
            reveal = page.evaluate(
                "()=>{const a=[...document.querySelectorAll('.reveal')];"
                "return {total:a.length, hidden:a.filter(e=>getComputedStyle(e).opacity==='0').length}}"
            )
            if reveal["hidden"]:
                problems.append(
                    f"main.js blocked: {reveal['hidden']} of {reveal['total']} elements stay invisible"
                )
            ctx.close()

            # Printing must not inherit the dark palette.
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            ctx.add_init_script("try{localStorage.setItem('theme','dark')}catch(e){}")
            page = ctx.new_page()
            page.goto(base + "index.html", wait_until="networkidle")
            page.emulate_media(media="print")
            # Ink is judged by contrast against paper, not by demanding pure black:
            # a grey caption prints fine, a near-white heading does not.
            print_sels = ["h1", "h2", ".section__title", ".facts__row dd",
                          ".timeline__org", ".prose p", ".spec__v", "body"]
            ink = page.evaluate(
                "(sels)=>sels.map(s=>{const e=document.querySelector(s);"
                "return e?{sel:s, color:getComputedStyle(e).color}:null}).filter(Boolean)",
                print_sels,
            )
            for row in ink:
                nums = [float(v) for v in re.findall(r"[\d.]+", row["color"])[:3]]
                if len(nums) < 3:
                    continue

                def channel(v: float) -> float:
                    v /= 255
                    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

                lum = 0.2126 * channel(nums[0]) + 0.7152 * channel(nums[1]) + 0.0722 * channel(nums[2])
                ratio = 1.05 / (lum + 0.05)
                if ratio < 4.5:
                    problems.append(
                        f"print from dark theme: {row['sel']} is {ratio:.1f}:1 on paper"
                    )
            ctx.close()

            # A menu that is not on screen must not be reachable by keyboard.
            ctx = browser.new_context(viewport={"width": 390, "height": 844})
            page = ctx.new_page()
            page.goto(base + "index.html", wait_until="networkidle")
            if page.evaluate(
                "()=>getComputedStyle(document.getElementById('nav-links')).visibility"
            ) != "hidden":
                problems.append("mobile: the closed nav panel is still in the tab order")
            ctx.close()
            browser.close()
    finally:
        srv.shutdown()

    for note in notes:
        print(f"  {note}")
    if small_inline:
        print("\n  inline links under 24px (exempt from the target rule, listed for judgement):")
        for item in sorted(small_inline):
            print(f"    {item}")
    if problems:
        print(f"\n✗ {len(problems)} problem(s):", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print("\n✓ audit passed — contrast, targets, diagrams, scroll cues, print, no-JS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
