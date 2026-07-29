# Inbox triage rules

Classifier labels (LLM returns exactly one):

| Label | Action |
|-------|--------|
| `PITCH` | Auto-decline from hello@; label `inbox-bot/pitch`; archive |
| `FAQ` | Auto-reply from store knowledge; label `inbox-bot/faq` |
| `DEAL` | Discount / best / last price / coupon ask → reply with the **volume deal** (HTML when enabled); do not escalate |
| `CUSTOMER` | Escalate to personal; label `inbox-bot/customer`. Owner asks: reply asking what it concerns, then escalate |
| `UNCLEAR` | Escalate (same as customer); label `inbox-bot/unclear` |
| `TRANSACTIONAL` | No bot action (Shopify, Google, banks, 2FA) |
| `IGNORE` | Clear newsletter / bulk only; archive, no reply. Prefer `PITCH` (decline+deal) or `UNCLEAR` when a person wrote |
| `BOT` | Clear autoresponder/chatbot → `inbox-bot/dead`, archive, no reply |
| `CLOSE` | Thanks / thread wrapping up → optional **deal follow-up** (once); see [deal-followup.md](deal-followup.md) |
| *(dead)* | Label `inbox-bot/dead` — no further bot actions |
| *(rescued)* | Label `inbox-bot/rescued-from-spam` — moved from Gmail Spam → Inbox for triage |

**Spam policy:** the bot **never** moves mail into Gmail Spam. Each triage run rescues human-looking threads from Spam into Inbox, then replies (FAQ / DEAL / decline+deal / escalate) as usual. Clear noreply bots and bulk newsletters stay in Spam.

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
- Is this the right inbox / store email / correct contact?
- Is ourtechaccessories.com your official website?
- Bare greetings / check-ins (“hi”, “are you there?”, “hello”) with **no** real question
- Rough delivery times (general)
- Contact / who is this store

**Not** bare greetings: “Hi there, do you offer international shipping?” → answer UK-only shipping.

## Speak to the owner

Route by intent — never treat as inbox-confirm FAQ:

| Intent | Action |
|--------|--------|
| **Pitch** (SEO / agency / partnership / marketing, or owner-ask after a pitch) | `PITCH` → decline + deal follow-up (one outbound) |
| **Customer / order** (order, refund, shipping help, product, or ongoing FAQ/customer thread) | Escalate to personal. If they only say “connect me to the owner” with no topic, ask what it concerns first, then escalate |
| **Unclear** | Ask what it concerns + escalate |

Examples:
- “Can I speak with the store owner about a partnership / SEO?” → pitch decline + deal
- “Connect me to the owner — order #1002 not arrived” → escalate
- “Can I speak with the store owner?” on a shipping FAQ thread → ask what it concerns + escalate
- Bare “Connect me to the store owner?” → ask what it concerns + escalate

## DEAL (discount / price) — examples

Reply directly with the current volume deal (same GaN HTML when `DEAL_FOLLOWUP_ENABLED=true`). Do **not** escalate.

- “Is this your last price or you got a discount?”
- “Any discount / coupon / promo?”
- “Can you do better on the price?”
- “Best price?” / “any deals?”

Facts: site prices are normal single-item prices; current offer is buy-more-save-more on the 120W GaN charger (2=15%, 3=20%, 4+=25%). No invented one-off coupons. One deal HTML per thread; if already sent, short plain reminder only.

Default facts today: **UK shipping only**; international planned later with **no promised date**.  
Shipping cost: **some products free UK shipping**, others a fee at checkout — never claim always free or always charged.  
Inbox confirm: yes, `hello@` is the official store customer email; do not share personal contact details. If that line is only a pitch opener, classify as **PITCH**.  
Website confirm: yes, `ourtechaccessories.com` is the official site.  
Generic greeting: FAQ with the fixed support-intro reply (not escalate) — only when there is **no** real question.

## Escalate (CUSTOMER) — examples

- Where is my order / tracking / delivery of a specific order
- Refund, return, damaged item, wrong colour
- Checkout or payment problems
- Anything needing an order number lookup
- Ask to speak with the store owner / manager:
  - Pitch → decline + deal follow-up
  - Customer / order → escalate (ask what it concerns when the topic is bare)
- Wholesale only if they sound like a real buyer (when unsure → UNCLEAR → escalate)

## Follow-ups (same thread)

The bot tracks a **per-thread watermark** (last handled message time), not “processed once forever”.

- If the latest message is from us → wait (no action).
- If the customer sends a new reply → re-classify that message (FAQ again, escalate, CLOSE, or IGNORE).
- Short follow-ups use prior thread context (“and to Germany?” after a shipping FAQ).
- Closing thanks (`CLOSE`) may trigger a one-shot deal follow-up when enabled — [deal-followup.md](deal-followup.md).

## Closed-thread deal follow-up

Optional (`DEAL_FOLLOWUP_ENABLED=true`). Sends the GaN-style deal HTML **once** (bodies from **`https://ourtechaccessories.com/pages/inbox-deal`**) when:

1. Customer closes the thread with thanks (and we already helped), or
2. After a **pitch** (one deal email with pitch intro when enabled; plain decline only if deal is off), or
3. Idle sweep: we replied last on an FAQ/customer thread and they stayed quiet for N hours (also retries pitch declines that never got a deal).
4. Customer asks for a **discount / last price** (`DEAL` label).

Details: **[deal-followup.md](deal-followup.md)** (website endpoint + Apps Script cache).

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
