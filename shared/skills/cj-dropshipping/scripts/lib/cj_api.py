"""
CJ Dropshipping API helpers.

Auth: POST apiKey → accessToken (header CJ-Access-Token).
Docs: https://developers.cjdropshipping.cn/en/api/api2/api/auth.html

Env:
  CJ_API_KEY          — required (from CJ personal center → API)
  CJ_BASE_URL         — optional, default https://developers.cjdropshipping.com/api2.0
  CJ_TOKEN_CACHE      — optional path for access/refresh token cache (default .cache/cj-token.json)
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

DEFAULT_BASE = "https://developers.cjdropshipping.com/api2.0"


def get_base_url() -> str:
    return (os.getenv("CJ_BASE_URL") or DEFAULT_BASE).rstrip("/")


def get_api_key() -> str:
    key = (os.getenv("CJ_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("CJ_API_KEY not set — add it to .env (see .env.example)")
    return key


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here, *here.parents]:
        if (p / ".env").exists() or (p / ".git").exists():
            return p
    return Path.cwd()


def _token_cache_path() -> Path:
    raw = (os.getenv("CJ_TOKEN_CACHE") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return _repo_root() / ".cache" / "cj-token.json"


def _load_cache() -> dict[str, Any]:
    path = _token_cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _save_cache(data: dict[str, Any]) -> None:
    path = _token_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _parse_expiry(iso: str | None) -> float:
    if not iso:
        return 0.0
    # e.g. 2021-08-18T09:16:33+08:00
    try:
        from datetime import datetime

        return datetime.fromisoformat(iso).timestamp()
    except Exception:
        return 0.0


def fetch_access_token(force: bool = False) -> str:
    """Exchange CJ_API_KEY for accessToken; cache on disk."""
    cache = _load_cache()
    now = time.time()
    if (
        not force
        and cache.get("accessToken")
        and _parse_expiry(cache.get("accessTokenExpiryDate")) > now + 3600
    ):
        return cache["accessToken"]

    # Try refresh first
    if not force and cache.get("refreshToken") and _parse_expiry(
        cache.get("refreshTokenExpiryDate")
    ) > now + 60:
        resp = requests.post(
            f"{get_base_url()}/v1/authentication/refreshAccessToken",
            headers={"Content-Type": "application/json"},
            json={"refreshToken": cache["refreshToken"]},
            timeout=60,
        )
        payload = resp.json()
        if resp.status_code == 200 and payload.get("code") == 200 and payload.get("data"):
            data = payload["data"]
            cache.update(
                {
                    "accessToken": data.get("accessToken"),
                    "accessTokenExpiryDate": data.get("accessTokenExpiryDate"),
                    "refreshToken": data.get("refreshToken") or cache.get("refreshToken"),
                    "refreshTokenExpiryDate": data.get("refreshTokenExpiryDate")
                    or cache.get("refreshTokenExpiryDate"),
                }
            )
            _save_cache(cache)
            return cache["accessToken"]

    resp = requests.post(
        f"{get_base_url()}/v1/authentication/getAccessToken",
        headers={"Content-Type": "application/json"},
        json={"apiKey": get_api_key()},
        timeout=60,
    )
    payload = resp.json()
    if resp.status_code != 200 or payload.get("code") != 200 or not payload.get("data"):
        raise RuntimeError(
            f"CJ getAccessToken failed HTTP {resp.status_code}: {json.dumps(payload)[:500]}"
        )
    data = payload["data"]
    cache = {
        "accessToken": data["accessToken"],
        "accessTokenExpiryDate": data.get("accessTokenExpiryDate"),
        "refreshToken": data.get("refreshToken"),
        "refreshTokenExpiryDate": data.get("refreshTokenExpiryDate"),
        "openId": data.get("openId"),
    }
    _save_cache(cache)
    return cache["accessToken"]


_last_request_at = 0.0


def _throttle(min_interval: float = 1.05) -> None:
    """CJ enforces QPS = 1."""
    global _last_request_at
    now = time.time()
    wait = min_interval - (now - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.time()


def cj_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    token = fetch_access_token()
    # Drop None values; stringify bools as CJ expects
    clean: dict[str, Any] = {}
    for k, v in (params or {}).items():
        if v is None or v == "":
            continue
        if isinstance(v, bool):
            clean[k] = "true" if v else "false"
        else:
            clean[k] = v
    url = f"{get_base_url()}{path}"
    if clean:
        url = f"{url}?{urlencode(clean, doseq=True)}"

    def _do(tok: str) -> tuple[requests.Response, dict[str, Any]]:
        _throttle()
        r = requests.get(url, headers={"CJ-Access-Token": tok}, timeout=60)
        return r, r.json()

    resp, payload = _do(token)
    # Retry once on rate limit
    if resp.status_code == 429 or payload.get("code") == 1600200:
        time.sleep(1.2)
        resp, payload = _do(token)
    if resp.status_code == 401 or payload.get("code") in (1600001, 1600003):
        token = fetch_access_token(force=True)
        resp, payload = _do(token)
    if resp.status_code != 200 or payload.get("code") != 200:
        raise RuntimeError(
            f"CJ GET {path} failed HTTP {resp.status_code}: {json.dumps(payload)[:800]}"
        )
    return payload


def search_products(
    *,
    key_word: str | None = None,
    country_code: str | None = None,
    is_warehouse: bool | None = True,
    verified_warehouse: int | None = 1,
    min_inventory: int | None = 10,
    page: int = 1,
    size: int = 20,
    zone_platform: str | None = "shopify",
    start_sell_price: float | None = None,
    end_sell_price: float | None = None,
) -> dict[str, Any]:
    """Search via listV2 with UK/EU-friendly defaults."""
    return cj_get(
        "/v1/product/listV2",
        {
            "keyWord": key_word,
            "countryCode": country_code,
            "isWarehouse": is_warehouse,
            "verifiedWarehouse": verified_warehouse,
            "startWarehouseInventory": min_inventory,
            "page": page,
            "size": size,
            "zonePlatform": zone_platform,
            "startSellPrice": start_sell_price,
            "endSellPrice": end_sell_price,
            "orderBy": 4,  # inventory
            "sort": "desc",
        },
    )


def flatten_list_v2(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize listV2 nested content → flat product dicts."""
    data = payload.get("data") or {}
    out: list[dict[str, Any]] = []
    content = data.get("content") or []
    # Two shapes observed in docs: content[].productList[] OR content as product rows
    for block in content:
        if isinstance(block, dict) and "productList" in block:
            out.extend(block.get("productList") or [])
        elif isinstance(block, dict) and block.get("id"):
            out.append(block)
    # Some responses put products under data.list
    if not out and isinstance(data.get("list"), list):
        out = data["list"]
    return out
