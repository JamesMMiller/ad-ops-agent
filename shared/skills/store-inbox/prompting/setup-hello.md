# Setup `hello@ourtechaccessories.com`

Goal: public `hello@`, mail lands in the store Gmail, James can **Send mail as** hello@, bot triages there.

## Recommended path (free / fast): ImprovMX + Gmail

### 1. ImprovMX

1. Sign up at [improvmx.com](https://improvmx.com) with the store Gmail.
2. Add domain `ourtechaccessories.com`.
3. Create alias: `hello` → `our.tech.accessories@gmail.com` (or whichever Gmail will run the bot).
4. Copy the **MX records** ImprovMX shows (usually `mx1.improvmx.com` / `mx2.improvmx.com`).

### 2. Shopify DNS

Domain is on Shopify / Google Cloud DNS (`ns-cloud-c*.googledomains.com`).

1. Shopify Admin → **Settings → Domains → ourtechaccessories.com → DNS settings**.
2. Remove or replace any existing **MX** records that conflict (keep Shopify email receiving only if you still need it).
3. Add ImprovMX MX records (priority as they specify, often 10 and 20).
4. Wait for DNS (can be minutes to a few hours). ImprovMX dashboard should show verified.

Do **not** move nameservers off Google/Shopify unless you intend a full DNS migration (Cloudflare Email Routing needs Cloudflare NS).

### 3. Gmail — Send mail as hello@

In the **mailbox Gmail** (`our.tech.accessories@gmail.com`):

1. Settings → **See all settings → Accounts → Send mail as → Add another email address**.
2. Name: `Our Tech Accessories`.
3. Email: `hello@ourtechaccessories.com`.
4. Treat as alias: yes.
5. Complete verification (ImprovMX forwards the Google verify mail into this inbox).

**From header quality:**

| Setup | Result |
|-------|--------|
| Free ImprovMX + “Send through Gmail” | Works; some clients show “via gmail” / on-behalf-of |
| ImprovMX paid SMTP or Google Workspace | Cleaner `From: hello@` |

For a hobby store, Gmail send-as is fine to start. Upgrade SMTP later if it bothers you.

### 4. Gmail filters (optional backup)

- Label `store-pitch` for known agency subjects.
- Never forward the whole inbox to personal — only bot escalations.

### 5. Public copy

Once hello@ receives mail:

- Shopify **Settings → Notifications**: Customer email / sender = `hello@ourtechaccessories.com` where offered.
- **Settings → Store details**: Store contact email → `hello@ourtechaccessories.com` (Admin UI; Admin API often cannot change this).
- Policies: **Contact information** should list hello@ (already set via API if it still showed the old Gmail). Privacy policy uses Liquid `{{ email }}` from Store details — fix that field and privacy follows.
- Contact page: same address if listed.

### 6. Personal address hygiene

- Remove personal email from Meta Page contact, Hashnode, GitHub commits, Stripe public forms.
- Do not reply to pitches from personal — only from hello@.
- If personal is already burned, keep filtering there; stop giving it out.

## Alternative: Google Workspace (one seat)

Cleaner mailbox + SMTP, ~£6–£10/mo. Create user `hello@`, skip ImprovMX, run Apps Script on that Workspace account (or forward Workspace → Gmail and script Gmail). Use if send-as “via gmail” is unacceptable.
