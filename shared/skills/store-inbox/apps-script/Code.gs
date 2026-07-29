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
 *   DEAL_FOLLOWUP_IDLE_HOURS = hours after our last reply before idle deal (default 48)
 *   DEAL_SUBJECT / DEAL_HTML / DEAL_PLAIN / DEAL_*_DRIVE_ID — optional body overrides
 *
 * Also paste DealFollowupBodies.gs (default GaN deal HTML/plain) into the same project.
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

/** Default knowledge — keep in sync with prompting/store-faq.md */
var DEFAULT_STORE_FAQ =
  'Our Tech Accessories (UK Shopify store).\n' +
  'Contact: hello@ourtechaccessories.com is the official customer inbox for Our Tech Accessories (ourtechaccessories.com).\n' +
  'If asked "is this the right inbox / store email / store owner contact": confirm this is the store\'s customer email. ' +
  'Do not share personal name, personal email, phone, or home address. ' +
  'Do not role-play as a named owner; offer to help with orders or product questions.\n' +
  'Generic greetings / check-ins with no real question (hi, hello, are you there, anyone there): ' +
  'reply with the short customer-support intro. Confirm this is the store support email and ask them to reply with product or order details (order number if they have one).\n' +
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
  ensureLabels_();
  // Do NOT exclude inbox-bot/processed — follow-ups stay on the same thread.
  var threads = GmailApp.search('in:inbox newer_than:2d', 0, 30);
  threads.forEach(triageThread_);
}

/** Manual test from the script editor */
function triageOneTest() {
  ensureLabels_();
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

/**
 * Process a thread when the latest message is inbound and newer than our last handle.
 * Follow-ups on the same thread are supported (per-message watermark, not thread-done).
 * Dead only for: already declined pitches, or clearly automated/bot mail.
 */
function triageThread_(thread) {
  if (!needsTriage_(thread)) return;

  var messages = thread.getMessages();
  var msg = messages[messages.length - 1];
  var from = msg.getFrom();
  var subject = msg.getSubject() || '';
  var body = msg.getPlainBody() || msg.getBody() || '';
  body = String(body).replace(/\s+/g, ' ').slice(0, 6000);
  var dry = String(props_().getProperty('DRY_RUN') || 'false').toLowerCase() === 'true';

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

  if (label === 'BOT') {
    markDead_(thread, 'classifier: BOT (' + (result.reason || '') + ')');
    markThreadProcessed_(thread, msg);
    thread.addLabel(getLabel_(LABEL_DONE));
    if (!dry) thread.moveToArchive();
    return;
  }

  if (label === 'CLOSE' || (label === 'IGNORE' && isClosingThanks_(subject, body))) {
    thread.addLabel(getLabel_(LABEL_CLOSE));
    if (!dry && maybeSendDealFollowUp_(thread, msg, 'close')) {
      // deal sent
    } else if (!dry) {
      thread.moveToArchive();
    }
  } else if (label === 'PITCH') {
    thread.addLabel(getLabel_(LABEL_PITCH));
    if (!dry) {
      sendDecline_(thread, msg);
      maybeSendDealFollowUp_(thread, msg, 'pitch');
      thread.moveToArchive();
    }
    // Decline closes triage; deal (if enabled) already sent above
    markDead_(thread, 'pitch declined');
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
    // CUSTOMER or UNCLEAR
    thread.addLabel(getLabel_(label === 'CUSTOMER' ? LABEL_CUSTOMER : LABEL_UNCLEAR));
    if (!dry) escalate_(thread, msg, result);
  }

  markThreadProcessed_(thread, msg);
  thread.addLabel(getLabel_(LABEL_DONE));
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
    'Return ONLY compact JSON: {"label":"PITCH|FAQ|CUSTOMER|UNCLEAR|TRANSACTIONAL|IGNORE|CLOSE|BOT","reason":"short","confidence":0.0}\n' +
    'PITCH = sales/SEO/agency/partnership/"we can stop your spam" cold outreach.\n' +
    'FAQ = general question answerable ONLY from this store knowledge (no order lookup needed):\n' +
    '---STORE KNOWLEDGE---\n' +
    faq +
    '\n---END---\n' +
    'Examples of FAQ: do you ship to my country, international shipping, UK only, delivery times, ' +
    'free shipping / shipping fee, is this the right inbox, is this the store email, ' +
    'am I emailing the store / store owner contact, is this your official website, ' +
    'ourtechaccessories.com official site, who are you / contact email.\n' +
    'If the message is ONLY a greeting or check-in with no real question ' +
    '(hi, hello, hey, are you there, anyone there, just checking), choose FAQ. ' +
    'Reply with the customer-support intro (this is store support; ask for product/order details).\n' +
    'If the message ONLY asks whether this is the right store inbox/contact, choose FAQ and confirm hello@ is the store customer email.\n' +
    'If the message ONLY asks whether ourtechaccessories.com is the official website, choose FAQ and confirm yes.\n' +
    'If "right inbox / store owner / official website" is just an opener before SEO, partnership, agency, or marketing pitch, choose PITCH.\n' +
    'CUSTOMER = order number, tracking, refund, return, damaged item, wrong colour, payment problem, or anything needing account/order data.\n' +
    'UNCLEAR = maybe customer or maybe FAQ but not safe to auto-answer. Escalate. Do NOT use UNCLEAR for a bare greeting.\n' +
    'TRANSACTIONAL = receipts, Shopify, Google, banks, 2FA.\n' +
    'CLOSE = thread wrapping up: short thanks / cheers / all good / that helps / perfect / sorted, ' +
    'with no new question (prefer CLOSE over IGNORE when PRIOR CONTEXT shows we already helped).\n' +
    'IGNORE = newsletters/bulk, or a short ok with no thanks and no new question.\n' +
    'BOT = clearly an autoresponder, chatbot, or non-human loop (not a real shopper). Only when obvious.\n' +
    'This may be a follow-up in an existing thread. Use PRIOR CONTEXT when the latest message is short (e.g. "and Germany?").\n' +
    'When unsure between FAQ and CUSTOMER, choose CUSTOMER or UNCLEAR (never invent order facts).\n' +
    'When unsure between PITCH and CUSTOMER, choose UNCLEAR.\n' +
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

  var customerHints = [
    'order #', 'order number', 'tracking', 'refund', 'return', 'parcel',
    'damaged', 'wrong colour', 'wrong color', 'my package', 'where is my order',
    'missing item', 'cancel my'
  ];
  for (var i = 0; i < customerHints.length; i++) {
    if (blob.indexOf(customerHints[i]) !== -1) {
      return { label: 'CUSTOMER', reason: 'customer keyword: ' + customerHints[i], confidence: 0.7 };
    }
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
  if (hits >= 1) {
    return { label: 'PITCH', reason: 'pitch keywords x' + hits, confidence: 0.65 };
  }

  if (isGenericGreeting_(subject, body)) {
    return { label: 'FAQ', reason: 'generic greeting/check-in', confidence: 0.75 };
  }

  var faqHints = [
    'ship to', 'shipping to', 'do you ship', 'international', 'deliver to',
    'outside the uk', 'outside uk', 'europe', 'eu shipping', 'worldwide',
    'only uk', 'uk only', 'how long does delivery', 'delivery time', 'postage',
    'free shipping', 'shipping fee', 'shipping included',
    'right inbox', 'correct inbox', 'right email', 'correct email',
    'store owner', 'store\'s email', 'stores email', 'official email',
    'is this the store', 'emailing the store', 'right contact',
    'official website', 'official site', 'official web',
    'ourtechaccessories.com', 'is this your website', 'your website'
  ];
  for (var f = 0; f < faqHints.length; f++) {
    if (blob.indexOf(faqHints[f]) !== -1) {
      return { label: 'FAQ', reason: 'faq keyword: ' + faqHints[f], confidence: 0.65 };
    }
  }

  return { label: 'UNCLEAR', reason: 'no strong signal', confidence: 0.4 };
}

function sendFaqReply_(thread, msg, from, subject, body, context) {
  var hello = helloFrom_();
  var replyBody = sanitizeCustomerReply_(draftFaqReply_(from, subject, body, context));
  thread.reply(replyBody, { from: hello });
}

function draftFaqReply_(from, subject, body, context) {
  // Fixed copy for bare greetings (don't let the model improvise)
  if (isGenericGreeting_(subject, body)) {
    return defaultSupportIntroReply_();
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
  return defaultSupportIntroReply_();
}

function geminiFaqReply_(apiKey, faq, from, subject, body, context) {
  var prompt =
    'Write a short customer-support reply for Our Tech Accessories.\n' +
    'Use ONLY facts from STORE KNOWLEDGE. If the question needs order/tracking/refund data, reply asking them to reply with their order number and say a human will help.\n' +
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

function isGenericGreeting_(subject, body) {
  var raw = String(body || '');
  // Drop common mobile mail footers so short check-ins still match
  raw = raw.replace(/sent from .*$/gim, '');
  raw = raw.replace(/get outlook for .*$/gim, '');
  var text = (String(subject || '') + ' ' + raw).toLowerCase();
  text = text.replace(/\s+/g, ' ').trim();

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
    if (text.indexOf(greetHints[i]) !== -1) return true;
  }

  // Very short hello/hi/hey with little else
  var compact = text
    .replace(/[^a-z0-9\s?]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  var words = compact.split(' ').filter(function (w) {
    return w.length;
  });
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

function isInboxConfirmQuestion_(subject, body) {
  var blob = ((subject || '') + ' ' + (body || '')).toLowerCase();
  var hints = [
    'right inbox',
    'correct inbox',
    'right email',
    'correct email',
    'store owner',
    'is this the store',
    'emailing the store',
    'right contact'
  ];
  for (var i = 0; i < hints.length; i++) {
    if (blob.indexOf(hints[i]) !== -1) return true;
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
  thread.reply(decline, { from: hello });
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

  GmailApp.sendEmail(escalateTo, subject, body, { from: hello, name: 'Our Tech Inbox Bot' });
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
  return (
    f.indexOf(hello) !== -1 ||
    (mailbox && f.indexOf(mailbox) !== -1) ||
    f.indexOf('our.tech.accessories@gmail.com') !== -1
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
    LABEL_CLOSE
  ].forEach(function (name) {
    getLabel_(name);
  });
}

function getLabel_(name) {
  var label = GmailApp.getUserLabelByName(name);
  if (!label) label = GmailApp.createLabel(name);
  return label;
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
 * Hourly: FAQ/customer threads where we replied last and they went quiet → one deal mail.
 */
function dealFollowUpSweep() {
  if (!dealFollowUpEnabled_()) {
    Logger.log('dealFollowUpSweep: DEAL_FOLLOWUP_ENABLED is not true — skip');
    return;
  }
  ensureLabels_();
  var dry = String(props_().getProperty('DRY_RUN') || 'false').toLowerCase() === 'true';
  var hours = Number(props_().getProperty('DEAL_FOLLOWUP_IDLE_HOURS') || '48');
  if (!(hours > 0)) hours = 48;
  var idleMs = hours * 60 * 60 * 1000;
  var q =
    '(label:' +
    LABEL_FAQ +
    ' OR label:' +
    LABEL_CUSTOMER +
    ') -label:' +
    LABEL_DEAL +
    ' -label:' +
    LABEL_DEAD +
    ' -label:' +
    LABEL_PITCH +
    ' newer_than:21d';
  var threads = GmailApp.search(q, 0, 40);
  var now = Date.now();
  threads.forEach(function (thread) {
    var messages = thread.getMessages();
    if (!messages.length) return;
    var last = messages[messages.length - 1];
    if (!isFromUs_(last.getFrom())) return;
    if (now - last.getDate().getTime() < idleMs) return;
    if (dry) {
      Logger.log('DRY_RUN idle deal candidate thread=' + thread.getId());
      return;
    }
    maybeSendDealFollowUp_(thread, last, 'idle');
  });
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
  if (!dealFollowUpEnabled_()) return false;
  if (hasLabel_(thread, LABEL_DEAL)) return false;
  if (isDead_(thread)) return false;
  // Pitch threads only get a deal when reason is explicitly 'pitch'
  if (hasLabel_(thread, LABEL_PITCH) && reason !== 'pitch') return false;
  if (!engagedForDeal_(thread) && reason !== 'idle' && reason !== 'pitch') {
    Logger.log('Skip deal follow-up (not engaged): ' + thread.getId());
    return false;
  }
  try {
    sendDealFollowUp_(thread, msg, reason);
    return true;
  } catch (e) {
    Logger.log('Deal follow-up failed: ' + e);
    return false;
  }
}

function sendDealFollowUp_(thread, msg, reason) {
  var hello = helloFrom_();
  var name = guessFirstName_(msg.getFrom());
  var mail = buildDealMail_(name, reason);
  var opts = mail.options;

  // Prefer From hello@ when Send-as works; fall back to replyTo.
  try {
    opts.from = hello;
    thread.reply(mail.plain, opts);
  } catch (e) {
    Logger.log('Deal follow-up from: failed (' + e + '); retry with replyTo');
    delete opts.from;
    opts.replyTo = hello;
    thread.reply(mail.plain, opts);
  }

  thread.addLabel(getLabel_(LABEL_DEAL));
  thread.addLabel(getLabel_(LABEL_CLOSE));
  thread.moveToArchive();
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
  var driveId = props_().getProperty('DEAL_PLAIN_DRIVE_ID');
  if (driveId) return DriveApp.getFileById(driveId).getBlob().getDataAsString();
  var inline = props_().getProperty('DEAL_PLAIN');
  if (inline) return inline;
  if (typeof defaultDealPlain_ === 'function') return defaultDealPlain_();
  throw new Error('No deal plain body — paste DealFollowupBodies.gs or set DEAL_PLAIN');
}

function loadDealHtml_() {
  var driveId = props_().getProperty('DEAL_HTML_DRIVE_ID');
  if (driveId) return DriveApp.getFileById(driveId).getBlob().getDataAsString();
  var inline = props_().getProperty('DEAL_HTML');
  if (inline) return inline;
  if (typeof defaultDealHtml_ === 'function') return defaultDealHtml_();
  throw new Error('No deal HTML body — paste DealFollowupBodies.gs or set DEAL_HTML');
}
