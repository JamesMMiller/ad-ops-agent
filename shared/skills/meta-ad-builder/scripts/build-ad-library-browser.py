#!/usr/bin/env python3
"""
Build a local Ad Library research browser from a research run directory.

Reads keyword-sweep.json / deep-pulls.json / top-pages.json (any subset) and
writes:
  browser.html       — self-contained searchable UI (open in a browser)
  browser-data.json  — normalized ads (token-stripped snapshot URLs)
  canvas-data.json   — slim subset for embedding in a Cursor canvas

Usage:
  python build-ad-library-browser.py --run-dir outputs/research/2026-07-24-ad-library-full
  python build-ad-library-browser.py --run-dir outputs/research/... --open

After building, the agent should also refresh the Cursor canvas from
canvas-data.json (see reference/ad-library-research.md).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

BODY_FULL_MAX = 6000
BODY_CANVAS_MAX = 700
CANVAS_ADS_MAX = 180


def strip_access_token(url: str | None) -> str | None:
    """Remove access_token from Ad Library snapshot URLs before writing to disk."""
    if not url:
        return url
    parsed = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
         if k.lower() != "access_token"]
    return urlunparse(parsed._replace(query=urlencode(q)))


def trunc(text: str | None, n: int) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"


def first_texts(values, n=3, maxlen=None):
    out = []
    for v in values or []:
        if not v:
            continue
        s = str(v).strip()
        if maxlen:
            s = trunc(s, maxlen)
        if s:
            out.append(s)
        if len(out) >= n:
            break
    return out


def load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text())


def signal_score(days_live, eu_reach) -> float:
    """Rough success proxy for commercial Ad Library ads.

    Meta does not expose ROAS/CTR/spend for normal product ads. Longevity and
    (when present) EU total reach are the usable public signals.
    """
    import math

    days = float(days_live or 0)
    reach = float(eu_reach or 0)
    # Days dominate: an ad still spending after 2–4 weeks beats a 1-day spray.
    # Reach (log) boosts when Meta returns EU DSA numbers.
    return round(days * 10.0 + math.log10(reach + 1.0) * 25.0, 1)


def library_urls(ad_id: str, page_id: str, country: str | None) -> dict:
    c = country or "GB"
    return {
        "library_url": f"https://www.facebook.com/ads/library/?id={ad_id}" if ad_id else None,
        "page_library_url": (
            "https://www.facebook.com/ads/library/?active_status=active&ad_type=all"
            f"&country={c}&view_all_page_id={page_id}"
            if page_id else None
        ),
    }


def normalize_ad(raw: dict, *, category: str | None, source: str,
                 country: str | None = None) -> dict:
    bodies = first_texts(raw.get("ad_creative_bodies"), n=5, maxlen=BODY_FULL_MAX)
    titles = first_texts(raw.get("ad_creative_link_titles"), n=5, maxlen=240)
    descs = first_texts(raw.get("ad_creative_link_descriptions"), n=3, maxlen=400)
    ad_id = str(raw.get("id") or "")
    page_id = str(raw.get("page_id") or "")
    return {
        "id": ad_id,
        "page_id": page_id,
        "page_name": raw.get("page_name") or "",
        "category": category or "",
        "source": source,
        "days_live": raw.get("_days_live"),
        "start": raw.get("ad_delivery_start_time"),
        "platforms": raw.get("publisher_platforms") or [],
        "eu_reach": raw.get("eu_total_reach"),
        "bodies": bodies,
        "titles": titles,
        "descriptions": descs,
        "snapshot_url": strip_access_token(raw.get("ad_snapshot_url")),
        **library_urls(ad_id, page_id, country),
        "body_preview": trunc(bodies[0] if bodies else "", 280),
        "title_preview": titles[0] if titles else "",
        "media": None,
        "signal_score": signal_score(raw.get("_days_live"), raw.get("eu_total_reach")),
        "signal_label": (
            "strong" if (raw.get("_days_live") or 0) >= 21
            else "watch" if (raw.get("_days_live") or 0) >= 7
            else "fresh"
        ),
    }


def load_media_index(run_dir: Path) -> dict:
    path = run_dir / "media" / "index.json"
    if not path.exists():
        return {}
    data = load_json(path) or {}
    return data.get("ads") or {}


def attach_media(ads: list[dict], media_index: dict) -> None:
    for ad in ads:
        entry = media_index.get(ad["id"])
        if entry:
            ad["media"] = {
                "preview": entry.get("preview"),
                "video": entry.get("video"),
                "snapshot_png": entry.get("snapshot_png"),
                "has_image": entry.get("has_image"),
                "has_video": entry.get("has_video"),
            }


def collect_ads(run_dir: Path) -> tuple[list[dict], dict]:
    sweep = load_json(run_dir / "keyword-sweep.json")
    deep = load_json(run_dir / "deep-pulls.json")
    top = load_json(run_dir / "top-pages.json")

    by_id: dict[str, dict] = {}
    meta = {
        "run_dir": str(run_dir),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "country": None,
        "date_min": None,
        "date_max": None,
        "categories": [],
        "top_pages": [],
    }

    if sweep:
        meta["country"] = sweep.get("country")
        meta["date_min"] = sweep.get("date_min")
        meta["date_max"] = sweep.get("date_max")
        meta["pulled_at"] = sweep.get("pulled_at")
        for cat, block in (sweep.get("categories") or {}).items():
            meta["categories"].append({
                "id": cat,
                "ad_count": block.get("ad_count") or len(block.get("ads") or []),
                "page_count": block.get("page_count"),
            })
            for raw in block.get("ads") or []:
                ad = normalize_ad(
                    raw, category=cat, source="keyword_sweep", country=meta["country"]
                )
                if not ad["id"]:
                    continue
                prev = by_id.get(ad["id"])
                if prev:
                    # Prefer longer days_live / richer bodies; merge categories.
                    cats = sorted({c for c in (prev.get("category") or "").split(",") if c}
                                  | {cat})
                    prev["category"] = ",".join(cats)
                    if (ad.get("days_live") or 0) > (prev.get("days_live") or 0):
                        prev["days_live"] = ad["days_live"]
                    if len(ad.get("bodies") or []) > len(prev.get("bodies") or []):
                        prev["bodies"] = ad["bodies"]
                        prev["body_preview"] = ad["body_preview"]
                    continue
                by_id[ad["id"]] = ad

    if deep:
        meta["deep_pulled_at"] = deep.get("pulled_at")
        for page in deep.get("pages") or []:
            cat = ",".join(page.get("categories") or []) or None
            for raw in page.get("ads") or []:
                ad = normalize_ad(
                    raw, category=cat, source="deep_pull", country=meta["country"]
                )
                if not ad["id"]:
                    continue
                if ad["id"] in by_id:
                    prev = by_id[ad["id"]]
                    if not prev.get("bodies") and ad.get("bodies"):
                        prev["bodies"] = ad["bodies"]
                        prev["body_preview"] = ad["body_preview"]
                    if not prev.get("titles") and ad.get("titles"):
                        prev["titles"] = ad["titles"]
                        prev["title_preview"] = ad["title_preview"]
                    continue
                by_id[ad["id"]] = ad

    if isinstance(top, list):
        meta["top_pages"] = [
            {
                "page_id": p.get("page_id"),
                "page_name": p.get("page_name"),
                "ad_count": p.get("ad_count"),
                "categories": p.get("categories") or [],
                "max_days_live": p.get("max_days_live"),
                "avg_days_live": p.get("avg_days_live"),
            }
            for p in top[:40]
        ]

    ads = list(by_id.values())
    media_index = load_media_index(run_dir)
    attach_media(ads, media_index)
    meta["media_count"] = len(media_index)
    ads.sort(key=lambda a: (a.get("days_live") is None, -(a.get("days_live") or 0),
                            a.get("page_name") or ""))
    # Prefer ads with local media when building canvas subset later —
    # keep chronological longevity sort for the full list.
    return ads, meta


def canvas_subset(ads: list[dict], meta: dict) -> dict:
    # Prefer longest-running, but bubble ads with local media toward the front.
    ranked = sorted(
        ads,
        key=lambda a: (
            0 if a.get("media") else 1,
            a.get("days_live") is None,
            -(a.get("days_live") or 0),
        ),
    )
    slim = []
    for ad in ranked[:CANVAS_ADS_MAX]:
        media = ad.get("media") or {}
        slim.append({
            "id": ad["id"],
            "page": ad["page_name"],
            "cat": ad["category"],
            "days": ad["days_live"],
            "title": trunc(ad.get("title_preview") or "", 120),
            "body": trunc((ad.get("bodies") or [""])[0], BODY_CANVAS_MAX),
            "platforms": (ad.get("platforms") or [])[:4],
            "snapshot": ad.get("snapshot_url"),
            "library": ad.get("library_url"),
            "preview": media.get("preview") or media.get("snapshot_png"),
            "video": media.get("video"),
            "has_media": bool(media.get("preview") or media.get("video") or media.get("snapshot_png")),
        })
    return {
        "meta": {
            "title": "Ad Library research",
            "country": meta.get("country"),
            "date_min": meta.get("date_min"),
            "date_max": meta.get("date_max"),
            "run_dir": meta.get("run_dir"),
            "built_at": meta.get("built_at"),
            "total_ads": len(ads),
            "shown_ads": len(slim),
            "media_count": meta.get("media_count") or 0,
            "categories": meta.get("categories") or [],
        },
        "ads": slim,
        "top_pages": (meta.get("top_pages") or [])[:15],
    }


def load_browser_template() -> str:
    path = Path(__file__).parent / "templates" / "browser.html"
    return path.read_text()




def default_canvas_out() -> Path | None:
    """Cursor-managed canvases dir for this workspace, if discoverable."""
    home = Path.home() / ".cursor" / "projects"
    if not home.is_dir():
        return None
    # Prefer exact path used by this repo's IDE project folder.
    preferred = home / "Users-jamesmiller-git-projects-ad-ops-agent" / "canvases"
    if preferred.is_dir():
        return preferred / "ad-library-research.canvas.tsx"
    # Fallback: any *ad-ops-agent* canvases folder.
    for p in home.glob("*ad-ops-agent*/canvases"):
        if p.is_dir():
            return p / "ad-library-research.canvas.tsx"
    return None


def write_canvas_tsx(canvas_data: dict, out_path: Path) -> Path:
    template = Path(__file__).parent / "templates" / "ad-library-research.canvas.tsx.template"
    if not template.exists():
        raise FileNotFoundError(f"Missing canvas template: {template}")
    embedded = json.dumps(canvas_data, ensure_ascii=False)
    # Keep JSX/TS safe if a body ever contains the closing script-ish sequences.
    text = template.read_text().replace("__DATA__", embedded)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    print(f"Wrote {out_path} ({out_path.stat().st_size // 1024} KB)")
    return out_path


def write_browser(
    run_dir: Path,
    ads: list[dict],
    meta: dict,
    *,
    open_after: bool,
    canvas_out: Path | None,
    write_canvas: bool = True,
) -> Path:
    media_index = load_media_index(run_dir)
    payload = {
        "meta": {
            "title": "Ad Library research",
            **{k: meta.get(k) for k in (
                "country", "date_min", "date_max", "run_dir", "built_at",
                "pulled_at", "categories", "media_count",
            )},
        },
        "ads": ads,
        "top_pages": meta.get("top_pages") or [],
        "media": media_index,
    }
    data_path = run_dir / "browser-data.json"
    data_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    canvas = canvas_subset(ads, meta)
    canvas_path = run_dir / "canvas-data.json"
    canvas_path.write_text(json.dumps(canvas, indent=2, ensure_ascii=False))

    embedded = json.dumps(payload, ensure_ascii=False)
    embedded = embedded.replace("<", "\\u003c").replace(">", "\\u003e")
    out = run_dir / "browser.html"
    out.write_text(load_browser_template().replace("__DATA_JSON__", embedded))
    print(f"Wrote {out} ({out.stat().st_size // 1024} KB)")
    print(f"Wrote {data_path}")
    print(f"Wrote {canvas_path} ({len(canvas['ads'])} ads for canvas)")
    if media_index:
        print(f"Linked local media for {len(media_index)} ads")

    if write_canvas:
        target = canvas_out or default_canvas_out()
        if target:
            write_canvas_tsx(canvas, target)
        else:
            print("No Cursor canvases/ dir found — skip .canvas.tsx "
                  "(pass --canvas-out).")

    if open_after:
        try:
            subprocess.run(["open", str(out)], check=False)
        except Exception as exc:
            print(f"Could not open browser: {exc}", file=sys.stderr)
    return out


def main():
    parser = argparse.ArgumentParser(description="Build Ad Library research browser UI")
    parser.add_argument("--run-dir", required=True,
                        help="Research output folder with keyword-sweep.json etc.")
    parser.add_argument("--open", action="store_true", help="Open browser.html after build")
    parser.add_argument(
        "--canvas-out",
        help="Path for ad-library-research.canvas.tsx "
             "(default: auto-detect ~/.cursor/projects/*/canvases/)",
    )
    parser.add_argument(
        "--no-canvas",
        action="store_true",
        help="Skip writing the Cursor .canvas.tsx file",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.is_dir():
        print(f"ERROR: not a directory: {run_dir}", file=sys.stderr)
        sys.exit(1)

    ads, meta = collect_ads(run_dir)
    if not ads:
        print("ERROR: no ads found — need keyword-sweep.json and/or deep-pulls.json",
              file=sys.stderr)
        sys.exit(1)

    write_browser(
        run_dir,
        ads,
        meta,
        open_after=args.open,
        canvas_out=Path(args.canvas_out) if args.canvas_out else None,
        write_canvas=not args.no_canvas,
    )
    print(f"\nOpen: {run_dir / 'browser.html'}")
    print("Canvas: ad-library-research.canvas.tsx (beside chat).")


if __name__ == "__main__":
    main()
