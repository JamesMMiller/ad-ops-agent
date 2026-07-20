#!/usr/bin/env python3
"""
Apply a storefront product content project from a local (gitignored) folder.

Project dir layout (default under outputs/shopify/projects/<name>/):
  project.json       — handle, titles, SEO, flags
  description.html   — proposed PDP body

Modes:
  --dry-run       Print mutations only
  --apply-draft   Create DRAFT duplicate for Admin review (live URL unchanged)
  --apply-live    Update LIVE product title/body/SEO (handle never changes)

Usage:
  python apply_product_project.py --project outputs/shopify/projects/neck-fan --dry-run
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


def load_project(project_dir: Path) -> tuple[dict, str]:
    cfg_path = project_dir / "project.json"
    if not cfg_path.exists():
        raise RuntimeError(f"Missing {cfg_path}")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    for key in ("handle", "proposed_title"):
        if not cfg.get(key):
            raise RuntimeError(f"project.json missing required key: {key}")
    desc_name = cfg.get("description_file", "description.html")
    desc_path = project_dir / desc_name
    if not desc_path.exists():
        raise RuntimeError(f"Missing description file: {desc_path}")
    return cfg, desc_path.read_text(encoding="utf-8")


def create_draft_duplicate(cfg: dict, description_html: str, *, dry_run: bool) -> dict:
    handle = cfg["handle"]
    draft_handle = f"{handle}-draft-review"
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
            "title": f"[DRAFT REVIEW] {cfg['proposed_title']}",
            "handle": draft_handle,
            "descriptionHtml": description_html,
            "status": "DRAFT",
            "seo": {
                "title": cfg.get("seo_title") or cfg["proposed_title"],
                "description": cfg.get("seo_description") or "",
            },
        }
    }
    return api.graphql(q, variables, dry_run=dry_run)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        required=True,
        help="Path to local project dir (e.g. outputs/shopify/projects/neck-fan)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply-draft", action="store_true")
    mode.add_argument("--apply-live", action="store_true")
    args = parser.parse_args()

    project_dir = Path(args.project).resolve()
    if not project_dir.is_dir():
        print(f"ERROR: project dir not found: {project_dir}", file=sys.stderr)
        return 1

    cfg, description_html = load_project(project_dir)
    handle = cfg["handle"]
    dry_run = bool(args.dry_run)

    slug = f"{date.today().isoformat()}-{cfg.get('name') or project_dir.name}"
    out_dir = api.resolve_output_dir(slug)

    print(f"Project: {project_dir}")
    print(f"Session output: {out_dir}")
    print(f"Handle: {handle}" + (" (LOCKED)" if cfg.get("live_url_locked") else ""))

    prod = api.get_product_by_handle(handle)
    if not prod:
        print(f"ERROR: product not found for handle {handle!r}", file=sys.stderr)
        return 1

    product_id = prod["id"]
    detail = api.get_product_detail(product_id)
    api.dump_json(out_dir / "product-before.json", detail)
    print(f"Backed up live product → {out_dir / 'product-before.json'}")

    if args.apply_live or dry_run:
        live_result = api.update_product(
            product_id,
            title=cfg["proposed_title"],
            description_html=description_html,
            seo_title=cfg.get("seo_title"),
            seo_description=cfg.get("seo_description"),
            dry_run=dry_run or not args.apply_live,
        )
        api.dump_json(out_dir / "live-update-result.json", live_result)
        print(
            "Live product update:",
            "DRY-RUN" if (dry_run or not args.apply_live) else "APPLIED (handle unchanged)",
        )

    if args.apply_draft or dry_run:
        draft_result = create_draft_duplicate(
            cfg,
            description_html,
            dry_run=dry_run or not args.apply_draft,
        )
        api.dump_json(out_dir / "draft-duplicate-result.json", draft_result)
        print(
            "Draft duplicate:",
            "DRY-RUN" if (dry_run or not args.apply_draft) else "CREATED (live URL untouched)",
        )

    plan = {
        "project": str(project_dir),
        "handle": handle,
        "live_url_locked": bool(cfg.get("live_url_locked")),
        "mode": "dry-run" if dry_run else ("apply-draft" if args.apply_draft else "apply-live"),
        "images": cfg.get("images", "reuse_existing_gallery"),
        "never_set_live_product_status_to_draft": True,
    }
    api.dump_json(out_dir / "plan.json", plan)
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
