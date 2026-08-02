#!/usr/bin/env python3
"""
Creative-iteration cycle for one Meta ad set: classify ACTIVE ads, plan
pauses for losers / excess mids, and open spawn slots for winner variations.

Default is dry-run (writes plan.json + summary.md). Pass --apply to pause
recommended ads. Never deletes. Never auto-activates new ads.

Usage:
  python iterate-adset.py --adset-id 120250218590230639
  python iterate-adset.py --adset-id … --apply
  python iterate-adset.py --adset-id … --protect-ad-id 123 --protect-ad-id 456

See reference/creative-iteration.md for rules and cadence.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent / "lib"))

load_dotenv()

import requests  # noqa: E402
import meta_api  # noqa: E402

INSIGHT_FIELDS = [
    "ad_id",
    "ad_name",
    "adset_id",
    "adset_name",
    "spend",
    "impressions",
    "clicks",
    "ctr",
    "cpc",
    "actions",
    "action_values",
]


def extract_purchases(actions, action_values):
    purchases, revenue = 0, 0.0
    for a in actions or []:
        if a.get("action_type") == "purchase":
            purchases = int(float(a.get("value", 0)))
    for a in action_values or []:
        if a.get("action_type") == "purchase":
            revenue = float(a.get("value", 0))
    return purchases, revenue


def sku_from_adset_name(name: str) -> str:
    """OTA | GaN | Cold | … → gan; fallback 'adset'."""
    if not name:
        return "adset"
    parts = [p.strip() for p in name.split("|")]
    if len(parts) >= 2 and parts[0].upper() == "OTA":
        return parts[1].lower().replace(" ", "-")
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in name.lower())
    return slug.strip("-")[:32] or "adset"


def fetch_adset_insights(adset_id: str, token: str, date_preset: str) -> list[dict]:
    url = f"{meta_api.BASE_URL}/{meta_api.get_ad_account_id()}/insights"
    params = {
        "access_token": token,
        "level": "ad",
        "fields": ",".join(INSIGHT_FIELDS),
        "date_preset": date_preset,
        "limit": 100,
        "filtering": json.dumps([
            {"field": "adset.id", "operator": "EQUAL", "value": str(adset_id)},
        ]),
    }
    rows = []
    while url:
        resp = requests.get(url, params=params, timeout=60)
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"insights error: {json.dumps(data['error'])}")
        rows.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        params = None
    return rows


def classify_ads(
    active_ads: list[dict],
    insights_by_id: dict[str, dict],
    *,
    min_spend: float,
    max_active: int,
    protect_ids: set[str],
) -> dict:
    """Return classified rows + pause list + spawn plan."""

    rows = []
    for ad in active_ads:
        ad_id = str(ad["id"])
        insight = insights_by_id.get(ad_id, {})
        spend = float(insight.get("spend", 0) or 0)
        purchases = int(insight.get("purchases", 0) or 0)
        revenue = float(insight.get("revenue", 0) or 0)
        roas = revenue / spend if spend > 0 else 0.0
        rows.append({
            "ad_id": ad_id,
            "ad_name": ad.get("name") or insight.get("ad_name") or "",
            "status": ad.get("status"),
            "effective_status": ad.get("effective_status"),
            "spend": round(spend, 2),
            "purchases": purchases,
            "revenue": round(revenue, 2),
            "roas": round(roas, 3),
            "impressions": int(insight.get("impressions", 0) or 0),
            "clicks": int(insight.get("clicks", 0) or 0),
            "ctr": float(insight.get("ctr", 0) or 0),
            "protected": ad_id in protect_ids,
            "bucket": None,
            "action": "keep",
            "reason": "",
        })

    judged = [r for r in rows if r["spend"] >= min_spend]
    median_roas = (
        statistics.median([r["roas"] for r in judged]) if judged else 0.0
    )
    loser_roas_cutoff = 0.5 * median_roas if judged else 0.0

    best_roas_id = None
    if judged:
        best = max(judged, key=lambda r: (r["roas"], r["purchases"], r["spend"]))
        best_roas_id = best["ad_id"]

    for r in rows:
        if r["spend"] < min_spend:
            r["bucket"] = "learning"
            r["reason"] = f"spend £{r['spend']:.2f} < £{min_spend:.0f} judge floor"
            continue

        is_zero_purchase_loser = r["purchases"] == 0
        is_roas_loser = (
            median_roas > 0 and r["roas"] < loser_roas_cutoff
        )
        if is_zero_purchase_loser or is_roas_loser:
            r["bucket"] = "loser"
            parts = []
            if is_zero_purchase_loser:
                parts.append(f"£{r['spend']:.2f} spend, 0 purchases")
            if is_roas_loser:
                parts.append(
                    f"ROAS {r['roas']:.2f} < 50% of judged median {median_roas:.2f}"
                )
            r["reason"] = "; ".join(parts)
            continue

        if r["purchases"] >= 1 or r["ad_id"] == best_roas_id:
            r["bucket"] = "winner"
            if r["purchases"] >= 1:
                r["reason"] = f"{r['purchases']} purchase(s), ROAS {r['roas']:.2f}"
            else:
                r["reason"] = f"best ROAS among judged ({r['roas']:.2f})"
            continue

        r["bucket"] = "mid"
        r["reason"] = f"judged mid (ROAS {r['roas']:.2f})"

    # Pause losers (unless protected)
    for r in rows:
        if r["bucket"] == "loser":
            if r["protected"]:
                r["action"] = "keep"
                r["reason"] += " — protected, not pausing"
            else:
                r["action"] = "pause"

    # Cap: after planned pauses, if still over max_active, pause worst mids
    keepers = [r for r in rows if r["action"] == "keep"]
    overflow = len(keepers) - max_active
    if overflow > 0:
        mid_candidates = sorted(
            [r for r in keepers if r["bucket"] == "mid" and not r["protected"]],
            key=lambda r: (r["roas"], -r["spend"]),
        )
        for r in mid_candidates[:overflow]:
            r["action"] = "pause"
            r["reason"] += f" — over ACTIVE cap ({max_active}); pause worst mid"
            overflow -= 1
        if overflow > 0:
            # Still over: winners + learning exceed cap; flag only
            pass

    remaining_active = sum(1 for r in rows if r["action"] == "keep")
    spawn_slots = max(0, max_active - remaining_active)
    cap_overflow = max(0, remaining_active - max_active)

    winners = sorted(
        [r for r in rows if r["bucket"] == "winner" and r["action"] == "keep"],
        key=lambda r: (r["roas"], r["purchases"], r["spend"]),
        reverse=True,
    )

    spawns = []
    for i in range(spawn_slots):
        source = winners[i % len(winners)] if winners else None
        if source is None:
            spawns.append({
                "slot": i + 1,
                "source_ad_id": None,
                "source_ad_name": None,
                "brief": (
                    "No winner in-window — generate a fresh CT creative "
                    "(one clear angle); deploy PAUSED; unmute only if under cap."
                ),
            })
        else:
            spawns.append({
                "slot": i + 1,
                "source_ad_id": source["ad_id"],
                "source_ad_name": source["ad_name"],
                "brief": (
                    f"Variation of winner «{source['ad_name']}»: keep sku/ratio/fmt; "
                    "change ONE of hook / visual / copy angle / format; bump variant "
                    "slug per naming-convention.md; deploy PAUSED into this ad set."
                ),
            })

    pause_list = [r for r in rows if r["action"] == "pause"]
    return {
        "rows": rows,
        "median_roas": round(median_roas, 3),
        "loser_roas_cutoff": round(loser_roas_cutoff, 3),
        "remaining_active": remaining_active,
        "spawn_slots": spawn_slots,
        "cap_overflow": cap_overflow,
        "pause_list": pause_list,
        "spawns": spawns,
        "winners": winners,
    }


def write_summary(path: Path, plan: dict) -> None:
    cfg = plan["config"]
    lines = [
        f"# Creative iteration — {plan['adset_name']}",
        "",
        f"- Ad set: `{plan['adset_id']}`",
        f"- Window: `{cfg['date_preset']}` · min spend £{cfg['min_spend']:.0f} · "
        f"max ACTIVE {cfg['max_active']}",
        f"- Total spend in window: £{plan['total_spend']:.2f}",
        f"- Judged median ROAS: {plan['median_roas']:.2f} "
        f"(loser cutoff {plan['loser_roas_cutoff']:.2f})",
        f"- Skip recommended: {plan['skip_recommended']} "
        f"({'<' if plan['skip_recommended'] else '≥'} £{cfg['min_cycle_spend']:.0f} cycle floor)",
        f"- After cuts: {plan['remaining_active']} keep · "
        f"{plan['spawn_slots']} spawn slot(s)",
        "",
    ]
    if plan.get("cap_overflow"):
        lines.append(
            f"**Cap overflow:** {plan['cap_overflow']} keeper(s) still above "
            f"max ACTIVE after pausing losers/mids — review winners/learning manually."
        )
        lines.append("")

    lines.extend(["## Ads", ""])
    lines.append("| Bucket | Action | Spend | Purch | ROAS | Name | Reason |")
    lines.append("|--------|--------|------:|------:|-----:|------|--------|")
    for r in plan["ads"]:
        lines.append(
            f"| {r['bucket']} | {r['action']} | £{r['spend']:.2f} | "
            f"{r['purchases']} | {r['roas']:.2f} | {r['ad_name'][:48]} | {r['reason']} |"
        )

    lines.extend(["", "## Pause", ""])
    if plan["pause"]:
        for p in plan["pause"]:
            lines.append(f"- `{p['ad_id']}` — {p['ad_name']} ({p['reason']})")
    else:
        lines.append("_None_")

    lines.extend(["", "## Spawn slots", ""])
    if plan["spawns"]:
        for s in plan["spawns"]:
            src = s["source_ad_name"] or "(no winner)"
            lines.append(f"- Slot {s['slot']} ← {src}")
            lines.append(f"  - {s['brief']}")
    else:
        lines.append("_None — at ACTIVE cap after keepers._")

    lines.extend([
        "",
        "## Next",
        "",
        "1. Review this plan. If pauses look right: re-run with `--apply`.",
        "2. For each spawn slot: generate creative → `deploy-ad.py` PAUSED.",
        "3. Unmute at most 2 new ads this cycle; stay under the ACTIVE cap.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Iterate one Meta creative-test ad set (cut losers, open spawn slots)"
    )
    parser.add_argument("--adset-id", required=True, help="Target ad set ID")
    parser.add_argument(
        "--date-preset",
        default="last_3d",
        help="Insights preset (default last_3d)",
    )
    parser.add_argument(
        "--min-spend",
        type=float,
        default=8.0,
        help="Min £ spend to judge (default 8)",
    )
    parser.add_argument(
        "--max-active",
        type=int,
        default=5,
        help="Hard ACTIVE ad cap (default 5)",
    )
    parser.add_argument(
        "--min-cycle-spend",
        type=float,
        default=20.0,
        help="Recommend skip if ad-set spend below this (default 20)",
    )
    parser.add_argument(
        "--protect-ad-id",
        action="append",
        default=[],
        help="Ad ID never paused (repeatable)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Pause recommended ads (default: dry-run only)",
    )
    args = parser.parse_args()

    token = meta_api.get_access_token()
    adset = meta_api.get_adset(args.adset_id)
    adset_name = adset.get("name") or args.adset_id
    sku = sku_from_adset_name(adset_name)
    protect_ids = {str(x) for x in args.protect_ad_id}

    print(f"ITERATE → {adset_name} ({args.adset_id})")
    print(f"  window={args.date_preset}  min_spend=£{args.min_spend:.0f}  "
          f"max_active={args.max_active}  apply={args.apply}\n")

    active_ads = meta_api.list_ads(args.adset_id, status_filter=["ACTIVE"])
    print(f"  ACTIVE ads: {len(active_ads)}")

    raw_insights = fetch_adset_insights(args.adset_id, token, args.date_preset)
    insights_by_id: dict[str, dict] = {}
    for row in raw_insights:
        ad_id = str(row.get("ad_id"))
        purchases, revenue = extract_purchases(
            row.get("actions"), row.get("action_values")
        )
        insights_by_id[ad_id] = {
            "ad_name": row.get("ad_name"),
            "spend": float(row.get("spend", 0) or 0),
            "impressions": int(row.get("impressions", 0) or 0),
            "clicks": int(row.get("clicks", 0) or 0),
            "ctr": float(row.get("ctr", 0) or 0),
            "purchases": purchases,
            "revenue": revenue,
        }

    total_spend = sum(v["spend"] for v in insights_by_id.values())
    # Prefer spend among ACTIVE ads for the skip floor
    active_ids = {str(a["id"]) for a in active_ads}
    active_spend = sum(
        insights_by_id[i]["spend"] for i in active_ids if i in insights_by_id
    )
    cycle_spend = active_spend if active_spend > 0 else total_spend
    skip_recommended = cycle_spend < args.min_cycle_spend

    result = classify_ads(
        active_ads,
        insights_by_id,
        min_spend=args.min_spend,
        max_active=args.max_active,
        protect_ids=protect_ids,
    )

    run_slug = f"{date.today().isoformat()}-iterate-{sku}"
    out_dir = meta_api.resolve_output_dir(run_slug)

    plan = {
        "adset_id": str(args.adset_id),
        "adset_name": adset_name,
        "sku": sku,
        "config": {
            "date_preset": args.date_preset,
            "min_spend": args.min_spend,
            "max_active": args.max_active,
            "min_cycle_spend": args.min_cycle_spend,
            "protect_ad_ids": sorted(protect_ids),
            "apply": args.apply,
        },
        "total_spend": round(cycle_spend, 2),
        "skip_recommended": skip_recommended,
        "median_roas": result["median_roas"],
        "loser_roas_cutoff": result["loser_roas_cutoff"],
        "remaining_active": result["remaining_active"],
        "spawn_slots": result["spawn_slots"],
        "cap_overflow": result["cap_overflow"],
        "ads": result["rows"],
        "pause": [
            {
                "ad_id": r["ad_id"],
                "ad_name": r["ad_name"],
                "bucket": r["bucket"],
                "reason": r["reason"],
            }
            for r in result["pause_list"]
        ],
        "spawns": result["spawns"],
        "applied": [],
        "apply_errors": [],
    }

    if args.apply and plan["pause"]:
        print(f"\nApplying pauses ({len(plan['pause'])})...")
        for p in plan["pause"]:
            ok = meta_api.set_ad_status(p["ad_id"], "PAUSED")
            if ok:
                plan["applied"].append(p["ad_id"])
            else:
                plan["apply_errors"].append(p["ad_id"])
    elif args.apply:
        print("\nNothing to pause.")

    plan_path = out_dir / "plan.json"
    summary_path = out_dir / "summary.md"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    write_summary(summary_path, plan)

    print(f"\n{'#':<3} {'Bucket':<10} {'Act':<6} {'Spend':>8} {'Purch':>5} "
          f"{'ROAS':>6}  Name")
    print("-" * 90)
    for r in result["rows"]:
        print(
            f"{'':3} {r['bucket']:<10} {r['action']:<6} "
            f"£{r['spend']:>7.2f} {r['purchases']:>5} {r['roas']:>6.2f}  "
            f"{(r['ad_name'] or '')[:48]}"
        )

    print(f"\nSpend £{cycle_spend:.2f} · keep {result['remaining_active']} · "
          f"pause {len(result['pause_list'])} · spawn {result['spawn_slots']}")
    if skip_recommended:
        print(f"NOTE: spend < £{args.min_cycle_spend:.0f} — consider skipping this cycle.")
    if result["cap_overflow"]:
        print(f"NOTE: {result['cap_overflow']} over cap after cuts "
              "(winners/learning) — review manually.")
    print(f"\nSaved → {plan_path}")
    print(f"        {summary_path}")
    if not args.apply and plan["pause"]:
        print("Dry-run only. Re-run with --apply to pause recommended ads.")


if __name__ == "__main__":
    main()
