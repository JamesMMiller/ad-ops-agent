---
name: shopify-store
description: >-
  Update a Shopify storefront via the Admin GraphQL API — products, pages, files,
  metafields, and theme templates. Uses Dev Dashboard client credentials (client ID + secret).
  Best-practice CRO copy and UI for homepage, PDP, and landing pages. Dry-run before every
  write. Use when the user asks to update Shopify theme, homepage, product page,
  store copy, PDP, metafields, product templates, or publish creatives to their Shopify store.
  Not for Meta ads (meta-ad-builder) or generating images/video (KIE skills).
---

# Shopify store

Update any Shopify store with high-quality copy, images, metafields, and storefront structure via the **Admin GraphQL API**. Theme file writes may fall back to **Shopify CLI + Theme Access password** when Admin `themeFilesUpsert` is blocked.

## When to use

- "Update the Shopify homepage" / "improve the product page"
- "Refresh PDP copy" / "create a draft product page for review"
- "Add product metafields" / "assign a product template"
- "Upload these creatives to Shopify Files"

Do **not** use for Meta ad deployment (`meta-ad-builder`) or generative creative (`kie-external-api`).

## Read order

1. **This file** — workflow, safety, scopes.
2. **[prompting/pdp-quality-bar.md](prompting/pdp-quality-bar.md)** — definition of done (hit before apply-live).
3. **[prompting/storefront-best-practices.md](prompting/storefront-best-practices.md)** — CRO + UI checklist.
4. **[prompting/metafields.md](prompting/metafields.md)** — standard `custom.*` pack.
5. **[prompting/product-templates.md](prompting/product-templates.md)** — `tech-accessory` template.
6. **[prompting/project-local-content.md](prompting/project-local-content.md)** — gitignored project layout.

## Project-local content (not in git)

**Never commit store-specific product copy, handles, or briefs into `shared/skills/`.**

Put them under the gitignored tree:

```
outputs/shopify/projects/<project-name>/
  project.json
  description.html
  brief.md            # optional
  landing-page.html   # optional
```

Record active campaign handles / goals in **local** `MASTER_CONTEXT.md` (also gitignored), not in templates with real product IDs.

## Prerequisites

- **Env** (`.env` — see `.env.example`):
  - `SHOPIFY_SHOP` — e.g. `your-store.myshopify.com`
  - `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET` — Dev Dashboard app credentials
  - `SHOPIFY_API_VERSION` — default `2025-10`
  - Optional: `SHOPIFY_THEME_ID`, `SHOPIFY_THEME_ACCESS_PASSWORD` (CLI theme push fallback)
- **Python:** `python3 -m venv .venv-shopify && source .venv-shopify/bin/activate && pip install -r scripts/requirements.txt`
- **Dev Dashboard scopes** on the installed app:
  `read_products`, `write_products`, `read_content`, `write_content`, `read_files`, `write_files`, `read_themes`, `write_themes`, `read_online_store_navigation`, `write_online_store_navigation`

Run `bash scripts/check-shopify-env.sh` before any write.

## Hard rules

1. **`--dry-run` first** on every mutation (product, page, theme files, metafields).
2. **Explicit user yes** before live writes.
3. **Backup before overwrite** — pull current product HTML / `templates/index.json` into `outputs/shopify/<date>-<slug>/` before applying.
4. **Never delete themes** or unpublish the live theme without user confirmation.
5. **Secrets stay in `.env`** — never log client secret, client ID, or access tokens (mask in check scripts).
6. **Campaign URL lock:** If ads point at a PDP, **never change `handle` / product URL**. Update title, body, SEO, media, metafields in place only.
7. **Draft before publish:** Default review path is a **DRAFT duplicate** (`--apply-draft`). **Never** set the live ACTIVE product to `DRAFT`. Draft enrich must:
   - Share live media via **`fileUpdate.referencesToAdd`** (images + videos) — never re-upload CDN URLs
   - Copy options/variants + prices
   - Link each variant to its featured media (`mediaId`)
8. **Images:** Prefer existing product gallery. Only generate new images after user approval + credit estimate (KIE Nano Banana / ChatGPT Image). Reject invented branding / failed likeness.
9. **No client product data in the skill pack** — briefs and HTML stay under `outputs/` (gitignored).
10. **Quality bar:** Do not request `--apply-live` until [pdp-quality-bar.md](prompting/pdp-quality-bar.md) Required items pass.
11. **Metafields + template:** On apply-live, set the standard `custom.*` pack and `template_suffix` when present in `project.json`.
12. **No em dashes (—) in storefront copy** (titles, body HTML, SEO, metafields, homepage/landing). Use colon, period, comma, or rewrite. See [storefront-best-practices.md](prompting/storefront-best-practices.md).

## Workflow

### Phase 1 — Connect

```bash
bash shared/skills/shopify-store/scripts/check-shopify-env.sh
python shared/skills/shopify-store/scripts/shopify_cli.py whoami
python shared/skills/shopify-store/scripts/shopify_cli.py list-themes
```

Record `MAIN` theme id in local `MASTER_CONTEXT.md` → Shopify section.

Ensure metafield definitions once per shop (script does this on apply):

```bash
python -c "from lib import shopify_api as api; import sys; sys.path.insert(0,'shared/skills/shopify-store/scripts'); ..."
```

(`apply_product_project.py` calls `ensure_product_metafield_definitions` automatically.)

### Phase 2 — Research (read-only)

```bash
python shared/skills/shopify-store/scripts/shopify_cli.py get-product --handle <product-handle>
python shared/skills/shopify-store/scripts/shopify_cli.py get-theme-file \
  --filename templates/product.json --out outputs/shopify/backup-product.json
```

Pull variants + media associations. Note if `templates/product.tech-accessory.json` already exists.

### Phase 3 — Draft copy locally

Create or update `outputs/shopify/projects/<name>/` per [project-local-content.md](prompting/project-local-content.md). Fill `metafields` + `template_suffix`. Follow [storefront-best-practices.md](prompting/storefront-best-practices.md) and [pdp-quality-bar.md](prompting/pdp-quality-bar.md). Show the user a summary; get approval.

### Phase 4 — Dry-run

```bash
python shared/skills/shopify-store/scripts/apply_product_project.py \
  --project outputs/shopify/projects/<name> \
  --dry-run
```

### Phase 5 — Apply (draft first)

```bash
python shared/skills/shopify-store/scripts/apply_product_project.py \
  --project outputs/shopify/projects/<name> \
  --apply-draft

# After approval — live title/body/SEO/metafields/template (handle locked when flagged)
python shared/skills/shopify-store/scripts/apply_product_project.py \
  --project outputs/shopify/projects/<name> \
  --apply-live
```

### Phase 6 — Product template (if missing)

Clone/tune `templates/product.tech-accessory.json` per [product-templates.md](prompting/product-templates.md). Upsert via `upsert-theme-files` or `theme_push.sh`. Assign with `template_suffix` in `project.json` on the next `--apply-live`, or `productUpdate.templateSuffix`.

### Phase 7 — Assets

**Default: keep existing gallery images.** New creatives only after **KIE credit estimate** + yes.

### Auth troubleshooting

| Error | Fix |
|-------|-----|
| `app_not_installed` | Dev Dashboard → Release version with scopes → **Install app** on the target shop |
| `shop_not_permitted` | App and store must be in the **same organization** |
| Wrong shop | `SHOPIFY_SHOP` must be exact `*.myshopify.com` subdomain |

## CLI reference

| Command / script | Purpose |
|------------------|---------|
| `whoami` | Shop + scopes |
| `list-products` / `get-product` | Catalog |
| `update-product` | PDP title, HTML, SEO |
| `list-pages` / `upsert-page` | Online Store pages |
| `list-themes` / `get-theme-file` | Theme read |
| `upsert-theme-files` | Theme write (may need exemption) |
| `upload-file` | Register image URL in Files |
| `apply_product_project.py` | Project-dir draft/live apply (media share, variants, metafields, template) |

All write commands accept `--dry-run`.

## Theme API exemption

If `themeFilesUpsert` returns a permissions/exemption error:

1. Request theme API access in Partner/Dev Dashboard if eligible, **or**
2. Set `SHOPIFY_THEME_ACCESS_PASSWORD` and run `bash scripts/theme_push.sh --path <delta-dir>`

## Logging

Append significant storefront changes to local `MASTER_CONTEXT.md` Changelog (dated). Do not commit `.env` or `outputs/`.
