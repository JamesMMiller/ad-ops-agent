# Product templates (Horizon / OS 2.0)

## Product type → template (pick one)

| Product type | `template_suffix` | When |
|--------------|-------------------|------|
| Default | _(empty)_ | Simple single-SKU / no special gallery needs |
| **Tech accessory** | `tech-accessory` | Multi-colour accessories; stronger gallery + swatches + sticky ATC |
| **Phone case** | `phone-case` | MagSafe / magnetic cases: model + colour picker, Qi2 strip, inline compat checker. Collection: `collection.phone-cases` + `qi2-compat-checker` section |
| **Bulk pack** | `bulk-pack` | Volume / mix-and-match (“buy more, save more” + per-line colour slots). Full guide: [bulk-pack.md](bulk-pack.md) |
| Legacy GaN pack | `gan-pack` | Existing GaN charger only — new volume SKUs use **`bulk-pack`** |

**Agent rule:** If the brief mentions volume discount, mix colours in one cart, pack builder, or “2 for 15% / 3 for 20%”, use **`bulk-pack`**, not `tech-accessory`.

## Template files

| File | `templateSuffix` |
|------|------------------|
| `templates/product.json` | _(empty)_ |
| `templates/product.tech-accessory.json` | `tech-accessory` |
| `templates/product.phone-case.json` | `phone-case` (+ `snippets/phone-case-picker.liquid`) |
| `templates/collection.phone-cases.json` | collection suffix `phone-cases` (+ `sections/qi2-compat-checker.liquid`) |
| `templates/product.bulk-pack.json` | `bulk-pack` |
| `templates/product.gan-pack.json` | `gan-pack` (legacy) |

## `tech-accessory` quality settings

When creating or updating `templates/product.tech-accessory.json` (clone from `product.json`, then tune):

- `large_first_image`: **true**
- `hide_variants`: **true** (gallery follows selected variant media)
- `thumbnail_position`: **bottom**
- Variant picker: **buttons** + `show_swatches`: **true**
- `enable_sticky_add_to_cart`: **true**
- Title type preset: **h2** (or stronger than body)
- Related products: `carousel_on_mobile`: **true**
- Reviews apps: use **product** data, not sample/demo data

Assign with Admin GraphQL `productUpdate` → `templateSuffix: "tech-accessory"`, or set `template_suffix` in `project.json` for `--apply-live`.

## `bulk-pack` quality settings

Theme must include `templates/product.bulk-pack.json` + `snippets/bulk-mix-pack.liquid` (wired from buy-buttons).

- `hide_variants`: **false** (keep full gallery in the DOM so pack JS can jump by media id; label is “hide unselected variant media”)
- `large_first_image`: **true**
- Product **featured media** = group / all-colours plate (first paint)
- Each **variant** featured media = that colour
- Pack UI hides native variant picker + ATC
- Optional metafields: `custom.bulk_pack` (JSON), `custom.bulk_pack_enabled` (boolean) — see [metafields.md](metafields.md) + [bulk-pack.md](bulk-pack.md)

Assign: `template_suffix: "bulk-pack"` in `project.json`, or Admin → Theme template → **product.bulk-pack**.

## Agent rules

1. Backup `templates/product.json` before cloning.
2. Prefer `themeFilesUpsert`; fall back to `theme_push.sh` if blocked.
3. Do not overwrite the default `product.json` with conversion tweaks — keep a separate suffix template.
4. After assign, hard-refresh the live PDP and verify colour → image swap (and pack tiers if bulk-pack).
5. Record the MAIN theme id + template suffix in local `MASTER_CONTEXT.md`.
6. Prefer **`bulk-pack`** over **`gan-pack`** for every new volume / mix-variant SKU.

## Bulk-pack checklist (volume + mix variants)

1. Read **[bulk-pack.md](bulk-pack.md)**.
2. Ensure theme has `templates/product.bulk-pack.json` + `snippets/bulk-mix-pack.liquid`.
3. Set product `templateSuffix` to `bulk-pack`.
4. Featured media = group shot; each variant media = that colour.
5. Optional: `custom.bulk_pack` JSON for tiers / unit labels / swatch colours.
