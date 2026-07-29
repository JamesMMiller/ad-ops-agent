# HTML mailer (property-driven)

Use [`templates/HtmlMailer.gs`](../templates/HtmlMailer.gs) for one-off or repeat HTML emails. **Do not hardcode** recipient, subject, or body in `.gs`.

## Script properties

| Property | Required | Purpose |
|----------|----------|---------|
| `EXPECTED_MAILBOX` | yes | Account that must own the run (e.g. store Gmail) |
| `MAIL_TO` | yes | Recipient |
| `MAIL_SUBJECT` | yes | Subject (supports `{{TOKENS}}`) |
| `FROM_NAME` | no | Display name (default `Our Tech Accessories`) |
| `REPLY_TO` | no | Public alias (e.g. `hello@…`) |
| `DRY_RUN` | no | Default `true`. Must be `false` to `sendMail` |
| `MAIL_HTML_DRIVE_ID` | one of* | Drive file id of `.html` body (**preferred** for large mail) |
| `MAIL_HTML_FILE` | one of* | Apps Script HTML filename (no `.html`) |
| `MAIL_HTML` | one of* | Inline HTML (Script Property ~9KB limit — avoid for big creatives) |
| `MAIL_PLAIN` / `MAIL_PLAIN_DRIVE_ID` | no | Plain part; else stripped from HTML |
| `MAIL_VARS` | no | JSON object for tokens, e.g. `{"NAME":"Joseph"}` |
| `MAIL_VAR_*` | no | Alternate tokens: `MAIL_VAR_NAME=Joseph` → `{{NAME}}` |

\* First match for HTML: Drive id → project HTML file → inline `MAIL_HTML`.

## Tokens

In HTML / plain / subject:

```text
Hi {{NAME}},
```

Set:

```text
MAIL_VARS={"NAME":"Joseph","FIRST_NAME":"Joseph"}
```

Unresolved `{{TOKENS}}` are logged as warnings.

## Install once

1. Sign into the **correct** Google account → [script.google.com](https://script.google.com).
2. Paste `HtmlMailer.gs`.
3. First run: `logWhoAmI` → grant Gmail (+ Drive if using Drive ids).
4. Set properties → `createMailDraft` → check Drafts → only then `DRY_RUN=false` + `sendMail`.

## New campaign (no code edits)

1. Author HTML under `outputs/.../email.html` with `{{NAME}}` etc.
2. Upload that file to **Drive** (same Google account) → copy file id from the URL (`/d/<ID>/`).
3. Update Script Properties only:

```text
MAIL_TO=person@example.com
MAIL_SUBJECT=Sorry about the auto-reply + GaN charger deal
MAIL_HTML_DRIVE_ID=<id>
MAIL_VARS={"NAME":"Joseph"}
MAIL_PLAIN=Hi {{NAME}}, …

EXPECTED_MAILBOX=our.tech.accessories@gmail.com
REPLY_TO=hello@ourtechaccessories.com
FROM_NAME=James / Our Tech Accessories
DRY_RUN=true
```

4. Run `createMailDraft`.

## Why not hardcode in .gs?

- Recipients and secrets must not live in git.
- Large HTML exceeds Script Property size; Drive or project HTML files scale.
- Same mailer covers GaN follow-ups, apologias, restocks — change properties, not code.
