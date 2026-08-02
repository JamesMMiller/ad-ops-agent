"""Shopify collector — orders, product costs, plan."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from config import repo_root

_SHOPIFY_SCRIPTS = repo_root() / "shared" / "skills" / "shopify-store" / "scripts"
if str(_SHOPIFY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SHOPIFY_SCRIPTS))


def list_catalog() -> list[dict[str, Any]]:
    """Active + draft product variants for warehouse / SKU pickers (no orders)."""
    from lib import shopify_api as api  # noqa: E402

    products_q = """
    query {
      products(first: 100) {
        nodes {
          id title handle status
          variants(first: 50) {
            nodes {
              id title sku price
              inventoryItem { unitCost { amount currencyCode } }
            }
          }
        }
      }
    }
    """
    products = api.graphql(products_q)["data"]["products"]["nodes"]
    catalog: list[dict[str, Any]] = []
    for p in products:
        for v in p["variants"]["nodes"]:
            sku = (v.get("sku") or "").strip()
            uc = (v.get("inventoryItem") or {}).get("unitCost")
            unit_cost = float(uc["amount"]) if uc and uc.get("amount") is not None else None
            catalog.append(
                {
                    "product": p["title"],
                    "handle": p["handle"],
                    "status": p["status"],
                    "variant": v["title"],
                    "sku": sku,
                    "price": float(v["price"]),
                    "unit_cost": unit_cost,
                }
            )
    catalog.sort(key=lambda r: ((r["product"] or "").lower(), r["sku"] or ""))
    return catalog


def collect_shopify() -> dict[str, Any]:
    from lib import shopify_api as api  # noqa: E402

    shop_q = """
    query {
      shop {
        name
        currencyCode
        plan { displayName partnerDevelopment shopifyPlus }
      }
    }
    """
    shop = api.graphql(shop_q)["data"]["shop"]

    catalog = list_catalog()
    cost_by_sku: dict[str, float] = {}
    for row in catalog:
        sku = row.get("sku") or ""
        if sku and row.get("unit_cost") is not None:
            cost_by_sku[sku] = float(row["unit_cost"])

    orders_q = """
    query {
      orders(first: 100, sortKey: CREATED_AT, reverse: true) {
        nodes {
          id name createdAt displayFinancialStatus
          totalPriceSet { shopMoney { amount currencyCode } }
          lineItems(first: 50) {
            nodes {
              title quantity sku
              discountedUnitPriceSet { shopMoney { amount currencyCode } }
            }
          }
        }
      }
    }
    """
    raw_orders = api.graphql(orders_q)["data"]["orders"]["nodes"]
    orders = _parse_order_nodes(raw_orders)

    return {
        "shop": {
            "name": shop.get("name"),
            "currency": shop.get("currencyCode"),
            "plan": (shop.get("plan") or {}).get("displayName"),
        },
        "cost_by_sku": cost_by_sku,
        "catalog": catalog,
        "orders": orders,
    }


def _parse_order_nodes(raw_orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    orders: list[dict[str, Any]] = []
    for o in raw_orders:
        status = (o.get("displayFinancialStatus") or "").upper()
        if status not in ("PAID", "PARTIALLY_REFUNDED", "PARTIALLY_PAID"):
            continue
        items = []
        for li in o["lineItems"]["nodes"]:
            items.append(
                {
                    "title": li["title"],
                    "sku": (li.get("sku") or "").strip(),
                    "qty": int(li["quantity"]),
                    "unit": float(li["discountedUnitPriceSet"]["shopMoney"]["amount"]),
                }
            )
        orders.append(
            {
                "name": o["name"],
                "date": o["createdAt"][:10],
                "status": status,
                "total": float(o["totalPriceSet"]["shopMoney"]["amount"]),
                "currency": o["totalPriceSet"]["shopMoney"]["currencyCode"],
                "items": items,
            }
        )
    return orders


def collect_orders_since(since: str, *, max_pages: int = 15) -> dict[str, Any]:
    """Paid orders from ``since`` (YYYY-MM-DD) onward, paginated."""
    from lib import shopify_api as api  # noqa: E402

    catalog = list_catalog()
    cost_by_sku: dict[str, float] = {}
    for row in catalog:
        sku = row.get("sku") or ""
        if sku and row.get("unit_cost") is not None:
            cost_by_sku[sku] = float(row["unit_cost"])

    # Shopify search query — filter financial status in Python for robustness.
    q = f"created_at:>={since}"
    orders_q = """
    query ($q: String!, $cursor: String) {
      orders(first: 100, query: $q, sortKey: CREATED_AT, reverse: false, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id name createdAt displayFinancialStatus
          totalPriceSet { shopMoney { amount currencyCode } }
          lineItems(first: 50) {
            nodes {
              title quantity sku
              discountedUnitPriceSet { shopMoney { amount currencyCode } }
            }
          }
        }
      }
    }
    """
    orders: list[dict[str, Any]] = []
    cursor = None
    truncated = False
    for _ in range(max_pages):
        data = api.graphql(orders_q, {"q": q, "cursor": cursor})["data"]["orders"]
        orders.extend(_parse_order_nodes(data.get("nodes") or []))
        page = data.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
        if not cursor:
            break
    else:
        truncated = True

    return {
        "cost_by_sku": cost_by_sku,
        "catalog": catalog,
        "orders": orders,
        "since": since,
        "truncated": truncated,
    }
