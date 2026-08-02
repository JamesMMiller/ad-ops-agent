# Closed-thread deal follow-up

After a real support/FAQ conversation wraps up, the bot can send **one** HTML deal email (same creative family as the GaN volume deal) so the customer stays aware of current offers.

## When it fires

| Trigger | Condition |
|---------|-----------|
| **Discount ask (`DEAL`)** | Customer asks for discount / last / best price / coupon → reply with the volume deal HTML (reason `discount`). Not escalated. |
| **CLOSE** | Customer sends thanks / cheers / all good / that helps (no new question), and the thread was already engaged (`inbox-bot/faq`, `customer`, `unclear`, or ≥3 messages) |
| **PITCH decline** | One outbound: the deal HTML with pitch intro (when enabled). Plain decline only if deal is off / fails. |
| **Idle sweep** | Hourly `dealFollowUpSweep`: loads threads via **label API** (`inbox-bot/faq`, `customer`, `pitch`), last message **from us**, quiet for `DEAL_FOLLOWUP_IDLE_HOURS` (default **24**; `0` = next sweep with no wait). Pitch retries skip the idle wait. |

## When it never fires

- Already labelled `inbox-bot/deal-followup` **or** Script Property `dealSent:<threadId>=1` (one shot per Gmail thread forever — survives label removal and the customer reopening the same thread)
- Thread body already contains a prior volume-deal send (healed into the claim)
- `DEAL_FOLLOWUP_ENABLED` is not `true` (idle/close/pitch HTML skipped; **discount asks still get a plain-text volume-deal reply**)
- `DRY_RUN=true` (logs candidates only)
- Transactional / bot mail
- Thread never engaged (stranger “thanks” with no prior help) — except **pitch** declines, which always qualify when enabled
- FAQ/customer idle threads still need last message **from us** and quiet for N hours (unless idle hours is `0`)

**Search note:** Do **not** rely on Gmail `label:inbox-bot/faq` search — nested labels often match nothing. The sweep uses `GmailApp.getUserLabelByName(...).getThreads()`.

**Anti-duplicate:** triage holds a script lock; each inbound message is claimed (`replySent:<threadId>:<msgId>`) before any reply. Deal claims happen *before* `thread.reply`. Pitch no longer sends decline + deal as two mails. Run `dealFollowUpDebug` in Apps Script to see per-thread skip reasons.

## Bodies

Canonical templates (edit these, then regenerate the Shopify page template):

- [`../apps-script/templates/deal-followup.html`](../apps-script/templates/deal-followup.html)
- [`../apps-script/templates/deal-followup.txt`](../apps-script/templates/deal-followup.txt)

**Live endpoint (preferred for the bot):**  
`https://ourtechaccessories.com/pages/inbox-deal` → JSON `{ "version", "base_price", "html", "plain" }`  
Templates use `__GAN_BASE_PRICE__`; the page Liquid fills it from the live GaN product (`all_products`), so Admin price changes show up without rewriting copy.  
Rebuild + push: `python3 shared/skills/store-inbox/scripts/build-inbox-deal-page.py` then theme upsert of `templates/page.inbox-deal.liquid`.

Apps Script property: `DEAL_BODIES_URL` (defaults to that URL). Falls back to Drive / inline / `DealFollowupBodies.gs`. Run `refreshDealBodiesCache` after editing.

**Logo:** dark banner uses CDN **`our-tech-logo-inverted`** on a solid rounded black pill (`#0A0A0A`, `border-radius: 18px`) so photo colour doesn’t show through glyph holes. Canonical file: `outputs/shopify/projects/branding/our-tech-logo-inverted.png`. Light surfaces use **`our-tech-logo-default`**. See `outputs/shopify/projects/branding/DIRECTIONS.md`.

**Sign-off:** brand only (`Our Tech Accessories` + `hello@`) — never a personal name.

Tokens: `{{NAME}}`, `{{NAME_SUFFIX}}` (`" Joseph"` or empty), `{{INTRO}}`, `{{BRIDGE}}`.

`Code.gs` fills `{{INTRO}}` from the trigger:

| Reason | Default intro |
|--------|----------------|
| `discount` | Site prices are normal single-item; here is the volume deal |
| `pitch` | Not looking for marketing/agency services; if you shop accessories yourself, here is a deal |
| `close` | Thanks — while this thread wraps up, here is a current deal |
| `idle` | Quick follow-up — here is a current deal |

Override with Script Properties: `DEAL_INTRO_DISCOUNT`, `DEAL_INTRO_PITCH`, `DEAL_INTRO_CLOSE`, `DEAL_INTRO_IDLE`, `DEAL_BRIDGE`.

Other overrides: `DEAL_HTML_DRIVE_ID`, `DEAL_PLAIN_DRIVE_ID`, `DEAL_HTML`, `DEAL_PLAIN`, `DEAL_SUBJECT` (subject only used in logs; reply stays on-thread).

## Enable

1. Confirm live endpoint works: open `https://ourtechaccessories.com/pages/inbox-deal` (JSON with `html` + `plain`).
2. Paste **`Code.gs`** into the store Apps Script project (optional: `DealFollowupBodies.gs` as offline fallback).
3. Script property: `DEAL_FOLLOWUP_ENABLED=true`
4. Optional: `DEAL_BODIES_URL` (defaults to the URL above), `DEAL_FOLLOWUP_IDLE_HOURS=24`
5. Run `installTriggers` (adds hourly sweep). Grant **UrlFetch** / external request access.
6. Run **`refreshDealBodiesCache`** — log should show `version=…`
7. Keep `DRY_RUN=true` until you have seen a dry log line (`DRY_RUN idle deal candidate…`).
8. Run **`dealFollowUpDebug`** — check Executions for `pool=` counts and per-thread skip reasons.
9. Then set `DRY_RUN=false` and run `dealFollowUpSweep`.

### Manual test send

1. Re-paste latest `Code.gs` (and rebuild/push the Shopify page if templates changed).
2. Optional Script Properties: `DEAL_TEST_TO`, `DEAL_TEST_NAME`, `DEAL_TEST_REASON` (`close` | `pitch` | `idle` | `discount`).
3. Signed into **store** Gmail → run `sendDealFollowUpTest` (defaults to `J.Malachy.miller@gmail.com`, name James, reason `close`).

## Labels

| Label | Meaning |
|-------|---------|
| `inbox-bot/closed` | Closing signal seen |
| `inbox-bot/deal-followup` | Deal mail already sent (also mirrored as Script Property `dealSent:<threadId>`) |

If the customer replies after the deal with an order question → normal triage (escalate / FAQ) still applies.
