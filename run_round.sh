#!/usr/bin/env bash
# ONE ROUND OF THE RELIABILITY GATE — five fixtures, five vibes.
#
# WHY THIS EXISTS AS A SCRIPT. Round 1 was launched as backgrounded `modal run`
# under a shell that then exited. The local clients were killed; the CONTAINERS
# kept running and kept billing, and the results — which `.remote()` returns to
# the client — went nowhere. Four complete edits were paid for and lost, and I
# had to reconstruct them from `modal app logs`.
#
# Two fixes, both structural:
#   1. --detach : Modal owns the run's lifetime, not the local client. Killing
#      this script can no longer strand a container or discard a result.
#   2. setsid   : the collector is its own session leader, so a parent exiting
#      cannot signal it.
# And the completion test is `modal app list` showing zero tasks — never "the
# local process returned", which is exactly the assumption that failed.
set -uo pipefail
cd "$(dirname "$0")"
P="ab-sources/reliability-fixtures-v1"
ROUND="${1:?usage: run_round.sh <round-number>}"
OUT="/tmp/fixtures/round${ROUND}"
mkdir -p "$OUT"
: > "$OUT/appmap.txt"

launch () {  # name key vibe
  local n="$1" k="$2" v="$3"
  echo "[launch] $n"
  modal run --detach agentic_editor_app.py --source "$k" --brief "$v" \
    > "$OUT/$n.launch.log" 2>&1
  local id
  id="$(grep -oE 'ap-[A-Za-z0-9]+' "$OUT/$n.launch.log" | head -1)"
  # A LAUNCH THAT YIELDED NO APP ID IS A FAILED LAUNCH, not a silent skip. A
  # missing row here would later read as "that fixture had no result", which the
  # gate correctly fails — but for the wrong reason, and undiagnosably.
  if [ -z "$id" ]; then
    echo "[launch] !! $n produced NO app id — launch failed:" >&2
    tail -5 "$OUT/$n.launch.log" >&2
    echo "$n LAUNCH_FAILED" >> "$OUT/appmap.txt"
    return 1
  fi
  echo "$n $id" >> "$OUT/appmap.txt"
}

launch talking_head "$P/talking_head-eeb40bc7.mp4" \
  "Punchy and direct. Fast cuts — cut the filler and dead air hard. Big bold captions, hit the numbers. This should feel urgent."
launch music "$P/music-b7893d5c.mp4" \
  "Let it breathe. Cinematic and moody, cuts landing on the beat, no captions at all."
launch screen_recording "$P/screen_recording-1b22be38.mp4" \
  "Clean and professional. Few cuts, subtle overlays only, no sound effects. Calm and legible."
launch product_shot "$P/product_shot-fc9951d5.mp4" \
  "Premium and slow. One hero moment, restrained motion, nothing busy."
launch pet_video "$P/pet_video-977757fc.mp4" \
  "Playful and quick. Fun energy, snappy cuts, a sound effect where it lands."

echo "[wait] polling modal app list until 0 agentic tasks (never 'the client returned')"
for i in $(seq 1 80); do
  live="$(modal app list 2>/dev/null | awk '/agentic/' | grep -cE '│ +[1-9][0-9]* +│')"
  echo "[poll $i] agentic apps holding tasks: ${live:-?}"
  [ "${live:-1}" = "0" ] && break
  sleep 30
done

echo "[collect] pulling each run's stdout from Modal"
while read -r n id; do
  [ "$id" = "LAUNCH_FAILED" ] && continue
  ( modal app logs "$id" > "$OUT/$n.log" 2>&1 ) &
  sleep 1
done < "$OUT/appmap.txt"
sleep 60
pkill -P $$ -f "modal app logs" 2>/dev/null
echo "ROUND $ROUND COLLECTED"
wc -l "$OUT"/*.log 2>/dev/null
