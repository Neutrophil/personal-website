#!/usr/bin/env python3
"""Static site generator for the personal website.

Stdlib only, on purpose. This repo has no package manager, no lockfile and no
network access at build time; `tomllib` and `xml.etree` are enough. Sources live
in `src/`, generated HTML is written to the repo root and committed, so GitHub
Pages keeps serving plain files with no CI step.

    python build.py            # render the site
    python build.py --check    # render, then run every automated gate
    python build.py --serve    # render, then serve on http://localhost:8910

The point of the build step is that the nav, the <head>, the pre-paint theme
script and the footer exist exactly once. Before it, adding a page meant editing
four files and hoping the relative paths were right at every depth.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
TEMPLATES = SRC / "templates"
PARTIALS = SRC / "partials"
PAGES = SRC / "pages"
POSTS_SRC = SRC / "posts"
POSTS_OUT = ROOT / "posts"

WORDS_PER_MINUTE = 200
# Social-card image. Referenced by absolute URL in a <meta content=...>, which
# the link checker cannot follow — so `--check` verifies it separately.
OG_IMAGE = "assets/og.png"
FRONTMATTER_FENCE = "+++"
TOKEN_RE = re.compile(r"\{\{\s*([A-Za-z0-9_:./-]+)\s*\}\}")
MAX_RESOLVE_PASSES = 6


# --------------------------------------------------------------------------
# Frontmatter
# --------------------------------------------------------------------------

@dataclass
class Doc:
    """A source fragment: TOML frontmatter plus an HTML body."""

    path: Path
    meta: dict
    body: str

    @property
    def slug(self) -> str:
        return self.path.stem


def parse_doc(path: Path) -> Doc:
    """Split a `+++`-fenced TOML header from the HTML body below it."""
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith(FRONTMATTER_FENCE):
        raise BuildError(f"{_rel(path)}: missing '{FRONTMATTER_FENCE}' frontmatter header")
    _, _, rest = raw.partition(FRONTMATTER_FENCE)
    header, fence, body = rest.partition("\n" + FRONTMATTER_FENCE)
    if not fence:
        raise BuildError(f"{_rel(path)}: frontmatter is never closed with '{FRONTMATTER_FENCE}'")
    try:
        meta = tomllib.loads(header)
    except tomllib.TOMLDecodeError as exc:
        raise BuildError(f"{_rel(path)}: bad TOML frontmatter — {exc}") from exc
    return Doc(path=path, meta=meta, body=body.lstrip("\n"))


class BuildError(Exception):
    """A problem in the sources that must stop the build."""


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


# --------------------------------------------------------------------------
# Templating — token substitution and file includes, nothing more
# --------------------------------------------------------------------------

def resolve(text: str, ctx: dict) -> str:
    """Expand `{{ include:path }}` and `{{ key }}` until the text stops changing.

    Unknown tokens are deliberately left in place so `--check` can report them
    rather than silently rendering an empty string into the page.
    """
    for _ in range(MAX_RESOLVE_PASSES):
        def sub(match: re.Match) -> str:
            key = match.group(1)
            if key.startswith("include:"):
                target = PARTIALS / key[len("include:"):]
                if not target.is_file():
                    raise BuildError(f"include not found: {_rel(target)}")
                return target.read_text(encoding="utf-8")
            value = ctx.get(key)
            return match.group(0) if value is None else str(value)

        expanded = TOKEN_RE.sub(sub, text)
        if expanded == text:
            return text
        text = expanded
    raise BuildError("template tokens did not settle — check for a self-referential include")


# --------------------------------------------------------------------------
# Site model
# --------------------------------------------------------------------------

@dataclass
class Post:
    doc: Doc
    title: str
    date: date
    summary: str
    tags: list[str]
    description: str
    minutes: int
    body: str
    featured: bool = False
    prev: "Post | None" = field(default=None, repr=False)
    next: "Post | None" = field(default=None, repr=False)

    @property
    def href(self) -> str:
        return f"posts/{self.doc.slug}.html"

    @property
    def iso(self) -> str:
        return self.date.isoformat()

    @property
    def pretty_date(self) -> str:
        return f"{self.date.day} {self.date:%B %Y}"

    @property
    def short_date(self) -> str:
        return f"{self.date.day} {self.date:%b %Y}"


SLUG_STRIP_RE = re.compile(r"<[^>]+>")
H2_RE = re.compile(r"<h2>(.*?)</h2>", re.S)
# Below this, a contents list is noise rather than navigation.
TOC_MIN_SECTIONS = 5


def slugify(text: str) -> str:
    text = html.unescape(SLUG_STRIP_RE.sub("", text)).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "section"


def add_heading_ids(body: str) -> tuple[str, list[tuple[str, str]]]:
    """Give every h2 a stable id and collect them for the contents list.

    Deep links into a nine-section postmortem are worth more than the four
    lines this costs, and the same pass is what the contents list is built from.
    """
    headings: list[tuple[str, str]] = []
    seen: dict[str, int] = {}

    def sub(match: re.Match) -> str:
        inner = match.group(1)
        title = html.unescape(SLUG_STRIP_RE.sub("", inner)).strip()
        slug = slugify(inner)
        seen[slug] = seen.get(slug, 0) + 1
        if seen[slug] > 1:
            slug = f"{slug}-{seen[slug]}"
        headings.append((slug, title))
        return f'<h2 id="{slug}">{inner}</h2>'

    return H2_RE.sub(sub, body), headings


def toc_html(headings: list[tuple[str, str]]) -> str:
    if len(headings) < TOC_MIN_SECTIONS:
        return ""
    items = "".join(
        f'\n              <li><a href="#{slug}">{esc(title)}</a></li>' for slug, title in headings
    )
    # Deliberately a <ul>: several posts number their own sections, and an <ol>
    # printed "1. 1. A page returns HTTP 200".
    return (
        '\n          <nav class="toc" aria-label="Sections in this post">'
        '\n            <p class="toc__title">On this page</p>'
        f'\n            <ul class="toc__list">{items}\n            </ul>'
        "\n          </nav>"
    )


def reading_minutes(body: str) -> int:
    words = len(re.sub(r"<[^>]+>", " ", body).split())
    return max(1, round(words / WORDS_PER_MINUTE))


def load_posts() -> list[Post]:
    posts: list[Post] = []
    for path in sorted(POSTS_SRC.glob("*.html")):
        if path.name.startswith("_"):
            continue
        doc = parse_doc(path)
        missing = [k for k in ("title", "date", "summary", "tags") if not doc.meta.get(k)]
        if missing:
            raise BuildError(f"{_rel(path)}: frontmatter missing {', '.join(missing)}")
        when = doc.meta["date"]
        if isinstance(when, datetime):
            when = when.date()
        if not isinstance(when, date):
            raise BuildError(f"{_rel(path)}: 'date' must be a plain date, e.g. 2026-08-13")
        posts.append(
            Post(
                doc=doc,
                title=doc.meta["title"],
                date=when,
                summary=doc.meta["summary"].strip(),
                tags=list(doc.meta["tags"]),
                description=doc.meta.get("description", doc.meta["summary"]).strip(),
                minutes=doc.meta.get("minutes") or reading_minutes(doc.body),
                body=doc.body,
                featured=bool(doc.meta.get("featured", False)),
            )
        )
    posts.sort(key=lambda p: (p.date, p.doc.slug), reverse=True)
    for i, post in enumerate(posts):
        post.next = posts[i - 1] if i > 0 else None          # newer
        post.prev = posts[i + 1] if i + 1 < len(posts) else None  # older
    return posts


# --------------------------------------------------------------------------
# HTML fragments assembled in Python (templates stay loop-free)
# --------------------------------------------------------------------------

def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def nav_links_html(site: dict, rel: str, active: str) -> str:
    out = []
    for item in site["nav"]:
        href = item["href"]
        page = href.split("#", 1)[0]
        # Compare the whole href, fragment included. Matching on the page alone
        # marked both "index.html#about" and "index.html#contact" as the current
        # page on the home page; the scrollspy in main.js owns that state now.
        is_active = href == active
        target = href if href.startswith("http") else rel + href
        attrs = ' class="is-active" aria-current="page"' if is_active else ""
        out.append(
            f'        <a href="{esc(target)}"{attrs}>'
            f'<span class="nav__bracket" aria-hidden="true">[</span>'
            f'{esc(item["label"])}'
            f'<span class="nav__bracket" aria-hidden="true">]</span></a>'
        )
    return "\n".join(out)


def tags_html(tags: list[str], cls: str = "tags tags--mini") -> str:
    items = "".join(f"<li>{esc(t)}</li>" for t in tags)
    return f'<ul class="{cls}">{items}</ul>'


def postcard_html(post: Post, rel: str) -> str:
    data_tags = esc("|".join(post.tags))
    return f"""          <li class="postlist__item reveal" data-tags="{data_tags}">
            <a class="postcard" href="{rel}{post.href}">
              <div class="postcard__meta">
                <time datetime="{post.iso}">{post.short_date}</time>
                <span class="dot" aria-hidden="true">·</span>
                <span>{post.minutes} min read</span>
              </div>
              <h2 class="postcard__title">{esc(post.title)}</h2>
              <p class="postcard__summary">{esc(post.summary)}</p>
              {tags_html(post.tags)}
              <span class="postcard__more">Read <span aria-hidden="true">→</span></span>
            </a>
          </li>"""


def tag_filter_html(posts: list[Post], pinned: list[str]) -> str:
    """A chip per tag worth filtering by: shared by two posts, or pinned.

    A chip that matches one post is a link to that post with extra steps, and
    eleven of them buried the four that actually group anything. Pinned tags
    are the site's own subject, shown even while only one post carries them.
    Cards keep every tag either way.
    """
    counts: dict[str, int] = {}
    for post in posts:
        for tag in post.tags:
            counts[tag] = counts.get(tag, 0) + 1
    ordered = sorted(
        ((t, n) for t, n in counts.items() if n >= 2 or t in pinned),
        key=lambda kv: (kv[0] not in pinned, -kv[1], kv[0]),
    )
    chips = [
        '<button type="button" class="chip is-on" data-tag="*" aria-pressed="true">'
        f'all <span class="chip__n">{len(posts)}</span></button>'
    ]
    for tag, n in ordered:
        chips.append(
            f'<button type="button" class="chip" data-tag="{esc(tag)}" aria-pressed="false">'
            f'{esc(tag)} <span class="chip__n">{n}</span></button>'
        )
    return (
        '        <div class="chips" id="tag-filter" role="group" aria-label="Filter posts by tag">\n'
        + "\n".join(f"          {c}" for c in chips)
        + "\n        </div>"
    )


def post_nav_html(post: Post, rel: str) -> str:
    if not (post.prev or post.next):
        return ""
    parts = ['        <nav class="postnav" aria-label="More posts">']
    if post.next:
        parts.append(
            f'          <a class="postnav__link postnav__link--prev" href="{rel}{post.next.href}">'
            f'<span class="postnav__dir"><span aria-hidden="true">←</span> Newer</span>'
            f'<span class="postnav__title">{esc(post.next.title)}</span></a>'
        )
    if post.prev:
        parts.append(
            f'          <a class="postnav__link postnav__link--next" href="{rel}{post.prev.href}">'
            f'<span class="postnav__dir">Older <span aria-hidden="true">→</span></span>'
            f'<span class="postnav__title">{esc(post.prev.title)}</span></a>'
        )
    parts.append("        </nav>")
    return "\n".join(parts)


def latest_posts_html(posts: list[Post], rel: str, limit: int = 3) -> str:
    # Featured posts lead, newest first within each group. Only this list is
    # reordered: prev/next and the feed stay in date order.
    chosen = sorted(posts, key=lambda p: not p.featured)[:limit]
    rows = []
    for post in chosen:
        rows.append(
            f'          <a class="pindex__row" href="{rel}{post.href}">\n'
            f'            <span class="pindex__date"><time datetime="{post.iso}">{post.short_date}</time></span>\n'
            f'            <span class="pindex__title">{esc(post.title)}</span>\n'
            f'            <span class="pindex__tag">{esc(post.tags[0])}</span>\n'
            f'          </a>'
        )
    return "\n".join(rows)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def base_context(site: dict, rel: str) -> dict:
    return {
        "rel": rel,
        "lang": site["lang"],
        "site_title": site["title"],
        "tagline": site["tagline"],
        "author": site["author"],
        "email": site["email"],
        "location": site["location"],
        "linkedin": site["links"]["linkedin"],
        "github": site["links"]["github"],
        "cv": site["links"]["cv"],
        "og_image": f"{site['url']}/{OG_IMAGE}",
        "year": str(date.today().year),
    }


def render_page(site: dict, template: str, ctx: dict, body: str) -> str:
    rel = ctx["rel"]
    nav = resolve(
        (PARTIALS / "nav.html").read_text(encoding="utf-8"),
        {**ctx, "nav_links": nav_links_html(site, rel, ctx["active"])},
    )
    footer = resolve((PARTIALS / "footer.html").read_text(encoding="utf-8"), ctx)
    return resolve(template, {**ctx, "body": resolve(body, ctx), "nav": nav, "footer": footer})


def build(check: bool = False) -> list[Path]:
    site = tomllib.loads((SRC / "site.toml").read_text(encoding="utf-8"))
    template = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    posts = load_posts()
    written: list[Path] = []

    # --- standalone pages ---------------------------------------------------
    for path in sorted(PAGES.rglob("*.html")):
        doc = parse_doc(path)
        rel_out = path.relative_to(PAGES)
        out = ROOT / rel_out
        out.parent.mkdir(parents=True, exist_ok=True)
        rel = "../" * (len(rel_out.parts) - 1)
        # The 404 page is served at whatever URL was missed, so a relative path
        # would resolve against /posts/ or wherever the visitor was. Root it.
        if doc.meta.get("root_relative"):
            rel = urlparse(site["url"]).path.rstrip("/") + "/"
        url_path = rel_out.as_posix().removesuffix("index.html")
        ctx = base_context(site, rel=rel)
        ctx.update(
            title=doc.meta.get("page_title") or f"{doc.meta['title']} — {site['author']}",
            description=doc.meta.get("description", site["description"]),
            og_type=doc.meta.get("og_type", "website"),
            og_title=doc.meta.get("og_title", doc.meta["title"]),
            og_description=doc.meta.get("og_description", doc.meta.get("description", site["description"])),
            og_url=f"{site['url']}/{url_path}",
            body_class=doc.meta.get("body_class", f"page-{doc.slug}"),
            active=doc.meta.get("active", f"{doc.slug}.html"),
            latest_posts=latest_posts_html(posts, rel=rel),
            post_count=str(len(posts)),
        )
        if out in written:
            raise BuildError(f"{_rel(path)}: writes {_rel(out)}, which another source already wrote")
        out.write_text(render_page(site, template, ctx, doc.body), encoding="utf-8")
        written.append(out)

    # --- blog index ---------------------------------------------------------
    blog_src = parse_doc(SRC / "blog.html")
    ctx = base_context(site, rel="")
    ctx.update(
        title=f"{blog_src.meta['title']} — {site['author']}",
        description=blog_src.meta.get("description", site["description"]),
        og_type="website",
        og_title=blog_src.meta["title"],
        og_description=blog_src.meta.get("description", site["description"]),
        og_url=f"{site['url']}/blog.html",
        body_class="page-blog",
        active="blog.html",
        post_list="\n".join(postcard_html(p, rel="") for p in posts),
        tag_filter=tag_filter_html(posts, site.get("blog", {}).get("pinned_tags", [])),
        post_count=str(len(posts)),
    )
    blog_out = ROOT / "blog.html"
    blog_out.write_text(render_page(site, template, ctx, blog_src.body), encoding="utf-8")
    written.append(blog_out)

    # --- posts --------------------------------------------------------------
    POSTS_OUT.mkdir(exist_ok=True)
    for post in posts:
        ctx = base_context(site, rel="../")
        ctx.update(
            title=f"{post.title} — {site['author']}",
            description=post.description,
            og_type="article",
            og_title=post.title,
            og_description=post.description,
            og_url=f"{site['url']}/{post.href}",
            body_class="page-post",
            active="blog.html",
            post_title=esc(post.title),
            post_date=post.iso,
            post_date_pretty=post.pretty_date,
            post_minutes=str(post.minutes),
            post_tags=tags_html(post.tags),
            post_nav=post_nav_html(post, rel="../"),
        )
        wrapper = (TEMPLATES / "post.html").read_text(encoding="utf-8")
        numbered, headings = add_heading_ids(post.body)
        ctx.update(post_summary=esc(post.summary), post_toc=toc_html(headings))
        body = resolve(wrapper, {**ctx, "post_body": numbered})
        out = POSTS_OUT / f"{post.doc.slug}.html"
        out.write_text(render_page(site, template, ctx, body), encoding="utf-8")
        written.append(out)

    # --- feed ---------------------------------------------------------------
    feed = ROOT / "feed.xml"
    feed.write_text(build_feed(site, posts), encoding="utf-8")
    written.append(feed)

    print(f"built {len(written)} files · {len(posts)} posts")

    if check:
        run_checks(site, written, posts)
    return written


def build_feed(site: dict, posts: list[Post]) -> str:
    """RSS 2.0. Hand-rolled rather than ElementTree so the output stays readable
    in a diff; `--check` parses it back to prove it is well-formed.

    lastBuildDate is derived from the newest post rather than the clock, so a
    rebuild that changed nothing produces no diff. A wall-clock value would put
    a spurious feed change in every future commit."""
    newest = max((p.date for p in posts), default=date.today())
    now = datetime(newest.year, newest.month, newest.day, 9, 0, tzinfo=timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S +0000"
    )
    items = []
    for post in posts:
        link = f"{site['url']}/{post.href}"
        pub = datetime(post.date.year, post.date.month, post.date.day, 9, 0, tzinfo=timezone.utc)
        categories = "".join(f"\n      <category>{esc(t)}</category>" for t in post.tags)
        items.append(
            f"""    <item>
      <title>{esc(post.title)}</title>
      <link>{esc(link)}</link>
      <guid isPermaLink="true">{esc(link)}</guid>
      <pubDate>{pub.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>
      <description>{esc(post.summary)}</description>{categories}
    </item>"""
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{esc(site['author'])} — writing</title>
    <link>{esc(site['url'])}/blog.html</link>
    <atom:link href="{esc(site['url'])}/feed.xml" rel="self" type="application/rss+xml" />
    <description>Notes on AI for life science, clinical genomics, and systems built on evenings.</description>
    <language>{esc(site['lang'])}</language>
    <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>
"""


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []
        self.ids: list[str] = []
        self.classes: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.refs.append(value)
            elif name == "id" and value:
                self.ids.append(value)
            elif name == "class" and value:
                self.classes.update(value.split())


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _luminance(rgb: tuple[float, float, float]) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    l1, l2 = _luminance(_hex_to_rgb(fg)), _luminance(_hex_to_rgb(bg))
    lo, hi = sorted((l1, l2))
    return (hi + 0.05) / (lo + 0.05)


# (foreground token, background token, minimum ratio, what it is used for)
CONTRAST_RULES = [
    ("text", "bg", 4.5, "body text"),
    ("text", "bg-elev", 4.5, "text on cards"),
    ("text-soft", "bg", 4.5, "secondary prose"),
    ("text-soft", "bg-elev", 4.5, "secondary prose on cards"),
    ("text-faint", "bg", 4.5, "metadata"),
    ("text-faint", "bg-elev", 4.5, "metadata on cards"),
    ("text-soft", "bg-sunken", 4.5, "secondary prose in banded sections"),
    ("text-faint", "bg-sunken", 4.5, "metadata in banded sections"),
    ("accent", "bg", 4.5, "links"),
    ("accent", "bg-elev", 4.5, "links on cards"),
    ("accent-2", "bg", 4.5, "secondary accent"),
    ("accent-2", "bg-elev", 4.5, "secondary accent on cards"),
    ("on-accent", "accent", 4.5, "text on the primary button and the active chip"),
    ("text", "bg-sunken", 4.5, "headings in banded sections"),
    ("accent", "bg-sunken", 4.5, "links in banded sections"),
    ("accent-2", "bg-sunken", 4.5, "secondary accent in banded sections"),
    ("text-soft", "code-bg", 4.5, "code block text"),
    ("text-faint", "code-bg", 4.5, "code block filename"),
]

# Smallest a diagram label may render at, in CSS pixels, on the narrowest
# supported viewport. Below this the figure is decoration, not information.
MIN_DIAGRAM_LABEL_PX = 10.0
MIN_CONTROL_PX = 24  # WCAG 2.2 pointer-target minimum

# What must never be published, however it got into a page. The workspace guard
# cannot see these here: `.privacy-guard-allow` turns its contact rule off so the
# owner's address can appear, and the phone pattern lives inside that rule.
PHONE_RES = (
    re.compile(r"(?<![\w])\+(?:65[ -]?\d{4}[ -]?\d{4}|86[ -]?1\d{2}[ -]?\d{4}[ -]?\d{4}|\d{9,15})(?![\w])"),
    re.compile(r"(?<![\w.+/-])[689]\d{3}[ -]?\d{4}(?![\w.-])"),     # bare Singapore number
    re.compile(r"(?<![\w.+/-])1[3-9]\d[ -]?\d{4}[ -]?\d{4}(?![\w.-])"),  # bare mainland mobile
)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Classes that only exist at runtime, added by the inline head script or main.js.
RUNTIME_CLASS_RE = re.compile(r"^(?:js|no-js|reveal-on|is-[a-z-]+|page-[a-z0-9-]+)$")


def unused_css_classes(css: str, used: set[str]) -> list[str]:
    """Class selectors in the stylesheet that nothing renders.

    Comments, url()s and strings go first: `jetbrains-mono-regular.woff2` is not
    a class called `woff2`.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"url\([^)]*\)|\"[^\"]*\"|'[^']*'", "", css)
    declared = set(re.findall(r"\.([a-zA-Z_][\w-]*)", css))
    return sorted(c for c in declared if c not in used and not RUNTIME_CLASS_RE.match(c))


def diagram_label_sizes(css: str, svg_dir: Path) -> list[tuple[str, float]]:
    """Work out how big each diagram's smallest label actually renders.

    The figures are drawn in a 900-unit coordinate space and scaled to fit, so
    a label's declared size says nothing about what a reader sees. The scale is
    fixed by the `min-width` on `.diagram svg`: that is the width the figure
    takes on a phone, and the worst case. This gate is the one that would have
    caught labels arriving at 7px.
    """
    min_width = re.search(r"\.diagram svg \{[^}]*min-width:\s*([0-9.]+)px", css)
    if not min_width:
        return [("css: .diagram svg has no min-width to scale from", 0.0)]
    render_px = float(min_width.group(1))
    declared = {
        name: float(size)
        for name, size in re.findall(r"\.(d-label[a-z-]*)\s*\{[^}]*font-size:\s*([0-9.]+)px", css)
    }
    if not declared:
        return [("css: no .d-label font sizes found", 0.0)]

    out: list[tuple[str, float]] = []
    for path in sorted(svg_dir.glob("*.svg")):
        text = path.read_text(encoding="utf-8")
        box = re.search(r'viewBox="0 0 ([0-9.]+)', text)
        if not box:
            continue
        used = [declared[cls] for cls in declared if f'"{cls}' in text or f" {cls}" in text]
        if not used:
            continue
        scale = render_px / float(box.group(1))
        out.append((path.name, round(min(used) * scale, 1)))
    return out


def strip_at_rules(css: str) -> str:
    """Drop every `@media`/`@supports` block, braces balanced.

    The theme palette lives in the unconditional `:root` and `[data-theme]`
    blocks. A `:root` inside `@media print` is a different palette entirely, and
    folding it into the real one would have the contrast gate checking colours
    no visitor ever sees.
    """
    out, i = [], 0
    while i < len(css):
        at = css.find("@", i)
        if at == -1:
            out.append(css[i:])
            break
        head_end = css.find("{", at)
        if head_end == -1 or not css[at:head_end].lstrip("@").split()[0] in ("media", "supports", "container"):
            out.append(css[i:at + 1])
            i = at + 1
            continue
        out.append(css[i:at])
        depth, j = 0, head_end
        while j < len(css):
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        i = j + 1
    return "".join(out)


def theme_tokens(css: str) -> dict[str, dict[str, str]]:
    """Pull the flat hex tokens out of the `:root` and `[data-theme=...]` blocks."""
    themes: dict[str, dict[str, str]] = {}
    for selector, block in re.findall(r"(:root|\[data-theme=\"[a-z]+\"\])\s*\{([^}]*)\}", strip_at_rules(css)):
        name = "dark" if selector == ":root" else selector.split('"')[1]
        found = dict(re.findall(r"--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;", block))
        if found:
            themes.setdefault(name, {}).update(found)
    return themes


def run_checks(site: dict, written: list[Path], posts: list[Post]) -> None:
    problems: list[str] = []

    # 1. every token was substituted
    for path in written:
        if path.suffix != ".html":
            continue
        for match in TOKEN_RE.finditer(path.read_text(encoding="utf-8")):
            problems.append(f"{_rel(path)}: unresolved template token {match.group(0)}")

    # 2. every local link resolves to a file that exists, and every #fragment
    #    to an id on its target page. Moving a section used to break inbound
    #    links silently: the file was still there, so the old gate was happy.
    pages: dict[Path, LinkCollector] = {}
    for path in written:
        if path.suffix == ".html":
            pages[path.resolve()] = collector = LinkCollector()
            collector.feed(path.read_text(encoding="utf-8"))
            for dup, n in Counter(collector.ids).items():
                if n > 1:
                    problems.append(f"{_rel(path)}: id {dup!r} appears {n} times")
    site_path = urlparse(site["url"]).path.rstrip("/")
    for path, collector in pages.items():
        for ref in collector.refs:
            if ref.startswith(("http://", "https://", "mailto:", "data:", "//")):
                continue
            file_part, _, frag = ref.partition("#")
            file_part = file_part.split("?", 1)[0]
            if file_part.startswith("/"):
                file_part = file_part.removeprefix(site_path).lstrip("/") or "index.html"
                target = (ROOT / file_part).resolve()
            else:
                target = (path.parent / file_part).resolve() if file_part else path
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                problems.append(f"{_rel(path)}: dead link → {ref}")
            elif frag and target in pages and frag not in pages[target].ids:
                problems.append(f"{_rel(path)}: link {ref} has no id {frag!r} to land on")

    # 3. the feed is well-formed and every link is absolute
    import xml.etree.ElementTree as ET

    try:
        tree = ET.fromstring((ROOT / "feed.xml").read_text(encoding="utf-8"))
        links = [e.text or "" for e in tree.iter("link")]
        if not links:
            problems.append("feed.xml: no <link> elements")
        for link in links:
            if not link.startswith("http"):
                problems.append(f"feed.xml: relative <link> {link!r}")
        if len(list(tree.iter("item"))) != len(posts):
            problems.append("feed.xml: item count does not match the post count")
    except ET.ParseError as exc:
        problems.append(f"feed.xml: not well-formed — {exc}")

    # 4. colour contrast, computed rather than assumed, in both themes
    themes = theme_tokens((ROOT / "css" / "styles.css").read_text(encoding="utf-8"))
    for theme in ("dark", "light"):
        tokens = themes.get(theme)
        if not tokens:
            problems.append(f"css: no colour tokens found for the {theme} theme")
            continue
        # the light theme only overrides what differs; fall back to the dark base
        merged = {**themes.get("dark", {}), **tokens}
        for fg, bg, minimum, what in CONTRAST_RULES:
            if fg not in merged or bg not in merged:
                problems.append(f"css/{theme}: missing token --{fg} or --{bg}")
                continue
            ratio = contrast_ratio(merged[fg], merged[bg])
            if ratio < minimum:
                problems.append(
                    f"css/{theme}: --{fg} on --{bg} is {ratio:.2f}:1, "
                    f"below {minimum}:1 ({what})"
                )

    # 5. the social card exists — every page points at it by absolute URL, so a
    #    missing file shows up only as a bare link preview, never as a 404 here
    if not (ROOT / OG_IMAGE).is_file():
        problems.append(f"{OG_IMAGE} is referenced by every page but does not exist "
                        f"— run tools/make_og.py")

    # 6. diagrams stay legible at the size they are actually drawn
    for name, rendered in diagram_label_sizes(
        (ROOT / "css" / "styles.css").read_text(encoding="utf-8"), PARTIALS / "diagrams"
    ):
        if rendered < MIN_DIAGRAM_LABEL_PX:
            problems.append(
                f"{name}: smallest label renders at {rendered}px, below {MIN_DIAGRAM_LABEL_PX}px"
            )

    # 7. nothing that matters may depend on a script that might not load.
    #    The stylesheet hides .reveal behind a class; main.js must be what adds it.
    css_text = (ROOT / "css" / "styles.css").read_text(encoding="utf-8")
    js_text = (ROOT / "js" / "main.js").read_text(encoding="utf-8")
    gate = re.search(r"\.([a-z-]+)\s+\.reveal\s*\{[^}]*opacity:\s*0", css_text)
    if not gate:
        problems.append("css: .reveal is no longer gated on a class — check it cannot blank the page")
    elif f"classList.add('{gate.group(1)}')" not in js_text:
        problems.append(
            f"js/main.js does not add '{gate.group(1)}', so a failed script would leave "
            f".reveal content hidden forever"
        )

    # 8. controls stay large enough to hit
    for pattern, what in (
        (r"--control:\s*([0-9.]+)px", "icon buttons"),
        (r"\.chip \{[^}]*min-height:\s*([0-9.]+)px", "filter chips"),
        (r"\.codeblock__copy \{[^}]*min-height:\s*([0-9.]+)px", "the copy button"),
    ):
        found = re.search(pattern, css_text)
        if not found:
            problems.append(f"css: no declared size for {what}")
        elif float(found.group(1)) < MIN_CONTROL_PX:
            problems.append(f"css: {what} are {found.group(1)}px, below {MIN_CONTROL_PX}px")

    # 9. one current page per page, and a theme colour on every one of them
    for path in written:
        if path.suffix != ".html":
            continue
        text = path.read_text(encoding="utf-8")
        marked = text.count('aria-current="page"')
        if marked > 1:
            problems.append(f"{_rel(path)}: {marked} links marked as the current page")
        if 'name="theme-color"' not in text:
            problems.append(f"{_rel(path)}: no theme-color meta tag")

    # 10. posts carry everything the index and the feed need
    for post in posts:
        if len(post.summary) < 40:
            problems.append(f"{_rel(post.doc.path)}: summary is too short to be useful")
        if not post.tags:
            problems.append(f"{_rel(post.doc.path)}: no tags")

    # 11. an element shipped `hidden` stays hidden: a component rule that sets
    # `display` outranks the browser's own [hidden] rule, so it needs its own
    for path in written:
        if path.suffix != ".html":
            continue
        tags = re.findall(r"<[a-z][^>]*>", path.read_text(encoding="utf-8"))
        shipped = [t for t in tags if re.search(r"(?<![\w-])hidden(?=[\s>/])", t)]
        for cls in {m.group(1) for t in shipped if (m := re.search(r'class="([\w-]+)', t))}:
            sets_display = re.search(rf"\.{re.escape(cls)} \{{[^}}]*display:", css_text)
            if sets_display and f".{cls}[hidden]" not in css_text:
                problems.append(f"{_rel(path)}: .{cls} ships hidden but its display rule overrides [hidden]")

    # 12. no class selector outlives the markup it styled
    used = set().union(*(c.classes for c in pages.values()))
    used |= set(re.findall(r"classList\.(?:add|remove|toggle|contains)\('([\w-]+)'", js_text))
    used |= {c for v in re.findall(r"className\s*=\s*'([^']+)'", js_text) for c in v.split()}
    # The post template is the catalogue of components a post may use, so what it
    # shows is in use even before a published post needs it.
    template = LinkCollector()
    template.feed((POSTS_SRC / "_TEMPLATE.html").read_text(encoding="utf-8"))
    used |= template.classes
    for cls in unused_css_classes(css_text, used):
        problems.append(f"css: .{cls} matches nothing on any page — delete it or use it")

    # 13. nothing private reaches a page: no phone number in any shape, and no
    #     address but the owner's own
    for path in pages:
        text = re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8"))
        for pattern in PHONE_RES:
            for m in pattern.finditer(text):
                problems.append(f"{_rel(path)}: looks like a phone number ({len(m.group())} chars) — never publish one")
        for m in EMAIL_RE.finditer(path.read_text(encoding="utf-8")):
            if m.group().lower() != site["email"].lower():
                problems.append(f"{_rel(path)}: email address other than the site's own")

    if problems:
        print(f"\n✗ {len(problems)} problem(s):", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        raise SystemExit(1)
    print("✓ checks passed — tokens, links, fragments, feed, contrast, diagrams, no-JS, controls, "
          "frontmatter, unused CSS, private data")


# --------------------------------------------------------------------------

def _not_found_handler():
    import http.server

    class Handler(http.server.SimpleHTTPRequestHandler):
        """Answer a miss with 404.html, the way GitHub Pages does."""

        def send_error(self, code, message=None, explain=None):
            page = ROOT / "404.html"
            if code != 404 or not page.is_file():
                return super().send_error(code, message, explain)
            body = page.read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def log_message(self, *args):  # noqa: D102 - keep the terminal quiet
            pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="run the automated gates after building")
    parser.add_argument("--serve", action="store_true", help="serve the built site on localhost:8910")
    args = parser.parse_args()

    try:
        build(check=args.check)
    except BuildError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if args.serve:
        import functools
        import http.server

        handler = functools.partial(_not_found_handler(), directory=str(ROOT))
        # Loopback only. This serves the repo root, which also holds .git, the
        # raw CV sources and the gitignored working notes — none of which should
        # be reachable from the LAN just to preview a page.
        print("serving http://localhost:8910 — ctrl-c to stop")
        http.server.ThreadingHTTPServer(("127.0.0.1", 8910), handler).serve_forever()


if __name__ == "__main__":
    main()
