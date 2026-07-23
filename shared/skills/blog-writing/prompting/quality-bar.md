# Blog quality bar

Hit every **Required** item before `upsert-draft` or `publish`.

## Required

- [ ] First person as James Miller (unless `post.json` sets another identity)
- [ ] Reads as **James's lived perspective**, not an agent session log
- [ ] No agent-only internals (CDN blocks, model IDs, credit burns, ffmpeg flags, env-check scripts) unless James explicitly wants that beat
- [ ] UK English; light humour present but not forced every paragraph
- [ ] Title is specific and human (not "My Amazing Journey into Ecom")
- [ ] Opening hook answers *why evenings / why this* within ~3 short paragraphs
- [ ] Clear distinction between **shipped** facts and **still experimental**
- [ ] No invented sales, ROAS, profit, or "it works" claims
- [ ] No money figures unless James supplied them for this post
- [ ] Tax section (if any) matches research-only unless James stated otherwise
- [ ] Supplier critique is policy-fit only (returns / freight / reliability docs)
- [ ] Mentions the calm aesthetic bet (Apple/Samsung-like) vs cluttered dropship stores when relevant
- [ ] If the post discusses the live store: at least homepage + one PDP screenshot under `images/` (see [screenshots.md](screenshots.md))
- [ ] Soft ending; no course-sell or fake urgency
- [ ] `post.json` valid: `title`, `slug`, `tags` (1–8), `subtitle` or `seo.description`
- [ ] Body markdown renders cleanly; headings are scannable
- [ ] No API secrets, tokens, or `.env` values in the post
- [ ] Prefer colon/period/comma over em dashes (—) in prose

## Strongly preferred

- [ ] At least one concrete down James felt (policy flip, mobile ATC buried, freight dead-end, supplier mismatch)
- [ ] At least one concrete up (domain live, calmer store, CJ move, clearer returns)
- [ ] Store named: Our Tech Accessories / `ourtechaccessories.com` when relevant
- [ ] Repo named: `ad-ops-agent` only when tooling is the point (keep light)
- [ ] Tags match content (`dropshipping`, `shopify`, `side-project`, etc.)
- [ ] SEO description ≤ 160 characters, no clickbait

## Fail (do not publish)

- Guru tone or "anyone can make 10k" energy
- Attacking a supplier with unverifiable claims
- Claiming VAT registered / limited company without James saying so
- Publishing without explicit user yes
- Body that only restates Shopify marketing jargon with no personal stake
- Body that narrates agent plumbing James never saw
