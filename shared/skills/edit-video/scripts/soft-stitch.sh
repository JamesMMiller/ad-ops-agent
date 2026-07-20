#!/usr/bin/env bash
# Soft-stitch 2+ clips with video xfade (no generative API).
#
# Video (default): pad outgoing clip with freeze-frame, then crossfade so the
# full clip plays before the blend.
#
# Audio (default with pad): hard join — outgoing audio ends, incoming audio
# starts at full volume at the join (no acrossfade). Use --audio crossfade
# only if you want both sides to blend.
#
# Usage:
#   ./soft-stitch.sh [--fade 0.6] [--pad 0.9] [--no-pad] \
#                    [--audio cut|crossfade] [--transition fade] \
#                    [--out path.mp4] clip1.mp4 clip2.mp4 [clip3.mp4 ...]
set -euo pipefail

FADE=0.6
PAD=""
USE_PAD=1
AUDIO_MODE=""   # empty → cut when pad on, crossfade when --no-pad
TRANSITION=fade
OUT=""
CLIPS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fade) FADE="$2"; shift 2 ;;
    --pad) PAD="$2"; USE_PAD=1; shift 2 ;;
    --no-pad) USE_PAD=0; shift ;;
    --audio) AUDIO_MODE="$2"; shift 2 ;;
    --transition) TRANSITION="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      CLIPS+=("$1")
      shift
      ;;
  esac
done

[[ -n "$PAD" ]] || PAD="$FADE"
if [[ -z "$AUDIO_MODE" ]]; then
  if [[ "$USE_PAD" == "1" ]]; then
    AUDIO_MODE=cut
  else
    AUDIO_MODE=crossfade
  fi
fi
case "$AUDIO_MODE" in
  cut|crossfade) ;;
  *) echo "Invalid --audio (use cut|crossfade)" >&2; exit 1 ;;
esac

if [[ ${#CLIPS[@]} -lt 2 ]]; then
  echo "Need at least 2 input clips." >&2
  exit 1
fi

for c in "${CLIPS[@]}"; do
  [[ -f "$c" ]] || { echo "Missing: $c" >&2; exit 1; }
done

if [[ -z "$OUT" ]]; then
  OUT="$(cd "$(dirname "${CLIPS[0]}")" && pwd)/soft-stitched.mp4"
fi
OUT="$(mkdir -p "$(dirname "$OUT")" && cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"

if [[ -f "$OUT" && ! -f "${OUT%.mp4}-hardcut.mp4" ]]; then
  cp "$OUT" "${OUT%.mp4}-hardcut.mp4"
  echo "Kept previous master as: ${OUT%.mp4}-hardcut.mp4"
fi

dur() {
  ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$1"
}

n=${#CLIPS[@]}
inputs=()
for c in "${CLIPS[@]}"; do
  inputs+=(-i "$c")
done

fc=""
for ((i=0; i<n; i++)); do
  fc+="[${i}:v]setpts=PTS-STARTPTS,format=yuv420p[vraw${i}];"
  fc+="[${i}:a]aresample=async=1:first_pts=0[araw${i}];"
done

fc+="[vraw0]null[v0];[araw0]anull[a0];"
cum="$(dur "${CLIPS[0]}")"

for ((i=1; i<n; i++)); do
  prev=$((i-1))
  next_dur="$(dur "${CLIPS[$i]}")"

  # --- video ---
  if [[ "$USE_PAD" == "1" ]]; then
    fc+="[v${prev}]tpad=stop_mode=clone:stop_duration=${PAD}[v${prev}p];"
    offset="$cum"
    fc+="[v${prev}p][vraw${i}]xfade=transition=${TRANSITION}:duration=${FADE}:offset=${offset}[v${i}];"
  else
    offset="$(python3 -c "print(max(0.0, float('$cum') - float('$FADE')))")"
    fc+="[v${prev}][vraw${i}]xfade=transition=${TRANSITION}:duration=${FADE}:offset=${offset}[v${i}];"
  fi

  # --- audio ---
  if [[ "$AUDIO_MODE" == "crossfade" ]]; then
    if [[ "$USE_PAD" == "1" ]]; then
      fc+="[a${prev}]apad=pad_dur=${PAD}[a${prev}p];"
      fc+="[a${prev}p][araw${i}]acrossfade=d=${FADE}:c1=tri:c2=tri[a${i}];"
    else
      fc+="[a${prev}][araw${i}]acrossfade=d=${FADE}:c1=tri:c2=tri[a${i}];"
    fi
  else
    # Hard audio join at content boundary: A ends, B starts at full volume.
    # Delay B so it begins when the visual transition starts (offset).
    delay_ms="$(python3 -c "print(int(round(float('$offset') * 1000)))")"
    # Trim outgoing to the join point (drop any trailing silence we don't need)
    fc+="[a${prev}]atrim=0:${offset},asetpts=PTS-STARTPTS[a${prev}t];"
    fc+="[araw${i}]adelay=${delay_ms}|${delay_ms}[a${i}d];"
    # Pad outgoing with silence so amix timelines align through the rest of B
    total="$(python3 -c "print(float('$offset') + float('$next_dur'))")"
    fc+="[a${prev}t]apad=whole_dur=${total}[a${prev}p];"
    fc+="[a${prev}p][a${i}d]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a${i}];"
  fi

  if [[ "$USE_PAD" == "1" ]]; then
    cum="$(python3 -c "print(float('$cum') + float('$next_dur'))")"
  else
    cum="$(python3 -c "print(float('$cum') + float('$next_dur') - float('$FADE'))")"
  fi
done

last=$((n-1))
if [[ "$USE_PAD" == "1" ]]; then
  pad_note="pad=${PAD}s freeze"
else
  pad_note="no-pad"
fi
echo "Soft-stitch ${n} clips → $OUT (fade=${FADE}s, ${pad_note}, audio=${AUDIO_MODE})"
ffmpeg -y "${inputs[@]}" -filter_complex "$fc" \
  -map "[v${last}]" -map "[a${last}]" \
  -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  "$OUT"

echo "Done: $OUT ($(dur "$OUT")s)"
