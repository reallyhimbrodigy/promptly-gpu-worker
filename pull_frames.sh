#!/bin/bash
# Pull a contact sheet from every fixture's OUTPUT so a human can look at it.
#
# WHY THIS EXISTS. Four StatCards rendered completely invisible in round 35 and
# EVERY instrument passed them: the composite psnr cannot see an empty alpha
# layer, and only one of the four tripped a relative threshold. They were found
# by rendering one and looking at it. Three of the five fixtures — music,
# product_shot, pet_video — have never been looked at by anyone.
#
# Frames, not metrics. The point is a picture.
set -uo pipefail
ROUND="${1:?usage: pull_frames.sh <round-number>}"
DIR="/tmp/fixtures/round${ROUND}"
OUT="$DIR/frames"
mkdir -p "$OUT"
command -v ffmpeg >/dev/null || { echo "ffmpeg not found"; exit 2; }

found=0
# THE FIXTURES THIS ROUND ACTUALLY RAN, from its own plan.tsv — the FOURTH
# reader of the v1 five-name list found in one session (the collector's loop,
# round_is_green, archive_round and this). On round 42 it printed "no log" four
# times for fixtures that were never in the round and skipped nothing real, but
# a reader that names fixtures a round does not have will silently skip ones it
# does, which is how a sheet nobody can pull becomes a sheet nobody looks at.
FIXTURES="$(cut -f1 "$DIR/plan.tsv" 2>/dev/null | tr '\n' ' ')"
[ -n "${FIXTURES// /}" ] || { echo "no plan.tsv in $DIR — cannot know which fixtures ran"; exit 2; }
for f in $FIXTURES; do
  log="$DIR/$f.log"
  [ -f "$log" ] || { echo "  $f: no log"; continue; }
  key=$(grep -oE 's3 key +: [^ ]+' "$log" | tail -1 | awk '{print $NF}')
  if [ -z "$key" ] || [ "$key" = "None" ]; then
    echo "  $f: NO OUTPUT (s3 key '$key') — nothing to look at, which is itself the finding"
    continue
  fi
  url=$(python3 presign_get.py "$key" 2>/dev/null)
  if [ -z "$url" ]; then echo "  $f: could not presign $key"; continue; fi
  # 9 frames evenly across the clip, tiled. -y so a re-run overwrites.
  ffmpeg -hide_banner -loglevel error -y -i "$url" \
    -vf "thumbnail,scale=360:-1,tile=3x3" -frames:v 1 "$OUT/$f.png" 2>/dev/null
  if [ -s "$OUT/$f.png" ]; then
    echo "  $f: $OUT/$f.png  ($(du -h "$OUT/$f.png" | cut -f1))"
    found=$((found+1))
  else
    echo "  $f: ffmpeg produced no sheet"
  fi
done
echo "$found sheet(s) in $OUT"
