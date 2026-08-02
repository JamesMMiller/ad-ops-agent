#!/usr/bin/env python3
"""Build Shopify page.inbox-deal.liquid from deal-followup.{html,txt}.

The page template looks up the live GaN product price via all_products and
replaces __GAN_BASE_PRICE__ so deal emails stay in sync with Admin pricing.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "shared/skills/store-inbox/apps-script/templates"
HTML = (SRC / "deal-followup.html").read_text(encoding="utf-8")
PLAIN = (SRC / "deal-followup.txt").read_text(encoding="utf-8")
if not HTML.endswith("\n"):
    HTML += "\n"
if not PLAIN.endswith("\n"):
    PLAIN += "\n"

# Bump when template structure changes (price itself is live from the product).
VERSION = "gan-live-price-2026-07-31"
GAN_HANDLE = "120w-gan-fast-charger-with-a-built-in-retractable-cable"
# Used only if all_products lookup fails on the storefront.
PRICE_FALLBACK = "18.99"
PRICE_TOKEN = "__GAN_BASE_PRICE__"

if PRICE_TOKEN not in HTML or PRICE_TOKEN not in PLAIN:
    raise SystemExit(
        f"Expected {PRICE_TOKEN} in deal-followup.html and deal-followup.txt"
    )

LIQUID = (
    "{% comment %}\n"
    "  Inbox bot deal bodies endpoint.\n"
    "  URL: /pages/inbox-deal\n"
    "  Returns JSON: html + plain + version + base_price.\n"
    "  __GAN_BASE_PRICE__ is filled from the live GaN product (all_products).\n"
    "  Source: apps-script/templates/deal-followup.{html,txt}\n"
    "  Regenerate: python3 shared/skills/store-inbox/scripts/build-inbox-deal-page.py\n"
    "{% endcomment %}\n"
    "{% layout none %}\n"
    f"{{% assign gan_product = all_products['{GAN_HANDLE}'] %}}\n"
    "{% if gan_product %}\n"
    "  {% assign gan_base_price = gan_product.price | money_without_currency | strip %}\n"
    "{% else %}\n"
    f"  {{% assign gan_base_price = '{PRICE_FALLBACK}' %}}\n"
    "{% endif %}\n"
    "{% capture deal_html %}{% raw %}\n"
    + HTML
    + "{% endraw %}{% endcapture %}\n"
    "{% capture deal_plain %}{% raw %}\n"
    + PLAIN
    + "{% endraw %}{% endcapture %}\n"
    f"{{% assign deal_html = deal_html | replace: '{PRICE_TOKEN}', gan_base_price %}}\n"
    f"{{% assign deal_plain = deal_plain | replace: '{PRICE_TOKEN}', gan_base_price %}}\n"
    f'{{% assign deal_version = "{VERSION}" %}}\n'
    "{\n"
    '  "version": {{ deal_version | json }},\n'
    '  "base_price": {{ gan_base_price | json }},\n'
    '  "html": {{ deal_html | strip | json }},\n'
    '  "plain": {{ deal_plain | strip | json }}\n'
    "}\n"
)

OUTS = [
    SRC / "page.inbox-deal.liquid",
    ROOT / "outputs/shopify/theme-inbox-deal/templates/page.inbox-deal.liquid",
]


def main() -> None:
    assert "{{NAME_SUFFIX}}" in LIQUID
    assert "{% raw %}" in LIQUID
    assert "all_products[" in LIQUID
    assert PRICE_TOKEN in LIQUID
    for path in OUTS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(LIQUID, encoding="utf-8")
        print(f"Wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
