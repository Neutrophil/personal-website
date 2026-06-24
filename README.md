# Junjie Chen — Personal Website

A fast, dependency-free personal site (static HTML / CSS / vanilla JS) showcasing my work in
clinical genomics, bioinformatics and machine learning, built to support a job search toward
**AI for Life Science**.

- **Live URL (once deployed):** https://neutrophil.github.io/
- **Stack:** plain HTML + CSS + vanilla JS. No build step, no framework, no trackers, no CDNs.

## Structure

```
index.html             # the single-page main site
blog.html              # blog index (lists posts)
posts/                 # one HTML file per post + _TEMPLATE.html
css/styles.css         # design system (light/dark themes, responsive)
js/main.js             # theme toggle, mobile nav, scrollspy, reveal-on-scroll
assets/cv/             # downloadable CV (PDF)
assets/favicon.svg     # monogram favicon
.nojekyll              # serve files as-is on GitHub Pages
```

## Publishing a blog post

No build step or Markdown — each post is a small standalone HTML file:

1. Copy `posts/_TEMPLATE.html` to `posts/YYYY-MM-DD-slug.html`.
2. Fill in the title, date, read time, tags, and write the body inside `<div class="prose">`
   (the template shows the supported elements: headings, bold/italic, links, lists, blockquotes,
   inline `code` and code blocks).
3. Add a card for it at the **top** of the list in `blog.html` — copy the existing
   `<li class="postlist__item">…</li>` block and update its link, date, title and summary.
4. Preview locally, then commit & push. The newest post goes first.

## Preview locally

No Node required — any static server works. Using the project's conda Python:

```bash
cd /home/junjie/claude/personal_website
~/miniconda3/envs/investing/bin/python -m http.server 8000
# open http://localhost:8000
```

## Deploy to GitHub Pages

This is a **user site**, so the repo must be named exactly `neutrophil.github.io`.

1. Create a public repo named `neutrophil.github.io` on GitHub (no README/license — keep it empty).
2. From this folder:

   ```bash
   git init
   git add -A
   git commit -m "Initial personal website"
   git branch -M main
   git remote add origin https://github.com/Neutrophil/neutrophil.github.io.git
   git push -u origin main
   ```

3. In the repo's **Settings → Pages**, confirm the source is the `main` branch (`/root`).
   The site goes live at https://neutrophil.github.io/ within a minute or two.

A custom domain can be added later under Settings → Pages → Custom domain.

## Editing

All content lives in `index.html` — update text, swap the CV in `assets/cv/`, or point the
project cards at specific GitHub repos. Colors and spacing are CSS variables at the top of
`css/styles.css`.
