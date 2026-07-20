#!/usr/bin/env python3
"""
Neck-fan PDP content update — campaign URL / handle locked.

Modes:
  --dry-run       Print mutations only (no writes)
  --apply-draft   Create DRAFT duplicate product for Admin review (live URL unchanged)
  --apply-live    Update LIVE product title/body/SEO only (handle never changes)

Never sets the live product status to DRAFT (would break active ads).
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
CONTENT_DIR = SCRIPT_DIR.parent / "content" / "neck-fan"

PROPOSED_TITLE = "Folding Hanging Neck Electric Fan — Hands-Free Cooling"
SEO_TITLE = "Folding Neck Fan | Hands-Free USB Cooling | Our Tech Accessories"
SEO_DESCRIPTION = (
    "Leafless hanging neck fan with quiet motors (under 36dB), adjustable fit, "
    "and 8–12 hour USB battery. Black, Pink, or White. Free your hands — stay cool."
)


def create_draft_duplicate(description_html: str, *, dry_run: bool) -> dict:
    draft_handle = f"{HANDLE}-draft-review"
    q = """
    mutation productCreate($input: ProductInput!) {
      productCreate(input: $input) {
        product { id title handle status }
        userErrors { field message }
      }
    }
    """
    variables = {
        "input": {
            "title": f"[DRAFT REVIEW] {PROPOSED_TITLE}",
            "handle": draft_handle,
            "descriptionHtml": description_html,
            "status": "DRAFT",
            "seo": {"title": SEO_TITLE, "description": SEO_DESCRIPTION},
        }
    }
    return api.graphql(q, variables, dry_run=dry_run)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply-draft", action="store_true")
    mode.add_argument("--apply-live", action="store_true")
    args = parser.parse_args()

    dry_run = bool(args.dry_run)
    slug = f"{date.today().isoformat()}-neck-fan-storefront"
    out_dir = api.resolve_output_dir(slug)
    description_html = (CONTENT_DIR / "description.html").read_text(encoding="utf-8")

    print(f"Session output: {out_dir}")
    print(f"LOCKED handle: {HANDLE}")

    prod = api.get_product_by_handle(HANDLE)
    if not prod:
        print(f"ERROR: product not found for handle {HANDLE!r}", file=sys.stderr)
        return 1

    product_id = prod["id"]
    detail = api.get_product_detail(product_id)
    api.dump_json(out_dir / "product-before.json", detail)
    print(f"Backed up live product → {out_dir / 'product-before.json'}")

    if args.apply_live or dry_run:
        live_result = api.update_product(
            product_id,
            title=PROPOSED_TITLE,
            description_html=description_html,
            seo_title=SEO_TITLE,
            seo_description=SEO_DESCRIPTION,
            dry_run=dry_run or not args.apply_live,
        )
        api.dump_json(out_dir / "live-update-result.json", live_result)
        print(
            "Live product update:",
            "DRY-RUN" if (dry_run or not args.apply_live) else "APPLIED (handle unchanged)",
        )

    if args.apply_draft or dry_run:
        draft_result = create_draft_duplicate(
            description_html,
            dry_run=dry_run or not args.apply_draft,
        )
        api.dump_json(out_dir / "draft-duplicate-result.json", draft_result)
        print(
            "Draft duplicate:",
            "DRY-RUN" if (dry_run or not args.apply_draft) else "CREATED (live URL untouched)",
        )

    plan = {
        "live_handle_locked": HANDLE,
        "live_url_locked": True,
        "mode": "dry-run" if dry_run else ("apply-draft" if args.apply_draft else "apply-live"),
        "images": "reuse_existing_gallery",
        "never_set_live_product_status_to_draft": True,
    }
    api.dump_json(out_dir / "plan.json", plan)
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
