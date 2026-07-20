# Local Shopify projects (gitignored)

Put **store-specific** briefs, HTML, and `project.json` under:

```
outputs/shopify/projects/<project-name>/
  project.json          # required
  description.html      # required — responsive PDP body
  brief.md              # optional
  landing-page.html     # optional — multi-variant deep links
  REVIEW.md             # optional — human checklist
```

These paths are under `outputs/` and are **not** committed to git.

## `project.json` schema

```json
{
  "name": "neck-fan",
  "handle": "folding-hanging-neck-electric-fan",
  "live_url_locked": true,
  "proposed_title": "…",
  "seo_title": "…",
  "seo_description": "…",
  "description_file": "description.html",
  "template_suffix": "tech-accessory",
  "images": "reuse_existing_gallery",
  "metafields": {
    "tagline": "…",
    "key_benefits": ["…", "…"],
    "battery_life": "…",
    "noise_level": "…",
    "power_supply": "…",
    "colours": "Black, Pink, White",
    "whats_in_box": "…",
    "fit_notes": "…"
  }
}
```

See [metafields.md](metafields.md), [pdp-quality-bar.md](pdp-quality-bar.md), [product-templates.md](product-templates.md).

## Apply

```bash
python shared/skills/shopify-store/scripts/apply_product_project.py \
  --project outputs/shopify/projects/<project-name> \
  --dry-run

# After approval:
python …/apply_product_project.py --project … --apply-draft   # enriched draft
python …/apply_product_project.py --project … --apply-live    # title/body/SEO/metafields/template
```

`--apply-live` never changes `handle` when `live_url_locked` is true. Metafields + `template_suffix` apply on live (and metafields optionally on draft).
