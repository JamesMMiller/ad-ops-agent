#!/usr/bin/env python3
"""Compress a Profit Admin snapshot or Ads+P&L report into an agent-friendly digest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any


def _num(x: Any) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _parse_day(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _tail_days(days: list[dict[str, Any]], n: int = 7) -> list[dict[str, Any]]:
    if not days:
        return []
    out = []
    for d in days[-n:]:
        out.append(
            {
                "date": d.get("date"),
                "rev": d.get("rev"),
                "ads": d.get("ads") if "ads" in d else d.get("spend"),
                "day_pnl": d.get("day_pnl"),
                "cum_pnl": d.get("cum_pnl"),
                "mer3d": d.get("mer3d"),
                "attr_rev": d.get("attr_rev"),
                "roas": d.get("roas"),
            }
        )
    return out


_CHANGELOG_HEAD = re.compile(
    r"^###\s+(\d{4}-\d{2}-\d{2})\s*(?:\((.+?)\))?\s*$", re.M
)
_TOOLING_HINTS = (
    "profit admin",
    "pdf export",
    "excel export",
    "skill",
    "docs synced",
    "apps script",
    "sync",
)


def parse_master_changelog(text: str) -> list[dict[str, str]]:
    """Parse MASTER_CONTEXT Changelog headings + Decision/What changed/Why bullets."""
    # Restrict to Changelog section when present
    idx = text.find("## Changelog")
    body = text[idx:] if idx >= 0 else text
    matches = list(_CHANGELOG_HEAD.finditer(body))
    events: list[dict[str, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        chunk = body[start:end]
        decision = ""
        changed = ""
        why = ""
        for line in chunk.splitlines():
            s = line.strip()
            if s.startswith("- **Decision:**"):
                decision = s.split(":**", 1)[-1].strip()
            elif s.startswith("- **What changed:**"):
                changed = s.split(":**", 1)[-1].strip()
            elif s.startswith("- **Why:**"):
                why = s.split(":**", 1)[-1].strip()
            elif s.startswith("- ") and not decision and "**" not in s[:20]:
                # Some older entries are single-bullet notes
                if not decision:
                    decision = s[2:].strip()
        title = (m.group(2) or "").strip() or decision[:80]
        blob = f"{title} {decision} {changed} {why}".lower()
        tooling = any(h in blob for h in _TOOLING_HINTS) and not any(
            k in blob
            for k in (
                "price",
                "ad set",
                "creative",
                "pdp",
                "deal",
                "meta",
                "gan",
                "vacuum",
                "launch",
                "live",
                "publish",
            )
        )
        events.append(
            {
                "date": m.group(1),
                "title": title,
                "decision": decision,
                "changed": changed,
                "why": why,
                "likely_tooling_only": tooling,
            }
        )
    return events


def _day_metrics(row: dict[str, Any]) -> dict[str, float]:
    rev = _num(row.get("rev")) or 0.0
    ads = _num(row.get("ads") if "ads" in row else row.get("spend")) or 0.0
    attr = _num(row.get("attr_rev")) or 0.0
    return {"rev": rev, "ads": ads, "attr_rev": attr, "day_pnl": _num(row.get("day_pnl")) or 0.0}


def _aggregate_slice(days: list[dict[str, Any]], start: date, end: date) -> dict[str, Any]:
    rows = []
    for d in days:
        dd = _parse_day(d.get("date"))
        if dd is None or dd < start or dd > end:
            continue
        rows.append(_day_metrics(d))
    if not rows:
        return {"days": 0, "rev": 0.0, "ads": 0.0, "attr_rev": 0.0, "day_pnl": 0.0, "mer": None, "roas": None}
    rev = sum(r["rev"] for r in rows)
    ads = sum(r["ads"] for r in rows)
    attr = sum(r["attr_rev"] for r in rows)
    pnl = sum(r["day_pnl"] for r in rows)
    return {
        "days": len(rows),
        "rev": round(rev, 2),
        "ads": round(ads, 2),
        "attr_rev": round(attr, 2),
        "day_pnl": round(pnl, 2),
        "mer": round(rev / ads, 2) if ads > 0 else None,
        "roas": round(attr / ads, 2) if ads > 0 else None,
    }


def correlate_changelog(
    *,
    events: list[dict[str, str]],
    days: list[dict[str, Any]],
    window_start: str | None,
    window_end: str | None,
    pre_days: int = 7,
    post_days: int = 7,
    include_tooling: bool = False,
) -> list[dict[str, Any]]:
    ws = _parse_day(window_start)
    we = _parse_day(window_end)
    if not days or not ws or not we:
        return []
    lookback = ws - timedelta(days=pre_days)
    out: list[dict[str, Any]] = []
    for ev in events:
        if ev.get("likely_tooling_only") and not include_tooling:
            continue
        ed = _parse_day(ev.get("date"))
        if ed is None or ed < lookback or ed > we:
            continue
        pre_start = max(ws, ed - timedelta(days=pre_days))
        pre_end = ed - timedelta(days=1)
        post_start = ed
        post_end = min(we, ed + timedelta(days=post_days))
        pre = _aggregate_slice(days, pre_start, pre_end) if pre_end >= pre_start else {
            "days": 0, "rev": 0.0, "ads": 0.0, "attr_rev": 0.0, "day_pnl": 0.0, "mer": None, "roas": None
        }
        post = _aggregate_slice(days, post_start, post_end)
        note = None
        if post["days"] < 3:
            note = "too_early_post_window"
        out.append(
            {
                "date": ev["date"],
                "title": ev.get("title"),
                "decision": ev.get("decision"),
                "changed": ev.get("changed"),
                "why": ev.get("why"),
                "likely_tooling_only": ev.get("likely_tooling_only"),
                "pre": {**pre, "start": pre_start.isoformat(), "end": pre_end.isoformat() if pre_end >= pre_start else None},
                "post": {**post, "start": post_start.isoformat(), "end": post_end.isoformat()},
                "note": note,
            }
        )
    out.sort(key=lambda r: r["date"])
    return out


def _series_days_from_digest_source(data: dict[str, Any], digest: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None, str | None]:
    if digest.get("kind") == "ads_report":
        pnl = data.get("pnl") or {}
        days = list(pnl.get("days") or data.get("days") or [])
        # Prefer pnl days (have rev); else meta days
        w = digest.get("window") or {}
        return days, w.get("since"), w.get("until")
    pnl = data.get("pnl") or {}
    days = list(pnl.get("days") or [])
    w = digest.get("window") or {}
    return days, w.get("start"), w.get("end")


def summarize_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    pnl = data.get("pnl") or {}
    totals = pnl.get("totals") or {}
    days = pnl.get("days") or []
    products = data.get("product_pnl") or []
    units = data.get("unit_economics") or []

    top_products = sorted(
        [
            {
                "product": p.get("product") or p.get("handle"),
                "handle": p.get("handle"),
                "revenue": p.get("revenue") or p.get("rev"),
                "contrib": p.get("contrib"),
                "units": p.get("units"),
            }
            for p in products
        ],
        key=lambda r: float(r.get("contrib") or 0),
        reverse=True,
    )[:8]

    weak_products = sorted(
        [p for p in top_products if _num(p.get("contrib")) is not None],
        key=lambda r: float(r.get("contrib") or 0),
    )[:5]

    unit_rows = [
        {
            "product": u.get("product") or u.get("handle"),
            "price": u.get("price") or u.get("sell_price"),
            "landed": u.get("landed") or u.get("unit_cogs"),
            "margin_after_fees": u.get("margin_after_fees") or u.get("margin"),
        }
        for u in units[:12]
    ]

    meta_src = (data.get("sources") or {}).get("meta") or {}
    kie_src = (data.get("sources") or {}).get("kie") or {}

    return {
        "kind": "snapshot",
        "refreshed_at": data.get("refreshed_at"),
        "window": {
            "start": days[0].get("date") if days else None,
            "end": days[-1].get("date") if days else None,
            "day_count": len(days),
        },
        "totals": {
            "revenue": totals.get("revenue"),
            "landed_cogs": totals.get("landed_cogs"),
            "fees": totals.get("fees"),
            "meta_spend": totals.get("meta_spend"),
            "kie_gbp": totals.get("kie_gbp"),
            "shopify_amortised": totals.get("shopify_amortised"),
            "cum_pnl": totals.get("cum_pnl"),
            "store_mer": totals.get("store_mer"),
            "meta_roas": totals.get("meta_roas"),
            "mer3d": totals.get("mer3d"),
            "orders": totals.get("orders"),
            "meta_attr_rev": totals.get("meta_attr_rev"),
        },
        "last_7_days": _tail_days(days, 7),
        "top_products_by_contrib": top_products[:5],
        "weakest_products_by_contrib": weak_products,
        "unit_economics_sample": unit_rows,
        "meta_account": {
            "name": (meta_src.get("account") or {}).get("name"),
            "total_spend": meta_src.get("total_spend"),
            "total_attr_rev": meta_src.get("total_attr_rev"),
        },
        "kie": {
            "total_gbp": kie_src.get("total_gbp") or kie_src.get("gbp"),
            "total_credits": kie_src.get("total_credits") or kie_src.get("credits"),
        },
        "warnings": data.get("warnings") or [],
        "assumptions": (pnl.get("assumptions") or {}),
    }


def summarize_ads_report(data: dict[str, Any]) -> dict[str, Any]:
    pnl = data.get("pnl") or {}
    pnl_totals = (pnl.get("totals") or {}) if isinstance(pnl, dict) else {}
    by_object = data.get("by_object") or []
    top = sorted(by_object, key=lambda r: float(r.get("spend") or 0), reverse=True)[:12]
    worst_roas = sorted(
        [r for r in by_object if _num(r.get("spend")) and float(r.get("spend") or 0) > 0],
        key=lambda r: float(r.get("roas") if r.get("roas") is not None else 1e9),
    )[:8]

    return {
        "kind": "ads_report",
        "window": {
            "since": data.get("since"),
            "until": data.get("until"),
            "date_preset": data.get("date_preset"),
        },
        "selection": {
            "campaign_ids": data.get("campaign_ids") or [],
            "adset_ids": data.get("adset_ids") or [],
            "ad_ids": data.get("ad_ids") or [],
            "skus": data.get("skus") or [],
            "handles": data.get("handles") or [],
        },
        "pnl_mode": data.get("pnl_mode"),
        "meta_totals": {
            "spend": data.get("spend"),
            "purchases": data.get("purchases"),
            "attr_rev": data.get("attr_rev"),
            "roas": data.get("roas"),
            "cpa": data.get("cpa"),
            "impressions": data.get("impressions"),
            "clicks": data.get("clicks"),
            "ctr": data.get("ctr"),
            "cpc": data.get("cpc"),
            "cpm": data.get("cpm"),
            "currency": data.get("currency"),
        },
        "pnl_totals": pnl_totals,
        "pnl_label": pnl.get("label") if isinstance(pnl, dict) else None,
        "pnl_note": pnl.get("note") if isinstance(pnl, dict) else None,
        "top_objects_by_spend": [
            {
                "level": o.get("level"),
                "name": o.get("name"),
                "spend": o.get("spend"),
                "purchases": o.get("purchases"),
                "attr_rev": o.get("attr_rev"),
                "roas": o.get("roas"),
                "cpa": o.get("cpa"),
            }
            for o in top
        ],
        "weakest_roas_with_spend": [
            {
                "level": o.get("level"),
                "name": o.get("name"),
                "spend": o.get("spend"),
                "roas": o.get("roas"),
                "purchases": o.get("purchases"),
            }
            for o in worst_roas
        ],
        "meta_last_7_days": _tail_days(data.get("days") or [], 7),
        "pnl_last_7_days": _tail_days((pnl.get("days") or []) if isinstance(pnl, dict) else [], 7),
        "warnings": data.get("warnings") or ([data["warning"]] if data.get("warning") else []),
    }


def detect_and_summarize(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("by_object") is not None or data.get("pnl_mode") is not None:
        return summarize_ads_report(data)
    if data.get("pnl") is not None or data.get("refreshed_at") is not None:
        return summarize_snapshot(data)
    raise SystemExit("Unrecognised JSON — expected a Profit Admin snapshot or Ads report.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--snapshot", type=Path, help="Path to snapshot JSON (e.g. latest.json)")
    g.add_argument("--report", type=Path, help="Path to saved Ads+P&L report JSON")
    ap.add_argument(
        "--changelog",
        type=Path,
        help="Path to MASTER_CONTEXT.md (adds Changelog × pre/post metric slices)",
    )
    ap.add_argument(
        "--include-tooling",
        action="store_true",
        help="Keep likely tooling-only changelog entries in the correlation list",
    )
    ap.add_argument("--markdown", action="store_true", help="Print a short markdown summary")
    args = ap.parse_args()

    path = args.snapshot or args.report
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    digest = detect_and_summarize(data)
    digest["source_path"] = str(path)

    if args.changelog:
        if not args.changelog.exists():
            raise SystemExit(f"Changelog not found: {args.changelog}")
        events = parse_master_changelog(args.changelog.read_text(encoding="utf-8"))
        days, start, end = _series_days_from_digest_source(data, digest)
        ws, we = _parse_day(start), _parse_day(end)
        lookback_events: list[dict[str, str]] = []
        if ws and we:
            lb = ws - timedelta(days=7)
            for e in events:
                ed = _parse_day(e.get("date"))
                if ed and lb <= ed <= we:
                    lookback_events.append(e)
        digest["changelog_events_all_in_lookback"] = lookback_events
        digest["changelog_correlation"] = correlate_changelog(
            events=events,
            days=days,
            window_start=start,
            window_end=end,
            include_tooling=args.include_tooling,
        )
        digest["changelog_path"] = str(args.changelog)

    if args.markdown:
        print(_as_markdown(digest))
    else:
        json.dump(digest, sys.stdout, indent=2)
        print()


def _as_markdown(d: dict[str, Any]) -> str:
    lines = [f"# Profit Admin digest — `{d.get('source_path')}`", ""]
    if d.get("kind") == "snapshot":
        t = d.get("totals") or {}
        w = d.get("window") or {}
        lines += [
            f"- Kind: snapshot · refreshed `{d.get('refreshed_at')}`",
            f"- Window: {w.get('start')} → {w.get('end')} ({w.get('day_count')} days)",
            f"- Revenue £{t.get('revenue')} · Ads £{t.get('meta_spend')} · Cum P&L £{t.get('cum_pnl')}",
            f"- Store MER {t.get('store_mer')}× · Meta ROAS {t.get('meta_roas')}× · MER3d {t.get('mer3d')}×",
            "",
            "## Top products (contrib)",
        ]
        for p in d.get("top_products_by_contrib") or []:
            lines.append(f"- {p.get('product')}: contrib £{p.get('contrib')} · rev £{p.get('revenue')}")
    else:
        m = d.get("meta_totals") or {}
        p = d.get("pnl_totals") or {}
        w = d.get("window") or {}
        lines += [
            f"- Kind: ads_report · mode `{d.get('pnl_mode')}`",
            f"- Window: {w.get('since')} → {w.get('until')} ({w.get('date_preset')})",
            f"- Meta spend £{m.get('spend')} · attr rev £{m.get('attr_rev')} · ROAS {m.get('roas')}× · CPA £{m.get('cpa')}",
            f"- P&L rev £{p.get('revenue')} · cum P&L £{p.get('cum_pnl')} · store MER {p.get('store_mer')}×",
            "",
            "## Top objects by spend",
        ]
        for o in d.get("top_objects_by_spend") or []:
            lines.append(
                f"- [{o.get('level')}] {o.get('name')}: £{o.get('spend')} · ROAS {o.get('roas')}× · purch {o.get('purchases')}"
            )

    corr = d.get("changelog_correlation") or []
    if corr or d.get("changelog_path"):
        lines += ["", f"## Changelog × data (`{d.get('changelog_path')}`)"]
        if not corr:
            lines.append("- No material overlapping events (or only tooling-only entries filtered).")
        for ev in corr:
            pre, post = ev.get("pre") or {}, ev.get("post") or {}
            lines.append(
                f"- **{ev.get('date')} — {ev.get('title')}**"
                f" · pre MER {pre.get('mer')}× / ROAS {pre.get('roas')}× / ads £{pre.get('ads')}"
                f" → post MER {post.get('mer')}× / ROAS {post.get('roas')}× / ads £{post.get('ads')}"
                f" ({post.get('days')}d post)"
                + (f" · _{ev.get('note')}_" if ev.get("note") else "")
            )
            if ev.get("decision"):
                lines.append(f"  - Decision: {ev['decision']}")

    warns = d.get("warnings") or []
    if warns:
        lines += ["", "## Warnings"]
        for w in warns:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
