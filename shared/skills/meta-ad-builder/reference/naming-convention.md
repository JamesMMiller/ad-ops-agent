# Meta naming convention (Our Tech Accessories)

Searchable, short names for Ads Manager and Profit Admin. Use **` | `** as the delimiter (substring search works on each token).

## Pattern

| Level | Pattern | Example |
|-------|---------|---------|
| Campaign | `OTA \| Sales \| {geo} \| {budget_mode}` | `OTA \| Sales \| GB \| ABO` |
| Ad set | `OTA \| {sku} \| {funnel} \| {goal} \| {test?}` | `OTA \| GaN \| Cold \| Purchase \| CT` |
| Ad | `OTA \| {sku} \| {angle} \| {variant} \| {ratio} \| {fmt}` | `OTA \| GaN \| v2 \| what-is-white \| 1x1 \| img` |

## Tokens

- **sku:** `GaN` · `Qi2` · `Vac` · `Fan` · `Multi` · `RT` (retargeting mix)
- **funnel:** `Cold` · `Warm` · `Hot`
- **goal:** `Purchase` (default for sales)
- **test:** `CT` = creative test (optional)
- **budget_mode:** `ABO` (ad-set budgets) · `CBO` (campaign budget)
- **angle:** `educate` · `explained` · `plain` · `v2` · `deal` · `reels` · …
- **variant:** short creative slug (`what-is-white`, `benefits-yellow`)
- **ratio:** `1x1` · `9x16` · `16x9`
- **fmt:** `img` · `vid`

## Rules

1. Always start with `OTA` so account-wide search is one token.
2. Put **SKU second** on ad sets and ads — filter `GaN` / `Qi2` instantly.
3. Do not put dates or £ amounts in names (budgets change; use Ads Manager columns).
4. Prefer renaming over deleting when pausing — history stays readable.
5. New deploys from `deploy-ad.py` should set `--name` (or post-rename) to this pattern.

## Applied 2026-07-31

Campaign `120250086201690639` → `OTA | Sales | GB | ABO` with ABO £15 GaN + £15 Qi2.
