#!/usr/bin/env bash
# run_frozen.sh — run a long job against a SNAPSHOT of the tree, not the tree.
#
# THE TOOLING GAP THIS CLOSES. Three self-inflicted failures in two hours, all
# the same shape: a long-running job reads the working tree while I keep editing
# it.
#
#   1. deploy.sh refused with DIRTY TREE — I edited handler.py while the deploy
#      sat queued on the quiet window.
#   2. v571 and v572 both carry a dirty `*` in modal app history for the same
#      reason, so the recorded SHA does not describe the running image.
#   3. A gate run reported 399 passed / 29 FAILED because handler.py passed
#      through a SyntaxError mid-run. I then spent real time diagnosing 29
#      phantom failures.
#
# (3) is the expensive one: not a broken build, a MISATTRIBUTED one. A gate that
# can report failures belonging to a tree that no longer exists is worse than a
# slow gate, because you act on the result.
#
# Discipline does not fix this — I already knew the rule and broke it three
# times in two hours while concentrating on something else. So: snapshot the
# tracked tree into a temp dir, run there, and let the main checkout be edited
# freely. The snapshot includes UNCOMMITTED changes deliberately — the point is
# to validate what I have right now, frozen, not what HEAD happens to be.
#
#   ./run_frozen.sh python3 validate_deploy.py
#
# Heavy directories are symlinked rather than copied (models/, node_modules/,
# .venv) so the snapshot is cheap; they are inputs, not code under test.
set -uo pipefail
[ $# -ge 1 ] || { echo "usage: ./run_frozen.sh <cmd> [args...]"; exit 2; }

ROOT="$(pwd)"
SNAP="$(mktemp -d -t promptly_frozen.XXXXXX)"
trap 'rm -rf "$SNAP"' EXIT

# tracked files only — the snapshot must describe the repo, not stray artefacts
# TRACKED **AND** UNTRACKED-BUT-NOT-IGNORED. `git ls-files -z` alone copies only
# TRACKED files, so a brand-new cert that has not been committed yet is ABSENT
# from the snapshot and its gate check fails on its first frozen run — which is
# exactly what happened to check 428. A freeze that cannot see new work is a
# freeze that blocks new work.
git ls-files -z --cached --others --exclude-standard > "$SNAP/.filelist" 2>/dev/null \
  || { echo "not a git tree"; exit 2; }
tar --null -cf - -T "$SNAP/.filelist" 2>/dev/null | (cd "$SNAP" && tar -xf -) || {
  echo "  snapshot failed"; exit 2; }
rm -f "$SNAP/.filelist"

# models/ IS HARDLINKED, NOT SYMLINKED. The MODELS-NOT-SYMLINK law (Zac
# RULE-1, 2026-08-03) exists because a symlink loop under models/ killed deploys
# — and validate_deploy asserts it, so a symlinked snapshot fails its own gate.
# `cp -al` gives the same near-zero cost with real directory entries.
if [ -e "$ROOT/models" ] && [ ! -e "$SNAP/models" ]; then
  cp -al "$ROOT/models" "$SNAP/models" 2>/dev/null || cp -R "$ROOT/models" "$SNAP/models"
fi
# node_modules/.venv are INPUTS, never code under test, and no law constrains
# their shape — symlinks are fine and keep the snapshot cheap.
for d in node_modules .venv src/remotion/node_modules; do
  [ -e "$ROOT/$d" ] && [ ! -e "$SNAP/$d" ] && ln -s "$ROOT/$d" "$SNAP/$d"
done

BEFORE="$(git status --porcelain | shasum | cut -d' ' -f1)"
echo "  frozen snapshot: $(find "$SNAP" -name '*.py' | wc -l | tr -d ' ') python file(s)"
echo "  running: $* "
( cd "$SNAP" && "$@" )
RC=$?
AFTER="$(git status --porcelain | shasum | cut -d' ' -f1)"

# The run is unaffected either way — but SAY it, because a result read against a
# tree that has since moved is the thing that cost the time.
if [ "$BEFORE" != "$AFTER" ]; then
  echo "  NOTE: the working tree CHANGED during this run. The result above"
  echo "        describes the SNAPSHOT taken at start, which is the point —"
  echo "        but re-run before acting on it if the edits were relevant."
fi
exit $RC
