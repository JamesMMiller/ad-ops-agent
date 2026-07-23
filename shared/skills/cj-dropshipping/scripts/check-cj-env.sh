#!/usr/bin/env bash
# Verify CJ Dropshipping API key.
# Usage: bash check-cj-env.sh
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
  set -a; # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "No .env found — relying on exported environment variables."
fi

if [[ -z "${CJ_API_KEY:-}" ]]; then
  echo "  MISSING: CJ_API_KEY"
  echo "Add it to .env (see .env.example). Get a key in CJ → personal center → API."
  exit 1
fi

echo "  OK: CJ_API_KEY is set"
echo
echo "Exchanging API key for access token..."
python3 "$SCRIPT_DIR/cj_cli.py" whoami
echo
echo "CJ env looks good. Try:"
echo "  python3 $SCRIPT_DIR/cj_cli.py search -q 'neck fan' --countries GB,DE"
