---
name: shopify-store
description: >-
  Update a Shopify storefront via the Admin GraphQL API — products, pages, files,
  and theme templates. Uses Dev Dashboard client credentials (client ID + secret).
  Best-practice copy and UI for homepage and landing pages. Dry-run before every
  write. Use when the user asks to update Shopify theme, homepage, product page,
  store copy, PDP, or publish creatives to their Shopify store. Not for Meta ads
  (meta-ad-builder) or generating images/video (KIE skills).
---

# Shopify store

Update **Our Tech Accessories** (or any Shopify store) with high-quality copy, images, and storefront structure via the **Admin GraphQL API**. Theme file writes may fall back to **Shopify CLI + Theme Access password** when Admin `themeFilesUpsert` is blocked.

## When to use

- "Update the Shopify homepage" / "improve the product page"
- "Publish neck fan copy to the store" / "landing page for Summer Wind"
- "Upload these creatives to Shopify" / "refresh PDP description"

Do **not** use for Meta ad deployment (`meta-ad-builder`) or generative creative (`kie-external-api`).

## Read order

1. **This file** — workflow, safety, scopes.
2. **[prompting/storefront-best-practices.md](prompting/storefront-best-practices.md)** — CRO + UI checklist.
3. **[prompting/neck-fan-brief.md](prompting/neck-fan-brief.md)** — Summer Wind / Lazy Mute product facts + approved VO lines.

## Prerequisites

- **Env** (`.env` — see `.env.example`):
  - `SHOPIFY_SHOP` — e.g. `our-tech-accessories.myshopify.com`
  - `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET` — Dev Dashboard app credentials
  - `SHOPIFY_API_VERSION` — default `2025-10`
  - Optional: `SHOPIFY_THEME_ID`, `SHOPIFY_THEME_ACCESS_PASSWORD` (CLI theme push fallback)
- **Python:** `python3 -m venv .venv-shopify && source .venv-shopify/bin/activate && pip install -r scripts/requirements.txt`
- **Dev Dashboard scopes** on the installed app:
  `read_products`, `write_products`, `read_content`, `write_content`, `read_files`, `write_files`, `read_themes`, `write_themes`, `read_online_store_navigation`, `write_online_store_navigation`

Run `bash scripts/check-shopify-env.sh` before any write.

## Hard rules

1. **`--dry-run` first** on every mutation (product, page, theme files).
2. **Explicit user yes** before live writes.
3. **Backup before overwrite** — pull current product HTML / `templates/index.json` into `outputs/shopify/<date>-<slug>/` before applying.
4. **Never delete themes** or unpublish the live theme without user confirmation.
5. **Secrets stay in `.env`** — never log client secret or access tokens.

## Workflow

### Phase 1 — Connect

```bash
bash shared/skills/shopify-store/scripts/check-shopify-env.sh
python shared/skills/shopify-store/scripts/shopify_cli.py whoami
python shared/skills/shopify-store/scripts/shopify_cli.py list-themes
```

Record `MAIN` theme id in `MASTER_CONTEXT.md` → Shopify section.

### Phase 2 — Research (read-only)

```bash
python shared/skills/shopify-store/scripts/shopify_cli.py get-product \
  --handle lazy-mute-outdoor-sports-usb-folding-leafless-hanging-neck-electric-fan

python shared/skills/shopify-store/scripts/shopify_cli.py get-theme-file \
  --filename templates/index.json --out outputs/shopify/backup-index.json
```

### Phase 3 — Draft copy + structure

Follow [storefront-best-practices.md](prompting/storefront-best-practices.md) and product brief. Write:

- PDP `description.html` (benefits, specs, FAQ)
- Optional dedicated page `body.html` for a campaign landing page
- Homepage section copy blocks (hero headline, subhead, CTA) aligned to Dawn/OS 2.0 section settings

Show the user a summary; get approval.

### Phase 4 — Dry-run

```bash
python shared/skills/shopify-store/scripts/shopify_cli.py update-product \
  --dry-run --id gid://shopify/Product/... \
  --title "Summer Wind Neck Fan — Hands-Free Cooling" \
  --description-file outputs/shopify/neck-fan/description.html \
  --seo-title "Summer Wind Neck Fan | Hands-Free USB Cooling" \
  --seo-description "Four turbo fans, whisper-quiet, Type-C battery. Wear it. Forget it."
```

### Phase 5 — Apply

Remove `--dry-run` after user confirms. For homepage JSON:

1. Try `upsert-theme-files` with edited `templates/index.json`
2. If exemption/permission error → use `scripts/theme_push.sh --path outputs/shopify/theme-delta/`

### Phase 6 — Assets

Upload local or CDN images:

```bash
python shared/skills/shopify-store/scripts/shopify_cli.py upload-file \
  --url "https://cdn.shopify.com/s/files/..." --alt "Summer Wind neck fan lifestyle"
```

Attach to product via Admin (manual or follow-up `productUpdate` media workflow).

## CLI reference

| Command | Purpose |
|---------|---------|
| `whoami` | Shop + scopes |
| `list-products` / `get-product` | Catalog |
| `update-product` | PDP title, HTML, SEO |
| `list-pages` / `upsert-page` | Online Store pages |
| `list-themes` / `get-theme-file` | Theme read |
| `upsert-theme-files` | Theme write (may need exemption) |
| `upload-file` | Register image URL in Files |

All write commands accept `--dry-run`.

## Theme API exemption

If `themeFilesUpsert` returns a permissions/exemption error:

1. Request theme API access in Partner/Dev Dashboard if eligible, **or**
2. Set `SHOPIFY_THEME_ACCESS_PASSWORD` and run `bash scripts/theme_push.sh --path <delta-dir>`

## Logging

Append significant storefront changes to `MASTER_CONTEXT.md` Changelog (dated). Do not commit `.env` or backup dumps with secrets.
