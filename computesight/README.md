# ComputeSight website

Static marketing site for ComputeSight: computer vision, AI loss prevention, sports analytics and custom AI.
No framework and no runtime build step. Plain HTML, CSS and JavaScript that any static host can serve.

## Structure

```
index.html                  Homepage (hand-built; nav, footer & latest-articles cards are injected by the builder)
solutions/<slug>/           Solution pages (generated)
about/ careers/ pricing/ contact/
legal/privacy|terms|cookies/  Legal templates (generated; complete highlighted placeholders)
blog/                       Blog index, articles, RSS feed (generated)
404.html                    Not-found page (generated)
css/styles.css              Design system and all styles
js/main.js                  Interactions, live demo engine, forms, cookie consent, analytics loader
js/blog.js                  Reading progress, table of contents, topic filter
js/config.js                Runtime settings (generated from tools/build_site.py)
assets/                     Fonts (self-hosted), icons, social images
tools/build_site.py         Site generator: edit CONFIG, SOLUTIONS and POSTS here
tools/posts/                Blog article bodies (HTML fragments)
sitemap.xml robots.txt site.webmanifest _headers .well-known/security.txt
```

## Build

```bash
python3 tools/build_site.py        # regenerate all pages, sitemap, feed, config
python3 tools/build_site.py --og   # also re-render social share images (needs Google Chrome)
```

Run it after changing anything in `tools/` and commit the generated files.

## Launch checklist

1. **Domain**: set `CONFIG["site"]` in `tools/build_site.py`, then find and replace `https://www.computesight.ai` in `index.html`.
2. **Contact & newsletter**: set `form_endpoint` (e.g. Formspree) and `newsletter_endpoint`. Until then, forms fall back to opening the visitor's email app.
3. **Emails**: set `email` and `careers_email`, and update `data-email` in the homepage contact form.
4. **Legal**: fill `legal_name`, `address` and `jurisdiction`, then have counsel review `legal/*`.
5. **Analytics (optional)**: set `analytics`. Scripts load only after the visitor accepts cookies.
6. **Social links**: add URLs under `social`. Empty entries are hidden.
7. **Content**: replace illustrative figures (homepage stats, case studies, target outcomes) with real, approved numbers.
8. Rebuild, deploy, then submit `sitemap.xml` in Google Search Console and Bing Webmaster Tools.

## Deploy

Any static host works. Point it at the project root with no build command.

- **Netlify / Cloudflare Pages**: `_headers` applies security and caching headers automatically; `404.html` is used for missing pages.
- **Vercel**: works as-is (add headers in `vercel.json` if needed).
- **GitHub Pages**: works as-is.

## Adding a blog post

1. Write the article body in `tools/posts/<slug>.html`. Start with a `<div class="takeaways">` block and give each `<h2>` an `id`.
2. Add an entry at the top of `POSTS` in `tools/build_site.py`.
3. Run `python3 tools/build_site.py --og`.
