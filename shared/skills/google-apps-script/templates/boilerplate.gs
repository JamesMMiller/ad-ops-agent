/**
 * Generic Apps Script starter.
 *
 * Install:
 * 1. Sign into the Google account that should own From / Sent.
 * 2. script.google.com → New project → paste this file.
 * 3. Project settings → Script properties:
 *      EXPECTED_MAILBOX = that account's email
 *      REPLY_TO         = optional public alias
 *      DRY_RUN          = true
 * 4. Run logWhoAmI, then createExampleDraft (or sendExample).
 */

function prop_(key, fallback) {
  var v = PropertiesService.getScriptProperties().getProperty(key);
  return v != null && v !== '' ? v : fallback;
}

function requireProp_(key) {
  var v = prop_(key);
  if (!v) throw new Error('Missing Script Property: ' + key);
  return v;
}

function assertMailbox_(expected) {
  expected = String(expected || requireProp_('EXPECTED_MAILBOX')).toLowerCase();
  var who = '';
  try {
    who = Session.getEffectiveUser().getEmail() || '';
  } catch (e) {}
  if (!who) {
    try {
      who = Session.getActiveUser().getEmail() || '';
    } catch (e2) {}
  }
  who = String(who).toLowerCase();
  if (who !== expected) {
    throw new Error(
      'Refusing to run. Effective user is "' +
        (who || '(unknown)') +
        '" but expected "' +
        expected +
        '". Sign into that account at script.google.com.'
    );
  }
  Logger.log('OK: running as ' + who);
}

function logWhoAmI() {
  Logger.log('effective=' + Session.getEffectiveUser().getEmail());
  try {
    Logger.log('active=' + Session.getActiveUser().getEmail());
  } catch (e) {
    Logger.log('active=(unavailable)');
  }
}

/**
 * Example: create a draft (safe default).
 * Set Script Property EXAMPLE_TO before running.
 */
function createExampleDraft() {
  assertMailbox_();
  var to = requireProp_('EXAMPLE_TO');
  var subject = 'Apps Script draft test';
  var plain = 'Hello — this is a draft created by Apps Script.';
  var html = '<p>Hello — this is a <strong>draft</strong> created by Apps Script.</p>';
  var opts = {
    name: prop_('FROM_NAME', 'Apps Script'),
    replyTo: prop_('REPLY_TO') || undefined
  };
  var draft = GmailApp.createDraft(to, subject, plain, {
    htmlBody: html,
    name: opts.name,
    replyTo: opts.replyTo
  });
  Logger.log('Draft id=' + draft.getId() + ' To=' + to);
}

/**
 * Example: live send. Requires DRY_RUN=false.
 */
function sendExample() {
  assertMailbox_();
  if (prop_('DRY_RUN', 'true') !== 'false') {
    throw new Error('DRY_RUN is not false — refusing to send. Set Script Property DRY_RUN=false to send.');
  }
  var to = requireProp_('EXAMPLE_TO');
  var subject = 'Apps Script send test';
  var plain = 'Hello — sent by Apps Script.';
  var html = '<p>Hello — <strong>sent</strong> by Apps Script.</p>';
  GmailApp.sendEmail(to, subject, plain, {
    htmlBody: html,
    name: prop_('FROM_NAME', 'Apps Script'),
    replyTo: prop_('REPLY_TO') || undefined
  });
  Logger.log('SENT to ' + to);
}
