#!/usr/bin/env python3
"""Render assets/og.png — the 1200x630 card social platforms show for a link.

Not part of `build.py`: this needs Pillow, and the whole point of the generator
is that it needs nothing. Run this by hand when the wordmark or palette changes,
and commit the result.

    ~/miniconda3/envs/investing/bin/python tools/make_og.py

The card is drawn to match css/styles.css — same canvas, same cyan and violet,
same waveform. If those tokens change, change them here too; nothing enforces it.

The wordmark is set in the site's own webfont, read straight out of
assets/fonts/. Pillow cannot open woff2, so fontTools decompresses it to a
TrueType file in a temp directory first. That keeps the card and the page on one
typeface without shipping a second copy of it.
"""

from __future__ import annotations

import atexit
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "og.png"
FONT_DIR = ROOT / "assets" / "fonts"

W, H = 1200, 630
PAD = 88

BG = (10, 11, 15)          # --bg
TEXT = (230, 232, 238)     # --text
SOFT = (154, 163, 184)     # --text-soft
FAINT = (125, 135, 158)    # --text-faint
CYAN = (34, 211, 238)      # --accent
VIOLET = (167, 139, 250)   # --accent-2

# Fallbacks only, for a machine without the site's fonts checked out.
FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FALLBACK_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

_TMP = Path(tempfile.mkdtemp(prefix="og-fonts-"))
atexit.register(shutil.rmtree, _TMP, True)


def _ttf(weight: str, fallback: str) -> str:
    """Return a TrueType path for one of the site's woff2 weights."""
    woff2 = FONT_DIR / f"jetbrains-mono-{weight}.woff2"
    if not woff2.is_file():
        return fallback
    try:
        from fontTools.ttLib import TTFont
    except ImportError:  # pragma: no cover - fontTools is a by-hand dependency
        print("fontTools not installed; falling back to DejaVu for the card")
        return fallback
    out = _TMP / f"{weight}.ttf"
    if not out.exists():
        face = TTFont(str(woff2))
        face.flavor = None
        face.save(str(out))
    return str(out)


MONO = _ttf("regular", FALLBACK)
MONO_BOLD = _ttf("bold", FALLBACK_BOLD)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError as exc:  # pragma: no cover - depends on the host's fonts
        raise SystemExit(f"font not found: {path} ({exc})")


def aurora(size: tuple[int, int]) -> Image.Image:
    """Two soft colour fields, matching the .aurora blur in the stylesheet."""
    layer = Image.new("RGB", size, BG)
    draw = ImageDraw.Draw(layer)
    draw.ellipse((-260, -320, 620, 300), fill=CYAN)
    draw.ellipse((700, -380, 1500, 220), fill=VIOLET)
    layer = layer.filter(ImageFilter.GaussianBlur(180))
    return Image.blend(Image.new("RGB", size, BG), layer, 0.22)


def dot_grid(img: Image.Image) -> None:
    """26px dot lattice, fading out toward the bottom like the CSS mask."""
    draw = ImageDraw.Draw(img, "RGBA")
    for y in range(0, H, 26):
        fade = max(0.0, 1.0 - (y / (H * 0.85)))
        alpha = int(46 * fade)
        if alpha <= 0:
            continue
        for x in range(0, W, 26):
            draw.point((x, y), fill=(126, 148, 190, alpha))


def waveform(draw: ImageDraw.ImageDraw, top: int) -> None:
    """The hero signal trace, same shape family as src/partials/signal.svg."""
    ys = [70, 66, 74, 58, 78, 50, 84, 44, 68, 32, 72, 26, 60, 38, 66, 18,
          74, 42, 80, 34, 88, 52, 62, 40, 76, 28, 58, 46, 66, 54, 70]
    step = (W - 2 * PAD) / (len(ys) - 1)
    pts = [(PAD + i * step, top + y * 0.62) for i, y in enumerate(ys)]

    # baseline
    draw.line([(PAD, top + 44), (W - PAD, top + 44)], fill=(40, 46, 62), width=1)
    draw.line(pts, fill=CYAN, width=3, joint="curve")

    for i in (15, 11, 25):
        x, y = pts[i]
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=CYAN)


def main() -> None:
    img = aurora((W, H))
    dot_grid(img)
    draw = ImageDraw.Draw(img)

    # corner ticks, echoing .card--tick (square on both, since 2026-09)
    t, ln = 34, 26
    for (cx, cy, dx, dy) in ((t, t, 1, 1), (W - t, t, -1, 1),
                             (t, H - t, 1, -1), (W - t, H - t, -1, -1)):
        draw.line([(cx, cy), (cx + dx * ln, cy)], fill=CYAN, width=2)
        draw.line([(cx, cy), (cx, cy + dy * ln)], fill=CYAN, width=2)

    # eyebrow: a drawn triangle, because the glyph is not in every font
    y = 150
    draw.polygon([(PAD, y + 2), (PAD, y + 16), (PAD + 12, y + 9)], fill=CYAN)
    draw.text((PAD + 24, y), "RESEARCH SCIENTIST II  ·  SINGAPORE",
              font=font(MONO, 22), fill=CYAN)

    draw.text((PAD, y + 46), "JUNJIE CHEN", font=font(MONO_BOLD, 92), fill=TEXT)

    # role line, with the plus picked out in the accent
    role_font = font(MONO, 38)
    ry = y + 172
    parts = [("AI for Life Science ", SOFT), ("·", CYAN), (" Clinical Genomics", SOFT)]
    x = PAD
    for text, colour in parts:
        draw.text((x, ry), text, font=role_font, fill=colour)
        x += draw.textlength(text, font=role_font)

    draw.line([(PAD, ry + 70), (W - PAD, ry + 70)], fill=(28, 32, 48), width=1)

    waveform(draw, ry + 104)

    small = font(MONO, 22)
    draw.text((PAD, H - PAD - 12), "neutrophil.github.io", font=small, fill=FAINT)
    tail = "clinical genomics  ·  ML  ·  systems"
    draw.text((W - PAD - draw.textlength(tail, font=small), H - PAD - 12),
              tail, font=small, fill=FAINT)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT.relative_to(OUT.parent.parent)}  {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
