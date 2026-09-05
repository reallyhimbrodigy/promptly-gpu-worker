#!/usr/bin/env bash
# AGENTIC vs MOODREEL — same source, same request, real production jobs.
# The OLD arm is not re-run: those ten jobs already completed in production and
# their rendered_video_url IS the baseline. Re-running would compare against a
# replay instead of the artifact the user actually received.
set -uo pipefail
cd "$(dirname "$0")"
OUT=/tmp/fixtures/ab; mkdir -p "$OUT/runs"; : > "$OUT/appmap.txt"
python3 - <<'PY' > "$OUT/launch.tsv"
import json
d=json.load(open("/tmp/fixtures/ab/staged.json"))
for jid,m in sorted(d.items()):
    print(f"{jid}\t{m['key']}\t{m['vibe']}")
PY
while IFS=$'\t' read -r jid key vibe; do
  [ -z "$jid" ] && continue
  echo "[launch] $jid"
  modal run --detach agentic_editor_app.py --source "$key" --brief "$vibe" \
    > "$OUT/runs/$jid.log" 2>&1
  id="$(grep -oE 'ap-[A-Za-z0-9]+' "$OUT/runs/$jid.log" | head -1)"
  if [ -z "$id" ]; then
    echo "$jid LAUNCH_FAILED" >> "$OUT/appmap.txt"
    echo "[launch] !! $jid failed:" >&2; tail -4 "$OUT/runs/$jid.log" >&2
  else
    echo "$jid $id" >> "$OUT/appmap.txt"
  fi
done < "$OUT/launch.tsv"
echo "[wait] polling until 0 agentic tasks"
for i in $(seq 1 100); do
  live="$(modal app list 2>/dev/null | awk '/agentic/' | grep -cE '│ +[1-9][0-9]* +│')"
  echo "[poll $i] holding tasks: ${live:-?}"
  [ "${live:-1}" = "0" ] && break
  sleep 30
done
echo "AB COLLECTED"
