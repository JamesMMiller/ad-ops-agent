# Voice and story

This is a **build diary from James's chair**, not a transcript of an agent session. Readers should feel like they sat next to him for an evening while he poked at Shopify, suppliers, and creatives, then went to bed still employed as a lead developer.

## Who is speaking

**James Miller** — UK lead developer by day. Evenings (and the odd weekend) he is building **Our Tech Accessories** ([ourtechaccessories.com](https://ourtechaccessories.com)) and the **ad-ops-agent** repo as his ops desk.

Say the motivation mix out loud. Do not pretend it is pure art or pure greed:

1. Make a bit of cash on the side.
2. Real curiosity: can this work if you refuse the classic dropshipping look?
3. The blog lives in this repo on purpose as an **organic traffic** experiment. Diary readers are unlikely to buy anything. That is fine: understate conversion, overstate honesty.

## Perspective filter (critical)

Write only what **James would notice, decide, or feel**.

| Include | Exclude |
|---------|---------|
| Storefront outcomes he can see (domain, layout, returns copy, mobile ATC buried) + real screenshots | Agent debugging (CDN blocks, model strings, credit burns, polling, ffmpeg flags) |
| Supplier / policy decisions he made | Internal skill names as plot points (`seedance-2-mini`, `nano-banana-2`, `check-*-env.sh`) |
| "I asked the agent / used the repo to…" as light tooling colour | Pretending James personally discovered every API quirk |
| Changelog facts he approved | Session leftovers he never saw |

`MASTER_CONTEXT.md` and `outputs/` are **evidence**, not autobiography. If a beat only exists in agent notes and James did not experience it, omit it or ask him.

When unsure: **ask James**, or cut.

## Tone dial

Default setting: **calm engineer telling a story in the pub**, not a LinkedIn thought leader.

| Turn this up | Turn this down |
|--------------|----------------|
| Specific decisions and why | Vague inspiration |
| Dry understatement | Hype adjectives |
| Self-aware jokes about mess-ups he lived through | Cringe memes / emoji storms |
| Plain UK English | US ecom slang ("crushing it", "scale to 7 figures") |
| "I do not know yet" | Fake certainty |
| Human stakes (on the hook for refunds) | Tooling trivia |

### Humour that fits

- Operational absurdity he felt ("returns policy did the cha-cha: 30 → 14 → 30 in a day").
- Contrast: Apple/Samsung quiet vs carnival dropship stores.
- Developer reflexes: reading supplier policies at 11pm, then fixing the storefront promise to match.

### Humour that does not fit

- Mocking customers.
- Calling suppliers criminals without evidence.
- "AI will replace everyone" hot takes.
- Fake dialogue with imaginary haters.
- Inside jokes about agent retries, Catbox uploads, or credit tables.

## Story spine

Use this for flagship journey posts. Shorter updates can take **one chapter** and nod at the rest.

1. **Hook** — evenings after work; cash + curiosity; not quitting the day job.
2. **Aesthetic bet** — calm tech store (Apple/Samsung energy) over incentive clutter.
3. **Tooling** — `ad-ops-agent` as the ops desk he opens in Cursor (keep light; not a skill tour).
4. **Store + backend** — domain, branding, PDPs, honest shipping, tax *research* (not registration theatre).
5. **Supplier chapter** — QKSource → returns-policy mismatch → same product family on CJ Dropshipping.
6. **Policy roller coaster** — 30-day promise → UK 14-day minimum (on the hook if someone bought, waited a week, then refunded) → 30-day again after migrating the same stock family to CJ with a returns path he could stand behind.
7. **Ops reality** — UK freight dead-ends, mobile gallery pushing ATC down, ads left paused; creatives only as outcomes he reviewed.
8. **Honest status** — infrastructure feels promising; profitability is unproven.
9. **Soft close** — what he will log next; invite build-diary readers, not course buyers.

### Opening patterns that work

- Start in media res ("I spent an evening arguing with a product gallery that thought it was a skyscraper").
- Or start with the bet ("I do not want another dropshipping store that shouts. I want one that whispers 'this will just work'").

### Endings that work

- "Next up: …"
- "If this turns into anything, you will see the scars here first."
- Avoid "Link in bio / use code JAMES20."

## Evidence rules

Prefer concrete artifacts James owns:

- Decisions in `MASTER_CONTEXT.md` Changelog (filter through perspective filter above)
- Live domain and brand name
- Supplier move: QS → CJ for the neck fan; returns promise tied to that
- Storefront outcomes on `ourtechaccessories.com`

If evidence is missing, ask James or omit. **Never invent.**

## Money and tax defaults

Unless James overrides for a given post:

- **Money:** no revenue, ad spend, credit totals, or margins. "Pre-proof / experimental" is fine.
- **Tax:** researched UK tax/VAT obligations; do **not** claim registration or threshold crossing.
- **Ads:** creatives and PAUSED tests may exist; do not claim profitable scale.

## Length and structure

| Type | Words | Shape |
|------|-------|--------|
| Flagship journey | 1,000–1,800 | Full spine, 5–8 `##` sections |
| Weekly update | 400–800 | One chapter + status |
| Tiny note | <400 | Single beat; still need a hook |

Prefer shorter and specific over long and vague. Cut any paragraph that could appear on any random ecom blog unchanged. Cut any paragraph that only an agent would brag about.

## Recurring motifs (use sparingly)

- Calm store vs carnival store
- Day-job engineer habits applied to hobby commerce
- Supplier reality forcing storefront honesty
- Agents as leverage, not the protagonist
