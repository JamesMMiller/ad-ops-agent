#!/usr/bin/env bash
# Syncs canonical skills to .claude/skills and .cursor/skills, then rewrites
# relative links that break when skills move one directory deeper
# (skills/X → .cursor/skills/X).
#
# Canonical sources stay under skills/ and shared/skills/. Edit those, then
# re-run this script (or open a new Cursor agent session — sessionStart hooks it).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

bash "$ROOT/shared/scripts/sync-skill.sh" "$@"

# Destination copies live at .cursor/skills/<name>/ (or .claude/...), one level
# deeper than skills/<name>/. Markdown that pointed at ../../shared/... from the
# canonical path must become ../../../shared/... after the copy.
rewrite_shared_links() {
  local dest_root="$1"
  [[ -d "$dest_root" ]] || return 0
  # Only touch markdown; leave scripts alone.
  while IFS= read -r -d '' f; do
    # Skip if already rewritten (idempotent).
    if grep -q '](\.\./\.\./\.\./shared/' "$f" 2>/dev/null; then
      # Still rewrite any remaining ../../shared that were not yet updated.
      :
    fi
    if grep -q '](\.\./\.\./shared/' "$f" 2>/dev/null; then
      sed -i.bak 's|](\.\./\.\./shared/|](../../../shared/|g' "$f"
      rm -f "${f}.bak"
    fi
  done < <(find "$dest_root" -type f -name '*.md' -print0 2>/dev/null)
}

rewrite_shared_links "$ROOT/.cursor/skills"
rewrite_shared_links "$ROOT/.claude/skills"

echo "Rewrote shared/ relative links in synced skill copies (Cursor/Claude depth fix)."
