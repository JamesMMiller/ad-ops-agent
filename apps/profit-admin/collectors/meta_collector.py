"""Meta Ads daily insights collector."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen
import json


def _act() -> str:
    act = (os.environ.get("META_AD_ACCOUNT_ID") or "").strip()
    if not act:
        raise RuntimeError("META_AD_ACCOUNT_ID not set")
    if not act.startswith("act_"):
        act = f"act_{act}"
    return act


def _token() -> str:
    tok = (os.environ.get("META_ACCESS_TOKEN") or "").strip()
    if not tok:
        raise RuntimeError("META_ACCESS_TOKEN not set")
    return tok


def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    ver = os.environ.get("META_API_VERSION", "v25.0")
    params = {**params, "access_token": _token()}
    url = f"https://graph.facebook.com/{ver}/{path}?{urlencode(params)}"
    with urlopen(url, timeout=60) as resp:
        return json.load(resp)


def collect_meta() -> dict[str, Any]:
    act = _act()
    acct = _get(
        act,
        {"fields": "name,currency,timezone_name,amount_spent,account_status"},
    )
    data = _get(
        f"{act}/insights",
        {
            "time_increment": 1,
            "date_preset": "maximum",
            "fields": "spend,impressions,clicks,actions,action_values,purchase_roas,account_currency",
            "level": "account",
        },
    )

    days: list[dict[str, Any]] = []
    for row in data.get("data") or []:
        spend = float(row.get("spend") or 0)
        purch = 0.0
        rev = 0.0
        for a in row.get("actions") or []:
            if a.get("action_type") in ("purchase", "omni_purchase"):
                purch = max(purch, float(a.get("value") or 0))
        for a in row.get("action_values") or []:
            if a.get("action_type") in (
                "purchase",
                "omni_purchase",
                "offsite_conversion.fb_pixel_purchase",
            ):
                rev = max(rev, float(a.get("value") or 0))
        days.append(
            {
                "date": row["date_start"],
                "spend": spend,
                "purchases": purch,
                "attr_rev": rev,
                "currency": row.get("account_currency") or acct.get("currency"),
            }
        )

    days.sort(key=lambda d: d["date"])
    total_spend = sum(d["spend"] for d in days)
    total_attr = sum(d["attr_rev"] for d in days)
    return {
        "account": {
            "id": act,
            "name": acct.get("name"),
            "currency": acct.get("currency"),
            "timezone": acct.get("timezone_name"),
        },
        "days": days,
        "total_spend": round(total_spend, 2),
        "total_attr_rev": round(total_attr, 2),
    }
