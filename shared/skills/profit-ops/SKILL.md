---
name: profit-ops
description: >-
  Analyse Profit Admin snapshots and Ads/P&L/Warehouse reports, cross-reference
  MASTER_CONTEXT.md Changelog dates with the time series (allowing for lag),
  judge which changes looked effective or not, and recommend next ops steps
  (budget, creative, SKU focus, COGS, warehouse). Use when the user mentions
  Profit Admin, P&L, MER, store ROAS, ad performance reports, profitability
  next steps, which ads/SKUs to scale or kill, changelog vs performance, or
  wants advice from one or many profit-admin exports/snapshots.
---

# Profit ops advisor

Turn **Profit Admin data** into clear, prioritized next steps for Our Tech
Accessories — not a generic media-buying lecture. Ground every recommendation
in numbers from the desk plus live store/account context.

## When to use

Trigger on phrases like:
- "what should I do next with ads / spend / P&L?"
- "analyse this Profit Admin report / snapshot / PDF"
- "which campaigns / ad sets / ads / SKUs to scale or kill?"
- "is MER / ROAS healthy?" / "why is P&L negative?"
- "compare these two Ads reports" / "warehouse plan vs past performance"

Do **not** use this skill to *generate* creatives (image/video skills) or to
*publish* Meta ads (`meta-ad-builder`). Hand off when a next step needs those.

## Read order

1. **This file** — workflow and hard rules.
2. **`MASTER_CONTEXT.md`** — brand, Meta default ad sets, **and the full Changelog** (dated events).
3. **[reference/changelog-correlation.md](reference/changelog-correlation.md)** — how to align events with daily metrics + lag.
4. **[reference/data-dictionary.md](reference/data-dictionary.md)** — field meanings, formulas, MER/ROAS bands.
5. **[prompting/recommendation-brief.md](prompting/recommendation-brief.md)** — output template (includes effectiveness section).
6. **`apps/profit-admin/README.md`** — desk math and API map (only if unsure).

## Inputs (gather in this order)

### A. Profit Admin evidence (required)

Prefer machine-readable JSON over PDF screenshots.

| Source | Path / how |
|--------|------------|
| Latest full Refresh | `outputs/profit-admin/snapshots/latest.json` |
| Older snapshots | `outputs/profit-admin/snapshots/*.json` |
| Saved desk views | `outputs/profit-admin/views/*.json` (filters/sections only — Reload ≠ Refresh) |
| Saved Ads+P&L reports | `outputs/profit-admin/reports/*.json` (pinned on Apply/Reload, or via `/api/ads/pin`) |
| Live desk | `http://127.0.0.1:8787` — unified desk; `GET /api/snapshot/latest`, `GET /api/views`, `POST /api/ads/performance` |
| User-attached PDF | Accept, but ask for JSON/snapshot when numbers are ambiguous |

**Refresh data** pulls Shopify/Meta/KIE into a snapshot. **Reload view** re-applies a saved view’s scope/sections without a source pull. Prefer snapshot + reports JSON for analysis; views are config recipes, not results.

Compress large snapshots before reasoning:

```bash
python3 shared/skills/profit-ops/scripts/summarize_snapshot.py \
  --snapshot outputs/profit-admin/snapshots/latest.json
```

Save an Ads performance API payload for multi-report memory:

```bash
# After Apply in the UI, or via curl — write the JSON response:
# outputs/profit-admin/reports/YYYY-MM-DD-<label>.json
python3 shared/skills/profit-ops/scripts/summarize_snapshot.py \
  --report outputs/profit-admin/reports/<file>.json
```

### B. Store + account context (required for “best next steps”)

- **Brand / defaults:** `MASTER_CONTEXT.md` (products, Meta ad set IDs, tone).
- **Changelog timeline (required):** parse every `### YYYY-MM-DD` entry that falls in the report window or up to **7 days before** the window start. These are candidate causes for bends in spend / MER / ROAS / P&L. See [reference/changelog-correlation.md](reference/changelog-correlation.md).
- **Catalog / products:** Shopify skill + Admin API, or Profit Admin `/api/catalog`, or `product_pnl` / `unit_economics` inside the snapshot.
- **Meta structure:** campaigns / ad sets / ads via Profit Admin `/api/meta/structure` or Meta skill scripts (`pull-top-ads.py` when ranking winners).
- **Creative pipeline:** KIE spend is in snapshot `sources.kie` / daily `kie_gbp` — treat as variable opex, not media ROAS.

If the snapshot is missing or stale, tell the user to open Profit Admin → **Refresh data**, then **Reload view** / **Apply** if they use a saved view.

Digest with changelog overlays:

```bash
python3 shared/skills/profit-ops/scripts/summarize_snapshot.py \
  --snapshot outputs/profit-admin/snapshots/latest.json \
  --changelog MASTER_CONTEXT.md --markdown
```

### C. Optional multi-report pack

When the user provides **several** reports (SKU Ads dig-ins, store window, warehouse past performance):

1. Normalise each to: window, selection (Meta ids + SKUs), mode (`store`/`sku`), spend, attr rev, Shopify rev, MER, Meta ROAS, cum P&L.
2. Compare **like with like** (same window and mode). Call out when one report is SKU-scoped and another is store-wide.
3. Prefer leaf Meta objects (ads/ad sets) for creative decisions; campaigns for budget/structure.

## Analysis workflow

### 1. Situate

State in 2–4 lines:
- Date window and data freshness (`refreshed_at`)
- Store MER vs Meta ROAS vs cum P&L (and whether KIE/Shopify amort are included)
- Mode: full store vs SKU subset vs selected Meta objects
- How many **material** MASTER_CONTEXT changelog events fall in / just before the window

### 2. Correlate changelog → data (required)

Do this **before** generic diagnosis. Follow [reference/changelog-correlation.md](reference/changelog-correlation.md).

1. Build the event list from `MASTER_CONTEXT.md` Changelog (filter out pure tooling unless it changed live store/ads).
2. For each material event date `D`, compare pre (`D-7…D-1`) vs post (`D…D+7`) metrics on the daily series. Allow for **lag** — short post windows ⇒ “too early / inconclusive”.
3. Verdict per event: **Effective** / **Ineffective** / **Mixed** / **Too early** / **Not in market** (e.g. still PAUSED).
4. Cluster confounding events within ±2 days; do not pretend you can isolate them.
5. Feed these verdicts into the brief sections **Changelog × data**, **What looks effective**, **What looks ineffective**.

### 3. Diagnose (use the dictionary)

Check, in order:
1. **Contribution before ads** — product_pnl / unit economics (negative contribution = pricing or COGS problem, not an ads problem).
2. **Media efficiency** — store MER and Meta ROAS vs bands in the data dictionary.
3. **Concentration** — top ads/ad sets by spend vs ROAS; waste (high spend, low purchases).
4. **Trend** — last 3–7 days vs earlier in the window (MER3d, cum P&L slope), annotated with nearby changelog events.
5. **Creative cost** — KIE £ as % of revenue / of ad spend.
6. **Ops** — warehouse / stock only if a warehouse or past-performance report is in the pack.

### 4. Recommend

Produce a brief using [prompting/recommendation-brief.md](prompting/recommendation-brief.md).

Every action must be:
- **Tied to a number** from the evidence (“Ad X spent £Y at 0.4× Meta ROAS”)
- **Informed by changelog lessons** when relevant (“after £19.99 GaN price on 2026-07-30, …”)
- **Owned** — who/what system (Meta Ads Manager, Shopify cost, KIE gen, CJ warehouse)
- **Sized** — kill / cut 50% / hold / scale +20%, not vague “optimise”
- **Sequenced** — P0 this week, P1 next, P2 later

When creative is the bottleneck, point to the right generator skill + `meta-ad-builder` for PAUSED deploy into the default ad sets from `MASTER_CONTEXT.md`.

### 5. Persist (when useful)

Write a short markdown brief under:

`outputs/profit-admin/briefs/YYYY-MM-DD-<topic>.md`

Link the source snapshot/report paths in the brief footer.

## Hard rules

- **Estimates only** — Profit Admin figures (especially KIE £, CJ fees, fallback COGS) are estimates. Say so when recommending spend changes.
- **No secrets** — never paste `.env` tokens; never commit snapshots that contain PII if the user asks to share externally (orders may include names).
- **Don’t invent attribution** — Meta attr rev ≠ Shopify revenue; SKU mode does not prove those ads caused those SKU sales unless the user asserts the link. Changelog vs metrics is **correlational**; use “consistent with”, not false certainty.
- **Always read the Changelog** — skipping MASTER_CONTEXT dated entries is a skill failure for this workflow.
- **Leaf-prefer Meta selection** — same as the Ads desk: don’t double-count campaign + its ad sets.
- **UK store context** — Our Tech Accessories; GBP; prefer GB/DE fulfilment thinking when warehouse advice comes up (`cj-dropshipping` skill).
- **No silent Meta/Shopify writes** — recommendations only unless the user explicitly asks to deploy or edit the store (then hand off to the right skill with dry-run).

## Related skills

| Need | Skill |
|------|--------|
| Change storefront / costs display | `shopify-store` |
| Deploy / pause Meta ads | `meta-ad-builder` |
| New creatives | `nano-banana-image-ad` / `chatgpt-image-ad` / video skills |
| Supplier / warehouse SKUs | `cj-dropshipping` |
| Desk itself | `apps/profit-admin/README.md` |
