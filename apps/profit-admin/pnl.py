"""Build daily / cumulative P&L and unit economics from collector payloads."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from config import fee_fixed_gbp, fee_pct, shopify_monthly_gbp

# Fallback landed GBP when Shopify unitCost missing (CJ-derived, Jul 2026).
FALLBACK_COGS_PREFIX: list[tuple[str, float]] = [
    ("CJSJ2765376", 5.69),  # GaN
    ("CJEJ1477239", 10.56),  # neck fan
    ("CJSJ2249530", 6.86),  # vacuum mount
    ("CJJT2757674", 12.02),  # travel adapter
]


def _landed_for_sku(sku: str, qty: int, cost_by_sku: dict[str, float]) -> float:
    if sku and sku in cost_by_sku:
        return cost_by_sku[sku] * qty
    for prefix, landed in FALLBACK_COGS_PREFIX:
        if sku.startswith(prefix):
            return landed * qty
    return 3.0 * qty  # unknown QS estimate


def _parse_day(s: str) -> date:
    return date.fromisoformat(s)


def build_pnl(
    *,
    shopify: dict[str, Any] | None,
    meta: dict[str, Any] | None,
    kie: dict[str, Any] | None,
) -> dict[str, Any]:
    cost_by_sku: dict[str, float] = dict((shopify or {}).get("cost_by_sku") or {})
    orders = list((shopify or {}).get("orders") or [])
    meta_days = list((meta or {}).get("days") or [])
    kie_days = list((kie or {}).get("days") or [])

    rev_by: dict[str, float] = defaultdict(float)
    cogs_by: dict[str, float] = defaultdict(float)
    fees_by: dict[str, float] = defaultdict(float)
    orders_by: dict[str, int] = defaultdict(int)

    fee_p = fee_pct()
    fee_f = fee_fixed_gbp()
    for o in orders:
        d = o["date"]
        rev_by[d] += float(o["total"])
        orders_by[d] += 1
        fees_by[d] += float(o["total"]) * fee_p + fee_f
        for it in o.get("items") or []:
            cogs_by[d] += _landed_for_sku(
                it.get("sku") or "", int(it.get("qty") or 0), cost_by_sku
            )

    spend_by = {r["date"]: float(r["spend"]) for r in meta_days}
    attr_by = {r["date"]: float(r["attr_rev"]) for r in meta_days}
    kie_by = {r["date"]: float(r["gbp"]) for r in kie_days}
    kie_cr_by = {r["date"]: float(r["credits"]) for r in kie_days}

    all_dates: set[str] = set()
    all_dates.update(rev_by)
    all_dates.update(spend_by)
    all_dates.update(kie_by)
    if not all_dates:
        # empty series — still return structure
        today = datetime.now(timezone.utc).date().isoformat()
        all_dates.add(today)

    start = min(_parse_day(d) for d in all_dates)
    end = max(_parse_day(d) for d in all_dates)
    # include today if meta is running
    today = datetime.now(timezone.utc).date()
    if end < today:
        end = today

    shop_day = shopify_monthly_gbp() / 31.0
    days: list[dict[str, Any]] = []
    cum_rev = cum_cogs = cum_fees = cum_ads = cum_kie = cum_shop = 0.0

    d = start
    while d <= end:
        key = d.isoformat()
        rev = rev_by.get(key, 0.0)
        cogs = cogs_by.get(key, 0.0)
        fees = fees_by.get(key, 0.0)
        ads = spend_by.get(key, 0.0)
        kie_gbp = kie_by.get(key, 0.0)
        kie_cr = kie_cr_by.get(key, 0.0)
        shop = shop_day
        day_var = rev - cogs - fees - ads
        day_pnl = day_var - kie_gbp - shop

        cum_rev += rev
        cum_cogs += cogs
        cum_fees += fees
        cum_ads += ads
        cum_kie += kie_gbp
        cum_shop += shop
        cum_contrib = cum_rev - cum_cogs - cum_fees - cum_ads
        cum_pnl = cum_contrib - cum_kie - cum_shop
        cum_costs = cum_cogs + cum_fees + cum_ads + cum_kie + cum_shop

        days.append(
            {
                "date": key,
                "label": key[5:],  # MM-DD
                "rev": round(rev, 2),
                "cogs": round(cogs, 2),
                "fees": round(fees, 2),
                "ads": round(ads, 2),
                "kie_gbp": round(kie_gbp, 2),
                "kie_credits": round(kie_cr, 2),
                "shopify": round(shop, 2),
                "day_pnl": round(day_pnl, 2),
                "cum_rev": round(cum_rev, 2),
                "cum_ads": round(cum_ads, 2),
                "cum_costs": round(cum_costs, 2),
                "cum_contrib": round(cum_contrib, 2),
                "cum_pnl": round(cum_pnl, 2),
                "orders": orders_by.get(key, 0),
                "attr_rev": round(attr_by.get(key, 0.0), 2),
                "mer3d": None,
            }
        )
        d += timedelta(days=1)

    for i, row in enumerate(days):
        if i < 2:
            continue
        window = days[i - 2 : i + 1]
        w_rev = sum(x["rev"] for x in window)
        w_ads = sum(x["ads"] for x in window)
        row["mer3d"] = round(w_rev / w_ads, 2) if w_ads > 0 else 0.0

    latest = days[-1] if days else None
    totals = {
        "revenue": round(cum_rev, 2),
        "landed_cogs": round(cum_cogs, 2),
        "fees": round(cum_fees, 2),
        "meta_spend": round(cum_ads, 2),
        "kie_gbp": round(cum_kie, 2),
        "shopify_amortised": round(cum_shop, 2),
        "shopify_monthly": shopify_monthly_gbp(),
        "cum_pnl": round(latest["cum_pnl"], 2) if latest else 0.0,
        "mer3d": latest["mer3d"] if latest else None,
        "meta_attr_rev": round(sum(attr_by.values()), 2),
        "orders": sum(orders_by.values()),
    }
    if totals["meta_spend"] > 0:
        totals["store_mer"] = round(totals["revenue"] / totals["meta_spend"], 2)
        totals["meta_roas"] = round(totals["meta_attr_rev"] / totals["meta_spend"], 2)
    else:
        totals["store_mer"] = None
        totals["meta_roas"] = None

    return {
        "assumptions": {
            "fee_pct": fee_p,
            "fee_fixed_gbp": fee_f,
            "shopify_monthly_gbp": shopify_monthly_gbp(),
            "shopify_per_day_gbp": round(shop_day, 4),
            "cogs_source": "Shopify unitCost preferred; CJ fallback prefixes; else £3/unit estimate",
        },
        "days": days,
        "totals": totals,
    }


def build_unit_economics(shopify: dict[str, Any] | None) -> list[dict[str, Any]]:
    """One row per ACTIVE product (cheapest/first variant with cost)."""
    if not shopify:
        return []
    fee_p = fee_pct()
    fee_f = fee_fixed_gbp()
    by_handle: dict[str, dict[str, Any]] = {}
    for row in shopify.get("catalog") or []:
        if (row.get("status") or "").upper() != "ACTIVE":
            continue
        handle = row["handle"]
        if handle in by_handle:
            continue
        sell = float(row["price"])
        cost = row.get("unit_cost")
        if cost is None:
            sku = row.get("sku") or ""
            for prefix, landed in FALLBACK_COGS_PREFIX:
                if sku.startswith(prefix):
                    cost = landed
                    break
        if cost is None:
            continue
        cost = float(cost)
        fees = sell * fee_p + fee_f
        contrib = sell - cost - fees
        margin = contrib / sell if sell else 0
        min_roas = sell / contrib if contrib > 0 else None
        by_handle[handle] = {
            "product": row["product"],
            "handle": handle,
            "sku": row.get("sku"),
            "sell": round(sell, 2),
            "landed": round(cost, 2),
            "fees": round(fees, 2),
            "contrib": round(contrib, 2),
            "margin": round(margin, 3),
            "min_roas": round(min_roas, 2) if min_roas else None,
            "max_cpa": round(contrib, 2) if contrib > 0 else None,
        }
    return sorted(by_handle.values(), key=lambda r: r.get("min_roas") or 999)
