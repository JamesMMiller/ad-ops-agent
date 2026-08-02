# Changelog × Profit Admin correlation

Always cross-reference **`MASTER_CONTEXT.md` → Changelog** with the report window. Dated decisions (price changes, new ad sets, PDP launches, deal bots, creative deploys) are the event timeline; Profit Admin days are the outcome series. Effects often lag **1–7 days** (learning, delivery, checkout).

## What to extract from MASTER_CONTEXT

For each `### YYYY-MM-DD (...title...)` entry inside the report window (and ~7 days before start):

| Pull | From |
|------|------|
| `date` | Heading date |
| `title` | Parenthetical / heading text |
| `decision` | **Decision:** line |
| `changed` | **What changed:** line (ids, prices, ad sets, handles) |
| `why` | **Why:** line |
| `tags` | Infer: `pricing`, `creative`, `meta-structure`, `pdp`, `inbox`, `ops-tooling`, `branding` |

Also read **Meta ad deployment** defaults (named ad set → id) so object names in Ads reports map to known tests.

Ignore pure tooling/docs changelog noise unless it changed live store or live ads (e.g. “Profit Admin PDF export” alone does not move MER). Prefer events that touch: price, offer, PDP, Meta ads/ad sets, creatives, shipping/COGS, deal inbox.

## How to align with data

1. Take daily series from snapshot `pnl.days` and/or Ads report `pnl.days` / Meta `days`.
2. For each **material** event date `D`:
   - **Pre window:** `D-7` … `D-1` (or from series start)
   - **Post window:** `D` … `D+7` (or to series end) — note if post window is shorter than 3 days (“too early”)
3. Compare: spend, rev, store MER (or rev/ads), Meta ROAS/attr_rev, cum P&L slope, purchases.
4. Label outcome:
   - **Effective** — clear improvement post-`D` vs pre (cite numbers)
   - **Ineffective / harmful** — clear worsening or spend up without rev/ROAS
   - **Mixed / inconclusive** — conflicting signals, too little post data, or confounding events within ±3 days
5. When multiple events cluster (±2 days), treat as a **bundle** and say you cannot isolate which change drove the move.

## Lag honesty

- Meta learning / delivery: often **2–5 days**
- Price or deal copy: can show in **same-day** conversion rate, but volume needs a few days
- New creatives in PAUSED sets: **no data impact until unmuted** — mark as “not yet in market” if still paused
- Organic Page posts: weak/noisy vs paid; don’t over-claim

## Script help

```bash
python3 shared/skills/profit-ops/scripts/summarize_snapshot.py \
  --snapshot outputs/profit-admin/snapshots/latest.json \
  --changelog MASTER_CONTEXT.md \
  --markdown
```

Adds overlapping changelog events and simple pre/post metric slices. Still apply judgment; the script does not decide “effective”.
