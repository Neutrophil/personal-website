# CLAUDE.md — personal_website

Static personal site on GitHub Pages. Workspace-wide rules live in
[../CLAUDE.md](../CLAUDE.md) — this file covers only what is specific here.

## What this is

A dependency-free personal site: plain HTML + CSS + vanilla JS. **No build step, no
framework, no trackers, no CDNs.** `.nojekyll` makes GitHub Pages serve the files as-is.
`README.md` is the authoring guide (how to add a blog post, how to preview) — read it before
editing content; this file is about the constraints.

This is **not** a Python app and does not follow the workspace app template. There is no
`requirements.txt`, no test suite and no conda dependency.

## Commands

No build. Preview with any static server, e.g.

```
cd /home/junjie/claude/personal_website
~/miniconda3/envs/investing/bin/python -m http.server 8910
```

## Architecture

```
index.html        the single-page main site
blog.html         blog index (lists posts)
posts/            one HTML file per post + _TEMPLATE.html
css/styles.css    design system (light/dark themes, responsive)
js/main.js        theme toggle, mobile nav, scrollspy, reveal-on-scroll
assets/           favicon + downloadable CV (PDF)
```

Adding a post is three edits, all by hand: copy `posts/_TEMPLATE.html`, fill it in, and add a
card at the **top** of the list in `blog.html`. Keep it that way — the value of this repo is
that it has no toolchain to rot.

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
- Nothing from the financial projects belongs in this repo, in any form.

## Known limitations

- No tests and no link checking — a broken relative link only shows up in the browser.
- Blog posts are hand-written HTML, so a malformed post breaks silently at render time rather
  than failing a build.
- The site's repo visibility governs whether Pages can serve it; confirm before assuming a
  push goes live.
