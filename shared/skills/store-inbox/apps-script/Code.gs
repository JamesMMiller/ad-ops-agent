/**
 * Our Tech Accessories — inbox triage bot (Gmail Apps Script)
 *
 * Install: see README.md in this folder.
 * Secrets: File → Project settings → Script properties
 *   HELLO_FROM          = hello@ourtechaccessories.com
 *   ESCALATE_TO         = your.personal@email.com
 *   GEMINI_API_KEY      = ... (https://aistudio.google.com/apikey)
 *   GEMINI_MODEL        = optional; default gemini-2.5-flash
 *   MAILBOX_ALIAS       = optional; default HELLO_FROM
 *   DRY_RUN             = true|false  (default false)
 *   STORE_FAQ           = optional override of default store knowledge (see prompting/store-faq.md)
 *   DEAL_FOLLOWUP_ENABLED = true|false (default false) — closed-thread deal mail
 *   DEAL_FOLLOWUP_IDLE_HOURS = hours after our last reply before idle deal (default 24)
 *   EMAIL_DAILY_BUDGET   = soft cap on bot sends/day (default 80; consumer Gmail hard cap is ~100)
 *   EMAIL_PER_RUN_MAX    = max sends per triage/sweep run (default 5)
 *   EMAIL_QUOTA_RESERVE  = stop when MailApp remaining ≤ this (default 5)
 *   SPAM_RESCUE_PER_RUN  = max Spam→Inbox moves per triage (default 2)
 *   SPAM_RESCUE_DAILY_MAX = max rescues per day (default 10)
 *   DEAL_BODIES_URL     = https://ourtechaccessories.com/pages/inbox-deal (JSON html+plain)
 *   DEAL_SUBJECT / DEAL_HTML / DEAL_PLAIN / DEAL_*_DRIVE_ID — optional body overrides
 *
 * Also paste DealFollowupBodies.gs (fallback GaN deal HTML/plain) into the same project.
 */

var DEFAULT_GEMINI_MODEL = 'gemini-2.5-flash';

var LABEL_PITCH = 'inbox-bot/pitch';
var LABEL_CUSTOMER = 'inbox-bot/customer';
var LABEL_UNCLEAR = 'inbox-bot/unclear';
var LABEL_FAQ = 'inbox-bot/faq';
var LABEL_DONE = 'inbox-bot/processed';
var LABEL_DEAD = 'inbox-bot/dead';
var LABEL_DEAL = 'inbox-bot/deal-followup';
var LABEL_CLOSE = 'inbox-bot/closed';
var LABEL_RESCUED = 'inbox-bot/rescued-from-spam';
var LABEL_OWNER_ASK = 'inbox-bot/owner-ask';

/** Reset each triageRecent / dealFollowUpSweep invocation. */
var EMAILS_SENT_THIS_RUN_ = 0;

/** Default knowledge — keep in sync with prompting/store-faq.md */
var DEFAULT_STORE_FAQ =
  'Our Tech Accessories (UK Shopify store).\n' +
  'Contact: hello@ourtechaccessories.com is the official customer inbox for Our Tech Accessories (ourtechaccessories.com).\n' +
  'If asked "is this the right inbox / store email / correct contact": confirm this is the store\'s customer email. ' +
  'Do not share personal name, personal email, phone, or home address. ' +
  'Do not role-play as a named owner.\n' +
  'If they ask to speak with / talk to / connect to the store owner or manager: ' +
  'pitch/SEO/agency/partnership → decline with deal follow-up; ' +
  'otherwise ask what it concerns first and do NOT escalate yet; escalate after they clarify if customer/order related. ' +
  'Do NOT claim you are the owner. Do NOT reply with only the generic support intro.\n' +
  'Generic greetings / check-ins with no real question (hi, hello, are you there, anyone there): ' +
  'reply with the short customer-support intro. Confirm this is the store support email and ask them to reply with product or order details (order number if they have one). ' +
  'A message that starts with "Hi there" but then asks a real question (e.g. shipping) is NOT a bare greeting — answer the question.\n' +
  'Official website: https://ourtechaccessories.com (with or without www). ' +
  'If asked "is this your official website?" and they mention ourtechaccessories.com, confirm yes. ' +
  'Do not invent other domains. If they name a different domain, say you only operate ourtechaccessories.com ' +
  'and they should not pay elsewhere; escalate if they already paid on another site.\n' +
  'Shipping destination: UK only for now. We do not ship internationally yet.\n' +
  'Future: We plan to offer international shipping later. No confirmed date. Do not promise a month.\n' +
  'Shipping cost: Depends on the product. Some items include free UK shipping (shown on the product page and at checkout). ' +
  'Others show a shipping fee at checkout. Never say shipping is always included or always extra. ' +
  'Never invent a pound amount. Point customers to the product page / checkout for the exact cost for their basket.\n' +
  'Delivery: Usually a few working days after dispatch within the UK; depends on product/carrier. Some PDPs say 3-7 working days for UK stock.\n' +
  'Never invent order status, tracking numbers, refunds, or returns decisions. Those need a human.\n' +
  'Discount / best price / last price / coupon asks: answer directly. Site prices are normal single-item prices. ' +
  'We run a volume deal on the 120W GaN retractable charger (2=15% off, 3=20% off, 4+=25% off). ' +
  'Do not invent other coupon codes or one-off markdowns. Send the current volume deal details.\n' +
  'Tone: short UK English, calm, human. No em dashes. No corporate or chatbot filler.';

function installTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    var fn = t.getHandlerFunction();
    if (fn === 'triageRecent' || fn === 'dealFollowUpSweep') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('triageRecent').timeBased().everyMinutes(5).create();
  ScriptApp.newTrigger('dealFollowUpSweep').timeBased().everyHours(1).create();
  ensureLabels_();
  Logger.log('Triggers installed: triageRecent (5m), dealFollowUpSweep (1h)');
}

function triageRecent() {
  EMAILS_SENT_THIS_RUN_ = 0;
  ensureLabels_();
  if (!canSendEmail_(1)) {
    Logger.log(
      'triageRecent aborted: daily email quota low (remaining=' +
        emailQuotaRemaining_() +
        ', budgetUsed=' +
        emailBudgetUsed_() +
        '). Quotas reset ~24h after first send.'
    );
    return;
  }
  // Gmail often parks cold outreach (and some real shoppers) in Spam.
  // We never move mail *to* Spam — we rescue a few human-looking threads, then triage.
  rescueSpamCandidates_();
  var maxSends = Number(props_().getProperty('EMAIL_PER_RUN_MAX') || '5');
  if (!(maxSends > 0)) maxSends = 5;
  var threads = GmailApp.search('in:inbox newer_than:2d', 0, 30);
  for (var i = 0; i < threads.length; i++) {
    if (EMAILS_SENT_THIS_RUN_ >= maxSends) {
      Logger.log('triageRecent: EMAIL_PER_RUN_MAX=' + maxSends + ' reached — defer rest');
      break;
    }
    if (!canSendEmail_(1)) {
      Logger.log('triageRecent: stopping early — email quota low');
      break;
    }
    triageThread_(threads[i]);
  }
  Logger.log(
    'triageRecent done sendsThisRun=' +
      EMAILS_SENT_THIS_RUN_ +
      ' remaining=' +
      emailQuotaRemaining_()
  );
}

/** Manual test from the script editor */
function triageOneTest() {
  EMAILS_SENT_THIS_RUN_ = 0;
  ensureLabels_();
  if (!canSendEmail_(1)) {
    Logger.log('triageOneTest aborted: email quota low remaining=' + emailQuotaRemaining_());
    return;
  }
  rescueSpamCandidates_();
  var threads = GmailApp.search('in:inbox newer_than:7d', 0, 5);
  if (!threads.length) {
    Logger.log('No inbox threads');
    return;
  }
  for (var i = 0; i < threads.length; i++) {
    if (needsTriage_(threads[i])) {
      triageThread_(threads[i]);
      return;
    }
  }
  Logger.log('No threads with a new inbound message to triage');
}

/** Manual: log MailApp remaining quota + bot budget counters. */
function logEmailQuota() {
  Logger.log(
    'MailApp remaining=' +
      emailQuotaRemaining_() +
      ' budgetUsed=' +
      emailBudgetUsed_() +
      '/' +
      emailDailyBudget_() +
      ' spamRescuedToday=' +
      spamRescueUsed_()
  );
}

/**
 * Pull likely-human mail out of Gmail Spam into Inbox so triage can reply
 * (decline+deal, FAQ, DEAL, or escalate). Leave clear bots / bulk newsletters in Spam.
 * Hard-capped — a big Spam folder must not burn the daily send quota.
 */
function rescueSpamCandidates_() {
  var dry = String(props_().getProperty('DRY_RUN') || 'false').toLowerCase() === 'true';
  if (!canSendEmail_(1)) {
    Logger.log('rescueSpamCandidates_: skip — email quota low');
    return;
  }
  var maxRun = Number(props_().getProperty('SPAM_RESCUE_PER_RUN') || '2');
  var maxDay = Number(props_().getProperty('SPAM_RESCUE_DAILY_MAX') || '10');
  if (!(maxRun > 0)) maxRun = 2;
  if (!(maxDay > 0)) maxDay = 10;
  var usedDay = spamRescueUsed_();
  if (usedDay >= maxDay) {
    Logger.log('rescueSpamCandidates_: daily max ' + maxDay + ' reached');
    return;
  }
  var room = Math.min(maxRun, maxDay - usedDay);
  var threads = GmailApp.search('in:spam newer_than:14d', 0, 25);
  Logger.log('rescueSpamCandidates_: spam pool=' + threads.length + ' room=' + room);
  var rescued = 0;
  for (var i = 0; i < threads.length && rescued < room; i++) {
    var thread = threads[i];
    var messages = thread.getMessages();
    if (!messages.length) continue;
    var msg = messages[messages.length - 1];
    var from = msg.getFrom();
    var subject = msg.getSubject() || '';
    var body = String(msg.getPlainBody() || msg.getBody() || '')
      .replace(/\s+/g, ' ')
      .slice(0, 6000);

    if (isTransactionalSender_(from, subject)) continue;
    if (isClearlyBot_(from, subject, body)) continue;
    if (looksLikeBulkNewsletter_(from, subject, body)) continue;
    if (hasLabel_(thread, LABEL_RESCUED)) continue;

    Logger.log(
      'Rescuing from Spam → Inbox thread=' +
        thread.getId() +
        ' from=' +
        from +
        ' subject=' +
        subject.slice(0, 80)
    );
    if (dry) continue;
    thread.moveToInbox();
    thread.addLabel(getLabel_(LABEL_RESCUED));
    noteSpamRescue_();
    rescued++;
  }
  Logger.log('rescueSpamCandidates_: rescued=' + rescued);
}

/** Clear marketing bulk — leave in Spam; do not rescue. */
function looksLikeBulkNewsletter_(from, subject, body) {
  var f = (from || '').toLowerCase();
  var blob = ((subject || '') + ' ' + (body || '')).toLowerCase();
  if (
    f.indexOf('noreply@') !== -1 ||
    f.indexOf('no-reply@') !== -1 ||
    f.indexOf('newsletter@') !== -1 ||
    f.indexOf('news@') !== -1 ||
    f.indexOf('marketing@') !== -1
  ) {
    return true;
  }
  var hints = [
    'unsubscribe',
    'view in browser',
    'view this email in your browser',
    'email preferences',
    'manage your subscription',
    'you are receiving this because',
    'you\'re receiving this email because',
    'this is a marketing email',
    'newsletter'
  ];
  var hits = 0;
  for (var i = 0; i < hints.length; i++) {
    if (blob.indexOf(hints[i]) !== -1) hits++;
  }
  return hits >= 2;
}

/** --- Email quota guards (consumer Gmail ≈ 100 recipients/day) --- */

function emailDayKey_() {
  var tz = Session.getScriptTimeZone() || 'Europe/London';
  return Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd');
}

function emailDailyBudget_() {
  var n = Number(props_().getProperty('EMAIL_DAILY_BUDGET') || '80');
  return n > 0 ? n : 80;
}

function emailBudgetUsed_() {
  return Number(props_().getProperty('emailSentCount:' + emailDayKey_()) || '0');
}

function emailQuotaRemaining_() {
  try {
    return MailApp.getRemainingDailyQuota();
  } catch (e) {
    Logger.log('MailApp.getRemainingDailyQuota failed: ' + e);
    return 999;
  }
}

function canSendEmail_(need) {
  need = need || 1;
  var reserve = Number(props_().getProperty('EMAIL_QUOTA_RESERVE') || '5');
  if (!(reserve >= 0)) reserve = 5;
  var remaining = emailQuotaRemaining_();
  if (remaining >= 0 && remaining <= reserve + need - 1) {
    Logger.log(
      'canSendEmail_: MailApp remaining=' + remaining + ' reserve=' + reserve + ' need=' + need
    );
    return false;
  }
  var used = emailBudgetUsed_();
  var budget = emailDailyBudget_();
  if (used + need > budget) {
    Logger.log('canSendEmail_: budget ' + used + '/' + budget + ' (need ' + need + ')');
    return false;
  }
  var maxRun = Number(props_().getProperty('EMAIL_PER_RUN_MAX') || '5');
  if (maxRun > 0 && EMAILS_SENT_THIS_RUN_ + need > maxRun) {
    Logger.log('canSendEmail_: per-run max ' + EMAILS_SENT_THIS_RUN_ + '/' + maxRun);
    return false;
  }
  return true;
}

function noteEmailSent_(n) {
  n = n || 1;
  EMAILS_SENT_THIS_RUN_ += n;
  var key = 'emailSentCount:' + emailDayKey_();
  props_().setProperty(key, String(emailBudgetUsed_() + n));
}

function spamRescueUsed_() {
  return Number(props_().getProperty('spamRescueCount:' + emailDayKey_()) || '0');
}

function noteSpamRescue_() {
  props_().setProperty('spamRescueCount:' + emailDayKey_(), String(spamRescueUsed_() + 1));
}

function isEmailQuotaError_(err) {
  var s = String(err || '').toLowerCase();
  return s.indexOf('too many times') !== -1 && s.indexOf('email') !== -1;
}

/** thread.reply with quota check + counting. Throws EmailQuotaError if blocked. */
function safeThreadReply_(thread, body, options) {
  if (!canSendEmail_(1)) {
    throw new Error('EmailQuota: daily/run budget exhausted — defer send');
  }
  try {
    thread.reply(body, options || {});
  } catch (e) {
    if (isEmailQuotaError_(e)) {
      throw new Error('EmailQuota: ' + e);
    }
    throw e;
  }
  noteEmailSent_(1);
}

function safeSendEmail_(to, subject, body, options) {
  if (!canSendEmail_(1)) {
    throw new Error('EmailQuota: daily/run budget exhausted — defer send');
  }
  try {
    GmailApp.sendEmail(to, subject, body, options || {});
  } catch (e) {
    if (isEmailQuotaError_(e)) {
      throw new Error('EmailQuota: ' + e);
    }
    throw e;
  }
  noteEmailSent_(1);
}

function clearRepliedToMessage_(thread, msg) {
  props_().deleteProperty(replyClaimKey_(thread, msg));
}

function clearDealSent_(thread) {
  try {
    var label = GmailApp.getUserLabelByName(LABEL_DEAL);
    if (label) thread.removeLabel(label);
  } catch (e) {
    /* ignore */
  }
  props_().deleteProperty(dealSentPropKey_(thread));
}

/**
 * Process a thread when the latest message is inbound and newer than our last handle.
 * Follow-ups on the same thread are supported (per-message watermark, not thread-done).
 * Dead only for: already declined pitches, or clearly automated/bot mail.
 */
function triageThread_(thread) {
  // Prevent overlapping triggers from double-sending the same inbound message.
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(30000);
  } catch (e) {
    Logger.log('triageThread_ lock timeout: ' + e);
    return;
  }
  try {
    triageThreadLocked_(thread);
  } finally {
    lock.releaseLock();
  }
}

function triageThreadLocked_(thread) {
  if (!needsTriage_(thread)) return;

  var messages = thread.getMessages();
  var msg = messages[messages.length - 1];
  var from = msg.getFrom();
  var subject = msg.getSubject() || '';
  var body = msg.getPlainBody() || msg.getBody() || '';
  body = String(body).replace(/\s+/g, ' ').slice(0, 6000);
  var dry = String(props_().getProperty('DRY_RUN') || 'false').toLowerCase() === 'true';

  // Same inbound message already got a bot reply (crash / overlapping run).
  if (alreadyRepliedToMessage_(thread, msg)) {
    Logger.log('Already replied to msg ' + msg.getId() + ' on thread ' + thread.getId());
    markThreadProcessed_(thread, msg);
    return;
  }

  // Already dead: swallow inbound quietly
  if (isDead_(thread)) {
    Logger.log('Thread ' + thread.getId() + ' is dead - ignoring inbound');
    markThreadProcessed_(thread, msg);
    return;
  }

  // Already declined a pitch on this thread: no more bot replies
  if (hasLabel_(thread, LABEL_PITCH)) {
    markDead_(thread, 'already declined pitch on this thread');
    markThreadProcessed_(thread, msg);
    thread.addLabel(getLabel_(LABEL_DONE));
    if (!dry) thread.moveToArchive();
    return;
  }

  if (isTransactionalSender_(from, subject)) {
    markThreadProcessed_(thread, msg);
    thread.addLabel(getLabel_(LABEL_DONE));
    return;
  }

  if (isClearlyBot_(from, subject, body)) {
    markDead_(thread, 'clearly automated/bot sender');
    markThreadProcessed_(thread, msg);
    thread.addLabel(getLabel_(LABEL_DONE));
    if (!dry) thread.moveToArchive();
    return;
  }

  // Short prior context helps follow-ups like "and Germany?"
  var context = threadContext_(messages);
  var result = classify_(from, subject, body, context);
  var label = (result.label || 'UNCLEAR').toUpperCase();

  Logger.log(
    'Thread ' +
      thread.getId() +
      ' msg ' +
      msg.getId() +
      ' → ' +
      label +
      ' (' +
      (result.reason || '') +
      ')'
  );

  // Discount / best-price asks → reply with the volume deal (never escalate).
  if (
    (label === 'DEAL' || isDiscountAsk_(subject, body)) &&
    label !== 'PITCH' &&
    label !== 'BOT' &&
    label !== 'TRANSACTIONAL' &&
    !hasOrderSupportSignals_(subject, body) &&
    !isOwnerEscalationAsk_(subject, body)
  ) {
    label = 'DEAL';
  }

  // "Speak to the owner" / "who runs this account" — pitch → decline+deal;
  // otherwise ask what it concerns first (never escalate on this message).
  if (
    (isOwnerEscalationAsk_(subject, body) || classifierImpliesOwnerAsk_(result, subject, body)) &&
    label !== 'BOT' &&
    label !== 'TRANSACTIONAL' &&
    label !== 'DEAL'
  ) {
    if (label === 'PITCH' || looksLikePitch_(subject, body, context)) {
      label = 'PITCH';
    } else {
      label = 'OWNER_ASK';
    }
  }

  // After we asked "what is this concerning?", their next reply → escalate (unless pitch/FAQ/deal/close).
  if (
    hasLabel_(thread, LABEL_OWNER_ASK) &&
    !isOwnerEscalationAsk_(subject, body) &&
    label !== 'BOT' &&
    label !== 'TRANSACTIONAL' &&
    label !== 'PITCH' &&
    label !== 'DEAL' &&
    label !== 'CLOSE' &&
    !(label === 'IGNORE' && isClosingThanks_(subject, body))
  ) {
    if (looksLikePitch_(subject, body, context)) {
      label = 'PITCH';
    } else if (label === 'FAQ' && (isShippingFaqAsk_(subject, body) || isInboxConfirmQuestion_(subject, body) || isOfficialWebsiteQuestion_(subject, body) || isGenericGreeting_(subject, body))) {
      // Allow a clear FAQ answer without escalating
    } else if (label === 'FAQ' || label === 'CUSTOMER' || label === 'UNCLEAR' || label === 'IGNORE') {
      label = 'CUSTOMER';
    }
  }

  if (label === 'BOT') {
    markDead_(thread, 'classifier: BOT (' + (result.reason || '') + ')');
    markThreadProcessed_(thread, msg);
    thread.addLabel(getLabel_(LABEL_DONE));
    if (!dry) thread.moveToArchive();
    return;
  }

  // Claim this inbound before any send so a second run cannot reply again.
  // If quota blocks the send, clear the claim and leave watermark unset so we retry later.
  if (!dry) {
    if (!canSendEmail_(1)) {
      Logger.log('Deferring thread ' + thread.getId() + ' — email quota low');
      return;
    }
    markRepliedToMessage_(thread, msg);
  }

  try {
    if (label === 'CLOSE' || (label === 'IGNORE' && isClosingThanks_(subject, body))) {
      thread.addLabel(getLabel_(LABEL_CLOSE));
      if (!dry && maybeSendDealFollowUpUnlocked_(thread, msg, 'close')) {
        // deal sent
      } else if (!dry) {
        thread.moveToArchive();
      }
    } else if (label === 'PITCH') {
      thread.addLabel(getLabel_(LABEL_PITCH));
      if (!dry) {
        // One outbound only: deal mail already includes the "not looking for marketing" intro.
        if (!(dealFollowUpEnabled_() && maybeSendDealFollowUpUnlocked_(thread, msg, 'pitch'))) {
          sendDecline_(thread, msg);
        }
        thread.moveToArchive();
      }
      // Stop further bot triage (sweep may still send a missed deal).
      markDead_(thread, 'pitch declined');
    } else if (label === 'DEAL') {
      thread.addLabel(getLabel_(LABEL_FAQ));
      if (!dry) handleDiscountAsk_(thread, msg, true);
    } else if (label === 'OWNER_ASK') {
      // Clarify first — do not escalate until they say what it is about.
      thread.addLabel(getLabel_(LABEL_OWNER_ASK));
      if (!dry) sendOwnerAskReply_(thread, msg);
    } else if (label === 'FAQ') {
      thread.addLabel(getLabel_(LABEL_FAQ));
      if (!dry) {
        sendFaqReply_(thread, msg, from, subject, body, context);
      }
    } else if (label === 'IGNORE') {
      if (!dry) thread.moveToArchive();
    } else if (label === 'TRANSACTIONAL') {
      // leave in inbox
    } else {
      // CUSTOMER or UNCLEAR (including clarification after owner-ask)
      thread.addLabel(getLabel_(label === 'CUSTOMER' ? LABEL_CUSTOMER : LABEL_UNCLEAR));
      if (!dry) {
        if (hasLabel_(thread, LABEL_OWNER_ASK) && !result.reason) {
          result.reason = 'clarified after owner-ask';
        }
        escalate_(thread, msg, result);
      }
    }
  } catch (e) {
    if (String(e).indexOf('EmailQuota') !== -1) {
      Logger.log('Email quota hit mid-triage — clearing claim for retry: ' + e);
      if (!dry) clearRepliedToMessage_(thread, msg);
      return;
    }
    throw e;
  }

  markThreadProcessed_(thread, msg);
  thread.addLabel(getLabel_(LABEL_DONE));
}

function replyClaimKey_(thread, msg) {
  return 'replySent:' + thread.getId() + ':' + msg.getId();
}

function alreadyRepliedToMessage_(thread, msg) {
  return props_().getProperty(replyClaimKey_(thread, msg)) === '1';
}

function markRepliedToMessage_(thread, msg) {
  props_().setProperty(replyClaimKey_(thread, msg), '1');
}

function needsTriage_(thread) {
  var messages = thread.getMessages();
  if (!messages.length) return false;
  var msg = messages[messages.length - 1];
  if (isFromUs_(msg.getFrom())) return false;
  var ts = msg.getDate().getTime();
  var prev = Number(props_().getProperty(threadWatermarkKey_(thread)) || 0);
  return ts > prev;
}

function isDead_(thread) {
  return hasLabel_(thread, LABEL_DEAD);
}

function markDead_(thread, reason) {
  thread.addLabel(getLabel_(LABEL_DEAD));
  Logger.log('Thread ' + thread.getId() + ' marked DEAD: ' + reason);
}

/** Hard signals that this is automated mail, not a person. */
function isClearlyBot_(from, subject, body) {
  var f = (from || '').toLowerCase();
  var blob = ((subject || '') + ' ' + (body || '')).toLowerCase();

  var fromHints = [
    'noreply@',
    'no-reply@',
    'no_reply@',
    'donotreply@',
    'do-not-reply@',
    'mailer-daemon@',
    'notifications@',
    'automated@',
    'bounce@'
  ];
  for (var i = 0; i < fromHints.length; i++) {
    if (f.indexOf(fromHints[i]) !== -1) return true;
  }

  var bodyHints = [
    'this is an automated message',
    'this is an automatic reply',
    'automatic reply:',
    'auto-reply:',
    'autoreply',
    'do not reply to this email',
    'please do not reply',
    'this mailbox is not monitored',
    'out of office auto'
  ];
  for (var j = 0; j < bodyHints.length; j++) {
    if (blob.indexOf(bodyHints[j]) !== -1) return true;
  }

  return false;
}

function markThreadProcessed_(thread, msg) {
  props_().setProperty(threadWatermarkKey_(thread), String(msg.getDate().getTime()));
}

function threadWatermarkKey_(thread) {
  return 'tw_' + thread.getId();
}

/** Last few messages for classifier context (follow-ups). */
function threadContext_(messages) {
  var start = Math.max(0, messages.length - 4);
  var chunks = [];
  for (var i = start; i < messages.length - 1; i++) {
    var m = messages[i];
    var who = isFromUs_(m.getFrom()) ? 'US' : 'THEM';
    var snippet = String(m.getPlainBody() || '')
      .replace(/\s+/g, ' ')
      .slice(0, 400);
    chunks.push(who + ': ' + (m.getSubject() || '') + ' | ' + snippet);
  }
  return chunks.join('\n');
}

function classify_(from, subject, body, context) {
  var key = props_().getProperty('GEMINI_API_KEY');
  if (!key) {
    return heuristicClassify_(from, subject, body);
  }
  try {
    return geminiClassify_(key, from, subject, body, context || '');
  } catch (e) {
    Logger.log('Gemini failed, heuristic fallback: ' + e);
    return heuristicClassify_(from, subject, body);
  }
}

function geminiClassify_(apiKey, from, subject, body, context) {
  var faq = storeFaq_();
  var prompt =
    'You triage email for a small UK Shopify store (Our Tech Accessories).\n' +
    'Return ONLY compact JSON: {"label":"PITCH|FAQ|DEAL|CUSTOMER|UNCLEAR|TRANSACTIONAL|IGNORE|CLOSE|BOT","reason":"short","confidence":0.0}\n' +
    'PITCH = sales/SEO/agency/partnership/"we can stop your spam" cold outreach.\n' +
    'DEAL = customer asking for a discount, better/last/best price, coupon, voucher, promo, or "any deals/offers" ' +
    'on store products (not refunds). Reply with the current volume deal. Do NOT escalate DEAL.\n' +
    'FAQ = general question answerable ONLY from this store knowledge (no order lookup needed):\n' +
    '---STORE KNOWLEDGE---\n' +
    faq +
    '\n---END---\n' +
    'Examples of FAQ: do you ship to my country, international shipping, UK only, delivery times, ' +
    'free shipping / shipping fee, is this the right inbox, is this the store email, ' +
    'am I emailing the correct store contact, is this your official website, ' +
    'ourtechaccessories.com official site, who are you / contact email.\n' +
    'Examples of DEAL: "is this your last price?", "any discount?", "can you do better on price?", ' +
    '"got a coupon?", "any promo on the charger?", "best price?"\n' +
    'If the message is ONLY a greeting or check-in with no real question ' +
    '(hi, hello, hey, are you there, anyone there, just checking), choose FAQ. ' +
    'Reply with the customer-support intro (this is store support; ask for product/order details).\n' +
    'IMPORTANT: "Hi there, …" followed by a real question (shipping, product, price) is NOT a bare greeting — ' +
    'classify as FAQ/DEAL/CUSTOMER for that question and answer it.\n' +
    'If the message ONLY asks whether this is the right store inbox/contact, choose FAQ and confirm hello@ is the store customer email.\n' +
    'If the message ONLY asks whether ourtechaccessories.com is the official website, choose FAQ and confirm yes.\n' +
    'If they ask to speak with / talk to / connect to the store owner or manager, ' +
    'OR ask who runs / owns / operates this account/store (without a stated order topic):\n' +
    '- If it is (or follows) a sales/SEO/agency/partnership pitch → choose PITCH (decline + deal).\n' +
    '- Otherwise choose FAQ (we will ask what their request is about first — do NOT treat as needing a human yet).\n' +
    'Do NOT choose CUSTOMER merely because they asked who runs the account or to speak to the owner.\n' +
    'Do NOT treat "speak to the owner" / "who runs this account" as FAQ inbox-confirm.\n' +
    'If "right inbox / official website" is just an opener before SEO, partnership, agency, or marketing pitch, choose PITCH.\n' +
    'CUSTOMER = order number, tracking, refund, return, damaged item, wrong colour, payment problem, ' +
    'or a stated customer topic after we asked what the owner request was about.\n' +
    'UNCLEAR = maybe customer or maybe FAQ but not safe to auto-answer. Escalate. Do NOT use UNCLEAR for a bare greeting, owner-identity ask, or a clear discount ask.\n' +
    'TRANSACTIONAL = receipts, Shopify, Google, banks, 2FA.\n' +
    'CLOSE = thread wrapping up: short thanks / cheers / all good / that helps / perfect / sorted, ' +
    'with no new question (prefer CLOSE over IGNORE when PRIOR CONTEXT shows we already helped).\n' +
    'IGNORE = only clear newsletters/bulk with unsubscribe (no real question from a person). ' +
    'When unsure, choose UNCLEAR, FAQ, or DEAL — never IGNORE a human question.\n' +
    'BOT = clearly an autoresponder, chatbot, or non-human loop (not a real shopper). Only when obvious.\n' +
    'This may be a follow-up in an existing thread. Use PRIOR CONTEXT when the latest message is short (e.g. "and Germany?").\n' +
    'When unsure between DEAL and FAQ, choose DEAL if they are asking about price/discount.\n' +
    'When unsure between FAQ and CUSTOMER, choose CUSTOMER or UNCLEAR (never invent order facts).\n' +
    'When unsure between PITCH and CUSTOMER, choose UNCLEAR.\n' +
    'When unsure between PITCH and IGNORE, choose PITCH (decline + optional deal) so a person still gets a reply.\n' +
    'When unsure whether BOT, do NOT choose BOT.\n\n' +
    (context ? 'PRIOR CONTEXT:\n' + context + '\n\n' : '') +
    'LATEST From: ' +
    from +
    '\nSubject: ' +
    subject +
    '\n\n' +
    body;

  var parsed = geminiJson_(apiKey, prompt);
  return {
    label: String(parsed.label || 'UNCLEAR').toUpperCase(),
    reason: String(parsed.reason || ''),
    confidence: Number(parsed.confidence || 0)
  };
}

function heuristicClassify_(from, subject, body) {
  var blob = (subject + ' ' + body).toLowerCase();
  var fromL = (from || '').toLowerCase();

  if (isTransactionalSender_(from, subject)) {
    return { label: 'TRANSACTIONAL', reason: 'known transactional', confidence: 0.9 };
  }

  if (isClosingThanks_(subject, body)) {
    return { label: 'CLOSE', reason: 'closing thanks', confidence: 0.7 };
  }

  if (hasOrderSupportSignals_(subject, body)) {
    return { label: 'CUSTOMER', reason: 'customer order/support signal', confidence: 0.7 };
  }

  if (isDiscountAsk_(subject, body)) {
    return { label: 'DEAL', reason: 'discount/price ask', confidence: 0.8 };
  }

  var pitchHints = [
    'seo', 'backlink', 'guest post', 'link building', 'partnership opportunity',
    'influencer', 'i can help you', 'stop spam', 'fake customer', 'marketing agency',
    'grow your store', 'facebook ads expert', 'we noticed your store', 'warm response'
  ];
  var hits = 0;
  for (var j = 0; j < pitchHints.length; j++) {
    if (blob.indexOf(pitchHints[j]) !== -1) hits++;
  }
  if (hits >= 1 || looksLikePitch_(subject, body, '')) {
    return { label: 'PITCH', reason: 'pitch keywords x' + hits, confidence: 0.65 };
  }

  if (isOwnerEscalationAsk_(subject, body)) {
    if (hasOrderSupportSignals_(subject, body)) {
      return { label: 'CUSTOMER', reason: 'owner ask + order/support', confidence: 0.85 };
    }
    return { label: 'FAQ', reason: 'owner-identity ask — clarify first', confidence: 0.8 };
  }

  if (isShippingFaqAsk_(subject, body)) {
    return { label: 'FAQ', reason: 'shipping destination/cost ask', confidence: 0.8 };
  }

  if (isGenericGreeting_(subject, body)) {
    return { label: 'FAQ', reason: 'generic greeting/check-in', confidence: 0.75 };
  }

  var faqHints = [
    'right inbox', 'correct inbox', 'right email', 'correct email',
    'store\'s email', 'stores email', 'official email',
    'is this the store', 'emailing the store', 'right contact',
    'official website', 'official site', 'official web',
    'ourtechaccessories.com', 'is this your website', 'your website',
    'how long does delivery', 'delivery time', 'postage',
    'free shipping', 'shipping fee', 'shipping included'
  ];
  for (var f = 0; f < faqHints.length; f++) {
    if (blob.indexOf(faqHints[f]) !== -1) {
      return { label: 'FAQ', reason: 'faq keyword: ' + faqHints[f], confidence: 0.65 };
    }
  }

  return { label: 'UNCLEAR', reason: 'no strong signal', confidence: 0.4 };
}

/** Order/refund support — escalate; do not treat as a discount ask. */
function hasOrderSupportSignals_(subject, body) {
  var blob = (String(subject || '') + ' ' + String(body || '')).toLowerCase();
  var hints = [
    'order #',
    'order number',
    'tracking',
    'refund',
    'return',
    'parcel',
    'damaged',
    'wrong colour',
    'wrong color',
    'my package',
    'where is my order',
    'missing item',
    'cancel my'
  ];
  for (var i = 0; i < hints.length; i++) {
    if (blob.indexOf(hints[i]) !== -1) return true;
  }
  return false;
}

/** Shopper asking for a discount / better price (not a refund). */
function isDiscountAsk_(subject, body) {
  if (hasOrderSupportSignals_(subject, body)) return false;
  var text = (String(subject || '') + ' ' + String(body || '')).toLowerCase();
  text = text.replace(/\s+/g, ' ').trim();
  if (!text) return false;
  var hints = [
    'last price',
    'best price',
    'final price',
    'any discount',
    'a discount',
    'got a discount',
    'have a discount',
    'got discount',
    'any deal',
    'better price',
    'lower price',
    'lower the price',
    'reduce the price',
    'cheaper',
    'price drop',
    'coupon',
    'voucher',
    'promo code',
    'promotional code',
    'special offer',
    'any offer',
    'any promo',
    'can you do better',
    'is that your best',
    'your best price',
    'negotiate',
    'do you discount',
    'discounts available',
    'student discount',
    'bulk discount',
    'volume discount'
  ];
  for (var i = 0; i < hints.length; i++) {
    if (text.indexOf(hints[i]) !== -1) return true;
  }
  // Loose: "discount?" / "discount please" as a short message
  if (/\bdiscounts?\b/.test(text) && text.length < 220) return true;
  return false;
}

/**
 * Customer asked for a discount / last price → send the volume deal (once per thread).
 * If the deal already went out, send a short plain reminder instead.
 * @param {boolean=} alreadyLocked true when caller holds ScriptLock (triage).
 */
function handleDiscountAsk_(thread, msg, alreadyLocked) {
  if (dealAlreadySent_(thread) || threadLooksLikeDealAlreadySent_(thread)) {
    if (threadLooksLikeDealAlreadySent_(thread) && !dealAlreadySent_(thread)) {
      markDealSent_(thread, 'discount');
    }
    sendDiscountAlreadySentReply_(thread, msg);
    return;
  }
  if (dealFollowUpEnabled_()) {
    var sent = alreadyLocked
      ? maybeSendDealFollowUpUnlocked_(thread, msg, 'discount')
      : maybeSendDealFollowUp_(thread, msg, 'discount');
    if (sent) return;
    Logger.log('Discount deal send failed; falling back to text reply');
  }
  sendDiscountTextReply_(thread, msg);
}

function sendDiscountAlreadySentReply_(thread, msg) {
  var hello = helloFrom_();
  var body =
    'Hi,\n\n' +
    'The prices on the site are the normal single-item prices. ' +
    'The volume deal we already shared on this thread is the current offer ' +
    '(more chargers = a deeper discount). We do not have a separate one-off coupon beyond that.\n\n' +
    'If you still need help with an order, reply with your order number.\n\n' +
    'Our Tech Accessories\n' +
    hello +
    '\n';
  safeThreadReply_(thread, sanitizeCustomerReply_(body), { from: hello });
}

function sendDiscountTextReply_(thread, msg) {
  var hello = helloFrom_();
  var body =
    'Hi,\n\n' +
    'Site prices are the normal single-item prices. We do not usually discount one-off, ' +
    'but we do have a current volume deal on the 120W GaN charger with the built-in retractable cable:\n\n' +
    '- 2 chargers: 15% off\n' +
    '- 3 chargers: 20% off\n' +
    '- 4 or more: 25% off\n\n' +
    'You can mix colours in one order. Shop here:\n' +
    'https://ourtechaccessories.com/products/120w-gan-fast-charger-with-a-built-in-retractable-cable\n\n' +
    'Happy to help if you have a product question or an order number.\n\n' +
    'Our Tech Accessories\n' +
    hello +
    '\n';
  safeThreadReply_(thread, sanitizeCustomerReply_(body), { from: hello });
}

function sendFaqReply_(thread, msg, from, subject, body, context) {
  var hello = helloFrom_();
  var replyBody = sanitizeCustomerReply_(draftFaqReply_(from, subject, body, context));
  safeThreadReply_(thread, replyBody, { from: hello });
}

function draftFaqReply_(from, subject, body, context) {
  // Fixed copy for bare greetings only (don't let the model improvise)
  if (isGenericGreeting_(subject, body)) {
    return defaultSupportIntroReply_();
  }
  // Deterministic shipping answer if Gemini is down / fails
  if (isShippingFaqAsk_(subject, body)) {
    var keyShip = props_().getProperty('GEMINI_API_KEY');
    if (keyShip) {
      try {
        return geminiFaqReply_(keyShip, storeFaq_(), from, subject, body, context || '');
      } catch (eShip) {
        Logger.log('Shipping FAQ draft failed, template fallback: ' + eShip);
      }
    }
    return defaultShippingReply_();
  }
  var key = props_().getProperty('GEMINI_API_KEY');
  var faq = storeFaq_();
  if (key) {
    try {
      return geminiFaqReply_(key, faq, from, subject, body, context || '');
    } catch (e) {
      Logger.log('FAQ draft failed, template fallback: ' + e);
    }
  }
  if (isInboxConfirmQuestion_(subject, body)) {
    return defaultInboxConfirmReply_();
  }
  if (isOfficialWebsiteQuestion_(subject, body)) {
    return defaultOfficialWebsiteReply_();
  }
  if (isShippingFaqAsk_(subject, body)) {
    return defaultShippingReply_();
  }
  return defaultSupportIntroReply_();
}

function geminiFaqReply_(apiKey, faq, from, subject, body, context) {
  var prompt =
    'Write a short customer-support reply for Our Tech Accessories.\n' +
    'Use ONLY facts from STORE KNOWLEDGE. If the question needs order/tracking/refund data, reply asking them to reply with their order number and say a human will help.\n' +
    'If they ask about international / outside-UK shipping: say we ship UK only for now, international is planned later with no date. Answer that first — do not send only a generic support intro.\n' +
    'If they ask to speak with the store owner: ask what their request is about. Do not claim you are the owner. Do not send only the generic support intro.\n' +
    'Style rules (strict):\n' +
    '- UK English. Plain text only. Max ~120 words. No subject line.\n' +
    '- Sound like a real small-shop person, not a chatbot or marketing email.\n' +
    '- Never use em dashes (the long dash). Use a full stop, comma, or hyphen instead.\n' +
    '- Avoid AI/corporate filler: "I hope this finds you well", "I\'d be happy to", ' +
    '"Don\'t hesitate", "Certainly", "Absolutely", "Please note that", "seamless", ' +
    '"leverage", "delve", "elevate", "Furthermore", "Additionally", "rest assured".\n' +
    '- Avoid stacked rhetorical questions and over-polished three-part lists.\n' +
    '- Keep it direct and warm. One "Thanks" is enough.\n' +
    '- If this is a follow-up, answer the latest message using PRIOR CONTEXT.\n' +
    'Start with Hi, end with:\nOur Tech Accessories\n' +
    helloFrom_() +
    '\n\nSTORE KNOWLEDGE:\n' +
    faq +
    (context ? '\n\nPRIOR CONTEXT:\n' + context : '') +
    '\n\nLATEST From: ' +
    from +
    '\nSubject: ' +
    subject +
    '\n\n' +
    body +
    '\n\nReturn ONLY the email body text.';

  var text = geminiText_(apiKey, prompt);
  text = String(text || '').replace(/```/g, '').trim();
  if (!text || text.length < 40) throw new Error('empty FAQ reply');
  return text;
}

function defaultFaqReply_() {
  return defaultSupportIntroReply_();
}

function defaultSupportIntroReply_() {
  var hello = helloFrom_();
  return (
    'Hi,\n\n' +
    'Thanks for getting in touch. This is the customer support email for Our Tech Accessories.\n\n' +
    'If you have a product question, or need help with an order, reply with a few details. ' +
    'For order help, include your order number if you have it.\n\n' +
    'Our Tech Accessories\n' +
    hello +
    '\n'
  );
}

function defaultShippingReply_() {
  var hello = helloFrom_();
  return (
    'Hi,\n\n' +
    'We currently ship within the UK only, so we are not offering international delivery yet.\n\n' +
    'We do plan to expand shipping later, but we do not have a confirmed date. ' +
    'Worth checking the site again in future, or email us if you have a UK delivery question.\n\n' +
    'Our Tech Accessories\n' +
    hello +
    '\n'
  );
}

function sendOwnerAskReply_(thread, msg) {
  var hello = helloFrom_();
  var body = sanitizeCustomerReply_(defaultOwnerAskReply_());
  safeThreadReply_(thread, body, { from: hello });
}

function defaultOwnerAskReply_() {
  var hello = helloFrom_();
  return (
    'Hi,\n\n' +
    'Happy to help. Could you tell me what this is about ' +
    '(an order, a product question, shipping, or something else)? ' +
    'Reply with a short note and we will take it from there.\n\n' +
    'Our Tech Accessories\n' +
    hello +
    '\n'
  );
}

/**
 * True only for bare hellos / check-ins with no real question.
 * "Hi there, do you ship internationally?" must return false.
 */
function isGenericGreeting_(subject, body) {
  if (isShippingFaqAsk_(subject, body)) return false;
  if (isOwnerEscalationAsk_(subject, body)) return false;
  if (isDiscountAsk_(subject, body)) return false;
  if (hasOrderSupportSignals_(subject, body)) return false;
  if (isInboxConfirmQuestion_(subject, body)) return false;
  if (isOfficialWebsiteQuestion_(subject, body)) return false;

  var raw = String(body || '');
  // Drop common mobile mail footers so short check-ins still match
  raw = raw.replace(/sent from .*$/gim, '');
  raw = raw.replace(/get outlook for .*$/gim, '');
  var text = (String(subject || '') + ' ' + raw).toLowerCase();
  text = text.replace(/\s+/g, ' ').trim();

  // Strip quoted history / signatures that can inflate length
  text = text.replace(/\bon \d{1,2}.*wrote:.*$/i, '');
  text = text.split('-----original message-----')[0];

  var compact = text
    .replace(/https?:\/\/\S+/g, ' ')
    .replace(/[^a-z0-9\s?']/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  var words = compact.split(' ').filter(function (w) {
    return w.length;
  });

  // Substantive asks are never "just a greeting"
  if (words.length > 12) return false;
  if (
    compact.indexOf('wondering') !== -1 ||
    compact.indexOf('question') !== -1 ||
    compact.indexOf('shipping') !== -1 ||
    compact.indexOf('deliver') !== -1 ||
    compact.indexOf('order') !== -1 ||
    compact.indexOf('product') !== -1 ||
    compact.indexOf('refund') !== -1 ||
    compact.indexOf('speak with') !== -1 ||
    compact.indexOf('speak to') !== -1 ||
    compact.indexOf('connect me') !== -1 ||
    compact.indexOf('store owner') !== -1
  ) {
    return false;
  }

  var greetHints = [
    'are you there',
    'anyone there',
    'you there',
    'just checking',
    'hello there',
    'hi there',
    'hey there',
    'good morning',
    'good afternoon',
    'good evening'
  ];
  for (var i = 0; i < greetHints.length; i++) {
    if (compact.indexOf(greetHints[i]) !== -1) {
      // Only if little remains after removing the greeting phrase
      var rest = compact.replace(greetHints[i], ' ').replace(/\s+/g, ' ').trim();
      rest = rest
        .replace(/\bour tech accessories\b/g, '')
        .replace(/\bhi\b/g, '')
        .replace(/\bhello\b/g, '')
        .replace(/\bhey\b/g, '')
        .replace(/\bthanks?\b/g, '')
        .replace(/\bplease\b/g, '')
        .replace(/\s+/g, ' ')
        .trim();
      if (!rest || rest.length <= 8) return true;
      return false;
    }
  }

  // Very short hello/hi/hey with little else
  if (words.length <= 6) {
    var first = words[0] || '';
    if (
      first === 'hi' ||
      first === 'hello' ||
      first === 'hey' ||
      first === 'hola' ||
      compact === 'hello our tech accessories' ||
      compact.indexOf('hello our tech') === 0
    ) {
      return true;
    }
  }
  return false;
}

/** Ask to speak with owner/manager, or who runs/owns the account (not inbox-confirm FAQ). */
function isOwnerEscalationAsk_(subject, body) {
  var blob = ((subject || '') + ' ' + (body || '')).toLowerCase().replace(/\s+/g, ' ');
  if (!blob) return false;
  // Inbox-confirm style ("is this the store owner contact?") is FAQ, not owner-ask.
  if (
    (blob.indexOf('right inbox') !== -1 ||
      blob.indexOf('correct inbox') !== -1 ||
      blob.indexOf('right email') !== -1 ||
      blob.indexOf('correct email') !== -1 ||
      blob.indexOf('right contact') !== -1) &&
    blob.indexOf('speak') === -1 &&
    blob.indexOf('talk') === -1 &&
    blob.indexOf('connect') === -1 &&
    blob.indexOf('who runs') === -1 &&
    blob.indexOf('who owns') === -1
  ) {
    return false;
  }
  if (/\b(speak|talk|chat)\s+(to|with)\s+(the\s+)?(store\s+)?(owner|manager)\b/.test(blob)) {
    return true;
  }
  if (/\bconnect\s+me\s+(to|with)\s+(the\s+)?(store\s+)?(owner|manager)\b/.test(blob)) {
    return true;
  }
  if (/\b(put|pass)\s+me\s+(through\s+)?(to\s+)?(the\s+)?(store\s+)?(owner|manager)\b/.test(blob)) {
    return true;
  }
  if (/\bcan i (speak|talk) (to|with)\b/.test(blob) && /\b(owner|manager)\b/.test(blob)) {
    return true;
  }
  if (/\bstore owner\??\s*$/.test(blob.trim()) || blob.trim() === 'store owner?') {
    return true;
  }
  if (blob.indexOf('connect me to the store owner') !== -1) return true;
  // Indirect owner asks (clarify first — do not escalate yet)
  if (/\bwho\s+(runs|owns|operates|manages)\b/.test(blob) && /\b(this\s+)?(account|store|shop|business|page)\b/.test(blob)) {
    return true;
  }
  if (/\bwho\s+(runs|owns|operates|manages)\s+this\b/.test(blob)) return true;
  if (/\bwho('?s| is)\s+(the\s+)?(real\s+)?(owner|manager|founder|operator)\b/.test(blob)) return true;
  if (/\b(are you|is this)\s+(the\s+)?(store\s+)?(owner|manager|founder)\b/.test(blob)) return true;
  if (/\bwho\s+is\s+in\s+charge\b/.test(blob)) return true;
  if (/\b(owner|manager)\s+of\s+(this\s+)?(account|store|shop)\b/.test(blob)) return true;
  return false;
}

/**
 * Gemini sometimes labels owner-identity asks as CUSTOMER; catch by reason text too.
 * Only when there is no clear order/support signal and it is not a pitch.
 */
function classifierImpliesOwnerAsk_(result, subject, body) {
  if (hasOrderSupportSignals_(subject, body)) return false;
  if (looksLikePitch_(subject, body, '')) return false;
  if (isOwnerEscalationAsk_(subject, body)) return true;
  var reason = String((result && result.reason) || '').toLowerCase();
  if (!reason) return false;
  var ownerish =
    reason.indexOf('owner') !== -1 ||
    reason.indexOf('manager') !== -1 ||
    reason.indexOf('who runs') !== -1 ||
    reason.indexOf('who owns') !== -1 ||
    reason.indexOf('speak to') !== -1 ||
    reason.indexOf('talk to') !== -1;
  if (!ownerish) return false;
  // Already stated a customer topic in the same mail → real escalate, not clarify-first
  if (hasOrderSupportSignals_(subject, body)) return false;
  return true;
}

/**
 * Sales / SEO / agency cold outreach — including "speak to the owner" as a pitch closer.
 * Prefer LATEST message signals; PRIOR CONTEXT only when the latest is a short owner-ask.
 */
function looksLikePitch_(subject, body, context) {
  var latest = (String(subject || '') + ' ' + String(body || '')).toLowerCase();
  var hints = [
    'seo',
    'backlink',
    'guest post',
    'link building',
    'partnership opportunity',
    'partnership',
    'collaborate with',
    'collaboration',
    'influencer',
    'i can help you',
    'stop spam',
    'fake customer',
    'marketing agency',
    'digital marketing',
    'grow your store',
    'grow your sales',
    'facebook ads expert',
    'google ads',
    'we noticed your store',
    'warm response',
    'white hat',
    'off-page',
    'rank on google',
    'lead generation',
    'i run an agency',
    'our agency',
    'media buying',
    'shopify expert',
    'free audit',
    'proposal for you'
  ];
  var hits = 0;
  for (var i = 0; i < hints.length; i++) {
    if (latest.indexOf(hints[i]) !== -1) hits++;
  }
  if (hits >= 1) return true;

  // Short owner-ask after a pitch in prior THEM messages
  if (isOwnerEscalationAsk_(subject, body) && context) {
    var ctx = String(context).toLowerCase();
    for (var j = 0; j < hints.length; j++) {
      if (ctx.indexOf('them:') !== -1 && ctx.indexOf(hints[j]) !== -1) return true;
    }
  }
  return false;
}

/** International / destination / UK-only shipping questions. */
function isShippingFaqAsk_(subject, body) {
  var blob = ((subject || '') + ' ' + (body || '')).toLowerCase();
  var hints = [
    'ship to',
    'shipping to',
    'do you ship',
    'offer international',
    'international shipping',
    'internationally',
    'deliver to',
    'deliver within',
    'only deliver',
    'outside the uk',
    'outside uk',
    'europe',
    'eu shipping',
    'worldwide',
    'only uk',
    'uk only',
    'within your country',
    'within the uk',
    'ship internationally',
    'shipping outside'
  ];
  for (var i = 0; i < hints.length; i++) {
    if (blob.indexOf(hints[i]) !== -1) return true;
  }
  if (blob.indexOf('international') !== -1 && (blob.indexOf('ship') !== -1 || blob.indexOf('deliver') !== -1)) {
    return true;
  }
  return false;
}

function isInboxConfirmQuestion_(subject, body) {
  if (isOwnerEscalationAsk_(subject, body)) return false;
  var blob = ((subject || '') + ' ' + (body || '')).toLowerCase();
  var hints = [
    'right inbox',
    'correct inbox',
    'right email',
    'correct email',
    'is this the store',
    'emailing the store',
    'right contact',
    'correct contact',
    'store email',
    'official email'
  ];
  for (var i = 0; i < hints.length; i++) {
    if (blob.indexOf(hints[i]) !== -1) return true;
  }
  // "is this the store owner contact?" without speak/connect → inbox confirm
  if (
    blob.indexOf('store owner') !== -1 &&
    (blob.indexOf('contact') !== -1 || blob.indexOf('email') !== -1 || blob.indexOf('inbox') !== -1) &&
    blob.indexOf('speak') === -1 &&
    blob.indexOf('talk') === -1 &&
    blob.indexOf('connect') === -1
  ) {
    return true;
  }
  return false;
}

function isOfficialWebsiteQuestion_(subject, body) {
  var blob = ((subject || '') + ' ' + (body || '')).toLowerCase();
  var asksWebsite =
    blob.indexOf('official website') !== -1 ||
    blob.indexOf('official site') !== -1 ||
    blob.indexOf('your website') !== -1 ||
    blob.indexOf('official web') !== -1;
  var mentionsOurs = blob.indexOf('ourtechaccessories.com') !== -1;
  if (asksWebsite) return true;
  if (mentionsOurs && (blob.indexOf('official') !== -1 || blob.indexOf('is this') !== -1)) {
    return true;
  }
  return false;
}

function defaultInboxConfirmReply_() {
  var hello = helloFrom_();
  return (
    'Hi,\n\n' +
    "Yes, you're in the right place. This is the customer email for Our Tech Accessories " +
    '(ourtechaccessories.com).\n\n' +
    'If you have an order or product question, reply with the details (and your order number if you have one) and we will help.\n\n' +
    'Our Tech Accessories\n' +
    hello +
    '\n'
  );
}

function defaultOfficialWebsiteReply_() {
  var hello = helloFrom_();
  return (
    'Hi,\n\n' +
    'Yes. ourtechaccessories.com is our official website.\n\n' +
    'If you have an order or product question, reply with the details (and your order number if you have one) and we will help.\n\n' +
    'Our Tech Accessories\n' +
    hello +
    '\n'
  );
}

/** Strip em dashes and a few common AI tells from outbound customer copy. */
function sanitizeCustomerReply_(text) {
  var t = String(text || '');
  t = t.replace(/\u2014/g, '. ').replace(/\u2013/g, '-'); // em / en dash
  t = t.replace(/\s+\.\s+\./g, '. ');
  t = t.replace(/I hope this (email )?finds you well\.?\s*/gi, '');
  t = t.replace(/I('d| would) be happy to (help|assist)( you)?\.?\s*/gi, '');
  t = t.replace(/Don('t|’t) hesitate to (reach out|get in touch|reply)\.?\s*/gi, '');
  t = t.replace(/\b(Certainly|Absolutely)[!.,]?\s*/gi, '');
  t = t.replace(/\bPlease note that\b/gi, '');
  t = t.replace(/\brest assured\b/gi, '');
  t = t.replace(/\b(Furthermore|Additionally|Moreover),?\s*/gi, '');
  t = t.replace(/[ \t]{2,}/g, ' ');
  t = t.replace(/\n{3,}/g, '\n\n');
  return t.trim() + (/\n$/.test(text) ? '\n' : '');
}

function sendDecline_(thread, msg) {
  var hello = helloFrom_();
  var decline = sanitizeCustomerReply_(
    'Hi,\n\n' +
      "Thanks for getting in touch. We're not looking for marketing, SEO, partnership, or agency services.\n\n" +
      "If you're a customer with an order or product question, reply with your order number (or the product link) and we'll help.\n\n" +
      'Our Tech Accessories\n' +
      hello +
      '\n'
  );
  safeThreadReply_(thread, decline, { from: hello });
}

function escalate_(thread, msg, result) {
  var escalateTo = props_().getProperty('ESCALATE_TO');
  if (!escalateTo) {
    Logger.log('ESCALATE_TO not set — leaving in inbox only');
    return;
  }
  var hello = helloFrom_();
  var subject = '[Our Tech] ' + (result.label || 'UNCLEAR') + ': ' + (msg.getSubject() || '(no subject)');
  var body =
    'Inbox bot escalated a message.\n\n' +
    'Label: ' +
    (result.label || '') +
    '\n' +
    'Reason: ' +
    (result.reason || '') +
    '\n' +
    'Confidence: ' +
    (result.confidence || '') +
    '\n\n' +
    'From: ' +
    msg.getFrom() +
    '\n' +
    'Subject: ' +
    msg.getSubject() +
    '\n' +
    'Date: ' +
    msg.getDate() +
    '\n\n' +
    '--- excerpt ---\n' +
    String(msg.getPlainBody() || '').slice(0, 2500) +
    '\n\nReply in the store Gmail thread, using From: ' +
    hello +
    '.\n';

  safeSendEmail_(escalateTo, subject, body, { from: hello, name: 'Our Tech Inbox Bot' });
}

function geminiJson_(apiKey, prompt) {
  var text = geminiText_(apiKey, prompt);
  text = text.replace(/```json|```/g, '').trim();
  return JSON.parse(text);
}

function geminiModel_() {
  return props_().getProperty('GEMINI_MODEL') || DEFAULT_GEMINI_MODEL;
}

function geminiText_(apiKey, prompt) {
  var model = geminiModel_();
  var url =
    'https://generativelanguage.googleapis.com/v1beta/models/' +
    encodeURIComponent(model) +
    ':generateContent?key=' +
    encodeURIComponent(apiKey);
  var payload = {
    contents: [{ role: 'user', parts: [{ text: prompt }] }],
    generationConfig: {
      temperature: 0.2,
      maxOutputTokens: 800,
      // Keep FAQ/classify cheap — 2.5 Flash thinks by default
      thinkingConfig: { thinkingBudget: 0 }
    }
  };
  var resp = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });
  var code = resp.getResponseCode();
  var raw = resp.getContentText();
  if (code >= 300) throw new Error('Gemini HTTP ' + code + ': ' + raw.slice(0, 300));

  var data = JSON.parse(raw);
  var parts = (((data.candidates || [])[0] || {}).content || {}).parts || [];
  return (parts[0] && parts[0].text) || '';
}

function storeFaq_() {
  return props_().getProperty('STORE_FAQ') || DEFAULT_STORE_FAQ;
}

function isTransactionalSender_(from, subject) {
  var f = (from || '').toLowerCase();
  var s = (subject || '').toLowerCase();
  var domains = [
    'shopify.com',
    'mail.shopify.com',
    'stripe.com',
    'paypal.com',
    'google.com',
    'accounts.google.com',
    'github.com',
    'facebookmail.com',
    'meta.com',
    'cjdropshipping.com',
    'judge.me',
    'improvmx.com'
  ];
  for (var i = 0; i < domains.length; i++) {
    if (f.indexOf(domains[i]) !== -1) return true;
  }
  if (s.indexOf('verification code') !== -1) return true;
  if (s.indexOf('security alert') !== -1) return true;
  return false;
}

function isFromUs_(from) {
  var f = (from || '').toLowerCase();
  var hello = helloFrom_().toLowerCase();
  var mailbox = (props_().getProperty('MAILBOX_ALIAS') || '').toLowerCase();
  var active = '';
  try {
    active = String(Session.getActiveUser().getEmail() || '').toLowerCase();
  } catch (e) {
    /* ignore */
  }
  return (
    f.indexOf(hello) !== -1 ||
    (mailbox && f.indexOf(mailbox) !== -1) ||
    f.indexOf('our.tech.accessories@gmail.com') !== -1 ||
    (active && f.indexOf(active) !== -1)
  );
}

function helloFrom_() {
  return props_().getProperty('HELLO_FROM') || 'hello@ourtechaccessories.com';
}

function props_() {
  return PropertiesService.getScriptProperties();
}

function ensureLabels_() {
  [
    LABEL_PITCH,
    LABEL_CUSTOMER,
    LABEL_UNCLEAR,
    LABEL_FAQ,
    LABEL_DONE,
    LABEL_DEAD,
    LABEL_DEAL,
    LABEL_CLOSE,
    LABEL_RESCUED,
    LABEL_OWNER_ASK
  ].forEach(function (name) {
    getLabel_(name);
  });
}

function getLabel_(name) {
  var label = GmailApp.getUserLabelByName(name);
  if (!label) label = GmailApp.createLabel(name);
  return label;
}

/**
 * Gmail search terms for nested labels.
 * UI name is "inbox-bot/faq" but search uses "label:inbox-bot-faq"
 * (slash → hyphen). Using "/" breaks -label: exclusions too.
 */
function gmailLabelTerm_(name) {
  return 'label:' + String(name || '').replace(/\//g, '-');
}

function hasLabel_(thread, name) {
  var labels = thread.getLabels();
  for (var i = 0; i < labels.length; i++) {
    if (labels[i].getName() === name) return true;
  }
  return false;
}

/** --- Closed-thread deal follow-up --- */

function dealFollowUpEnabled_() {
  return String(props_().getProperty('DEAL_FOLLOWUP_ENABLED') || 'false').toLowerCase() === 'true';
}

/**
 * Hourly: quiet FAQ/customer threads (and pitch declines that never got a deal) → one deal mail.
 * Uses Label.getThreads() — Gmail search for nested labels (slash or hyphen) is unreliable.
 */
function dealFollowUpSweep() {
  EMAILS_SENT_THIS_RUN_ = 0;
  if (!dealFollowUpEnabled_()) {
    Logger.log('dealFollowUpSweep: DEAL_FOLLOWUP_ENABLED is not true — skip');
    return;
  }
  if (!canSendEmail_(1)) {
    Logger.log(
      'dealFollowUpSweep aborted: email quota low remaining=' + emailQuotaRemaining_()
    );
    return;
  }
  ensureLabels_();
  var dry = String(props_().getProperty('DRY_RUN') || 'false').toLowerCase() === 'true';
  var hours = dealIdleHours_();
  var idleMs = hours * 60 * 60 * 1000;
  var maxAgeMs = 21 * 24 * 60 * 60 * 1000;
  var now = Date.now();
  var maxSends = Number(props_().getProperty('EMAIL_PER_RUN_MAX') || '5');
  if (!(maxSends > 0)) maxSends = 5;

  var threads = collectDealSweepThreads_(50);
  Logger.log(
    'dealFollowUpSweep: pool=' +
      threads.length +
      ' idleHours=' +
      hours +
      ' dry=' +
      dry
  );

  var sent = 0;
  var skipped = 0;
  for (var i = 0; i < threads.length; i++) {
    if (sent >= maxSends || !canSendEmail_(1)) {
      Logger.log('dealFollowUpSweep: stop early (quota/run max)');
      break;
    }
    var thread = threads[i];
    var why = dealSweepSkipReason_(thread, now, idleMs, maxAgeMs);
    if (why) {
      skipped++;
      Logger.log('dealFollowUpSweep skip thread=' + thread.getId() + ' reason=' + why);
      continue;
    }
    var isPitch = hasLabel_(thread, LABEL_PITCH);
    if (dry) {
      Logger.log(
        'DRY_RUN idle deal candidate thread=' +
          thread.getId() +
          ' pitch=' +
          isPitch +
          ' faq=' +
          hasLabel_(thread, LABEL_FAQ) +
          ' customer=' +
          hasLabel_(thread, LABEL_CUSTOMER)
      );
      continue;
    }
    var messages = thread.getMessages();
    var last = messages[messages.length - 1];
    var reason = isPitch ? 'pitch' : 'idle';
    try {
      if (maybeSendDealFollowUp_(thread, last, reason)) sent++;
      else {
        skipped++;
        Logger.log('dealFollowUpSweep send-failed/skipped thread=' + thread.getId());
      }
    } catch (e) {
      skipped++;
      Logger.log('dealFollowUpSweep error thread=' + thread.getId() + ' ' + e);
      if (String(e).indexOf('EmailQuota') !== -1) break;
    }
  }
  Logger.log('dealFollowUpSweep done sent=' + sent + ' skipped=' + skipped);
}

/** Manual: log every FAQ/customer/pitch thread and why it would/wouldn't get a deal. */
function dealFollowUpDebug() {
  ensureLabels_();
  var hours = dealIdleHours_();
  var idleMs = hours * 60 * 60 * 1000;
  var maxAgeMs = 21 * 24 * 60 * 60 * 1000;
  var now = Date.now();
  Logger.log(
    'dealFollowUpDebug enabled=' +
      dealFollowUpEnabled_() +
      ' idleHours=' +
      hours +
      ' dry=' +
      String(props_().getProperty('DRY_RUN') || 'false')
  );
  var threads = collectDealSweepThreads_(50);
  Logger.log('dealFollowUpDebug pool=' + threads.length);
  threads.forEach(function (thread) {
    var why = dealSweepSkipReason_(thread, now, idleMs, maxAgeMs);
    var msgs = thread.getMessages();
    var last = msgs.length ? msgs[msgs.length - 1] : null;
    Logger.log(
      'thread=' +
        thread.getId() +
        ' faq=' +
        hasLabel_(thread, LABEL_FAQ) +
        ' customer=' +
        hasLabel_(thread, LABEL_CUSTOMER) +
        ' pitch=' +
        hasLabel_(thread, LABEL_PITCH) +
        ' deal=' +
        dealAlreadySent_(thread) +
        ' dead=' +
        isDead_(thread) +
        ' lastFrom=' +
        (last ? last.getFrom() : '') +
        ' lastAgeH=' +
        (last ? ((now - last.getDate().getTime()) / 3600000).toFixed(1) : 'n/a') +
        ' → ' +
        (why || 'WOULD_SEND')
    );
  });
}

function dealIdleHours_() {
  var raw = props_().getProperty('DEAL_FOLLOWUP_IDLE_HOURS');
  if (raw === null || raw === '') return 24;
  var hours = Number(raw);
  // Allow 0 = send on next sweep once we replied last (no quiet wait).
  if (isNaN(hours) || hours < 0) return 24;
  return hours;
}

/**
 * Prefer Label.getThreads over Gmail search — nested names like inbox-bot/faq
 * often return 0 hits via label: queries.
 */
function collectDealSweepThreads_(maxPerLabel) {
  var n = maxPerLabel || 50;
  var seen = {};
  var out = [];
  [LABEL_FAQ, LABEL_CUSTOMER, LABEL_PITCH].forEach(function (name) {
    var label = GmailApp.getUserLabelByName(name);
    if (!label) {
      Logger.log('collectDealSweepThreads_: no label ' + name);
      return;
    }
    var threads = label.getThreads(0, n);
    Logger.log('collectDealSweepThreads_: ' + name + ' → ' + threads.length);
    threads.forEach(function (thread) {
      var id = thread.getId();
      if (seen[id]) return;
      seen[id] = true;
      out.push(thread);
    });
  });
  return out;
}

/** @return {string|null} skip reason, or null if eligible */
function dealSweepSkipReason_(thread, now, idleMs, maxAgeMs) {
  var messages = thread.getMessages();
  if (!messages.length) return 'empty';
  var last = messages[messages.length - 1];
  var age = now - last.getDate().getTime();
  if (age > maxAgeMs) return 'older_than_21d';
  if (!isFromUs_(last.getFrom())) return 'last_not_from_us:' + last.getFrom();
  var isPitch = hasLabel_(thread, LABEL_PITCH);
  if (!isPitch && age < idleMs) {
    return 'idle_wait_' + (idleMs / 3600000) + 'h (age=' + (age / 3600000).toFixed(1) + 'h)';
  }
  if (isDead_(thread) && !isPitch) return 'dead';
  if (dealAlreadySent_(thread)) return 'already_dealt';
  if (!hasLabel_(thread, LABEL_FAQ) && !hasLabel_(thread, LABEL_CUSTOMER) && !isPitch) {
    return 'no_faq_customer_pitch_label';
  }
  return null;
}

function isClosingThanks_(subject, body) {
  var raw = String(body || '');
  raw = raw.replace(/sent from .*$/gim, '');
  raw = raw.replace(/get outlook for .*$/gim, '');
  var text = (String(subject || '') + ' ' + raw).toLowerCase().replace(/\s+/g, ' ').trim();
  if (!text) return false;

  // Still a real question → not closing
  if (
    text.indexOf('?') !== -1 &&
    (text.indexOf('order') !== -1 ||
      text.indexOf('ship') !== -1 ||
      text.indexOf('refund') !== -1 ||
      text.indexOf('track') !== -1 ||
      text.indexOf('return') !== -1)
  ) {
    return false;
  }

  var hints = [
    'thank you',
    'thanks',
    'thx',
    'cheers',
    'much appreciated',
    'all good',
    'all set',
    "that's all",
    'thats all',
    'that helps',
    "that's helpful",
    'perfect',
    'sorted',
    'no further questions',
    'that answers',
    'great help'
  ];
  var hit = false;
  for (var i = 0; i < hints.length; i++) {
    if (text.indexOf(hints[i]) !== -1) {
      hit = true;
      break;
    }
  }
  if (!hit) return false;

  var compact = text.replace(/[^a-z0-9\s']/g, ' ').replace(/\s+/g, ' ').trim();
  var words = compact.split(' ').filter(function (w) {
    return w.length;
  });
  return words.length <= 40;
}

function engagedForDeal_(thread) {
  return (
    hasLabel_(thread, LABEL_FAQ) ||
    hasLabel_(thread, LABEL_CUSTOMER) ||
    hasLabel_(thread, LABEL_UNCLEAR) ||
    thread.getMessageCount() >= 3
  );
}

function maybeSendDealFollowUp_(thread, msg, reason) {
  // One deal per thread forever — claim under lock *before* send.
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(15000);
  } catch (e) {
    Logger.log('Deal follow-up lock timeout: ' + e);
    return false;
  }
  try {
    return maybeSendDealFollowUpUnlocked_(thread, msg, reason);
  } finally {
    lock.releaseLock();
  }
}

/**
 * Deal send without acquiring LockService (caller must already hold the script lock,
 * e.g. triageThreadLocked_). Sweep should call maybeSendDealFollowUp_ instead.
 */
function maybeSendDealFollowUpUnlocked_(thread, msg, reason) {
  if (!dealFollowUpEnabled_()) return false;
  if (dealAlreadySent_(thread)) return false;
  if (threadLooksLikeDealAlreadySent_(thread)) {
    markDealSent_(thread, reason);
    Logger.log('Deal already present in thread history — claimed, skip send: ' + thread.getId());
    return false;
  }
  // Pitch declines are marked dead on purpose; still allow pitch/idle deal send.
  if (isDead_(thread) && !(hasLabel_(thread, LABEL_PITCH) && (reason === 'pitch' || reason === 'idle'))) {
    return false;
  }
  // Pitch threads only get a deal when reason is pitch (or idle retry after decline).
  if (hasLabel_(thread, LABEL_PITCH) && reason !== 'pitch' && reason !== 'idle') return false;
  if (
    !engagedForDeal_(thread) &&
    reason !== 'idle' &&
    reason !== 'pitch' &&
    reason !== 'discount'
  ) {
    Logger.log('Skip deal follow-up (not engaged): ' + thread.getId());
    return false;
  }

  if (!canSendEmail_(1)) {
    Logger.log('Deal follow-up deferred — email quota low');
    return false;
  }
  var sendReason = hasLabel_(thread, LABEL_PITCH) ? 'pitch' : reason;
  markDealSent_(thread, sendReason);
  try {
    sendDealFollowUp_(thread, msg, sendReason);
    return true;
  } catch (e) {
    Logger.log('Deal follow-up failed — clearing claim for retry: ' + e);
    clearDealSent_(thread);
    if (String(e).indexOf('EmailQuota') !== -1) throw e;
    return false;
  }
}

function dealSentPropKey_(thread) {
  return 'dealSent:' + thread.getId();
}

/** True if this Gmail thread already got a deal (label and/or Script Property). */
function dealAlreadySent_(thread) {
  if (hasLabel_(thread, LABEL_DEAL)) {
    // Keep prop in sync so label removal alone cannot unlock a second send.
    props_().setProperty(dealSentPropKey_(thread), '1');
    return true;
  }
  if (props_().getProperty(dealSentPropKey_(thread)) === '1') {
    thread.addLabel(getLabel_(LABEL_DEAL));
    Logger.log('Healed missing ' + LABEL_DEAL + ' on thread ' + thread.getId());
    return true;
  }
  return false;
}

/** Heuristic: prior outbound already contains the volume-deal creative. */
function threadLooksLikeDealAlreadySent_(thread) {
  var messages = thread.getMessages();
  var start = Math.max(0, messages.length - 8);
  for (var i = start; i < messages.length; i++) {
    var m = messages[i];
    if (!isFromUs_(m.getFrom())) continue;
    var blob = (
      String(m.getPlainBody() || '') +
      ' ' +
      String(m.getBody() || '')
    ).toLowerCase();
    if (blob.indexOf('buy more, save more') !== -1) return true;
    if (blob.indexOf('buy-more-save-more') !== -1) return true;
    if (
      blob.indexOf('4 or more') !== -1 &&
      blob.indexOf('25%') !== -1 &&
      blob.indexOf('gan') !== -1
    ) {
      return true;
    }
    if (blob.indexOf('120w gan charger with retractable') !== -1) return true;
  }
  return false;
}

function markDealSent_(thread, reason) {
  thread.addLabel(getLabel_(LABEL_DEAL));
  // Discount asks are still an active shopper thread — don't mark closed.
  if (String(reason || '') !== 'discount') {
    thread.addLabel(getLabel_(LABEL_CLOSE));
  }
  props_().setProperty(dealSentPropKey_(thread), '1');
}

function sendDealFollowUp_(thread, msg, reason) {
  var hello = helloFrom_();
  var name = guessFirstName_(msg.getFrom());
  var mail = buildDealMail_(name, reason);
  var opts = mail.options;

  // Prefer From hello@ when Send-as works; fall back to replyTo.
  try {
    opts.from = hello;
    safeThreadReply_(thread, mail.plain, opts);
  } catch (e) {
    if (String(e).indexOf('EmailQuota') !== -1) throw e;
    Logger.log('Deal follow-up from: failed (' + e + '); retry with replyTo');
    delete opts.from;
    opts.replyTo = hello;
    safeThreadReply_(thread, mail.plain, opts);
  }

  // Keep discount replies visible in inbox; archive closed/pitch/idle deals.
  if (String(reason || '') !== 'discount') {
    thread.moveToArchive();
  }
  Logger.log(
    'Deal follow-up sent (' +
      reason +
      ') thread=' +
      thread.getId() +
      ' subject=' +
      mail.subject
  );
}

/**
 * Manual test: sends one deal email (not a thread reply).
 * Run while signed into our.tech.accessories@gmail.com.
 * Optional props: DEAL_TEST_TO, DEAL_TEST_NAME, DEAL_TEST_REASON (close|pitch|idle).
 */
function sendDealFollowUpTest() {
  assertStoreMailboxForDeal_();
  var to = props_().getProperty('DEAL_TEST_TO') || 'J.Malachy.miller@gmail.com';
  var name = props_().getProperty('DEAL_TEST_NAME') || 'James';
  var reason = props_().getProperty('DEAL_TEST_REASON') || 'close';
  var mail = buildDealMail_(name, reason);
  var hello = helloFrom_();
  var opts = mail.options;
  opts.replyTo = hello;
  try {
    opts.from = hello;
    GmailApp.sendEmail(to, mail.subject, mail.plain, opts);
  } catch (e) {
    Logger.log('Test from: failed (' + e + '); retry with replyTo only');
    delete opts.from;
    GmailApp.sendEmail(to, mail.subject, mail.plain, opts);
  }
  Logger.log('TEST deal follow-up SENT to ' + to + ' reason=' + reason);
}

function buildDealMail_(name, reason) {
  var copy = dealFollowUpCopy_(reason);
  var vars = {
    NAME: name || '',
    NAME_SUFFIX: name ? ' ' + name : '',
    INTRO: copy.intro,
    BRIDGE: copy.bridge
  };
  var subject =
    props_().getProperty('DEAL_SUBJECT') ||
    'One more thing from Our Tech Accessories';
  var plain = sanitizeCustomerReply_(applyDealTokens_(loadDealPlain_(), vars));
  var html = applyDealTokens_(loadDealHtml_(), vars);
  return {
    subject: subject,
    plain: plain,
    options: {
      htmlBody: html,
      name: props_().getProperty('FROM_NAME') || 'Our Tech Accessories'
    }
  };
}

function assertStoreMailboxForDeal_() {
  var expected = (
    props_().getProperty('EXPECTED_MAILBOX') ||
    'our.tech.accessories@gmail.com'
  ).toLowerCase();
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
      'Refusing test send. Running as "' +
        (who || '(unknown)') +
        '" but expected "' +
        expected +
        '". Sign into the store Gmail at script.google.com.'
    );
  }
  Logger.log('OK: running as ' + who);
}

/** Opening copy by trigger — keep UK, short, no em dashes. */
function dealFollowUpCopy_(reason) {
  var r = String(reason || '').toLowerCase();
  var bridge =
    props_().getProperty('DEAL_BRIDGE') ||
    'Our 120W GaN charger with the built-in retractable USB-C cable has a buy-more-save-more offer right now.';
  var intro;
  if (r === 'pitch') {
    intro =
      props_().getProperty('DEAL_INTRO_PITCH') ||
      "We're not looking for marketing, SEO, partnership, or agency services. " +
        'If you shop tech accessories yourself though, here is a current deal from our store.';
  } else if (r === 'idle') {
    intro =
      props_().getProperty('DEAL_INTRO_IDLE') ||
      'Just a quick follow-up from Our Tech Accessories. Here is a current deal from the shop in case it is useful.';
  } else if (r === 'discount') {
    intro =
      props_().getProperty('DEAL_INTRO_DISCOUNT') ||
      'Site prices are the normal single-item prices. We do not usually discount one-off, ' +
        'but we do have a current volume deal if you want more than one charger.';
  } else {
    // close (default)
    intro =
      props_().getProperty('DEAL_INTRO_CLOSE') ||
      'Thanks again for getting in touch. While this thread is wrapping up, here is a current deal from the shop in case it is useful.';
  }
  return { intro: intro, bridge: bridge };
}

function applyDealTokens_(text, vars) {
  var out = String(text || '');
  Object.keys(vars || {}).forEach(function (k) {
    out = out.split('{{' + k + '}}').join(String(vars[k]));
  });
  return out;
}

function guessFirstName_(from) {
  var s = String(from || '').trim();
  var m = s.match(/^"?([^"<]+)"?\s*</);
  if (m) {
    var first = m[1].trim().split(/\s+/)[0];
    if (first && first.indexOf('@') === -1 && /^[A-Za-z]/.test(first)) {
      return first.charAt(0).toUpperCase() + first.slice(1);
    }
  }
  return '';
}

function loadDealPlain_() {
  var inline = props_().getProperty('DEAL_PLAIN');
  if (inline) return inline;
  var driveId = props_().getProperty('DEAL_PLAIN_DRIVE_ID');
  if (driveId) return DriveApp.getFileById(driveId).getBlob().getDataAsString();
  try {
    return fetchDealBodies_().plain;
  } catch (e) {
    Logger.log('Deal plain from website failed: ' + e);
  }
  if (typeof defaultDealPlain_ === 'function') return defaultDealPlain_();
  throw new Error('No deal plain body — set DEAL_BODIES_URL or paste DealFollowupBodies.gs');
}

function loadDealHtml_() {
  var inline = props_().getProperty('DEAL_HTML');
  if (inline) return inline;
  var driveId = props_().getProperty('DEAL_HTML_DRIVE_ID');
  if (driveId) return DriveApp.getFileById(driveId).getBlob().getDataAsString();
  try {
    return fetchDealBodies_().html;
  } catch (e) {
    Logger.log('Deal HTML from website failed: ' + e);
  }
  if (typeof defaultDealHtml_ === 'function') return defaultDealHtml_();
  throw new Error('No deal HTML body — set DEAL_BODIES_URL or paste DealFollowupBodies.gs');
}

/**
 * GET DEAL_BODIES_URL (default /pages/inbox-deal) → { html, plain, version }.
 * Cached 10 minutes in ScriptCache.
 */
function fetchDealBodies_() {
  var cache = CacheService.getScriptCache();
  var cached = cache.get('dealBodiesJson');
  if (cached) {
    try {
      return JSON.parse(cached);
    } catch (e) {
      /* refetch */
    }
  }
  var url =
    props_().getProperty('DEAL_BODIES_URL') ||
    'https://ourtechaccessories.com/pages/inbox-deal';
  var resp = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    followRedirects: true,
    headers: { Accept: 'application/json, text/plain, */*' }
  });
  var code = resp.getResponseCode();
  var text = String(resp.getContentText() || '').trim();
  if (code < 200 || code >= 300) {
    throw new Error('DEAL_BODIES_URL HTTP ' + code + ' body=' + text.slice(0, 200));
  }
  if (text.charAt(0) !== '{') {
    var m = text.match(/\{[\s\S]*"html"[\s\S]*\}/);
    if (m) text = m[0];
  }
  var data = JSON.parse(text);
  if (!data || !data.html || !data.plain) {
    throw new Error('DEAL_BODIES_URL JSON missing html/plain');
  }
  try {
    cache.put('dealBodiesJson', JSON.stringify(data), 600);
  } catch (e2) {
    /* cache optional */
  }
  Logger.log('Fetched deal bodies version=' + (data.version || '') + ' from ' + url);
  return data;
}

/** Manual: clear cached deal JSON + fetch once (log version). */
function refreshDealBodiesCache() {
  CacheService.getScriptCache().remove('dealBodiesJson');
  var data = fetchDealBodies_();
  Logger.log(
    'Deal bodies refreshed version=' +
      (data.version || '') +
      ' htmlChars=' +
      String(data.html).length +
      ' plainChars=' +
      String(data.plain).length
  );
}
