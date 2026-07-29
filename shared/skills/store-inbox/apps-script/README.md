# Gmail Apps Script — inbox triage bot

Runs inside the **store Gmail** that receives `hello@` (via ImprovMX forward).

## Install

1. Finish [../prompting/setup-hello.md](../prompting/setup-hello.md) so `hello@` forwards into this Gmail and **Send mail as** works.
2. Visit [script.google.com](https://script.google.com) while logged into **`our.tech.accessories@gmail.com`** (or your mailbox).
3. New project → name it `our-tech-inbox-bot`.
4. Paste `Code.gs` into `Code.gs`.
5. Add a second script file → paste `DealFollowupBodies.gs` (default closed-thread deal HTML).
6. **Project settings → Script properties** → add:

| Property | Value |
|----------|--------|
| `HELLO_FROM` | `hello@ourtechaccessories.com` |
| `ESCALATE_TO` | your personal email |
| `GEMINI_API_KEY` | from [Google AI Studio](https://aistudio.google.com/apikey) |
| `GEMINI_MODEL` | optional — default `gemini-2.5-flash` |
| `DRY_RUN` | `true` for the first day |
| `STORE_FAQ` | optional — paste blob from `prompting/store-faq.md` to override defaults |
| `DEAL_FOLLOWUP_ENABLED` | `true` to send closed-thread deal mail (default off) |
| `DEAL_FOLLOWUP_IDLE_HOURS` | optional — default `48` |

7. Select function `installTriggers` → Run → grant Gmail + external request permissions (+ Drive if using `DEAL_*_DRIVE_ID`).
8. Select `triageOneTest` → Run → check **Executions** logs.
9. When happy, set `DRY_RUN` = `false`.

## Behaviour

- Every 5 minutes: inbox threads from the last 2 days (including ones already labelled `inbox-bot/processed`).
- Only acts when the **latest** message is inbound and newer than the thread watermark (so follow-ups work).
- **PITCH** → reply with decline (From hello@), optional deal follow-up, label, archive.
- **FAQ** → short auto-reply from store knowledge (UK shipping, etc.); label `inbox-bot/faq`.
- **CUSTOMER / UNCLEAR** → email personal with excerpt; leave/label for you to reply From hello@ in Gmail.
- **CLOSE** (thanks / wrapped up) → optional one-shot **deal follow-up** HTML when `DEAL_FOLLOWUP_ENABLED=true`.
- Hourly **idle sweep**: FAQ/customer threads where we replied last and they stayed quiet → same deal once.
- **TRANSACTIONAL** → ignore.
- **Dead** (`inbox-bot/dead`): only after a pitch decline, or when mail is clearly automated/BOT; FAQ threads with people stay open.

Deal template docs: [`../prompting/deal-followup.md`](../prompting/deal-followup.md).

After updating `.gs` files in this repo, re-paste into the Apps Script project (or sync the changed functions) and re-run `installTriggers` if needed.

## Gemini free tier

Create an API key in AI Studio. If Gemini is down, the script falls back to keyword heuristics (still escalates when unsure).

## Create / send HTML follow-ups (generic)

Do **not** hardcode recipients or bodies in Apps Script. Use:

- [`../../google-apps-script/templates/HtmlMailer.gs`](../../google-apps-script/templates/HtmlMailer.gs)
- Docs: [`../../google-apps-script/reference/html-mailer.md`](../../google-apps-script/reference/html-mailer.md)

GaN deal example content: `outputs/shopify/2026-07-27-gan-volume-deal/FOLLOW-UP-EMAIL.md`  
(`CreateGanDealDraft.gs` is retired — points at the mailer above.)
