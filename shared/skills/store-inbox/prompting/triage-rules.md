# Inbox triage rules

Classifier labels (LLM returns exactly one):

| Label | Action |
|-------|--------|
| `PITCH` | Auto-decline from hello@; label `inbox-bot/pitch`; archive |
| `FAQ` | Auto-reply from store knowledge; label `inbox-bot/faq` |
| `CUSTOMER` | Escalate to personal; label `inbox-bot/customer` |
| `UNCLEAR` | Escalate (same as customer); label `inbox-bot/unclear` |
| `TRANSACTIONAL` | No bot action (Shopify, Google, banks, 2FA) |
| `IGNORE` | Newsletter / bulk; archive, no reply |
| `BOT` | Clear autoresponder/chatbot → `inbox-bot/dead`, archive, no reply |
| *(dead)* | Label `inbox-bot/dead` — no further bot actions |

Store knowledge: **[store-faq.md](store-faq.md)** (also Script property `STORE_FAQ`).

## Dead conversations

Only in these cases (FAQ follow-ups with real people stay open):

1. **Already declined** — after a `PITCH` decline, thread is marked dead; further mail on that thread is ignored/archived.
2. **Clearly a bot** — noreply/auto-reply signals, or classifier label `BOT` when obvious.

While dead: new inbound is watermarked and ignored.  
To revive: remove `inbox-bot/dead` (and `inbox-bot/pitch` if needed) in Gmail.

## Decline (PITCH) — examples

- “I can stop your customer spam”
- SEO / link building / guest post / “partnership”
- Influencer or agency cold outreach
- “Are you getting fake customer messages every day?” openers
- Payment gateway / app install cold sales
- Crypto / loan / amazing ROI

## FAQ auto-reply — examples

Answerable from store knowledge only (no order lookup):

- Do you ship to Ireland / EU / US / internationally?
- Is shipping UK only?
- Is shipping free / is shipping included in the price?
- Rough delivery times (general)
- Contact / who is this store

Default facts today: **UK shipping only**; international planned later with **no promised date**.  
Shipping cost: **some products free UK shipping**, others a fee at checkout — never claim always free or always charged.

## Escalate (CUSTOMER) — examples

- Where is my order / tracking / delivery of a specific order
- Refund, return, damaged item, wrong colour
- Checkout or payment problems
- Anything needing an order number lookup
- Wholesale only if they sound like a real buyer (when unsure → UNCLEAR → escalate)

## Follow-ups (same thread)

The bot tracks a **per-thread watermark** (last handled message time), not “processed once forever”.

- If the latest message is from us → wait (no action).
- If the customer sends a new reply → re-classify that message (FAQ again, escalate, or IGNORE for a bare “thanks”).
- Short follow-ups use prior thread context (“and to Germany?” after a shipping FAQ).

## Never auto-decline if

- Body or subject contains order-like tokens (`#`, `Order`, `tracking`, `refund`, `delivered`)
- Sender domain is `shopify.com`, `stripe.com`, `paypal.com`, `google.com`, etc.
- The latest message is already from James / hello@ (human owns the thread)

## Never treat as FAQ if

- Mentions a specific order, tracking code, refund, return, or damaged parcel
- Asks the bot to change an order or approve money back
- When unsure → `CUSTOMER` / `UNCLEAR` (escalate)

## Auto-decline copy (UK, short)

```
Hi,

Thanks for getting in touch. We're not looking for marketing, SEO, partnership, or agency services.

If you're a customer with an order or product question, reply with your order number (or the product link) and we'll help.

Our Tech Accessories
hello@ourtechaccessories.com
```

## FAQ reply shape

- Short UK English; only facts from `STORE_FAQ` / store-faq.md
- Mention UK-only shipping + future international (no date) when relevant
- Offer: reply with order number if they need human help
- Sign-off: Our Tech Accessories + hello@
- No em dashes; no chatbot/corporate filler (see tone rules in store-faq.md)
- `Code.gs` runs `sanitizeCustomerReply_` on FAQ + pitch declines before send

## Escalation mail to personal

Subject: `[Our Tech] Customer? {original subject}`  
Body: classifier label + confidence + why + original From/Subject + plain-text excerpt + link to Gmail thread if available.  
James replies **on the original thread in the store Gmail** (or opens the escalated copy and replies From hello@ on a new message to the customer — prefer replying on the store mailbox thread so history stays in one place).
