# Apps Script patterns

## Mailbox guard (required for send/draft)

```javascript
var EXPECTED_MAILBOX = 'owner@example.com'; // Script Property preferred

function assertMailbox_(expected) {
  expected = String(expected || '').toLowerCase();
  var who = '';
  try { who = Session.getEffectiveUser().getEmail() || ''; } catch (e) {}
  if (!who) {
    try { who = Session.getActiveUser().getEmail() || ''; } catch (e2) {}
  }
  who = String(who).toLowerCase();
  if (!expected || who !== expected) {
    throw new Error(
      'Refusing to run. Effective user is "' +
        (who || '(unknown)') +
        '" but expected "' +
        expected +
        '". Sign into that account at script.google.com and open the matching project.'
    );
  }
  Logger.log('OK: running as ' + who);
}

function logWhoAmI() {
  Logger.log('effective=' + Session.getEffectiveUser().getEmail());
  try { Logger.log('active=' + Session.getActiveUser().getEmail()); } catch (e) {}
}
```

Load `EXPECTED_MAILBOX` from `PropertiesService.getScriptProperties()` when it varies per install.

## Send vs draft

```javascript
function sendHtmlEmail_(to, subject, plain, html, opts) {
  opts = opts || {};
  assertMailbox_(opts.expectedMailbox || prop_('EXPECTED_MAILBOX'));
  GmailApp.sendEmail(to, subject, plain, {
    htmlBody: html,
    name: opts.name || 'Sender Name',
    replyTo: opts.replyTo || undefined
    // Avoid `from:` unless Send-as for that address is verified on THIS account.
  });
}

function createHtmlDraft_(to, subject, plain, html, opts) {
  opts = opts || {};
  assertMailbox_(opts.expectedMailbox || prop_('EXPECTED_MAILBOX'));
  return GmailApp.createDraft(to, subject, plain, {
    htmlBody: html,
    name: opts.name || 'Sender Name',
    replyTo: opts.replyTo || undefined
  });
}
```

### From identity

| Goal | Approach |
|------|----------|
| Send as the Gmail that owns the script | Default — no `from` |
| Replies go to a public alias | `replyTo: 'hello@example.com'` |
| Visible From = custom domain | Configure Gmail **Send mail as** on that account first; then try `from`. If Apps Script throws `Invalid argument: alias@…`, fall back to store Gmail + `replyTo` |

## Script Properties

```javascript
function prop_(key, fallback) {
  var v = PropertiesService.getScriptProperties().getProperty(key);
  return v != null && v !== '' ? v : fallback;
}

function requireProp_(key) {
  var v = prop_(key);
  if (!v) throw new Error('Missing Script Property: ' + key);
  return v;
}
```

Typical keys: `EXPECTED_MAILBOX`, `REPLY_TO`, `DRY_RUN`, API keys. Never hard-code secrets in committed `.gs`.

## Time-driven triggers

```javascript
function installTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('tick')
    .timeBased()
    .everyMinutes(5)
    .create();
}

function tick() {
  if (prop_('DRY_RUN', 'true') === 'true') {
    Logger.log('DRY_RUN: would process…');
    return;
  }
  // real work
}
```

Re-run `installTriggers` after renaming the entry function. User must approve OAuth scopes on first run.

## Labels / threads (Gmail)

```javascript
function ensureLabel_(name) {
  return GmailApp.getUserLabelByName(name) || GmailApp.createLabel(name);
}
```

Prefer thread watermarks (last processed message date) over “processed forever” when follow-ups matter.

## Quotas & debugging

- Check **Executions** in the Apps Script UI for stack traces.
- Gmail daily send quotas are lower on consumer accounts than Workspace.
- `UrlFetchApp` needs explicit scope; first run prompts the user.
- Large HTML emails: keep under a few hundred KB; host images on HTTPS CDN URLs.

## HTML campaigns

For one-off promotional / apology emails, use [html-mailer.md](html-mailer.md) + `templates/HtmlMailer.gs`.  
Set `MAIL_TO` / `MAIL_HTML_DRIVE_ID` / `MAIL_VARS` — do not bake recipient or HTML into the `.gs` file.

## Multi-account checklist

1. Incognito / correct avatar → store (or intended) Google account.
2. Open the project owned by that account (not a copy under personal).
3. `logWhoAmI` → matches `EXPECTED_MAILBOX`.
4. Draft first; then send.
5. Confirm in that account’s **Sent** folder.

