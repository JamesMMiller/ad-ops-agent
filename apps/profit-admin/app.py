"""
Profit Admin — local ops dashboard (embed-ready API).

Run from repo root:
  python -m venv .venv-profit && source .venv-profit/bin/activate
  pip install -r apps/profit-admin/requirements.txt
  uvicorn app:app --app-dir apps/profit-admin --reload --port 8787

Or:
  cd apps/profit-admin && uvicorn app:app --reload --port 8787
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from auth import AuthDep
from config import kie_log_path, port, repo_root
from pnl import build_product_pnl
from refresh import run_refresh
from snapshots import list_snapshots, read_latest, read_snapshot

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Our Tech Profit Admin", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


def _with_product_pnl(payload: dict) -> dict:
    """Backfill product dig-in for snapshots saved before this field existed."""
    if payload.get("product_pnl") is not None:
        return payload
    shopify = (payload.get("sources") or {}).get("shopify")
    if shopify:
        payload = {**payload, "product_pnl": build_product_pnl(shopify)}
    else:
        payload = {**payload, "product_pnl": []}
    return payload


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health(_auth: AuthDep) -> dict:
    root = repo_root()
    shopify_ok = bool(
        __import__("os").getenv("SHOPIFY_SHOP")
        and __import__("os").getenv("SHOPIFY_CLIENT_ID")
        and __import__("os").getenv("SHOPIFY_CLIENT_SECRET")
    )
    meta_ok = bool(
        __import__("os").getenv("META_ACCESS_TOKEN")
        and __import__("os").getenv("META_AD_ACCOUNT_ID")
    )
    kie_ok = kie_log_path().exists()
    latest = read_latest()
    return {
        "ok": True,
        "port_default": port(),
        "repo": str(root),
        "connectors": {
            "shopify_env": shopify_ok,
            "meta_env": meta_ok,
            "kie_log": kie_ok,
        },
        "has_snapshot": latest is not None,
        "last_refreshed_at": (latest or {}).get("refreshed_at"),
    }


@app.post("/api/refresh")
def refresh(_auth: AuthDep) -> dict:
    try:
        return run_refresh()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/snapshot/latest")
def snapshot_latest(_auth: AuthDep) -> dict:
    latest = read_latest()
    if not latest:
        raise HTTPException(status_code=404, detail="No snapshot yet — hit Refresh")
    return _with_product_pnl(latest)


@app.get("/api/snapshots")
def snapshots(_auth: AuthDep) -> dict:
    return {"snapshots": list_snapshots()}


@app.get("/api/snapshot/{snapshot_id}")
def snapshot_one(snapshot_id: str, _auth: AuthDep) -> dict:
    snap = read_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return _with_product_pnl(snap)
