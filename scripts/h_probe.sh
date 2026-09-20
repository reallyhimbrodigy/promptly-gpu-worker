#!/bin/sh
# THE THREE MOTION-GRAPHIC RUNTIME QUESTIONS, in one run. No model calls.
#   two_video_layers   gates all NINE transitions and BOTH tight-cut overlays
#   spring             gates SnapReframe, whose curve IS a spring
#   interpolate_easing what every ported transition would rather use than a hand-rolled clamp
# Serial by the same rule as h_stage.sh and h_pair.sh; the same two gates before the spend.
set -u
set -o pipefail
cd "$(dirname "$0")/.." || exit 2
mkdir -p /tmp/bs; LOG=/tmp/bs/h_probe.log; RC=/tmp/bs/h_probe.rc
RUNNING=$(modal app list 2>/dev/null | /usr/bin/grep -i 'chatcut' | /usr/bin/grep -ci 'running\|ephemeral')
[ "$RUNNING" = "0" ] || { echo "REFUSED: $RUNNING chatcut app(s) running"; exit 3; }
python3 -m pyflakes chatcut_job_app.py > /tmp/bs/h_probe_pyflakes.log 2>&1
BAD=$(/usr/bin/grep -c "undefined name\|redefinition of unused" /tmp/bs/h_probe_pyflakes.log)
[ "$BAD" = "0" ] || { echo "REFUSED: $BAD undefined/shadowed name(s) on disk:"; /usr/bin/grep "undefined name\|redefinition of unused" /tmp/bs/h_probe_pyflakes.log; exit 6; }
K="ab-sources/reliability-fixtures-v3/talking_head-f4195ca9.mp4"
SRC=$(python3 presign.py "$K" | cut -f1); [ -n "$SRC" ] || { echo "presign failed"; exit 4; }
CODE=$(curl -s -o /dev/null -w '%{http_code}' "$SRC"); [ "$CODE" = "200" ] || { echo "presign GET -> $CODE"; exit 4; }
CMD="modal run --detach chatcut_job_app.py::mg_runtime_probe --clip-url '$SRC'"
echo "$CMD" | sed "s|$SRC|<presigned>|"
sh -c "$CMD" > "$LOG" 2>&1
echo $? > "$RC"
echo "rc=$(cat $RC)  log=$LOG"
/usr/bin/grep -E "two_video_layers|spring|interpolate_easing|PRESTAGE" "$LOG" | tail -8
