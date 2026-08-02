"""Orchestrate collectors → P&L → snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from collectors import cj_collector, kie_collector, meta_collector, shopify_collector
from config import resolve_usdgbp
from pnl import build_pnl, build_product_pnl, build_unit_economics
from snapshots import write_snapshot


def run_refresh() -> dict[str, Any]:
    warnings: list[str] = []
    errors: dict[str, str] = {}
    usdgbp = resolve_usdgbp()

    shopify: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    kie: dict[str, Any] | None = None
    cj: dict[str, Any] | None = None

    try:
        shopify = shopify_collector.collect_shopify()
    except Exception as e:
        errors["shopify"] = str(e)
        warnings.append(f"Shopify failed: {e}")

    try:
        meta = meta_collector.collect_meta()
    except Exception as e:
        errors["meta"] = str(e)
        warnings.append(f"Meta failed: {e}")

    try:
        kie = kie_collector.collect_kie(usdgbp=usdgbp)
        if not kie.get("log_exists"):
            warnings.append("KIE log missing — creative spend will be £0 until generations are logged")
    except Exception as e:
        errors["kie"] = str(e)
        warnings.append(f"KIE failed: {e}")

    try:
        cj = cj_collector.collect_cj_orders()
        if not cj.get("order_count"):
            warnings.append("CJ returned no orders — delivery postage in COGS will be £0")
    except Exception as e:
        errors["cj"] = str(e)
        warnings.append(f"CJ postage failed: {e}")

    pnl = build_pnl(shopify=shopify, meta=meta, kie=kie, cj=cj)
    units = build_unit_economics(shopify)
    by_product = build_product_pnl(shopify, cj=cj)

    payload: dict[str, Any] = {
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "usdgbp": usdgbp,
        "warnings": warnings,
        "errors": errors,
        "sources": {
            "shopify": shopify,
            "meta": meta,
            "kie": kie,
            "cj": {
                "order_count": (cj or {}).get("order_count"),
                "postage_missing": (cj or {}).get("postage_missing"),
                "usdgbp": (cj or {}).get("usdgbp"),
                "note": (cj or {}).get("note"),
                # Keep full map for re-renders / dig-in without a second CJ pull
                "by_order_num": (cj or {}).get("by_order_num"),
            }
            if cj
            else None,
        },
        "pnl": pnl,
        "unit_economics": units,
        "product_pnl": by_product,
    }
    return write_snapshot(payload)
