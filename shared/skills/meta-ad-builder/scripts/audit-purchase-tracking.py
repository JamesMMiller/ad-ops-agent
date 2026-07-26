#!/usr/bin/env python3
"""On-demand reconcile: paid Shopify orders vs Meta Purchase event totals.

Lookback is capped at 7 days (Meta pixel stats API limit). Exits non-zero when
Shopify paid count > Meta Purchase count. Never prints customer PII.

Usage:
  python audit-purchase-tracking.py
  python audit-purchase-tracking.py --days 7
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(ROOT / "shared/skills/shopify-store/scripts"))

import meta_api  # noqa: E402
from lib import shopify_api as shopify  # noqa: E402


def _load_env() -> None:
    for candidate in (ROOT / ".env", Path.cwd() / ".env"):
        if candidate.is_file():
            load_dotenv(candidate)
            return
    load_dotenv()


def _paid_orders_since(since: datetime) -> list[dict]:
    """Return non-test PAID/PARTIALLY_PAID web orders created since `since`."""
    # Shopify search uses shop timezone-ish filters; use created_at ISO date
    day = since.date().isoformat()
    q = """
    query Orders($q: String!, $cursor: String) {
      orders(first: 50, query: $q, after: $cursor, sortKey: CREATED_AT, reverse: true) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          name
          createdAt
          displayFinancialStatus
          test
          sourceName
          totalPriceSet { shopMoney { amount currencyCode } }
        }
      }
    }
    """
    # Broad query then filter client-side for reliability
    query = f"created_at:>={day} financial_status:paid"
    out: list[dict] = []
    cursor = None
    since_ts = since.timestamp()
    while True:
        data = shopify.graphql(q, {"q": query, "cursor": cursor})["data"]["orders"]
        for node in data["nodes"]:
            if node.get("test"):
                continue
            status = (node.get("displayFinancialStatus") or "").upper()
            if status not in ("PAID", "PARTIALLY_PAID"):
                continue
            created = node.get("createdAt") or ""
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                continue
            if dt.timestamp() < since_ts:
                continue
            money = ((node.get("totalPriceSet") or {}).get("shopMoney")) or {}
            out.append(
                {
                    "name": node.get("name"),
                    "created_at": created,
                    "source_name": node.get("sourceName"),
                    "currency": money.get("currencyCode"),
                    "amount": money.get("amount"),
                    # hashed-ish stable id for logs — last 6 of numeric id only
                    "order_id_suffix": meta_api.normalize_order_event_id(node["id"])[-6:],
                }
            )
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
        if len(out) > 200:
            break
    return out


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Lookback days (capped at 7 for Meta stats)",
    )
    args = parser.parse_args()
    days = max(1, min(int(args.days), 7))

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    orders = _paid_orders_since(since)
    shopify_paid = len(orders)
    revenue = 0.0
    for o in orders:
        try:
            revenue += float(o.get("amount") or 0)
        except (TypeError, ValueError):
            pass

    totals = meta_api.pixel_event_totals(days=days)
    meta_purchase = int(totals.get("purchase") or 0)
    counts = totals.get("counts") or {}

    mismatch = shopify_paid > meta_purchase
    report = {
        "lookback_days": days,
        "since_utc": since.isoformat(),
        "until_utc": now.isoformat(),
        "pixel_id": totals.get("pixel_id"),
        "shopify_paid_orders": shopify_paid,
        "shopify_paid_revenue_sum": round(revenue, 2),
        "meta_purchase_events": meta_purchase,
        "delta_shopify_minus_meta": shopify_paid - meta_purchase,
        "mismatch": mismatch,
        "meta_funnel_counts": {
            k: counts.get(k, 0)
            for k in (
                "PageView",
                "ViewContent",
                "AddToCart",
                "InitiateCheckout",
                "AddPaymentInfo",
                "Purchase",
            )
        },
        "orders": orders,
        "diagnostics": [],
    }

    diags: list[str] = []
    if mismatch:
        diags.append(
            "Shopify has more paid orders than Meta Purchase events. "
            "Check Facebook & Instagram → Share data is Maximum + correct pixel, "
            "then backfill with send-purchase-capi.py --order-name '#…' --send"
        )
    if shopify_paid == 0 and meta_purchase == 0:
        diags.append("No paid orders and no Purchase events in lookback — nothing to reconcile.")
    if counts.get("InitiateCheckout", 0) > 0 and meta_purchase == 0 and shopify_paid > 0:
        diags.append(
            "Funnel reaches InitiateCheckout but Purchase is missing while Shopify has paid orders "
            "— classic thank-you / CAPI gap."
        )
    if not mismatch and shopify_paid > 0:
        diags.append(
            "Counts match at aggregate level. Meta Stats API cannot prove order-level receipt."
        )
    report["diagnostics"] = diags

    print(json.dumps(report, indent=2))
    return 1 if mismatch else 0


if __name__ == "__main__":
    raise SystemExit(main())
