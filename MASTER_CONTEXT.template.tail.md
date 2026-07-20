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
