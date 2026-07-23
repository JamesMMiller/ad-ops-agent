# Ad Ops Agent

Brief, generate, organize, and iterate AI marketing creatives **from your IDE** (Cursor, Claude Code, or any assistant that reads `AGENTS.md`).

**Primary backend:** [KIE.ai](https://kie.ai) — Seedance, Veo, Sora, Kling, Nano Banana, ChatGPT Image 2, and more via one API key. Pair that with a **37-template** Meta image-ad library, **Pixar / claymation** pipelines, local **ffmpeg** edit helpers, optional **Meta ad publishing**, a **Shopify storefront** skill, and a **Hashnode journey blog** (organic-traffic experiment; see [Step 11](#step-11--journey-blog-optional-but-part-of-the-experiment)).

**Architecture (how agents, skills, and APIs fit together):** **[ARCHITECTURE.md](ARCHITECTURE.md)**

> Credit: creative workflow patterns and prompt libraries originated in an open skill pack by [Mr. Paid Social](https://skool.com/mrpaidsocial). This repo is maintained as a **standalone** IDE ad-ops agent with KIE as the default generative path.

---

## Full walkthrough

This is the end-to-end guide for **this** repo. No external video required.

### Step 0 — What you will be able to do

After setup, you open the repo in Cursor (or Claude Code), talk in plain English, and the agent:

1. Reads your brand notes from `MASTER_CONTEXT.md`
2. Picks the right skill (video, still, image ad, Shopify, Meta)
3. Estimates cost, confirms with you, then calls KIE (or Shopify / Meta)
4. Saves outputs under `outputs/` and logs API calls under `logs/`

You do **not** need to learn every endpoint. You do need a KIE key for generation, and optional Shopify / Meta credentials for those surfaces.

---

### Step 1 — Prerequisites

| Tool | Required for | Install (macOS) |
|---|---|---|
| **Python 3.10+** | Image-ad generators, Shopify scripts | preinstalled or `brew install python@3.12` |
| **`ffmpeg`** | Stitching, soft-crossfade, captions, Pixar/claymation | `brew install ffmpeg` |
| **`jq`** | Several bash pipelines | `brew install jq` |
| **Node.js + `npx hyperframes`** | Caption burn-in | `brew install node` |
| **`whisper`** | Caption transcription | `pip install openai-whisper` |
| **`meta-ad-builder` deps** | Publishing to Meta | `pip install -r shared/skills/meta-ad-builder/scripts/requirements.txt` |
| **`shopify-store` deps** | Shopify Admin API scripts | `pip install -r shared/skills/shopify-store/scripts/requirements.txt` |
| **Shopify CLI** (optional) | Theme push fallback | `npm install -g @shopify/cli @shopify/theme` |

Linux: `apt install ffmpeg jq nodejs python3`. Windows: WSL2 recommended.

---

### Step 2 — Clone and run setup

```bash
git clone https://github.com/JamesMMiller/ad-ops-agent.git
cd ad-ops-agent
./scripts/setup.sh --with-kie
```

Or run interactive `./scripts/setup.sh` and choose **Configure KIE.ai**.

Setup will:

- Create `.env` with `AD_OPS_BACKEND=kie`
- Create your personal `MASTER_CONTEXT.md` (from the template)
- Sync skills into `.cursor/skills/` and `.claude/skills/`

Get a key at **[kie.ai/api-key](https://kie.ai/api-key)**, paste it into `.env`:

```bash
KIE_API_KEY=your_key_here
```

Verify:

```bash
./scripts/check-kie-env.sh
```

You should see a clean auth check. If it fails, fix the key (no quotes issues, no trailing spaces) and re-run.

---

### Step 3 — Open the repo in your AI editor

| Editor | What loads automatically |
|--------|--------------------------|
| **Cursor** | `.cursor/hooks.json` `sessionStart` syncs skills + orientation banner; rules in `.cursor/rules/` |
| **Claude Code** | `.claude/settings.json` `SessionStart` |
| **Other agents** | Point at [`AGENTS.md`](AGENTS.md) + `MASTER_CONTEXT.md` + `skills/` / `shared/skills/` |

**First chat:** ask the agent to read `MASTER_CONTEXT.md` and fill any empty fields (brand voice, default product, image hosting). Those values stick across sessions.

---

### Step 4 — Drop in reference media

Put local files here (gitignored):

```
references/products/     # product photos, packaging
references/influencers/  # face / character refs
references/aesthetics/   # mood / style boards
```

**Important for KIE:** generation endpoints need **public HTTPS URLs**, not local paths. Host refs (CDN, temporary public upload, Shopify Files, etc.) and record your approach under *Image hosting* in `MASTER_CONTEXT.md`. The agent should use those URLs when building prompts.

---

### Step 5 — Your first Seedance video (flagship path)

In chat, give a concrete brief. Examples:

> Make a 12-second Seedance UGC video — woman in a kitchen, holding the product, says she stopped buying [competitor]. Use my product ref URL from MASTER_CONTEXT.

> Premium reveal of [product] — dark void, text narrative, hero rotation. 1:1 for Meta feed.

What the agent should do (you can check against this):

1. Load `skills/kie-external-api/SKILL.md` (synced copy under `.cursor/skills/…`)
2. Pick a Seedance formula from `prompting/prompt-library/`
3. Show an **estimated** credit cost and wait for your OK
4. Create the task on KIE, poll until ready
5. Save the video under `outputs/` and append a line to `logs/kie-api.jsonl`

**Meta dual-placement tip:** default video creatives that must run on **Instagram + Facebook feed** to **`1:1`**. Use `9:16` only for Stories/Reels-only.

Longer scripts: Seedance max is ~15s per clip. Generate segments, then soft-stitch with `shared/skills/edit-video/`.

Other video models via the same skill:

| Model | Typical ask |
|-------|-------------|
| **Veo 3** | "Animate this still into an 8s Veo with dialogue" |
| **Sora 2** | "Generate a 16s Sora video of [scene]" |
| **Kling** | "Make a 5s b-roll clip of [scene]" |

---

### Step 6 — Stills and static Meta image ads

**Character / product stills (Nano Banana):**

> Create a UGC selfie of [character] holding [product]. Use nano-banana-2 and my hosted product URL.

Default still model: `nano-banana-2`. Use `nano-banana-pro` for tighter identity lock; `nano-banana-edit` to edit an existing hosted image.

**Static Meta ads (37-template library):**

> Make me an Apple Notes-style ad for [offer].

> Clone this comparison-table ad as a reusable template.

| Skill | When to use |
|-------|-------------|
| **`chatgpt-image-ad`** | Typography / UI mimicry (`gpt-image-2`) |
| **`nano-banana-image-ad`** | Photoreal / lifestyle |
| **`image-ad-clone`** | Reverse-engineer an existing ad into the shared library |

Read **`shared/skills/image-ad-prompting/OVERVIEW.md`** before the first image-ad job. Finished images hand off to `meta-ad-builder` when you are ready to publish (always **PAUSED**).

---

### Step 7 — Local post (optional but common)

| Workflow | Path | Typical ask |
|----------|------|-------------|
| Soft-stitch / crossfade | `shared/skills/edit-video/` | "Stitch these three Seedance clips with soft crossfades" |
| Burn captions | `shared/skills/caption-video/` | "Caption this UGC with burned-in subtitles" |
| Pixar-style ad | `shared/skills/pixar-style-ad/` | "Make a Pixar-style product ad" |
| Claymation ad | `shared/skills/claymation-ad/` | "Claymation version of this brief" |
| YouTube thumbnails | `skills/generate-youtube-thumbnail/` | "Three CTR thumbnail variants with my face ref" |

These skills expect `ffmpeg` (and captions need Node + whisper as listed above).

---

### Step 8 — Shopify storefront (optional)

Use when you want the agent to update products, pages, theme templates, or homepage sections via Admin GraphQL.

1. Create a Dev Dashboard app with Admin API scopes; put credentials in `.env`:

```bash
SHOPIFY_SHOP=your-store.myshopify.com
SHOPIFY_CLIENT_ID=...
SHOPIFY_CLIENT_SECRET=...
SHOPIFY_API_VERSION=2025-10
```

2. Install deps and verify:

```bash
python3 -m venv .venv-shopify && source .venv-shopify/bin/activate
pip install -r shared/skills/shopify-store/scripts/requirements.txt
bash shared/skills/shopify-store/scripts/check-shopify-env.sh
```

3. Keep **store-specific** copy and HTML under `outputs/shopify/projects/<name>/` (gitignored). The skill pack stays generic.

4. Always dry-run before live writes:

```bash
python shared/skills/shopify-store/scripts/apply_product_project.py \
  --project outputs/shopify/projects/<name> --dry-run
```

Then `--apply-draft` for Admin review, or `--apply-live` when you are sure.

Example chat briefs:

> Draft PDP copy for [product] and dry-run against Shopify.

> Soften the homepage hero overlay and swap the hero image to this Shopify Files URL.

Skill entry: `shared/skills/shopify-store/SKILL.md`. Customer-facing storefront copy should avoid em dashes.

---

### Step 9 — Publish to Meta (optional)

1. Add to `.env` (see `.env.example`):

```bash
META_ACCESS_TOKEN=...
META_AD_ACCOUNT_ID=act_...
# plus page / IG / pixel as needed
```

2. Install deps from `shared/skills/meta-ad-builder/scripts/requirements.txt`.

3. Ask in chat:

> Upload this creative and create a PAUSED ad in ad set [id] with TEXT_LIQUIDITY variants.

Ads are always created **PAUSED**. You turn them on in Ads Manager after review.

---

### Step 10 — Day-to-day habits

- **Confirm costs** before generate. Totals are estimates; check [kie.ai/pricing](https://kie.ai/pricing) and [kie.ai/logs](https://kie.ai/logs) for truth.
- **Never paste API keys in chat.** Keep them in `.env` only.
- **Write learnings back** to `MASTER_CONTEXT.md` (model strings that worked, brand rules, hosting pattern).
- **After editing skills**, run `./scripts/sync-skill.sh` (session-start hooks also sync in Cursor / Claude Code).
- **Stay current:**

```bash
git pull origin main
./scripts/sync-skill.sh
```

`.env`, `MASTER_CONTEXT.md`, `references/`, and `outputs/` are gitignored and survive updates.

---

### Quick prompt cheat sheet

Copy-paste starters once setup is done:

| Goal | Say this |
|------|----------|
| UGC video | "12s Seedance UGC — kitchen, holding product, competitor switch story, 1:1" |
| Product reveal | "Seedance premium reveal — dark void, hero rotation, no talent" |
| Still | "nano-banana-2 lifestyle still of [product] on white, edge-safe for Meta" |
| UI-style static ad | "chatgpt-image-ad Apple Notes list for [offer]" |
| Photoreal static ad | "nano-banana image ad — sticky note flatlay for [offer]" |
| Clone ad look | "Clone this ad image into a reusable template" |
| Stitch | "Soft-crossfade stitch these clips in outputs/…" |
| Shopify PDP | "Dry-run apply project outputs/shopify/projects/…" |
| Meta | "Publish this file as a PAUSED Meta ad in ad set …" |
| Journey blog | "Write the next Hashnode build-diary post from this week's changelog" |

---

### Step 11 — Journey blog (optional, but part of the experiment)

This repo also ships a **public build diary**: candid posts about evenings spent trying to make a bit of money online with [Our Tech Accessories](https://ourtechaccessories.com), without building another carnival-style dropshipping store.

**Why it lives in this repo:** James (UK lead developer by day) added blogging here on purpose, next to the ad-ops and Shopify tooling, to see whether writing openly about the journey can generate **organic traffic** back to the store. Same agent desk that writes PDPs and drafts Meta creatives can also draft Hashnode posts from the changelog.

**Honest expectation:** organic discovery is the goal; conversion from blog readers is not. If someone finds the diary, they will probably enjoy the scars and the tooling notes. They are very unlikely to buy a neck fan. That is fine. The blog is an SEO / storytelling experiment, not a secret sales funnel pretending to be a diary.

| Piece | Path |
|-------|------|
| Post source (committed) | [`blog/posts/`](blog/) |
| Voice + publish skill | [`shared/skills/blog-writing/`](shared/skills/blog-writing/SKILL.md) |
| Host | **Hashnode** — [Evening Ops](https://eveningops.hashnode.dev) (`eveningops.hashnode.dev`; **Pro** required for API writes) |
| Branding | [`blog/branding/`](blog/branding/) — EO mark, lockups, favicon, OG |
| First post | [`blog/posts/2026-07-23-lead-dev-dropshipping-calm-store/`](blog/posts/2026-07-23-lead-dev-dropshipping-calm-store/) |

Setup:

1. Read [`blog/README.md`](blog/README.md). Publication is **Evening Ops** at `eveningops.hashnode.dev` (Pro required for API writes).
2. Add to `.env`:

```bash
HASHNODE_PAT=...
HASHNODE_PUBLICATION_ID=...
HASHNODE_HOST=eveningops.hashnode.dev
```

3. Verify and draft:

```bash
bash shared/skills/blog-writing/scripts/check-hashnode-env.sh
python3 shared/skills/blog-writing/scripts/hashnode_cli.py upsert-draft \
  --project blog/posts/<YYYY-MM-DD>-<slug> --dry-run
```

Always upsert a **Hashnode draft** first; publish only with an explicit yes. Example chat: *"Write the next Hashnode build-diary post from this week's changelog."*

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
| `shared/skills/blog-writing/` | Journey blog voice + Hashnode draft/publish CLI |
| `blog/` | Committed post source (`blog/posts/<date>-<slug>/`) |
| `shared/skills/meta-ad-builder/` | Meta Marketing API publish (PAUSED) |
| `MASTER_CONTEXT.template.md` | Template for workspace memory |
| `scripts/setup.sh` · `check-kie-env.sh` · `sync-skill.sh` | Setup, auth check, skill sync |
| `logs/kie-api.jsonl` | Per-call audit log (powers credit estimates) |
| `references/` · `outputs/` | Local media (gitignored) |

## Your API key

KIE authenticates with a Bearer token. Paste once into `.env` as `KIE_API_KEY` — never into chat.

- Keys: **[kie.ai/api-key](https://kie.ai/api-key)**
- Pricing / logs: **[kie.ai/pricing](https://kie.ai/pricing)** · **[kie.ai/logs](https://kie.ai/logs)** · **[kie.ai/market](https://kie.ai/market)**

For Meta publishing, add `META_ACCESS_TOKEN` / `META_AD_ACCOUNT_ID`. For Shopify, add `SHOPIFY_*`. For the journey blog, add `HASHNODE_PAT` / `HASHNODE_PUBLICATION_ID` (see `.env.example`).

## Project memory

`MASTER_CONTEXT.md` (created by setup, gitignored) stores brand voice, credit costs, confirmed model strings, image-hosting strategy, Meta defaults (including **`1:1` video for IG+FB feed**), and a changelog. Agents read it every session and write learnings back.

## Supported models (KIE)

Exact `model` strings vary by marketplace listing. Confirm on [kie.ai/market](https://kie.ai/market) and record verified strings in `MASTER_CONTEXT.md`.

| Family | Best for |
|--------|----------|
| **Seedance 2** (`bytedance/seedance-2`, `-fast`, `-mini`) | Flagship short video, UGC, reveals, lookbooks |
| **Veo 3** | Still → video, dialogue clips |
| **Sora 2** | Longer text/image → video |
| **Kling** | B-roll / scenes |
| **Nano Banana 2 / Pro / Edit** | Stills, character sheets, image-ad photoreal, inpaint |
| **ChatGPT Image 2** | Typography-heavy static ads / storyboards |

Cost is always an **estimate** before generate. Confirm on the KIE dashboard when budgeting.

## Editing skills

Canonical sources live in `skills/` and `shared/skills/`. After edits:

```bash
./scripts/sync-skill.sh
```

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
