# Personal Website — Progress / Restart Guide

**Last updated:** 2026-06-24
**Owner:** Junjie Chen (chen_junjie@outlook.com · LinkedIn `in/junjie-chen-nus` · GitHub `@Neutrophil`)
**Location:** `/home/junjie/claude/personal_website/`
**Plan file:** `/home/junjie/.claude/plans/build-a-personal-website-cheerful-pony.md`

---

## 1. What this is

A personal/professional website to support a job search toward **AI for Life Science**. It
showcases the bridge between Junjie's wet-lab background (PhD Microbiology & Immunology, NUS) and
his current computational work (**Research Scientist II at Lucence Diagnostics** — cfDNA/gDNA/
FFPE-DNA WGS workflows, ML for cancer differentiation/classification, multi-omics integration).

**Strategic narrative:** trained molecular biologist & immunologist → clinical-genomics + ML
practitioner → moving toward AI for Life Science. Wet-lab and computational work get *balanced*
billing (a confirmed design decision).

## 2. Stack & key decisions

- **Pure static site**: HTML + CSS + vanilla JS. **No Node/npm, no framework, no build step, no
  CDNs, no trackers.** (Node is not available in this environment; git is.)
- **Visual style:** "modern scientific minimal" — clean whitespace, single teal accent
  (`#0d9488` light / `#2dd4bf` dark), **light default with a persisted dark-mode toggle**.
- **Deploy target:** GitHub Pages **user site** at `https://neutrophil.github.io/` (repo must be
  named exactly `neutrophil.github.io`). Not yet pushed (outward-facing; do on request).
- **Extras included:** downloadable CV, Projects section, Publications list, **Blog**.
  Declined: contact form.

## 3. Environment & commands

No dependencies to install. Preview with any static server; use the project's conda Python:

```bash
cd /home/junjie/claude/personal_website
~/miniconda3/envs/investing/bin/python -m http.server 8000
# open http://localhost:8000/   (blog at /blog.html)
pkill -f "http.server 8000"     # stop it
```

There is **no test suite** (static site). "Verification" = the curl/HTTP checks below.

### Verification used (all passed 2026-06-24)
```bash
# every asset returns 200
for p in / css/styles.css js/main.js assets/favicon.svg assets/cv/CHEN_Junjie_CV.pdf \
         blog.html posts/2026-06-24-bridging-biology-and-ai.html posts/_TEMPLATE.html; do
  curl -s -o /dev/null -w "%{http_code}  $p\n" "http://localhost:8000/$p"
done
```
Also manually confirm: dark toggle persists across reload, mobile nav (hamburger) works at
<720px, Download CV opens the PDF, scrollspy highlights active nav link, all external/DOI links
resolve, no JS console errors.

> **Note:** Playwright (Python pkg) is present but its **browser binary cannot be installed**
> on this OS (`ubuntu26.04-x64` is unsupported) — so no automated screenshots here. Verify
> visually in a real browser.

## 4. File / architecture map

```
personal_website/
  index.html              # single-page main site (all sections)
  blog.html               # blog index — lists posts as cards
  posts/
    2026-06-24-bridging-biology-and-ai.html   # inaugural post (DRAFT in Junjie's voice)
    _TEMPLATE.html         # copy this to start a new post
  css/styles.css           # ALL styling: design tokens, light/dark, responsive, blog, prose
  js/main.js               # theme toggle, mobile nav, scrollspy, reveal-on-scroll (no deps)
  assets/
    cv/CHEN_Junjie_CV.pdf  # copy of CV/CV_CHEN Junjie_for Lucence 202507.pdf
    favicon.svg            # "JC" monogram
  .nojekyll                # serve files as-is on GitHub Pages (skip Jekyll)
  README.md                # what it is + preview + deploy + how-to-publish-a-post
  CV/                      # original source CVs (pdf + docx), unchanged
  2026-06-24_personal_website_progress.md   # this file
```

**index.html sections (single page):** sticky nav → hero → About (bridge narrative + "at a
glance" facts) → Expertise (3 balanced cards: Computational & ML / Genomics & NGS / Molecular &
Cell Biology) → Experience (vertical timeline: Lucence → NUS Fellow → NUS RA → AbbVie) →
Projects (4 cards) → Publications (8 entries w/ DOIs, name bolded) → Contact → footer.

**CSS conventions:** CSS custom properties in `:root` (light) with `[data-theme="dark"]`
overrides; max content width 980px (720px for `.container--narrow` blog/post body); single mobile
breakpoint at 720px; `.reveal` class fades content in via IntersectionObserver (guarded by
`prefers-reduced-motion`). Accent/spacing/radius are all variables at top of `styles.css`.

**JS:** one IIFE, no libraries. Theme is set pre-paint by an inline script in each `<head>` (reads
`localStorage.theme`, else `prefers-color-scheme`) to avoid a flash; `main.js` handles the toggle,
hamburger, year stamp, reveal, and scrollspy.

## 5. Conventions & gotchas

- **Cross-page links / relative paths.** `index.html` nav uses same-page anchors (`#about`);
  `blog.html` uses `index.html#about`; files in `posts/` use `../index.html#about`,
  `../css/…`, `../js/…`, `../assets/…`. Keep these correct when copying templates.
- **`.nojekyll` must stay** or GitHub Pages' Jekyll may mishandle files (e.g. the `_TEMPLATE.html`
  underscore name).
- **Repo name is load-bearing:** a GitHub *user* site only serves from a repo named
  `neutrophil.github.io`.
- **Lucence content is intentionally high-level** (no proprietary detail).
- **Inferred fields to confirm with Junjie:** Research Fellow dates shown as **2022–2024**, and
  Lucence start date is shown as "Current" only — adjust in `index.html` timeline if wrong.

## 6. Publishing a new blog post (the workflow)

1. Copy `posts/_TEMPLATE.html` → `posts/YYYY-MM-DD-slug.html`; fill title/date/read-time/tags and
   write the body inside `<div class="prose">` (supports h2, bold/italic, links, lists,
   blockquote, inline `code`, `<pre><code>` blocks).
2. Add a card at the **top** of the `<ul class="postlist">` in `blog.html` (copy an existing
   `<li class="postlist__item">…</li>`, update link/date/title/summary/tags).
3. Preview, then commit & push. Newest post first.

## 7. Current functional state

✅ Complete and verified locally: main page, all sections, dark mode, responsive/mobile nav,
Download CV, Projects, Publications, **Blog index + first post + post template**, README, favicon.
❌ Not done: not yet committed to git or pushed to GitHub Pages (deliberately deferred).

## 8. Deploy steps (when ready — outward-facing, do on request)

```bash
cd /home/junjie/claude/personal_website
git init && git add -A && git commit -m "Personal website + blog"
git branch -M main
# create empty public repo named exactly  neutrophil.github.io  on GitHub, then:
git remote add origin https://github.com/Neutrophil/neutrophil.github.io.git
git push -u origin main
# Settings → Pages: source = main / root. Live at https://neutrophil.github.io/
```

## 9. Deferred / next ideas

- **Review & edit the inaugural post** — it's written in Junjie's first-person voice; he should
  approve/adjust before it's public.
- Point Projects cards at specific public GitHub repos (currently link to the profile generically).
- Optional later: profile photo in hero, RSS feed, custom domain, Open Graph image, simple
  per-post "previous/next" links, tag filtering on the blog index.
- Confirm/adjust the inferred employment dates (section 5).
