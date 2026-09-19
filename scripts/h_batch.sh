#!/bin/sh
# THE BATCH (Zac, 2026-09-18, on his go, inside one hour):
#   ping (off: the job's thinking) -> G at 2 fps WITH ITS NEGATIVE CONTROL -> G at 1 fps -> H1 thinking-off -> ping low
#   -> H1 effort-low -> no-speech -> Zac's clip -> NO-WATCH (cold, its own prefix, BY DESIGN) -> up to three production
#   briefs from Builder-2's fixture file (a preset+modifier, a no-captions constraint, one structured brief).
# Stop rules: A red on H1 (either scope) stops everything; a cold write on G's control (the same cross-run fault,
# seen before H1 spends) stops; $12 cumulative stops; any API refusal stops.
# EVERY EXIT CODE IS READ BARE: pipefail is on and no verdict is read through a pipe (a `| tee` once reported tee's
# 0 for a 400 and the batch went on). One report after the batch.
set -u
set -o pipefail
D=$(cd "$(dirname "$0")/.." && pwd); SC=$D/scripts
B=/tmp/batch; mkdir -p $B $B/sheets; LEDGER=$B/ledger.txt; T0=$(date +%s)
# START=<stage> resumes after a launch-side failure (Modal answered "app is stopped or disabled" at a spawn,
# 2026-09-18) without re-running the stages whose records already exist; the ledger is appended, not reset.
START=${START:-ping}; SKIP=1; [ "$START" = "ping" ] && SKIP=0 && : > $LEDGER
# FRESH RUN IDS PER LAUNCH (see h_stage.sh RUNSFX): the suffix is this launch's clock unless the caller resumes with one
export RUNSFX=${RUNSFX:--$(date +%H%M)}
END=${END:-briefs}; DONE=0
at() { [ "$SKIP" = "1" ] && [ "$1" = "$START" ] && SKIP=0; [ "$DONE" = "1" ] && return 1; [ "$1" = "$END" ] && DONE=1; [ "$SKIP" = "0" ]; }
log() { echo "$*" >> $LEDGER; echo "$*"; }
idle() { while [ "$(modal app list 2>/dev/null | /usr/bin/grep -i 'chatcut' | /usr/bin/grep -ci 'running\|ephemeral')" != "0" ]; do sleep 10; done; }
spend() { python3 "$SC/batch_spend.py"; }
over_cap() { python3 -c "import sys; sys.exit(0 if float(sys.argv[1]) > 12.0 else 1)" "$(spend)"; }
stage() { name=$1; runid=$2; out=$3; idle; sh $SC/h_stage.sh $name >> $LEDGER 2>&1; sh $SC/h_wait.sh "$runid" "$out" >> $LEDGER 2>&1; [ -f "$out" ] || { log "NO RECORD for $name"; return 1; }; return 0; }
verdict() { python3 "$SC/batch_verdict.py" "$1" > $B/verdict.txt; rc=$?; log "$(cat $B/verdict.txt)"; return $rc; }
mp4() { runid=$1; out=$2; (cd $D && modal run chatcut_read_result.py --run-id "$runid-mp4" --out "$out.json" > $B/read_$runid.log 2>&1); python3 "$SC/batch_mp4.py" "$out" > $B/mp4.txt; log "$(cat $B/mp4.txt)"; }
cap_or_stop() { if over_cap; then log "STOP: spend cap (\$$(spend))"; exit 6; fi; log "spend so far: \$$(spend)"; }
waitrc() { f=$1; lim=${2:-900}; t=$(date +%s); while [ ! -f "$f" ]; do sleep 10; [ $(( $(date +%s) - t )) -gt $lim ] && { log "STOP: launcher for $f wrote no result in ${lim}s (the modal client died: 'app is stopped or disabled' twice today)"; exit 7; }; done; }
# THE PING, per arm: it must carry the job's thinking and effort (a ping at adaptive leaves no entry a job at disabled can read)
ping() { st=$1; [ "${SKIP_PING:-0}" = "1" ] && { log "ping $st SKIPPED (the arm's 1h entry is alive)"; return 0; }; idle; rm -f /tmp/bs/h_$st.rc; sh $SC/h_stage.sh $st >> $LEDGER 2>&1; waitrc /tmp/bs/h_$st.rc 900; sleep 5
  WL=$(/usr/bin/grep -E "  WARM            :" /tmp/bs/h_$st.log | tail -1); log "$WL"
  if /usr/bin/grep -q "Credit balance is too low" /tmp/bs/h_$st.log; then log "STOP: the ping was refused (credits)"; exit 3; fi
  echo "$WL" | /usr/bin/grep -qE "write=[0-9]+ .* rc=0" || { log "STOP: the ping did not succeed: $WL"; exit 3; }; }
# G: the probe's record lands in /tmp/bs/<stage>.json; its sheets (control and planted) come out of the results store for Zac's eye
probe() { st=$1; idle; rm -f /tmp/bs/h_$st.rc; sh $SC/h_stage.sh $st >> $LEDGER 2>&1; waitrc /tmp/bs/h_$st.rc 1500; cp /tmp/bs/$st.json $B/$st.json 2>/dev/null; [ -f $B/$st.json ] || { log "NO RECORD for $st"; return 1; }; log "$(/usr/bin/grep -E '  CONTROL  |  G @ ' /tmp/bs/h_$st.log)"; return 0; }
sheets() { key=$1; st=$2; (cd $D && modal run chatcut_read_result.py --run-id "$key" --out "$B/${st}_full.json" > $B/read_$st.log 2>&1); python3 "$SC/batch_sheets.py" "$B/${st}_full.json" "$B/sheets/$st" > $B/sheets.txt; log "$(cat $B/sheets.txt)"; }
log "BATCH START $(date '+%H:%M:%S') run ids *$RUNSFX"
# 1. the off-arm ping (the 1h watch-end breakpoint; its system text and thinking are what the preflight compares against)
if at ping; then ping warm; fi
# 2. G at 2 fps with its negative control (the control's call is the first job-shaped call after the ping: a cold write here is the cross-run fault, before H1 spends)
if at probe2; then
probe probe2 || exit 4
verdict $B/probe2.json; rc=$?; [ $rc -eq 0 ] || { log "STOP: A is red on G (rc=$rc)"; exit 5; }
sheets probe-rewatch-2fps probe2; cap_or_stop
fi
# 3. G at 1 fps (20 frames): the result that decides whether the 90s law is reachable on ChatCut's serial preview
if at probe1; then
probe probe1 || exit 4
verdict $B/probe1.json; rc=$?; [ $rc -ne 2 ] || { log "STOP: API refusal on G at 1 fps"; exit 5; }
sheets probe-rewatch-1fps probe1; cap_or_stop
fi
# 4. H1 — thinking off: the preflight, the cross-run proof, the within-run assertion
if at th0; then
ping warm                                   # the off ping again: a restart from here, or the probes, must not leave the low ping as the preflight's reference
stage th0 h-th-think0$RUNSFX $B/th0.json || exit 4
verdict $B/th0.json; rc=$?
[ $rc -eq 0 ] || { log "STOP: A is red on H1 (rc=$rc) — nothing else fires"; exit 5; }
mp4 h-th-think0$RUNSFX $B/th0.mp4; cap_or_stop
fi
# 5. F's second arm: effort low (the API refuses a token budget on this model) — its own ping, same thinking/effort
if at thlow; then
ping warmlow
stage thlow h-th-low$RUNSFX $B/thlow.json || exit 4
verdict $B/thlow.json; rc=$?; [ $rc -ne 2 ] || { log "STOP: API refusal on the low arm"; exit 5; }
mp4 h-th-low$RUNSFX $B/thlow.mp4; cap_or_stop
fi
# 6. no-speech, 7. Zac's clip (both on the off arm). THE OFF PING RUNS AGAIN FIRST: the preflight compares against the
# LAST ping, which after thlow is the low one, and an off-arm job against a low ping is refused (2026-09-18). A re-ping reads
# the live 1h entry (~$0.07), it does not rewrite it.
if at motion; then ping warm; stage motion h-motion-1$RUNSFX $B/motion.json || exit 4; verdict $B/motion.json; rc=$?; [ $rc -ne 2 ] || exit 5; mp4 h-motion-1$RUNSFX $B/motion.mp4; cap_or_stop; fi
if at car; then stage car h-car-1$RUNSFX $B/car.json || exit 4; verdict $B/car.json; rc=$?; [ $rc -ne 2 ] || exit 5; mp4 h-car-1$RUNSFX $B/car.mp4; cap_or_stop; fi
# 8. the no-watch run: COLD BY DESIGN — its own prefix, no ping, no pinning; the verdict names the cold write and still reds a within-run miss
if at nowatch; then stage nowatch h-th-nowatch$RUNSFX $B/nowatch.json || exit 4; verdict $B/nowatch.json; rc=$?; [ $rc -ne 2 ] || exit 5; mp4 h-th-nowatch$RUNSFX $B/nowatch.mp4; cap_or_stop; fi
# 9. up to three production briefs from Builder-2's file — each a job on the off arm, the brief travelling as a file
if at briefs; then
python3 "$SC/batch_briefs.py" "$D/fixtures/production_briefs.v1.jsonl" /tmp/bs > $B/briefs.tsv 2> $B/briefs_listing.txt; log "$(cat $B/briefs_listing.txt)"
TAB="$(printf '\t')"
while IFS="$TAB" read -r bid bkey bfile bslot; do
  [ -n "$bid" ] || continue
  log "BRIEF $bid ($bslot) on $bkey"
  idle; BRIEF_ID=$bid BRIEF_KEY=$bkey BRIEF_FILE=$bfile sh $SC/h_stage.sh brief >> $LEDGER 2>&1
  sh $SC/h_wait.sh "h-brief-$bid$RUNSFX" "$B/brief_$bid.json" >> $LEDGER 2>&1
  [ -f "$B/brief_$bid.json" ] || { log "NO RECORD for brief $bid"; continue; }
  verdict $B/brief_$bid.json; rc=$?; [ $rc -ne 2 ] || { log "STOP: API refusal on brief $bid"; exit 5; }
  mp4 "h-brief-$bid$RUNSFX" "$B/brief_$bid.mp4"; cap_or_stop
done < $B/briefs.tsv
fi
python3 "$SC/batch_pair.py" > $B/pair.txt; log "$(cat $B/pair.txt)"
log "spend total: \$$(spend)"; log "BATCH DONE $(date '+%H:%M:%S') after $(( $(date +%s) - T0 ))s"
