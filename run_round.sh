#!/usr/bin/env bash
# ONE ROUND OF THE RELIABILITY GATE — five fixtures, five vibes.
#
# Sources and briefs come from the STAGED MANIFEST, not from hardcoded keys.
# The keys are content-addressed, so regenerating a fixture changes its key and
# every hardcoded copy silently points at the old bytes — which is how four
# fixtures stayed at 540x960 for three rounds while the harness logged
# `wrong_resolution` and the gate called the rounds green.
#
# Presigning happens HERE, with the system python3: the modal CLI ships its own
# interpreter without boto3, and the container is meant to hold no credentials.
set -uo pipefail
cd "$(dirname "$0")"
ROUND="${1:?usage: run_round.sh <round-number>}"
OUT="/tmp/fixtures/round${ROUND}"; mkdir -p "$OUT"; : > "$OUT/appmap.txt"

python3 - "$OUT" <<'PY' > "$OUT/plan.tsv"
import json, sys
BRIEFS = {
 "talking_head": "Punchy and direct. Fast cuts — cut the filler and dead air hard. Big bold captions, hit the numbers. This should feel urgent.",
 "music": "Let it breathe. Cinematic and moody, cuts landing on the beat, no captions at all.",
 "screen_recording": "Clean and professional. Few cuts, subtle overlays only, no sound effects. Calm and legible.",
 "product_shot": "Premium and slow. One hero moment, restrained motion, nothing busy.",
 "pet_video": "Playful and quick. Fun energy, snappy cuts, a sound effect where it lands.",
}
d = json.load(open("/tmp/fixtures/staged.json"))
missing = sorted(set(BRIEFS) - set(d))
if missing:
    sys.stderr.write(f"FIXTURE(S) NOT STAGED: {missing}\n"); sys.exit(1)
for name, brief in BRIEFS.items():
    print(f"{name}\t{d[name]['key']}\t{brief}")
PY
[ -s "$OUT/plan.tsv" ] || { echo "no plan — fixtures not staged"; exit 1; }

while IFS=$'\t' read -r name key brief; do
  [ -z "$name" ] && continue
  IFS=$'\t' read -r S O K < <(python3 presign.py "$key")
  if [ -z "${S:-}" ]; then
    echo "$name PRESIGN_FAILED" >> "$OUT/appmap.txt"; continue
  fi
  echo "[launch] $name"
  modal run --detach agentic_editor_app.py --source "$key" --brief "$brief" \
    --src-url "$S" --out-url "$O" --out-key "$K" > "$OUT/$name.log" 2>&1
  id="$(grep -oE 'ap-[A-Za-z0-9]+' "$OUT/$name.log" | head -1)"
  [ -n "$id" ] && echo "$name $id" >> "$OUT/appmap.txt" \
                || echo "$name LAUNCH_FAILED" >> "$OUT/appmap.txt"
done < "$OUT/plan.tsv"

echo "[wait] polling until 0 agentic tasks"
for i in $(seq 1 100); do
  live="$(modal app list 2>/dev/null | awk '/agentic/' | grep -cE '│ +[1-9][0-9]* +│')"
  echo "[poll $i] holding tasks: ${live:-?}"
  [ "${live:-1}" = "0" ] && break
  sleep 30
done

# SCORE THE ROUND THROUGH THE GATE ITSELF, not by eye. Contract violations,
# passthroughs and unbalanced accounting all fail here rather than being read
# past in a log.
python3 - "$OUT" <<'PY'
import json, re, sys, os, importlib.util
out = sys.argv[1]
spec = importlib.util.spec_from_file_location("rg", "reliability_gate.py")
rg = importlib.util.module_from_spec(spec); spec.loader.exec_module(rg)
res = {}
for name in rg.REQUIRED_SOURCES:
    p = os.path.join(out, f"{name}.log")
    if not os.path.exists(p):
        continue
    t = open(p, encoding="utf-8", errors="ignore").read()
    ok = bool(re.search(r"^  ok +: True", t, re.M))
    kept = re.search(r"kept [\d.]+s of [\d.]+s \(([\d.]+)\)", t)
    pm = re.search(r"PLACEMENT MANIFEST — (\d+) declared", t)
    cv = re.findall(r"(wrong_resolution|no_audio_stream|output_has_no_speech|"
                    r"no_output|speech_loss_severe): ?([^\n]{0,50})", t)
    unbal = re.findall(r"accounting_unbalanced: ([^\n]{0,70})", t)
    res[name] = {"ok": ok,
                 "kept_ratio": float(kept.group(1)) if kept else None,
                 "placements": int(pm.group(1)) if pm else 0,
                 "contract_violations": [f"{a}: {b}" for a, b in cv] + unbal}
green, why = rg.round_is_green(res)
json.dump({"result": res, "green": green, "why": why},
          open(os.path.join(out, "score.json"), "w"), indent=1)
print(f"\nROUND {out[-1]} GREEN={green}")
print(f"  {why}")
for n, v in sorted(res.items()):
    print(f"  {n:<18} ok={v['ok']} kept={v['kept_ratio']} placements={v['placements']}"
          + (f" VIOLATIONS={v['contract_violations']}" if v["contract_violations"] else ""))
PY
echo "ROUND $ROUND COLLECTED"
