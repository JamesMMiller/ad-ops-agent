/**
 * Generic HTML mailer (no campaign-specific hardcoding).
 *
 * Install (store or any mailbox):
 * 1. Sign into the Google account that should own From / Sent.
 * 2. script.google.com → New project (or open existing) → paste this file as Code.gs
 *    (or a second .gs file — avoid name clashes with other helpers).
 * 3. Project settings → Script properties — see showMailConfig / README.
 * 4. Run logWhoAmI → createMailDraft (safe) → sendMail only when ready.
 *
 * Body sources (first match wins for HTML):
 *   MAIL_HTML_DRIVE_ID  — Drive file id of an .html (best for large emails)
 *   MAIL_HTML_FILE      — Apps Script HTML file name (File → New → HTML), without .html
 *   MAIL_HTML           — inline HTML in a Script Property (keep small; ~9KB limit)
 *
 * Plain text:
 *   MAIL_PLAIN or MAIL_PLAIN_DRIVE_ID
 *
 * Personalisation: put {{NAME}}, {{FIRST_NAME}}, etc. in plain/HTML.
 * Fill via MAIL_VARS JSON, e.g. {"NAME":"Joseph","FIRST_NAME":"Joseph"}
 * Or MAIL_VAR_NAME / MAIL_VAR_FIRST_NAME script properties.
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

function logWhoAmI() {
  Logger.log('effective=' + Session.getEffectiveUser().getEmail());
  try {
    Logger.log('active=' + Session.getActiveUser().getEmail());
  } catch (e) {
    Logger.log('active=(unavailable)');
  }
}

function showMailConfig() {
  var keys = [
    'EXPECTED_MAILBOX',
    'MAIL_TO',
    'MAIL_SUBJECT',
    'FROM_NAME',
    'REPLY_TO',
    'DRY_RUN',
    'MAIL_HTML_DRIVE_ID',
    'MAIL_HTML_FILE',
    'MAIL_PLAIN_DRIVE_ID',
    'MAIL_VARS'
  ];
  keys.forEach(function (k) {
    var v = prop_(k, '');
    if (k.indexOf('HTML') >= 0 && v && v.length > 80) v = v.slice(0, 80) + '…';
    Logger.log(k + '=' + (v || '(unset)'));
  });
  Logger.log('MAIL_HTML set? ' + (prop_('MAIL_HTML') ? 'yes (' + prop_('MAIL_HTML').length + ' chars)' : 'no'));
  Logger.log('MAIL_PLAIN set? ' + (prop_('MAIL_PLAIN') ? 'yes (' + prop_('MAIL_PLAIN').length + ' chars)' : 'no'));
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

function mailVars_() {
  var vars = {};
  var json = prop_('MAIL_VARS', '');
  if (json) {
    try {
      vars = JSON.parse(json) || {};
    } catch (e) {
      throw new Error('MAIL_VARS must be valid JSON object. ' + e);
    }
  }
  var all = PropertiesService.getScriptProperties().getProperties();
  Object.keys(all).forEach(function (k) {
    if (k.indexOf('MAIL_VAR_') === 0) {
      vars[k.slice('MAIL_VAR_'.length)] = all[k];
    }
  });
  if (!vars.TO && prop_('MAIL_TO')) vars.TO = prop_('MAIL_TO');
  return vars;
}

function applyTokens_(text, vars) {
  if (!text) return text;
  var out = String(text);
  Object.keys(vars || {}).forEach(function (k) {
    var token = '{{' + k + '}}';
    out = out.split(token).join(String(vars[k]));
  });
  if (/\{\{[A-Z0-9_]+\}\}/.test(out)) {
    Logger.log('Warning: unresolved tokens remain in body: ' + out.match(/\{\{[A-Z0-9_]+\}\}/g));
  }
  return out;
}

function loadDriveText_(fileId) {
  var blob = DriveApp.getFileById(fileId).getBlob();
  return blob.getDataAsString();
}

function loadHtml_() {
  var driveId = prop_('MAIL_HTML_DRIVE_ID');
  if (driveId) return loadDriveText_(driveId);

  var file = prop_('MAIL_HTML_FILE');
  if (file) {
    // Project HTML file (File → New → HTML). Name without extension.
    return HtmlService.createHtmlOutputFromFile(file).getContent();
  }

  var inline = prop_('MAIL_HTML');
  if (inline) return inline;

  throw new Error(
    'No HTML body. Set MAIL_HTML_DRIVE_ID (preferred), or MAIL_HTML_FILE, or MAIL_HTML.'
  );
}

function loadPlain_() {
  var driveId = prop_('MAIL_PLAIN_DRIVE_ID');
  if (driveId) return loadDriveText_(driveId);
  var inline = prop_('MAIL_PLAIN');
  if (inline) return inline;
  // Fallback: strip tags poorly — better than empty for GmailApp
  var html = loadHtml_();
  return html
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function buildMail_() {
  assertMailbox_();
  var vars = mailVars_();
  var to = requireProp_('MAIL_TO');
  var subject = applyTokens_(requireProp_('MAIL_SUBJECT'), vars);
  var plain = applyTokens_(loadPlain_(), vars);
  var html = applyTokens_(loadHtml_(), vars);
  var options = {
    htmlBody: html,
    name: prop_('FROM_NAME', 'Our Tech Accessories'),
    replyTo: prop_('REPLY_TO') || undefined
  };
  return { to: to, subject: subject, plain: plain, options: options };
}

/** Safe default — creates a Gmail draft from Script Properties. */
function createMailDraft() {
  var mail = buildMail_();
  var draft = GmailApp.createDraft(mail.to, mail.subject, mail.plain, mail.options);
  Logger.log('Draft id=' + draft.getId() + ' To=' + mail.to + ' Subject=' + mail.subject);
  return draft;
}

/**
 * Live send. Requires DRY_RUN=false.
 * Always prefer createMailDraft first.
 */
function sendMail() {
  if (prop_('DRY_RUN', 'true') !== 'false') {
    throw new Error(
      'DRY_RUN is not false — refusing to send. Set Script Property DRY_RUN=false after a successful draft.'
    );
  }
  var mail = buildMail_();
  GmailApp.sendEmail(mail.to, mail.subject, mail.plain, mail.options);
  Logger.log('SENT to ' + mail.to + ' Subject=' + mail.subject);
}
