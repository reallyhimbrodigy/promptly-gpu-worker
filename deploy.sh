#!/bin/bash
# Safe deploy wrapper. Runs validate_deploy.py FIRST. If validation fails,
# the deploy doesn't happen. Use this instead of `modal deploy modal_app.py`
# directly.

set -e

cd "$(dirname "$0")"

echo "════════════════════════════════════════════════════════════"
echo "  Pre-deploy validation"
echo "════════════════════════════════════════════════════════════"
python3 validate_deploy.py
VALIDATION_EXIT=$?

if [ $VALIDATION_EXIT -ne 0 ]; then
    echo ""
    echo "❌ Validation failed. Deploy ABORTED."
    echo "   Fix the issues above and re-run: ./deploy.sh"
    exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  Deploying to Modal"
echo "════════════════════════════════════════════════════════════"
# Single-deployer protocol (directive #10): every deploy names its operator.
# Override per-operator: PROMPTLY_DEPLOYER=codex ./deploy.sh (etc.)
export PROMPTLY_DEPLOYER="${PROMPTLY_DEPLOYER:-claude-code}"
echo "  deployer: $PROMPTLY_DEPLOYER"
modal deploy modal_app.py

# Deploy-state guard (Zac 2026-08-01): record the deployed HEAD so validate_deploy
# fails a LATER deploy that would drop a commit already known live. `set -e` above
# means we only reach here on a SUCCESSFUL deploy.
git rev-parse HEAD > .last_deployed_commit 2>/dev/null || true
echo "  recorded deployed commit: $(cat .last_deployed_commit 2>/dev/null)"
