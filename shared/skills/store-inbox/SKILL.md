---
name: store-inbox
description: >-
  Set up hello@ourtechaccessories.com and an LLM Gmail triage bot that declines
  sales/spam pitches, auto-answers simple FAQ (e.g. UK-only shipping), escalates
  order/refund mail, and optionally sends a one-shot deal follow-up when a
  support thread closes. Use when the user mentions store inbox spam, fake
  customer emails, hello@ domain email, ImprovMX, FAQ auto-reply, inbox triage,
  or closed-thread deal follow-ups.
---

# Store inbox (hello@ + triage bot)

Public address: **`hello@ourtechaccessories.com`**.  
Spam sink / mailbox: Gmail (usually `our.tech.accessories@gmail.com`).  
Escalation: personal address in secret config (never commit).  
Outbound: reply **From: hello@ourtechaccessories.com**.

## Read order

1. This file — architecture + hard rules.
2. **[prompting/setup-hello.md](prompting/setup-hello.md)** — DNS / ImprovMX / Gmail Send-as.
3. **[prompting/triage-rules.md](prompting/triage-rules.md)** — decline / FAQ / escalate / close.
4. **[prompting/store-faq.md](prompting/store-faq.md)** — facts the bot may auto-answer.
5. **[prompting/deal-followup.md](prompting/deal-followup.md)** — closed-thread deal mail (optional).
6. **[apps-script/Code.gs](apps-script/Code.gs)** + **[apps-script/DealFollowupBodies.gs](apps-script/DealFollowupBodies.gs)** + **[apps-script/README.md](apps-script/README.md)** — install the bot.
7. Generic Apps Script craft (mailbox guard, Send-as vs `replyTo`): **[../google-apps-script/SKILL.md](../google-apps-script/SKILL.md)**.

## Architecture

```text
Sender
  → MX (ImprovMX / mail provider)
  → hello@ourtechaccessories.com
  → forward into store Gmail
  → Apps Script (LLM classify)
        ├─ PITCH / AGENCY_SPAM → polite auto-decline From hello@, optional deal follow-up, label, archive
        ├─ FAQ (shipping countries, general delivery) → auto-reply from STORE_FAQ
        ├─ CUSTOMER / ORDER / UNCLEAR → forward to personal + label Escalate
        ├─ CLOSE (thanks / wrapped up) → optional one-shot deal follow-up
        ├─ idle FAQ/customer (us last, quiet N hours) → optional deal follow-up
        ├─ pitch declined or clear BOT → inbox-bot/dead (stop); FAQ follow-ups stay open
        └─ TRANSACTIONAL (Shopify/receipts) → leave alone
James opens escalated mail on personal → replies in Gmail with From: hello@
```

Deal creatives: **[prompting/deal-followup.md](prompting/deal-followup.md)** + `apps-script/DealFollowupBodies.gs`.
## Hard rules

1. **Never commit** personal email, app passwords, or API keys. Use Gmail Script Properties / `.env`.
2. **Public storefront** must show `hello@ourtechaccessories.com`, not a personal address, and prefer not to show the old Gmail once hello@ works.
3. **When unsure, escalate** (false decline of a real customer is worse than one extra ping).
4. Auto-decline only clear sales / SEO / “partnership” / anti-spam-service pitches.
5. FAQ auto-replies may use **only** facts in [store-faq.md](prompting/store-faq.md) / `STORE_FAQ` — never invent tracking, refunds, or order status.
6. Mail that mentions an order number, tracking, refund, return, or damaged item → escalate (not FAQ).

## Agent workflow

1. Confirm DNS/MX steps in [setup-hello.md](prompting/setup-hello.md) with James (he must click ImprovMX + Shopify DNS).
2. Help install Apps Script per [apps-script/README.md](apps-script/README.md).
3. Set Script Properties: `ESCALATE_TO`, `GEMINI_API_KEY`, `HELLO_FROM`; optional `STORE_FAQ` override from [store-faq.md](prompting/store-faq.md).
4. Update Shopify **Customer email** / contact + privacy policy text to `hello@ourtechaccessories.com` (Admin or `shopify-store` skill; legal policies may need Admin UI if scope missing).
5. Test: pitch (decline), “Do you ship to France?” (FAQ), “Where is my order?” (escalate).
6. Log the decision in local `MASTER_CONTEXT.md` Changelog.

## Env (optional local notes)

```bash
# .env — never commit real personal address into git
STORE_INBOX_HELLO=hello@ourtechaccessories.com
STORE_INBOX_MAILBOX=our.tech.accessories@gmail.com
# STORE_INBOX_ESCALATE_TO=you@personal.example   # local only; also set in Apps Script
# GEMINI_API_KEY=...   # for Apps Script / local experiments
```
