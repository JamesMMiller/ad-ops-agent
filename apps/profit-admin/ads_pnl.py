"""Combine Meta Ads performance with Shopify P&L (SKU or whole-store)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from collectors.cj_collector import collect_cj_orders, postage_gbp_for_order
from collectors.meta_collector import ads_performance_report
from collectors.shopify_collector import collect_orders_since
from config import fee_fixed_gbp, fee_pct, shopify_monthly_gbp
from pnl import _landed_for_sku
from snapshots import read_latest
from subset_pnl import shopify_daily_by_skus


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _resolve_window(meta: dict[str, Any]) -> tuple[str, str]:
    until = (meta.get("until") or _today().isoformat())[:10]
    since = meta.get("since")
    if since:
        return str(since)[:10], until
    days = meta.get("days") or []
    if days:
        return str(days[0]["date"])[:10], until
    # Fallback label window
    start = (_today() - timedelta(days=29)).isoformat()
    return start, until


def _fill_mer3d(days: list[dict[str, Any]]) -> None:
    for i, row in enumerate(days):
        if i < 2:
            row["mer3d"] = None
            continue
        window = days[i - 2 : i + 1]
        w_rev = sum(x["rev"] for x in window)
        w_ads = sum(x["ads"] for x in window)
        row["mer3d"] = round(w_rev / w_ads, 2) if w_ads > 0 else 0.0


def _join_pnl_days(
    *,
    start: str,
    end: str,
    shop_by: dict[str, dict[str, float]],
    meta_days: list[dict[str, Any]],
    include_kie_shop: bool,
) -> list[dict[str, Any]]:
    spend_by = {r["date"]: float(r.get("spend") or 0) for r in meta_days}
    attr_by = {r["date"]: float(r.get("attr_rev") or 0) for r in meta_days}
    purch_by = {r["date"]: float(r.get("purchases") or 0) for r in meta_days}

    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    days: list[dict[str, Any]] = []
    cum_rev = cum_cogs = cum_fees = cum_ads = cum_kie = cum_shop = 0.0
    shop_day = shopify_monthly_gbp() / 31.0 if include_kie_shop else 0.0

    d = start_d
    while d <= end_d:
        key = d.isoformat()
        bucket = shop_by.get(key) or {}
        rev = float(bucket.get("rev") or 0)
        cogs = float(bucket.get("cogs") or 0)
        fees = float(bucket.get("fees") or 0)
        ads = float(spend_by.get(key) or 0)
        if include_kie_shop:
            kie_gbp = float(bucket.get("kie_gbp") or 0)
            shop = float(bucket["shopify"]) if "shopify" in bucket else shop_day
        else:
            kie_gbp = 0.0
            shop = 0.0
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
                "label": key[5:],
                "rev": round(rev, 2),
                "cogs": round(cogs, 2),
                "fees": round(fees, 2),
                "ads": round(ads, 2),
                "kie_gbp": round(kie_gbp, 2),
                "kie_credits": float(bucket.get("kie_credits") or 0) if include_kie_shop else 0.0,
                "shopify": round(shop, 2),
                "day_pnl": round(day_pnl, 2),
                "cum_rev": round(cum_rev, 2),
                "cum_ads": round(cum_ads, 2),
                "cum_costs": round(cum_costs, 2),
                "cum_contrib": round(cum_contrib, 2),
                "cum_pnl": round(cum_pnl, 2),
                "orders": int(bucket.get("orders") or 0),
                "attr_rev": round(float(attr_by.get(key) or 0), 2),
                "purchases": round(float(purch_by.get(key) or 0), 2),
                "mer3d": None,
            }
        )
        d += timedelta(days=1)

    _fill_mer3d(days)
    return days


def _pnl_totals(days: list[dict[str, Any]], *, meta_attr_rev: float, orders: int, units: int | None = None) -> dict[str, Any]:
    latest = days[-1] if days else None
    cum_ads = float(latest["cum_ads"]) if latest else 0.0
    cum_rev = float(latest["cum_rev"]) if latest else 0.0
    totals = {
        "revenue": round(cum_rev, 2),
        "landed_cogs": round(sum(d["cogs"] for d in days), 2),
        "fees": round(sum(d["fees"] for d in days), 2),
        "meta_spend": round(cum_ads, 2),
        "kie_gbp": round(sum(d["kie_gbp"] for d in days), 2),
        "shopify_amortised": round(sum(d["shopify"] for d in days), 2),
        "cum_pnl": round(latest["cum_pnl"], 2) if latest else 0.0,
        "mer3d": latest["mer3d"] if latest else None,
        "meta_attr_rev": round(meta_attr_rev, 2),
        "orders": orders,
        "store_mer": round(cum_rev / cum_ads, 2) if cum_ads > 0 else None,
        "meta_roas": round(meta_attr_rev / cum_ads, 2) if cum_ads > 0 else None,
    }
    if units is not None:
        totals["units"] = units
    return totals


def _shop_by_from_snapshot(snapshot: dict[str, Any], since: str, until: str) -> dict[str, dict[str, float]] | None:
    pnl = snapshot.get("pnl") or {}
    days = pnl.get("days") or []
    if not days:
        return None
    out: dict[str, dict[str, float]] = {}
    for row in days:
        key = row.get("date")
        if not key or key < since or key > until:
            continue
        out[key] = {
            "rev": float(row.get("rev") or 0),
            "cogs": float(row.get("cogs") or 0),
            "fees": float(row.get("fees") or 0),
            "kie_gbp": float(row.get("kie_gbp") or 0),
            "kie_credits": float(row.get("kie_credits") or 0),
            "shopify": float(row.get("shopify") or 0),
            "orders": float(row.get("orders") or 0),
        }
    return out if out else None


def _shop_by_from_orders(orders_payload: dict[str, Any], cj: dict[str, Any] | None) -> dict[str, dict[str, float]]:
    cost_by_sku: dict[str, float] = dict(orders_payload.get("cost_by_sku") or {})
    fee_p = fee_pct()
    fee_f = fee_fixed_gbp()
    by_day: dict[str, dict[str, float]] = defaultdict(
        lambda: {"rev": 0.0, "cogs": 0.0, "fees": 0.0, "orders": 0.0}
    )
    for o in orders_payload.get("orders") or []:
        day = o.get("date")
        if not day:
            continue
        total = float(o.get("total") or 0)
        by_day[day]["rev"] += total
        by_day[day]["orders"] += 1
        by_day[day]["fees"] += total * fee_p + fee_f
        for it in o.get("items") or []:
            by_day[day]["cogs"] += _landed_for_sku(
                it.get("sku") or "", int(it.get("qty") or 0), cost_by_sku
            )
        postage = postage_gbp_for_order(cj, o.get("name"))
        if postage:
            by_day[day]["cogs"] += postage
    return by_day


def _build_sku_pnl(
    *,
    since: str,
    until: str,
    meta_days: list[dict[str, Any]],
    skus: list[str],
    handles: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    shopify_payload = collect_orders_since(since)
    if shopify_payload.get("truncated"):
        warnings.append(
            "Shopify order history was truncated at the page limit — early days may be incomplete."
        )
    cj_part: dict[str, Any] | None = None
    try:
        cj_part = collect_cj_orders()
    except Exception as e:
        warnings.append(f"CJ postage lookup failed: {e}")

    shop_by, shop_meta = shopify_daily_by_skus(
        orders_payload=shopify_payload,
        skus=skus,
        handles=handles,
        cj=cj_part,
    )
    if shop_meta["units"] == 0:
        warnings.append("No matching Shopify line items for the selected SKUs in this window.")

    days = _join_pnl_days(
        start=since,
        end=until,
        shop_by=shop_by,
        meta_days=meta_days,
        include_kie_shop=False,
    )
    attr = sum(float(d.get("attr_rev") or 0) for d in meta_days)
    totals = _pnl_totals(
        days,
        meta_attr_rev=attr,
        orders=shop_meta["orders"],
        units=shop_meta["units"],
    )
    return {
        "mode": "sku",
        "label": shop_meta["label"],
        "note": (
            f"SKU P&L {since} → {until}. Revenue/COGS/fees = selected SKUs "
            "(COGS includes CJ postageAmount); ads = selected Meta objects. "
            "KIE and Shopify plan amortisation omitted."
        ),
        "source": "live_orders",
        "days": days,
        "totals": totals,
        "shopify": shop_meta,
    }


def _build_store_pnl(
    *,
    since: str,
    until: str,
    meta_days: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    snapshot = read_latest()
    shop_by = _shop_by_from_snapshot(snapshot, since, until) if snapshot else None
    source = "snapshot"
    if shop_by is None:
        source = "live_orders"
        warnings.append(
            "No Refresh snapshot covering this window — building store P&L from live Shopify orders "
            "(KIE/Shopify amortisation estimated per day)."
        )
        shopify_payload = collect_orders_since(since)
        if shopify_payload.get("truncated"):
            warnings.append(
                "Shopify order history was truncated at the page limit — early days may be incomplete."
            )
        cj_part: dict[str, Any] | None = None
        try:
            cj_part = collect_cj_orders()
        except Exception as e:
            warnings.append(f"CJ postage lookup failed: {e}")
        shop_by = _shop_by_from_orders(shopify_payload, cj_part)

    days = _join_pnl_days(
        start=since,
        end=until,
        shop_by=shop_by,
        meta_days=meta_days,
        include_kie_shop=True,
    )
    attr = sum(float(d.get("attr_rev") or 0) for d in meta_days)
    orders = int(sum(d.get("orders") or 0 for d in days))
    totals = _pnl_totals(days, meta_attr_rev=attr, orders=orders)
    note = (
        f"Store P&L {since} → {until}. Whole-store revenue/COGS/fees"
        + (" + KIE + Shopify amortisation from latest Refresh snapshot" if source == "snapshot" else " + estimated KIE/Shopify amortisation")
        + "; ads = selected Meta objects only (not full account spend)."
    )
    return {
        "mode": "store",
        "label": "Whole store",
        "note": note,
        "source": source,
        "days": days,
        "totals": totals,
        "shopify": None,
    }


def build_ads_performance_with_pnl(
    *,
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
    ad_ids: list[str] | None = None,
    skus: list[str] | None = None,
    handles: list[str] | None = None,
    date_preset: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, Any]:
    """Meta Ads report + profitability (SKU if products picked, else whole store)."""
    skus = [str(s).strip() for s in (skus or []) if s and str(s).strip()]
    handles = [str(h).strip() for h in (handles or []) if h and str(h).strip()]

    meta = ads_performance_report(
        campaign_ids=campaign_ids,
        adset_ids=adset_ids,
        ad_ids=ad_ids,
        date_preset=date_preset,
        since=since,
        until=until,
    )

    warnings: list[str] = []
    if meta.get("warning"):
        warnings.append(str(meta["warning"]))

    # No Meta selection — return Meta envelope with empty pnl
    if not (meta.get("campaign_ids") or meta.get("adset_ids") or meta.get("ad_ids")):
        return {
            **meta,
            "pnl_mode": "store" if not (skus or handles) else "sku",
            "pnl": None,
            "skus": skus,
            "handles": handles,
            "warnings": warnings,
        }

    win_since, win_until = _resolve_window(meta)
    # Persist resolved window on the report for UI/PDF
    meta = {**meta, "since": win_since, "until": win_until}

    meta_days = list(meta.get("days") or [])
    if skus or handles:
        pnl = _build_sku_pnl(
            since=win_since,
            until=win_until,
            meta_days=meta_days,
            skus=skus,
            handles=handles,
            warnings=warnings,
        )
    else:
        pnl = _build_store_pnl(
            since=win_since,
            until=win_until,
            meta_days=meta_days,
            warnings=warnings,
        )

    return {
        **meta,
        "pnl_mode": pnl["mode"],
        "pnl": {
            "totals": pnl["totals"],
            "days": pnl["days"],
            "label": pnl["label"],
            "note": pnl["note"],
            "source": pnl["source"],
            "shopify": pnl.get("shopify"),
        },
        "skus": skus,
        "handles": handles,
        "warnings": warnings,
    }
