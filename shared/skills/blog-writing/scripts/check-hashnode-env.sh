#!/usr/bin/env bash
# Verify Hashnode env for blog-writing skill.
# Usage: bash check-hashnode-env.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${ROOT}" ]]; then
  ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
fi

ENV_FILE=""
for candidate in "$ROOT/.env" "$SCRIPT_DIR/../../../../.env"; do
  if [[ -f "$candidate" ]]; then
    ENV_FILE="$candidate"
    break
  fi
done

if [[ -n "$ENV_FILE" ]]; then
  echo "Loading env from: $ENV_FILE"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "No .env found — relying on exported environment variables."
fi

missing=0
if [[ -z "${HASHNODE_PAT:-}" ]]; then
  echo "  MISSING: HASHNODE_PAT"
  missing=1
else
  echo "  OK: HASHNODE_PAT is set (${#HASHNODE_PAT} chars, prefix ${HASHNODE_PAT:0:4}…)"
fi

if [[ -z "${HASHNODE_PUBLICATION_ID:-}" ]]; then
  echo "  MISSING: HASHNODE_PUBLICATION_ID (needed for draft/publish)"
else
  echo "  OK: HASHNODE_PUBLICATION_ID is set"
fi

echo "  HASHNODE_GQL_URL=${HASHNODE_GQL_URL:-https://gql.hashnode.com}"
if [[ -n "${HASHNODE_HOST:-}" ]]; then
  echo "  HASHNODE_HOST=$HASHNODE_HOST"
fi

if [[ "$missing" -ne 0 ]]; then
  echo
  echo "Add HASHNODE_PAT (and HASHNODE_PUBLICATION_ID) to .env — see blog/README.md"
  echo "Write mutations require Hashnode Pro on the publication."
  exit 1
fi

echo
echo "Calling Hashnode whoami..."
python3 "$SCRIPT_DIR/hashnode_cli.py" whoami
echo
echo "Hashnode env looks good. Try:"
echo "  python3 $SCRIPT_DIR/hashnode_cli.py preview --project blog/posts/<date>-<slug>"
echo "  python3 $SCRIPT_DIR/hashnode_cli.py upsert-draft --project blog/posts/<date>-<slug> --dry-run"
