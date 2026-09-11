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

# ── WHICH CORPUS, DECLARED AND PRINTED ──────────────────────────────────────
# Rounds 35-41 all ran ab-sources/reliability-fixtures-v1 — the flat/noise set —
# because the plan came from /tmp/fixtures/staged.json, a per-checkout cache that
# stage_fixtures_v3.py never wrote. Zac's real footage sat in S3, probed and
# manifested, unreachable. THE MISSING WRITE WAS THE BUG; THE MISSING PRINTED
# CORPUS LINE WAS THE DEFECT — seven rounds, no line, no way to notice.
#
# The plan is now built FROM THE CORPUS MANIFEST and verified against the corpus
# somebody declared. staged.json is retired.
CORPUS="${PROMPTLY_CORPUS:-ab-sources/reliability-fixtures-v3}"
python3 build_plan.py "$CORPUS" > "$OUT/plan.tsv" || {
  echo "could not build a plan for $CORPUS"; exit 1; }
[ -s "$OUT/plan.tsv" ] || { echo "no plan — fixtures not staged"; exit 1; }

# REFUSES a plan that spans two corpora, runs a corpus nobody declared, names a
# key the manifest does not list, or points two fixtures at one video. On PASS it
# PRINTS the corpus and every fixture's duration, provenance and cannot_score
# list, into this round's log, so the numbers can never again be read without
# knowing what they were measured on. Six RED legs proven in smoke_corpus_guard.
python3 corpus_guard.py "$OUT/plan.tsv" "$CORPUS" || exit 2

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
# PRE-FLIGHT BEFORE THE FIRST ARM IS PAID FOR.
#
# The fingerprint below catches drift DURING a round, which is right and has
# fired twice on real drift. But it catches it AFTER arms have been spent:
# rounds 37 and 38 both died three arms in, once when scratch appeared under a
# mounted path and once when the same scratch was tidied away.
#
# This asks whether the tree is round-ready BEFORE launching. It checks the
# RESOLVED mounted paths, not the checkout it runs in — src/remotion resolves to
# the MAIN checkout via _HERE/../../src/remotion even when the round launches
# from a worktree, so a checker that inspected the local tree would report a
# confident CLEAN about a directory the image never sees.
if ! python3 mount_preflight.py; then
  echo "[ABORT] the tree is not round-ready — see above. Nothing has been spent."
  exit 2
fi

MOUNT_SHA="$(python3 mount_fingerprint.py)"
if [ -z "$MOUNT_SHA" ]; then
  echo "[ABORT] mount_fingerprint.py produced nothing — refusing to run a round"
  echo "        whose cohort integrity cannot be established."
  exit 2
fi
echo "[mount] $(python3 mount_fingerprint.py --verbose | tail -1)"
echo "$MOUNT_SHA" > "$OUT/mount_sha.txt"

# ONE FIXTURE, WHEN THE QUESTION IS ABOUT ONE FIXTURE. PROMPTLY_ONLY=car_short
# re-runs a single arm after a document fix instead of spending the other four
# on a question they cannot answer. The corpus guard still runs over the WHOLE
# plan first, so the filter can never smuggle in an undeclared corpus — it only
# decides which declared rows launch, and the skipped ones are PRINTED so a
# partial round can never be read as a full one.
ONLY="${PROMPTLY_ONLY:-}"
[ -n "$ONLY" ] && echo "[scope] PROMPTLY_ONLY=$ONLY — this is a PARTIAL round"

while IFS=$'\t' read -r name key brief model; do
  [ -z "$name" ] && continue
  if [ -n "$ONLY" ] && [ "$name" != "$ONLY" ]; then
    echo "[skip] $name (PROMPTLY_ONLY=$ONLY)"; continue
  fi
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
  # SETSID, BECAUSE --detach PROTECTS THE APP AND NOT THE CLIENT.
  #
  # Round 58 lost four of five arms: three cancelled TWICE and one deadline.
  # Every failed log ends "[modal-client] Received a cancellation signal" —
  # CLIENT-side. `modal run --detach` keeps the Modal APP alive when the client
  # disconnects, but the client still cancels its own inputs when IT is
  # signalled, and this script runs inside a process group that gets reaped.
  # car_mid had already reached BENCH AT PAINT when it was killed. The arms
  # were never a Modal problem, and the round-19/22 note above — "it is
  # infrastructure" — has been wrong about at least this class since.
  #
  # setsid.py (macOS ships no setsid) puts each launch in its own session and
  # ignores HUP/INT/TERM, so nothing upstream can reap it.
  # THE RESULT JSON LANDS BESIDE THE LOG. keep_spans crossed the container
  # boundary correctly and was then dropped here, because this captured stdout
  # and nothing else. Judging whether a placement hit the right moment needs the
  # SPANS, and the log only ever carried their count.
  PROMPTLY_RESULT_JSON="$OUT/$name.result.json" \
  python3 "$(dirname "$0")/setsid.py" modal run --detach agentic_editor_app.py --source "$key" --brief "$brief" \
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
    python3 "$(dirname "$0")/setsid.py" modal run --detach agentic_editor_app.py --source "$key" --brief "$brief" \
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
# ONE COLLECTOR, NOT TWO. This was a ~110-line inline copy of collect_round.py,
# which had itself been EXTRACTED so a finished round could be re-scored without
# paying for five fixtures again. Keeping both meant every scorer fix had to be
# made twice, and the corpus change proved it: both copies resolved fixtures from
# a hardcoded v1 tuple, so a v3 round would have found zero logs and scored an
# empty round rather than failing.
python3 collect_round.py "$ROUND" || exit 2

# ── ARCHIVE, EVERY ROUND, AUTOMATICALLY ────────────────────────────────────
# /tmp was wiped between rounds 25 and 26 and took rounds 6-25 with it — every
# per-fixture log, every score.json. The streak audit that reset the count from
# 3 to 0 was derived from those logs and can no longer be re-derived by anyone.
# A one-time manual upload would rot the same way; this runs on every round or
# it is not a record.
python3 archive_round.py "$ROUND" || echo "  [archive] round $ROUND NOT staged — the record is only in /tmp"
echo "ROUND $ROUND COLLECTED"
