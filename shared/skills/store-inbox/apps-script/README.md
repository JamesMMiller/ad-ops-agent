# Gmail Apps Script — inbox triage bot

Runs inside the **store Gmail** that receives `hello@` (via ImprovMX forward).

## Install

1. Finish [../prompting/setup-hello.md](../prompting/setup-hello.md) so `hello@` forwards into this Gmail and **Send mail as** works.
2. Visit [script.google.com](https://script.google.com) while logged into **`our.tech.accessories@gmail.com`** (or your mailbox).
3. New project → name it `our-tech-inbox-bot`.
4. Paste `Code.gs` into `Code.gs`.
5. **Optional fallback:** add a second script file named **`DealFollowupBodies`** → paste [`DealFollowupBodies.gs`](DealFollowupBodies.gs). Prefer the live website bodies (step 6). Keep this file only for offline / fetch failure.
6. **Project settings → Script properties** → add:

| Property | Value |
|----------|--------|
| `HELLO_FROM` | `hello@ourtechaccessories.com` |
| `ESCALATE_TO` | your personal email |
| `GEMINI_API_KEY` | from [Google AI Studio](https://aistudio.google.com/apikey) |
| `GEMINI_MODEL` | optional — default `gemini-2.5-flash` |
| `DRY_RUN` | `true` for the first day |
| `STORE_FAQ` | optional — paste blob from `prompting/store-faq.md` to override defaults |
| `DEAL_FOLLOWUP_ENABLED` | `true` to send deal HTML (default off) |
| `DEAL_FOLLOWUP_IDLE_HOURS` | optional — default `24` |
| `DEAL_BODIES_URL` | optional — default `https://ourtechaccessories.com/pages/inbox-deal` (JSON `{html,plain,version}`) |
| `EMAIL_DAILY_BUDGET` | soft send cap/day (default `80`; consumer Gmail hard cap ≈100) |
| `EMAIL_PER_RUN_MAX` | max sends per triage/sweep run (default `5`) |
| `SPAM_RESCUE_PER_RUN` | max Spam→Inbox moves per run (default `2`) |
| `SPAM_RESCUE_DAILY_MAX` | max spam rescues/day (default `10`) |

7. Select function `installTriggers` → Run → grant Gmail + **external request** (UrlFetch for deal JSON) permissions (+ Drive if using `DEAL_*_DRIVE_ID`).
8. Run `refreshDealBodiesCache` — confirm logs show a `version=` from the website.
9. Select `triageOneTest` → Run → check **Executions** logs.
10. When happy, set `DRY_RUN` = `false`.

## Deal bodies (website endpoint)

Canonical edit path:

1. Edit [`templates/deal-followup.html`](templates/deal-followup.html) + [`templates/deal-followup.txt`](templates/deal-followup.txt).
2. `python3 shared/skills/store-inbox/scripts/build-inbox-deal-page.py`
3. Upsert `templates/page.inbox-deal.liquid` to the MAIN theme (`shopify-store` skill / Admin API).
4. Live URL: **https://ourtechaccessories.com/pages/inbox-deal**
5. In Apps Script run `refreshDealBodiesCache` (or wait ≤10 minutes for ScriptCache TTL).

Full docs: [`../prompting/deal-followup.md`](../prompting/deal-followup.md).

## Behaviour

- Every 5 minutes: **rescue** up to a few human-looking Spam → Inbox, then triage inbox (capped sends). Consumer Gmail allows ~**100 emails/day**; the bot soft-stops via `MailApp.getRemainingDailyQuota()` + `EMAIL_DAILY_BUDGET`. Run `logEmailQuota` to inspect. The bot **never** moves mail into Spam.
- Only acts when the **latest** message is inbound and newer than the thread watermark (so follow-ups work).
- **PITCH** → one outbound (deal with pitch intro when enabled, else plain decline), label, archive.
- **DEAL** → discount / last-price asks → volume deal HTML from `/pages/inbox-deal` (or text tiers).
- **FAQ** → short auto-reply from store knowledge (UK shipping, etc.); label `inbox-bot/faq`.
  “Hi there” + a real question (e.g. international shipping) is answered, not treated as a bare greeting.
- **Owner ask** → pitch → decline + deal; customer/order → escalate (ask what it concerns if bare); unclear → ask + escalate.
- **CUSTOMER / UNCLEAR** → email personal with excerpt; leave/label for you to reply From hello@ in Gmail.
- **CLOSE** (thanks / wrapped up) → optional one-shot **deal follow-up** HTML when `DEAL_FOLLOWUP_ENABLED=true`.
- Hourly **idle sweep**: FAQ/customer threads where we replied last and they stayed quiet → same deal once.
- **TRANSACTIONAL** → ignore.
- **Dead** (`inbox-bot/dead`): only after a pitch decline, or when mail is clearly automated/BOT; FAQ threads with people stay open.

After updating `.gs` files in this repo, re-paste into the Apps Script project and re-run `installTriggers` if needed.

## Gemini free tier

Create an API key in AI Studio. If Gemini is down, the script falls back to keyword heuristics (still escalates when unsure).

## Create / send HTML follow-ups (generic)

Do **not** hardcode recipients or bodies in Apps Script. Use:

- [`../../google-apps-script/templates/HtmlMailer.gs`](../../google-apps-script/templates/HtmlMailer.gs)
- Docs: [`../../google-apps-script/reference/html-mailer.md`](../../google-apps-script/reference/html-mailer.md)

GaN deal example content: `outputs/shopify/2026-07-27-gan-volume-deal/FOLLOW-UP-EMAIL.md`  
(`CreateGanDealDraft.gs` is retired — points at the mailer above.)
