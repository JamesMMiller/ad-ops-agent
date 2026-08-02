"""
Shared Meta Marketing API helpers for the meta-ad-builder skill.

Distilled from the Ad Builder Agent deploy scripts: image/video upload,
video-processing polling, and ad creation with transient-error retry/backoff.

Credentials come from environment (load a .env first with python-dotenv):
  META_ACCESS_TOKEN   (required) — long-lived user/system token, ads_management scope
  META_AD_ACCOUNT_ID  (required) — with or without the act_ prefix
  META_API_VERSION    (optional) — Graph API version, default v25.0
  META_PIXEL_ID       (optional) — Pixel / dataset ID for CAPI + tracking
  META_CAPI_ACCESS_TOKEN (optional) — dedicated Conversions API token;
                          falls back to META_ACCESS_TOKEN when unset
"""

import base64
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

API_VERSION = os.getenv("META_API_VERSION", "v25.0")
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"


def get_pixel_id() -> str:
    pixel = (os.getenv("META_PIXEL_ID") or "").strip()
    if not pixel:
        raise RuntimeError("META_PIXEL_ID not set — see check-meta-env.sh / .env.example")
    return pixel


def get_capi_access_token() -> str:
    """Prefer a dedicated CAPI token; fall back to the Marketing API token."""
    token = (os.getenv("META_CAPI_ACCESS_TOKEN") or "").strip()
    if token:
        return token
    return get_access_token()


def sha256_norm(value: str | None) -> str | None:
    """Normalize then SHA-256 hash a customer match key. Returns None if empty."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_phone(phone: str | None, default_country: str = "44") -> str | None:
    """Digits-only E.164-ish phone for Meta hashing (country code required)."""
    if not phone:
        return None
    digits = re.sub(r"\D+", "", str(phone))
    if not digits:
        return None
    # UK local numbers often start with 0 — strip and prefix 44
    if digits.startswith("0") and default_country == "44":
        digits = default_country + digits.lstrip("0")
    elif not digits.startswith(default_country) and len(digits) <= 10 and default_country == "44":
        digits = default_country + digits
    return digits or None


def normalize_order_event_id(order_id: str | int | None) -> str:
    """Stable Meta event_id from a Shopify order id (numeric string, no # / gid)."""
    if order_id is None:
        raise ValueError("order_id is required for event_id")
    text = str(order_id).strip()
    if text.startswith("gid://"):
        text = text.rsplit("/", 1)[-1]
    text = text.lstrip("#").strip()
    # OrderIdentity / Order numeric
    if not text.isdigit():
        m = re.search(r"(\d+)$", text)
        if m:
            text = m.group(1)
    if not text:
        raise ValueError(f"Could not normalize order_id={order_id!r}")
    return text


def extract_fbclid(url: str | None) -> str | None:
    if not url:
        return None
    try:
        qs = parse_qs(urlparse(url).query)
    except Exception:
        return None
    vals = qs.get("fbclid") or []
    return vals[0] if vals else None


def build_fbc_from_fbclid(fbclid: str, creation_time_ms: int | None = None) -> str:
    ts = creation_time_ms if creation_time_ms is not None else int(time.time() * 1000)
    return f"fb.1.{ts}.{fbclid}"


def send_capi_events(
    events: list[dict[str, Any]],
    *,
    pixel_id: str | None = None,
    access_token: str | None = None,
    test_event_code: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """POST one or more events to Meta Conversions API.

    dry_run=True returns the redacted payload without calling Meta.
    """
    pixel = pixel_id or get_pixel_id()
    token = access_token or get_capi_access_token()
    body: dict[str, Any] = {"data": events}
    if test_event_code:
        body["test_event_code"] = test_event_code

    url = f"{BASE_URL}/{pixel}/events"
    if dry_run:
        return {
            "dry_run": True,
            "url": url,
            "pixel_id": pixel,
            "event_count": len(events),
            "event_names": [e.get("event_name") for e in events],
            "event_ids": [e.get("event_id") for e in events],
            "has_test_event_code": bool(test_event_code),
            # Never echo user_data / tokens
            "custom_data_keys": [
                sorted((e.get("custom_data") or {}).keys()) for e in events
            ],
            "user_data_keys": [
                sorted((e.get("user_data") or {}).keys()) for e in events
            ],
        }

    resp = requests.post(
        url,
        params={"access_token": token},
        json=body,
        timeout=60,
    )
    try:
        data = resp.json()
    except json.JSONDecodeError:
        raise RuntimeError(f"CAPI non-JSON HTTP {resp.status_code}: {resp.text[:400]}")
    if resp.status_code >= 400 or "error" in data:
        err = data.get("error") or data
        raise RuntimeError(f"CAPI error HTTP {resp.status_code}: {json.dumps(err)[:800]}")
    return data


def pixel_event_totals(
    *,
    pixel_id: str | None = None,
    start_unix: int | None = None,
    end_unix: int | None = None,
    days: int = 7,
) -> dict[str, Any]:
    """Aggregate event counts for a pixel (last N days, max 7 per Meta stats API)."""
    pixel = pixel_id or get_pixel_id()
    end = end_unix if end_unix is not None else int(time.time())
    start = start_unix if start_unix is not None else end - min(days, 7) * 86400
    token = get_access_token()
    url = f"{BASE_URL}/{pixel}/stats"
    resp = requests.get(
        url,
        params={
            "access_token": token,
            "aggregation": "event_total_counts",
            "start_time": start,
            "end_time": end,
        },
        timeout=60,
    )
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"Pixel stats error: {json.dumps(data['error'])[:500]}")
    counts: dict[str, int] = {}
    for block in data.get("data") or []:
        for row in block.get("data") or []:
            name = row.get("value")
            if not name:
                continue
            counts[name] = counts.get(name, 0) + int(row.get("count") or 0)
    return {
        "pixel_id": pixel,
        "start_unix": start,
        "end_unix": end,
        "counts": counts,
        "purchase": counts.get("Purchase", 0),
    }


def get_access_token():
    token = os.getenv("META_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("META_ACCESS_TOKEN not set — see check-meta-env.sh")
    return token


def get_ad_account_id():
    acct = os.getenv("META_AD_ACCOUNT_ID")
    if not acct:
        raise RuntimeError("META_AD_ACCOUNT_ID not set — see check-meta-env.sh")
    return acct if acct.startswith("act_") else f"act_{acct}"


def resolve_output_dir(run_slug):
    """Resolve a per-run output directory.

    Honors OUTPUT_BASE (set by the gen-ai-core workspace); otherwise writes
    under ./outputs/meta-ads/ — both are gitignored, so account-specific ad
    IDs and pulled performance data never land in version control.
    """
    base = os.getenv("OUTPUT_BASE")
    root = Path(base) if base else Path("outputs/meta-ads")
    run_dir = root / run_slug
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def upload_image(path, name=None):
    """Upload an image to /adimages (base64). Returns the image hash."""
    path = Path(path)
    if not path.exists():
        print(f"  ERROR: image not found: {path}")
        return None
    with open(path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
    url = f"{BASE_URL}/{get_ad_account_id()}/adimages"
    resp = requests.post(
        url,
        data={
            "access_token": get_access_token(),
            "bytes": img_b64,
            "name": (name or path.stem)[:90],
        },
        timeout=120,
    )
    data = resp.json()
    if "images" in data:
        h = list(data["images"].values())[0].get("hash")
        print(f"  Uploaded image. hash={h}")
        return h
    print(f"  Upload error: {json.dumps(data, indent=2)[:500]}")
    return None


def upload_video(path):
    """Upload a video to /advideos (multipart). Returns the video_id."""
    path = Path(path)
    if not path.exists():
        print(f"  ERROR: video not found: {path}")
        return None
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"  Uploading {path.name} ({size_mb:.1f} MB)...")
    url = f"{BASE_URL}/{get_ad_account_id()}/advideos"
    with open(path, "rb") as f:
        files = {"source": (path.name, f, "video/mp4")}
        data = {"access_token": get_access_token(), "name": path.name}
        resp = requests.post(url, data=data, files=files, timeout=900)
    if resp.status_code != 200:
        print(f"  ERROR HTTP {resp.status_code}: {resp.text[:500]}")
        return None
    result = resp.json()
    if "error" in result:
        print(f"  ERROR uploading: {json.dumps(result['error'], indent=2)}")
        return None
    vid = result.get("id")
    print(f"  Video uploaded: {vid}")
    return vid


def wait_for_video_processing(video_id, max_wait=360):
    """Poll a video until processing completes. Returns a thumbnail URL.

    Meta rejects video-ad creation until the video is fully processed; the
    returned thumbnail is required by video_data.image_url.
    """
    print("  Waiting for video processing...")
    url = f"{BASE_URL}/{video_id}"
    for attempt in range(max_wait // 10):
        time.sleep(10)
        resp = requests.get(url, params={
            "access_token": get_access_token(),
            "fields": "status,picture,thumbnails{uri,is_preferred}",
        })
        data = resp.json()
        if "error" in data:
            print(f"    Poll error: {data['error'].get('message', '?')}")
            continue
        status = data.get("status", {})
        phase = status.get("processing_phase", {}).get("status", "unknown")
        video_status = status.get("video_status", "unknown")
        elapsed = (attempt + 1) * 10
        print(f"    {elapsed}s: phase={phase}, video_status={video_status}")
        if phase == "complete" and video_status == "ready":
            thumbs = data.get("thumbnails", {}).get("data", [])
            preferred = next((t for t in thumbs if t.get("is_preferred")), None)
            return (preferred or {}).get("uri") or data.get("picture")
    print("  WARNING: processing timed out. Falling back to picture.")
    resp = requests.get(url, params={"access_token": get_access_token(), "fields": "picture"})
    return resp.json().get("picture")


def list_ads(adset_id, status_filter=None):
    """List ads in an ad set. Returns [{id, name, status, effective_status}, ...].

    status_filter: optional list of effective_status values to keep
    (e.g. ["ACTIVE"]). When None, returns all ads.
    """
    url = f"{BASE_URL}/{adset_id}/ads"
    params = {
        "access_token": get_access_token(),
        "fields": "id,name,status,effective_status",
        "limit": 100,
    }
    ads = []
    while url:
        resp = requests.get(url, params=params, timeout=60)
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"list_ads error: {json.dumps(data['error'])}")
        ads.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        params = None
    if status_filter is not None:
        allowed = set(status_filter)
        ads = [a for a in ads if a.get("effective_status") in allowed]
    return ads


def get_adset(adset_id):
    """Fetch ad set id + name."""
    url = f"{BASE_URL}/{adset_id}"
    resp = requests.get(
        url,
        params={"access_token": get_access_token(), "fields": "id,name,status"},
        timeout=60,
    )
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"get_adset error: {json.dumps(data['error'])}")
    return data


def set_ad_status(ad_id, status):
    """Set an ad's status (PAUSED or ACTIVE). Returns True on success.

    Prefer PAUSED for iteration cuts. Do not call with ACTIVE unless the user
    explicitly asked to un-pause.
    """
    if status not in ("PAUSED", "ACTIVE"):
        raise ValueError(f"status must be PAUSED or ACTIVE, got {status!r}")
    url = f"{BASE_URL}/{ad_id}"
    for attempt in range(1, 5):
        resp = requests.post(
            url,
            data={"access_token": get_access_token(), "status": status},
            timeout=60,
        )
        data = resp.json()
        if data.get("success") is True or ("error" not in data and resp.status_code == 200):
            print(f"  Set ad {ad_id} → {status}")
            return True
        err = data.get("error") or {}
        if err.get("is_transient") and attempt < 4:
            backoff = min(60, 5 * (2 ** (attempt - 1)))
            print(f"  Transient error pausing {ad_id}. Retry {attempt}/4 in {backoff}s.")
            time.sleep(backoff)
            continue
        print(f"  ERROR set_ad_status {ad_id}: {json.dumps(err or data, indent=2)}")
        return False
    return False


def create_ad(adset_id, ad_name, creative, status="PAUSED", pixel_id=None):
    """Create an ad in an ad set. Retries transient OAuthException errors.

    status defaults to PAUSED — the skill never launches spending ads
    automatically. The user reviews and un-pauses in Ads Manager.
    """
    url = f"{BASE_URL}/{get_ad_account_id()}/ads"
    payload = {
        "access_token": get_access_token(),
        "adset_id": adset_id,
        "name": ad_name,
        "status": status,
        "creative": json.dumps(creative),
    }
    if pixel_id:
        payload["tracking_specs"] = json.dumps([{
            "action.type": ["offsite_conversion"],
            "fb_pixel": [pixel_id],
        }])

    for attempt in range(1, 5):
        resp = requests.post(url, data=payload)
        data = resp.json()
        if "error" not in data:
            ad_id = data["id"]
            print(f"  Created ad: {ad_id} ({ad_name}) [status={status}]")
            return ad_id
        err = data["error"]
        if err.get("is_transient") and attempt < 4:
            backoff = min(60, 5 * (2 ** (attempt - 1)))
            print(f"  Transient error (code {err.get('code')}). Retry {attempt}/4 in {backoff}s.")
            time.sleep(backoff)
            continue
        print(f"  ERROR creating ad: {json.dumps(err, indent=2)}")
        return None
    return None
