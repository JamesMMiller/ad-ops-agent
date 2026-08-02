"""Meta Ads daily insights collector."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen


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
    try:
        with urlopen(url, timeout=90) as resp:
            return json.load(resp)
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Meta API {e.code}: {body[:500]}") from e


def _get_all(path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Paginate Graph API list endpoints."""
    out: list[dict[str, Any]] = []
    data = _get(path, params)
    out.extend(data.get("data") or [])
    while data.get("paging", {}).get("next"):
        next_url = data["paging"]["next"]
        with urlopen(next_url, timeout=90) as resp:
            data = json.load(resp)
        out.extend(data.get("data") or [])
    return out


def _purchases_revenue(row: dict[str, Any]) -> tuple[float, float]:
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
    return purch, rev


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
        purch, rev = _purchases_revenue(row)
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


def list_structure() -> dict[str, Any]:
    """Campaigns + ad sets + ads for historic-spend / Ads performance pickers."""
    act = _act()
    campaigns = _get_all(
        f"{act}/campaigns",
        {
            "fields": "id,name,status,effective_status,objective",
            "limit": 100,
        },
    )
    adsets = _get_all(
        f"{act}/adsets",
        {
            "fields": (
                "id,name,status,effective_status,campaign_id,"
                "daily_budget,lifetime_budget,start_time,created_time"
            ),
            "limit": 100,
        },
    )
    ads = _get_all(
        f"{act}/ads",
        {
            "fields": "id,name,status,effective_status,adset_id,campaign_id",
            "limit": 100,
        },
    )
    camp_by_id = {c["id"]: c for c in campaigns}
    adset_by_id = {a["id"]: a for a in adsets}
    adset_rows = []
    for a in adsets:
        camp = camp_by_id.get(a.get("campaign_id") or "", {})
        adset_rows.append(
            {
                "id": a["id"],
                "name": a.get("name") or a["id"],
                "status": a.get("effective_status") or a.get("status"),
                "campaign_id": a.get("campaign_id"),
                "campaign_name": camp.get("name"),
                "start_time": a.get("start_time") or a.get("created_time"),
                "created_time": a.get("created_time"),
            }
        )
    adset_rows.sort(key=lambda r: ((r.get("campaign_name") or ""), r["name"]))
    campaign_rows = [
        {
            "id": c["id"],
            "name": c.get("name") or c["id"],
            "status": c.get("effective_status") or c.get("status"),
            "objective": c.get("objective"),
        }
        for c in campaigns
    ]
    campaign_rows.sort(key=lambda r: r["name"])
    ad_rows = []
    for ad in ads:
        camp = camp_by_id.get(ad.get("campaign_id") or "", {})
        adset = adset_by_id.get(ad.get("adset_id") or "", {})
        ad_rows.append(
            {
                "id": ad["id"],
                "name": ad.get("name") or ad["id"],
                "status": ad.get("effective_status") or ad.get("status"),
                "adset_id": ad.get("adset_id"),
                "adset_name": adset.get("name"),
                "campaign_id": ad.get("campaign_id"),
                "campaign_name": camp.get("name"),
            }
        )
    ad_rows.sort(
        key=lambda r: (
            (r.get("campaign_name") or ""),
            (r.get("adset_name") or ""),
            r["name"],
        )
    )
    return {
        "account_id": act,
        "campaigns": campaign_rows,
        "adsets": adset_rows,
        "ads": ad_rows,
    }


def insights_for_selection(
    *,
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
    date_preset: str = "maximum",
) -> dict[str, Any]:
    """Aggregate Meta insights for selected campaigns and/or ad sets."""
    campaign_ids = [str(x) for x in (campaign_ids or []) if x]
    adset_ids = [str(x) for x in (adset_ids or []) if x]
    if not campaign_ids and not adset_ids:
        return {
            "spend": 0.0,
            "purchases": 0.0,
            "attr_rev": 0.0,
            "impressions": 0,
            "clicks": 0,
            "cpa": None,
            "roas": None,
            "by_object": [],
            "date_preset": date_preset,
            "warning": "No campaigns or ad sets selected.",
        }

    act = _act()
    fields = (
        "campaign_id,campaign_name,adset_id,adset_name,"
        "spend,impressions,clicks,ctr,cpc,actions,action_values,account_currency"
    )
    by_object: list[dict[str, Any]] = []
    total_spend = 0.0
    total_purch = 0.0
    total_rev = 0.0
    total_impr = 0
    total_clicks = 0
    currency = None

    def _pull(level: str, ids: list[str], id_field: str) -> None:
        nonlocal total_spend, total_purch, total_rev, total_impr, total_clicks, currency
        if not ids:
            return
        # Meta filtering IN is limited; chunk ids
        for i in range(0, len(ids), 25):
            chunk = ids[i : i + 25]
            filtering = json.dumps(
                [{"field": id_field, "operator": "IN", "value": chunk}]
            )
            rows = _get_all(
                f"{act}/insights",
                {
                    "level": level,
                    "date_preset": date_preset,
                    "fields": fields,
                    "filtering": filtering,
                    "limit": 100,
                },
            )
            for row in rows:
                spend = float(row.get("spend") or 0)
                purch, rev = _purchases_revenue(row)
                impr = int(float(row.get("impressions") or 0))
                clicks = int(float(row.get("clicks") or 0))
                currency = row.get("account_currency") or currency
                total_spend += spend
                total_purch += purch
                total_rev += rev
                total_impr += impr
                total_clicks += clicks
                cpa = (spend / purch) if purch > 0 else None
                roas = (rev / spend) if spend > 0 else None
                by_object.append(
                    {
                        "level": level,
                        "id": row.get("adset_id") if level == "adset" else row.get("campaign_id"),
                        "name": (
                            row.get("adset_name")
                            if level == "adset"
                            else row.get("campaign_name")
                        ),
                        "campaign_name": row.get("campaign_name"),
                        "spend": round(spend, 2),
                        "purchases": round(purch, 2),
                        "attr_rev": round(rev, 2),
                        "impressions": impr,
                        "clicks": clicks,
                        "cpa": round(cpa, 2) if cpa is not None else None,
                        "roas": round(roas, 2) if roas is not None else None,
                    }
                )

    # Prefer adset-level when both selected (avoids double-counting a campaign + its adsets)
    if adset_ids:
        _pull("adset", adset_ids, "adset.id")
        # Only add campaigns that aren't parents of selected adsets
        if campaign_ids:
            structure = list_structure()
            parent_of_selected = {
                a["campaign_id"]
                for a in structure["adsets"]
                if a["id"] in set(adset_ids) and a.get("campaign_id")
            }
            extra_camps = [c for c in campaign_ids if c not in parent_of_selected]
            _pull("campaign", extra_camps, "campaign.id")
    else:
        _pull("campaign", campaign_ids, "campaign.id")

    by_object.sort(key=lambda r: r["spend"], reverse=True)
    cpa = (total_spend / total_purch) if total_purch > 0 else None
    roas = (total_rev / total_spend) if total_spend > 0 else None
    return {
        "spend": round(total_spend, 2),
        "purchases": round(total_purch, 2),
        "attr_rev": round(total_rev, 2),
        "impressions": total_impr,
        "clicks": total_clicks,
        "cpa": round(cpa, 2) if cpa is not None else None,
        "roas": round(roas, 2) if roas is not None else None,
        "currency": currency,
        "by_object": by_object,
        "date_preset": date_preset,
        "campaign_ids": campaign_ids,
        "adset_ids": adset_ids,
    }


def daily_insights_for_selection(
    *,
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
    since: str,
    until: str | None = None,
) -> dict[str, Any]:
    """Daily Meta spend / attributed revenue for selected campaigns and/or ad sets."""
    from datetime import datetime, timezone

    campaign_ids = [str(x) for x in (campaign_ids or []) if x]
    adset_ids = [str(x) for x in (adset_ids or []) if x]
    until = until or datetime.now(timezone.utc).date().isoformat()
    if not campaign_ids and not adset_ids:
        return {
            "days": [],
            "total_spend": 0.0,
            "total_attr_rev": 0.0,
            "since": since,
            "until": until,
            "warning": "No campaigns or ad sets selected.",
        }

    act = _act()
    fields = "spend,actions,action_values,account_currency,date_start,date_stop"
    spend_by: dict[str, float] = {}
    attr_by: dict[str, float] = {}
    purch_by: dict[str, float] = {}
    currency = None

    def _pull(level: str, ids: list[str], id_field: str) -> None:
        nonlocal currency
        if not ids:
            return
        for i in range(0, len(ids), 25):
            chunk = ids[i : i + 25]
            filtering = json.dumps(
                [{"field": id_field, "operator": "IN", "value": chunk}]
            )
            rows = _get_all(
                f"{act}/insights",
                {
                    "level": level,
                    "time_increment": 1,
                    "time_range": json.dumps({"since": since, "until": until}),
                    "fields": fields,
                    "filtering": filtering,
                    "limit": 500,
                },
            )
            for row in rows:
                day = row.get("date_start")
                if not day:
                    continue
                spend = float(row.get("spend") or 0)
                purch, rev = _purchases_revenue(row)
                currency = row.get("account_currency") or currency
                spend_by[day] = spend_by.get(day, 0.0) + spend
                attr_by[day] = attr_by.get(day, 0.0) + rev
                purch_by[day] = purch_by.get(day, 0.0) + purch

    if adset_ids:
        _pull("adset", adset_ids, "adset.id")
        if campaign_ids:
            structure = list_structure()
            parent_of_selected = {
                a["campaign_id"]
                for a in structure["adsets"]
                if a["id"] in set(adset_ids) and a.get("campaign_id")
            }
            extra_camps = [c for c in campaign_ids if c not in parent_of_selected]
            _pull("campaign", extra_camps, "campaign.id")
    else:
        _pull("campaign", campaign_ids, "campaign.id")

    days = [
        {
            "date": d,
            "spend": round(spend_by[d], 2),
            "purchases": round(purch_by.get(d, 0.0), 2),
            "attr_rev": round(attr_by.get(d, 0.0), 2),
            "currency": currency,
        }
        for d in sorted(spend_by)
    ]
    return {
        "days": days,
        "total_spend": round(sum(spend_by.values()), 2),
        "total_attr_rev": round(sum(attr_by.values()), 2),
        "currency": currency,
        "since": since,
        "until": until,
        "campaign_ids": campaign_ids,
        "adset_ids": adset_ids,
    }


# ── Ads performance desk (campaign / ad set / ad) ─────────────────

_META_DATE_PRESETS = frozenset(
    {
        "today",
        "yesterday",
        "this_month",
        "last_month",
        "this_quarter",
        "maximum",
        "last_3d",
        "last_7d",
        "last_14d",
        "last_28d",
        "last_30d",
        "last_90d",
        "last_week_mon_sun",
        "last_week_sun_sat",
        "this_week_mon_today",
        "this_week_sun_today",
        "lifetime",
    }
)

_INSIGHT_METRICS = (
    "spend,impressions,clicks,ctr,cpc,cpm,actions,action_values,account_currency"
)


def _f(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key) or default)
    except (TypeError, ValueError):
        return default


def _derived_rates(spend: float, purch: float, rev: float, impr: int, clicks: int) -> dict[str, Any]:
    cpa = (spend / purch) if purch > 0 else None
    roas = (rev / spend) if spend > 0 else None
    ctr = (clicks / impr * 100.0) if impr > 0 else None
    cpc = (spend / clicks) if clicks > 0 else None
    cpm = (spend / impr * 1000.0) if impr > 0 else None
    return {
        "cpa": round(cpa, 2) if cpa is not None else None,
        "roas": round(roas, 2) if roas is not None else None,
        "ctr": round(ctr, 3) if ctr is not None else None,
        "cpc": round(cpc, 2) if cpc is not None else None,
        "cpm": round(cpm, 2) if cpm is not None else None,
    }


def _resolve_date_window(
    *,
    date_preset: str | None,
    since: str | None,
    until: str | None,
) -> dict[str, Any]:
    """Return Meta query params + resolved since/until labels."""
    from datetime import datetime, timedelta, timezone

    today = datetime.now(timezone.utc).date()
    until_s = (until or today.isoformat()).strip()
    preset = (date_preset or "").strip() or None

    if since and since.strip():
        return {
            "since": since.strip(),
            "until": until_s,
            "date_preset": None,
            "params": {"time_range": json.dumps({"since": since.strip(), "until": until_s})},
        }

    if preset and preset in _META_DATE_PRESETS:
        # Approximate label window for UI (Meta owns the exact window for presets)
        days_map = {
            "last_3d": 3,
            "last_7d": 7,
            "last_14d": 14,
            "last_28d": 28,
            "last_30d": 30,
            "last_90d": 90,
        }
        if preset == "maximum" or preset == "lifetime":
            label_since = None
        elif preset in days_map:
            label_since = (today - timedelta(days=days_map[preset] - 1)).isoformat()
        else:
            label_since = None
        return {
            "since": label_since,
            "until": until_s,
            "date_preset": preset,
            "params": {"date_preset": preset},
        }

    # Default: last 30 days
    start = (today - timedelta(days=29)).isoformat()
    return {
        "since": start,
        "until": until_s,
        "date_preset": "last_30d",
        "params": {"time_range": json.dumps({"since": start, "until": until_s})},
    }


def _leaf_prefer_selection(
    *,
    campaign_ids: list[str],
    adset_ids: list[str],
    ad_ids: list[str],
    structure: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    """Prefer leaf objects so parent + child ticks do not double-count."""
    structure = structure or list_structure()
    ads = structure.get("ads") or []
    adsets = structure.get("adsets") or []
    ad_id_set = set(ad_ids)
    adset_id_set = set(adset_ids)
    campaign_id_set = set(campaign_ids)

    if ad_id_set:
        parent_adsets = {
            a.get("adset_id") for a in ads if a["id"] in ad_id_set and a.get("adset_id")
        }
        parent_camps = {
            a.get("campaign_id") for a in ads if a["id"] in ad_id_set and a.get("campaign_id")
        }
        adset_id_set -= parent_adsets
        campaign_id_set -= parent_camps

    if adset_id_set:
        parent_camps = {
            a.get("campaign_id")
            for a in adsets
            if a["id"] in adset_id_set and a.get("campaign_id")
        }
        campaign_id_set -= parent_camps

    return {
        "campaign_ids": sorted(campaign_id_set),
        "adset_ids": sorted(adset_id_set),
        "ad_ids": sorted(ad_id_set),
    }


def _object_identity(level: str, row: dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None]:
    """Return (id, name, campaign_name, adset_name) for an insights row."""
    if level == "ad":
        return (
            row.get("ad_id"),
            row.get("ad_name"),
            row.get("campaign_name"),
            row.get("adset_name"),
        )
    if level == "adset":
        return (
            row.get("adset_id"),
            row.get("adset_name"),
            row.get("campaign_name"),
            row.get("adset_name"),
        )
    return (
        row.get("campaign_id"),
        row.get("campaign_name"),
        row.get("campaign_name"),
        None,
    )


def _level_fields(level: str) -> str:
    if level == "ad":
        return (
            "ad_id,ad_name,adset_id,adset_name,campaign_id,campaign_name,"
            + _INSIGHT_METRICS
        )
    if level == "adset":
        return "campaign_id,campaign_name,adset_id,adset_name," + _INSIGHT_METRICS
    return "campaign_id,campaign_name," + _INSIGHT_METRICS


def _id_field(level: str) -> str:
    if level == "ad":
        return "ad.id"
    if level == "adset":
        return "adset.id"
    return "campaign.id"


def ads_performance_report(
    *,
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
    ad_ids: list[str] | None = None,
    date_preset: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, Any]:
    """Full Meta Ads Manager-style report for selected campaigns / ad sets / ads."""
    campaign_ids = [str(x) for x in (campaign_ids or []) if x]
    adset_ids = [str(x) for x in (adset_ids or []) if x]
    ad_ids = [str(x) for x in (ad_ids or []) if x]

    window = _resolve_date_window(date_preset=date_preset, since=since, until=until)
    date_params = window["params"]

    if not campaign_ids and not adset_ids and not ad_ids:
        return {
            "spend": 0.0,
            "purchases": 0.0,
            "attr_rev": 0.0,
            "impressions": 0,
            "clicks": 0,
            "ctr": None,
            "cpc": None,
            "cpm": None,
            "cpa": None,
            "roas": None,
            "currency": None,
            "by_object": [],
            "days": [],
            "series": [],
            "since": window["since"],
            "until": window["until"],
            "date_preset": window["date_preset"],
            "campaign_ids": [],
            "adset_ids": [],
            "ad_ids": [],
            "warning": "No campaigns, ad sets, or ads selected.",
        }

    structure = list_structure()
    resolved = _leaf_prefer_selection(
        campaign_ids=campaign_ids,
        adset_ids=adset_ids,
        ad_ids=ad_ids,
        structure=structure,
    )
    campaign_ids = resolved["campaign_ids"]
    adset_ids = resolved["adset_ids"]
    ad_ids = resolved["ad_ids"]

    act = _act()
    by_object: list[dict[str, Any]] = []
    total_spend = 0.0
    total_purch = 0.0
    total_rev = 0.0
    total_impr = 0
    total_clicks = 0
    currency = None

    # Combined daily buckets
    spend_by: dict[str, float] = {}
    purch_by: dict[str, float] = {}
    attr_by: dict[str, float] = {}
    impr_by: dict[str, int] = {}
    clicks_by: dict[str, int] = {}

    # Per-object daily series
    series_map: dict[str, dict[str, Any]] = {}

    def _ensure_series(level: str, oid: str, name: str | None, camp: str | None, adset: str | None) -> dict:
        key = f"{level}:{oid}"
        if key not in series_map:
            series_map[key] = {
                "level": level,
                "id": oid,
                "name": name or oid,
                "campaign_name": camp,
                "adset_name": adset,
                "_days": {},
            }
        return series_map[key]

    def _pull_aggregate(level: str, ids: list[str]) -> None:
        nonlocal total_spend, total_purch, total_rev, total_impr, total_clicks, currency
        if not ids:
            return
        fields = _level_fields(level)
        id_field = _id_field(level)
        for i in range(0, len(ids), 25):
            chunk = ids[i : i + 25]
            filtering = json.dumps(
                [{"field": id_field, "operator": "IN", "value": chunk}]
            )
            rows = _get_all(
                f"{act}/insights",
                {
                    "level": level,
                    "fields": fields,
                    "filtering": filtering,
                    "limit": 100,
                    **date_params,
                },
            )
            for row in rows:
                spend = _f(row, "spend")
                purch, rev = _purchases_revenue(row)
                impr = int(_f(row, "impressions"))
                clicks = int(_f(row, "clicks"))
                currency = row.get("account_currency") or currency
                total_spend += spend
                total_purch += purch
                total_rev += rev
                total_impr += impr
                total_clicks += clicks
                rates = _derived_rates(spend, purch, rev, impr, clicks)
                # Prefer Meta-provided rates when present
                if row.get("ctr") not in (None, ""):
                    rates["ctr"] = round(_f(row, "ctr"), 3)
                if row.get("cpc") not in (None, ""):
                    rates["cpc"] = round(_f(row, "cpc"), 2)
                if row.get("cpm") not in (None, ""):
                    rates["cpm"] = round(_f(row, "cpm"), 2)
                oid, name, camp, adset_name = _object_identity(level, row)
                if not oid:
                    continue
                by_object.append(
                    {
                        "level": level,
                        "id": oid,
                        "name": name or oid,
                        "campaign_name": camp,
                        "adset_name": adset_name if level == "ad" else None,
                        "spend": round(spend, 2),
                        "purchases": round(purch, 2),
                        "attr_rev": round(rev, 2),
                        "impressions": impr,
                        "clicks": clicks,
                        **rates,
                    }
                )

    def _pull_daily(level: str, ids: list[str]) -> None:
        nonlocal currency
        if not ids:
            return
        fields = _level_fields(level) + ",date_start,date_stop"
        id_field = _id_field(level)
        for i in range(0, len(ids), 25):
            chunk = ids[i : i + 25]
            filtering = json.dumps(
                [{"field": id_field, "operator": "IN", "value": chunk}]
            )
            rows = _get_all(
                f"{act}/insights",
                {
                    "level": level,
                    "time_increment": 1,
                    "fields": fields,
                    "filtering": filtering,
                    "limit": 500,
                    **date_params,
                },
            )
            for row in rows:
                day = row.get("date_start")
                if not day:
                    continue
                spend = _f(row, "spend")
                purch, rev = _purchases_revenue(row)
                impr = int(_f(row, "impressions"))
                clicks = int(_f(row, "clicks"))
                currency = row.get("account_currency") or currency
                spend_by[day] = spend_by.get(day, 0.0) + spend
                purch_by[day] = purch_by.get(day, 0.0) + purch
                attr_by[day] = attr_by.get(day, 0.0) + rev
                impr_by[day] = impr_by.get(day, 0) + impr
                clicks_by[day] = clicks_by.get(day, 0) + clicks

                oid, name, camp, adset_name = _object_identity(level, row)
                if not oid:
                    continue
                ser = _ensure_series(level, oid, name, camp, adset_name)
                bucket = ser["_days"].setdefault(
                    day,
                    {
                        "date": day,
                        "spend": 0.0,
                        "purchases": 0.0,
                        "attr_rev": 0.0,
                        "impressions": 0,
                        "clicks": 0,
                    },
                )
                bucket["spend"] += spend
                bucket["purchases"] += purch
                bucket["attr_rev"] += rev
                bucket["impressions"] += impr
                bucket["clicks"] += clicks

    _pull_aggregate("ad", ad_ids)
    _pull_aggregate("adset", adset_ids)
    _pull_aggregate("campaign", campaign_ids)

    _pull_daily("ad", ad_ids)
    _pull_daily("adset", adset_ids)
    _pull_daily("campaign", campaign_ids)

    by_object.sort(key=lambda r: r["spend"], reverse=True)
    totals_rates = _derived_rates(total_spend, total_purch, total_rev, total_impr, total_clicks)

    days = []
    for d in sorted(spend_by):
        spend = spend_by[d]
        purch = purch_by.get(d, 0.0)
        rev = attr_by.get(d, 0.0)
        impr = impr_by.get(d, 0)
        clicks = clicks_by.get(d, 0)
        rates = _derived_rates(spend, purch, rev, impr, clicks)
        days.append(
            {
                "date": d,
                "spend": round(spend, 2),
                "purchases": round(purch, 2),
                "attr_rev": round(rev, 2),
                "impressions": impr,
                "clicks": clicks,
                "ctr": rates["ctr"],
                "cpc": rates["cpc"],
                "cpm": rates["cpm"],
                "cpa": rates["cpa"],
                "roas": rates["roas"],
                "currency": currency,
            }
        )

    series: list[dict[str, Any]] = []
    for ser in series_map.values():
        obj_days = []
        for d in sorted(ser["_days"]):
            b = ser["_days"][d]
            rates = _derived_rates(
                b["spend"], b["purchases"], b["attr_rev"], b["impressions"], b["clicks"]
            )
            obj_days.append(
                {
                    "date": d,
                    "spend": round(b["spend"], 2),
                    "purchases": round(b["purchases"], 2),
                    "attr_rev": round(b["attr_rev"], 2),
                    "impressions": b["impressions"],
                    "clicks": b["clicks"],
                    **rates,
                }
            )
        series.append(
            {
                "level": ser["level"],
                "id": ser["id"],
                "name": ser["name"],
                "campaign_name": ser["campaign_name"],
                "adset_name": ser["adset_name"],
                "days": obj_days,
                "spend": round(sum(x["spend"] for x in obj_days), 2),
            }
        )
    series.sort(key=lambda r: r["spend"], reverse=True)

    return {
        "spend": round(total_spend, 2),
        "purchases": round(total_purch, 2),
        "attr_rev": round(total_rev, 2),
        "impressions": total_impr,
        "clicks": total_clicks,
        **totals_rates,
        "currency": currency,
        "by_object": by_object,
        "days": days,
        "series": series,
        "since": window["since"],
        "until": window["until"],
        "date_preset": window["date_preset"],
        "campaign_ids": campaign_ids,
        "adset_ids": adset_ids,
        "ad_ids": ad_ids,
        "account_id": act,
    }
