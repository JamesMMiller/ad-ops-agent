# Storefront best practices (Shopify)

Use this checklist when rewriting **homepage**, **collection**, or **product (PDP)** content.

## Homepage (index)

**Section order (mobile-first):**

1. **Hero** — one product or category promise; full-bleed image or video; single primary CTA (e.g. "Shop now").
2. **Problem → solution** — 3 bullets max above the fold on mobile.
3. **Featured product** — hero SKU with price, rating placeholder, secondary CTA.
4. **Benefits grid** — 3–4 icons + short lines (not paragraphs).
5. **Social proof** — reviews, UGC stills, or "as seen in" strip.
6. **How it works** — 3 steps with product-in-use photos.
7. **FAQ** — 4–6 accordion items (shipping, battery, noise, fit).
8. **Final CTA** — repeat primary offer; trust badges (secure checkout, returns).

**Copy rules:**

- Headline ≤ 8 words; subhead ≤ 20 words.
- Write for **scannability**: short paragraphs, bold lead-ins.
- One primary keyword per section; avoid keyword stuffing.
- UK/US spelling: pick one locale and stay consistent.
- **No em dashes (—) in customer-facing copy** (homepage, PDP, landing pages, metafields, SEO). They read as AI-generated. Prefer a colon, comma, period, or a short rewrite (`Hands-free design: wear it…` / `Free your hands. Stay cool.`). ASCII hyphen `-` is fine in ranges (`8-12 hours`).

**UI rules (OS 2.0 / Dawn family):**

- Generous vertical rhythm; avoid more than 2 font sizes per section.
- Product photos on neutral or lifestyle backgrounds — match ad creative where possible.
- Buttons: high contrast; one primary color only.
- No unmuted autoplay on hero/background video (browser policy). **Product gallery videos** should be click-to-play with sound: `video_autoplay: false`, `video_muted: false`, full controls — do not hardcode `muted: true` + `disable_controls: true` on PDP media.
- **Never leave the hero section `disabled: true`** on a live homepage.
- Put the **hero SKU on the homepage** with variant picker + Add to cart (`featured-product-information` on Horizon) — a product grid alone under-converts paid traffic.
- Backup `templates/index.json` before every homepage write.

## Product page (PDP)

**Above the fold:** product title, price, variant selector, Add to cart, 2-line value prop.

**Below the fold structure:**

1. **Benefits** (not features first) — lead with the customer outcome
2. **Feature/spec table** — turbo fans, battery, noise, USB-C, adjustable angle
3. **Lifestyle gallery** — 4–6 images; alt text on every image
4. **Comparison** — vs generic neck fans (quiet, dual-sided airflow)
5. **FAQ** — mask-friendly, gym, office, battery life
6. **Shipping & returns** — short policy summary

**Description HTML (responsive):**

- Wrap body in a single container with `max-width` + `width: 100%` (theme column already constrains; avoid fixed px widths).
- Prefer stacked `<dl>` / grid rows over wide `<table>` (tables overflow on mobile).
- Use `clamp()` for type; stack spec labels above values under ~420px.
- Colour / option callouts: chips or short list matching **live** option values — variant picker stays in the theme form above the description.
- FAQ: `<details>/<summary>` accordion (works in most themes without JS).

**SEO:**

- Title: `Brand + Product + primary benefit` (≤ 60 chars)
- Meta description: benefit + spec hook + CTA (≤ 155 chars)
- H1 = product title only; use H2 for sections in description HTML

## Landing page (campaign)

When creating a dedicated page (not PDP):

- Match ad creative headline verbatim in H1.
- Primary CTA linking to PDP (add UTM params when the campaign needs them).
- Remove main nav distractions if using a minimal landing template.
- Mobile: CTA sticky or repeated after every 2 sections.

### Multi-variant products (required when the SKU has options)

If the product has options (e.g. Color: Black / Pink / White):

1. **Pull live variants** before drafting — Admin GraphQL `product.variants` + `options`; store numeric IDs for storefront `?variant=<id>` links.
2. **Surface every sellable option** above the fold — swatches or labelled buttons, not a single generic “Shop now” that hides colour choice.
3. **Deep-link each option** to `/products/<handle>?variant=<variantNumericId>` so the PDP opens with that variant pre-selected (price/image/ATC match).
4. Keep a **fallback CTA** to `/products/<handle>` (no variant) for shoppers who want to compare on the PDP.
5. **Never invent brand names / colourways** that are not on the live product; copy must match Admin option values exactly.
6. Repeat the variant chooser near the final CTA (mobile often never scrolls back to the hero picker).
7. If inventory differs by variant, prefer linking only `availableForSale` options (or label sold-out clearly).
8. **Variant featured media (required for colour/style options):** each sellable variant must have a matching product media item attached (`productVariantsBulkUpdate` → `mediaId`). Themes then swap the gallery featured image when the shopper changes the option. Copying a gallery without linking variants leaves colour pickers stuck on the first image.
9. **Draft media quality:** when duplicating a product for Admin review, **share** live files via `fileUpdate.referencesToAdd` (images + videos). Do **not** re-upload CDN URLs with `productCreateMedia` — that re-encodes and can soften images. If the live masters are only ~800–1000px, sharpness is limited until higher-res originals are uploaded to the live product.

## Quality gate before publish

Use **[pdp-quality-bar.md](pdp-quality-bar.md)** as the full checklist. Minimum:

- [ ] Dry-run mutations printed and user approved
- [ ] Backup saved under `outputs/shopify/`
- [ ] Draft had shared media + variant image links (not empty gallery)
- [ ] Responsive description HTML (no wide tables)
- [ ] `custom.*` metafields filled when applying live
- [ ] `template_suffix` set for tech accessories when theme file exists
- [ ] All images have alt text (or plan to fix alts)
- [ ] No lorem ipsum; no placeholder prices; no invented brand/colour names
- [ ] Links tested on mobile viewport
- [ ] Spelling / brand name consistent with `MASTER_CONTEXT.md`

Related: [metafields.md](metafields.md) · [product-templates.md](product-templates.md) · [project-local-content.md](project-local-content.md)
