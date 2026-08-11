#!/usr/bin/env bash
# golden/ignite.sh — ONE-COMMAND ignition for the golden freeze (LANE 2).
#
#   bash golden/ignite.sh            # smokes -> full freeze -> cert -> handoff
#   bash golden/ignite.sh --smoke    # health smokes only (~$0.06), no freeze
#
# Order is load-bearing: three priced health smokes gate the ~$5 freeze.
# A freeze on a sick pipeline canonizes the sickness (2026-08-09: Vertex
# dunning-denial made 100% of editorial plans safe_edit fallbacks; a freeze
# that day would have locked fallback behavior in as "golden").
set -euo pipefail
cd "$(dirname "$0")/.."   # the lane-harness worktree root

SMOKE_DIR="$(mktemp -d /tmp/golden-smoke.XXXXXX)"
LEDGER=MODAL_SPEND_LEDGER.md
TODAY=$(date +%F)

fail() { echo "❌ IGNITION ABORT: $*" >&2; exit 1; }

echo "== [0/5] preflight (free) =="
[ "$(git rev-parse --short HEAD | cut -c1-7)" != "" ] || fail "not a git checkout"
git merge-base --is-ancestor 1601ae0 HEAD || fail "worktree does not contain base 1601ae0"
[ -f models/rife-v4.18/RIFE_HDv3.py ] || fail "models/ missing — cp -R ../../models . (image build needs it)"
command -v modal >/dev/null || fail "modal CLI not on PATH"
python3 harness_plan_diff.py self-test >/dev/null || fail "differ self-test"
python3 - <<'PY' || exit 1
import json
mf=json.load(open("golden/manifest.json"))
assert len(mf["sources"])>=20 and all(s.get("sha256") for s in mf["sources"])
print("   manifest: %d sources + %d tweak cases OK" % (len(mf["sources"]), len(mf.get("tweak_cases",[]))))
PY

echo "| ${TODAY} | harness | golden-freeze IGNITION smokes x3 | 3 | est ~60 | ~\$0.06 est | (see prior) |" >> "$LEDGER"

smoke() {  # smoke <source_id> <python-assert-body>
  local sid="$1"; local check="$2"
  echo "-- smoke ${sid}"
  modal run golden_freeze_app.py --runs 1 --only "$sid" --out "$SMOKE_DIR" >/dev/null 2>&1 \
    || fail "smoke run ${sid} did not complete"
  RUN_JSON="$SMOKE_DIR/$sid/run1.json" python3 - <<PY || fail "smoke ${sid}: health assert failed — DO NOT FREEZE (read $SMOKE_DIR/$sid/run1.json)"
import json, os
d=json.load(open(os.environ["RUN_JSON"])); cap=d.get("capture") or {}
${check}
print("   %s: healthy" % d["source_id"])
PY
}

echo "== [1/5] Vertex health smoke (editorial, ~\$0.02) =="
smoke editorial_eng_5decdf11 '
assert d["kind"]=="editorial", "kind=%r" % d["kind"]
assert (cap.get("gemini_n_calls") or 0) > 0, "gemini_n_calls=0 -> safe_edit fallback (Vertex still sick: dunning/billing?)"
ep=cap.get("edit_plan") or {}
zooms=[e.get("zoom_effect") for e in ep.get("emphasis_moments",[]) if isinstance(e,dict) and e.get("zoom_effect")]
arcs=[z.get("arc_position") for z in zooms if isinstance(z,dict) and z.get("arc_position")]
assert not zooms or arcs, "zoom_effects carry NO arc_position -> moment-class dimension would be VACUOUS"'

echo "== [2/5] moodreel route smoke (extinction tripwire, ~\$0.02) =="
smoke moodreel_xx_d5cf8ea2 '
assert d["kind"]=="light_route", "kind=%r (moodreel source did not light-route)" % d["kind"]
mk=cap.get("route_markers") or []
assert "moodreel" in mk, "route_markers=%r — moodreel builder never ran (the 3-day extinction is STILL LIVE)" % mk'

echo "== [3/5] hype route smoke (~\$0.02) =="
smoke hype_xx_c71030e5 '
assert d["kind"]=="light_route", "kind=%r" % d["kind"]
mk=cap.get("route_markers") or []
assert "hype" in mk, "route_markers=%r — hype builder never ran (extinction class)" % mk'

if [ "${1:-}" = "--smoke" ]; then
  echo "✅ all three health smokes green — pipeline is freeze-ready. Re-run without --smoke to freeze."
  exit 0
fi

echo "== [4/5] FULL FREEZE: 25 sources x 3 runs (~\$4.50-6.50, cap \$8) =="
echo "| ${TODAY} | harness | golden-freeze FULL 25x3 | 75 | (printed below) | est \$4.50-6.50 | (see prior) |" >> "$LEDGER"
modal run --detach golden_freeze_app.py --runs 3 --out golden/plans \
  || fail "full freeze failed"

echo "== [5/5] offline cert + baseline =="
python3 cert_golden_output.py || fail "cert_golden_output RED — inspect before committing anything"

echo ""
echo "✅ FREEZE COMPLETE. Now, in order:"
echo "  1. modal app list                 # must show 0 tasks for golden-freeze"
echo "  2. append ACTUAL container-s + \$ to $LEDGER (freeze printed its est)"
echo "  3. git add golden/plans golden/baseline_report.json $LEDGER && git commit"
echo "  4. forced-failure proofs (Step 4), then TRUTH merges golden/validate_deploy_addition.py"
echo "  5. announce differ SLA open: SEAM/DELIVERY candidates judged same-few-hours;"
echo "     SEAM tweak captures -> golden/tweaks/ then:"
echo "     python3 harness_plan_diff.py tweak-judge --manifest golden/manifest.json --captures golden/tweaks"
