---
name: meta-ad-builder
description: >-
  Publish finished creatives as live Meta (Facebook/Instagram) ads via the Meta
  Marketing API, plus research and ad-copy support. Uploads an image or video,
  builds a multi-variant TEXT_LIQUIDITY creative, and creates a PAUSED ad in an
  existing ad set. Also pulls top-performing ads (ranked by ROAS) and competitor
  ads from the Ad Library to inform copy. Builds a local research browser +
  Cursor canvas so the user can browse competitor creatives and cite them in
  chat. Use when the user asks to deploy / publish / launch a creative as a Meta
  or Facebook ad, build a Meta ad, push a video or image into an ad set, pull
  their top ads, research competitor ads, or browse Ad Library research.
  Not for generating creative (use the image/video skills) and not for writing
  AdTable/Airtable rows (use adtable-light).
---

# Meta ad builder

Turn a finished creative — typically the output of a generative-AI skill in this
workspace — into a live Meta ad. The skill covers three phases: **research**
(optional) → **copy** → **deploy**. It talks to the Meta Marketing API directly
via ported, parameterized Python scripts.

## When to use this skill

Trigger on phrases like:
- "deploy this video to Meta" / "publish this as a Facebook ad"
- "build/launch a Meta ad" / "push this creative into <ad set>"
- "create a Meta ad with this image and copy"
- "pull my top-performing ads" / "what are my best ads by ROAS"
- "research competitor ads" / "pull <brand>'s ads from the Ad Library"
- "browse Ad Library research" / "open the research UI"

Do **not** use this skill to *generate* creative — that's `pixar-style-ad`,
`claymation-ad`, `generate-youtube-thumbnail`, `uni1-image-ad`, etc. Do not use
it to write AdTable/Airtable rows — that's `adtable-light`. This skill is the
*direct Meta Marketing API* deployment step.

## Read order

1. **This file** — workflow, decision tree, safety rules.
2. **[prompting/copy-guide.md](prompting/copy-guide.md)** — the 5-body / 5-title /
   3-description frameworks and the `--copy-file` JSON shape.
3. **[reference/deploy-patterns.md](reference/deploy-patterns.md)** — creative
   spec mechanics, video polling, retry, failure modes.
4. **[reference/ad-library-research.md](reference/ad-library-research.md)** —
   keyword sweeps, `browser.html`, Cursor canvas from `canvas-data.json`.
5. **[reference/meta-api-cheatsheet.md](reference/meta-api-cheatsheet.md)** — the
   full Meta Marketing API reference (campaigns, ad sets, ads, enums, gotchas,
   Ad Library). Consult as needed; don't read end-to-end.

## Prerequisites

- **Env** (in `.env` — see your repo's `.env.example`):
  - `META_ACCESS_TOKEN` (required) — long-lived token with `ads_management` scope
  - `META_AD_ACCOUNT_ID` (required) — with or without the `act_` prefix
  - `META_PAGE_ID`, `META_IG_USER_ID`, `META_PIXEL_ID` (optional defaults for deploy / CAPI)
  - `META_API_VERSION` (optional, default `v25.0`)
  - `META_CAPI_ACCESS_TOKEN` (optional) — dedicated Conversions API token from
    Events Manager → Settings; falls back to `META_ACCESS_TOKEN`
- **Python deps:** `python3 -m pip install -r scripts/requirements.txt`
- **A target ad set** that already exists. The skill deploys ads into an existing
  ad set — it does not create campaigns or ad sets. If the user needs a new ad
  set, create it in Ads Manager or via the cheatsheet §3–§4 first.
- **The finished creative on disk** — an image or video file path. Chat-pasted
  files are not accessible; ask the user for a real path.

Run `bash scripts/check-meta-env.sh` to verify credentials before anything else.

## Purchase tracking (Shopify ↔ Meta)

Keep the Facebook & Instagram sales channel live with **Maximum** data sharing
and pixel `META_PIXEL_ID`. Do **not** paste a second Meta pixel into the theme.

When a paid Shopify order does not appear as a Meta `Purchase` (or after the
next real sale), reconcile and optionally backfill:

```bash
# Compare paid Shopify orders vs Meta Purchase totals (max 7-day lookback)
python scripts/audit-purchase-tracking.py --days 7

# Dry-run a Conversions API Purchase for one order (default — no send)
python scripts/send-purchase-capi.py --order-name '#1002'

# Send for real (after dry-run review). Prefer a rotated CAPI token.
python scripts/send-purchase-capi.py --order-name '#1002' --send
```

Scripts never print raw email/phone. Meta Stats API is aggregate-only, so a
count match is strong evidence, not an order-level receipt.

## Workflow

### Phase 1 — Research (optional, when copy should model winners)

```bash
# Rank the account's ads and pull the winning copy
python scripts/pull-top-ads.py --date-preset last_30d --min-spend 100 --limit 15

# Category keyword sweep + deep page pulls + local browse UI
python scripts/sweep-ad-library.py --country GB --days 180 --open-browser

# Narrow: one competitor page from the Ad Library
python scripts/pull-competitor-ads.py --pages "BrandName" --limit 50
```

Account top-ads write under `OUTPUT_BASE` (or `./outputs/meta-ads/`). Ad Library
sweeps write under `outputs/research/<slug>/` and **always** build
`browser.html` + `canvas-data.json` (see
[ad-library-research.md](reference/ad-library-research.md)).

**After every Ad Library research run:**

1. Optionally enrich creatives: `enrich-ad-library-media.py --rebuild-browser`
   (Meta’s API does not return image/video files — this captures them locally).
2. Open / point the user at `browser.html` for the full corpus + inline assets.
3. Refresh the Cursor canvas from `canvas-data.json` so they can browse beside
   chat and cite ads back into this conversation.
4. Write `REPORT.md` gleanings (longevity + on-category copy > raw volume).

Rebuild UI only: `python scripts/build-ad-library-browser.py --run-dir <dir> --open`.

### Phase 2 — Copy

Write a `copy.json` following **[copy-guide.md](prompting/copy-guide.md)**:
5 bodies (one per framework angle), 5 titles, 3 descriptions. If Phase 1 ran,
mirror the voice and patterns of the winners — new creative + proven copy DNA.
Save `copy.json` somewhere under `outputs/` so it isn't committed.

### Phase 3 — Deploy

**Always dry-run first** — it prints the full creative payload, makes no API calls:

```bash
python scripts/deploy-ad.py --dry-run \
  --adset-id <AD_SET_ID> --copy-file copy.json --link <DESTINATION_URL> \
  --image path/to/creative.png
```

Review the payload with the user, then deploy for real:

```bash
python scripts/deploy-ad.py \
  --adset-id <AD_SET_ID> --copy-file copy.json --link <DESTINATION_URL> \
  --video clip-a.mp4 --video clip-b.mp4 --cta SIGN_UP --pixel-id <PIXEL_ID>
```

- `--image` / `--video` are repeatable — each becomes its own ad in the ad set.
- Every ad is created **PAUSED**. Tell the user to review and un-pause in Meta
  Ads Manager. The skill never launches a spending ad automatically.
- Results (ad IDs) are written to `deployment_results.json` under `OUTPUT_BASE`.

## Decision tree

| User intent | Phases |
|---|---|
| "Deploy this creative to Meta" + copy provided | Phase 3 only |
| "Build a Meta ad, write the copy too" | Phase 2 → 3 |
| "Make ads modeled on my winners" | Phase 1 → 2 → 3 |
| "What are my best ads / competitor research" | Phase 1 only (+ browser/canvas) |
| "Browse / open Ad Library research UI" | Rebuild browser + canvas from run dir |

## Safety rules

- **Ads deploy PAUSED.** Never add an `--active` override or un-pause ads without
  an explicit user instruction. Confirm the user knows the ads are paused.
- **Dry-run before every real deploy.** Show the payload; get a go-ahead.
- **Confirm the target ad set and destination URL** with the user before
  deploying — an ad in the wrong ad set spends against the wrong budget.
- **Deploying ads is a shared-state, money-adjacent action.** Treat the live
  `deploy-ad.py` run as something to confirm, not assume.
- The skill creates ads only — it does **not** create or edit campaigns, ad sets,
  budgets, or audiences. Those stay manual.

## Quirks and pitfalls

- **Video processing is async.** `deploy-ad.py` polls the uploaded video until
  Meta finishes processing before creating the ad — a video deploy can take a
  few minutes. See [deploy-patterns.md](reference/deploy-patterns.md).
- **Transient `OAuthException` (code 2).** Retried automatically with backoff.
- **`act_` prefix** is added automatically if missing from `META_AD_ACCOUNT_ID`.
- **Account-specific data stays out of git.** All output routes through
  `outputs/` (gitignored): ad IDs, pulled spend/revenue, competitor data.
- **Special Ad Categories** (credit, employment, housing, social issues) change
  ad-set targeting rules — flag to the user; see cheatsheet §3.5.

## Cost note

The Meta Marketing API itself is free to call. **Ad spend is real money** — but
because every ad deploys PAUSED, nothing spends until the user un-pauses it in
Ads Manager. There are no per-call credits to estimate.
