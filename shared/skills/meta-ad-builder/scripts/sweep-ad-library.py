#!/usr/bin/env python3
"""
Keyword + page Ad Library research sweep for competitor creative DNA.

Writes under outputs/research/<slug>/:
  keyword-sweep.json  — ads by category (bodies, titles, snapshot URLs)
  top-pages.json      — ranked advertiser pages
  deep-pulls.json     — full active ads for top pages (optional)
  browser.html        — searchable UI (via build-ad-library-browser.py)
  canvas-data.json    — slim payload for Cursor canvas

Usage:
  python sweep-ad-library.py --country GB --days 180
  python sweep-ad-library.py --country GB --categories neck_fan,charger --skip-deep
  python sweep-ad-library.py --run-dir outputs/research/my-run --open-browser

Requires Ad Library API access on the Meta app behind META_ACCESS_TOKEN
(see facebook.com/ads/library/api — Marketing scopes alone are not enough).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent / "lib"))

load_dotenv()

import meta_api  # noqa: E402

DEFAULT_QUERIES = {
    "neck_fan": [
        "neck fan",
        "portable neck fan",
        "bladeless neck fan",
        "folding neck fan",
        "hanging neck fan",
        "wearable neck fan",
    ],
    "charger": [
        "3 in 1 wireless charger",
        "folding wireless charger",
        "magnetic folding charger",
        "MagSafe folding charger",
        "3-in-1 magnetic charger",
    ],
    "gan_retractable": [
        "retractable USB-C charger",
        "retractable GaN charger",
        "120W GaN charger",
        "GaN charger retractable cable",
        "built in retractable USB-C cable",
        "retractable charger cable",
        "multi port GaN charger UK",
    ],
    "massage_gun": [
        "massage gun",
        "mini massage gun",
        "fascia gun",
        "percussion massager",
    ],
    "car_vacuum": [
        "car vacuum",
        "handheld car vacuum",
        "wireless car vacuum",
    ],
    # Everyday “next-gen tech” accessories (not charging-only) — 2026-07-27
    "find_my_tracker": [
        "Find My tracker",
        "AirTag alternative",
        "Bluetooth item finder",
        "Apple Find My tag",
        "smart luggage tracker",
    ],
    "phone_cooler": [
        "phone cooler",
        "magnetic phone cooler",
        "phone semiconductor cooler",
        "gaming phone radiator",
        "TEC phone cooler",
    ],
    "portable_ssd": [
        "portable SSD",
        "external NVMe SSD",
        "USB-C portable SSD",
        "pocket SSD",
    ],
    "mini_projector": [
        "mini projector",
        "portable projector",
        "pocket projector Android",
        "pico projector",
    ],
    "bone_conduction": [
        "bone conduction headphones",
        "open ear headphones",
        "bone conduction earbuds",
        "open ear sport headphones",
    ],
    "translation_earbuds": [
        "translation earbuds",
        "AI translation earbuds",
        "real time translator earbuds",
        "language translator earbuds",
    ],
    "uv_sanitizer": [
        "UV phone sanitizer",
        "UV sterilizer box",
        "UV-C sanitizer phone",
        "phone UV cleaner",
    ],
    "qi2_charger": [
        "Qi2 charger",
        "Qi2 magnetic charger",
        "Qi2 wireless charger",
        "MagSafe Qi2",
    ],
    "portable_monitor": [
        "portable monitor",
        "USB-C portable monitor",
        "15.6 portable screen",
        "laptop portable display",
    ],
    "smart_ring": [
        "smart ring fitness",
        "smart ring sleep tracker",
        "health smart ring",
    ],
    # GaN-adjacent / cable-freedom / desk-travel (product discovery 2026-07-29)
    "vacuum_phone_mount": [
        "vacuum phone mount",
        "MagSafe vacuum mount",
        "foldable magnetic phone mount",
        "vacuum MagSafe car mount",
        "suction phone holder desk",
    ],
    "power_bank": [
        "MagSafe power bank",
        "magnetic power bank",
        "capsule power bank",
        "5000mAh MagSafe charger",
        "slim magnetic power bank",
    ],
    "gan_power_bank": [
        "GaN power bank",
        "65W power bank",
        "100W portable charger GaN",
        "GaN laptop power bank",
        "PD power bank USB-C",
    ],
    "usb_c_hub": [
        "USB-C hub multiport",
        "USB-C docking station",
        "Thunderbolt hub",
        "MacBook USB-C hub",
        "HDMI USB-C hub",
    ],
    "retractable_cable": [
        "retractable USB-C cable",
        "retractable charging cable",
        "3 in 1 retractable cable",
        "MagSafe retractable cable",
        "tangle free retractable cable",
    ],
    "travel_adapter": [
        "universal travel adapter",
        "GaN travel adapter",
        "worldwide travel plug",
        "UK travel adapter multiport",
        "international charger adapter",
    ],
    "desk_charger": [
        "desktop charging station",
        "multi device charging station",
        "wireless charging stand desk",
        "GaN desktop charger",
        "nightstand charger multiple devices",
    ],
    "laptop_stand": [
        "aluminum laptop stand",
        "adjustable laptop riser",
        "ergonomic laptop stand",
        "portable laptop stand foldable",
    ],
    "car_phone_mount": [
        "MagSafe car mount",
        "magnetic car phone holder",
        "vent car phone mount",
        "dashboard MagSafe mount",
    ],
    "wireless_hdmi": [
        "wireless HDMI transmitter",
        "phone to TV wireless",
        "USB-C to HDMI cable",
        "Switch HDMI cable TV",
    ],
    "turbo_blower": [
        "electric air duster",
        "compressed air blower",
        "cordless air duster keyboard",
        "electric dust blower PC",
    ],
    "cable_organizer": [
        "magnetic cable organizer",
        "desk cable management",
        "cable clips magnetic",
        "retractable cable organizer",
    ],
    # Productive / ahead-of-the-curve desk + AI (2026-07-29)
    "monitor_light_bar": [
        "monitor light bar",
        "screen bar desk lamp",
        "BenQ style monitor light",
        "USB monitor light bar",
        "computer monitor hanging lamp",
    ],
    "ai_voice_recorder": [
        "AI voice recorder",
        "Plaud AI recorder",
        "AI meeting note taker",
        "ChatGPT voice recorder",
        "AI transcription recorder",
    ],
    "macro_pad": [
        "Stream Deck",
        "macro pad keyboard",
        "programmable keypad desk",
        "shortcut keypad productivity",
        "mini Stream Deck alternative",
    ],
    "vertical_mouse": [
        "vertical ergonomic mouse",
        "ergonomic vertical mouse",
        "upright computer mouse",
        "wrist friendly mouse",
    ],
    "e_ink_tablet": [
        "e-ink tablet",
        "electronic paper notebook",
        "reMarkable alternative",
        "digital paper tablet",
        "e-note writing tablet",
    ],
    "webcam_light": [
        "video call lighting",
        "webcam ring light",
        "desk LED for Zoom",
        "laptop light bar meeting",
    ],
    "foldable_keyboard": [
        "foldable Bluetooth keyboard",
        "portable folding keyboard",
        "travel Bluetooth keyboard",
        "compact wireless keyboard",
    ],
    "phone_second_screen": [
        "phone as second monitor",
        "Duarte spacedesk",
        "iPhone second screen app",
        "wireless phone monitor laptop",
    ],
    "drawing_tablet": [
        "drawing tablet USB-C",
        "graphics tablet portable",
        "pen display tablet",
        "digital drawing pad",
    ],
    "desk_timer": [
        "Pomodoro timer desk",
        "focus timer cube",
        "productivity timer gadget",
        "flip focus timer",
    ],
    "ai_glasses": [
        "AI smart glasses",
        "ChatGPT glasses",
        "AI translation glasses",
        "smart glasses camera",
    ],
    "magnetic_desk_shelf": [
        "MagSafe desk shelf",
        "laptop monitor shelf MagSafe",
        "desk shelf phone charger",
        "aluminum monitor stand shelf",
    ],
}

NOISE_RE = re.compile(
    r"(romance|novel|fiction|story|stories|book|kindle|dating|casino|slot|"
    r"forex|crypto|bitcoin|nft|weight.?loss|diet.?pill|cbd)",
    re.I,
)

FIELDS = (
    "id,page_id,page_name,ad_delivery_start_time,ad_delivery_stop_time,"
    "ad_snapshot_url,publisher_platforms,eu_total_reach,"
    "ad_creative_bodies,ad_creative_link_titles,ad_creative_link_descriptions"
)


def strip_access_token(url: str | None) -> str | None:
    if not url:
        return url
    parsed = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
         if k.lower() != "access_token"]
    return urlunparse(parsed._replace(query=urlencode(q)))


def scrub_ad(ad: dict) -> dict:
    out = dict(ad)
    if "ad_snapshot_url" in out:
        out["ad_snapshot_url"] = strip_access_token(out.get("ad_snapshot_url"))
    return out


def days_live(ad, now):
    start = ad.get("ad_delivery_start_time")
    if not start:
        return None
    try:
        s = datetime.fromisoformat(start.replace("Z", "+00:00"))
    except Exception:
        return None
    if s.tzinfo is None:
        s = s.replace(tzinfo=timezone.utc)
    stop = ad.get("ad_delivery_stop_time")
    if stop:
        try:
            e = datetime.fromisoformat(stop.replace("Z", "+00:00"))
        except Exception:
            e = now
        if e.tzinfo is None:
            e = e.replace(tzinfo=timezone.utc)
    else:
        e = now
    return max(0, (e - s).days)


def fetch(params, max_ads=80):
    url = f"{meta_api.BASE_URL}/ads_archive"
    ads, seen = [], set()
    while url and len(ads) < max_ads:
        resp = requests.get(url, params=params, timeout=60)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 30))
            print(f"    rate-limit {wait}s")
            time.sleep(wait)
            continue
        if resp.status_code >= 500:
            time.sleep(4)
            continue
        data = resp.json()
        if "error" in data:
            return ads, data["error"]
        for ad in data.get("data", []):
            aid = ad.get("id")
            if aid and aid not in seen:
                seen.add(aid)
                ads.append(ad)
        url = data.get("paging", {}).get("next")
        params = None
        time.sleep(0.35)
    return ads[:max_ads], None


def is_noise(ad):
    name = ad.get("page_name") or ""
    if NOISE_RE.search(name):
        return True
    bodies = " ".join(ad.get("ad_creative_bodies") or [])
    titles = " ".join(ad.get("ad_creative_link_titles") or [])
    blob = f"{name} {bodies} {titles}".lower()
    productish = any(
        k in blob
        for k in (
            "fan", "charger", "massage", "fascia", "vacuum", "cooling", "magsafe",
            "wireless", "neck", "portable", "bladeless", "usb", "battery",
            "gan", "retractable", "120w", "watt", "hub", "dock", "ssd", "projector",
            "tracker", "find my", "earbuds", "headphones", "monitor", "stand",
            "mount", "power bank", "adapter", "hdmi", "blower", "duster", "qi2",
            "cooler", "sanitizer", "ring", "laptop", "thunderbolt", "pd ",
            "light bar", "stream deck", "macro", "ergonomic", "vertical mouse",
            "e-ink", "eink", "recorder", "transcription", "pomodoro", "focus",
            "keyboard", "tablet", "glasses", "shelf", "webcam", "zoom", "meeting",
            "ai ", "chatgpt", "plaud", "drawing", "pen display",
        )
    )
    if not productish and NOISE_RE.search(blob):
        return True
    return False


def resolve_research_dir(run_dir: str | None, slug: str | None) -> Path:
    if run_dir:
        path = Path(run_dir)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        name = slug or f"{stamp}-ad-library"
        path = Path("outputs/research") / name
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def run_browser_builder(out: Path, open_browser: bool):
    builder = Path(__file__).parent / "build-ad-library-browser.py"
    cmd = [sys.executable, str(builder), "--run-dir", str(out)]
    if open_browser:
        cmd.append("--open")
    subprocess.run(cmd, check=False)


def main():
    parser = argparse.ArgumentParser(description="Ad Library keyword + deep-page research sweep")
    parser.add_argument("--country", default="GB")
    parser.add_argument("--days", type=int, default=180, help="Lookback window ending yesterday")
    parser.add_argument("--categories", default=",".join(DEFAULT_QUERIES.keys()),
                        help="Comma-separated category keys from the default map")
    parser.add_argument("--per-term", type=int, default=50, help="Max ads kept per search term")
    parser.add_argument("--deep-pages", type=int, default=12, help="Top pages to deep-pull")
    parser.add_argument("--skip-deep", action="store_true")
    parser.add_argument("--run-dir", help="Exact output directory")
    parser.add_argument("--slug", help="Folder name under outputs/research/")
    parser.add_argument("--open-browser", action="store_true",
                        help="Open browser.html after the sweep")
    parser.add_argument("--no-browser", action="store_true",
                        help="Skip building browser.html / canvas-data.json")
    args = parser.parse_args()

    cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    for c in cats:
        if c not in DEFAULT_QUERIES:
            print(f"ERROR: unknown category {c!r}. Known: {list(DEFAULT_QUERIES)}",
                  file=sys.stderr)
            sys.exit(1)

    token = meta_api.get_access_token()
    now = datetime.now(timezone.utc)
    date_max = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    date_min = (now - timedelta(days=args.days)).strftime("%Y-%m-%d")
    out = resolve_research_dir(args.run_dir, args.slug)
    print(f"Output → {out}")
    print(f"Window {date_min} → {date_max} · country {args.country}")

    sweep = {
        "pulled_at": now.isoformat(),
        "country": args.country,
        "date_min": date_min,
        "date_max": date_max,
        "categories": {},
    }

    all_pages = Counter()
    page_names = {}
    page_cats = defaultdict(set)
    page_ads = defaultdict(list)

    for cat in cats:
        terms = DEFAULT_QUERIES[cat]
        print(f"\n######## CATEGORY: {cat} ########")
        cat_ads = []
        seen_ids = set()
        for term in terms:
            print(f"  search: {term!r}")
            params = {
                "access_token": token,
                "search_terms": term,
                "ad_reached_countries": args.country,
                "ad_delivery_date_min": date_min,
                "ad_delivery_date_max": date_max,
                "ad_active_status": "ACTIVE",
                "ad_type": "ALL",
                "sort_by": "impressions_high_to_low",
                "fields": FIELDS,
                "limit": 50,
            }
            ads, err = fetch(params, max_ads=args.per_term)
            if err:
                print("    ERROR", err.get("message"), err.get("error_subcode"))
                if err.get("error_subcode") == 2332002:
                    print("    Tip: complete Ad Library API access at facebook.com/ads/library/api")
                continue
            kept = 0
            for ad in ads:
                if ad["id"] in seen_ids or is_noise(ad):
                    continue
                ad = scrub_ad(ad)
                ad["_days_live"] = days_live(ad, now)
                seen_ids.add(ad["id"])
                cat_ads.append(ad)
                kept += 1
                pid = ad.get("page_id")
                if pid:
                    all_pages[pid] += 1
                    page_names[pid] = ad.get("page_name") or pid
                    page_cats[pid].add(cat)
                    page_ads[pid].append(ad)
            print(f"    raw={len(ads)} kept_new={kept}")
            time.sleep(0.6)

        pc = Counter(a.get("page_id") for a in cat_ads if a.get("page_id"))
        top = []
        for pid, n in pc.most_common(15):
            sample = next((a for a in cat_ads if a.get("page_id") == pid), {})
            lives = [
                a["_days_live"] for a in cat_ads
                if a.get("page_id") == pid and a.get("_days_live") is not None
            ]
            top.append({
                "page_id": pid,
                "page_name": page_names.get(pid),
                "ad_count": n,
                "max_days_live": max(lives) if lives else None,
                "avg_days_live": round(sum(lives) / len(lives), 1) if lives else None,
                "sample_snapshot": sample.get("ad_snapshot_url"),
                "sample_bodies": (sample.get("ad_creative_bodies") or [])[:2],
                "sample_titles": (sample.get("ad_creative_link_titles") or [])[:3],
            })
            print(f"    PAGE {n:3d} ads | max_days={top[-1]['max_days_live']} | {page_names.get(pid)}")

        sweep["categories"][cat] = {
            "ad_count": len(cat_ads),
            "page_count": len(pc),
            "top_pages": top,
            "ads": cat_ads,
        }

    (out / "keyword-sweep.json").write_text(json.dumps(sweep, indent=2, ensure_ascii=False))
    print("\nSaved keyword-sweep.json")

    ranked = []
    for pid, n in all_pages.most_common(40):
        lives = [a["_days_live"] for a in page_ads[pid] if a.get("_days_live") is not None]
        ranked.append({
            "page_id": pid,
            "page_name": page_names[pid],
            "ad_count": n,
            "categories": sorted(page_cats[pid]),
            "max_days_live": max(lives) if lives else 0,
            "avg_days_live": round(sum(lives) / len(lives), 1) if lives else 0,
        })
    ranked.sort(key=lambda x: (x["ad_count"] * 2 + x["max_days_live"], x["ad_count"]), reverse=True)
    (out / "top-pages.json").write_text(json.dumps(ranked, indent=2, ensure_ascii=False))

    if not args.skip_deep and args.deep_pages > 0:
        deep = {"pulled_at": now.isoformat(), "pages": []}
        for p in ranked[: args.deep_pages]:
            pid = p["page_id"]
            print(f"\nDEEP PULL {p['page_name']} ({pid})")
            params = {
                "access_token": token,
                "search_page_ids": pid,
                "ad_reached_countries": args.country,
                "ad_delivery_date_min": date_min,
                "ad_delivery_date_max": date_max,
                "ad_active_status": "ACTIVE",
                "ad_type": "ALL",
                "sort_by": "longest_running",
                "fields": FIELDS,
                "limit": 50,
            }
            ads, err = fetch(params, max_ads=40)
            if err:
                print("  ERROR", err)
                deep["pages"].append({**p, "error": err, "ads": []})
                continue
            cleaned = []
            for ad in ads:
                if is_noise(ad):
                    continue
                ad = scrub_ad(ad)
                ad["_days_live"] = days_live(ad, now)
                cleaned.append(ad)
            lives = [a["_days_live"] for a in cleaned if a.get("_days_live") is not None]
            bodies, titles = [], []
            for a in cleaned:
                bodies.extend(a.get("ad_creative_bodies") or [])
                titles.extend(a.get("ad_creative_link_titles") or [])
            print(f"  {len(cleaned)} active ads | max_days={max(lives) if lives else None}")
            deep["pages"].append({
                **p,
                "deep_ad_count": len(cleaned),
                "deep_max_days": max(lives) if lives else None,
                "deep_avg_days": round(sum(lives) / len(lives), 1) if lives else None,
                "unique_bodies": list(dict.fromkeys(bodies))[:15],
                "unique_titles": list(dict.fromkeys(titles))[:15],
                "platforms": sorted({plat for a in cleaned for plat in (a.get("publisher_platforms") or [])}),
                "ads": cleaned,
            })
            time.sleep(0.8)
        (out / "deep-pulls.json").write_text(json.dumps(deep, indent=2, ensure_ascii=False))
        print("\nSaved deep-pulls.json")

    if not args.no_browser:
        run_browser_builder(out, open_browser=args.open_browser)

    print(f"\nDone → {out}")
    print("Next: write REPORT.md, refresh Cursor canvas from canvas-data.json, cite ads in chat.")


if __name__ == "__main__":
    main()
