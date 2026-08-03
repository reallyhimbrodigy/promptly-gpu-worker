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

# Post-deploy AUTH PING (Zac 2026-08-03): prove the just-deployed worker can
# AUTHENTICATE to the server. A MODAL_CALLBACK_SECRET mismatch degraded SILENTLY
# into the recovery path for HOURS tonight (every completion 401'd, all recovered
# via the reconciler = the double-loss storm). This fails the deploy LOUDLY so the
# class is impossible: an authenticated round-trip using the worker's OWN secret.
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  Post-deploy auth ping (worker → server callback auth)"
echo "════════════════════════════════════════════════════════════"
set +e
AUTH_OUT="$(modal run cert_auth_ping.py 2>&1)"
AUTH_STATUS="$(printf '%s\n' "$AUTH_OUT" | grep -oE 'AUTH_PING_STATUS=[-0-9]+' | cut -d= -f2 | tail -1)"
set -e
if [ "$AUTH_STATUS" = "200" ]; then
    echo "  ✅ auth-ping OK (200) — the worker authenticates to the server."
else
    echo ""
    echo "  🚨🚨 AUTH-PING FAILED (status=${AUTH_STATUS:-unknown})."
    echo "     The worker's MODAL_CALLBACK_SECRET does NOT authenticate to the server, so"
    echo "     EVERY completion callback will 401 and fall to the reconciler (double-loss"
    echo "     storm). FIX: reconcile MODAL_CALLBACK_SECRET across Modal (promptly-secrets)"
    echo "     and Render to the SAME value, then re-run ./deploy.sh. The server logs the"
    echo "     mismatch at [modal-auth] (server-vs-got fingerprints)."
    printf '%s\n' "$AUTH_OUT" | grep -E 'AUTH_PING_DETAIL' | tail -1
    exit 1
fi
