#!/bin/bash
# Can a zoom on THIS source be told apart from a passthrough on THIS source?
#
# REPLACES AN ABSOLUTE FLOOR THAT HAD LEARNED THE WRONG PROPERTY. The corpus
# gate rejected any source whose 1.10x zoom read above 18.0 dB. Zac's two real
# clips read 19.13 and 22.33 — IT WOULD HAVE REJECTED BOTH REAL VIDEOS while
# admitting grey cellular static at 11.6. Builder-2 named the consequence
# exactly: a gate that rejects real footage and accepts synthetic has learned
# "detailed" and called it "usable", and every source it admits from then on is
# one our instruments can measure and the product never sees.
#
# THE PROPERTY THAT ACTUALLY MATTERS is not how responsive a source is in the
# absolute. It is whether a zoom SEPARATES from a passthrough ON THAT SOURCE.
# Both arms are measured against the same content, so content cancels and there
# is no population constant to mis-fit — the same reasoning that made
# Builder-2's scale-fit test survive a corpus swap that broke both our bars.
#
# BOTH ARMS GO THROUGH THE SAME SCALE+CROP+ENCODE so encoder loss is matched and
# the difference is the geometry, not the codec.
set -uo pipefail
URL="${1:?usage: zoom_separability.sh <url-or-path> [label] [ss]}"
LABEL="${2:-source}"
SS="${3:-5}"
T=$(mktemp -d)
# reference: plain downscale
ffmpeg -hide_banner -loglevel error -y -ss "$SS" -t 1 -i "$URL" -vf "scale=540:960" "$T/ref.mp4" 2>/dev/null
# passthrough arm: scale UP then back DOWN to the same frame — same pipeline, no zoom
ffmpeg -hide_banner -loglevel error -y -ss "$SS" -t 1 -i "$URL" -vf "scale=594:1056,scale=540:960" "$T/pass.mp4" 2>/dev/null
# zoom arm: scale up then CROP the centre — a real 1.10x push
ffmpeg -hide_banner -loglevel error -y -ss "$SS" -t 1 -i "$URL" -vf "scale=594:1056,crop=540:960:27:48" "$T/zoom.mp4" 2>/dev/null
for f in ref pass zoom; do [ -s "$T/$f.mp4" ] || { echo "  $LABEL: could not build $f arm"; rm -rf "$T"; exit 1; }; done
psnr () {
  ffmpeg -hide_banner -nostats -i "$1" -i "$2" -lavfi psnr -f null - 2>&1 \
    | grep -oE "average:[0-9.]+" | head -1 | cut -d: -f2
}
DP=$(psnr "$T/ref.mp4" "$T/pass.mp4")
DZ=$(psnr "$T/ref.mp4" "$T/zoom.mp4")
rm -rf "$T"
python3 - "$LABEL" "${DP:-0}" "${DZ:-0}" <<'PY'
import sys
label, dp, dz = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
sep = dp - dz
# A zoom must be at least this many dB further from the source than a
# passthrough is. Not a floor on responsiveness — a floor on DISTINGUISHABILITY.
BAR = 8.0
print(f"  {label:20} passthrough {dp:6.2f} dB   zoom {dz:6.2f} dB   "
      f"separation {sep:6.2f} dB   {'OK' if sep >= BAR else 'REJECT (<%.1f)' % BAR}")
PY
