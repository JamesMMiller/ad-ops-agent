#!/usr/bin/env python3
"""
Capture Ad Library creative assets (image/video) for local research browsing.

Meta's ads_archive API does **not** return media file URLs — only ad_snapshot_url.
This script opens each snapshot in headless Chromium (Playwright), extracts the
creative image/video CDN URLs, and downloads them under:

  <run-dir>/media/<ad_id>/preview.jpg   (or .png / poster)
  <run-dir>/media/<ad_id>/video.mp4     (when present)
  <run-dir>/media/<ad_id>/meta.json
  <run-dir>/media/index.json

Then rebuild the browser:

  python build-ad-library-browser.py --run-dir <run-dir>

Usage:
  python enrich-ad-library-media.py --run-dir outputs/research/2026-07-24-ad-library-full --limit 40
  python enrich-ad-library-media.py --run-dir ... --min-days 10 --categories neck_fan,charger
  python enrich-ad-library-media.py --run-dir ... --ids 991459206853037,123

Requires: pip install playwright && playwright install chromium
Analysis-only use — comply with Meta Ad Library / data storage terms.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent / "lib"))
load_dotenv()

import meta_api  # noqa: E402

SKIP_HOST_FRAGMENTS = (
    "cookie",
    "hsts-pixel",
    "/images/cookies/",
    "static.xx.fbcdn.net/rsrc.php",
)
MIN_PREVIEW_EDGE = 120


def load_ads(run_dir: Path) -> list[dict]:
    browser = run_dir / "browser-data.json"
    if browser.exists():
        data = json.loads(browser.read_text())
        return list(data.get("ads") or [])

    # Fallback: import builder module (hyphenated filename)
    import importlib.util

    builder = Path(__file__).parent / "build-ad-library-browser.py"
    spec = importlib.util.spec_from_file_location("adlib_browser_builder", builder)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    ads, _ = mod.collect_ads(run_dir)
    return ads


def fresh_snapshot_url(ad_id: str, page_id: str | None, token: str, country: str) -> str:
    """Prefer a freshly minted snapshot URL (tokens expire)."""
    if page_id:
        params = {
            "access_token": token,
            "search_page_ids": page_id,
            "ad_reached_countries": country,
            "ad_active_status": "ALL",
            "fields": "id,ad_snapshot_url",
            "limit": 50,
        }
        try:
            resp = requests.get(
                f"{meta_api.BASE_URL}/ads_archive", params=params, timeout=40
            )
            data = resp.json()
            for item in data.get("data") or []:
                if str(item.get("id")) == str(ad_id) and item.get("ad_snapshot_url"):
                    return item["ad_snapshot_url"]
        except Exception:
            pass
    return (
        f"https://www.facebook.com/ads/archive/render_ad/"
        f"?id={ad_id}&access_token={token}"
    )


def should_skip_url(url: str) -> bool:
    low = (url or "").lower()
    if not low.startswith("http"):
        return True
    return any(frag in low for frag in SKIP_HOST_FRAGMENTS)


def pick_best_image(imgs: list[dict]) -> dict | None:
    scored = []
    for img in imgs:
        src = img.get("src") or ""
        if should_skip_url(src):
            continue
        w = int(img.get("w") or 0)
        h = int(img.get("h") or 0)
        if max(w, h) < MIN_PREVIEW_EDGE and "scontent" not in src and "fbcdn" not in src:
            continue
        # Prefer larger creatives; boost scontent/fbcdn
        score = (w * h) + (50_000 if ("scontent" in src or "fbcdn" in src) else 0)
        # Prefer non-tiny thumbs
        if "s60x60" in src or "p64x64" in src:
            score *= 0.2
        scored.append((score, img))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def pick_best_video(vids: list[dict]) -> dict | None:
    for v in vids:
        src = v.get("src") or ""
        if src and not should_skip_url(src):
            return v
    return None


def download(url: str, dest: Path, timeout: int = 90) -> bool:
    try:
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
        return dest.exists() and dest.stat().st_size > 0
    except Exception as exc:
        print(f"    download failed: {exc}")
        return False


def guess_ext(url: str, default: str) -> str:
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".mp4", ".webm"):
        if ext in path:
            return ext if ext != ".jpeg" else ".jpg"
    return default


def dismiss_overlays(page) -> None:
    selectors = [
        'button:has-text("Allow all cookies")',
        'button:has-text("Accept all")',
        'button:has-text("Accept All")',
        'button:has-text("Decline optional cookies")',
        'button:has-text("Only allow essential cookies")',
        '[data-testid="cookie-policy-manage-dialog-accept-button"]',
        '[aria-label="Close"]',
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=400):
                loc.click(timeout=1000)
                time.sleep(0.4)
        except Exception:
            continue


def capture_ad(page, snapshot_url: str) -> dict:
    page.goto(snapshot_url, wait_until="domcontentloaded", timeout=60000)
    dismiss_overlays(page)
    try:
        page.wait_for_selector("img, video", timeout=15000)
    except Exception:
        pass
    time.sleep(1.5)
    dismiss_overlays(page)
    media = page.evaluate(
        """() => {
      const imgs = [...document.querySelectorAll('img')].map(i => ({
        src: i.currentSrc || i.src,
        w: i.naturalWidth || 0,
        h: i.naturalHeight || 0,
        alt: i.alt || ''
      }));
      const vids = [...document.querySelectorAll('video')].map(v => ({
        src: v.currentSrc || v.src || '',
        poster: v.poster || ''
      }));
      return { imgs, vids, title: document.title, text: (document.body.innerText || '').slice(0, 400) };
    }"""
    )
    return media


def main():
    parser = argparse.ArgumentParser(description="Enrich Ad Library research with creative media")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--min-days", type=int, default=0)
    parser.add_argument("--categories", default="",
                        help="Comma-separated category ids (substring match)")
    parser.add_argument("--ids", default="", help="Comma-separated ad ids only")
    parser.add_argument("--country", default="GB")
    parser.add_argument("--rebuild-browser", action="store_true",
                        help="Run build-ad-library-browser.py after enrich")
    parser.add_argument("--force", action="store_true", help="Re-download even if media exists")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed.", file=sys.stderr)
        print("  .venv/bin/pip install playwright && .venv/bin/playwright install chromium",
              file=sys.stderr)
        sys.exit(1)

    run_dir = Path(args.run_dir).resolve()
    media_root = run_dir / "media"
    media_root.mkdir(parents=True, exist_ok=True)

    ads = load_ads(run_dir)
    id_filter = {x.strip() for x in args.ids.split(",") if x.strip()}
    cat_filter = {x.strip() for x in args.categories.split(",") if x.strip()}

    candidates = []
    for ad in ads:
        if id_filter and ad.get("id") not in id_filter:
            continue
        if (ad.get("days_live") or 0) < args.min_days:
            continue
        if cat_filter:
            cats = {c.strip() for c in (ad.get("category") or "").split(",") if c.strip()}
            if not (cats & cat_filter):
                continue
        candidates.append(ad)

    candidates.sort(
        key=lambda a: (a.get("days_live") is None, -(a.get("days_live") or 0)),
    )
    candidates = candidates[: args.limit]
    print(f"Enriching {len(candidates)} ads → {media_root}")

    token = meta_api.get_access_token()
    index_path = media_root / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {"ads": {}}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 1800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        for i, ad in enumerate(candidates, 1):
            ad_id = ad["id"]
            dest = media_root / ad_id
            meta_file = dest / "meta.json"
            if meta_file.exists() and not args.force:
                print(f"[{i}/{len(candidates)}] skip existing {ad_id} ({ad.get('page_name')})")
                index["ads"][ad_id] = json.loads(meta_file.read_text())
                continue

            print(f"[{i}/{len(candidates)}] {ad.get('page_name')} · {ad_id} · {ad.get('days_live')}d")
            snap = fresh_snapshot_url(ad_id, ad.get("page_id"), token, args.country)
            try:
                media = capture_ad(page, snap)
            except Exception as exc:
                print(f"  capture error: {exc}")
                continue

            best_vid = pick_best_video(media.get("vids") or [])
            best_img = pick_best_image(media.get("imgs") or [])
            if not best_img and best_vid and best_vid.get("poster"):
                best_img = {"src": best_vid["poster"], "w": 0, "h": 0}

            dest.mkdir(parents=True, exist_ok=True)
            # Full-page fallback screenshot always helps browsing
            shot = dest / "snapshot.png"
            try:
                page.screenshot(path=str(shot), full_page=False)
            except Exception:
                shot = None

            entry = {
                "id": ad_id,
                "page_name": ad.get("page_name"),
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "has_video": False,
                "has_image": False,
                "preview": None,
                "video": None,
                "snapshot_png": None,
                "source_image_url": None,
                "source_video_url": None,
            }

            if best_vid and best_vid.get("src"):
                ext = guess_ext(best_vid["src"], ".mp4")
                vpath = dest / f"video{ext}"
                if download(best_vid["src"], vpath):
                    entry["has_video"] = True
                    entry["video"] = f"media/{ad_id}/{vpath.name}"
                    entry["source_video_url"] = best_vid["src"]
                    print(f"  video → {vpath.name}")

            # Prefer video poster over tiny profile/list thumbs.
            poster = (best_vid or {}).get("poster") if best_vid else None
            image_src = None
            if poster and not should_skip_url(poster) and "s60x60" not in poster:
                image_src = poster
            elif best_img and best_img.get("src"):
                image_src = best_img["src"]

            if image_src:
                ext = guess_ext(image_src, ".jpg")
                ipath = dest / f"preview{ext}"
                if download(image_src, ipath):
                    entry["has_image"] = True
                    entry["preview"] = f"media/{ad_id}/{ipath.name}"
                    entry["source_image_url"] = image_src
                    print(f"  image → {ipath.name}")

            if shot and shot.exists():
                entry["snapshot_png"] = f"media/{ad_id}/snapshot.png"
                src = entry.get("source_image_url") or ""
                tiny = any(t in src for t in ("s60x60", "s60x40", "p64x64", "s130x130"))
                if not entry["preview"] or tiny:
                    entry["preview"] = entry["snapshot_png"]
                    entry["has_image"] = True
                    print("  preview → snapshot.png (fallback)")

            meta_file.write_text(json.dumps(entry, indent=2))
            index["ads"][ad_id] = entry
            time.sleep(0.6)

        browser.close()

    index["updated_at"] = datetime.now(timezone.utc).isoformat()
    index["count"] = len(index["ads"])
    index_path.write_text(json.dumps(index, indent=2))
    print(f"\nIndex → {index_path} ({index['count']} ads with media)")

    if args.rebuild_browser:
        builder = Path(__file__).parent / "build-ad-library-browser.py"
        import subprocess

        subprocess.run(
            [sys.executable, str(builder), "--run-dir", str(run_dir)],
            check=False,
        )


if __name__ == "__main__":
    main()
