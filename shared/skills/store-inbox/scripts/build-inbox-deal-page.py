#!/usr/bin/env python3
"""Build Shopify page.inbox-deal.liquid from deal-followup.{html,txt}."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "shared/skills/store-inbox/apps-script/templates"
HTML = (SRC / "deal-followup.html").read_text(encoding="utf-8")
PLAIN = (SRC / "deal-followup.txt").read_text(encoding="utf-8")
if not HTML.endswith("\n"):
    HTML += "\n"
if not PLAIN.endswith("\n"):
    PLAIN += "\n"

VERSION = "gan-volume-2026-07-29"

LIQUID = (
    "{% comment %}\n"
    "  Inbox bot deal bodies endpoint.\n"
    "  URL: /pages/inbox-deal\n"
    "  Returns JSON: html + plain + version (email tokens stay literal inside raw).\n"
    "  Source: apps-script/templates/deal-followup.{html,txt}\n"
    "  Regenerate: python3 shared/skills/store-inbox/scripts/build-inbox-deal-page.py\n"
    "{% endcomment %}\n"
    "{% layout none %}\n"
    "{% capture deal_html %}{% raw %}\n"
    + HTML
    + "{% endraw %}{% endcapture %}\n"
    "{% capture deal_plain %}{% raw %}\n"
    + PLAIN
    + "{% endraw %}{% endcapture %}\n"
    f'{{% assign deal_version = "{VERSION}" %}}\n'
    "{\n"
    '  "version": {{ deal_version | json }},\n'
    '  "html": {{ deal_html | strip | json }},\n'
    '  "plain": {{ deal_plain | strip | json }}\n'
    "}\n"
)

OUTS = [
    SRC / "page.inbox-deal.liquid",
    ROOT / "outputs/shopify/theme-inbox-deal/templates/page.inbox-deal.liquid",
]


def main() -> None:
    assert "{{NAME_SUFFIX}}" in LIQUID
    assert "{% raw %}" in LIQUID
    for path in OUTS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(LIQUID, encoding="utf-8")
        print(f"Wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
