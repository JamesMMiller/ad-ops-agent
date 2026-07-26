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
 */

var DEFAULT_GEMINI_MODEL = 'gemini-2.5-flash';

var LABEL_PITCH = 'inbox-bot/pitch';
var LABEL_CUSTOMER = 'inbox-bot/customer';
var LABEL_UNCLEAR = 'inbox-bot/unclear';
var LABEL_FAQ = 'inbox-bot/faq';
var LABEL_DONE = 'inbox-bot/processed';
var LABEL_DEAD = 'inbox-bot/dead';

/** Default knowledge — keep in sync with prompting/store-faq.md */
var DEFAULT_STORE_FAQ =
  'Our Tech Accessories (UK Shopify store).\n' +
  'Contact: hello@ourtechaccessories.com\n' +
  'Shipping: UK only for now. We do not ship internationally yet.\n' +
  'Future: We plan to offer international shipping later. No confirmed date. Do not promise a month.\n' +
  'Delivery: Usually a few working days after dispatch within the UK; depends on product/carrier. Some PDPs say 3-7 working days for UK stock.\n' +
  'Never invent order status, tracking numbers, refunds, or returns decisions. Those need a human.\n' +
  'Tone: short UK English, calm, human. No em dashes. No corporate or chatbot filler.';

function installTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'triageRecent') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('triageRecent').timeBased().everyMinutes(5).create();
  ensureLabels_();
  Logger.log('Trigger installed: triageRecent every 5 minutes');
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

  if (label === 'PITCH') {
    thread.addLabel(getLabel_(LABEL_PITCH));
    if (!dry) {
      sendDecline_(thread, msg);
      thread.moveToArchive();
    }
    // Decline closes the thread for the bot
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
    'Return ONLY compact JSON: {"label":"PITCH|FAQ|CUSTOMER|UNCLEAR|TRANSACTIONAL|IGNORE|BOT","reason":"short","confidence":0.0}\n' +
    'PITCH = sales/SEO/agency/partnership/"we can stop your spam" cold outreach.\n' +
    'FAQ = general question answerable ONLY from this store knowledge (no order lookup needed):\n' +
    '---STORE KNOWLEDGE---\n' +
    faq +
    '\n---END---\n' +
    'Examples of FAQ: do you ship to my country, international shipping, UK only, delivery times in general, who are you / contact email.\n' +
    'CUSTOMER = order number, tracking, refund, return, damaged item, wrong colour, payment problem, or anything needing account/order data.\n' +
    'UNCLEAR = maybe customer or maybe FAQ but not safe to auto-answer. Escalate.\n' +
    'TRANSACTIONAL = receipts, Shopify, Google, banks, 2FA.\n' +
    'IGNORE = newsletters/bulk, or a short thanks/ok with no new question.\n' +
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

  var faqHints = [
    'ship to', 'shipping to', 'do you ship', 'international', 'deliver to',
    'outside the uk', 'outside uk', 'europe', 'eu shipping', 'worldwide',
    'only uk', 'uk only', 'how long does delivery', 'delivery time', 'postage'
  ];
  for (var f = 0; f < faqHints.length; f++) {
    if (blob.indexOf(faqHints[f]) !== -1) {
      return { label: 'FAQ', reason: 'faq keyword: ' + faqHints[f], confidence: 0.65 };
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

  return { label: 'UNCLEAR', reason: 'no strong signal', confidence: 0.4 };
}

function sendFaqReply_(thread, msg, from, subject, body, context) {
  var hello = helloFrom_();
  var replyBody = sanitizeCustomerReply_(draftFaqReply_(from, subject, body, context));
  thread.reply(replyBody, { from: hello });
}

function draftFaqReply_(from, subject, body, context) {
  var key = props_().getProperty('GEMINI_API_KEY');
  var faq = storeFaq_();
  if (key) {
    try {
      return geminiFaqReply_(key, faq, from, subject, body, context || '');
    } catch (e) {
      Logger.log('FAQ draft failed, template fallback: ' + e);
    }
  }
  return defaultFaqReply_();
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
  var hello = helloFrom_();
  return (
    'Hi,\n\n' +
    'Thanks for getting in touch. We currently ship to the United Kingdom only. ' +
    "International shipping isn't available yet, though we do plan to expand in the future " +
    '(no firm date yet).\n\n' +
    'UK delivery is usually a few working days after dispatch, depending on the product and carrier.\n\n' +
    'If you have an order question, reply with your order number and we will help.\n\n' +
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
  [LABEL_PITCH, LABEL_CUSTOMER, LABEL_UNCLEAR, LABEL_FAQ, LABEL_DONE, LABEL_DEAD].forEach(
    function (name) {
      getLabel_(name);
    }
  );
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
