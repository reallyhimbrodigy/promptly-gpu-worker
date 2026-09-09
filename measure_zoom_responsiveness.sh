#!/bin/bash
# How much does a 1.10x zoom actually change the picture on this source?
#
# THIS IS THE PROPERTY THE CORPUS FAILED. zoom_not_applied fired on three
# components in round 36, but every fixture is a flat field or noise — zooming a
# near-uniform picture cannot move pixels, so the check may have been measuring
# the corpus rather than the components.
#
# LOW psnr = the zoom changed a lot (good, measurable).
# HIGH psnr = the zoom changed almost nothing (the source cannot exercise zoom).
set -uo pipefail
URL="${1:?usage: measure_zoom_responsiveness.sh <url-or-path> [label] [ss]}"
LABEL="${2:-source}"
# THE TIMESTAMP WAS SILENTLY IGNORED. -ss was hardcoded to 5, so eleven
# "measurements" at eleven different timestamps returned 13.801452 dB — the same
# value to six decimals, which is the tell. Third time this session that an
# identical number from a changed input was the thing that caught the bug.
SS="${3:-5}"
T=$(mktemp -d)
# One second, mid-clip, at native scale vs the same second zoomed 1.10x centre.
ffmpeg -hide_banner -loglevel error -y -ss "$SS" -t 1 -i "$URL" -vf "scale=540:960" "$T/a.mp4" 2>/dev/null
ffmpeg -hide_banner -loglevel error -y -ss "$SS" -t 1 -i "$URL" \
  -vf "scale=594:1056,crop=540:960:27:48" "$T/b.mp4" 2>/dev/null
if [ ! -s "$T/a.mp4" ] || [ ! -s "$T/b.mp4" ]; then echo "  $LABEL: could not build arms"; rm -rf "$T"; exit 1; fi
DB=$(ffmpeg -hide_banner -nostats -i "$T/a.mp4" -i "$T/b.mp4" \
     -lavfi "psnr" -f null - 2>&1 | grep -oE "average:[0-9.]+" | head -1 | cut -d: -f2)
echo "  ${LABEL}: 1.10x zoom -> psnr ${DB:-n/a} dB"
rm -rf "$T"
