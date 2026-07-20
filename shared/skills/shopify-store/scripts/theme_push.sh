#!/usr/bin/env bash
# Push local theme files via Shopify CLI (fallback when Admin themeFilesUpsert is blocked).
#
# Prerequisites:
#   npm install -g @shopify/cli @shopify/theme
#   SHOPIFY_SHOP, SHOPIFY_THEME_ACCESS_PASSWORD in .env
#
# Usage:
#   ./theme_push.sh --path ./outputs/shopify/my-theme-delta
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || cd "$SCRIPT_DIR/../../../.." && pwd)"

if [[ -f "$ROOT/.env" ]]; then
  set -a; source "$ROOT/.env"; set +a
fi

THEME_PATH=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --path) THEME_PATH="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 --path <directory-with-theme-files>"
      exit 0
      ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$THEME_PATH" || ! -d "$THEME_PATH" ]]; then
  echo "Provide --path to a directory containing theme files (e.g. templates/index.json)."
  exit 1
fi

if [[ -z "${SHOPIFY_SHOP:-}" ]]; then
  echo "SHOPIFY_SHOP not set"
  exit 1
fi

if [[ -z "${SHOPIFY_THEME_ACCESS_PASSWORD:-}" ]]; then
  echo "SHOPIFY_THEME_ACCESS_PASSWORD not set."
  echo "Create one in Shopify Admin → Online Store → Themes → … → Edit code → Theme access."
  exit 1
fi

if ! command -v shopify >/dev/null 2>&1; then
  echo "Shopify CLI not found. Install: npm install -g @shopify/cli @shopify/theme"
  exit 1
fi

export SHOPIFY_FLAG_STORE="$SHOPIFY_SHOP"
export SHOPIFY_CLI_THEME_TOKEN="$SHOPIFY_THEME_ACCESS_PASSWORD"

THEME_ID_ARG=()
if [[ -n "${SHOPIFY_THEME_ID:-}" ]]; then
  THEME_ID_ARG=(--theme "${SHOPIFY_THEME_ID}")
fi

echo "Pushing theme files from $THEME_PATH to $SHOPIFY_SHOP ..."
shopify theme push "${THEME_ID_ARG[@]}" --path "$THEME_PATH" --only "$(find "$THEME_PATH" -type f | sed "s|^$THEME_PATH/||" | paste -sd, -)"
echo "Done."
