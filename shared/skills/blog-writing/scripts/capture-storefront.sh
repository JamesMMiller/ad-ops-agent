#!/usr/bin/env bash
# Capture live Our Tech storefront screenshots into a post's images/ dir.
# Usage:
#   bash shared/skills/blog-writing/scripts/capture-storefront.sh \
#     blog/posts/2026-07-23-lead-dev-dropshipping-calm-store/images
set -euo pipefail

OUT="${1:-}"
if [[ -z "$OUT" ]]; then
  echo "Usage: $0 <output-images-dir>" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${ROOT}" ]]; then
  ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
fi

mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [[ ! -x "$CHROME" ]]; then
  echo "Google Chrome not found at $CHROME" >&2
  exit 1
fi

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

# Prefer playwright-core for cookie dismiss; fall back to headless Chrome.
if command -v npm >/dev/null 2>&1; then
  cd "$TMP"
  npm install --silent playwright-core@1.54.0 >/dev/null 2>&1 || true
fi

if [[ -d "$TMP/node_modules/playwright-core" ]]; then
  cat > "$TMP/capture.mjs" <<EOF
import { chromium } from 'playwright-core';
import path from 'path';

const out = process.argv[2];
const chrome = ${CHROME@Q};

async function dismissCookies(page) {
  for (const label of ['Accept', 'Decline']) {
    const btn = page.getByRole('button', { name: label });
    if (await btn.count()) {
      await btn.first().click({ timeout: 2000 }).catch(() => {});
      await page.waitForTimeout(400);
      return;
    }
  }
}

async function shot(page, name, url, viewport) {
  await page.setViewportSize(viewport);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(2200);
  await dismissCookies(page);
  await page.screenshot({ path: path.join(out, name), fullPage: false });
  console.log('wrote', name);
}

const browser = await chromium.launch({
  executablePath: chrome,
  headless: true,
  args: ['--disable-gpu', '--hide-scrollbars'],
});
const page = await browser.newPage();
await shot(page, 'homepage-desktop.png', 'https://ourtechaccessories.com/', { width: 1440, height: 1600 });
await shot(page, 'pdp-neck-fan-desktop.png', 'https://ourtechaccessories.com/products/folding-hanging-neck-electric-fan', { width: 1440, height: 1600 });
await shot(page, 'about-desktop.png', 'https://ourtechaccessories.com/pages/about', { width: 1440, height: 1400 });
await shot(page, 'collections-cooling-desktop.png', 'https://ourtechaccessories.com/collections/cooling', { width: 1440, height: 1200 });
await shot(page, 'pdp-neck-fan-mobile.png', 'https://ourtechaccessories.com/products/folding-hanging-neck-electric-fan', { width: 390, height: 900 });
await browser.close();
EOF
  node "$TMP/capture.mjs" "$OUT"
else
  echo "playwright-core unavailable; using headless Chrome (cookie banner may appear)" >&2
  FLAGS=(--headless=new --disable-gpu --hide-scrollbars --no-first-run --disable-background-networking)
  perl -e 'alarm shift; exec @ARGV' 25 "$CHROME" "${FLAGS[@]}" --window-size=1440,1600 \
    --screenshot="$OUT/homepage-desktop.png" "https://ourtechaccessories.com/" || true
  perl -e 'alarm shift; exec @ARGV' 25 "$CHROME" "${FLAGS[@]}" --window-size=1440,1600 \
    --screenshot="$OUT/pdp-neck-fan-desktop.png" \
    "https://ourtechaccessories.com/products/folding-hanging-neck-electric-fan" || true
fi

ls -la "$OUT"
echo "Done. Wire images into post.md with relative paths like ![...](images/homepage-desktop.png)"
