## This repo specifically

- **API:** Arcads external API (`https://external-api.arcads.ai`).
- **Auth:** HTTP Basic via `ARCADS_BASIC_AUTH` (pre-encoded `Basic ...` header) or `ARCADS_API_KEY` as the Basic password. Values in `.env` must be **single-quoted** due to special characters.
- **IDE-agnostic fork:** This repo is `arcads-ide-agnostic`, kept in sync with upstream `krusemediallc/arcads-claude-code` `main`. Cursor: `.cursor/hooks.json` `sessionStart` + `.cursor/rules/`. Claude Code: `.claude/settings.json`. Other agents: this file + `skills/` / `shared/skills/`.
- **Skills:**
  - `arcads-external-api` — main API reference (endpoints, auth, polling, asset routing).
  - `generate-youtube-thumbnail` — YouTube thumbnail batch workflow on top of the Nano Banana 2 image endpoint.
  - **Image-ad ecosystem** (3 skills + shared 37-template library) — see [shared/skills/image-ad-prompting/OVERVIEW.md](shared/skills/image-ad-prompting/OVERVIEW.md):
    - `chatgpt-image-ad` — generate via Arcads `gpt-image-2` (typography / UI-mimicry creatives)
    - `nano-banana-image-ad` — generate via Arcads `nano-banana-2`/`-pro`/`-edit` (photoreal / lifestyle creatives)
    - `image-ad-clone` — single backend-agnostic skill that reverse-engineers existing ads into reusable templates (asks which backend to validate against at Phase 1; optionally cross-validates at Phase 8)
- **Setup check:** `./scripts/check-arcads-env.sh`.
