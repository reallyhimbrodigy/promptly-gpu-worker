# Promptly — standing rules for every agent

These apply to every task, every agent, every commit. They are not advice.

## Rule 0 — ONE deploy lineage: `zero-reject-routing`, and only TRUTH deploys

**Canonical worker deploy branch: `zero-reject-routing`** (reconciled
2026-08-09: `agent/smoothness` — which carried the live image v521 = `1601ae0`
— was merged in at `d9c6e4d`, so the live commit is an ancestor of this branch
and every deploy from it). The live commit being an ancestor of the deploying
HEAD is now ENFORCED by `predeploy_no_regress.py` — a deploy from any forked
branch fails the gate (`PROMPTLY_ALLOW_ROLLBACK=1` is the only, deliberate,
per-run exception).

**The only cross-lane deploy truth is `modal app history promptly-gpu-worker`.**
`.last_deployed_commit` is an UNTRACKED per-checkout cache written from that
history by `deploy.sh`; it must never be git-tracked again (validate_deploy
check `_last_deployed_commit_untracked` enforces this). To read what is
deployed, ask Modal, then verify **function presence in the running image**
(grep the deployed bundle) — never trust a branch name or a SHA alone.

**Only the TRUTH lane runs `deploy.sh` or pushes a deploy branch.** Every other
lane commits to its `lane/<name>` branch and files a deploy request with TRUTH
(see `LANE_OWNERSHIP.md`). `main` is a read-only fast-forward mirror of
`zero-reject-routing`, kept current after every deploy; **never treat
origin/main as the source of truth for what is running** (it once sat 447
commits behind — a *dead main* — and cost hours of misdirected investigation).
(content-studio is separate: it *does* deploy from `main` via Render.)

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
- **Render determinism (2026-08-01)**: the x264 encode thread count is PINNED
  (`_X264_ENCODE_THREADS=48` in handler.py, never x264-auto — auto makes output
  depend on the machine's core count). Renders are now **byte-identical on a
  fixed plan across ANY cpu**. Byte-identity is the cert bar — any difference on
  a fixed plan is a **DEFECT**, not variance. No PSNR/SSIM threshold for
  fixed-plan A/Bs (this retires the old "x264 nondeterminism ~0.99994"
  determinism-relative bar). A canary/harness that renders the pipeline MUST
  mount the deployed app's FULL secret set (incl. `promptly-lang-flags`) — a
  missing secret changes the render flags and confounds every comparison.

## Working agreement

- Every agent works in **its own git worktree**. Never edit outside your
  assigned region.
- **The `speed` agent owns merge and deploy.** Nobody else deploys. Ever. All
  branches merge through the speed worktree, which runs `validate_deploy.py` and
  `deploy.sh`. Other agents open their work for merge; they never touch prod.
- Report format: what shipped, what number moved. One line per item.
- Ask Zac only for taste calls and credentials. Never for permission to measure.

## Standing rules earned 2026-08-27

- **Nothing ships on a path you haven't verified in the running image.** Commit
  truth is not truth. Precedent: the cpu=8 regression (completion 78.9%→35.7%).
- **Mechanical rewrites require a semantic check, not just a shape check.** A
  regex converted 19 call sites and the cert went green; pyflakes caught a
  definition placed after its callers AND a local that rebound the name,
  shadowing it for a whole function. A cert reasons about text; scope is not text.
- **A clean zero is guilty until proven innocent.** Four zeros in one day were
  all reader bugs, not measurements: 0/18 legs, 42/42 empty, 0.0 density, 0.01
  density. A zero that looks tidy is the most expensive result to trust.
- **Never infer a universal shape from one sampled instance.** Three times in one
  day: `1.3.16 (234)` broke a version parser that sampled one format; a
  `[render-full]` filter excluded 100% of the `[RENDERCLOCK]` lines it wrapped;
  and `edit_recipe` was read as nested from one diverted-route sample when
  std-editorial — 77% of output — writes it FLAT. Sample the bucket you intend
  to measure, or measure the bucket you sampled.
