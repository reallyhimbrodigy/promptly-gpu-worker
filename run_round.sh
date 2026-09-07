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
# PER-FIXTURE MODEL. The agent's only job is judgement now — set_spec and
# rule_all_beats — because execution moved into the harness. Run M measured
# Haiku's verdicts as indistinguishable from Sonnet's (19/19 distinct, 19/19
# citing their own beat) at 78% less; the reason Haiku failed then was
# EXECUTION, and the agent no longer executes. talking_head is the expensive
# source, so it is the one that carries the test.
# ALL FIVE ON HAIKU. Measured on pet_video, one frozen mount, viral brief:
# Sonnet $0.2856 for 3 placements, Haiku $0.0331 for 6 — 88% cheaper and TWICE
# the output, with the extra entirely `text`, the family Sonnet placed ZERO of
# on a brief demanding captions on every claim. No-speech is 46.5% of real
# traffic and it was the expensive half; talking_head at $0.0667 was already the
# cheapest of the five.
MODELS = {k: "claude-haiku-4-5" for k in BRIEFS}
for name, brief in BRIEFS.items():
    print(f"{name}\t{d[name]['key']}\t{brief}\t{MODELS.get(name, 'claude-sonnet-5')}")
PY
[ -s "$OUT/plan.tsv" ] || { echo "no plan — fixtures not staged"; exit 1; }

# ── THE MOUNT MUST BE IDENTICAL ACROSS EVERY ARM ────────────────────────────
# Modal mounts agentic_editor_app.py per LAUNCH, and launches here are
# sequential. Editing the file mid-round therefore gives different arms
# different code — a mixed cohort that cannot be scored. That has now
# invalidated two rounds (2 and 7): both times I fixed something real while a
# round was still launching, and both times the round became unreadable.
#
# The hash is captured BEFORE the first launch and re-checked before each one.
# A round that cannot guarantee one codebase refuses to continue rather than
# producing a number nobody can trust.
MOUNT_SHA="$(shasum -a 256 agentic_editor_app.py | cut -c1-16)"
echo "[mount] agentic_editor_app.py @ $MOUNT_SHA"
echo "$MOUNT_SHA" > "$OUT/mount_sha.txt"

while IFS=$'\t' read -r name key brief model; do
  [ -z "$name" ] && continue
  IFS=$'\t' read -r S O K < <(python3 presign.py "$key")
  if [ -z "${S:-}" ]; then
    echo "$name PRESIGN_FAILED" >> "$OUT/appmap.txt"; continue
  fi
  now_sha="$(shasum -a 256 agentic_editor_app.py | cut -c1-16)"
  if [ "$now_sha" != "$MOUNT_SHA" ]; then
    echo "[ABORT] agentic_editor_app.py changed mid-round ($MOUNT_SHA -> $now_sha)."
    echo "        Arms would mount different code and the round is unscoreable."
    echo "        Re-run the whole round on a frozen tree."
    echo "$name MOUNT_DRIFT" >> "$OUT/appmap.txt"
    exit 2
  fi
  echo "[launch] $name  model=${model:-claude-sonnet-5}"
  modal run --detach agentic_editor_app.py --source "$key" --brief "$brief" \
    --model "${model:-claude-sonnet-5}" \
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
# THE SIGNATURE ON EVERY FIXTURE, not just the one being read closely. A run at
# half the turns and two-thirds the placements of its neighbours is green for
# the wrong reason — it did less, and every gate passes because everything it
# DID do was correct. Printed per fixture so the variance question accumulates
# evidence across rounds instead of being re-litigated from one log at a time.
import re as _re
print()
print(f"  {'fixture':18} {'turns':>6} {'cost':>9} {'placed':>7}  families")
for _n in sorted(res):
    _p = os.path.join(out, f"{_n}.log")
    _t = open(_p, encoding='utf-8', errors='ignore').read() if os.path.exists(_p) else ''
    _m = _re.search(r"RUN SIGNATURE   : turns (\d+)\s+cost \$([\d.]+)\s+placements (\d+)\s+\[([^\]]*)\]", _t)
    if _m:
        print(f"  {_n:18} {_m.group(1):>6} {'$'+_m.group(2):>9} {_m.group(3):>7}  [{_m.group(4)}]")
    else:
        print(f"  {_n:18} {'—':>6} {'—':>9} {'—':>7}  (no signature — run did not reach the summary)")
print()
for n, v in sorted(res.items()):
    print(f"  {n:<18} ok={v['ok']} kept={v['kept_ratio']} placements={v['placements']}"
          + (f" VIOLATIONS={v['contract_violations']}" if v["contract_violations"] else ""))
PY
echo "ROUND $ROUND COLLECTED"
