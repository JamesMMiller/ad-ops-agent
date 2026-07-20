#!/usr/bin/env bash
# Verify Shopify Admin API credentials (client credentials grant).
# Usage: bash check-shopify-env.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || cd "$SCRIPT_DIR/../../../.." && pwd)"

ENV_FILE="${ENV_FILE:-}"
for candidate in "$ROOT/.env" "$SCRIPT_DIR/../../../../.env"; do
  if [[ -f "$candidate" ]]; then
    ENV_FILE="$candidate"
    break
  fi
done

if [[ -n "$ENV_FILE" && -f "$ENV_FILE" ]]; then
  echo "Loading env from: $ENV_FILE"
  set -a; source "$ENV_FILE"; set +a
else
  echo "No .env found — relying on exported environment variables."
fi

fail=0
for var in SHOPIFY_SHOP SHOPIFY_CLIENT_ID SHOPIFY_CLIENT_SECRET; do
  if [[ -z "${!var:-}" ]]; then
    echo "  MISSING: $var"
    fail=1
  elif [[ "$var" == *SECRET* ]]; then
    echo "  OK: $var is set"
  else
    echo "  OK: $var = ${!var}"
  fi
done

if [[ "$fail" -ne 0 ]]; then
  echo
  echo "Add missing keys to .env (see .env.example)."
  exit 1
fi

echo
echo "Exchanging client credentials for Admin API token..."
python3 "$SCRIPT_DIR/shopify_cli.py" whoami
echo
echo "Shopify env looks good. Use shopify_cli.py for products, pages, and theme files."
