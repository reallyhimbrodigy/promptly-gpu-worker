#!/bin/sh
set -o pipefail
# wait for the container to stop, then read the record for RUNID into OUT
cd "$(dirname "$0")/.." || exit 2
RUNID="$1"; OUT="$2"; T0=$(date +%s); sleep 45
while [ "$(modal app list 2>/dev/null | /usr/bin/grep -i 'chatcut' | /usr/bin/grep -ci 'running\|ephemeral')" != "0" ]; do sleep 15; done
echo "idle after $(( $(date +%s) - T0 ))s at $(date '+%H:%M:%S')"
modal run chatcut_read_result.py --run-id "$RUNID" --out "$OUT" > /tmp/bs/read_$RUNID.log 2>&1
[ -f "$OUT" ] && echo "RECORD $OUT" || { echo "NO RECORD"; /usr/bin/grep -E 'ABSENT|Error' /tmp/bs/read_$RUNID.log | head -2; }
echo "WAIT DONE"
