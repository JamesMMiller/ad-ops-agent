"""Profit Admin configuration from repo-root .env."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def repo_root() -> Path:
    return ROOT


def snapshots_dir() -> Path:
    d = ROOT / "outputs" / "profit-admin" / "snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def views_dir() -> Path:
    d = ROOT / "outputs" / "profit-admin" / "views"
    d.mkdir(parents=True, exist_ok=True)
    return d


def reports_dir() -> Path:
    d = ROOT / "outputs" / "profit-admin" / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def kie_log_path() -> Path:
    return ROOT / "logs" / "kie-api.jsonl"


def port() -> int:
    return int(os.getenv("PROFIT_ADMIN_PORT", "8787"))


def shopify_monthly_gbp() -> float:
    return float(os.getenv("SHOPIFY_MONTHLY_GBP", "25"))


def kie_usd_per_credit() -> float:
    return float(os.getenv("KIE_USD_PER_CREDIT", "0.005"))


def fee_pct() -> float:
    return float(os.getenv("PROFIT_FEE_PCT", "0.015"))


def fee_fixed_gbp() -> float:
    return float(os.getenv("PROFIT_FEE_FIXED_GBP", "0.25"))


def usdgbp() -> float | None:
    raw = (os.getenv("USDGBP") or "").strip()
    if not raw:
        return None
    return float(raw)


def resolve_usdgbp() -> float:
    """Env override, else live rate, else last-known fallback."""
    override = usdgbp()
    if override is not None:
        return override
    try:
        import requests

        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15)
        r.raise_for_status()
        rate = float(r.json()["rates"]["GBP"])
        if rate > 0:
            return rate
    except Exception:
        pass
    return 0.749517
