# Creative iteration (ad-set cycle)

Agent-assisted loop for **creative-test** ad sets: cut losers, keep a hard
active-ad cap, spawn winner variations into free slots. One ad set per run.

Defaults are tuned for ~£15/day ABO CT sets (`OTA | {sku} | Cold | Purchase | CT`).

## When to run

- Trigger phrases: "iterate this ad set", "creative cycle", "cut losers spawn winners".
- Cadence: every **3–4 days**.
- Skip the cycle if ad-set spend in the window is **&lt; £20** (not enough signal).
- Run once per CT ad set (GaN, Qi2, …) — do not orchestrate the whole account here.

## Defaults

| Knob | Default | Meaning |
|------|---------|---------|
| Window | `last_3d` | Insights lookback |
| Max ACTIVE | **5** | Cap so ads do not drown each other |
| Min spend to judge | **£8** | Below = `learning` (never cut) |
| Loser ROAS | &lt; 50% of judged median | Relative underperformer among judged ads |
| Apply | dry-run | `--apply` pauses only; never deletes or auto-activates |

## Classification

Only **ACTIVE** ads count toward the cap.

| Bucket | Rule | Action |
|--------|------|--------|
| Learning | spend &lt; min | Keep |
| Winner | ≥1 purchase, or best ROAS among judged (spend ≥ min) | Keep; source for variations |
| Loser | spend ≥ min and 0 purchases; **or** ROAS &lt; 50% of judged median | Pause |
| Mid | Judged, not winner/loser | Keep if under cap; else pause worst mids first (lowest ROAS) |

**Protect list:** `--protect-ad-id` (repeatable). Controls are never paused.

**Capacity after cuts:**

```text
spawn_slots = max(0, max_active - remaining_active)
```

If winners + learning already exceed the cap after pausing losers/mids, note the
overflow in the plan — do **not** auto-pause winners.

## Spawn brief

Each free slot gets one variation of a winner:

- Keep sku / ratio / fmt from the winner name ([naming-convention.md](naming-convention.md)).
- Change **one** thing: hook, visual, copy angle, or format — not a full rebrand.
- Bump the `variant` slug in the ad name.
- Generate via the image/video skills → `deploy-ad.py` (**PAUSED**) → human unmutes.

Prefer at most **2** new ads unmuted into a set in one cycle, even if more slots exist.

## Script

```bash
# Dry-run (default) — writes plan.json + summary.md
python scripts/iterate-adset.py --adset-id 120250218590230639

# Pause recommended losers / excess mids after review
python scripts/iterate-adset.py --adset-id 120250218590230639 --apply

# Keep controls safe
python scripts/iterate-adset.py --adset-id … \
  --protect-ad-id 120250246785460639 --protect-ad-id 120250246779770639
```

Output: `outputs/meta-ads/YYYY-MM-DD-iterate-<sku>/plan.json` + `summary.md`.

## Hand-off

1. Run `iterate-adset.py` (dry-run) → review plan with the user.
2. `--apply` if pause list is correct.
3. For each spawn slot: generate creative → Phase 2 copy (optional) →
   `deploy-ad.py` PAUSED into the **same** ad set.
4. Unmute only into free delivery room (respect the ACTIVE cap).

## Anti-patterns

- Launching more than **2** new ads at once into a set already near the cap.
- Cutting `learning` ads (spend below the judge threshold).
- Deleting ads — pause so history and naming stay readable.
- Auto-unpausing deploys (skill safety: always PAUSED until human review).
- Growing a CT ad set past the ACTIVE cap "to test more" — that dilutes delivery.
- Changing budgets / audiences in this loop — out of scope; use Ads Manager or a
  separate budget plan.
