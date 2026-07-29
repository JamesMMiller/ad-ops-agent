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

Open [http://localhost:8787](http://localhost:8787) → click **Refresh**.

Snapshots write to `outputs/profit-admin/snapshots/` (`latest.json` + timestamped files). That tree is gitignored via `outputs/`.

## API

| Method | Path | Notes |
|---|---|---|
| `GET` | `/` | SPA |
| `GET` | `/api/health` | Connector readiness (no secrets) |
| `POST` | `/api/refresh` | Pull all sources, save snapshot, return payload |
| `GET` | `/api/snapshot/latest` | Last snapshot |
| `GET` | `/api/snapshots` | List snapshot ids |
| `GET` | `/api/snapshot/{id}` | One snapshot |

Snapshot includes `pnl`, `unit_economics` (list-price theory), and `product_pnl` (actual sold-unit contribution by product, with variant + order dig-in).

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
