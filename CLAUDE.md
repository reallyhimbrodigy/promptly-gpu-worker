# Promptly — standing rules for every agent

These apply to every task, every agent, every commit. They are not advice.

## Rule 1 — Every fix ships with a check that makes its regression impossible

Not a comment. Not a note in a report. A gate assertion, a fingerprint, a cert,
or a validate_deploy check. **If you cannot name the check, the fix is not
finished.**

Precedent: the deploy-state guard, the MG anti-drift fingerprint, the
`UNKNOWN=0` gate, `cert_prompt_content_diff`, the migration-guard smoke test.
Every one of those caught a real regression later. The fixes that relied on
memory instead all rotted.

## Rule 2 — Nothing is "done" until observed working on real traffic, with a denominator

`built` ≠ `committed` ≠ `deployed` ≠ `working`.

Report zero only with what it is zero *out of*. "0 blocks" is meaningless;
"0 blocks / 47 uploads" is a result. Nine features have shipped gate-green and
done nothing: the BOOLEAN preview column, an unmounted `moodreel_editor`,
`_progressive_enabled` reading only a dark global, an unset `KNOWN_OUTAGE_UNTIL`,
the memory-snapshot env freeze, unallowlisted analytics events, and the
`extra="forbid"` schema mirror that silently blocked `motionTokens`.

**A secret flip is not live until a redeploy.** Memory snapshots capture
`os.environ` at deploy time.

## Rule 3 — Never send Zac a pair that has not been proven to differ

Frame-diff every arm before it reaches his eye. Report PSNR and the
consecutive-frame crops. Three rounds of his time were lost judging pairs that
may have been identical.

## Rule 4 — Assert only what you can directly observe

Label everything else as inference, explicitly. The frontend owns client and DB
truth; the backend owns Modal, deploy and worker truth. Neither states the
other's domain as fact. A wrong revert order was issued because an inferred
deploy was reported as observed.

## Rule 5 — Cut every measurement to a clean cohort

Six false alarms came from contaminated windows: outage hours, pre-flip traffic,
pre-deploy jobs, small-sample zeros. Before reporting any rate, state the window
and why it is clean. Cut cost and latency **by route** — a blended number over a
mixed route population is not a product metric.

## Rule 6 — Measure before building, and price before spending

No synthetic Modal spend. Validate on watched real traffic. Every Modal run
carries a stated dollar figure in advance, and all agent test spend is reported
in the same ledger as user-job spend with a running session total.
`.spawn()`ed containers outlive the local orchestrator — a batch is dead only
when `modal app list` shows 0 tasks.

## Rule 7 — Cut by USER before declaring a systemic failure

Compute failure rates **per affected user**, not per job. A user who fails five
times and gives up is **one lost user, not five failures** — per-job counting
inflates every class by the retry multiplier, which is exactly what made a
one-user 100fps bug read as a 67% outage. **Report both numbers; lead with the
user count.**

Precedent from Aug 1: the render "wave" (1 user), UPLOAD_STALLED (5 of 6 = 1
user), RENDER_FATAL (4 of N = 1 user) — three classes, three single users, each
inflated by retries into an apparent outage.

## Standing product laws

- **Zero-reject**: content classes are ROUTES, not errors. The only permitted
  rejections are `<2.0s` and `>300s`.
- **Quality wins over speed** in every trade, including reconsidering speed
  decisions already made.
- **Never retry as an answer to failure** — root-cause and exterminate.
- **$0.10/job** is the cost law. **90s end-to-end** is the latency law.
- **Fail loudly to us, never to the user.**

## Working agreement

- Every agent works in **its own git worktree**. Never edit outside your
  assigned region.
- **The `speed` agent owns merge and deploy.** Nobody else deploys. Ever. All
  branches merge through the speed worktree, which runs `validate_deploy.py` and
  `deploy.sh`. Other agents open their work for merge; they never touch prod.
- Report format: what shipped, what number moved. One line per item.
- Ask Zac only for taste calls and credentials. Never for permission to measure.
