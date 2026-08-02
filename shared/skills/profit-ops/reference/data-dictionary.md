# Profit Admin — data dictionary

Use this when reading snapshots, Ads+P&L API responses, or summarize-script digests.

## Snapshot (`outputs/profit-admin/snapshots/*.json`)

Top-level (typical):

| Field | Meaning |
|-------|---------|
| `refreshed_at` | UTC timestamp of last Refresh |
| `pnl.totals` | Store-level cumulative metrics for the full joined series |
| `pnl.days[]` | Daily series used by P&L charts |
| `product_pnl[]` | Actual sold-unit contribution by product (variants + orders dig-in) |
| `unit_economics[]` | List-price theory margins (not realised sales) |
| `sources.shopify` | Orders, catalog costs |
| `sources.meta` | Account daily spend / attr rev |
| `sources.kie` | Credits from `logs/kie-api.jsonl` |
| `sources.cj` | Postage matching (when present) |
| `warnings[]` | Partial connector failures |

### Daily P&L row (`pnl.days[]`)

| Field | Meaning |
|-------|---------|
| `rev` | Shopify order totals that day |
| `cogs` | Landed product COGS + CJ postage shares |
| `fees` | Checkout fees (default 1.5% + £0.25) |
| `ads` | Meta account spend that day (full Refresh) |
| `kie_gbp` | Estimated KIE £ that day |
| `shopify` | Shopify Basic amortised (£/day) |
| `day_pnl` | `rev − cogs − fees − ads − kie − shopify` |
| `cum_pnl` | Running sum of day_pnl |
| `attr_rev` | Meta attributed purchase revenue that day |
| `mer3d` | Trailing 3-day store MER (`sum rev / sum ads`) |

### Totals of note

| Field | Formula / note |
|-------|----------------|
| `store_mer` | Shopify revenue ÷ Meta spend (cash efficiency) |
| `meta_roas` | Meta attr rev ÷ Meta spend (Ads Manager-style) |
| `cum_pnl` | True-ish ops P&L including KIE + Shopify plan |

**Store MER ≠ Meta ROAS.** Prefer store MER for “are we making money after ads?” Prefer Meta ROAS for creative/ad-set ranking inside Ads Manager attribution.

## Ads + P&L report (`POST /api/ads/performance`)

| Field | Meaning |
|-------|---------|
| `spend`, `purchases`, `attr_rev`, `roas`, `cpa`, `ctr`, `cpc`, `cpm` | Meta Insights for the **selected** objects |
| `by_object[]` | Per campaign / ad set / ad breakdown |
| `days[]` | Combined Meta daily series |
| `series[]` | Per-object daily (overlay charts) |
| `pnl_mode` | `sku` or `store` |
| `pnl.days[]` | Chart-compatible P&L with `ads` = **selected** Meta spend |
| `pnl.totals` | Joined profitability KPIs |
| `skus` / `handles` | Product filter (empty ⇒ store mode) |
| `warnings[]` | Truncation, missing snapshot, etc. |

SKU mode **omits** KIE + Shopify amortisation (matches subset P&L). Store mode **includes** them when days come from a Refresh snapshot.

Leaf-prefer dedup: selected ads suppress parent ad sets/campaigns in the Meta pull.

## Warehouse / past performance

Planner outputs are **forward estimates**. Past-performance blocks combine Shopify product history + Meta selection — useful as a reality check vs modelled COGS/ads, not as proof of causation.

## Heuristic bands (Our Tech — starting points)

Adjust with evidence; do not treat as laws.

| Signal | Weak | Watch | Healthy |
|--------|------|-------|---------|
| Trailing 3-day store MER | &lt; 1.5× | 1.5–2.0× | ≥ 2.0× |
| Meta ROAS (attr) | &lt; 1.0× | 1.0–1.8× | ≥ 1.8× (context-dependent) |
| Cum P&L slope (7d) | Clearly down | Flat | Up |
| KIE £ / revenue | &gt; 15% | 5–15% | &lt; 5% once creatives exist |
| Product contribution (pre-ads) | Negative | Thin | Comfortably positive |

If contribution **before ads** is negative, fix price/COGS/postage before scaling spend.

## Common failure modes

1. **Comparing Meta ROAS to store MER** as if equal — they measure different things.
2. **SKU Ads report** treated as causal attribution — selection is manual.
3. **Stale snapshot** — Refresh before advising large budget changes.
4. **Fallback COGS (£3 or prefix table)** — flag low-confidence unit economics.
5. **Double-counting** Meta parents + children — desk dedupes; manually pasted tables may not.
