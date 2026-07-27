/**
 * DEPRECATED — do not add campaign hardcoding here.
 *
 * Use the generic HTML mailer instead:
 *   shared/skills/google-apps-script/templates/HtmlMailer.gs
 *   shared/skills/google-apps-script/reference/html-mailer.md
 *
 * GaN follow-up bodies live in the repo (paste/upload; do not embed in .gs):
 *   outputs/shopify/2026-07-27-gan-volume-deal/follow-up-gan-deal.html
 *   outputs/shopify/2026-07-27-gan-volume-deal/follow-up-gan-deal.txt
 *
 * Set Script Properties (MAIL_TO, MAIL_SUBJECT, MAIL_HTML_DRIVE_ID, MAIL_VARS, …)
 * then run createMailDraft / sendMail from HtmlMailer.gs.
 */

function _deprecated_CreateGanDealDraft() {
  throw new Error(
    'CreateGanDealDraft.gs is retired. Paste HtmlMailer.gs from ' +
      'shared/skills/google-apps-script/templates/ and set Script Properties ' +
      '(see reference/html-mailer.md).'
  );
}
