"""Subset P&L: selected SKUs + Meta ad sets, from earliest ad-set start."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from collectors.cj_collector import collect_cj_orders, postage_gbp_for_order
from collectors.meta_collector import daily_insights_for_selection, list_structure
from collectors.shopify_collector import collect_orders_since
from config import fee_fixed_gbp, fee_pct
from pnl import _landed_for_sku, _short_product_name


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Meta: 2026-06-01T12:00:00+0000 or ...Z
    try:
        if "T" in s:
            s2 = s.replace("Z", "+00:00")
            if len(s2) >= 5 and (s2[-5] in "+-" and s2[-3] != ":"):
                # +0000 → +00:00
                s2 = s2[:-2] + ":" + s2[-2:]
            return datetime.fromisoformat(s2).date()
        return date.fromisoformat(s[:10])
    except ValueError:
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            return None


def _resolve_selection(
    *,
    skus: list[str],
    handles: list[str],
    adset_ids: list[str],
    campaign_ids: list[str],
    structure: dict[str, Any],
) -> dict[str, Any]:
    adset_ids_set = {str(x) for x in adset_ids if x}
    campaign_ids_set = {str(x) for x in campaign_ids if x}
    adsets_all = structure.get("adsets") or []

    selected_adsets = [a for a in adsets_all if a.get("id") in adset_ids_set]
    # If campaigns selected without their adsets, include those adsets for start-date only
    # when no adsets picked — but spend still uses campaign-level daily when no adsets.
    if not selected_adsets and campaign_ids_set:
        selected_adsets = [
            a for a in adsets_all if a.get("campaign_id") in campaign_ids_set
        ]

    starts: list[tuple[date, dict[str, Any]]] = []
    for a in selected_adsets:
        d = _parse_iso_date(a.get("start_time") or a.get("created_time"))
        if d:
            starts.append((d, a))

    start_date: date | None = min((d for d, _ in starts), default=None)
    start_source = None
    if start_date is not None:
        # Pick the ad set that defines the start
        for d, a in starts:
            if d == start_date:
                start_source = {
                    "id": a.get("id"),
                    "name": a.get("name"),
                    "start_time": a.get("start_time") or a.get("created_time"),
                }
                break

    return {
        "skus": [s for s in skus if s and str(s).strip()],
        "handles": [h for h in handles if h and str(h).strip()],
        "adset_ids": sorted(adset_ids_set),
        "campaign_ids": sorted(campaign_ids_set),
        "adsets": [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "campaign_name": a.get("campaign_name"),
                "status": a.get("status"),
                "start_time": a.get("start_time") or a.get("created_time"),
            }
            for a in selected_adsets
            if a.get("id") in adset_ids_set
            or (not adset_ids_set and a.get("campaign_id") in campaign_ids_set)
        ],
        "start_date": start_date.isoformat() if start_date else None,
        "start_source": start_source,
    }


def shopify_daily_by_skus(
    *,
    orders_payload: dict[str, Any],
    skus: list[str],
    handles: list[str],
    cj: dict[str, Any] | None = None,
) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    """Daily Shopify rev/COGS/fees for selected SKUs/handles (CJ postage included in COGS)."""
    skus_set = {s.strip().lower() for s in skus if s and s.strip()}
    handles_set = {h.strip().lower() for h in handles if h and h.strip()}
    catalog = orders_payload.get("catalog") or []
    cost_by_sku: dict[str, float] = dict(orders_payload.get("cost_by_sku") or {})
    sku_meta: dict[str, dict[str, Any]] = {}
    for row in catalog:
        sku = (row.get("sku") or "").strip()
        if sku:
            sku_meta[sku.lower()] = row

    if handles_set and not skus_set:
        for row in catalog:
            if (row.get("handle") or "").lower() in handles_set:
                sku = (row.get("sku") or "").strip()
                if sku:
                    skus_set.add(sku.lower())

    match_skus_only = bool(skus)
    fee_p = fee_pct()
    fee_f = fee_fixed_gbp()

    by_day: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "rev": 0.0,
            "cogs": 0.0,
            "postage": 0.0,
            "fees": 0.0,
            "orders": 0.0,
            "units": 0.0,
        }
    )
    order_seen: dict[str, set[str]] = defaultdict(set)
    matched_skus: set[str] = set()
    matched_handles: set[str] = set()
    label_bits: list[str] = []

    for row in catalog:
        h = (row.get("handle") or "").lower()
        s = (row.get("sku") or "").strip()
        if (skus_set and s.lower() in skus_set) or (handles_set and h in handles_set):
            name = _short_product_name(row.get("product"), row.get("handle"))
            if name and name not in label_bits:
                label_bits.append(name)

    for o in orders_payload.get("orders") or []:
        items = list(o.get("items") or [])
        if not items:
            continue
        line_revs = [float(it.get("unit") or 0) * int(it.get("qty") or 0) for it in items]
        sub = sum(line_revs) or 1.0
        order_fee = float(o.get("total") or 0) * fee_p + fee_f
        total_qty = sum(int(it.get("qty") or 0) for it in items) or 1
        order_postage = postage_gbp_for_order(cj, o.get("name")) or 0.0
        day = o.get("date")
        if not day:
            continue
        matched_any = False
        for it, line_rev in zip(items, line_revs):
            sku = (it.get("sku") or "").strip()
            meta = sku_meta.get(sku.lower()) or {}
            handle = (meta.get("handle") or "").lower()
            qty = int(it.get("qty") or 0)
            if qty <= 0:
                continue
            match = False
            if skus_set and sku.lower() in skus_set:
                match = True
            elif (not match_skus_only) and handles_set and handle in handles_set:
                match = True
            if not match:
                continue
            matched_any = True
            landed = _landed_for_sku(sku, qty, cost_by_sku)
            postage_share = order_postage * (qty / total_qty)
            fee_share = order_fee * (line_rev / sub)
            bucket = by_day[day]
            bucket["rev"] += line_rev
            bucket["cogs"] += landed + postage_share
            bucket["postage"] += postage_share
            bucket["fees"] += fee_share
            bucket["units"] += qty
            if sku:
                matched_skus.add(sku)
            if handle:
                matched_handles.add(handle)
        if matched_any:
            name = o.get("name") or ""
            if name not in order_seen[day]:
                order_seen[day].add(name)
                by_day[day]["orders"] += 1

    meta = {
        "label": " · ".join(label_bits) if label_bits else "Selected SKUs",
        "skus": sorted(matched_skus),
        "handles": sorted(matched_handles or handles_set),
        "units": int(sum(b["units"] for b in by_day.values())),
        "orders": int(sum(b["orders"] for b in by_day.values())),
        "revenue": round(sum(b["rev"] for b in by_day.values()), 2),
        "cogs": round(sum(b["cogs"] for b in by_day.values()), 2),
        "postage": round(sum(b["postage"] for b in by_day.values()), 2),
        "fees": round(sum(b["fees"] for b in by_day.values()), 2),
    }
    return by_day, meta


def build_subset_pnl(
    *,
    skus: list[str] | None = None,
    handles: list[str] | None = None,
    adset_ids: list[str] | None = None,
    campaign_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Build a chart-compatible P&L for SKUs + Meta selection from ad-set start."""
    skus = list(skus or [])
    handles = list(handles or [])
    adset_ids = list(adset_ids or [])
    campaign_ids = list(campaign_ids or [])
    warnings: list[str] = []

    if not adset_ids and not campaign_ids:
        raise ValueError("Select at least one Meta ad set (or campaign).")
    if not skus and not handles:
        raise ValueError("Select at least one SKU (or product handle).")

    structure = list_structure()
    selection = _resolve_selection(
        skus=skus,
        handles=handles,
        adset_ids=adset_ids,
        campaign_ids=campaign_ids,
        structure=structure,
    )
    start_s = selection.get("start_date")
    if not start_s:
        # Fallback: use first day with Meta spend (pulled with a wide window)
        warnings.append(
            "Could not read ad set start_time — using first day with Meta spend instead."
        )
        start_s = (datetime.now(timezone.utc).date() - timedelta(days=365)).isoformat()

    today = datetime.now(timezone.utc).date()
    until_s = today.isoformat()

    # Prefer explicit ad sets; otherwise use selected campaigns.
    if selection["adset_ids"]:
        meta = daily_insights_for_selection(
            campaign_ids=[],
            adset_ids=selection["adset_ids"],
            since=start_s,
            until=until_s,
        )
    else:
        meta = daily_insights_for_selection(
            campaign_ids=selection["campaign_ids"],
            adset_ids=[],
            since=start_s,
            until=until_s,
        )

    # If start_time missing, snap to first spend day
    if not selection.get("start_date") and meta.get("days"):
        start_s = meta["days"][0]["date"]
        selection["start_date"] = start_s

    shopify_payload = collect_orders_since(start_s)
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
        skus=selection["skus"],
        handles=selection["handles"],
        cj=cj_part,
    )
    if shop_meta["units"] == 0:
        warnings.append("No matching Shopify line items for the selected SKUs in this window.")

    spend_by = {r["date"]: float(r["spend"]) for r in meta.get("days") or []}
    attr_by = {r["date"]: float(r["attr_rev"]) for r in meta.get("days") or []}

    start = date.fromisoformat(start_s)
    end = today
    days: list[dict[str, Any]] = []
    cum_rev = cum_cogs = cum_fees = cum_ads = 0.0

    d = start
    while d <= end:
        key = d.isoformat()
        bucket = shop_by.get(key) or {}
        rev = float(bucket.get("rev") or 0)
        cogs = float(bucket.get("cogs") or 0)
        fees = float(bucket.get("fees") or 0)
        ads = float(spend_by.get(key) or 0)
        day_var = rev - cogs - fees - ads
        # Subset view: product economics vs selected ads (no KIE / Shopify amort)
        day_pnl = day_var

        cum_rev += rev
        cum_cogs += cogs
        cum_fees += fees
        cum_ads += ads
        cum_contrib = cum_rev - cum_cogs - cum_fees - cum_ads
        cum_pnl = cum_contrib
        cum_costs = cum_cogs + cum_fees + cum_ads

        days.append(
            {
                "date": key,
                "label": key[5:],
                "rev": round(rev, 2),
                "cogs": round(cogs, 2),
                "fees": round(fees, 2),
                "ads": round(ads, 2),
                "kie_gbp": 0.0,
                "kie_credits": 0.0,
                "shopify": 0.0,
                "day_pnl": round(day_pnl, 2),
                "cum_rev": round(cum_rev, 2),
                "cum_ads": round(cum_ads, 2),
                "cum_costs": round(cum_costs, 2),
                "cum_contrib": round(cum_contrib, 2),
                "cum_pnl": round(cum_pnl, 2),
                "orders": int(bucket.get("orders") or 0),
                "attr_rev": round(float(attr_by.get(key) or 0), 2),
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
        "kie_gbp": 0.0,
        "shopify_amortised": 0.0,
        "cum_pnl": round(latest["cum_pnl"], 2) if latest else 0.0,
        "mer3d": latest["mer3d"] if latest else None,
        "meta_attr_rev": round(sum(attr_by.values()), 2),
        "orders": shop_meta["orders"],
        "units": shop_meta["units"],
        "store_mer": round(cum_rev / cum_ads, 2) if cum_ads > 0 else None,
        "meta_roas": round(sum(attr_by.values()) / cum_ads, 2) if cum_ads > 0 else None,
    }

    return {
        "selection": selection,
        "label": shop_meta["label"],
        "start_date": start_s,
        "end_date": until_s,
        "days": days,
        "totals": totals,
        "shopify": shop_meta,
        "meta": {
            "total_spend": meta.get("total_spend"),
            "total_attr_rev": meta.get("total_attr_rev"),
            "currency": meta.get("currency"),
        },
        "note": (
            f"Subset P&L from {start_s} (earliest selected ad set start) through {until_s}. "
            "Revenue/COGS/fees = selected SKUs only (COGS includes CJ postageAmount); "
            "ads = selected Meta objects. KIE and Shopify plan amortisation omitted."
        ),
        "warnings": warnings,
    }
