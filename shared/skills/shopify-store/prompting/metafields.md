# Product metafields (standard pack)

Namespace: **`custom`**. Create definitions once per shop (idempotent), then set values per product from `project.json` → `metafields`.

Storefront access: **PUBLIC_READ** so Horizon / Online Store 2.0 can read them in Liquid (`{{ product.metafields.custom.tagline.value }}`).

## Definitions (PRODUCT owner)

| Key | Type | Name | Use |
|-----|------|------|-----|
| `tagline` | `single_line_text_field` | Tagline | One-line value prop under title |
| `key_benefits` | `list.single_line_text_field` | Key benefits | 3-6 short benefit lines |
| `battery_life` | `single_line_text_field` | Battery life | e.g. `Approx. 8-12 hours` |
| `noise_level` | `single_line_text_field` | Noise level | e.g. `Below 36dB` |
| `power_supply` | `single_line_text_field` | Power supply | e.g. `USB (5V)` |
| `colours` | `single_line_text_field` | Colours | Comma-separated live option values |
| `whats_in_box` | `multi_line_text_field` | What's in the box | One item per line |
| `fit_notes` | `multi_line_text_field` | Fit / use notes | Optional wear/use guidance |

## `project.json` shape

```json
{
  "metafields": {
    "tagline": "Hands-free cooling that actually earns its keep.",
    "key_benefits": [
      "Hands-free hanging design",
      "Leafless airflow: quieter and safer around hair",
      "Quiet under 36dB",
      "About 8-12 hours per USB charge"
    ],
    "battery_life": "Approx. 8-12 hours",
    "noise_level": "Below 36dB",
    "power_supply": "USB (5V)",
    "colours": "Black, Pink, White",
    "whats_in_box": "Electric neck fan × 1\nPower cord × 1\nManual × 1\nPacking box × 1",
    "fit_notes": "Adjustable arms; silicone mid-section for comfort and grip."
  }
}
```

`list.single_line_text_field` values are sent as a JSON array string by the apply script.

## Agent rules

1. On first Shopify session for a shop, ensure definitions exist (`ensure_product_metafield_definitions`).
2. On `--apply-live`, set metafields from `project.json` (skip empty keys).
3. Do not overwrite unrelated namespaces (`mc-facebook.*`, `global.*`, `shopify.*`) unless the user asks.
4. Keep values factual and aligned with the live listing / description HTML — no invented specs.
5. Prefer metafields for structured facts themes can render; keep narrative copy in `description.html`.

## Liquid examples (Horizon / OS 2.0)

```liquid
{{ product.metafields.custom.tagline.value }}
{% for benefit in product.metafields.custom.key_benefits.value %}
  <li>{{ benefit }}</li>
{% endfor %}
```
