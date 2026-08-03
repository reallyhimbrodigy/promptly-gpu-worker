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

# Server→WORKER auth gate (Zac 2026-08-03): IF the run-job auth gate
# (_require_worker_auth, keyed on MODAL_RUN_SECRET) is present in the image, PROVE
# the server's own credential authenticates to the worker (non-403) BEFORE the
# deploy completes. This is the exact check that would have caught v446, where the
# gate 403'd every dispatch because no caller sent _worker_auth. INERT while the
# gate is stashed (the grep finds nothing); activates the day it ships — and it
# tests the REAL round-trip, not a cross-repo grep.
if grep -q "_require_worker_auth" modal_app.py; then
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  Run-job auth gate PRESENT — verifying server → worker auth"
    echo "════════════════════════════════════════════════════════════"
    set +e
    RUN_OUT="$(modal run cert_run_auth_ping.py 2>&1)"
    RUN_403="$(printf '%s\n' "$RUN_OUT" | grep -oE '"is_403": ?(true|false)' | grep -oE 'true|false' | tail -1)"
    set -e
    if [ "$RUN_403" = "true" ]; then
        echo ""
        echo "  🚨🚨 SERVER→WORKER AUTH 403 — the run-job gate rejects the server's MODAL_RUN_SECRET."
        echo "     EVERY dispatch will 403 (this IS the v446 outage). FIX: reconcile MODAL_RUN_SECRET"
        echo "     across Modal (promptly-secrets), Render, and the iOS callers, THEN re-deploy."
        printf '%s\n' "$RUN_OUT" | grep -E 'RUN_AUTH_PING' | tail -1
        exit 1
    else
        echo "  ✅ server→worker auth OK (non-403) — the run-job gate accepts the server credential."
    fi
fi
