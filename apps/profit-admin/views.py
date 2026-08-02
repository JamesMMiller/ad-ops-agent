"""Saved desk views under outputs/profit-admin/views/."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import views_dir


def _ts_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_slug(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", (name or "").strip())[:48].strip("-")
    return slug or "view"


def list_views(limit: int = 100) -> list[dict[str, str]]:
    vdir = views_dir()
    files = sorted(vdir.glob("*.json"), reverse=True)
    out: list[dict[str, str]] = []
    for p in files[:limit]:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            out.append({"id": p.stem, "name": p.stem, "updated_at": ""})
            continue
        out.append(
            {
                "id": data.get("id") or p.stem,
                "name": data.get("name") or p.stem,
                "updated_at": data.get("updated_at") or "",
            }
        )
    out.sort(key=lambda r: r.get("updated_at") or r.get("id") or "", reverse=True)
    return out


def read_view(view_id: str) -> dict[str, Any] | None:
    path = views_dir() / f"{view_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_view(payload: dict[str, Any], view_id: str | None = None) -> dict[str, Any]:
    """Create or overwrite a view. Stores filters/config only."""
    name = str(payload.get("name") or "Untitled view").strip() or "Untitled view"
    sid = view_id or payload.get("id") or f"{_ts_id()}-{_safe_slug(name)}"
    now = _now_iso()
    existing = read_view(sid) if view_id or payload.get("id") else None
    body = {
        **payload,
        "id": sid,
        "name": name,
        "updated_at": now,
        "created_at": payload.get("created_at")
        or (existing or {}).get("created_at")
        or now,
    }
    path = views_dir() / f"{sid}.json"
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
    return body


def delete_view(view_id: str) -> bool:
    path = views_dir() / f"{view_id}.json"
    if not path.exists():
        return False
    path.unlink()
    return True


def pin_ads_report(report: dict[str, Any], label: str | None = None) -> Path:
    """Write Ads Apply JSON under outputs/profit-admin/reports/ for profit-ops."""
    from config import reports_dir

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = _safe_slug(label or "ads")
    path = reports_dir() / f"{stamp}-{slug}.json"
    # Avoid clobber: append short suffix if exists
    if path.exists():
        path = reports_dir() / f"{stamp}-{slug}-{_ts_id()[-6:]}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
