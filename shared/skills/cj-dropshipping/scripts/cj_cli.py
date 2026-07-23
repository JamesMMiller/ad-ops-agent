#!/usr/bin/env python3
"""
CJ Dropshipping CLI — search / screen products for Our Tech listing decisions.

Examples:
  python cj_cli.py whoami
  python cj_cli.py search --query "neck fan" --countries GB,DE --min-inventory 20
  python cj_cli.py search --query "neck fan" --countries GB --json > out.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve()
for p in ROOT.parents:
    if (p / ".env").exists() or (p / ".git").exists():
        load_dotenv(p / ".env")
        break
else:
    load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import cj_api as api  # noqa: E402


def cmd_whoami(_: argparse.Namespace) -> int:
    token = api.fetch_access_token(force=True)
    cache = api._load_cache()
    print("CJ auth OK")
    print(f"  openId: {cache.get('openId')}")
    print(f"  accessTokenExpiry: {cache.get('accessTokenExpiryDate')}")
    print(f"  tokenPrefix: {token[:8]}…")
    return 0


def _score_row(p: dict, countries: list[str]) -> dict:
    """Attach a simple UK/EU listing score (heuristic, not a legal guarantee)."""
    inv = int(p.get("warehouseInventoryNum") or p.get("totalVerifiedInventory") or 0)
    verified = int(p.get("verifiedWarehouse") or 0)
    ce = int(p.get("hasCECertification") or 0)
    price = p.get("discountPrice") or p.get("nowPrice") or p.get("sellPrice")
    delivery = p.get("deliveryCycle") or ""
    flags = []
    score = 0
    if verified == 1:
        score += 2
        flags.append("verified_wh")
    if inv >= 20:
        score += 2
        flags.append("stock_ok")
    elif inv >= 10:
        score += 1
        flags.append("stock_low")
    if ce == 1:
        score += 1
        flags.append("ce")
    if countries:
        flags.append("wh:" + ",".join(countries))
        score += 1
    return {
        "score": score,
        "flags": flags,
        "id": p.get("id"),
        "sku": p.get("sku") or p.get("spu"),
        "name": p.get("nameEn") or p.get("productNameEn") or p.get("name"),
        "price": price,
        "inventory": inv,
        "verifiedWarehouse": verified,
        "hasCECertification": ce,
        "deliveryCycle": delivery,
        "image": p.get("bigImage") or p.get("productImage"),
        "category": p.get("threeCategoryName") or p.get("categoryName"),
    }


def cmd_search(args: argparse.Namespace) -> int:
    countries = [c.strip().upper() for c in (args.countries or "").split(",") if c.strip()]
    # CJ countryCode is a single code per request — search each and merge
    seen: set[str] = set()
    rows: list[dict] = []
    targets = countries or [None]
    for cc in targets:
        payload = api.search_products(
            key_word=args.query,
            country_code=cc,
            is_warehouse=not args.any_warehouse,
            verified_warehouse=None if args.include_unverified else 1,
            min_inventory=args.min_inventory,
            page=args.page,
            size=args.size,
            zone_platform=None if args.no_shopify_zone else "shopify",
            start_sell_price=args.min_price,
            end_sell_price=args.max_price,
        )
        for p in api.flatten_list_v2(payload):
            pid = str(p.get("id") or p.get("sku") or "")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            scored = _score_row(p, [cc] if cc else [])
            scored["_countryQueried"] = cc
            rows.append(scored)

    rows.sort(key=lambda r: (-r["score"], -(r["inventory"] or 0)))
    if args.min_score is not None:
        rows = [r for r in rows if r["score"] >= args.min_score]

    if args.json:
        print(json.dumps({"count": len(rows), "products": rows}, indent=2))
        return 0

    if not rows:
        print("No products matched. Try a broader query or --include-unverified.")
        return 1

    print(
        f"{'SCORE':>5}  {'PRICE':>8}  {'INV':>5}  {'CE':>2}  {'DELIV':>7}  SKU / name"
    )
    print("-" * 100)
    for r in rows[: args.limit]:
        print(
            f"{r['score']:>5}  {str(r['price'] or '-'):>8}  {r['inventory']:>5}  "
            f"{r['hasCECertification']:>2}  {str(r['deliveryCycle'] or '-'):>7}  "
            f"{r['sku']}  {r['name']}"
        )
        if args.verbose:
            print(f"       flags={','.join(r['flags'])}  id={r['id']}")
            if r.get("image"):
                print(f"       image={r['image']}")
    print()
    print(
        f"Shown {min(len(rows), args.limit)} of {len(rows)}. "
        "Higher score ≈ better UK/EU warehouse fit (not a compliance guarantee)."
    )
    print("Next: sample-order GB + DE before listing; confirm battery/lithium lane in CJ.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CJ Dropshipping product screening")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_who = sub.add_parser("whoami", help="Auth check")
    p_who.set_defaults(func=cmd_whoami)

    p_s = sub.add_parser("search", help="Search products (warehouse-first defaults)")
    p_s.add_argument("--query", "-q", required=True, help="Keyword (e.g. neck fan)")
    p_s.add_argument(
        "--countries",
        default="GB,DE",
        help="Comma warehouse country codes (default GB,DE). Empty = no country filter",
    )
    p_s.add_argument("--min-inventory", type=int, default=10)
    p_s.add_argument("--min-price", type=float, default=None)
    p_s.add_argument("--max-price", type=float, default=None)
    p_s.add_argument("--page", type=int, default=1)
    p_s.add_argument("--size", type=int, default=20)
    p_s.add_argument("--limit", type=int, default=25, help="Rows to print")
    p_s.add_argument("--min-score", type=int, default=None)
    p_s.add_argument("--include-unverified", action="store_true")
    p_s.add_argument("--any-warehouse", action="store_true", help="Do not force isWarehouse")
    p_s.add_argument("--no-shopify-zone", action="store_true")
    p_s.add_argument("--json", action="store_true")
    p_s.add_argument("--verbose", "-v", action="store_true")
    p_s.set_defaults(func=cmd_search)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
