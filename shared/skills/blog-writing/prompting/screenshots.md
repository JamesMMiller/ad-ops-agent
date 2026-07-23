# Screenshots

Journey posts should **show** the store, not only describe it. Prefer real captures of `ourtechaccessories.com` (and related pages James built) over stock photos.

## When screenshots are required

Flagship posts that talk about the site, PDPs, branding, or UX must include at least:

1. Homepage (desktop), full first viewport or tall full-page if the hero story needs it
2. One polished product page (desktop)
3. Optional but strong: About / shipping / collections, or a **mobile** PDP when mobile UX is the beat

Weekly updates only need shots for pages that changed.

## Local layout

```
blog/posts/<YYYY-MM-DD>-<slug>/
  post.md
  post.json
  images/
    homepage-desktop.png
    pdp-neck-fan-desktop.png
    about-desktop.png          # optional
    pdp-neck-fan-mobile.png    # optional
```

- Commit PNGs (or WebP) under `images/` next to the post.
- Reference in markdown with relative paths:

```markdown
![Our Tech Accessories homepage](images/homepage-desktop.png)
```

- Alt text: plain UK English, what the reader sees (not "screenshot 1").
- Place images **after** the paragraph they illustrate, not as a dump at the end.
- Caption lightly in surrounding prose if needed; avoid heavy figure chrome.

## Capture (agent)

Prefer the helper (playwright-core + system Chrome, dismisses Shopify cookie banner):

```bash
bash shared/skills/blog-writing/scripts/capture-storefront.sh \
  blog/posts/<date>-<slug>/images
```

Edit the script's URL list when the post's hero SKU / pages differ. Fallback without playwright: headless Chrome `--screenshot=` with a hard process timeout (Shopify media pages can hang).

Typical set for a store flagship post:

| File | URL |
|------|-----|
| `homepage-desktop.png` | `https://ourtechaccessories.com/` |
| `pdp-<sku>-desktop.png` | live product URL |
| `about-desktop.png` | `/pages/about` |
| `collections-<handle>-desktop.png` | optional browse page |
| `pdp-<sku>-mobile.png` | same PDP, ~390×900 |

Rules:

- Capture the **live** storefront James is writing about (not Admin, not unpublished drafts).
- **Dismiss the cookie banner** before screenshot when possible.
- Do not invent UI. If the page is wrong, fix the URL or ask James.
- No customer PII, open carts with real emails, or Ads Manager IDs unless James asks.
- Place each image next to the prose it proves.

## Hashnode publish

Relative `images/` paths work in the repo. Before / during Hashnode draft upsert:

1. Upload each image (Hashnode `createImageUploadURL` flow, or paste into the Hashnode editor).
2. Replace local relative paths in the published markdown with the returned **public HTTPS** URLs, **or** keep locals in git and upload via CLI helper when available.
3. Optionally set `coverImageURL` in `post.json` to the best wide homepage / brand shot.

Until images are uploaded, local draft still uses relative paths for James to review in the repo.

## Perspective

Screenshots are evidence of **James's store**, not agent tooling. Prefer storefront and public pages over Cursor IDE, terminal, or Ads Manager unless that is the explicit topic.
