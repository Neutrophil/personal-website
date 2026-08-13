# CLAUDE.md — personal_website

Static personal site on GitHub Pages. Workspace-wide rules live in
[../CLAUDE.md](../CLAUDE.md) — this file covers only what is specific here.

## What this is

A personal site with no runtime dependencies: the browser gets plain HTML + CSS + vanilla JS,
no framework, no bundler, no CDN, no trackers. `.nojekyll` makes GitHub Pages serve the files
as-is.

It **is** generated, by `build.py` — a stdlib-only Python script with no `requirements.txt` and
nothing to install. Sources live in `src/`; the generated HTML is written to the repo root and
committed, so Pages needs no CI step and a clone with no Python still serves correctly.

> The build step was added on 2026-08-13, replacing hand-maintained pages. Before it, the nav,
> the `<head>`, the pre-paint theme script and the footer were copy-pasted into every HTML
> file, and the blog index was a hand-written list — adding a page meant four edits plus
> getting relative paths right at two directory depths. `README.md` is the authoring guide;
> read it before editing content.

This is not a Python *app* and does not follow the workspace app template: no `core/`, no
`storage/`, no conda dependency, no pytest suite. Its verification lives in `build.py --check`.

## Commands

```
cd /home/junjie/claude/personal_website
~/miniconda3/envs/investing/bin/python build.py --check    # build + every gate; run before committing
~/miniconda3/envs/investing/bin/python build.py --serve    # build, then http://localhost:8910
```

Any Python ≥ 3.11 works (`tomllib` is the only version-sensitive import); the conda env is
just what is on this machine.

## Architecture

```
build.py                  generator: TOML frontmatter, {{token}} substitution, includes,
                          blog index, RSS, prev/next, and the --check gates
src/site.toml             site metadata + primary nav
src/templates/            base.html (page skeleton) · post.html (article wrapper)
src/partials/             nav.html · footer.html · signal.svg · diagrams/*.svg
src/pages/*.html          index · projects · 404 — body fragments + frontmatter
src/blog.html             writing index; the post list is generated into it
src/posts/*.html          one fragment per post (+ _TEMPLATE.html, skipped by the build)
css/styles.css            design system — dark default, light counterpart
js/main.js                theme toggle, nav, reveal, tag filter, copy buttons, progress bar
assets/                   favicon + CV (PDF)
→ index.html projects.html blog.html 404.html feed.xml posts/*.html    generated, committed
```

**Never hand-edit a generated file at the repo root.** Edit the matching source in `src/` and
rebuild — the next build overwrites root-level changes without warning.

## Conventions

- **Templating is deliberately primitive**: `{{ key }}` substitution and
  `{{ include:path }}`, no expressions and no loops. Anything list-shaped (post cards, tag
  chips, nav links) is assembled in Python, in `build.py`. Keep it that way; the value of this
  generator is that it fits in one readable file.
- **`--check` is the test suite.** It fails on unresolved tokens, dead local links, incomplete
  frontmatter, a malformed feed, and **any text/background pair below WCAG AA in either
  theme** — contrast is computed from the CSS tokens, not eyeballed. Add a gate here rather
  than relying on a manual look.
- **JS is enhancement only.** The inline head script swaps `no-js` for `js` on `<html>`, and
  `.reveal` is hidden only under `.js`. If `main.js` fails to load, the page must still be
  complete — do not add content that only appears after script runs.
- **Diagrams** go in `src/partials/diagrams/` as inline SVG using the shared `d-*` classes, so
  they follow the theme. Wrap them in `.diagram > .diagram__scroll`: they carry a `min-width`
  so a narrow screen scrolls the figure rather than shrinking 11px labels into illegibility.
- No automated screenshots — Playwright's browser cannot be installed on this OS. Visual
  checks are manual in a real browser, in both themes.

## Privacy — read this before adding anything

**This is the one repo in the workspace whose content is published deliberately.** Its whole
purpose is to put the owner's name, biography, contact address and CV under their own domain,
so `.privacy-guard-allow` disables the `denylist-name` and `contact` rules here and exempts
`assets/**` from scanning entirely.

That exemption is the reason to be careful, not a reason to relax:

- **Anything under `assets/` is world-readable and is not scanned.** Check every file added
  there — especially a new CV revision — for a phone number, a home address, or anything else
  that should not be public.
- **Every other privacy rule still applies.** No account numbers, no card numbers, no real
  financial figures, no third-party names. A person who is not the owner has not consented to
  being published here.
- The site **describes** the other projects (`projects.html` and several posts) because the
  owner asked it to. That is architecture, engineering metrics and lessons only. It carries no
  repo links — those repositories are private and stay private — no screenshots of real
  dashboards, no holdings, no tickers, no amounts, and no bank or broker names.
- Writing a post about a bug is fine. Pasting the data that revealed it is not. When a post
  needs a number, use a measurement (timing, coverage, test count) or an explicitly synthetic
  one.
- Run `tools/privacy-guard scan .` before committing; note that a plausible card number or
  local account format written as an *example* in prose will correctly be blocked, so describe
  formats rather than instantiating them.

## Known limitations

- Root-level generated files are committed, so a diff after any content change is larger than
  the edit that caused it. That is the price of no CI.
- No syntax highlighting in code blocks; they are styled `<pre><code>` and escaped by hand.
- Posts are HTML fragments, not Markdown. Deliberate — the diagrams and callouts are inline
  HTML anyway, and a Markdown parser would be the largest thing in `build.py`.
- The site's repo visibility governs whether Pages can serve it; confirm before assuming a
  push goes live.
