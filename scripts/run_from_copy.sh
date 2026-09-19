#!/bin/sh
# EXECUTE A LAUNCHER FROM A RUN-UNIQUE COPY, never from the tree (2026-09-19, second instance this week).
#   run_from_copy.sh <script-name> [args...]
# `sh` reads a script incrementally and keeps a byte offset; editing the file it is executing can make it
# resume mid-line in shifted bytes. Both hazards this week were edits to a launcher DURING its own run —
# once to h_batch.sh (avoided deliberately) and once to h_window.sh (walked into, and it survived by luck).
# The copy is the fix: the tree stays editable and the running shell reads bytes nobody can move.
set -u
set -o pipefail
D=$(cd "$(dirname "$0")/.." && pwd)
NAME=$1; shift
RUNDIR=${RUNDIR:-/tmp/launcher_$(date +%Y%m%d_%H%M%S)_$$}
mkdir -p "$RUNDIR/scripts" || exit 2
# every script the launcher may call, not just the entry point — h_window.sh calls h_stage.sh and h_wait.sh
cp "$D"/scripts/*.sh "$D"/scripts/*.py "$RUNDIR/scripts/" || exit 2
echo "LAUNCHER COPY: $RUNDIR/scripts/$NAME  (source $D, HEAD $(git -C "$D" rev-parse --short HEAD 2>/dev/null))"
SC_DIR="$RUNDIR/scripts" exec sh "$RUNDIR/scripts/$NAME" "$@"
