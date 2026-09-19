#!/bin/sh
# THE FOUR-RUN WARM WINDOW (Zac, 2026-09-19), serial, run bound 600s for these only.
#   1. th0low   H1 talking-head, thinking DISABLED + effort LOW — the untested cell
#   2. haiku    same fixture and brief, thinking disabled, its own prefix (a model's cache entry is its own)
#   3. nowatch  the no-watch arm on the turn-1 tools fix (cold by design)
#   4. car      Zac's clip on the turn-1 tools fix
# NO PINGS (Zac, 2026-09-19). Each Sonnet cell COLD-WRITES ITS OWN PREFIX at the 5-minute rate
# (--prefix-ttl 5m): 226k at $3.75/M is $0.85, against $1.36 for a 1h ping the cell then reads — and it
# removes the preflight's dependency on a ping whose thinking and effort must match. Haiku writes its own
# prefix at Haiku's rate because a model's cache entry is its own; no-watch is cold by design.
# WITHIN-RUN CACHING IS UNAFFECTED: calls 2+ still assert they read >= 0.95x of what call 1 established.
# Every exit code is read bare (pipefail, verdict from a file) and Modal runs stay serial.
set -u
set -o pipefail
D=$(cd "$(dirname "$0")/.." && pwd); SC=$D/scripts
B=/tmp/window; mkdir -p $B; LEDGER=$B/ledger.txt; T0=$(date +%s)
export RUNSFX=${RUNSFX:--w$(date +%H%M)}
export BOUND=${BOUND:-600}
export TTL=${TTL:-5m}              # each Sonnet cell writes its own prefix; no ping stands behind it
: > $LEDGER
log() { echo "$*" >> $LEDGER; echo "$*"; }
idle() { while [ "$(modal app list 2>/dev/null | /usr/bin/grep -i 'chatcut' | /usr/bin/grep -ci 'running\|ephemeral')" != "0" ]; do sleep 10; done; }
waitrc() { f=$1; lim=${2:-1200}; t=$(date +%s); while [ ! -f "$f" ]; do sleep 10; [ $(( $(date +%s) - t )) -gt $lim ] && { log "STOP: launcher for $f wrote no result in ${lim}s"; exit 7; }; done; }
run() { st=$1; rid=$2; out=$B/$st.json; idle; sh $SC/h_stage.sh $st >> $LEDGER 2>&1; sh $SC/h_wait.sh "$rid$RUNSFX" "$out" >> $LEDGER 2>&1
  [ -f "$out" ] || { log "NO RECORD for $st"; return 1; }
  python3 "$SC/batch_verdict.py" "$out" > $B/verdict.txt; rc=$?; log "$(cat $B/verdict.txt)"
  log "$(/usr/bin/grep -E '  TOOL BLOCK      :|  THINKING BLOCKS :|  RUN BOUND       :|  LAW MISS' /tmp/bs/h_$st.log | head -6)"
  (cd $D && modal run chatcut_read_result.py --run-id "$rid$RUNSFX-mp4" --out "$B/$st.mp4.json" > $B/read_$st.log 2>&1)
  python3 "$SC/batch_mp4.py" "$B/$st.mp4" "$out" > $B/mp4.txt; log "$(cat $B/mp4.txt)"
  [ $rc -ne 2 ] || { log "STOP: API refusal on $st"; exit 5; }; return 0; }
log "WINDOW START $(date '+%H:%M:%S')  run ids *$RUNSFX  bound ${BOUND}s  from $(git -C $D rev-parse --short HEAD)"
run th0low  h-th0low               # thinking disabled + effort LOW — the untested cell
run car     h-car-1                # Zac's clip on the turn-1 tools fix
run haiku   h-haiku                # its own prefix, cold at Haiku's rate
run nowatch h-th-nowatch           # cold by design
log "WINDOW DONE $(date '+%H:%M:%S') after $(( $(date +%s) - T0 ))s"
