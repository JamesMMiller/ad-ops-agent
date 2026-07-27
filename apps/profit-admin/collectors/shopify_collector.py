"""Shopify collector — orders, product costs, plan."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from config import repo_root

_SHOPIFY_SCRIPTS = repo_root() / "shared" / "skills" / "shopify-store" / "scripts"
if str(_SHOPIFY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SHOPIFY_SCRIPTS))


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

    products_q = """
    query {
      products(first: 50) {
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

    cost_by_sku: dict[str, float] = {}
    catalog: list[dict[str, Any]] = []
    for p in products:
        for v in p["variants"]["nodes"]:
            sku = (v.get("sku") or "").strip()
            price = float(v["price"])
            uc = (v.get("inventoryItem") or {}).get("unitCost")
            unit_cost = float(uc["amount"]) if uc and uc.get("amount") is not None else None
            if sku and unit_cost is not None:
                cost_by_sku[sku] = unit_cost
            catalog.append(
                {
                    "product": p["title"],
                    "handle": p["handle"],
                    "status": p["status"],
                    "variant": v["title"],
                    "sku": sku,
                    "price": price,
                    "unit_cost": unit_cost,
                }
            )

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
