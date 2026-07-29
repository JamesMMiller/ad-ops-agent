@shared/CLAUDE.md

# Session rules — ad-ops-agent

- **API:** KIE.ai (`https://api.kie.ai`) when `AD_OPS_BACKEND=kie`.
- **Auth:** Bearer via `KIE_API_KEY`. Setup check: `./scripts/check-kie-env.sh`.
- **Skill:** `.claude/skills/kie-external-api/SKILL.md` for API calls, prompts, and polling.
- **YouTube thumbnails:** `.claude/skills/generate-youtube-thumbnail/SKILL.md`.
- **Image-ad ecosystem:** read `shared/skills/image-ad-prompting/OVERVIEW.md` FIRST (`chatgpt-image-ad`, `nano-banana-image-ad`, `image-ad-clone`). Meta upload is the separate `meta-ad-builder` skill.
- **Local video post:** `.claude/skills/edit-video/SKILL.md` (ffmpeg soft-stitch — no API).
- **Shopify storefront:** `.claude/skills/shopify-store/SKILL.md` — products, pages, metafields, theme files via Admin API (`check-shopify-env.sh`). PDP quality bar: `prompting/pdp-quality-bar.md`. Volume/mix packs: `prompting/bulk-pack.md` (`templateSuffix: bulk-pack`).
- **Journey blog:** `.claude/skills/blog-writing/SKILL.md` — `blog/posts/` source + Hashnode draft-first publish (`check-hashnode-env.sh`).
- **Store inbox:** `.claude/skills/store-inbox/SKILL.md` — `hello@` + Gmail Apps Script triage (ImprovMX / escalate customers).
- **Google Apps Script (generic):** `.claude/skills/google-apps-script/SKILL.md` — author/install `.gs` helpers (mailbox guard, properties, triggers).
- **Meta ads:** `.claude/skills/meta-ad-builder/SKILL.md` (optional). Ad Library research browser: `reference/ad-library-research.md`.
- **Meta video default:** `1:1` for creatives that must run on Instagram + Facebook feed.
- **Cost disclosure:** Always present credit totals as **estimates**. Confirm on [kie.ai/pricing](https://kie.ai/pricing) / [kie.ai/logs](https://kie.ai/logs).
- **Logging:** Log every generation call to `logs/kie-api.jsonl`.
- **First-time setup:** If `.env` is missing, run `./scripts/setup.sh --with-kie`. If `MASTER_CONTEXT.md` is missing, copy `MASTER_CONTEXT.template.md` to `MASTER_CONTEXT.md`.
