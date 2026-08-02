"""CJ Dropshipping order costs (postage / product) keyed by Shopify order name."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from config import repo_root, resolve_usdgbp

_CJ_SCRIPTS = repo_root() / "shared" / "skills" / "cj-dropshipping" / "scripts"
_CJ_API_PATH = _CJ_SCRIPTS / "lib" / "cj_api.py"


def _load_cj_api():
    """Load CJ API module by path (avoids clash with shopify-store scripts/lib)."""
    if "cj_dropshipping_api" in sys.modules:
        return sys.modules["cj_dropshipping_api"]
    spec = importlib.util.spec_from_file_location("cj_dropshipping_api", _CJ_API_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load CJ API from {_CJ_API_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cj_dropshipping_api"] = mod
    # Ensure sibling imports under cj scripts/lib resolve if needed
    if str(_CJ_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_CJ_SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


def _norm_order_num(value: str | None) -> str:
    s = (value or "").strip()
    if not s:
        return ""
    if not s.startswith("#") and s.isdigit():
        return f"#{s}"
    return s


def collect_cj_orders(*, max_pages: int = 40) -> dict[str, Any]:
    """
    Pull CJ shopping orders and index by Shopify-style order number (#1011).

    postageAmount / productAmount are USD on the CJ side.
    """
    cj_api = _load_cj_api()

    fx = resolve_usdgbp()
    rows = cj_api.list_all_orders(page_size=50, max_pages=max_pages)
    by_order: dict[str, dict[str, Any]] = {}
    postage_missing = 0

    for r in rows:
        key = _norm_order_num(r.get("orderNum"))
        if not key:
            continue
        postage_usd = r.get("postageAmount")
        product_usd = r.get("productAmount")
        try:
            postage_f = float(postage_usd) if postage_usd is not None else None
        except (TypeError, ValueError):
            postage_f = None
        try:
            product_f = float(product_usd) if product_usd is not None else None
        except (TypeError, ValueError):
            product_f = None
        if postage_f is None:
            postage_missing += 1
        by_order[key] = {
            "order_num": key,
            "cj_order_id": r.get("cjOrderId") or r.get("orderId"),
            "status": r.get("orderStatus"),
            "postage_usd": postage_f,
            "product_usd": product_f,
            "order_amount_usd": (
                float(r["orderAmount"]) if r.get("orderAmount") is not None else None
            ),
            "postage_gbp": round(postage_f * fx, 4) if postage_f is not None else None,
            "product_gbp": round(product_f * fx, 4) if product_f is not None else None,
            "country": r.get("shippingCountryCode"),
            "logistic_name": r.get("logisticName"),
            "track_number": r.get("trackNumber"),
            "storage_name": r.get("storageName"),
        }

    return {
        "usdgbp": fx,
        "order_count": len(by_order),
        "postage_missing": postage_missing,
        "by_order_num": by_order,
        "source": "CJ shopping/order/list",
        "note": (
            "CJ postageAmount (USD→GBP) is merchant delivery cost per store order. "
            "Matched to Shopify via orderNum = Shopify order name (#1011)."
        ),
    }


def postage_gbp_for_order(cj: dict[str, Any] | None, order_name: str | None) -> float | None:
    if not cj:
        return None
    key = _norm_order_num(order_name)
    row = (cj.get("by_order_num") or {}).get(key)
    if not row:
        return None
    val = row.get("postage_gbp")
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
