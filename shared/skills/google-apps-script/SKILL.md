---
name: google-apps-script
description: >-
  Author, install, and harden Google Apps Script projects (Gmail, Sheets, Drive,
  Triggers, Script Properties). Enforces correct Google account / From identity,
  secrets hygiene, and paste-into-script.google.com workflow. Use when the user
  asks for an Apps Script, GmailApp automation, time-driven triggers, Script
  Properties, Send-as / replyTo mail, or a .gs helper for Gmail/Sheets.
---

# Google Apps Script (generic)

Write **generic** Apps Script helpers for Gmail / Sheets / Drive / Calendar.  
Domain bots (e.g. store inbox triage) stay in their own skills; this skill is the **how to ship .gs safely**.

## When to use this vs a specialised skill

| Need | Skill |
|------|--------|
| Generic Gmail/Sheets automation, one-shot send, triggers, properties | **this skill** |
| Store `hello@` triage / ImprovMX / FAQ / DEAL / `/pages/inbox-deal` bodies | `store-inbox` |

## Hard rules

1. **Never commit** emails that must stay private, app passwords, API keys, or OAuth tokens. Put them in **Script Properties** (or local `.env` notes only).
2. **Effective user = From mailbox.** `GmailApp.sendEmail` / `createDraft` always send as the Google account that owns the script execution. Wrong avatar at [script.google.com](https://script.google.com) → wrong From.
3. Prefer **`replyTo`** for a public alias when Send-as is unreliable. Setting `from: alias@domain` fails with `Invalid argument` unless that alias is a verified Send-as on the same account.
4. For any send/draft that must not leave a personal mailbox, call an **`assertMailbox_(expected)`** guard first (see [reference/patterns.md](reference/patterns.md)).
5. Ship code under the repo (e.g. `outputs/.../*.gs` or a skill `apps-script/` folder). User **pastes** into the Apps Script project; there is no silent remote deploy from this agent unless they ask for clasp.

## Agent workflow

1. **Clarify**
   - Goal (send, draft, triage, sheet sync, …)
   - Which Google account must own the project
   - From / Reply-To expectations
   - One-shot function vs time-driven trigger
2. **Author** `.gs` from [templates/HtmlMailer.gs](templates/HtmlMailer.gs) (HTML email) or [templates/boilerplate.gs](templates/boilerplate.gs) + patterns in [reference/patterns.md](reference/patterns.md).
   - Prefer **Script Properties** + Drive HTML (`MAIL_HTML_DRIVE_ID`) over embedding campaign copy in `.gs`.
   - Use `{{NAME}}` tokens + `MAIL_VARS` for personalisation.
3. **Install instructions** (always give the user these steps):
   - Sign into the **correct** Google account (check top-right avatar).
   - [script.google.com](https://script.google.com) → New project (or open existing).
   - Paste file(s); name functions clearly (`sendX`, `installTriggers`, `dryRun`).
   - **Project settings → Script properties** for secrets.
   - Run once → grant scopes → check **Executions** logs.
4. **Verify identity** before any real send: run a tiny `logWhoAmI` that prints `Session.getEffectiveUser().getEmail()`.
5. Prefer **draft** or `DRY_RUN=true` before live send.

## Output layout

```text
shared/skills/google-apps-script/   # this skill (generic guidance + templates)
outputs/<date>-<slug>/              # one-off scripts for a job (optional)
some-skill/apps-script/             # productised bots (store-inbox, etc.)
```

Name files `Something.gs`. Keep one concern per file when helpers grow large.

## Out of scope

- Generating creative / Meta ads / Shopify Admin API (other skills).
- Guaranteeing `From: alias@custom-domain` without working Gmail Send-as (or Workspace SMTP).
- clasp CI unless the user explicitly asks to wire it.

## Read next

- [reference/patterns.md](reference/patterns.md) — mailbox guard, send/draft, properties, triggers, quotas.
- [reference/html-mailer.md](reference/html-mailer.md) — property-driven HTML emails (no hardcoded recipients/bodies).
- [templates/HtmlMailer.gs](templates/HtmlMailer.gs) — pasteable mailer (`createMailDraft` / `sendMail`).
- [templates/boilerplate.gs](templates/boilerplate.gs) — minimal starter / identity check.
