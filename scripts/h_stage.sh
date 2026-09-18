#!/bin/sh
# Part 2 H: one stage per call, serial, a fresh presign each time. Refuses while any chatcut app runs.
#   h_stage.sh warm | warmlow | probe | th0 | thlow | nowatch | motion | car   (set -o pipefail; every exit code read bare)
set -u
set -o pipefail
cd "$(dirname "$0")/.." || exit 2
STAGE="$1"; mkdir -p /tmp/bs; LOG=/tmp/bs/h_$STAGE.log; RC=/tmp/bs/h_$STAGE.rc
RUNNING=$(modal app list 2>/dev/null | /usr/bin/grep -i 'chatcut' | /usr/bin/grep -ci 'running\|ephemeral')
[ "$RUNNING" = "0" ] || { echo "REFUSED: $RUNNING chatcut app(s) running"; exit 3; }
key() { case "$1" in th0|th3000|th2000|thlow|nowatch|probe) echo "ab-sources/reliability-fixtures-v3/talking_head-f4195ca9.mp4";; motion) echo "ab-sources/reliability-fixtures-v3/motion-31fa2646.mp4";; car) echo "ab-sources/reliability-fixtures-v3/car_mid-0643be1c.mp4";; esac; }
if [ "$STAGE" != "warm" ] && [ "$STAGE" != "warmlow" ]; then
  SRC=$(python3 presign.py "$(key $STAGE)" | cut -f1); [ -n "$SRC" ] || { echo "presign failed"; exit 4; }
  CODE=$(curl -s -o /dev/null -w '%{http_code}' "$SRC"); [ "$CODE" = "200" ] || { echo "presign GET -> $CODE"; exit 4; }
fi
case "$STAGE" in
  warm)   CMD="modal run --detach chatcut_job_app.py::warm --think-tokens 0" ;;
  warmlow) CMD="modal run --detach chatcut_job_app.py::warm --think-tokens 3000 --effort low" ;;
  probe)  CMD="modal run --detach chatcut_job_app.py::probe_rw --clip-url '$SRC' --out /tmp/bs/probe_rewatch.json" ;;
  th0)    CMD="modal run --detach chatcut_job_app.py::main --clip-url '$SRC' --brief 'just make it pop' --run-id h-th-think0 --think-tokens 0" ;;
  th3000) CMD="modal run --detach chatcut_job_app.py::main --clip-url '$SRC' --brief 'just make it pop' --run-id h-th-think3000 --think-tokens 3000" ;;
  thlow)  CMD="modal run --detach chatcut_job_app.py::main --clip-url '$SRC' --brief 'just make it pop' --run-id h-th-low --think-tokens 3000 --effort low" ;;
  nowatch) CMD="modal run --detach chatcut_job_app.py::main --clip-url '$SRC' --brief 'just make it pop' --run-id h-th-nowatch --think-tokens 0 --no-watch" ;;
  motion) CMD="modal run --detach chatcut_job_app.py::main --clip-url '$SRC' --brief 'just make it pop' --run-id h-motion-1 --think-tokens 3000" ;;
  car)    CMD="modal run --detach chatcut_job_app.py::main --clip-url '$SRC' --brief 'just make it pop' --run-id h-car-1 --think-tokens 3000" ;;
  *) echo "unknown stage"; exit 2 ;;
esac
rm -f "$LOG" "$RC"; nohup sh -c "$CMD > $LOG 2>&1; echo \$? > $RC" >/dev/null 2>&1 &
echo "launched $STAGE pid $! at $(date '+%H:%M:%S')  log=$LOG"
