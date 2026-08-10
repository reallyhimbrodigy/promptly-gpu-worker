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
# DEPLOYING BRANCH (Zac 2026-08-03): the worker deploys from the WORKING TREE of
# whatever branch is checked out — historically `zero-reject-routing`, NOT main.
# A silent 447-commit main→branch gap cost hours today. Print it every run so a
# gap can never open unnoticed, and keep main fast-forwarded to this branch.
echo "  deploying from branch: $(git branch --show-current 2>/dev/null || echo '(detached)') @ $(git rev-parse --short HEAD 2>/dev/null)"
if git rev-parse --verify main >/dev/null 2>&1 \
   && [ "$(git rev-parse HEAD)" != "$(git rev-parse main)" ] \
   && git merge-base --is-ancestor main HEAD 2>/dev/null; then
    echo "  ⚠️  main is BEHIND this branch by $(git rev-list --count main..HEAD) commit(s) — it is stale; fast-forward + push it after this deploy."
fi
# NO-REGRESS GATE (2026-08-04). The `.last_deployed_commit` guard below is
# written into the DEPLOYING checkout, so each agent's copy records only their
# own last deploy and is structurally blind to everyone else's. Twice in 16
# hours two agents' branches diverged and the later deploy silently reverted the
# earlier one's shipped fixes — v512 dropped clean_export_key on both routes,
# RENDER_CANON_UNREADABLE and the VFR clamp, and four completions ran on the
# reverted image before a DB read noticed. This asks MODAL what is actually live
# and refuses a deploy that would drop any of it.
python3 predeploy_no_regress.py

modal deploy modal_app.py

# Deploy-state guard (Zac 2026-08-01): record the deployed HEAD so validate_deploy
# fails a LATER deploy that would drop a commit already known live. `set -e` above
# means we only reach here on a SUCCESSFUL deploy.
git rev-parse HEAD > .last_deployed_commit 2>/dev/null || true
echo "  recorded deployed commit: $(cat .last_deployed_commit 2>/dev/null)"

# POST-DEPLOY TOCTOU GUARD (Zac 2026-08-04). The predeploy_no_regress gate above
# is a POINT-IN-TIME check: a concurrent lane can deploy in the window between it
# and `modal deploy`, and the last deploy wins — exactly the race that dropped
# clean_export_key twice. Prevention cannot win that race; DETECTION can. Re-run
# the guard now, against what Modal reports live AFTER our deploy: a non-zero delta
# means a concurrent deploy raced us and live diverged from what we just shipped
# (ours may have dropped theirs, or theirs superseded ours). Loud + non-zero exit
# so the race can never pass unnoticed the way v512 did.
echo "  [post-deploy] TOCTOU re-check against live..."
if ! python3 predeploy_no_regress.py; then
    echo "  🚨 POST-DEPLOY REGRESSION — a concurrent deploy raced this one; live and the"
    echo "     shipped tree diverged. RECONCILE NOW: git merge the live commit, re-verify"
    echo "     predeploy delta is zero, redeploy."
    # PAGE, DON'T PRINT (Errors, wiring Speed's deferred ask). A printed warning
    # is read only by whoever is watching this terminal; v512 dropped
    # clean_export_key on both routes and went unseen for 70 minutes. The local
    # shell has no MODAL_CALLBACK_SECRET, so fire from inside Modal where the
    # deployed secret set is mounted — same trick as the auth ping. Never let the
    # alert itself abort the reconcile message.
    set +e
    ALERT_OUT="$(modal run cert_deploy_alert.py --detail \
        "deploy race: $(git rev-parse --short HEAD) shipped, live diverged — reconcile" 2>&1)"
    ALERT_STATUS="$(printf '%s\n' "$ALERT_OUT" | grep -oE 'DEPLOY_ALERT_STATUS=[-0-9]+' | cut -d= -f2 | tail -1)"
    set -e
    if [ "$ALERT_STATUS" = "202" ] || [ "$ALERT_STATUS" = "200" ]; then
        echo "     📟 owner paged (DEPLOY_RACE, status=$ALERT_STATUS)."
    else
        echo "     ⚠️  owner page FAILED (status=${ALERT_STATUS:-unknown}) — this finding is"
        echo "        terminal-only. Tell the team by hand."
    fi
    exit 1
fi
echo "  [post-deploy] TOCTOU clean — no concurrent deploy dropped identifiers."

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

# ── REGRESSION CORPUS (Zac 2026-08-04, "gone for good") ──────────────────────
# Re-render one saved source per FIXED sub-code and assert it still COMPLETES, so
# no fixed class can return silently. The entrypoint SPAWNS a Modal container
# (returns immediately — never blocks the deploy loop) that renders, asserts, and
# SELF-ALERTS on REGRESSED: a loud [ALERT] line in Modal logs + an owner push. So
# a regression can no longer sit unread in a detached log. ~$0.10-0.15/source.
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  Regression corpus — spawning the fixed-defect re-render (self-alerts)"
echo "════════════════════════════════════════════════════════════"
set +e
if [ -n "$PROMPTLY_SKIP_REGRESSION" ]; then
    echo "  regression corpus SKIPPED (PROMPTLY_SKIP_REGRESSION set - zero discretionary spend during surge)"
else
    modal run modal_app.py::regression_corpus 2>&1 | grep -E "REGRESSION_CORPUS|spawned"
fi
set -e
echo "  ▶ spawned — verdict in Modal logs ([REGRESSION-CORPUS] ALL GREEN / REGRESSED:);"
echo "     a REGRESSED fires an [ALERT] + owner push, so it can't go unread"
