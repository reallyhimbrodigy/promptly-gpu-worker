#!/bin/sh
# OUR LAYER AT REST AGAINST THE BARE SOURCE (Zac, 2026-09-19).
# A zoom component at scale 1.0 must be pixel-identical to the source; anything else
# changes every frame outside its own move, which is tampering by another name.
#   h_rest.sh [at_s] [span_s] [component]
# Serial, same two pre-spend gates as h_pair.sh, exit codes read BARE.
set -u
set -o pipefail
cd "$(dirname "$0")/.." || exit 2
AT=${1:-12.0}; SPAN=${2:-2.0}; COMP=${3:-SmoothPush}
mkdir -p /tmp/bs; LOG=/tmp/bs/h_rest.log; RC=/tmp/bs/h_rest.rc
RUNNING=$(modal app list 2>/dev/null | /usr/bin/grep -i 'chatcut' | /usr/bin/grep -ci 'running\|ephemeral')
[ "$RUNNING" = "0" ] || { echo "REFUSED: $RUNNING chatcut app(s) running"; exit 3; }
python3 red_proof_the_cap_has_one_source.py > /tmp/bs/h_rest_gate.log 2>&1
[ $? -eq 0 ] || { echo "REFUSED: the cap gate is not green — see /tmp/bs/h_rest_gate.log"; exit 5; }
python3 -m pyflakes chatcut_job_app.py > /tmp/bs/h_rest_pyflakes.log 2>&1
BAD=$(/usr/bin/grep -c "undefined name\|redefinition of unused" /tmp/bs/h_rest_pyflakes.log)
[ "$BAD" = "0" ] || { echo "REFUSED: $BAD undefined/shadowed name(s) on disk"; /usr/bin/grep "undefined name\|redefinition of unused" /tmp/bs/h_rest_pyflakes.log; exit 6; }
K="ab-sources/reliability-fixtures-v3/talking_head-f4195ca9.mp4"
SRC=$(python3 presign.py "$K" | cut -f1); [ -n "$SRC" ] || { echo "presign failed"; exit 4; }
CODE=$(curl -s -o /dev/null -w '%{http_code}' "$SRC"); [ "$CODE" = "200" ] || { echo "presign GET -> $CODE"; exit 4; }
CMD="modal run --detach chatcut_job_app.py::zoom_rest --clip-url '$SRC' --at-s $AT --span-s $SPAN --component $COMP"
echo "$CMD" | sed "s|$SRC|<presigned>|"
sh -c "$CMD" > "$LOG" 2>&1
echo $? > "$RC"
echo "rc=$(cat $RC)  log=$LOG"
/usr/bin/grep -E "PROJECT|BARE SOURCE|PLACED AT REST|WITH THE LAYER|REST|PROFILE" "$LOG" | tail -8
