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
    # THE ARM MUST BE WHAT IT CLAIMS. Read the state back out of the run's own
    # log, from the predicate the injection uses — an arm that says ON while
    # claiming OFF is the fabricated null this whole round is exposed to.
    local got
    got=$(grep -oE "PREFIX MATERIAL : .*" "$OUT/$name.log" | head -1)
    echo "   ${got:-PREFIX MATERIAL LINE ABSENT — arm state UNVERIFIED}"
    echo "$arm/$name ${got:-ABSENT}" >> "$BASE/armmap.txt"
  done < "$BASE/plan.tsv"
}

run_arm both_on          ""
run_arm no_examples      "reference_examples"
run_arm no_knowledge     "ruling_time_knowledge"

echo
echo "=== ARM VERIFICATION (each line must match its arm) ==="
cat "$BASE/armmap.txt"
