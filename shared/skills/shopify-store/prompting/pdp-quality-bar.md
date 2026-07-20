# PDP quality bar (definition of done)

Agents must hit this bar **before** asking the user to approve `--apply-live`. Drafts that fail any **Required** item are not review-ready.

## Required (every PDP project)

1. **Campaign URL lock** — if ads hit the PDP, `live_url_locked: true` and **never** change `handle`.
2. **Responsive description HTML** — see [storefront-best-practices.md](storefront-best-practices.md): fluid type, stacked specs (no wide tables), colour chips matching live options, FAQ `<details>`.
3. **SEO** — `seo_title` ≤ 60 chars, `seo_description` ≤ 155 chars, filled in `project.json`.
4. **Multi-variant products** — live options pulled; every sellable colour/size has:
   - Correct Admin option values (no invented brand names)
   - Featured media linked (`mediaId`) so the theme gallery swaps on select
5. **Draft preview quality** (`--apply-draft`):
   - Share live media via `fileUpdate.referencesToAdd` (images **and** videos) — **never** re-upload CDN URLs with `productCreateMedia`
   - Copy options/variants + prices
   - Link variant → media (same as live)
   - Empty-media drafts are a **bug**
6. **Admin review path** — user reviews draft (or Theme Preview) before `--apply-live`. Never set the live ACTIVE product to `DRAFT`.
7. **Metafields** — set the standard `custom.*` pack from [metafields.md](metafields.md) on apply-live (and optionally on draft).
8. **Product template** — for tech accessories, assign `templateSuffix: tech-accessory` when the theme file exists (see [product-templates.md](product-templates.md)).

## Strongly recommended

- Landing page with per-variant `?variant=` deep links when running paid traffic to a campaign page
- Sticky ATC + colour swatches on the assigned theme template
- Judge.me / reviews on `product_data`, not sample data
- Backup under `outputs/shopify/<date>-<slug>/` before every live write
- Dated `MASTER_CONTEXT.md` Changelog entry after material storefront changes

## Image generation (optional)

- Prefer the existing live gallery
- New stills only after credit estimate + explicit yes
- Reject stills that invent badges/brand names or fail product likeness
- Do not replace live masters with softer re-uploads

## Anti-patterns (do not ship)

| Anti-pattern | Do instead |
|--------------|------------|
| Draft with empty media | `referencesToAdd` from live |
| Re-upload gallery via CDN URL | Share file GIDs |
| Wide `<table>` specs | Stacked `<dl>` / grid |
| Single “Shop now” on multi-colour landing | Swatches + `?variant=` |
| Invented “Summer Wind” style branding | Live option values only |
| Em dashes (—) in titles, body, SEO, metafields | Colon, period, comma, or rewrite |
| Apply-live without draft/user yes | `--apply-draft` → approve → `--apply-live` |
| Change handle to “clean up” URL | Keep handle; 301s already protect ads |
