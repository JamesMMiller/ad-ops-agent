# Product templates (Horizon / OS 2.0)

## Default vs conversion template

| File | `templateSuffix` | When to use |
|------|------------------|-------------|
| `templates/product.json` | _(empty)_ | Theme default PDP |
| `templates/product.tech-accessory.json` | `tech-accessory` | Tech accessories / multi-colour SKUs needing stronger gallery + variant UX |

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

## Agent rules

1. Backup `templates/product.json` before cloning.
2. Prefer `themeFilesUpsert`; fall back to `theme_push.sh` if blocked.
3. Do not overwrite the default `product.json` with conversion tweaks — keep a separate suffix template.
4. After assign, hard-refresh the live PDP and verify colour → image swap.
5. Record the MAIN theme id + template suffix in local `MASTER_CONTEXT.md`.
