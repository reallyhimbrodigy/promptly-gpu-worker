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
- **An AST scan of a closure body cannot see mutation one frame down.**
  Enumerate what a function PASSES, not just what it assigns.
  `_do_shot_changes` scanned clean — zero stores, zero mutating method calls on
  any captured name — because it only *passes* `_shot_change_scores` as
  `out_scores=`. The callee fills it; line 42506 reads it back. It is a second
  output wearing an input's clothes, and it would have crossed a container
  boundary and arrived EMPTY. Out-parameters, callee-side writes, anything by
  reference: the scan is blind to all of it.
  **And it would have failed SILENTLY** — downstream reads an empty dict, not an
  exception. Scores quietly become nothing, the plan degrades, every gate passes.
  Fix: return `(result, scores)`; never accept an out-parameter across a seam.

## Standing rules earned 2026-09-05 (agentic lane)

- **A check that reads SOURCE cannot tell code from string content.** The rule
  that prevents unmounted prompt blocks was itself unmounted: a
  string-replacement anchor matched prose inside a docstring, so the definition
  AND its call were inserted into that string. The file parsed, every text and
  AST-over-source check passed, and the rule never ran once — committed as the
  fix for the exact class it then exemplified. Eight text-match false greens
  preceded it, each fixed with a more careful regex or an AST walk. The
  categorical fix is to **IMPORT THE MODULE AND ASSERT THE SYMBOL EXISTS**.
  Source is where code might be; runtime is where it is.

- **A checker that invents failures trains you to bypass it.** The first
  pre-commit hook exec'd each `_assert_*` in a hand-built namespace and blocked
  on a `NameError` that did not exist, while the real mutation went unnoticed.
  Replace a lying checker; never tune around it. Same principle as *a check that
  cries wolf gets loosened until it is not a check* — both failures end with the
  check switched off, one by hand and one by habit.

- **Verification output that contradicts the commit message BLOCKS the commit.**
  Not a judgement call. A message claimed "zero bare continues remain"; the
  verification printed five, at named line numbers, in the same step, and the
  commit went through. Enforced by `.githooks/pre-commit`, which runs the
  adversarial gate and imports the module for its asserts.

- **A half-ruling is refused where it is made.** A beat ruled `sfx: yes` with no
  `sfx_name` decided the moment needs SOUND and never said which — and which
  sound is not derivable, so the beat silently built nothing while the aggregate
  read "sfx ruled 2, built 0". Every family that carries content (text→copy,
  card→hero, sfx→name, cutaway→keyword) is completed at ruling time, when it
  costs one line, not discovered at build time when it costs the placement.

- **A capability in the schema will be used.** The prompt said "do not
  orchestrate" and the agent orchestrated anyway. Telling a model not to use a
  tool it has is a preference; not giving it the tool is a property. Withhold
  the capability, or enforce in the dispatch — but do not rely on the prompt.
  (Corollary, measured: the tool list is part of the CACHED PREFIX. Changing it
  mid-run cost 43,222 cache_write tokens, 74% of a run. Gate in the handler, not
  the schema.)

- **A derived signal that is not printed cannot be verified.** `visual_cut
  _candidates` was computed and ledgered and never shown, so a run that kept
  100% was indistinguishable from a detector that found nothing, errored, or
  never ran — and its absence from a log that never contained it was read as
  evidence it was unwired.

## Standing rules earned 2026-09-07 (the component parity port)

- **A CHANGE THAT IS REAL AND WRONG is a third failure class, and the inert
  check cannot see it.** This lane has had "nothing happened" (`placement_inert`)
  and "nobody looked" (`placement_effect_uncovered`). StagedPush was neither: the
  composite genuinely changed those frames, it just spliced in an UN-ZOOMED copy
  of them. Right frame count, right duration, real footage, real difference from
  the previous file — and no zoom. Six other types separated cleanly from their
  passthrough arms while StagedPush's "real" render was byte-for-byte its own
  passthrough (psnr@1.0 24.59 for both), because `StagedPush.tsx` refuses
  `stages.length < 2` by returning nothing.
  **The only instrument that sees this class compares the output against the
  input it was DERIVED FROM, not against the pipeline state before the step.**
  A step-to-step diff says something happened; only source-to-output says the
  right thing happened.

- **A threshold borrowed from a different code path is a guess wearing a
  measurement's clothes.** The zoom geometry bar was set at 40 dB from an ffmpeg
  re-encode reading 45.1 — but the failure being detected renders through
  CHROMIUM, which loses far more. Measured: real 15.94-16.84, passthrough
  24.30-26.11. At 40.0 both arms read as "changed" and the check passed the
  exact failure it existed to catch. Measure the threshold on the ARMS YOU WILL
  ACTUALLY SEE, never on an analogous path.

- **Measure where the signal is largest, not where the window is convenient.**
  Second half of the same lesson: aimed at the clip HEAD, the geometry check read
  StagedPush at 20.37 dB and called a perfectly applied zoom inert — every ramp
  legitimately starts at scale 1.0, so the head is where a real move and a
  passthrough look most alike. The tables that say where the peak is were already
  ported; the check just was not using them.

- **"Is it called" is not "is it choosing".** A check that the derivation
  function appears in the call graph stayed green when the primary assignment
  became a hardcoded literal, because a fallback path further down still called
  it. Walk every assignment to the name and refuse a constant.

- **One hop of indirection is still scope.** `smoke_chain_paths` tested only the
  expression AT the call site, so binding a constant to a variable one line above
  defeated it entirely — the argument is a Name, not a Constant. Resolve through
  the binding. (Third instance of *scope is not text* in this repo.)

## Contract rules for the three-container split (PR #1)

- **What crosses a boundary: artifacts staged to S3 plus plain data. Never a
  local path, never a future, never an out-parameter.** Two of four relocated
  closures carried a hidden crosser — `future_gemini_proxy` (a live Future) and
  `_shot_change_scores` (an out-param). Neither was visible from line numbers or
  from an AST scan of the closure body.
- **Every relocated call asserts its outputs are non-empty and well-typed before
  returning.** A scores dict that arrives empty must PAGE, not degrade a plan.
  This is the check that would have caught the out-parameter with nobody reading
  the code.
- **TWO checks, two failure classes.** Byte-identity in-process proves the
  SIGNATURE change is safe and proves NOTHING about the return contract — a
  local work_dir works whether or not the contract is right. Relocation needs its
  own verification: a job through the REAL boundary, output compared against the
  in-process baseline. Same lesson as cert-green vs deploy-green.
