#!/bin/sh
# ONE PAIR FOR ZAC'S EYE: our SmoothPush beside ChatCut's slow-push, on the same word.
#   h_pair.sh [at_s] [span_s] [magnification]
# Serial by the same rule as h_stage.sh: refuses while any chatcut app is running, fresh
# presign each call, exit codes read BARE (never through a pipe).
set -u
set -o pipefail
cd "$(dirname "$0")/.." || exit 2
AT=${1:-12.0}; SPAN=${2:-2.0}; MAG=${3:-1.2}
mkdir -p /tmp/bs; LOG=/tmp/bs/h_pair.log; RC=/tmp/bs/h_pair.rc
RUNNING=$(modal app list 2>/dev/null | /usr/bin/grep -i 'chatcut' | /usr/bin/grep -ci 'running\|ephemeral')
[ "$RUNNING" = "0" ] || { echo "REFUSED: $RUNNING chatcut app(s) running"; exit 3; }
# THE GATES BEFORE THE SPEND. A blob that drifted from the cap is not worth a run, and a
# pair built from one would be a measurement of the wrong component.
python3 red_proof_the_cap_has_one_source.py > /tmp/bs/h_pair_gate.log 2>&1
[ $? -eq 0 ] || { echo "REFUSED: the cap gate is not green — see /tmp/bs/h_pair_gate.log"; exit 5; }
# THE NAMES ON DISK, BEFORE THE SPEND. red_proof_no_undefined_names judges the COMMITTED
# tree from an isolated worktree; a run is launched from what is on disk. A slice edit once
# removed two closures and a table from zoom_pair, the proof reported the committed state,
# and the container died on NameError after paying for a prestage.
python3 -m pyflakes chatcut_job_app.py > /tmp/bs/h_pair_pyflakes.log 2>&1
BAD=$(/usr/bin/grep -c "undefined name\|redefinition of unused" /tmp/bs/h_pair_pyflakes.log)
[ "$BAD" = "0" ] || { echo "REFUSED: $BAD undefined/shadowed name(s) on disk:"; /usr/bin/grep "undefined name\|redefinition of unused" /tmp/bs/h_pair_pyflakes.log; exit 6; }
K="ab-sources/reliability-fixtures-v3/talking_head-f4195ca9.mp4"
SRC=$(python3 presign.py "$K" | cut -f1); [ -n "$SRC" ] || { echo "presign failed"; exit 4; }
CODE=$(curl -s -o /dev/null -w '%{http_code}' "$SRC"); [ "$CODE" = "200" ] || { echo "presign GET -> $CODE"; exit 4; }
CMD="modal run --detach chatcut_job_app.py::zoom_pair --clip-url '$SRC' --at-s $AT --span-s $SPAN --magnification $MAG"
echo "$CMD" | sed "s|$SRC|<presigned>|"
sh -c "$CMD" > "$LOG" 2>&1
echo $? > "$RC"
echo "rc=$(cat $RC)  log=$LOG"
tail -20 "$LOG"
