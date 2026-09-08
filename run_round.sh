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
# EVERY MOUNTED PATH, not just the app file.
#
# This hashed agentic_editor_app.py ALONE and called it "the mount". The image
# also mounts src/remotion (368 files — the entire Remotion source, where the
# caption port lives), remotion_batch.mjs, knowledge/, the skills tree, the
# sound assets, the asset inventory, moodreel_editor.py and type_registries.py.
# Eight paths uncovered. PROVEN blind: appending a line to remotion_batch.mjs
# left the old sha byte-identical at 3ebafe2294660e18 while the fingerprint
# moved 144fc21ccbbe2bab -> d33f8959e4a51076.
#
# Rounds 32 and 33 differ 6.1x on caption paint under shas that could not have
# distinguished them. A cohort guard blind to the files being changed is worse
# than no guard: it certifies two arms as identical code when they are not.
MOUNT_SHA="$(python3 mount_fingerprint.py)"
if [ -z "$MOUNT_SHA" ]; then
  echo "[ABORT] mount_fingerprint.py produced nothing — refusing to run a round"
  echo "        whose cohort integrity cannot be established."
  exit 2
fi
echo "[mount] $(python3 mount_fingerprint.py --verbose | tail -1)"
echo "$MOUNT_SHA" > "$OUT/mount_sha.txt"

while IFS=$'\t' read -r name key brief model; do
  [ -z "$name" ] && continue
  IFS=$'\t' read -r S O K < <(python3 presign.py "$key")
  if [ -z "${S:-}" ]; then
    echo "$name PRESIGN_FAILED" >> "$OUT/appmap.txt"; continue
  fi
  now_sha="$(python3 mount_fingerprint.py)"
  if [ "$now_sha" != "$MOUNT_SHA" ]; then
    echo "[ABORT] a MOUNTED PATH changed mid-round ($MOUNT_SHA -> $now_sha)."
    echo "        Run: python3 mount_fingerprint.py --verbose   to see which."
    echo "        Arms would mount different code and the round is unscoreable."
    echo "        Re-run the whole round on a frozen tree."
    echo "$name MOUNT_DRIFT" >> "$OUT/appmap.txt"
    exit 2
  fi
  echo "[launch] $name  model=${model:-claude-sonnet-5}"
  modal run --detach agentic_editor_app.py --source "$key" --brief "$brief" \
    --model "${model:-claude-sonnet-5}" \
    --src-url "$S" --out-url "$O" --out-key "$K" > "$OUT/$name.log" 2>&1

  # ONE AUTOMATIC RETRY, FOR CANCELLATION ONLY.
  #
  # Modal has cancelled a fixture mid-run twice in four rounds — music in 19,
  # talking_head in 22 — with NO exception, NO ledger entry, and ~69 lines of
  # log: "Received a cancellation signal" and nothing else. Both passed on a
  # manual retry on the identical mount, so it is infrastructure, and failing a
  # whole round on it throws away the other four fixtures' evidence.
  #
  # NARROW ON PURPOSE. Only a cancellation retries. A crash, a contract
  # violation, a passthrough or any real failure is the result — retrying those
  # would be the pipeline laundering its own defects, which is the opposite of
  # what this harness is for.
  #
  # LOGGED, never silent: the retry appears in appmap.txt and in the round
  # output, so "green" can always be read against how many fixtures needed one.
  # INFRASTRUCTURE SIGNATURES, ENUMERATED — never matched loosely.
  #
  # The test each one passes: NO AGENT RAN, NO OUTPUT EXISTED, and nothing
  # about the pipeline was exercised. A crash, a contract violation, a
  # passthrough or a real failure is the RESULT and must never be retried —
  # "retry anything that looks like infra" is how a pipeline launders its
  # own defects.
  #
  #   cancellation signal    Modal cancelled mid-run, no exception, no ledger
  #                          entry (music r19, talking_head r22; both passed
  #                          on a manual retry of the identical mount)
  #   modified during build  five fixtures launch in sequence and each
  #                          `modal run` re-imports the app, so one build read
  #                          _asset_inventory.json while the next import
  #                          rewrote it (pet_video r31 — never launched). The
  #                          race is fixed by writing that file only on
  #                          change; this stays as the backstop.
  if grep -qE "cancellation signal|was modified during build process" "$OUT/$name.log" 2>/dev/null; then
    echo "[retry] $name — Modal cancelled the run (infrastructure, no exception); retrying ONCE"
    echo "$name CANCELLED_RETRIED" >> "$OUT/appmap.txt"
    mv "$OUT/$name.log" "$OUT/$name.cancelled.log"
    IFS=$'\t' read -r S O K < <(python3 presign.py "$key")
    modal run --detach agentic_editor_app.py --source "$key" --brief "$brief" \
      --model "${model:-claude-sonnet-5}" \
      --src-url "$S" --out-url "$O" --out-key "$K" > "$OUT/$name.log" 2>&1
    if grep -qE "cancellation signal|was modified during build process" "$OUT/$name.log" 2>/dev/null; then
      echo "[retry] $name — cancelled TWICE; that is a real failure, not infrastructure"
    fi
  fi
  id="$(grep -oE 'ap-[A-Za-z0-9]+' "$OUT/$name.log" | head -1)"
  [ -n "$id" ] && echo "$name $id" >> "$OUT/appmap.txt" \
                || echo "$name LAUNCH_FAILED" >> "$OUT/appmap.txt"
done < "$OUT/plan.tsv"

# WAIT ON THIS ROUND'S APPS, NOT EVERY APP NAMED "agentic".
#
# Round 30 hung for 35 polls after all five fixtures had finished. `modal app
# list` still showed an orphaned agentic-editor app from THREE DAYS EARLIER
# holding 1 task, and the name filter counted it. Rule 6 names this exact case
# — ".spawn()ed containers outlive the local orchestrator; a batch is dead only
# when `modal app list` shows 0 tasks" — but "0 tasks" has to mean 0 tasks IN
# THIS BATCH. A name match makes every future round hostage to every past one.
#
# appmap.txt already holds this round's app ids, which is the scoping key.
echo "[wait] polling until THIS round's apps are idle"
_ids="$(awk '{print $2}' "$OUT/appmap.txt" 2>/dev/null | grep -E '^ap-' | tr '\n' '|' | sed 's/|$//')"
if [ -z "$_ids" ]; then
  echo "[wait] no app ids in appmap.txt — cannot scope the wait; falling back to the name filter"
  _ids="agentic"
fi
for i in $(seq 1 100); do
  live="$(modal app list 2>/dev/null | grep -E "$_ids" | grep -cE '│ +[1-9][0-9]* +│')"
  echo "[poll $i] holding tasks: ${live:-?}  (scoped to $(echo "$_ids" | tr '|' '\n' | grep -c ap-) app id(s))"
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
    # READ THE PRODUCER'S VERDICT, DO NOT RE-DERIVE IT.
    #
    # This used to scrape the log for a hardcoded enum of five violation kinds.
    # CONTRACT_FAILURES has SEVEN, and the two it did not know were invisible —
    # round 23 carried 12 spec_shortfall_unresolved across 4 fixtures and scored
    # "all five green". A reader that re-declares the producer's vocabulary
    # falls behind it silently, because a kind it has never heard of looks
    # exactly like a clean run.
    cvm = re.search(r"CONTRACT VIOLATIONS: (\d+)((?:\n\s+- [^\n]*)*)", t)
    if cvm:
        cv_list = [l.strip()[2:] for l in cvm.group(2).split("\n") if l.strip().startswith("- ")]
        if len(cv_list) != int(cvm.group(1)):
            cv_list.append(f"COLLECTOR_MISPARSE: line said {cvm.group(1)}, parsed {len(cv_list)}")
    else:
        # NO LINE AT ALL is not "no violations" — it is a run that never reached
        # its own summary, or a binary predating the line. Absence must never
        # render as success; say so and let the round go red.
        cv_list = ([] if not ok else
                   ["no_contract_verdict: run produced no CONTRACT VIOLATIONS line"])
    res[name] = {"ok": ok,
                 "kept_ratio": float(kept.group(1)) if kept else None,
                 "placements": int(pm.group(1)) if pm else 0,
                 "contract_violations": cv_list}
green, why = rg.round_is_green(res)
json.dump({"result": res, "green": green, "why": why},
          open(os.path.join(out, "score.json"), "w"), indent=1)
print(f"\nROUND {os.environ.get('PROMPTLY_ROUND') or os.path.basename(out).replace('round','')} GREEN={green}")
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

# ── THE ROUND-LEVEL AGGREGATE ──────────────────────────────────────────────
# Sub-unit families (sfx 0.82/25s, zoom 0.35/25s) cannot be scored per fixture:
# zoom needs a 178.6s source to be within 20% of its own rate and production's
# LONGEST job is 180.0s. Their expectations are summed across the round instead,
# UNROUNDED — rounding per fixture and then summing is the error this undoes.
#
# The same fittability bar applies at round level: an aggregate expectation
# under 2.5 still cannot be judged within 20%, and saying so beats printing a
# number that means nothing.
import json as _json
_agg, _durs = {}, []
for _n in sorted(res):
    _p = os.path.join(out, f"{_n}.log")
    _t2 = open(_p, encoding='utf-8', errors='ignore').read() if os.path.exists(_p) else ''
    _rm = _re.search(r"RATE REGIMES    : (\{.*)", _t2)
    if not _rm:
        continue
    try:
        _blob = _json.loads(_rm.group(1))
    except Exception:
        continue
    _durs.append(_blob.get("dur_s") or 0)
    for _f, _d in (_blob.get("families") or {}).items():
        a = _agg.setdefault(_f, {"expected": 0.0, "actual": 0, "regimes": {},
                                 "rate": _d.get("rate")})
        a["expected"] += float(_d.get("expected") or 0)
        a["actual"] += int(_d.get("actual") or 0)
        a["regimes"][_d.get("regime")] = a["regimes"].get(_d.get("regime"), 0) + 1

if _agg:
    _tot = sum(_durs)
    print()
    print(f"  ROUND AGGREGATE  ({len(_durs)} fixtures, {_tot:.1f}s total)")
    print(f"  {'family':10} {'rate':>6} {'expected':>9} {'actual':>7} {'err':>7}   per-fixture regimes")
    for _f in sorted(_agg, key=lambda k: -(_agg[k]["rate"] or 0)):
        a = _agg[_f]
        _regs = ",".join(f"{k}x{v}" for k, v in sorted(a["regimes"].items()))
        if a["expected"] < 2.5:
            _need = (2.5 / a["expected"]) if a["expected"] > 0 else float('inf')
            _err = "UNSCOREABLE"
            _note = f"  needs ~{_need:.1f} rounds of this corpus"
        else:
            _e = abs(a["actual"] - a["expected"]) / a["expected"] * 100
            _err = f"{_e:.0f}%"
            _note = "  WITHIN 20%" if _e <= 20 else "  OUTSIDE 20%"
        print(f"  {_f:10} {a['rate']:>6.2f} {a['expected']:>9.2f} {a['actual']:>7} "
              f"{_err:>7}   {_regs}{_note}")
    print("  (per_run families are judged per fixture above; aggregate/out_of_scope "
          "families are judged only here)")
PY
# ── ARCHIVE, EVERY ROUND, AUTOMATICALLY ────────────────────────────────────
# /tmp was wiped between rounds 25 and 26 and took rounds 6-25 with it — every
# per-fixture log, every score.json. The streak audit that reset the count from
# 3 to 0 was derived from those logs and can no longer be re-derived by anyone.
# A one-time manual upload would rot the same way; this runs on every round or
# it is not a record.
python3 archive_round.py "$ROUND" || echo "  [archive] round $ROUND NOT staged — the record is only in /tmp"
echo "ROUND $ROUND COLLECTED"
