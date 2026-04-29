#!/usr/bin/env bash
# Deploy promptly-gpu-worker to Modal with a clean container fleet.
#
# What this does that `modal deploy` alone doesn't:
#   1. Confirms the working tree is committed (or warns if --allow-dirty).
#   2. Runs the local smoke render — every Remotion composition mounts and
#      renders against synthetic inputs. Catches the entire class of
#      "bundle compiles but blows up at render time" bugs before they reach
#      Modal. Skippable with --skip-smoke for emergencies.
#   3. Pushes to origin so the SHA on Modal matches the SHA on GitHub.
#   4. Stops every running container BEFORE deploying so warm containers
#      cannot serve old code post-deploy. Modal's normal behaviour is to
#      keep warm containers alive until scaledown_window expires; that
#      window can mask "did my fix actually deploy?" for up to 5 min.
#
# In-flight jobs DO fail when containers are stopped — use this for dev
# iteration. For production hotfixes where you can't kill in-flight work,
# use `modal deploy modal_app.py` directly and rely on the BUILD log line
# to disambiguate which build a given job ran on.

set -euo pipefail

cd "$(dirname "$0")/.."

ALLOW_DIRTY=0
SKIP_SMOKE=0
for arg in "$@"; do
  case "$arg" in
    --allow-dirty) ALLOW_DIRTY=1 ;;
    --skip-smoke)  SKIP_SMOKE=1 ;;
    *) echo "ERROR: unknown flag $arg" >&2; exit 1 ;;
  esac
done

# 1. Working-tree check.
if [[ -n "$(git status --porcelain)" ]]; then
  if [[ "$ALLOW_DIRTY" -ne 1 ]]; then
    echo "ERROR: working tree has uncommitted changes."
    echo "Commit them, or pass --allow-dirty to deploy anyway (BUILD_DIRTY=1)."
    git status --short
    exit 1
  fi
  echo "WARNING: deploying with uncommitted changes (BUILD_DIRTY=1)."
fi

# 2. Smoke render.
if [[ "$SKIP_SMOKE" -ne 1 ]]; then
  echo
  echo "── Pre-deploy smoke render ──"
  bash scripts/smoke.sh
  echo "── Smoke passed ──"
  echo
fi

# 3. Push to origin (only if clean — dirty deploys stay local).
if [[ "$ALLOW_DIRTY" -ne 1 ]]; then
  git push origin "$(git rev-parse --abbrev-ref HEAD)"
fi

# 4. Stop running containers to flush old code.
echo "Stopping any warm containers so post-deploy traffic hits new build..."
modal app stop promptly-gpu-worker 2>/dev/null || true

# 5. Deploy.
modal deploy modal_app.py

SHA="$(git rev-parse HEAD)"
echo
echo "Deployed sha=${SHA:0:12} (dirty=$ALLOW_DIRTY)"
echo "Verify in Modal logs: every job should print 'BUILD sha=${SHA:0:12} ...' on its first line."
