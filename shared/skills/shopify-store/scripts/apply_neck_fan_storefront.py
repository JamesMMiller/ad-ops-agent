#!/usr/bin/env python3
"""
Apply neck-fan storefront updates: PDP copy + campaign landing page.
Always backs up current product JSON to outputs/shopify/ before writes.

Usage:
  python apply_neck_fan_storefront.py --dry-run
  python apply_neck_fan_storefront.py --apply   # requires explicit flag
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from dotenv import load_dotenv

load_dotenv(SCRIPT_DIR / "../../../../.env")
load_dotenv(SCRIPT_DIR / "../../../.env")
load_dotenv()

from lib import shopify_api as api  # noqa: E402

HANDLE = "lazy-mute-outdoor-sports-usb-folding-leafless-hanging-neck-electric-fan"
LANDING_HANDLE = "summer-wind-neck-fan"
CONTENT_DIR = SCRIPT_DIR.parent / "content" / "neck-fan"


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    dry_run = args.dry_run

    slug = f"{date.today().isoformat()}-neck-fan-storefront"
    out_dir = api.resolve_output_dir(slug)

    description_html = (CONTENT_DIR / "description.html").read_text(encoding="utf-8")
    landing_html = (CONTENT_DIR / "landing-page.html").read_text(encoding="utf-8")

    print(f"Session output: {out_dir}")

    prod = api.get_product_by_handle(HANDLE)
    if not prod:
        print(f"ERROR: product not found for handle {HANDLE!r}", file=sys.stderr)
        return 1

    product_id = prod["id"]
    detail = api.get_product_detail(product_id)
    api.dump_json(out_dir / "product-before.json", detail)
    print(f"Backed up product → {out_dir / 'product-before.json'}")

    title = "Summer Wind Neck Fan — Hands-Free USB Cooling"
    seo_title = "Summer Wind Neck Fan | Hands-Free USB Cooling | Our Tech Accessories"
    seo_description = (
        "Four turbo fans front and rear, whisper-quiet motors, adjustable angle, "
        "Type-C battery. Free your hands — stay cool anywhere."
    )

    product_result = api.update_product(
        product_id,
        title=title,
        description_html=description_html,
        seo_title=seo_title,
        seo_description=seo_description,
        dry_run=dry_run,
    )
    api.dump_json(out_dir / "product-update-result.json", product_result)
    print("Product update:", "DRY-RUN" if dry_run else "APPLIED")

    existing_page = api.get_page_by_handle(LANDING_HANDLE)
    page_id = existing_page["id"] if existing_page else None
    page_result = api.upsert_page(
        title="Summer Wind Neck Fan",
        handle=LANDING_HANDLE,
        body_html=landing_html,
        page_id=page_id,
        is_published=True,
        dry_run=dry_run,
    )
    api.dump_json(out_dir / "landing-page-result.json", page_result)
    print("Landing page:", "DRY-RUN" if dry_run else "APPLIED", f"(handle: {LANDING_HANDLE})")

    theme_id = api.get_main_theme_id()
    if theme_id:
        index_json = api.get_theme_file(theme_id, "templates/index.json")
        if index_json:
            (out_dir / "index-before.json").write_text(index_json, encoding="utf-8")
            print(f"Backed up templates/index.json → {out_dir / 'index-before.json'}")
            print(
                "Homepage: backup only in this script. Edit index.json sections manually "
                "or use shopify_cli.py upsert-theme-files / theme_push.sh after review."
            )
        else:
            print("Could not read templates/index.json (check read_themes scope).")
    else:
        print("No MAIN theme id — set SHOPIFY_THEME_ID in .env")

    plan = {
        "product_handle": HANDLE,
        "landing_page_handle": LANDING_HANDLE,
        "landing_url": f"/pages/{LANDING_HANDLE}",
        "dry_run": dry_run,
    }
    api.dump_json(out_dir / "plan.json", plan)
    print(json.dumps(plan, indent=2))

    if dry_run:
        print("\nRe-run with --apply after user confirms.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
