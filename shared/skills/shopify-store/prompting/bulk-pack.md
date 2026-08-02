# Bulk-pack product template

Reusable PDP for **volume / mix-and-match** products with colour (or style) variants — same UX as the GaN charger pack builder.

## What you get

- Buy-more-save-more tier buttons (default 2→15% / 3→20% / 4+→25%)
- Per-line colour swatches (mix colours in one pack)
- Hides native variant picker + ATC (pack UI owns add-to-cart)
- First paint shows **product featured media**; swatches jump the gallery to that variant’s media
- Template: `templates/product.bulk-pack.json` → suffix **`bulk-pack`**
- Snippet: `snippets/bulk-mix-pack.liquid` (wired from `blocks/buy-buttons.liquid`)

`gan-pack` still works (back-compat). Prefer **`bulk-pack`** for new SKUs.

## Assign to a product

```bash
# After theme files are live
python3 <<'PY'
import sys
sys.path.insert(0, 'shared/skills/shopify-store/scripts')
from lib import shopify_api as api
r = api.graphql(
  '''
  mutation ($input: ProductInput!) {
    productUpdate(input: $input) {
      product { id handle templateSuffix }
      userErrors { field message }
    }
  }
  ''',
  {'input': {
    'id': 'gid://shopify/Product/PRODUCT_ID',
    'templateSuffix': 'bulk-pack',
  }},
)
print(r)
PY
```

Or in Admin: product → Theme template → **product.bulk-pack**.

## Product setup checklist

1. **Variants** — option1 = colour/style name (Black, Green, …). Each variant should have its own featured media (colour hero).
2. **Product featured media** — group / lifestyle / all-colours plate (shown on first load).
3. **Gallery** — include featured + each colour image (`hide_variants` is on so the full set stays visible).
4. **Optional metafield** `custom.bulk_pack` (type JSON) to override copy/tiers:

```json
{
  "eyebrow": "Buy more, save more",
  "lead": "2: 15% off · 3: 20% off · 4+: 25% off",
  "unit": "charger",
  "unit_plural": "chargers",
  "max_pack": 12,
  "tiers": [
    { "qty": 1, "pct": 0, "label": "No discount", "badge": "Single" },
    { "qty": 2, "pct": 0.15, "label": "15% off", "badge": "15% off" },
    { "qty": 3, "pct": 0.2, "label": "20% off", "badge": "20% off" },
    { "qty": 4, "pct": 0.25, "label": "25% off", "badge": "25% off", "plus": true }
  ],
  "colour_css": {
    "Black": "#1c1c1c",
    "White": "#f2f0ea",
    "Green": "#7d8d53",
    "Yellow": "#d9b84a"
  }
}
```

Or set boolean metafield `custom.bulk_pack_enabled` = true on a product that still uses the default product template (pack UI will appear without changing suffix — still prefer `bulk-pack` for gallery settings).

## Discount note

Pack discounts are **calculated in the storefront UI** and applied by adding multiple line items. For automatic Shopify discounts, pair with a volume discount app / Functions later — this template is the conversion UX, not the pricing engine of record.

## Files

| Theme path | Role |
|------------|------|
| `templates/product.bulk-pack.json` | PDP layout |
| `snippets/bulk-mix-pack.liquid` | Pack builder |
| `snippets/gan-mix-pack.liquid` | Thin wrapper → bulk-mix-pack |
| `blocks/buy-buttons.liquid` | Renders pack snippet after form |
