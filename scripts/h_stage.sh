#!/bin/sh
# One stage per call, serial, a fresh presign each time. Refuses while any chatcut app runs.
#   h_stage.sh warm | warmlow | probe2 | probe1 | th0 | thlow | nowatch | motion | car | brief   (set -o pipefail; every exit code read bare)
#   brief: BRIEF_ID, BRIEF_KEY (S3 source key), BRIEF_FILE (the brief's text) from the environment — see h_brief.sh
#   DENSITY (default 2) is the rewatch density in frames per second for every job stage (Zac: 1 fps decides the 90s law)
set -u
set -o pipefail
cd "$(dirname "$0")/.." || exit 2
STAGE="$1"; mkdir -p /tmp/bs; LOG=/tmp/bs/h_$STAGE.log; RC=/tmp/bs/h_$STAGE.rc; DENSITY=${DENSITY:-2}
RUNNING=$(modal app list 2>/dev/null | /usr/bin/grep -i 'chatcut' | /usr/bin/grep -ci 'running\|ephemeral')
[ "$RUNNING" = "0" ] || { echo "REFUSED: $RUNNING chatcut app(s) running"; exit 3; }
key() { case "$1" in th0|th3000|th2000|thlow|nowatch|probe|probe2|probe1) echo "ab-sources/reliability-fixtures-v3/talking_head-f4195ca9.mp4";; motion) echo "ab-sources/reliability-fixtures-v3/motion-31fa2646.mp4";; car) echo "ab-sources/reliability-fixtures-v3/car_mid-0643be1c.mp4";; brief) echo "${BRIEF_KEY:-}";; esac; }
if [ "$STAGE" != "warm" ] && [ "$STAGE" != "warmlow" ]; then
  K=$(key $STAGE); [ -n "$K" ] || { echo "no source key for stage $STAGE"; exit 4; }
  SRC=$(python3 presign.py "$K" | cut -f1); [ -n "$SRC" ] || { echo "presign failed"; exit 4; }
  CODE=$(curl -s -o /dev/null -w '%{http_code}' "$SRC"); [ "$CODE" = "200" ] || { echo "presign GET -> $CODE"; exit 4; }
fi
case "$STAGE" in
  warm)   CMD="modal run --detach chatcut_job_app.py::warm --think-tokens 0" ;;
  warmlow) CMD="modal run --detach chatcut_job_app.py::warm --think-tokens 3000 --effort low" ;;
  # G: the control review on the clean timeline, then the three plants — at 2 fps (40 frames) and at 1 fps (20 frames), two records
  probe|probe2) CMD="modal run --detach chatcut_job_app.py::probe_rw --clip-url '$SRC' --out /tmp/bs/probe2.json --density-fps 2" ;;
  probe1) CMD="modal run --detach chatcut_job_app.py::probe_rw --clip-url '$SRC' --out /tmp/bs/probe1.json --density-fps 1" ;;
  th0)    CMD="modal run --detach chatcut_job_app.py::main --clip-url '$SRC' --brief 'just make it pop' --run-id h-th-think0 --think-tokens 0 --density-fps $DENSITY" ;;
  th3000) CMD="modal run --detach chatcut_job_app.py::main --clip-url '$SRC' --brief 'just make it pop' --run-id h-th-think3000 --think-tokens 3000 --density-fps $DENSITY" ;;
  thlow)  CMD="modal run --detach chatcut_job_app.py::main --clip-url '$SRC' --brief 'just make it pop' --run-id h-th-low --think-tokens 3000 --effort low --density-fps $DENSITY" ;;
  # COLD BY DESIGN (Zac, 2026-09-18): no ping, no pinning — its own ~72k prefix, one measurement
  nowatch) CMD="modal run --detach chatcut_job_app.py::main --clip-url '$SRC' --brief 'just make it pop' --run-id h-th-nowatch --think-tokens 0 --no-watch --density-fps $DENSITY" ;;
  motion) CMD="modal run --detach chatcut_job_app.py::main --clip-url '$SRC' --brief 'just make it pop' --run-id h-motion-1 --think-tokens 0 --density-fps $DENSITY" ;;
  car)    CMD="modal run --detach chatcut_job_app.py::main --clip-url '$SRC' --brief 'just make it pop' --run-id h-car-1 --think-tokens 0 --density-fps $DENSITY" ;;
  brief)  [ -n "${BRIEF_ID:-}" ] && [ -f "${BRIEF_FILE:-/nonexistent}" ] || { echo "brief stage needs BRIEF_ID and an existing BRIEF_FILE"; exit 4; }
          LOG=/tmp/bs/h_brief_$BRIEF_ID.log; RC=/tmp/bs/h_brief_$BRIEF_ID.rc
          CMD="modal run --detach chatcut_job_app.py::main --clip-url '$SRC' --brief-file '$BRIEF_FILE' --run-id h-brief-$BRIEF_ID --think-tokens 0 --density-fps $DENSITY" ;;
  *) echo "unknown stage"; exit 2 ;;
esac
rm -f "$LOG" "$RC"; nohup sh -c "$CMD > $LOG 2>&1; echo \$? > $RC" >/dev/null 2>&1 &
echo "launched $STAGE pid $! at $(date '+%H:%M:%S') from $(git rev-parse --short HEAD 2>/dev/null)  log=$LOG"
