#!/usr/bin/env bash
# ROUND 49 — THE ABLATION. Which of the seven commits moved the clean cohort?
#
# THREE ARMS, ONE TREE. The ONLY difference between arms is --prefix-removals,
# which reaches the container as os.environ and is applied before any prompt is
# assembled. No code differs between arms, so a difference between them is the
# material and nothing else.
#
# WHY BOTH-ON IS RE-RUN RATHER THAN REUSED FROM ROUND 48. The truncation fixes
# moved the mount fingerprint 8c74fffe2bb17f2a -> 15ccf9dbe7cc6290. Round 48's
# baseline is a different tree, and comparing across it would smuggle in every
# change since. Arm A costs three extra runs and buys a replication of round
# 48's clean-cohort result on the tree the other arms actually run.
#
# CLEAN COHORT ONLY. talking_head and motion had 22 and 3 rejections in round 47
# and their round-48 movement is fully explained by the rejection fix — they are
# UNMEASURED and cannot answer anything here, so they are not run and not paid
# for.
set -uo pipefail
cd "$(dirname "$0")"
ROUND="${1:-49}"
BASE="/tmp/fixtures/round${ROUND}"; mkdir -p "$BASE"
CORPUS="${PROMPTLY_CORPUS:-ab-sources/reliability-fixtures-v3}"
CLEAN="car_short screen_recording car_mid"

python3 build_plan.py "$CORPUS" > "$BASE/plan.tsv" || { echo "no plan"; exit 1; }
python3 corpus_guard.py "$BASE/plan.tsv" "$CORPUS" || exit 2

# THE MOUNT MUST BE IDENTICAL ACROSS EVERY ARM AND EVERY FIXTURE. Nine launches
# here, not five, so there is more room for a mid-round edit to split the cohort.
MOUNT_SHA=$(python3 mount_fingerprint.py | tail -1)
echo "[mount] frozen at $MOUNT_SHA"
echo "$MOUNT_SHA" > "$BASE/mount_sha.txt"

# arm name -> --prefix-removals value
run_arm() {
  local arm="$1" removals="$2"
  local OUT="$BASE/$arm"; mkdir -p "$OUT"
  echo "=== ARM $arm  removals='${removals:-none}' ==="
  while IFS=$'\t' read -r name key brief model; do
    case " $CLEAN " in *" $name "*) ;; *) continue ;; esac
    # RESIDUE CHECK BEFORE THE FINGERPRINT CHECK, because they answer different
    # questions and the residue one is more specific.
    #
    # A mutating harness restores from memory, which removes the CROSS-BRANCH
    # surface and does NOTHING about an INTERRUPTED run: a SIGKILL between
    # mutate and restore leaves the mutant on disk. Builder-2 found exactly that
    # after a killed sweep —
    #     -  led["cut_word_intrusions"] = cut_word_intrusions(spans, words)
    #     +  led["cut_word_intrusions"] = []
    # one line in 12,000, in the measurement whose whole job is that count, and
    # every gate passes on an empty list.
    #
    # The fingerprint check below would catch it too, but it says only "the tree
    # moved". This says WHAT moved and hands over a diff.
    _residue=$(git status --porcelain agentic_editor_app.py)
    if [ -n "$_residue" ]; then
      echo "[ABORT] RESIDUE in a mounted file before launching $arm/$name:"
      echo "        $_residue"
      echo "        A harness was interrupted mid-mutation, or something else"
      echo "        wrote here. The frozen fingerprint is now around a MUTANT."
      git --no-pager diff --stat agentic_editor_app.py | sed 's/^/        /'
      exit 2
    fi
    now=$(python3 mount_fingerprint.py | tail -1)
    if [ "$now" != "$MOUNT_SHA" ]; then
      echo "[ABORT] mounted path changed mid-ablation ($MOUNT_SHA -> $now)."
      echo "        Arms would mount different code and NOTHING here is scoreable."
      exit 2
    fi
    IFS=$'\t' read -r S O K < <(python3 presign.py "$key")
    echo "[launch] $arm/$name"
    modal run --detach agentic_editor_app.py --source "$key" --brief "$brief" \
      --model "${model:-claude-haiku-4-5}" \
      --src-url "$S" --out-url "$O" --out-key "$K" \
      --prefix-removals "$removals" > "$OUT/$name.log" 2>&1
    if grep -qE "cancellation signal|was modified during build process" "$OUT/$name.log" 2>/dev/null; then
      echo "[retry] $arm/$name — Modal cancellation (infrastructure); retrying ONCE"
      mv "$OUT/$name.log" "$OUT/$name.cancelled.log"
      IFS=$'\t' read -r S O K < <(python3 presign.py "$key")
      modal run --detach agentic_editor_app.py --source "$key" --brief "$brief" \
        --model "${model:-claude-haiku-4-5}" \
        --src-url "$S" --out-url "$O" --out-key "$K" \
        --prefix-removals "$removals" > "$OUT/$name.log" 2>&1
    fi
    # THE ARM MUST BE WHAT IT CLAIMS, AND THE CLAIM MUST COME FROM THE CONTAINER.
    #
    # An earlier version of this grepped the PREFIX MATERIAL line and called it
    # verification. That line USED TO BE COMPUTED IN main() — the local
    # entrypoint — so it reported the shell that launched the run, not the
    # process that built the prompt. Nine rows of it would have agreed with what
    # each arm was ASKED to run, by construction, whether or not the container
    # obeyed. The void condition ("a row says ON in an OFF arm") could never
    # fire, so the table would have looked like verification and been a
    # restatement of the request.
    #
    # The state is now recorded by edit() into the ledger and printed with the
    # marker `(measured in-container)`. REQUIRING THAT MARKER is what makes each
    # row a measurement: a run whose container did not report prints UNKNOWN and
    # is void for the other good reason — we do not know what it ran.
    local got
    got=$(grep -oE "PREFIX MATERIAL : .*" "$OUT/$name.log" | head -1)
    case "$got" in
      *"measured in-container"*) ;;
      *) got="VOID — ${got:-no PREFIX MATERIAL line}; not measured in-container" ;;
    esac
    echo "   $got"
    echo "$arm/$name	$got" >> "$BASE/armmap.txt"
  done < "$BASE/plan.tsv"
}

run_arm both_on          ""
run_arm no_examples      "reference_examples"
run_arm no_knowledge     "ruling_time_knowledge"

echo
echo "=== ARM VERIFICATION — every row must be measured IN-CONTAINER ==="
cat "$BASE/armmap.txt"
_void=$(grep -c "VOID" "$BASE/armmap.txt" 2>/dev/null || echo 0)
if [ "$_void" != "0" ]; then
  echo
  echo "[UNUSABLE] $_void of 9 run(s) did not report their own state from the"
  echo "           container. Those arms say what they were ASKED to run and"
  echo "           nothing about what they ran, so they are not evidence."
fi
