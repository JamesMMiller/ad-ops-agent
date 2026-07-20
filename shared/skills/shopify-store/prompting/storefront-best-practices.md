# Storefront best practices (Shopify)

Use this checklist when rewriting **homepage**, **collection**, or **product (PDP)** content.

## Homepage (index)

**Section order (mobile-first):**

1. **Hero** — one product or category promise; full-bleed image or video; single primary CTA ("Shop Summer Wind").
2. **Problem → solution** — 3 bullets max above the fold on mobile.
3. **Featured product** — hero SKU with price, rating placeholder, secondary CTA.
4. **Benefits grid** — 3–4 icons + short lines (not paragraphs).
5. **Social proof** — reviews, UGC stills, or "as seen in" strip.
6. **How it works** — 3 steps with product-in-use photos.
7. **FAQ** — 4–6 accordion items (shipping, battery, noise, fit).
8. **Final CTA** — repeat primary offer; trust badges (secure checkout, returns).

**Copy rules:**

- Headline ≤ 8 words; subhead ≤ 20 words.
- Write for **scannability** — short paragraphs, bold lead-ins.
- One primary keyword per section; avoid keyword stuffing.
- UK/US spelling: pick one locale and stay consistent.

**UI rules (OS 2.0 / Dawn family):**

- Generous vertical rhythm; avoid more than 2 font sizes per section.
- Product photos on neutral or lifestyle backgrounds — match ad creative where possible.
- Buttons: high contrast; one primary color only.
- No autoplay audio on hero video.

## Product page (PDP)

**Above the fold:** product title, price, variant selector, Add to cart, 2-line value prop.

**Below the fold structure:**

1. **Benefits** (not features first) — "Hands-free cooling that earns its keep"
2. **Feature/spec table** — turbo fans, battery, noise, USB-C, adjustable angle
3. **Lifestyle gallery** — 4–6 images; alt text on every image
4. **Comparison** — vs generic neck fans (quiet, dual-sided airflow)
5. **FAQ** — mask-friendly, gym, office, battery life
6. **Shipping & returns** — short policy summary

**SEO:**

- Title: `Brand + Product + primary benefit` (≤ 60 chars)
- Meta description: benefit + spec hook + CTA (≤ 155 chars)
- H1 = product title only; use H2 for sections in description HTML

## Landing page (campaign)

When creating a dedicated page (not PDP):

- Match ad creative headline verbatim in H1.
- Single CTA linking to PDP with UTM params.
- Remove main nav distractions if using a minimal landing template.
- Mobile: CTA sticky or repeated after every 2 sections.

## Quality gate before publish

- [ ] Dry-run mutations printed and user approved
- [ ] Backup saved under `outputs/shopify/`
- [ ] All images have alt text
- [ ] No lorem ipsum; no placeholder prices
- [ ] Links tested on mobile viewport
- [ ] Spelling / brand name consistent ("Summer Wind", "Our Tech Accessories")
