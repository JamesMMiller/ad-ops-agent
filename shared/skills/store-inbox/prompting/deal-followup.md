# Closed-thread deal follow-up

After a real support/FAQ conversation wraps up, the bot can send **one** HTML deal email (same creative family as the GaN volume deal) so the customer stays aware of current offers.

## When it fires

| Trigger | Condition |
|---------|-----------|
| **CLOSE** | Customer sends thanks / cheers / all good / that helps (no new question), and the thread was already engaged (`inbox-bot/faq`, `customer`, `unclear`, or ≥3 messages) |
| **PITCH decline** | After the polite auto-decline, send the same one-shot deal (product offer, not a yes to their pitch) |
| **Idle sweep** | Hourly `dealFollowUpSweep`: FAQ or customer thread, last message **from us**, quiet for `DEAL_FOLLOWUP_IDLE_HOURS` (default 48) |

## When it never fires

- Already labelled `inbox-bot/deal-followup` (one shot per thread)
- `DEAL_FOLLOWUP_ENABLED` is not `true`
- Transactional / bot mail
- Thread never engaged (stranger “thanks” with no prior help) — except **pitch** declines, which always qualify when enabled
- Idle sweep does not re-mail pitch threads (deal goes out immediately after decline)

## Bodies

Canonical templates (edit these, then regenerate `DealFollowupBodies.gs` or upload to Drive):

- [`../apps-script/templates/deal-followup.html`](../apps-script/templates/deal-followup.html)
- [`../apps-script/templates/deal-followup.txt`](../apps-script/templates/deal-followup.txt)

Tokens: `{{NAME}}`, `{{NAME_SUFFIX}}` (`" Joseph"` or empty), `{{INTRO}}`, `{{BRIDGE}}`.

`Code.gs` fills `{{INTRO}}` from the trigger:

| Reason | Default intro |
|--------|----------------|
| `pitch` | Not looking for marketing/agency services; if you shop accessories yourself, here is a deal |
| `close` | Thanks — while this thread wraps up, here is a current deal |
| `idle` | Quick follow-up — here is a current deal |

Override with Script Properties: `DEAL_INTRO_PITCH`, `DEAL_INTRO_CLOSE`, `DEAL_INTRO_IDLE`, `DEAL_BRIDGE`.

Other overrides: `DEAL_HTML_DRIVE_ID`, `DEAL_PLAIN_DRIVE_ID`, `DEAL_HTML`, `DEAL_PLAIN`, `DEAL_SUBJECT` (subject only used in logs; reply stays on-thread).

## Enable

1. Paste **`Code.gs`** + **`DealFollowupBodies.gs`** into the store Apps Script project.
2. Script property: `DEAL_FOLLOWUP_ENABLED=true`
3. Optional: `DEAL_FOLLOWUP_IDLE_HOURS=48`
4. Run `installTriggers` (adds hourly sweep).
5. Keep `DRY_RUN=true` until you have seen a dry log line.

### Manual test send

1. Re-paste latest `Code.gs` + `DealFollowupBodies.gs`.
2. Optional Script Properties: `DEAL_TEST_TO`, `DEAL_TEST_NAME`, `DEAL_TEST_REASON` (`close` | `pitch` | `idle`).
3. Signed into **store** Gmail → run `sendDealFollowUpTest` (defaults to `J.Malachy.miller@gmail.com`, name James, reason `close`).

## Labels

| Label | Meaning |
|-------|---------|
| `inbox-bot/closed` | Closing signal seen |
| `inbox-bot/deal-followup` | Deal mail already sent |

If the customer replies after the deal with an order question → normal triage (escalate / FAQ) still applies.
