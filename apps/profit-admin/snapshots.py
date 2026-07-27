"""Snapshot persistence under outputs/profit-admin/snapshots/."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import snapshots_dir


def _ts_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def write_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    snap_dir = snapshots_dir()
    sid = _ts_id()
    payload = {**payload, "snapshot_id": sid}
    path = snap_dir / f"{sid}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    latest = snap_dir / "latest.json"
    latest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def read_latest() -> dict[str, Any] | None:
    path = snapshots_dir() / "latest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_snapshots(limit: int = 50) -> list[dict[str, str]]:
    snap_dir = snapshots_dir()
    files = sorted(
        (p for p in snap_dir.glob("*.json") if p.name != "latest.json"),
        reverse=True,
    )
    out: list[dict[str, str]] = []
    for p in files[:limit]:
        out.append({"id": p.stem, "file": p.name})
    return out


def read_snapshot(snapshot_id: str) -> dict[str, Any] | None:
    path = snapshots_dir() / f"{snapshot_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
