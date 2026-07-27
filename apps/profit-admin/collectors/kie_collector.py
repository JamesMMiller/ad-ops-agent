"""KIE credit burn from logs/kie-api.jsonl."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from config import kie_log_path, kie_usd_per_credit, repo_root


def collect_kie(*, usdgbp: float) -> dict[str, Any]:
    path = kie_log_path()
    by_day: dict[str, float] = defaultdict(float)
    by_model: dict[str, float] = defaultdict(float)
    charged_calls = 0

    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            resp = o.get("response") or {}
            cr = resp.get("creditsCharged")
            if cr is None:
                cr = resp.get("creditsConsumed")
            try:
                cr_f = float(cr or 0)
            except (TypeError, ValueError):
                cr_f = 0.0
            if cr_f <= 0:
                continue
            ts = (o.get("timestamp") or "")[:10]
            if not ts:
                continue
            model = o.get("model") or "unknown"
            by_day[ts] += cr_f
            by_model[model] += cr_f
            charged_calls += 1

    usd_per = kie_usd_per_credit()
    days = []
    total_credits = 0.0
    for day in sorted(by_day):
        cr = by_day[day]
        total_credits += cr
        gbp = cr * usd_per * usdgbp
        days.append(
            {
                "date": day,
                "credits": round(cr, 2),
                "gbp": round(gbp, 2),
            }
        )

    try:
        rel = str(path.relative_to(repo_root()))
    except ValueError:
        rel = str(path)

    return {
        "log_path": rel,
        "log_exists": path.exists(),
        "usd_per_credit": usd_per,
        "usdgbp": usdgbp,
        "total_credits": round(total_credits, 2),
        "total_gbp": round(total_credits * usd_per * usdgbp, 2),
        "charged_calls": charged_calls,
        "by_model": {k: round(v, 2) for k, v in sorted(by_model.items(), key=lambda x: -x[1])},
        "days": days,
    }
