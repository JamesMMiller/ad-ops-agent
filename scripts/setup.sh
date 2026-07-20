#!/usr/bin/env bash
# First-run setup for ad-ops-agent.
# Creates workspace files, syncs skills, and (by default) configures KIE.ai.
#
# Usage:
#   ./scripts/setup.sh              # interactive (default: configure KIE)
#   ./scripts/setup.sh --with-kie
#   ./scripts/setup.sh --skip-api   # workspace only, no API key
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== ad-ops-agent setup ==="
echo ""

WITH_ARCADS=""
WITH_KIE=""

for arg in "$@"; do
  case "$arg" in
    --skip-api|--skip-arcads|--no-arcads|--workspace-only)
      WITH_ARCADS=0
      WITH_KIE=0
      ;;
    --with-arcads|--arcads)
      echo "Note: --with-arcads is deprecated in this repo; configuring KIE.ai instead."
      echo "      Use: ./scripts/setup.sh --with-kie"
      WITH_KIE=1
      WITH_ARCADS=0
      ;;
    --with-kie|--kie)
      WITH_KIE=1
      WITH_ARCADS=0
      ;;
    -h|--help)
      echo "Usage: $0 [--with-kie|--skip-api]"
      echo "  --with-kie    Configure KIE.ai (recommended / default interactive choice)."
      echo "  --skip-api    Workspace only — no generative API key required."
      exit 0
      ;;
  esac
done

if [[ -z "$WITH_KIE" && -z "$WITH_ARCADS" ]]; then
  if [[ "${SKIP_ARCADS:-}" == "1" || "${AD_OPS_SKIP_ARCADS:-}" == "1" ]]; then
    WITH_ARCADS=0
    WITH_KIE=0
  fi
fi

# Ensure .env exists from .env.example.
ensure_env_file() {
  if [[ ! -f "$ROOT/.env" ]]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    echo "Created .env from template."
  else
    echo ".env already exists."
  fi
  chmod 600 "$ROOT/.env" 2>/dev/null || true
}

set_backend() {
  local backend="$1"
  if grep -q '^AD_OPS_BACKEND=' "$ROOT/.env" 2>/dev/null; then
    sed "s|^AD_OPS_BACKEND=.*|AD_OPS_BACKEND=${backend}|" "$ROOT/.env" > "$ROOT/.env.tmp" \
      && mv "$ROOT/.env.tmp" "$ROOT/.env"
  else
    {
      echo ""
      echo "# ad-ops-agent: generative backend mode"
      echo "# kie | none"
      echo "AD_OPS_BACKEND=${backend}"
    } >> "$ROOT/.env"
  fi
}

mark_api_skipped() {
  # Prefer KIE if a real key is already present; otherwise none.
  if grep -q "^KIE_API_KEY=" "$ROOT/.env" 2>/dev/null \
    && ! grep -q "^KIE_API_KEY=your_key_here" "$ROOT/.env" 2>/dev/null \
    && ! grep -q "^KIE_API_KEY=''" "$ROOT/.env" 2>/dev/null; then
    set_backend kie
  else
    set_backend none
  fi
}

mark_kie_enabled() {
  set_backend kie
}

prompt_backend_choice() {
  echo "Choose generative backend setup:"
  echo ""
  echo "  [1] Configure KIE.ai  (recommended — https://kie.ai/api-key)"
  echo "  [2] Workspace only    (no API key — local skills / docs)"
  echo ""
  printf "Choice [1/2] (default 1): "
  read -r choice || choice=""
  case "${choice:-1}" in
    2|none|skip|n|N)
      WITH_KIE=0
      WITH_ARCADS=0
      ;;
    *)
      WITH_KIE=1
      WITH_ARCADS=0
      ;;
  esac
}

# ── Step 0: choose backend mode ──────────────────────────────────────────────
if [[ -z "$WITH_KIE" && -z "$WITH_ARCADS" ]]; then
  if [[ -f "$ROOT/.env" ]] && grep -q '^AD_OPS_BACKEND=kie' "$ROOT/.env" 2>/dev/null \
    && grep -q "^KIE_API_KEY=" "$ROOT/.env" 2>/dev/null \
    && ! grep -q "^KIE_API_KEY=your_key_here" "$ROOT/.env" 2>/dev/null; then
    echo ".env already has KIE configured — keeping it."
    WITH_KIE=1
    WITH_ARCADS=0
  else
    prompt_backend_choice
  fi
fi

# ── Step 1: .env ─────────────────────────────────────────────────────────────
ensure_env_file

if [[ "$WITH_KIE" == "1" ]]; then
  if ! grep -q '^KIE_API_KEY=' "$ROOT/.env" 2>/dev/null; then
    {
      echo ""
      echo "# ── KIE.ai ───────────────────────────────────────────────────────────────────"
      echo "# https://kie.ai/api-key"
      echo "KIE_API_KEY=your_key_here"
    } >> "$ROOT/.env"
  fi
  if grep -qE "^KIE_API_KEY=(your_key_here|'')?$" "$ROOT/.env" 2>/dev/null \
    || grep -q "^KIE_API_KEY=your_key_here" "$ROOT/.env" 2>/dev/null; then
    echo "Paste your KIE API key into .env (KIE_API_KEY=...) then re-run:"
    echo "  ./scripts/check-kie-env.sh"
  fi
  mark_kie_enabled
  echo "Backend mode: kie"
else
  mark_api_skipped
  if grep -q '^AD_OPS_BACKEND=kie' "$ROOT/.env" 2>/dev/null; then
    echo "Backend mode: kie (KIE_API_KEY already present)."
  else
    echo "Backend mode: none (no generative API required)."
    echo "Add KIE later with: ./scripts/setup.sh --with-kie"
  fi
fi

echo ""

# ── Step 2: MASTER_CONTEXT.md ────────────────────────────────────────────────
if [[ ! -f "$ROOT/MASTER_CONTEXT.md" ]]; then
  cp "$ROOT/MASTER_CONTEXT.template.md" "$ROOT/MASTER_CONTEXT.md"
  echo "Created MASTER_CONTEXT.md from template."
  echo "The agent will help you fill brand / product defaults on first use."
else
  echo "MASTER_CONTEXT.md already exists — skipping."
fi

echo ""

# ── Step 3: Sync skills to .claude/ and .cursor/ ─────────────────────────────
"$ROOT/scripts/sync-skill.sh"

echo ""

# ── Step 4: Optional connectivity check ─────────────────────────────────────
if [[ "$WITH_KIE" == "1" ]] || grep -q '^AD_OPS_BACKEND=kie' "$ROOT/.env" 2>/dev/null; then
  if ! grep -q "^KIE_API_KEY=your_key_here" "$ROOT/.env" 2>/dev/null; then
    "$ROOT/scripts/check-kie-env.sh" || true
  else
    echo "Skipping KIE check — replace your_key_here in .env first."
  fi
else
  echo "Skipping generative API connectivity check."
fi

echo ""
echo "Setup complete."
echo "  • Workspace: MASTER_CONTEXT.md + synced skills in .cursor/skills/"
if grep -q '^AD_OPS_BACKEND=kie' "$ROOT/.env" 2>/dev/null; then
  echo "  • Backend: KIE.ai (AD_OPS_BACKEND=kie)"
else
  echo "  • Backend: none — IDE agent + local skills only (AD_OPS_BACKEND=none)"
fi
echo "Open this folder in Cursor / Claude Code / your IDE agent to start."
