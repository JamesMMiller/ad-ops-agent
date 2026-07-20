#!/usr/bin/env python3
"""CLI for shopify-store skill. Run from repo root after pip install -r requirements.txt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python shopify_cli.py` from scripts/ without installing as package.
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from dotenv import load_dotenv

load_dotenv(SCRIPT_DIR / "../../../../.env")
load_dotenv(SCRIPT_DIR / "../../../.env")
load_dotenv()

from lib import shopify_api as api  # noqa: E402


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_whoami(_args: argparse.Namespace) -> int:
    _print(api.shop_info())
    return 0


def cmd_list_products(args: argparse.Namespace) -> int:
    _print(api.list_products(first=args.limit, query=args.query))
    return 0


def cmd_get_product(args: argparse.Namespace) -> int:
    if args.id:
        _print(api.get_product_detail(args.id))
        return 0
    if args.handle:
        prod = api.get_product_by_handle(args.handle)
        if not prod:
            print(f"No product with handle {args.handle!r}", file=sys.stderr)
            return 1
        _print(api.get_product_detail(prod["id"]))
        return 0
    print("Provide --id or --handle", file=sys.stderr)
    return 1


def cmd_update_product(args: argparse.Namespace) -> int:
    description = None
    if args.description_file:
        description = Path(args.description_file).read_text(encoding="utf-8")
    elif args.description_html:
        description = args.description_html

    result = api.update_product(
        args.id,
        title=args.title,
        description_html=description,
        seo_title=args.seo_title,
        seo_description=args.seo_description,
        dry_run=args.dry_run,
    )
    _print(result)
    if args.dry_run:
        print("(dry-run — no changes applied)", file=sys.stderr)
    return 0


def cmd_list_pages(_args: argparse.Namespace) -> int:
    _print(api.list_pages())
    return 0


def cmd_upsert_page(args: argparse.Namespace) -> int:
    body = Path(args.body_file).read_text(encoding="utf-8")
    page_id = args.id
    if not page_id and args.handle:
        existing = api.get_page_by_handle(args.handle)
        if existing:
            page_id = existing["id"]
    result = api.upsert_page(
        title=args.title,
        handle=args.handle,
        body_html=body,
        page_id=page_id,
        is_published=not args.draft,
        dry_run=args.dry_run,
    )
    _print(result)
    if args.dry_run:
        print("(dry-run — no changes applied)", file=sys.stderr)
    return 0


def cmd_upload_file(args: argparse.Namespace) -> int:
    result = api.create_file_from_url(args.url, alt=args.alt, dry_run=args.dry_run)
    _print(result)
    return 0


def cmd_list_themes(_args: argparse.Namespace) -> int:
    _print(api.list_themes())
    return 0


def cmd_get_theme_file(args: argparse.Namespace) -> int:
    theme_id = args.theme_id or api.get_main_theme_id()
    if not theme_id:
        print("No MAIN theme found; pass --theme-id", file=sys.stderr)
        return 1
    content = api.get_theme_file(theme_id, args.filename)
    if content is None:
        print(f"File not found: {args.filename}", file=sys.stderr)
        return 1
    if args.out:
        Path(args.out).write_text(content, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(content)
    return 0


def cmd_upsert_theme_files(args: argparse.Namespace) -> int:
    theme_id = args.theme_id or api.get_main_theme_id()
    if not theme_id:
        print("No MAIN theme found; pass --theme-id", file=sys.stderr)
        return 1
    files_payload = json.loads(Path(args.files_json).read_text(encoding="utf-8"))
    result = api.upsert_theme_files(theme_id, files_payload, dry_run=args.dry_run)
    _print(result)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Shopify Admin API CLI (shopify-store skill)")
    parser.add_argument("--dry-run", action="store_true", help="Print mutation only; no API write")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("whoami", help="Shop name + granted scopes").set_defaults(func=cmd_whoami)

    p = sub.add_parser("list-products")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--query", default=None)
    p.set_defaults(func=cmd_list_products)

    p = sub.add_parser("get-product")
    p.add_argument("--id", default=None)
    p.add_argument("--handle", default=None)
    p.set_defaults(func=cmd_get_product)

    p = sub.add_parser("update-product")
    p.add_argument("--id", required=True)
    p.add_argument("--title", default=None)
    p.add_argument("--description-html", default=None)
    p.add_argument("--description-file", default=None)
    p.add_argument("--seo-title", default=None)
    p.add_argument("--seo-description", default=None)
    p.set_defaults(func=cmd_update_product)

    sub.add_parser("list-pages").set_defaults(func=cmd_list_pages)

    p = sub.add_parser("upsert-page")
    p.add_argument("--title", required=True)
    p.add_argument("--handle", required=True)
    p.add_argument("--body-file", required=True)
    p.add_argument("--id", default=None)
    p.add_argument("--draft", action="store_true")
    p.set_defaults(func=cmd_upsert_page)

    p = sub.add_parser("upload-file")
    p.add_argument("--url", required=True)
    p.add_argument("--alt", default=None)
    p.set_defaults(func=cmd_upload_file)

    sub.add_parser("list-themes").set_defaults(func=cmd_list_themes)

    p = sub.add_parser("get-theme-file")
    p.add_argument("--filename", required=True)
    p.add_argument("--theme-id", default=None)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_get_theme_file)

    p = sub.add_parser("upsert-theme-files")
    p.add_argument("--files-json", required=True, help="JSON array of theme file upsert inputs")
    p.add_argument("--theme-id", default=None)
    p.set_defaults(func=cmd_upsert_theme_files)

    args = parser.parse_args()
    try:
        return args.func(args)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
