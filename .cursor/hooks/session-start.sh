#!/usr/bin/env bash
# Cursor sessionStart — mirror Claude Code's SessionStart hooks:
#   1) sync skills into .cursor/skills (and .claude/skills)
#   2) run the context banner and inject it as additional_context
#
# Stdout must be valid JSON only. Banner / sync chatter is captured into the
# JSON payload so Cursor does not reject the hook output.
set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 0

# Cursor sends hook input JSON on stdin and closes it. Never block on a TTY
# (manual runs / debugging), or the agent session will hang.
if [[ -t 0 ]]; then
  :
else
  cat >/dev/null || true
fi

tmp="$(mktemp -t arcads-cursor-session.XXXXXX)"
trap 'rm -f "$tmp"' EXIT

{
  # Skip upstream git fetch in check-context during Cursor startup — it can
  # hang on SSH/network and sessionStart is fire-and-forget with a timeout.
  export ARCADS_SKIP_UPSTREAM_CHECK=1
  bash "$ROOT/scripts/sync-skill.sh" 2>&1 || true
  bash "$ROOT/shared/scripts/check-context.sh" 2>&1 || true
} >"$tmp"

if command -v python3 >/dev/null 2>&1; then
  python3 - "$tmp" <<'PY'
import json, sys
path = sys.argv[1]
try:
    text = open(path, encoding="utf-8", errors="replace").read().strip()
except OSError:
    text = ""
if not text:
    text = (
        "Arcads skill pack (Cursor): session sync ran. "
        "Read MASTER_CONTEXT.md and .cursor/skills/*/SKILL.md before generating."
    )
print(json.dumps({"additional_context": text}))
PY
else
  body="$(tr -d '\000-\010\013\014\016-\037' <"$tmp" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk '{printf "%s\\n", $0}')"
  printf '{"additional_context":"%s"}\n' "$body"
fi

exit 0
