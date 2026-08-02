# Our Tech — Profit Admin

Local ops dashboard that aggregates **Shopify sales + COGS**, **Meta ad spend**, and **KIE creative credits** into a P&L view with a **Refresh** button.

v1 runs on localhost. The `/api/*` layer is separate from the UI so a later Shopify Admin embed (App Bridge + public URL) can reuse the same collectors.

## Setup

From the repo root (with `.env` already configured for Shopify + Meta):

```bash
python3 -m venv .venv-profit
source .venv-profit/bin/activate
pip install -r apps/profit-admin/requirements.txt
```

Required env (see `.env.example`):

| Variable | Purpose |
|---|---|
| `SHOPIFY_SHOP` / `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET` | Orders + `unitCost` |
| `META_ACCESS_TOKEN` / `META_AD_ACCOUNT_ID` | Daily ad spend |
| `KIE_API_KEY` | Optional; credits come from `logs/kie-api.jsonl` |
| `SHOPIFY_MONTHLY_GBP` | Default `25` (Basic plan amortised) |
| `KIE_USD_PER_CREDIT` | Default `0.005` (estimate — confirm on kie.ai/pricing) |
| `USDGBP` | Optional FX override |
| `PROFIT_ADMIN_PORT` | Default `8787` |

Shopify Dev Dashboard app needs at least: `read_orders`, `read_products`, `read_inventory` (for `unitCost`).

Meta token needs ads insights read on the ad account.

## Run

```bash
cd apps/profit-admin
source ../../.venv-profit/bin/activate   # or your venv
uvicorn app:app --reload --port 8787
```

Open [http://localhost:8787](http://localhost:8787).

The desk is a **single scrollable page** with optional sections (Desk KPIs, Daily, Product P&L, Unit economics, Subset, Ads, Ads profitability, Warehouse). Toggle sections, set shared **Scope** (dates / Meta / SKUs), then **Apply**.

- **Refresh data** — pull Shopify / Meta / KIE into a new snapshot, then re-Apply enabled sections.
- **Reload view** — rehydrate a saved view’s filters and re-Apply (no source pull).
- **Save / Save as…** — persist filters + section toggles under `outputs/profit-admin/views/`.

Snapshots write to `outputs/profit-admin/snapshots/` (`latest.json` + timestamped files). Saved views: `outputs/profit-admin/views/`. Ads Apply can pin JSON to `outputs/profit-admin/reports/`. That tree is gitignored via `outputs/`.

### Agent skill — next steps from this data

Use **`profit-ops`** (`shared/skills/profit-ops/SKILL.md`) to interpret snapshots / Ads+P&L reports in context of the Shopify store and Meta account, and get prioritized scale/kill/creative/COGS recommendations.

```bash
python3 shared/skills/profit-ops/scripts/summarize_snapshot.py \
  --snapshot outputs/profit-admin/snapshots/latest.json \
  --changelog MASTER_CONTEXT.md --markdown
```

The digest cross-references **MASTER_CONTEXT Changelog** dates with pre/post metric slices (effects often lag). Save Ads Apply JSON under `outputs/profit-admin/reports/` for multi-report packs; briefs under `outputs/profit-admin/briefs/`.

## Concepts (in-app + exports)

Section and chart footnotes explain MER vs Meta ROAS, contribution, Min ROAS / Max CPA, leaf-prefer, STORE vs SKU mode, overlay, and warehouse ROAS / POAS. Source of truth:

- UI: `static/concepts.js` (loaded before `app.js` / `ads.js`)
- PDFs: `concept_copy.py` (imported by `export_pnl_pdf.py` / `export_ads_pdf.py`)

Keep those two files in sync when editing glossary copy.

## API

| Method | Path | Notes |
|---|---|---|
| `GET` | `/` | SPA (unified desk + optional sections) |
| `GET` | `/api/health` | Connector readiness (no secrets) |
| `POST` | `/api/refresh` | Pull all sources, save snapshot, return payload |
| `GET` | `/api/snapshot/latest` | Last snapshot |
| `GET` | `/api/snapshots` | List snapshot ids |
| `GET` | `/api/snapshot/{id}` | One snapshot |
| `GET` | `/api/views` | List saved desk views |
| `GET` | `/api/views/{id}` | One saved view (filters/config only) |
| `POST` | `/api/views` | Create view |
| `PUT` | `/api/views/{id}` | Update view |
| `DELETE` | `/api/views/{id}` | Delete view |
| `GET` | `/api/catalog` | Shopify variants for SKU picker |
| `GET` | `/api/warehouse/meta` | CJ warehouses, MOQ, transit defaults |
| `GET` | `/api/warehouse/lanes/{wh}` | CN→warehouse stock lanes |
| `GET` | `/api/meta/structure` | Campaigns + ad sets + ads for pickers |
| `POST` | `/api/ads/performance` | Meta insights + P&L join (optional `skus` / `handles`; store mode if empty) |
| `POST` | `/api/ads/pin` | Write Ads report JSON under `outputs/profit-admin/reports/` |
| `POST` | `/api/ads/export` | PDF of Ads + profitability (report + chart images) |
| `POST` | `/api/warehouse/past-performance` | Shopify product history + Meta insights for selected objects |
| `POST` | `/api/warehouse/calculate` | 3PL cost projection + unit COGS (+ optional past performance) |
| `POST` | `/api/pnl/subset` | Subset P&L days for selected SKUs + Meta ad sets (from earliest ad-set start) |
| `POST` | `/api/pnl/export` | PDF of the P&L desk (snapshot + all chart images; includes active subset) |
| `POST` | `/api/warehouse/export` | Excel (.xlsx) of the last calculation payload |

Snapshot includes `pnl`, `unit_economics` (list-price theory), and `product_pnl` (actual sold-unit contribution by product, with variant + order dig-in).

### Ads performance

Enable **Ads performance** / **Ads profitability** sections. Scope provides campaigns, ad sets, and/or ads (search autocomplete + chips); optional product/SKU multi-select; date preset or custom range. **Apply** runs Insights + P&L join (and pins JSON under `reports/` when Apply/Reload succeeds).

- **SKU mode** — when any SKUs are selected: product revenue/COGS/fees vs selected Meta spend (KIE / Shopify amortisation omitted).
- **Store mode** — when no SKUs: whole-store P&L for the window (prefer latest Refresh snapshot; else live orders) with ads replaced by the selected Meta spend.

Meta KPIs + charts (combined or overlay up to 12 objects), sortable breakdown table, profitability KPIs + P&L charts (cum P&L, rev vs costs, daily stack, 3-day MER). **Export Ads PDF** includes Meta + P&L sections. Leaf objects win when a parent and child are both ticked.

### Warehouse planner

Enable the **Warehouse planner** section. Models CJ 3PL fees from [cjdropshipping.com/service-fee](https://cjdropshipping.com/service-fee): inbound, labels, stock shipping CN→WH, storage by age band, outbound, plus editable last-mile postage and destination mix (UK/EU/US/CAN). Uses Scope SKUs when selected, or enter costs manually.

- **Postage included / excluded** — include = free shipping in COGS & P&L; exclude = customer pays (matches P&L desk unit economics).
- **Wholesale / dropship** — on (default): track inventory (qty, inbound, storage, restock, stockouts). Off: stock doesn’t matter — open demand at sell rate × horizon.
- **Show past performance** — optional; Shopify sales for the selected SKU’s product plus Meta spend from ticked campaigns/ad sets. Landed COGS includes CJ `postageAmount` (USD→GBP) matched by Shopify order name. Combined ROAS / ROAS-after-COGS / POAS for reality check vs the planner.
- **Daily ad spend (£)** — charged on days with stock (default); toggle off “Stop daily ads when stock is 0” to burn spend after stockout.
- **Ad cost / purchase (£)** — optional; charged per unit sold (e.g. Meta CPA). Can be used with or instead of daily spend.
- **Repeat restock** — optional (stock mode); add N units every M days (inbound fees each event; FIFO batch storage ages).
- **Overall profit / loss** — revenue − product COGS − full inbound − storage − outbound − postage (if on) − checkout fees − ads.

Figures are **estimates** — confirm live rates on CJ.

**Do not expose this server publicly in v1** — there is no auth yet (`auth.py` is a Phase 2 stub).

## P&L math

Per day:

`P&L = revenue − landed COGS − checkout fees − Meta spend − KIE (£) − Shopify Basic/31`

Per product (`product_pnl`):

`Contribution = line revenue − landed COGS − allocated checkout fees`

Checkout fees are split across line items by revenue share within the order. Meta and KIE are **not** attributed per SKU in v1.

- Landed COGS prefers Shopify **Cost per item** (`unitCost`); falls back to known CJ-derived GBP for OTA SKU prefixes; else £3/unit estimate.
- Fees default to Shopify Payments Basic UK: **1.5% + £0.25** (`PROFIT_FEE_PCT` / `PROFIT_FEE_FIXED_GBP`).
- KIE £ = credits × `KIE_USD_PER_CREDIT` × USDGBP.

## Phase 2 — embed in Shopify Admin (not built yet)

1. Host this FastAPI app on HTTPS (or a tunnel).
2. In Dev Dashboard: enable **Embed app in Shopify admin**, set **App URL** to the hosted origin.
3. Add App Bridge CDN script + `shopify-api-key` meta tag to `static/index.html`.
4. Flip `embedded = True` in [`auth.py`](auth.py) and validate session tokens on `/api/*`.
5. Keep collectors unchanged — only the auth boundary changes.

## Not in scope (v1)

- Writing costs back to Shopify
- Arcads legacy spend
- Multi-user auth / public hosting
