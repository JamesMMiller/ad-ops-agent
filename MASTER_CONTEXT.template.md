<!-- DO NOT EDIT — this file is auto-generated.
     The repo-specific section lives in MASTER_CONTEXT.template.tail.md; edit there. -->

# Master context (project + agents)

**Purpose:** One place for humans and AI agents to capture **decisions**, **brand voice**, **API quirks**, and **what we learned** while using this repo.

## How agents should use this file

- **At the start of substantive work:** Read this file for project-specific context that is not in the skill.
- **After meaningful changes:** Append a new **dated entry** under [Changelog](#changelog) (Decision / What changed / Why).
- **If fields are empty:** Offer to populate them — ask the user once and write the values back.

## Brand (optional)

_Edit or replace with your real brand blocks. A starter template lives at `skills/<this-repo's-api>-external-api/prompting/brand-voice-starter.md` (e.g. `skills/arcads-external-api/...` in the Arcads repo, `skills/kie-external-api/...` in the KIE repo)._

- **Tone:**
- **Audience:**
- **Words to use / avoid:**

## Reference images

Drop reference images into the `references/` folder at the repo root:
- `references/influencers/` — face/body photos to recreate as AI people
- `references/products/` — product photos for showcase workflows
- `references/aesthetics/` — mood boards, lighting references, style inspiration

The agent checks this folder when composing prompts. (If the API in this repo requires hosted URLs rather than local file uploads, also fill in your hosting strategy in the API-specific section below.)

## Universal prompting principles

These apply across all generative-image and generative-video APIs.

### UGC realism

- **Imperfection block (camera):** Every UGC image/video prompt must include camera imperfections: motion blur, overexposure, grain, lens distortion, off-center framing, soft focus. Without this, output looks too polished.
- **Skin realism block (mandatory):** Include 3–4 subtle skin cues inline with character description: "visible pores, slight unevenness in skin tone, minor undereye shadows, hint of shine from natural oils." Do NOT use: acne, pimples, breakouts, blemishes, redness. Goal is "real person, not retouched" — not "person with skin problems."
- **Reference image order:** character hero first (strongest identity signal), then product, then style refs.

### Influencer / character recreation

- Two-step flow: (1) generate a still image with the reference image as input, (2) show user for approval, (3) only then generate video using the approved still as the start frame / reference.
- Never skip the approval step — video is expensive, stills are cheap to iterate.

### Image QA

- Visually review still images after generation (hands, fingers, limbs, face, merged objects, artifacts).
- If defective, regenerate with refined prompt — up to **2 retries** (3 attempts total).
- QA retries skip a second credit confirmation but still bill credits.

### Video prompting

- **No subtitles, no captions, no text overlays** — append this clause to every prompt; many video models burn captions in by default.
- **Human motion cues are mandatory** for person-on-screen videos: 3–4 cues per prompt (breaking eye contact, head tilts, weight shifts, grip adjustments). Without these, subjects look like frozen mannequins.

## Meta ad deployment

Used by the **`meta-ad-builder`** shared skill (`shared/skills/meta-ad-builder/`) — publishes
finished creatives as Meta (Facebook/Instagram) ads. Fill in your account IDs once; the skill
reads them so you don't paste them every run. These are account identifiers, not secrets, but
the file is gitignored either way.

- **Default video aspect ratio:** `1:1` (square) — required for creatives that run on both Instagram and Facebook feed. Do **not** default to `9:16` for Meta dual-placement video unless the user explicitly wants Stories/Reels-only.
- **Default ad account** (`META_AD_ACCOUNT_ID`):
- **Facebook Page ID** (`META_PAGE_ID`):
- **Instagram user ID** (`META_IG_USER_ID`):
- **Meta Pixel ID** (`META_PIXEL_ID`):
- **Default destination URL / offer link:**
- **Default ad set(s) to deploy into** (name → ID):
- **Default CTA type** (e.g. `SIGN_UP`, `LEARN_MORE`):

The access token itself (`META_ACCESS_TOKEN`) lives in `.env`, never here. Every ad the skill
creates is **PAUSED** — review and un-pause in Meta Ads Manager.

## Shopify storefront

Used by **`shopify-store`** (`shared/skills/shopify-store/`) — updates products, Online Store pages, files, and theme templates via the Admin GraphQL API.

- **Shop domain** (`SHOPIFY_SHOP`): _(e.g. `your-store.myshopify.com`)_
- **Primary product handle(s)** (campaign URL locks): _(fill locally — never commit secrets)_
- **Local project dirs:** `outputs/shopify/projects/<name>/` (gitignored)
- **Main theme ID** (`SHOPIFY_THEME_ID` in `.env` or record GID here after `list-themes`):
- **Storefront goals:** _(homepage hero, PDP refresh, etc.)_

Client ID and client secret live in `.env` only (`SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`). Optional `SHOPIFY_THEME_ACCESS_PASSWORD` for Shopify CLI theme push fallback.



## Project snapshot — KIE.ai

- **API base:** `https://api.kie.ai` (see `.env.example`).
- **Auth:** Bearer token (`KIE_API_KEY`).
- **Backend flag:** `AD_OPS_BACKEND=kie`
- **Skills:**
  - `.claude/skills/kie-external-api/` and `.cursor/skills/kie-external-api/` (sync from `skills/kie-external-api/` via `scripts/sync-skill.sh`).
  - `.claude/skills/generate-youtube-thumbnail/` (and Cursor equivalent) for YouTube thumbnails.
  - `.claude/skills/edit-video/` — local ffmpeg soft-stitch (no API).
- **Dashboard:** [kie.ai/logs](https://kie.ai/logs) · [kie.ai/api-key](https://kie.ai/api-key) · [kie.ai/pricing](https://kie.ai/pricing) · [kie.ai/market](https://kie.ai/market)
- **Setup check:** `./scripts/check-kie-env.sh`

## Image hosting (required for KIE refs)

KIE does **not** provide a presigned-upload flow. Reference images must be at **publicly reachable URLs**. Record your hosting strategy here:

- **Host:** _(e.g. Cloudflare R2 public bucket, S3, Cloudinary, Shopify CDN, imgur)_
- **Upload flow:** _(brief — how you get from a local file in `references/` to a hosted URL)_
- **URL lifetime:** _(permanent? 24h? note any expiry)_

Agents should **stop and ask** for a hosted URL before firing any generation that needs references if this section is empty.

## Credit costs (KIE)

_Fill in your account's credit costs below. The agent references this table before every generation. Check [kie.ai/pricing](https://kie.ai/pricing) and [kie.ai/logs](https://kie.ai/logs) for current values._

| Model | `model` string | Credits / cost per generation | Notes |
|-------|---------------|-------------------------------|-------|
| Seedance 2 Fast | `bytedance/seedance-2-fast` | **396 credits / 12s** @ 720p (~33 cr/sec) | Confirmed 2026-07-19 |
| Seedance 2 | `bytedance/seedance-2` | ~41 cr/sec @ 720p | Confirmed 2026-07-19 (12s+8s jobs) |
| Seedance 2 Mini | `bytedance/seedance-2-mini` | ~20.5 cr/sec @ 720p | Confirmed 2026-07-19 |
| Veo 3 Fast | `veo3_fast` | _(fill in)_ | |
| Nano Banana 2 | `nano-banana-2` | _(fill in)_ | |
| Nano Banana Edit | `nano-banana-edit` | _(fill in)_ | |

## Confirmed model strings

Record exact KIE `model` strings that you've verified work in your account:

- `bytedance/seedance-2-fast` (2026-07-19)
- `bytedance/seedance-2` (2026-07-19)
- `bytedance/seedance-2-mini` (2026-07-19)
- `nano-banana-2` / `nano-banana-edit` — verify on marketplace before first use

## API learnings — KIE.ai

### Auth

- Bearer token on every request: `Authorization: Bearer $KIE_API_KEY`.
- Connectivity check: `GET /api/v1/chat/credit` (also returns balance).

### Endpoint families

- **Veo (first-party):** `POST /api/v1/veo/generate` → `GET /api/v1/veo/record-info?taskId=...`
- **Jobs (marketplace):** `POST /api/v1/jobs/createTask` → `GET /api/v1/jobs/recordInfo?taskId=...`

### Reference images

- URL-based only (`imageUrls` / `input.image_input` / `reference_image_urls`). No local file upload.
- Minimum longest-side **1024 px** recommended.

### Aspect ratio (Meta)

- Default **`1:1`** for video creatives that must run on Instagram + Facebook feed.
- Use `9:16` only for Stories/Reels-only placements.

### Logging

- Append every generation to `logs/kie-api.jsonl` (see `logs/README.md`).
