#!/bin/sh
# THE BATCH (Zac, Part 3, 2026-09-18): ping -> [preflight inside the job] -> H1 talking-head thinking-off
# -> talking-head effort-low -> G on JPEG -> no-speech -> Zac's clip -> NO-WATCH (only with A green both scopes).
# Stop rules: A red on H1 (either scope) stops everything; $12 cumulative stops; any API refusal stops.
# EVERY EXIT CODE IS READ BARE: pipefail is on and no verdict is read through a pipe (a `| tee` once
# reported tee's 0 for a 400 and the batch went on). One report after the batch.
set -u
set -o pipefail
D=$(cd "$(dirname "$0")/.." && pwd); SC=$D/scripts
B=/tmp/batch; mkdir -p $B; LEDGER=$B/ledger.txt; : > $LEDGER; T0=$(date +%s)
log() { echo "$*" >> $LEDGER; echo "$*"; }
idle() { while [ "$(modal app list 2>/dev/null | /usr/bin/grep -i 'chatcut' | /usr/bin/grep -ci 'running\|ephemeral')" != "0" ]; do sleep 10; done; }
spend() { python3 "$SC/batch_spend.py"; }
over_cap() { python3 -c "import sys; sys.exit(0 if float(sys.argv[1]) > 12.0 else 1)" "$(spend)"; }
stage() { name=$1; runid=$2; out=$3; idle; sh $SC/h_stage.sh $name >> $LEDGER 2>&1; sh $SC/h_wait.sh "$runid" "$out" >> $LEDGER 2>&1; [ -f "$out" ] || { log "NO RECORD for $name"; return 1; }; return 0; }
verdict() { python3 "$SC/batch_verdict.py" "$1" > $B/verdict.txt; rc=$?; log "$(cat $B/verdict.txt)"; return $rc; }
mp4() { runid=$1; out=$2; (cd $D && modal run chatcut_read_result.py --run-id "$runid-mp4" --out "$out.json" > $B/read_$runid.log 2>&1); python3 "$SC/batch_mp4.py" "$out" > $B/mp4.txt; log "$(cat $B/mp4.txt)"; }
cap_or_stop() { if over_cap; then log "STOP: spend cap (\$$(spend))"; exit 6; fi; log "spend so far: \$$(spend)"; }
log "BATCH START $(date '+%H:%M:%S')"
# 1. the ping (the 1h watch-end breakpoint; its system text is what the preflight compares against)
idle; sh $SC/h_stage.sh warm >> $LEDGER 2>&1; while [ ! -f /tmp/bs/h_warm.rc ]; do sleep 10; done; sleep 5
WL=$(/usr/bin/grep -E "  WARM            :" /tmp/bs/h_warm.log | tail -1); log "$WL"
if /usr/bin/grep -q "Credit balance is too low" /tmp/bs/h_warm.log; then log "STOP: the ping was refused (credits)"; exit 3; fi
echo "$WL" | /usr/bin/grep -qE "write=[0-9]+ .* rc=0" || { log "STOP: the ping did not succeed: $WL"; exit 3; }
# 2. H1 — thinking off: the preflight, the cross-run proof, the within-run assertion
stage th0 h-th-think0 $B/th0.json || exit 4
verdict $B/th0.json; rc=$?
[ $rc -eq 0 ] || { log "STOP: A is red on H1 (rc=$rc) — nothing else fires"; exit 5; }
mp4 h-th-think0 $B/th0.mp4; cap_or_stop
# 3. F's second arm: effort low (the API refuses a token budget on this model)
stage thlow h-th-low $B/thlow.json || exit 4
verdict $B/thlow.json; rc=$?; [ $rc -ne 2 ] || { log "STOP: API refusal on the low arm"; exit 5; }
mp4 h-th-low $B/thlow.mp4; cap_or_stop
# 4. G on JPEG sheets — no kill of ours below the run bound
idle; sh $SC/h_stage.sh probe >> $LEDGER 2>&1; while [ ! -f /tmp/bs/h_probe.rc ]; do sleep 15; done; cp /tmp/bs/probe_rewatch.json $B/probe.json 2>/dev/null
log "$(/usr/bin/grep -E 'REVIEW NAMED|PREVIEW_TIMELINE|EXPORT\+INSPECT' /tmp/bs/h_probe.log)"; cap_or_stop
# 5. no-speech, 6. Zac's clip
stage motion h-motion-1 $B/motion.json || exit 4; verdict $B/motion.json; rc=$?; [ $rc -ne 2 ] || exit 5; mp4 h-motion-1 $B/motion.mp4; cap_or_stop
stage car h-car-1 $B/car.json || exit 4; verdict $B/car.json; rc=$?; [ $rc -ne 2 ] || exit 5; mp4 h-car-1 $B/car.mp4; cap_or_stop
# 7. the no-watch run (A was green both scopes on H1, or we would not be here)
stage nowatch h-th-nowatch $B/nowatch.json || exit 4; verdict $B/nowatch.json; mp4 h-th-nowatch $B/nowatch.mp4
python3 "$SC/batch_pair.py" > $B/pair.txt; log "$(cat $B/pair.txt)"
log "spend total: \$$(spend)"; log "BATCH DONE $(date '+%H:%M:%S') after $(( $(date +%s) - T0 ))s"
