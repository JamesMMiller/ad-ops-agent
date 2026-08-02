"""Historic Shopify sales + Meta spend for warehouse planner comparison."""

from __future__ import annotations

from typing import Any

from collectors.cj_collector import collect_cj_orders, postage_gbp_for_order
from collectors.meta_collector import insights_for_selection
from collectors.shopify_collector import collect_shopify
from config import fee_fixed_gbp, fee_pct
from pnl import _landed_for_sku, _short_product_name


def _shopify_product_history(
    *,
    handles: list[str],
    skus: list[str],
    cj: dict[str, Any] | None = None,
) -> dict[str, Any]:
    handles_set = {h.strip().lower() for h in handles if h and h.strip()}
    skus_set = {s.strip().lower() for s in skus if s and s.strip()}

    shopify = collect_shopify()
    cost_by_sku: dict[str, float] = dict(shopify.get("cost_by_sku") or {})
    sku_meta: dict[str, dict[str, Any]] = {}
    for row in shopify.get("catalog") or []:
        sku = (row.get("sku") or "").strip()
        if sku:
            sku_meta[sku.lower()] = row
            sku_meta[sku] = row

    # If only handle(s) given (no explicit SKUs), include all skus for those handles
    if handles_set and not skus_set:
        for row in shopify.get("catalog") or []:
            if (row.get("handle") or "").lower() in handles_set:
                sku = (row.get("sku") or "").strip()
                if sku:
                    skus_set.add(sku.lower())

    # When specific SKUs are selected, match those only (don't expand via handle)
    match_skus_only = bool(skus)

    fee_p = fee_pct()
    fee_f = fee_fixed_gbp()

    units = 0
    revenue = 0.0
    product_cogs = 0.0
    postage = 0.0
    fees = 0.0
    order_names: set[str] = set()
    lines: list[dict[str, Any]] = []
    matched_handles: set[str] = set()
    matched_skus: set[str] = set()
    postage_matched_orders = 0
    postage_missing_orders = 0

    for o in shopify.get("orders") or []:
        items = list(o.get("items") or [])
        if not items:
            continue
        line_revs = [float(it.get("unit") or 0) * int(it.get("qty") or 0) for it in items]
        sub = sum(line_revs) or 1.0
        order_fee = float(o.get("total") or 0) * fee_p + fee_f
        total_qty = sum(int(it.get("qty") or 0) for it in items) or 1
        order_postage = postage_gbp_for_order(cj, o.get("name"))

        matched_lines: list[tuple[dict[str, Any], float, dict[str, Any], int]] = []
        for it, line_rev in zip(items, line_revs):
            sku = (it.get("sku") or "").strip()
            meta = sku_meta.get(sku.lower()) or sku_meta.get(sku) or {}
            handle = (meta.get("handle") or "").lower()
            title = it.get("title") or meta.get("product") or "Unknown"
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
            matched_lines.append((it, line_rev, meta, qty))

        if not matched_lines:
            continue

        if order_postage is not None:
            postage_matched_orders += 1
        else:
            postage_missing_orders += 1
            order_postage = 0.0

        for it, line_rev, meta, qty in matched_lines:
            sku = (it.get("sku") or "").strip()
            handle = (meta.get("handle") or "").lower()
            title = it.get("title") or meta.get("product") or "Unknown"
            landed = _landed_for_sku(sku, qty, cost_by_sku)
            # Allocate CJ order postage by unit share of the whole order
            postage_share = order_postage * (qty / total_qty)
            fee_share = order_fee * (line_rev / sub)
            line_cogs = landed + postage_share
            units += qty
            revenue += line_rev
            product_cogs += landed
            postage += postage_share
            fees += fee_share
            order_names.add(o.get("name") or "")
            if handle:
                matched_handles.add(handle)
            if sku:
                matched_skus.add(sku)
            lines.append(
                {
                    "order": o.get("name"),
                    "date": o.get("date"),
                    "sku": sku or "—",
                    "variant": meta.get("variant") or "—",
                    "product": _short_product_name(
                        meta.get("product") or title, meta.get("handle")
                    ),
                    "qty": qty,
                    "revenue": round(line_rev, 2),
                    "product_cogs": round(landed, 2),
                    "postage": round(postage_share, 2),
                    "cogs": round(line_cogs, 2),
                    "fees": round(fee_share, 2),
                    "contrib": round(line_rev - line_cogs - fee_share, 2),
                }
            )

    cogs = product_cogs + postage
    contrib = revenue - cogs - fees
    margin = contrib / revenue if revenue else None
    label_bits = []
    for row in shopify.get("catalog") or []:
        h = (row.get("handle") or "").lower()
        s = (row.get("sku") or "").strip()
        if (handles_set and h in handles_set) or (s and s.lower() in skus_set):
            name = _short_product_name(row.get("product"), row.get("handle"))
            if name and name not in label_bits:
                label_bits.append(name)

    return {
        "label": " · ".join(label_bits) if label_bits else "Selected products",
        "handles": sorted(matched_handles or handles_set),
        "skus": sorted(matched_skus or skus_set),
        "units": units,
        "orders": len([n for n in order_names if n]),
        "revenue": round(revenue, 2),
        "product_cogs": round(product_cogs, 2),
        "postage": round(postage, 2),
        "cogs": round(cogs, 2),
        "fees": round(fees, 2),
        "contrib": round(contrib, 2),
        "margin": round(margin, 4) if margin is not None else None,
        "avg_unit_revenue": round(revenue / units, 2) if units else None,
        "avg_unit_product_cogs": round(product_cogs / units, 2) if units else None,
        "avg_unit_postage": round(postage / units, 2) if units else None,
        "avg_unit_cogs": round(cogs / units, 2) if units else None,
        "postage_orders_matched": postage_matched_orders,
        "postage_orders_missing": postage_missing_orders,
        "lines": sorted(lines, key=lambda r: (r.get("date") or "", r.get("order") or ""), reverse=True)[
            :40
        ],
        "currency": (shopify.get("shop") or {}).get("currency") or "GBP",
        "note": (
            "Shopify paid orders (last 100 pulled). "
            "Landed COGS = product unitCost + CJ postageAmount (USD→GBP) allocated by units. "
            "Contribution = revenue − landed COGS − checkout fee share."
        ),
    }


def build_past_performance(
    *,
    handles: list[str] | None = None,
    skus: list[str] | None = None,
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
    date_preset: str = "maximum",
) -> dict[str, Any]:
    handles = handles or []
    skus = skus or []
    warnings: list[str] = []

    shopify_part: dict[str, Any] | None = None
    meta_part: dict[str, Any] | None = None
    cj_part: dict[str, Any] | None = None

    try:
        cj_part = collect_cj_orders()
        if cj_part.get("order_count", 0) == 0:
            warnings.append("CJ returned no orders — historic postage will be £0.")
    except Exception as e:
        warnings.append(f"CJ postage lookup failed: {e}")
        cj_part = None

    if handles or skus:
        try:
            shopify_part = _shopify_product_history(handles=handles, skus=skus, cj=cj_part)
            if shopify_part["units"] == 0:
                warnings.append(
                    "No paid Shopify orders matched the selected product/SKU in the recent order pull."
                )
            elif shopify_part.get("postage_orders_missing", 0):
                warnings.append(
                    f"CJ postage missing for {shopify_part['postage_orders_missing']} matched "
                    "Shopify order(s) — treated as £0 delivery."
                )
        except Exception as e:
            warnings.append(f"Shopify history failed: {e}")
            shopify_part = None
    else:
        warnings.append("No product/SKU selected — Shopify history skipped.")

    if campaign_ids or adset_ids:
        try:
            meta_part = insights_for_selection(
                campaign_ids=campaign_ids,
                adset_ids=adset_ids,
                date_preset=date_preset,
            )
            if meta_part.get("warning"):
                warnings.append(str(meta_part["warning"]))
            if meta_part["spend"] <= 0 and not meta_part.get("warning"):
                warnings.append("Selected Meta objects have £0 spend in this date range.")
        except Exception as e:
            warnings.append(f"Meta insights failed: {e}")
            meta_part = None
    else:
        warnings.append("No campaigns/ad sets selected — Meta spend skipped.")

    combined: dict[str, Any] = {}
    summary: dict[str, Any] | None = None

    if shopify_part and shopify_part.get("units", 0) > 0:
        rev = float(shopify_part["revenue"])
        cogs = float(shopify_part["cogs"])
        postage = float(shopify_part.get("postage") or 0)
        product_cogs = float(shopify_part.get("product_cogs") or (cogs - postage))
        fees = float(shopify_part["fees"])
        units = float(shopify_part["units"])
        contrib_ex_ads = rev - cogs - fees  # same as planner contribution before ads
        spend = float((meta_part or {}).get("spend") or 0)

        avg_sell = rev / units
        landed_cogs = cogs / units
        fee_per_unit = fees / units
        ads_per_unit = spend / units if units else 0.0
        contrib_unit = avg_sell - landed_cogs - fee_per_unit
        contrib_after_ads = contrib_unit - ads_per_unit
        margin = contrib_unit / avg_sell if avg_sell else None
        margin_after_ads = contrib_after_ads / avg_sell if avg_sell else None

        overall_pnl = contrib_ex_ads - spend  # revenue − COGS (incl postage) − fees − ads
        roas = (rev / spend) if spend > 0 else None
        roas_after_cogs = (contrib_ex_ads / spend) if spend > 0 else None
        poas = (overall_pnl / spend) if spend > 0 else None
        net_margin = (overall_pnl / rev) if rev > 0 else None

        # Mirror planner KPI / unit_economics field names so UI can reuse the same labels
        summary = {
            "label": shopify_part.get("label") or "Historic",
            "source_note": (
                "Historic mirror of planner KPIs: Shopify revenue + product COGS + CJ delivery "
                "(postageAmount) + checkout fees"
                + (
                    " + Meta spend from selected campaigns/ad sets."
                    if spend > 0
                    else " (no Meta spend selected)."
                )
            ),
            "revenue_gbp": round(rev, 2),
            "ads_gbp": round(spend, 2),
            "units_sold": round(units, 2),
            "product_cogs_gbp": round(product_cogs, 2),
            "postage_gbp": round(postage, 2),
            "overall_pnl": {
                "profit_gbp": round(overall_pnl, 2),
                "is_profit": overall_pnl >= 0,
                "roas": round(roas, 2) if roas is not None else None,
                "roas_after_cogs": round(roas_after_cogs, 2) if roas_after_cogs is not None else None,
                "poas": round(poas, 2) if poas is not None else None,
                "net_margin": round(net_margin, 4) if net_margin is not None else None,
            },
            "totals": {
                "revenue_gbp": round(rev, 2),
                "ads_gbp": round(spend, 2),
                "units_sold": round(units, 2),
                "product_cogs_gbp": round(product_cogs, 2),
                "postage_gbp": round(postage, 2),
                "roas": round(roas, 2) if roas is not None else None,
                "roas_after_cogs": round(roas_after_cogs, 2) if roas_after_cogs is not None else None,
                "poas": round(poas, 2) if poas is not None else None,
                "net_margin": round(net_margin, 4) if net_margin is not None else None,
            },
            "unit_economics": {
                "sell_price_gbp": round(avg_sell, 4),
                "product_cost_gbp": round(product_cogs / units, 4),
                "postage_gbp": round(postage / units, 4),
                "landed_cogs_gbp": round(landed_cogs, 4),
                "checkout_fee_gbp": round(fee_per_unit, 4),
                "ads_alloc_gbp": round(ads_per_unit, 4),
                "contribution_gbp": round(contrib_unit, 4),
                "margin": round(margin, 4) if margin is not None else None,
                "contribution_after_ads_gbp": round(contrib_after_ads, 4),
                "margin_after_ads": (
                    round(margin_after_ads, 4) if margin_after_ads is not None else None
                ),
                "roas": round(roas, 2) if roas is not None else None,
                "roas_after_cogs": (
                    round(roas_after_cogs, 2) if roas_after_cogs is not None else None
                ),
                "poas": round(poas, 2) if poas is not None else None,
            },
            "formulas": {
                "roas": "revenue ÷ ads",
                "roas_after_cogs": "contribution before ads ÷ ads (product COGS + CJ postage + fees)",
                "poas": "profit ÷ ads",
                "margin_inc_ads": "contrib after ads ÷ avg sell price",
                "overall_pnl": "revenue − product COGS − CJ postage − checkout fees − ads",
                "landed_cogs": "Shopify unitCost + CJ postageAmount (allocated by units)",
            },
        }

        if spend > 0:
            combined = {
                "shopify_roas": summary["totals"]["roas"],
                "roas_after_cogs": summary["totals"]["roas_after_cogs"],
                "poas": summary["totals"]["poas"],
                "cpa_shopify_units": round(spend / units, 2),
                "meta_cpa": (meta_part or {}).get("cpa"),
                "meta_roas": (meta_part or {}).get("roas"),
                "avg_postage_per_unit": round(postage / units, 2),
                "note": (
                    "Same KPI math as the planner: ROAS = Shopify revenue ÷ Meta ads; "
                    "ROAS (after COGS) = (revenue − product COGS − CJ postage − fees) ÷ ads; "
                    "Margin (inc ads) / Contrib after ads use Meta spend ÷ units as ads/unit."
                ),
            }

    return {
        "shopify": shopify_part,
        "meta": meta_part,
        "cj": {
            "order_count": (cj_part or {}).get("order_count"),
            "postage_missing": (cj_part or {}).get("postage_missing"),
            "usdgbp": (cj_part or {}).get("usdgbp"),
            "note": (cj_part or {}).get("note"),
        }
        if cj_part
        else None,
        "combined": combined,
        "summary": summary,
        "warnings": warnings,
        "date_preset": date_preset,
    }
