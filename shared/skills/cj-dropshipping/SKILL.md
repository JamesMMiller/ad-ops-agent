---
name: cj-dropshipping
description: >-
  Search and screen CJ Dropshipping products via API for Shopify listing decisions.
  Prefers GB/DE warehouse stock, verified inventory, and Shopify-oriented catalog filters.
  Use when the user mentions CJ, CJdropshipping, supplier product search for UK/EU, or
  wants to pick dropship SKUs with better SLAs than China-only fulfilment.
---

# CJ Dropshipping

Use CJ’s API to **find listing candidates**, not to auto-publish. You remain merchant of record; prefer **GB/DE warehouse** stock for UK + EU.

## Setup

1. CJ personal center → **API** → create **API Key** → copy.
2. Add to repo `.env` (never commit):
   ```bash
   CJ_API_KEY='your_key_here'
   ```
3. Check:
   ```bash
   bash shared/skills/cj-dropshipping/scripts/check-cj-env.sh
   ```

## Search (UK/EU-first defaults)

```bash
python3 shared/skills/cj-dropshipping/scripts/cj_cli.py search \
  --query "neck fan" \
  --countries GB,DE \
  --min-inventory 20 \
  --verbose
```

Defaults: `isWarehouse=true`, `verifiedWarehouse=1`, `zonePlatform=shopify`, inventory sort.

JSON for review packs:

```bash
python3 shared/skills/cj-dropshipping/scripts/cj_cli.py search \
  -q "wireless charger" --countries GB,DE --json \
  > outputs/cj/$(date +%F)-wireless-charger.json
```

## Listing gate (before Shopify import)

Only advance a SKU if:

1. Stock in **GB and/or DE** (search both; prefer SKUs that appear for both).
2. Verified warehouse inventory above your floor.
3. Sample order to **UK + one EU country** with real tracking.
4. CJ confirms **battery/lithium** shipping for that lane (if applicable).
5. Returns/lost-parcel terms are acceptable **in writing**.
6. Storefront promises stay at legal minimum until reverse logistics is proven.

## Hard rules

- Do **not** put `CJ_API_KEY` or tokens in git, chats logs, or `outputs/` JSON.
- Token cache lives in `.cache/cj-token.json` (gitignored).
- Score in the CLI is a **heuristic**, not compliance advice.
- Install the [CJ Shopify app](https://cjdropshipping.com/integrations/shopify) for order automation after a SKU passes the gate.
