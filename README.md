# Ad Ops Agent

Brief, generate, organize, and iterate AI marketing creatives **from your IDE** (Cursor, Claude Code, or any assistant that reads `AGENTS.md`).

**Primary backend:** [KIE.ai](https://kie.ai) — Seedance, Veo, Sora, Kling, Nano Banana, ChatGPT Image 2, and more via one API key. Pair that with a **37-template** Meta image-ad library, **Pixar / claymation** pipelines, local **ffmpeg** edit helpers, and optional **Meta ad publishing**.

> **Origins:** This project started as a fork of Caleb Kruse’s ([Mr. Paid Social](https://skool.com/mrpaidsocial)) open skill pack. It is maintained as a **standalone** IDE ad-ops agent; KIE is the default generative path. Credit for the original creative workflows and prompt libraries goes to that upstream work.

**Architecture (how agents, skills, and APIs fit together):** **[ARCHITECTURE.md](ARCHITECTURE.md)**

## 🎥 Walkthrough (original pack)

[![How To Build Entire AI Ad Campaigns With Claude Code (free repo)](https://i.ytimg.com/vi/HHGQN9Zqaxo/hqdefault.jpg)](https://youtu.be/HHGQN9Zqaxo)

**[How To Build Entire AI Ad Campaigns With Claude Code](https://youtu.be/HHGQN9Zqaxo)** — tutorial by Mr. Paid Social covering the creative skill-pack approach this repo builds on.

## Prerequisites

| Tool | Required for | Install (macOS) |
|---|---|---|
| **Python 3.10+** | Image-ad generators (stdlib-only) | preinstalled or `brew install python@3.12` |
| **`ffmpeg`** | Stitching, soft-crossfade, captions, Pixar/claymation | `brew install ffmpeg` |
| **`jq`** | Several bash pipelines | `brew install jq` |
| **Node.js + `npx hyperframes`** | Caption burn-in | `brew install node` |
| **`whisper`** | Caption transcription | `pip install openai-whisper` |
| **`meta-ad-builder` deps** | Publishing to Meta | `pip install -r shared/skills/meta-ad-builder/scripts/requirements.txt` |
| **`shopify-store` deps** | Shopify Admin API scripts | `pip install -r shared/skills/shopify-store/scripts/requirements.txt` |
| **Shopify CLI** (optional) | Theme push fallback | `npm install -g @shopify/cli @shopify/theme` |

Linux: `apt install ffmpeg jq nodejs python3`. Windows: WSL2 recommended.

## Get started (5 minutes)

### 1. Clone

```bash
git clone https://github.com/JamesMMiller/ad-ops-agent.git
cd ad-ops-agent
```

### 2. Setup + KIE key

1. Get an API key at **[kie.ai/api-key](https://kie.ai/api-key)**
2. Run:

```bash
./scripts/setup.sh --with-kie
```

Or interactive `./scripts/setup.sh` and choose **Configure KIE.ai**.

Setup:
- Creates `.env` with `AD_OPS_BACKEND=kie`
- Creates your personal `MASTER_CONTEXT.md`
- Syncs skills into `.cursor/skills/` and `.claude/skills/`

Then paste the key into `.env` (`KIE_API_KEY=...`) and verify:

```bash
./scripts/check-kie-env.sh
```

### 3. Open in your AI editor

| Editor | What loads automatically |
|--------|--------------------------|
| **Cursor** | `.cursor/hooks.json` `sessionStart` syncs skills + orientation banner; rules in `.cursor/rules/` |
| **Claude Code** | `.claude/settings.json` `SessionStart` |
| **Other agents** | Point at [`AGENTS.md`](AGENTS.md) + `MASTER_CONTEXT.md` + `skills/` / `shared/skills/` |

### 4. Start creating

The agent handles API calls, polling, prompt engineering, file organization, and **credit confirmation before generate**.

---

### 🎬 Seedance videos (flagship)

Seedance on KIE: 4–15s clips, native audio, image refs. Prompt formulas ship under `skills/kie-external-api/prompting/prompt-library/`.

#### UGC selfie-style product review

> "Make a 12-second Seedance UGC video — woman in a kitchen, holding the product, says she stopped buying [competitor]"

#### Premium product reveal (no person)

> "Premium reveal of [product] — dark void, text narrative, hero rotation"

#### Studio lookbook with voiceover

> "Studio lookbook of [product] — multi-look, polished, with voiceover script"

#### Feature walkthrough / product hero

> "Seedance feature walkthrough — fast-paced, show off [features]"

**Meta dual-placement tip:** default video creatives that must run on **Instagram + Facebook feed** to **`1:1`**. Use `9:16` only for Stories/Reels-only.

Longer scripts: Seedance max is ~15s per clip — generate segments, then soft-stitch locally with `shared/skills/edit-video/`.

---

### 🎬 Other video models (via KIE)

| Model | Typical ask |
|-------|-------------|
| **Veo 3** | "Animate this still into an 8s Veo with dialogue" |
| **Sora 2** | "Generate a 16s Sora video of [scene]" |
| **Kling** | "Make a 5s b-roll clip of [scene]" |

See `skills/kie-external-api/SKILL.md` for model → endpoint mapping.

---

### 🖼️ Images (Nano Banana + ChatGPT Image 2)

> "Create a new AI influencer — 22-year-old college student…"  
> "UGC selfie of Sofia holding [product]"  
> "Translate this Korean product graphic into English" (edit mode + reference URL)

Default still model: `nano-banana-2`. Use `nano-banana-pro` for tighter identity lock; `nano-banana-edit` to edit an existing hosted image.

**KIE refs are public URLs only** — record your hosting approach in `MASTER_CONTEXT.md` (*Image hosting*).

---

### 📸 Static Meta image ads (37-template library)

> "Make me an Apple Notes-style ad" / "Clone this comparison-table ad as a template"

- **`chatgpt-image-ad`** — typography / UI mimicry (`gpt-image-2`)
- **`nano-banana-image-ad`** — photoreal / lifestyle
- **`image-ad-clone`** — reverse-engineer an existing ad into the shared library

Read **`shared/skills/image-ad-prompting/OVERVIEW.md`** first. Hand off finished images to `meta-ad-builder` to publish (PAUSED).

---

### 🎞️ Multi-step pipelines & local post

| Workflow | Path |
|----------|------|
| Pixar-style animated ad | `shared/skills/pixar-style-ad/` |
| Claymation ad | `shared/skills/claymation-ad/` |
| YouTube thumbnails | `skills/generate-youtube-thumbnail/` |
| Soft-stitch / crossfade clips | `shared/skills/edit-video/` |
| Burn captions | `shared/skills/caption-video/` |
| Publish to Meta (PAUSED) | `shared/skills/meta-ad-builder/` |
| Update Shopify storefront | `shared/skills/shopify-store/` |

### 🛍️ Shopify storefront

> "Update the homepage" / "refresh a product page" / "draft PDP copy for review"

`shopify-store` skill — Admin GraphQL for products, pages, files, and theme templates. Dev Dashboard **client ID + secret** in `.env` (client credentials grant). Always `--dry-run` before live writes.

**Store-specific copy lives under `outputs/shopify/projects/` (gitignored)** — not in the skill pack.

```bash
python3 -m venv .venv-shopify && source .venv-shopify/bin/activate
pip install -r shared/skills/shopify-store/scripts/requirements.txt
bash shared/skills/shopify-store/scripts/check-shopify-env.sh
python shared/skills/shopify-store/scripts/apply_product_project.py \
  --project outputs/shopify/projects/<name> --dry-run
```

---

## What's in the box

| Path | What it does |
|------|-------------|
| `skills/kie-external-api/` | **Core skill.** KIE endpoints, auth, polling, Seedance / Veo / Sora / Nano Banana prompt libraries |
| `skills/generate-youtube-thumbnail/` | CTR thumbnail formulas + batch generation |
| `skills/chatgpt-image-ad/` · `nano-banana-image-ad/` · `image-ad-clone/` | Static Meta image-ad family |
| `shared/skills/image-ad-prompting/` | 37 templates, safety suffixes, `OVERVIEW.md` |
| `shared/skills/edit-video/` | Local ffmpeg soft-stitch (no API) |
| `shared/skills/pixar-style-ad/` · `claymation-ad/` · `caption-video/` | Multi-step creative pipelines |
| `shared/skills/shopify-store/` | Shopify Admin API — products, pages, theme files |
| `shared/skills/meta-ad-builder/` | Meta Marketing API publish (PAUSED) |
| `MASTER_CONTEXT.template.md` | Template for workspace memory |
| `scripts/setup.sh` · `check-kie-env.sh` · `sync-skill.sh` | Setup, auth check, skill sync |
| `logs/kie-api.jsonl` | Per-call audit log (powers credit estimates) |
| `references/` · `outputs/` | Local media (gitignored) |

## Your API key

KIE authenticates with a Bearer token. Paste once into `.env` as `KIE_API_KEY` — never into chat.

- Keys: **[kie.ai/api-key](https://kie.ai/api-key)**
- Pricing / logs: **[kie.ai/pricing](https://kie.ai/pricing)** · **[kie.ai/logs](https://kie.ai/logs)** · **[kie.ai/market](https://kie.ai/market)**

For Meta publishing, add `META_ACCESS_TOKEN` / `META_AD_ACCOUNT_ID` (see `.env.example`).

## Project memory

`MASTER_CONTEXT.md` (created by setup, gitignored) stores brand voice, credit costs, confirmed model strings, image-hosting strategy, Meta defaults (including **`1:1` video for IG+FB feed**), and a changelog. Agents read it every session and write learnings back.

## Supported models (KIE)

Exact `model` strings vary by marketplace listing — confirm on [kie.ai/market](https://kie.ai/market) and record verified strings in `MASTER_CONTEXT.md`.

| Family | Best for |
|--------|----------|
| **Seedance 2** (`bytedance/seedance-2`, `-fast`, `-mini`) | Flagship short video, UGC, reveals, lookbooks |
| **Veo 3** | Still → video, dialogue clips |
| **Sora 2** | Longer text/image → video |
| **Kling** | B-roll / scenes |
| **Nano Banana 2 / Pro / Edit** | Stills, character sheets, image-ad photoreal, inpaint |
| **ChatGPT Image 2** | Typography-heavy static ads / storyboards |

Cost is always an **estimate** before generate — confirm on the KIE dashboard when budgeting.

## Reference images

Drop files into `references/influencers/`, `references/products/`, `references/aesthetics/`. For KIE generation, host them at a public URL first (see *Image hosting* in `MASTER_CONTEXT.md`).

## Editing skills

Canonical sources live in `skills/` and `shared/skills/`. After edits:

```bash
./scripts/sync-skill.sh
```

Session-start hooks also sync automatically in Cursor / Claude Code.

## Staying current

```bash
git pull origin main
./scripts/sync-skill.sh
```

`.env`, `MASTER_CONTEXT.md`, `references/`, and `outputs/` are gitignored and survive updates.

## Security

- `.env` and `MASTER_CONTEXT.md` are gitignored
- Never paste API keys in issues or public chats
- Meta ads via `meta-ad-builder` are created **PAUSED**

## Vendor prompting guides

| Model | Guide |
|-------|--------|
| Seedance | Summarized in `skills/kie-external-api/prompting/prompt-library/seedance-2.md` |
| Sora 2 | [OpenAI Sora 2 prompting](https://developers.openai.com/cookbook/examples/sora/sora2_prompting_guide) |
| Veo | [Google — Veo](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1) |
| Nano Banana | [Google — Nano Banana](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana) |
| ChatGPT Image 2 | `shared/skills/chatgpt-image-ad/prompting/guide.md` |

## API docs

- [KIE docs](https://docs.kie.ai) · [Market models](https://kie.ai/market)

## Other AI assistants

Point them at [AGENTS.md](AGENTS.md), `MASTER_CONTEXT.md`, and `skills/` / `shared/skills/`.

---

### Optional: media-buying community

This creative stack sits next to Caleb’s private Skool community — **[The AI Ad Alchemists](https://skool.com/mrpaidsocial)** — for ROAS systems, Meta masterclass material, and peer help. Useful if you want strategy beyond generating creatives; not required to use this repo.
