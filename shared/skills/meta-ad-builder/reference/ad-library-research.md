# Ad Library research + browse UI

Use this when the user wants competitor Ad Library research they can **browse**
and **cite in chat** — not just a markdown report.

## Prerequisites

- `META_ACCESS_TOKEN` with **Ad Library API access** completed for the app/user
  ([facebook.com/ads/library/api](https://www.facebook.com/ads/library/api)).
  Marketing scopes alone are not enough (`error_subcode` `2332002`).
- Python deps from `scripts/requirements.txt`.

## End-to-end workflow

### 1. Sweep

```bash
python scripts/sweep-ad-library.py --country GB --days 180 --open-browser
```

Useful flags:

| Flag | Purpose |
|---|---|
| `--categories neck_fan,charger` | Subset of default category map |
| `--skip-deep` | Keyword sweep only (faster) |
| `--deep-pages 12` | How many top pages to expand |
| `--run-dir outputs/research/...` | Fixed output folder |
| `--no-browser` | Skip UI build (rare) |

Outputs under `outputs/research/<slug>/`:

| File | Role |
|---|---|
| `keyword-sweep.json` | Ads + copy by category |
| `top-pages.json` | Ranked advertiser pages |
| `deep-pulls.json` | Full active ads for top pages |
| `browser.html` | Full searchable local UI |
| `browser-data.json` | Normalized ads (token-stripped) |
| `canvas-data.json` | Slim payload for Cursor canvas |
| `REPORT.md` | Agent-written gleanings (you write this) |

Snapshot URLs are **stripped of `access_token`** before write. Never commit
raw Meta tokens into research JSON or HTML.

### 2. Rebuild UI only (existing run)

```bash
python scripts/build-ad-library-browser.py \
  --run-dir outputs/research/2026-07-24-ad-library-full --open
```

### 3. Capture creatives (optional but recommended)

Meta’s Ad Library API returns **copy + snapshot links only** — not image/video
files. To browse assets inline in `browser.html`:

```bash
# Needs: pip install playwright && playwright install chromium
python scripts/enrich-ad-library-media.py \
  --run-dir outputs/research/<slug> \
  --limit 40 --min-days 7 \
  --categories neck_fan,charger \
  --rebuild-browser
```

This opens each ad’s Meta snapshot in headless Chromium, downloads the creative
image/video into `media/<ad_id>/`, and rebuilds the browser so grid thumbnails
and the detail player work offline.

Without enrich: use **Open Meta creative** in the UI (public Ad Library URL).

### 4. Open the full browser

```bash
open outputs/research/<slug>/browser.html
```

Features: grid/list/pages views, category + platform + page filters, pins
(localStorage), keyboard (`j`/`k`/`/`/`p`/`o`), search, min days-live, media
filters (has preview / needs enrich), detail pane with inline video/image when
enriched, **Open Meta creative**, **Copy cite for chat**.

### 5. Cursor canvas (chat-side reference)

`build-ad-library-browser.py` auto-writes
`ad-library-research.canvas.tsx` into the Cursor `canvases/` folder when it can
detect one (override with `--canvas-out`). Template:
`scripts/templates/ad-library-research.canvas.tsx.template`.

After every research run the agent **must**:

1. Confirm the canvas file was written (re-run the builder if needed).
2. Tell the user they can open
   [ad-library-research](/Users/<user>/.cursor/projects/<workspace>/canvases/ad-library-research.canvas.tsx)
   beside the chat to browse / filter ads and cite them back into the conversation.

Canvas holds a **subset** (media-enriched + longest-running first, truncated
bodies). Point the user at `browser.html` for the full corpus and inline assets.

### 6. Citing ads in chat

Prefer the browser’s **Copy cite for chat**, or paste:

```text
Ad Library ref: <page_name> (<ad_id>)
Category: …
Days live: …
Title: …
Body: …
Snapshot: …
```

When the user references an ad from the canvas/browser, use that `ad_id` +
copy when drafting Meta copy or briefs.

## Competitor page pull (narrow)

For one brand / page (not a category sweep):

```bash
python scripts/pull-competitor-ads.py --pages "BrandName" --limit 50
```

Then either analyse the JSON directly, or drop/merge into a research folder and
run `build-ad-library-browser.py` if you reshaped it into the sweep schema.

## Reading “success” from Ad Library

Commercial product ads **do not** expose ROAS, CTR, or exact spend in the API.
What you *can* use as proxies (surfaced in `browser.html` as **success proxy**):

| Signal | Meaning |
|---|---|
| **Days live** (best) | Still spending after 14–30+ days → creative/offer is at least not dying fast. Spam farms spray 1–5 day ads. |
| **EU total reach** | Present for some EU-delivered ads; rough volume, not UK-only and not conversions. |
| **Page variant volume + longevity** | Many short-lived ads = testing/spam. Fewer ads, longer max days = stronger signal. |
| **`sort_by=impressions_high_to_low`** | Accepted by Meta and can bias result order, but impression *values* are not returned for normal product ads. |

**Your own ads:** use `pull-top-ads.py` (account insights / ROAS) — that is real performance, not Ad Library.

Browser badges: `21d+ survivor` / `7d+ running` / `fresh / test`. Default sort is success proxy.

## Safety

- Research outputs stay under `outputs/` (gitignored).
- Never paste live `access_token` query params into chat, canvas, or commits.
- Ad Library keyword search is noisy — prefer longevity + on-category copy over
  raw page volume when writing REPORT.md.

