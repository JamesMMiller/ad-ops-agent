# Recommendation brief template

Copy this structure when advising from Profit Admin evidence. Keep it short; link paths, don’t paste huge tables.

```markdown
# Profit ops brief — YYYY-MM-DD

## Situation
- Window: …
- Sources: `outputs/profit-admin/snapshots/…`, `reports/…` (list all)
- Mode: store / SKU / mixed
- Headline: Store MER … · Meta ROAS … · Cum P&L … · Spend …
- MASTER_CONTEXT events in window: N material (list dates/titles)

## Changelog × data (what moved after what)
For each material MASTER_CONTEXT event overlapping the window (include ~7d before start if it could still be lagging):

| Date | Event | Pre → post (key metrics) | Verdict |
|------|-------|--------------------------|---------|
| YYYY-MM-DD | … | MER …→… · spend …→… · ROAS …→… · lag note | Effective / Ineffective / Mixed / Too early |

Notes:
- Call out confounding clusters (±2 days).
- PAUSED creatives / not-unmuted ads = “not yet in market”.
- Effects often take days — say when post-window is short.

## What looks effective
- … (event + numbers + why you think it worked)
- …

## What looks ineffective (or not yet proven)
- … (event + numbers, or “insufficient post data”)
- …

## What’s working (current stock / ads, independent of changelog)
- …
- …

## What’s broken / risky
- … (cite £ / × / object names)

## Next steps

### P0 — this week
1. **Action** — why (number + related changelog lesson if any) — where (Meta ad set / Shopify / KIE)
2. …

### P1 — next
1. …

### P2 — later / only if P0 holds
1. …

## Do not do
- … (anti-patterns given this data + failed changelog experiments)

## Hand-offs
- Creative: `nano-banana-image-ad` / `chatgpt-image-ad` / video → `meta-ad-builder` (PAUSED) into …
- Store: `shopify-store` …
- Supplier: `cj-dropshipping` …

## Confidence
- High / medium / low — what’s missing (fresh Refresh, unitCost, more post-event days, SKU link clarity, changelog gaps)
```

## Tone

- Direct UK English; no em dashes.
- Prefer one clear owner per action.
- If data conflicts across reports, say which report wins and why (usually: newest window + leaf Meta objects + realised `product_pnl` over list-price theory).
- Never claim a changelog event “caused” a move without numbers and a lag caveat; prefer “consistent with” / “coincides with”.
