---
name: edit-video
description: >-
  Local post-production for generated ad clips using ffmpeg only — soft-stitch
  multi-clip masters, crossfades, trims, audio fades. No generative API calls.
  Use when the user wants to fix an abrupt cut between stitched Seedance/Veo/Sora
  clips, smooth a transition, trim dead space, or re-assemble a multi-clip ad
  without regenerating.
---

# Edit video (local ffmpeg — no API)

**Rule zero:** Prefer local edits over regenerating. If the user says "don't run another query" / "don't regenerate" / "just edit", stay offline — ffmpeg only.

## When to use

| Signal | Action |
|--------|--------|
| Abrupt cut between stitched clips | Soft-stitch with `xfade` + `acrossfade` |
| First clip feels cut off / unfinished at the join | Soft-stitch **with end pad** (default) — freeze last frame so the full clip plays before the fade |
| Hard concat feels jumpy on lookbook / reveal ads | Re-stitch with fade (default **0.5–0.75s**) |
| Dead space after VO | Trim clip to `vo_dur + 0.5s` then concat |
| Captions needed after edit | Trim/stitch **first**, then `caption-video` |

## Prerequisites

```bash
which ffmpeg && which ffprobe || echo "MISSING — brew install ffmpeg"
```

## Soft-stitch (default for multi-clip ads)

Hard `-c copy` concat causes abrupt A/V jumps. For premium reveals and lookbooks, **always soft-stitch** unless the user asks for a hard cut.

### Helper script

```bash
./shared/skills/edit-video/scripts/soft-stitch.sh \
  --fade 0.6 \
  --pad 0.9 \
  --out outputs/my-ad/final-smooth.mp4 \
  outputs/my-ad/clip-a.mp4 \
  outputs/my-ad/clip-b.mp4
```

- Supports **2+ clips** (pairwise xfade chain).
- **Default: end-pad on** — freezes the last frame for `--pad` seconds (defaults to `--fade`) so the outgoing clip finishes fully; the **video** crossfade runs on that pad.
- **Default audio with pad: `--audio cut`** — incoming clip audio starts at **full volume** at the join (no fade-in). Outgoing audio stops at the join.
- `--audio crossfade` — blend both audio beds (only if you explicitly want a soft VO handoff).
- `--no-pad` — fade eats the last N seconds of the outgoing clip. Avoid for reveals/lookbooks.
- Default fade: **0.6s**. For a short hold before the blend, set `--pad` a bit higher than `--fade` (e.g. pad 0.9 / fade 0.6).
- Keeps a `-hardcut.mp4` copy if overwriting an existing master.

### Manual two-clip recipe (padded — preferred)

```bash
DUR_A=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 clip-a.mp4)
FADE=0.6
PAD=0.9

ffmpeg -y -i clip-a.mp4 -i clip-b.mp4 -filter_complex \
  "[0:v]format=yuv420p,tpad=stop_mode=clone:stop_duration=${PAD}[v0]; \
   [0:a]apad=pad_dur=${PAD}[a0]; \
   [v0][1:v]xfade=transition=fade:duration=${FADE}:offset=${DUR_A}[v]; \
   [a0][1:a]acrossfade=d=${FADE}:c1=tri:c2=tri[a]" \
  -map "[v]" -map "[a]" \
  -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k \
  final-smooth.mp4
```

With padding, final duration ≈ `sum(clip_durations)` (pad and fade cancel). Without `--pad`, duration shrinks by `fade * (n-1)`.

### Transition presets

| Feel | `xfade` transition | Fade length |
|------|-------------------|-------------|
| Premium / Apple reveal (default) | `fade` | 0.5–0.75s |
| Slightly softer | `smoothleft` / `smoothright` | 0.6–1.0s |
| Dip to black | `fadeblack` | 0.4–0.6s |
| Hard cut (only if asked) | concat demuxer `-c copy` | 0 |

## Workflow for agents

1. **Confirm no API** — editing is local; do not call KIE/Arcads.
2. Locate source clips (prefer per-clip files, not only the hardcut master).
3. Soft-stitch with the helper (or manual recipe).
4. Deliver the smooth master path; keep hardcut as `*-hardcut.mp4` if useful.
5. Log nothing to `logs/*-api.jsonl` (no generation). Optional note in the session folder `edit-notes.md`.

## Generation skills should point here

When Seedance/Veo/Sora workflows stitch multi-clip outputs (duration > model max):

1. Generate clips as usual.
2. **Default join = soft-stitch with end pad** via this skill (not raw concat, not fade-without-pad).
3. Offer fade/pad lengths; defaults **fade 0.6s / pad 0.9s** for dark-void / lookbook ads.

## Out of scope

- Generative re-roll / prompt changes → use `kie-external-api` / `arcads-external-api`
- Burned captions → `caption-video` after the edit
- Color grade / Resolve projects → out of band
