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
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
TEMPLATES = SRC / "templates"
PARTIALS = SRC / "partials"
PAGES = SRC / "pages"
POSTS_SRC = SRC / "posts"
POSTS_OUT = ROOT / "posts"

WORDS_PER_MINUTE = 200
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
        is_active = page == active
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


def tag_filter_html(posts: list[Post]) -> str:
    counts: dict[str, int] = {}
    for post in posts:
        for tag in post.tags:
            counts[tag] = counts.get(tag, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
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
    rows = []
    for post in posts[:limit]:
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
    for path in sorted(PAGES.glob("*.html")):
        doc = parse_doc(path)
        out = ROOT / f"{doc.slug}.html"
        ctx = base_context(site, rel="")
        ctx.update(
            title=doc.meta.get("page_title") or f"{doc.meta['title']} — {site['author']}",
            description=doc.meta.get("description", site["description"]),
            og_type=doc.meta.get("og_type", "website"),
            og_title=doc.meta.get("og_title", doc.meta["title"]),
            og_description=doc.meta.get("og_description", doc.meta.get("description", site["description"])),
            og_url=f"{site['url']}/" if doc.slug == "index" else f"{site['url']}/{doc.slug}.html",
            body_class=doc.meta.get("body_class", f"page-{doc.slug}"),
            active=doc.meta.get("active", f"{doc.slug}.html"),
            latest_posts=latest_posts_html(posts, rel=""),
            post_count=str(len(posts)),
        )
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
        tag_filter=tag_filter_html(posts),
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
        body = resolve(wrapper, {**ctx, "post_body": post.body})
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
    in a diff; `--check` parses it back to prove it is well-formed."""
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
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
    <description>Notes on genomics, machine learning, and systems built on evenings.</description>
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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.refs.append(value)


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
]


def theme_tokens(css: str) -> dict[str, dict[str, str]]:
    """Pull the flat hex tokens out of the `:root` and `[data-theme=...]` blocks."""
    themes: dict[str, dict[str, str]] = {}
    for selector, block in re.findall(r"(:root|\[data-theme=\"[a-z]+\"\])\s*\{([^}]*)\}", css):
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

    # 2. every local link resolves to a file that exists
    for path in written:
        if path.suffix != ".html":
            continue
        collector = LinkCollector()
        collector.feed(path.read_text(encoding="utf-8"))
        for ref in collector.refs:
            if ref.startswith(("http://", "https://", "mailto:", "#", "data:", "//")):
                continue
            target = (path.parent / ref.split("#", 1)[0].split("?", 1)[0]).resolve()
            if not target.exists():
                problems.append(f"{_rel(path)}: dead link → {ref}")

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

    # 5. posts carry everything the index and the feed need
    for post in posts:
        if len(post.summary) < 40:
            problems.append(f"{_rel(post.doc.path)}: summary is too short to be useful")
        if not post.tags:
            problems.append(f"{_rel(post.doc.path)}: no tags")

    if problems:
        print(f"\n✗ {len(problems)} problem(s):", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        raise SystemExit(1)
    print("✓ checks passed — tokens, links, feed, contrast, frontmatter")


# --------------------------------------------------------------------------

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

        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
        print("serving http://localhost:8910 — ctrl-c to stop")
        http.server.ThreadingHTTPServer(("", 8910), handler).serve_forever()


if __name__ == "__main__":
    main()
