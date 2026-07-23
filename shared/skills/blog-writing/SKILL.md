---
name: blog-writing
description: >-
  Write and publish candid journey blog posts about building Our Tech Accessories
  and the ad-ops-agent experiment. First-person UK English with light humour,
  evidence from the repo, Hashnode GraphQL draft-first publishing. Use when the
  user asks for a blog post, founder log, build diary, Hashnode draft/publish,
  journey update, SEO packaging for a post, or editing existing blog/posts content.
---

# Blog writing (journey log)

Write and optionally publish **James Miller's** public build diary: evenings after a UK lead-developer day job, a bit of side-income ambition, and honest curiosity about whether a calm tech store can work without the classic dropshipping carnival.

**Publication feel:** engineer in the pub, not guru on a stage.  
**Point of view:** James's lived decisions and storefront outcomes. Agents are leverage in the background, not the narrator's co-star.  
**Publication:** Evening Ops — `https://eveningops.hashnode.dev` (`HASHNODE_HOST=eveningops.hashnode.dev`).  
**Branding:** [`blog/branding/DIRECTIONS.md`](../../../blog/branding/DIRECTIONS.md) — EO squircle + amber; do not use the store OT mark on the blog.  
**Host API:** Hashnode GraphQL `https://gql-beta.hashnode.com`. **Writes need Hashnode Pro**.

**Canonical posts:** committed under `blog/posts/`. Skill pack stays generic; story facts come from **James** first, then local `MASTER_CONTEXT.md` filtered through the perspective rules in [voice-and-story.md](prompting/voice-and-story.md).

## When to use

- "Write a blog post" / "founder log" / "journey update" / "build diary"
- "Draft this for Hashnode" / "publish the blog post"
- Editing anything under `blog/posts/`

Do **not** use for Shopify PDP/homepage copy (`shopify-store`) or Meta ad copy (`meta-ad-builder`).

## Read order

1. **This file** — workflow, safety, CLI.
2. **[prompting/voice-and-story.md](prompting/voice-and-story.md)** — voice, humour, narrative shape.
3. **[prompting/quality-bar.md](prompting/quality-bar.md)** — definition of done before draft/publish.
4. **[prompting/screenshots.md](prompting/screenshots.md)** — storefront captures under `images/`.
5. **[prompting/project-schema.md](prompting/project-schema.md)** — `post.md` + `post.json` layout.
6. Local **`MASTER_CONTEXT.md`** — brand facts, changelog (source of truth for what actually happened).
7. Repo **`blog/README.md`** — publication purpose + Hashnode signup checklist.

## Project layout

Committed source of truth:

```
blog/posts/<YYYY-MM-DD>-<slug>/
  post.md      # body (markdown)
  post.json    # metadata + Hashnode ids after sync
```

Optional scratch (gitignored): `outputs/blog/...` — prefer committing finished posts under `blog/posts/`.

## Prerequisites

`.env` (see `.env.example`):

| Var | Required for | Notes |
|-----|--------------|-------|
| `HASHNODE_PAT` | whoami / draft / publish | Personal Access Token |
| `HASHNODE_PUBLICATION_ID` | draft / publish | Publication ObjectId |
| `HASHNODE_HOST` | optional | e.g. `yourblog.hashnode.dev` |
| `HASHNODE_GQL_URL` | optional | default `https://gql.hashnode.com` |

```bash
bash shared/skills/blog-writing/scripts/check-hashnode-env.sh
```

If credentials are missing: still write the local post; stop before network writes and tell James to complete the Hashnode Pro + PAT checklist in `blog/README.md`.

## Hard rules

1. **Local first.** Finish `post.md` + `post.json` and pass the quality bar before any API call.
2. **Draft by default.** `upsert-draft` is the normal remote action. Never publish without an explicit user yes.
3. **Dry-run / preview** before the first live draft upsert for a post.
4. **James's perspective only.** Write what he noticed, decided, or felt. Do **not** narrate agent-only internals (CDN blocks, model strings, credit tables, ffmpeg stitches, env-check scripts) unless he asks for that beat.
5. **Changelog ≠ autobiography.** Use `MASTER_CONTEXT.md` / `outputs/` as evidence of approved decisions; filter out session leftovers he never saw. When unsure, ask.
6. **No invented results.** No fake sales, ROAS, or "it works" claims. Distinguish shipped facts vs still experimental.
7. **No money figures** unless James supplies them for that post.
8. **Tax honesty.** Research / curiosity only unless James states otherwise. Do not invent VAT registration or company status.
9. **Supplier criticism = policy fit.** Returns, freight, reliability documentation: not accusations. Prefer "I moved because of X policy" over "they are scammers."
10. **Secrets stay in `.env`.** Never log or commit `HASHNODE_PAT`. Mask tokens in check output.
11. **Identity:** James Miller + Our Tech Accessories unless a post's `post.json` overrides.
12. **Em dashes:** Prefer colon, period, or comma in published prose (same tell as storefront copy). Occasional en dash in date ranges is fine.

## Workflow

### Phase 1 — Brief

Confirm with James (or infer from chat + `MASTER_CONTEXT.md`):

- Topic / date window
- What is in-scope vs off-limits
- Money disclosure level (default: no numbers)
- Publish target: local only | Hashnode draft | publish after approval

### Phase 2 — Outline

Use the story spine in [voice-and-story.md](prompting/voice-and-story.md). Show a short outline; adjust once if needed.

### Phase 3 — Draft locally

```bash
mkdir -p blog/posts/<YYYY-MM-DD>-<slug>
# write post.md + post.json per prompting/project-schema.md
```

Write first person as James. Light humour. Prefer beats he lived (storefront, suppliers, policy, mobile). Use changelog / `outputs/` only after the perspective filter. Capture storefront screenshots per [screenshots.md](prompting/screenshots.md) and place them next to the prose they illustrate. End understated (invite the next log, not a hard sell).

### Phase 4 — Quality gate

Run through [quality-bar.md](prompting/quality-bar.md). Fix before remote steps.

### Phase 5 — Preview payload

```bash
python3 shared/skills/blog-writing/scripts/hashnode_cli.py preview \
  --project blog/posts/<YYYY-MM-DD>-<slug>
```

### Phase 6 — Upsert Hashnode draft

```bash
python3 shared/skills/blog-writing/scripts/hashnode_cli.py upsert-draft \
  --project blog/posts/<YYYY-MM-DD>-<slug>
```

Writes `hashnode.draftId` (and related fields) back into `post.json`.

### Phase 7 — Publish (explicit yes only)

```bash
python3 shared/skills/blog-writing/scripts/hashnode_cli.py publish \
  --project blog/posts/<YYYY-MM-DD>-<slug>
```

Writes `hashnode.postId`, `url`, `publishedAt` into `post.json`.

## CLI reference

| Command | Purpose |
|---------|---------|
| `whoami` | Validate PAT; list publications |
| `preview --project <dir>` | Print GraphQL input JSON (no network write) |
| `upsert-draft --project <dir>` | Create or update draft |
| `publish --project <dir>` | `publishDraft` (or `publishPost` if no draft) |
| `update-post --project <dir>` | Update an already-published post |

All write commands accept `--dry-run` (builds payload, no mutation).

## Logging

Append a dated note to local `MASTER_CONTEXT.md` Changelog when a post is drafted or published (Decision / What changed / Why). Do not commit `.env`.
