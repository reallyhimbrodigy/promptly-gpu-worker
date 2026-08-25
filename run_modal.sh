#!/bin/zsh
# THE ONLY SANCTIONED WAY TO INVOKE `modal run` FROM A HARNESS.
#
# WHY THIS EXISTS. On 2026-08-24 the v3 cross-arm run was invoked as:
#
#     modal run app.py > log 2>&1
#     echo "MODAL_RC=$?"
#
# `modal run` returned **1**. The shell's exit status came from `echo`, which
# succeeded, so the background task reported SUCCESS. 19 of 26 cells survived
# only because the per-cell S3 write worked, and the result was reported with
# the wrong confidence: "19 cells, errors=0, I don't know why it stopped" when
# the truth was "the run FAILED and the harness hid it".
#
# The exit code was captured into a variable and then DISCARDED BY PRINTING IT.
# That is the standing rule — exit codes captured directly, never through a pipe
# — broken in exactly the shape it exists to prevent.
#
# "Remember to write RC=$?" is a discipline gap, and discipline gaps recur. This
# is the tooling that closes it: the runner propagates, so no caller has to.
#
#   ./run_modal.sh <app.py> [modal-run-args...]
#
#   exit 0   the run succeeded
#   exit N   modal's OWN exit code, propagated verbatim
#   exit 2   could not run (no app file / modal absent) — NOT a pass
#
# Env passes through, so N_SOURCES / ARMS / REPEATS / RUN_TAG work as before.
# stdout+stderr are TEE'd, not redirected: the log is kept AND the caller sees
# the run, because a silent harness is how the last failure stayed invisible.
set -uo pipefail

APP="${1:-}"
[[ -n "$APP" && -f "$APP" ]] || { echo "run_modal: no such app file: ${APP:-<none>} — NOT run (exit 2)"; exit 2; }
shift
command -v modal >/dev/null 2>&1 || { echo "run_modal: modal CLI absent — NOT run (exit 2)"; exit 2; }

LOG="${PROMPTLY_MODAL_LOG:-/tmp/modal_run_$(date -u +%Y%m%dT%H%M%SZ).log}"
echo "run_modal: $APP  ->  $LOG"

# THE WHOLE POINT. `set -o pipefail` + PIPESTATUS gives modal's status through
# the tee; nothing after this line may become the exit code.
modal run "$APP" "$@" 2>&1 | tee "$LOG"
RC=${pipestatus[1]}

echo "run_modal: modal exited ${RC}  (log: $LOG)"
if [[ $RC -ne 0 ]]; then
  echo "run_modal: ❌ THE RUN FAILED. Any cells that completed are in the app's"
  echo "           own durable record, NOT in this exit status. Do not read a"
  echo "           partial result as a finished one."
fi
exit $RC
