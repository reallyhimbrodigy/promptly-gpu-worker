# LAUNCH DAY — ignition runbook

Co-owned document. Section ownership is hard: edits to a section go through
its owner's lane; the other co-owner reviews, never rewrites.

| section | owner |
|---|---|
| §1 Freeze and differ | **HARNESS** (lane/harness) |
| §2 Deploy order, quiet window, no-regress | **TRUTH** |
| §3 Flip sequence + rollback | **TRUTH** (SEAM consulted) |

---

## §1 Freeze and differ — HARNESS-owned

HARNESS is first in the water. Nothing in §2/§3 starts until the freeze is
committed and the baseline is GREEN.

### Preconditions (all four, no exceptions)

1. **Vertex healthy** — the editorial smoke must show `gemini_n_calls > 0`
   AND `arc_position` present on zoom claims. (2026-08-08→? dunning outage:
   100% of editorial plans were `safe_edit` fallbacks; a freeze then would
   have canonized fallback behavior. The smoke assert is proven to RED on
   the stored outage-era capture.)
2. **moodreel + hype alive** — their route-builder markers must fire on the
   route smokes. As of 2026-08-11 both routes sit at exactly 0 completions
   for 3 days, unresolved; this is the tripwire.
3. Run from the `lane/harness` worktree (image bundles the tree == the
   commit being frozen; base 1601ae0) with `models/` present.
4. Ledger line before each spend batch (`MODAL_SPEND_LEDGER.md`).

### T-0 sequence

```bash
cd .worktrees/lane-harness
bash golden/ignite.sh --smoke    # 3 priced health smokes, ~$0.06
bash golden/ignite.sh            # full freeze 25x3 (~$4.50-6.50, cap $8)
                                 #   -> cert_golden_output.py -> baseline GREEN
```

Then, in order: `modal app list` = 0 → ledger actuals → commit
`golden/plans/` + `golden/baseline_report.json` → the three forced-failure
proofs (Step 4: corrupt a golden → RED; disable a family in a scratch
branch → RED; schema-violating plan → RED) → hand
`golden/validate_deploy_addition.py` to TRUTH's merge queue (it fails loudly
on an unfrozen corpus by design — merge only after this sequence).

### The abort rule

> One standing caution for ignition day: if the moodreel/hype smoke REDs, do
> not partial-freeze around it — 8 of 25 sources are light-route, and
> freezing them mid-extinction would canonize the wrong routing. The runbook
> aborts whole, by design.

The same whole-or-nothing applies to every gate in `ignite.sh`: a failed
precondition aborts ignition entirely; there is no "freeze what's healthy."

### Differ SLA (opens at freeze commit)

- **SEAM / DELIVERY candidates: judged same-few-hours.** The candidate diff
  is offline and free once their captures exist:
  `python3 harness_plan_diff.py diff --golden golden/plans --candidate <dir>
  --manifest golden/manifest.json`
- SEAM tweak-op captures land in `golden/tweaks/<case_id>.json` (contract in
  the manifest), judged via
  `python3 harness_plan_diff.py tweak-judge --manifest golden/manifest.json
  --captures golden/tweaks`.
- Verdict semantics on launch day: **RED = no flip.** YELLOW = itemized
  drift, flip only with a deliberate, recorded decision. GREEN = the corpus
  saw no regression (not proof of improvement).
- Re-freeze is a deliberate act with Zac's sign-off recorded in the commit
  that replaces `golden/plans/` — never automatic, never same-day-casual.

---

## §2 Deploy order, quiet window, no-regress — TRUTH-owned

*[TRUTH: fill. Known constraints HARNESS depends on: quiet-window gate reads
DB in-flight jobs, not `modal app list` tasks; deploys batch + announce per
the orphan law; `predeploy_no_regress.py` ancestry gate;
`golden/validate_deploy_addition.py` merges here, post-freeze only.]*

## §3 Flip sequence + rollback — TRUTH-owned (SEAM consulted)

*[TRUTH: fill. HARNESS interlock: every editorial flip runs the differ
pre-flip (§1 SLA); a RED verdict blocks the flip, no override path.]*
