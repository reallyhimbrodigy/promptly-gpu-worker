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

- **INSTRUMENTS ARE REVIEWED ACROSS LANES, DELIBERATELY.** A check written by the
  person who wrote the code is STRUCTURALLY WEAKER than one written by someone
  reading it cold — not because the author is careless, but because every
  failure in the family below is invisible from the inside. You wrote the
  `[:20]` and you remember it is 20. You wrote the predicate and you know which
  process it runs in. The reader has only the output.

  The evidence is the record: on 2026-09-09 nearly every instrument defect was
  found by the OTHER lane, in files their author had read many times — the
  boundary-side observable, the `/tmp` cross-branch backup, the missing flag
  writer, the empty-leg floors, the truncated `sample`, the loose-pattern
  floor-checker. Including a mis-citation made *while arguing for precision
  about naming*. That was happening incidentally all day and caught more than
  either lane's own discipline; **it should happen on purpose.**

  So: when a lane ships a check, the other lane reads it before it is trusted —
  and reads it for the four costumes specifically, not for style.

  **The proof, 2026-09-09 — four found in each direction, NONE found by the
  author.** This is not a soft observation that review is good practice; it is
  evidence that self-review is structurally blind to these four costumes.

  | found by BUILDER-2, in BUILDER-1's files | found by BUILDER-1, in BUILDER-2's files |
  |---|---|
  | the observable computed on the wrong side of a process boundary | the truncated `sample` printed as a complete record |
  | the `/tmp` backup shared across every branch and worktree | the orphan check scoped one schema too narrow |
  | the missing writer behind the removal flag | the filter mutation that went semantically dead |
  | the empty-leg floors (26 of 27 across both lanes) | the stale-anchor `edit_quality`, from the other end |

  And the sharper cautionary case is the one that WOULD HAVE SURVIVED REVIEW: a
  residue-checker that mutated its own checkout and restored correctly every
  time it COMPLETED. It looks right in the diff and passes every run; only a
  kill exposes it, leaving exactly the residue it exists to detect, under the
  name of the check for it. The cruder failure — running a mutating sweep during
  a live round — was louder, and therefore cheaper.

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

- **GREP PROVES A STRING IS PRESENT; ONLY THE AST PROVES THE CODE RUNS.** Six
  checks in this port were too weak to fire on their first mutation, and every
  one failed the same way: a substring that survived the change it existed to
  catch. `if False:` leaves the `fail()` string in the file. Renaming a call to
  `_NOT_record_effect(` still CONTAINS `_record_effect(`. Moving a literal from
  `"type": "StatCard"` to `_ctype = "StatCard"` moves it out of the pattern and
  changes nothing else. Deleting a ledger write leaves the name in the print
  statement. Deleting the field a print reads leaves the print's header intact.
  A guard rewritten from a conjunction to a disjunction puts the same name in
  the same condition and means the opposite.
  **This is the fifth consecutive session in which it has happened.** It is no
  longer a mistake to notice; it is a default to design against. A check on
  BEHAVIOUR reads the AST — every assignment to the name, the guard that wraps
  the call, the call's own identifier — or better, IMPORTS THE MODULE AND RUNS
  THE PREDICATE. Reserve substring tests for the one thing they are honest
  about: a literal that must be present verbatim.

- **A THRESHOLD FROM ONE DRAW IS NOT A THRESHOLD — it measures the fixture, not
  the thing.** The zoom geometry bar was set at 20.0 dB from a single
  high-detail fixture, where real zooms read 15.94-16.84 and passthroughs
  24.30-26.11. On a FLAT field the whole scale moves and the arms SWAP SIDES:

      content    arm    abs psnr   bar 20.0 says
      detailed   real      15.99   APPLIED
      detailed   pass      26.11   NOT APPLIED
      FLAT       real      26.91   NOT APPLIED   <-- a real zoom, called a no-op
      FLAT       pass      53.25   NOT APPLIED

  It produced three false failures in round 36 and would have sent someone to
  edit three working components. The check was never measuring the component; it
  was measuring how much DETAIL the source had.
  This is the same failure as the invented fixture, one level up: **both are a
  threshold from one draw.** Calibrate on every content class the corpus
  actually contains — and prefer a form where the content CANCELS (a ratio
  within one measurement) over any absolute bar. The replacement asks which
  SCALE better explains the render, so both terms read the same pixels.
  **And make the test one-sided where the errors are asymmetric**: a false "it
  did not work" sends someone to edit working code; a missed one costs less.

- **A BARE ENUM IS A LIST OF WORDS.** Two rounds read "1 distinct of 29
  selectable, StatCard=4" and it was read as taste, then as incumbency. It was
  neither: the cached prefix named StatCard and ProgressBar and NOTHING ELSE,
  while the enum offered 29 bare names. Learning what any of the other 27 was
  for cost a knowledge-read turn the agent never spent, so it picked the only
  component it had ever been told about — and the field description wrote the
  incumbency down: "Defaults to StatCard only if you do not say."
  **A capability the agent cannot NAME is indistinguishable from one it
  declined, and a capability it cannot UNDERSTAND is indistinguishable from one
  it rejected.** An enum entry ships with the one line that says what it claims,
  in the surface where the choice is made — 469 tokens bought 29 usable options.
  Corollary: every silent default is a vote for the incumbent. Three of them sat
  behind that enum, including one where an untyped item became a rendered
  StatCard nobody chose and was REPORTED as chosen.

- **A MEASURED TIMING TABLE THAT NOTHING READS IS THE MOST EXPENSIVE KIND OF
  DEAD CODE, because the family it corrects ships VISIBLY WRONG and nothing
  errors.** Twice in one port: `_SFX_ATTACK_MS` (16 argmax-of-RMS-envelope
  measurements) and `_MG_ATTACK_MS` (24 entrance times from the MGAttackProbe
  battery) were both built and both mounted in `_asset_inventory.json`, and the
  MG one was read by NOTHING — so every motion graphic this lane ever placed
  entered late by its own attack, PullQuote by 500ms and Reticle by 400ms. The
  sound table nearly went the same way.
  These tables are expensive to produce and silent when absent: the component
  still renders, still lands in the manifest, still passes every count. **When a
  measured table lands, the commit that adds it wires a CONSUMER and a check
  that the consumer is called** — the same bar as a counter being printed in the
  commit that adds it. `cert_production_table_parity.py` reports PORTED BUT DARK
  for exactly this.

- **"Is it called" is not "is it choosing".** A check that the derivation
  function appears in the call graph stayed green when the primary assignment
  became a hardcoded literal, because a fallback path further down still called
  it. Walk every assignment to the name and refuse a constant.

- **One hop of indirection is still scope.** `smoke_chain_paths` tested only the
  expression AT the call site, so binding a constant to a variable one line above
  defeated it entirely — the argument is a Name, not a Constant. Resolve through
  the binding. (Third instance of *scope is not text* in this repo.)

## THE FAMILY: A FAILURE THAT RENDERS IDENTICALLY TO A SUCCESS

**Read this header, not the twenty-four instances.** Nearly every rule below is
one shape wearing different clothes: *the failed thing and the working thing
produce the same output, so nothing in the log distinguishes them.* A reader who
internalises the shape catches the twenty-fifth instance without having seen it.

The shape has four recurring costumes:

1. **ABSENCE RENDERED AS A VALUE.** `or 0` turns a key nobody wrote into a
   measured zero. `alpha_layer_max` returns `None` and the guard reads
   `x <= 260`. `paint_ms` is never recorded and prints `0.0s` beside a 458s
   stage. `float(duration or 0)` converts ABSENT into a well-typed 0.0 that no
   consumer-side check can see. **Return a STATE — MEASURED / ABSENT / FAILED —
   and make ABSENT and FAILED fail.**

2. **A CHECK THAT ASSERTS NOTHING.** `all([])` is True, so 26 of 27 red proofs
   passed on an empty mutation list. A leg iterating a population that is empty
   *here*. A walk that finds zero enums. A mutation whose anchor no longer
   matches, whose operand went empty, whose match landed in prose, or that never
   parsed. A pattern loose enough to match the defect it forbids. **Count the
   population and assert the count.**

2b. **AND ITS TWIN: A PATTERN TIGHT ENOUGH TO EXCLUDE A CORRECT IMPLEMENTATION
   IS NOT A CHECK EITHER.** The floors checker went both ways on one axis: v1
   matched a shape loose enough to admit the defect (`all(r) and rc == 0`
   passed); v2 matched a shape tight enough to reject a *working* floor
   (`red and red == len(MUTATIONS)` — which floors on the COUNT rather than the
   container, and is equally valid). It failed 5 of 16 correct harnesses in the
   other lane. A style rule wearing a correctness rule's clothes, and the next
   person to hit it "fixes" their working code to match the checker's spelling.
   **Assert the property by EXECUTION where you can** — the red proof for this
   was right all along, because it emptied a real harness and observed
   `0/0, exit 1`. The static matcher and the executed proof disagreed about what
   the rule was, and the proof was correct.

3. **A MEASUREMENT OF THE WRONG THING.** An observable computed on the wrong
   side of a process boundary. Two numbers with the same name counting different
   things (visual cuts vs beats-ruled-cut). A judgement wearing a measurement's
   clothes (model-annotated rates printed as fact). A truncated list printed as
   a total. A stale identifier from a run that no longer exists. **State what a
   number COUNTS and WHERE it was computed, beside the number.**

4. **A PRODUCER OR CONSUMER THAT ISN'T THERE.** A gate demanding a field the
   schema does not offer. A flag with a reader and no writer. A tool in the
   enum that the prompt never explains. A capability mounted and never read.
   **A flag's test surface is the PAIR, not the reader.**

**Two corollaries about verifying a writer:**

- **A STALE IDENTIFIER AND A REAL ONE ARE INDISTINGUISHABLE ONCE WRITTEN DOWN.**
  A killed run and a live run produce identically well-formed fingerprints;
  `91f4d58c3c1c0e51` sat in a PRE-REGISTRATION for an hour looking exactly like
  a fact — the one class of document nobody re-checks, because re-checking it
  after the result is what a pre-registration exists to prevent. A hash carries
  no evidence of its own currency. Re-read the identifier from the artifact that
  owns it (`mount_sha.txt`, `modal app history`), never from a message.

- **VERIFY A WRITER IN A WORKTREE YOU CREATE FOR THE PURPOSE.**
  `git worktree add --detach <tmp> HEAD` costs a second and makes the whole
  class impossible. Twice today the verification and the thing verified were the
  same writer: a background red-proof sweep drifted a frozen fingerprint and
  aborted a nine-launch round mid-arm, and Builder-2's first residue-checker
  mutated the checkout it ran from — it restored correctly every time it
  completed, and a kill would have left exactly the residue it exists to detect,
  shipping the hazard into the repo under the name of the check for it. **A
  mutating harness and a running round cannot share a worktree at all; there is
  no safe moment.**

**Why it keeps happening:** every one of these is invisible from the inside. You
wrote the `[:20]` and you remember it is 20. You wrote the predicate and you know
which process it runs in. The reader has neither. And the two people who found
most of these found them in each other's files, not their own.

**The corollary that decides priority:** a failure mode with a *plausible
innocent explanation* is worse than one that fires constantly. `anchor 0x`
demands investigation; `FileNotFoundError` on a `/tmp` path reads as someone
else's laptop. Same rot, one gets looked at.

## Standing rules earned 2026-09-09 (a mutation that changes a file, not a result)

- **A TRUNCATED LIST MUST CARRY ITS DENOMINATOR** (Builder-2's framing). It is
  Rule 2 applied to OUTPUT rather than measurement: *report zero only with what
  it is zero out of* and *print a list only with what it is a subset of* are the
  same instruction, and they fail the same way — the incomplete thing renders
  identically to the complete thing.

  MEASURE THE CLASS BEFORE CHECKING IT. A first scan found **187** `[:N]` slices
  in print-bearing scopes and the number was useless: it is dominated by
  `str[:200]` truncating error messages, which is legitimate. Truncating a
  MESSAGE loses characters; truncating a COLLECTION loses countable items, and
  only the second makes a subset read as a total. Narrowed to `for x in
  NAME[:N]` that prints: **4** in agentic_editor_app.py, **2** in
  smoke_tree_parses.py, 0 elsewhere. Four real instances beat a check that fires
  on 187.

  One of the four was `_rej[:6]` on the CUTAWAY REJECTIONS — a run rejecting 30
  would print 6 and read as 6, in the family whose entire diagnosis that round
  was "ruled zero".

- **AND THE MECHANICAL CHECK CANNOT CATCH THE CASE THAT MOTIVATED IT.**
  `for _v in (_vq.get("sample") or [])` has no slice: the list was ALREADY a
  subset when it reached the printer. `for x in NAME[:N]` catches truncation AT
  the print and is blind to truncation BEFORE it. The other half is a
  CONVENTION, not a proof, and is recorded as one: a subset must be named where
  it is CREATED — `sample`, `head`, `first`, `subset` — and printed with a count
  beside it. Prefer removing the truncation to annotating it: the per-beat
  record is nine lines and never needed sampling at all.

- **A TRUNCATED PRINT LOOKS CORRECT FROM THE INSIDE.** Neither agent caught this
  in their own file while catching it in the other's — one found it in a check
  shipped two hours earlier, the other in a printer read every round for weeks.
  You wrote the `[:20]` and you remember it is 20. The reader does not. This is
  why it is a rule and not two fixes.

- **A MUTATING HARNESS AND A RUNNING ROUND CANNOT SHARE A WORKTREE.** Red proofs
  are WRITERS — they mutate the file under test and restore it — and
  `agentic_editor_app.py` is MOUNTED. Launching a background verification of the
  red proofs during a nine-launch ablation drifted the frozen fingerprint and
  the round ABORTED mid-arm. Done twice in twenty minutes, the second time
  immediately after diagnosing it, by the person who had just written the rule
  down. The suite is named "run the checks"; nothing in that phrase says it
  rewrites 12,000 lines and puts them back.

- **A FIXTURE BELONGS IN THE TREE; A BACKUP BELONGS IN MEMORY.** They are
  opposite requirements and converging them is a mistake. A fixture (mutation
  blocks) must drift WITH the tree or fail loudly at merge — so it lives in
  `red_proof_blocks/`. A backup must not survive the run that made it — so it
  lives in memory, never at a `/tmp` path shared across every branch and
  worktree on the machine. Builder-2 watched one such backup silently restore
  ANOTHER BRANCH'S app over their working copy — a 914-line rewrite — and the
  harness then printed `19/19 RED-proven` about a file it had just replaced with
  a stranger.

- **FOUR SYMPTOMS OF THE FIXTURE-OUTSIDE-THE-TREE DEFECT**, and the fourth is
  orthogonal to where the backup lives:
      MISSING              died at import, reported nothing
      DRIFTED              rewrapped four lines, reported `anchor 0x`
      STALE FROM A BRANCH  silent 914-line rewrite, green tally
      INTERRUPTED          SIGKILL between mutate and restore leaves the MUTANT
                           on disk — in-memory backup does not survive a kill
  Only a post-run `git status --porcelain <mounted file>` catches the fourth,
  and it must name WHICH harness left the residue. Builder-2 found
  `led["cut_word_intrusions"] = []` sitting on disk after a killed sweep: one
  line in 12,000, in the measurement whose whole job is that count, and every
  gate passes on an empty list.

- **26 OF 27 RED PROOFS PASSED ON AN EMPTY MUTATION LIST.** `all([])` is True and
  `0 == len([])` is True, so a harness whose mutations are deleted — bad merge,
  botched refactor, commented-out block — reports SUCCESS. 10 of 11 here, 16 of
  16 on Builder-2's tree. **The verification layer failing in exactly the way it
  exists to catch**, and every "RED-proven" claim in either lane rested on it.
  The floor is one token: `r and all(r)`, `MUTATIONS and red == len(MUTATIONS)`.
  And the floor-CHECKER needs a floor too — a check over an empty population
  asserts nothing, including the check that checks for that.

- **A PATTERN LOOSE ENOUGH TO MATCH THE DEFECT IS NOT A CHECK.** The first
  floor-checker matched the SHAPE `BoolOp and And and all(...)` and therefore
  passed `all(r) and rc == 0`, which has no floor at all — it would have
  green-lit the exact defect it was written for, and only its own RED proof
  exposed it. Assert the PROPERTY: the container the exit reasons about must
  also appear as a bare truthy operand. Same family as keying a concept map to
  incidental wording that survives the mutation deleting the sentence.

- **A FAILURE MODE WITH A PLAUSIBLE INNOCENT EXPLANATION IS WORSE THAN ONE THAT
  FIRES CONSTANTLY.** The same fixture-outside-the-tree rot surfaced two ways:
  `anchor 0x`, which names itself and demands investigation, and
  `FileNotFoundError` on a `/tmp` path, which reads as someone else's laptop and
  gets skipped. A chronic red is ignored; an *innocent-looking* red is never
  examined at all. Builder-2's harness reported nothing for weeks that way —
  nineteen legs believed, zero running.

- **A CORRECT RULE THAT ARRIVES AS A WAVE OF RED GETS REVERTED, NOT
  INVESTIGATED.** An unconditional `ast.parse` guard on mutants would have
  turned FOUR working harnesses red here (they mutate `.md`/`.json`, or
  deliberately mutate into unparseable code) and two on Builder-2's tree. "Four
  red proofs broke when the guard landed" reads as the guard being wrong, and it
  would have been discarded on its first day for being right about nothing.
  Crying wolf at BIRTH rather than developing. Scope it before landing it, or
  land it with the scoping already in.

- **AN OBSERVABLE MUST BE COMPUTED ON THE SIDE OF THE BOUNDARY IT DESCRIBES**
  (Builder-2). `prefix_material_enabled()` gated the prefix material inside
  `edit()` — `@app.function`, the CONTAINER. `prefix_material_state()` produced
  the report inside `main()` — `@app.local_entrypoint`, THE DEVELOPER'S MACHINE.
  Same function, same predicate, same file, two processes, and `os.environ` is
  per-process. The report described the wrong machine, and failed in whichever
  direction the environments disagreed: export locally and the log says REMOVED
  while the container runs ON (confirming a fabricated null); pass a parameter
  with a clean shell and the log says ON while the container removes (making a
  real arm unverifiable). Neither is visible in the log, because the log is what
  is wrong. Record the state where it is USED and print THAT.

- **A FLAG'S TEST SURFACE IS THE PAIR, NOT THE READER** (Builder-2). The removal
  switches had a reader, a smoke driving the reader, and a red proof mutating
  the reader — and NOTHING ANYWHERE SET THEM in the container. A consumer with
  no producer, in the mechanism a whole round's attribution depended on. It
  would have produced a FABRICATED NULL: the arm reports no effect because the
  arm never happened, and under a null-is-attributable registration that reads
  as a finding rather than as a broken arm. A flag reads as configuration; it is
  a wire. Hardening the reader does nothing for a missing writer.

- **A CHECK THAT COMPARES AGAINST AN EMPTY SET PASSES, AND PASSES QUIETLY.** An
  ordering leg compared an `os.environ` write against `prefix_material_enabled`
  call sites *inside* `edit()` — there are none, the predicate is read at module
  scope — so it compared against an empty list, asserted nothing, and passed
  with the write relocated to the end of the function. The precondition guard
  catches an empty operand in a MUTATION; nothing catches an empty population in
  a CHECK LEG except asking, every time, what it iterates and whether that can
  be empty here. Same instruction as the denominator rule one level up: a leg
  over an empty set and a printed list with no total both look complete and both
  assert nothing.

- **A FOURTH WAY A MUTATION STOPS MUTATING: IT DOES NOT PARSE.** `mut()` must
  `ast.parse` the mutant before writing it; a SyntaxError is a HARNESS FAILURE,
  never a silent non-result. The full set now:
      anchor 0x               a refactor moved it        count guard
      operand is empty        the edit is a no-op        precondition
      match lands in prose    a comment owns the anchor  _match_is_prose
      mutant will not parse   it never ran at all        ast.parse

- **A HARNESS MUST FAIL LOUDLY AND DIFFERENTLY FROM THE THINGS IT RUNS** (Builder-2).
  A suite run through macOS `timeout` — which does not exist there — reported
  **163/163 FAIL**. That tally is indistinguishable from a real catastrophe, and
  from `0/163 FAIL`, because the RUNNER's failure was reported through the same
  channel as the checks' results. A missing runner must **exit 2 with HARNESS**
  and contribute NO per-check rows. "Read the first line" is not the lesson —
  next time the first line will be plausible.

  Same family as *read exit codes without a pipe*: the question is always
  whether the thing reporting is the thing being measured.

- **TWENTY RED CHECKS CAN BE ONE FACT.** ~20 handler.py certs went red at once
  and read as "the handler certs are red again". One stash pop, one file, one
  cause. A tally is not a count of problems, and treating it as twenty sends
  someone into twenty investigations.

- **A JUDGEMENT WEARING A MEASUREMENT'S CLOTHES.** `reference_index.json`'s 153
  beats are `claude-sonnet-5`'s READING of ten videos, not mechanical counts,
  and nothing in the artifact says so — it carries `source`, `note` and
  `beats_in_corpus`. So "reference median 0.253 cuts/s" printed in the agent's
  own report as a fact all week. Every rate ships its PROVENANCE beside it:
  annotator, model, date, and MODEL-ANNOTATED vs COUNTED per family. The rule
  that rates GRADE and never instruct only holds if the grade is honest about
  what it is.

- **AND CROSS-CORPUS RATES CARRY AN ANNOTATOR SEAM.** `reference_videos` is
  claude-sonnet-5 (2026-08-25); `trend_analyses` is gemini-2.5-pro (2026-03-16).
  Different model families, six months apart. Before any cross-corpus number is
  quoted, the seam must be bounded — and a same-family agreement number bounds
  only its own seam, never the cross-family one.

- **TWO NUMBERS WITH THE SAME NAME MEASURING DIFFERENT THINGS.** The reference
  corpus stores `cuts` (141 VISUAL cuts = 8.27/25s) and beats-ruled-cut (81 =
  4.75/25s). The trend corpus's `cuts.total_count` is VISUAL cuts. Comparing it
  against 4.75 produced "trends cut 46% more" when the truth is the reference
  cuts ~19% MORE (8.27 vs 6.92) — the direction inverted, reported as a finding.
  Before comparing two numbers, state what each one COUNTS.

- **A 404 THAT MEANS "WRONG PATH SHAPE" READS EXACTLY LIKE ONE THAT MEANS "THE
  DATA IS GONE."** Every `trend_videos.video_file_url` uses `/object/public/`
  against a PRIVATE bucket, and Supabase answers `Bucket not found`. Trusting
  that reading would have written off 743 MB of intact corpus — all 103 objects
  were present. Check the container before believing the contents are missing.

- **PROVE THE MUTATION CHANGES A RESULT, NOT A FILE.** `mut()` guards against an
  anchor that no longer matches — `count != 1` — and that guard is
  *structurally* blind to the other way a mutation dies: the anchor matches, the
  file changes, and **the behaviour does not**. A red proof removed the
  reference-retrieval `_unbuildable` filter to prove the filter filters. The day
  cutaway shipped, `_unbuildable` became EMPTY — and removing an empty filter is
  a no-op. The mutant was byte-different and behaviourally identical, and the
  proof read `NOT RED` with nothing wrong in the code it guards.

  Every prior instance in this repo was an anchor that stopped matching, which
  the occurrence guard catches. This one it cannot. The defence generalises even
  though its application does not: **a mutation must be shown to fail against
  the case it protects, on a fixture that actually exercises that case.** If
  removing the unbuildable filter cannot be shown to change an outcome on a
  fixture carrying an unbuildable treatment, the mutation is untested regardless
  of what the diff says.

- **A CHECK ANCHORED TO A LINE DIES WHEN THAT LINE IS LEGITIMATELY REMOVED, AND
  READS GREEN WHILE DEAD.** The per-tool orphan check bounded the acceptance gate
  on `_rejected.append(_why6)` — the bare-string append whose *correct* repair
  deleted it. So a correct fix blinded the check written to protect it, and it
  reported `lines NNNN..None` instead of a finding. Anchor on CONTROL FLOW
  (`if _why6:`), not on one spelling of one statement inside the region.

- **AN EXISTENCE CHECK CANNOT SEE A CHANGE IT DOES NOT COUNT — second instance.**
  `smoke_card_derived` kept ONE `_hero_desc` and overwrote it per hit, so with
  two `card_hero` declarations it judged whichever the walk reached last and
  passed with REQUIRED stripped from the other. Identical to the
  `"credit_charged": False` lesson already written down here, which did not
  prevent it. Collect ALL occurrences and assert the count.

- **A CHECK THAT IS ALWAYS RED IS A CHECK NOBODY READS.**
  `smoke_modal_app_preflight`'s condition was INVERTED: it flagged the safe
  `open(__file__)` form and was blind to the bare relative literal it exists for.
  Six false positives, permanently red — and hiding one real finding
  (`lumen_first_edit_app.py` importing `modal_app` without mounting it, so that
  harness could not start at all, and had not since 2026-08-15). I reported that
  red as "pre-existing" for rounds without naming it, which is exactly what a
  standing red buys.

- **A RED PROOF ANCHORED OUTSIDE THE TREE IS ONE REBOOT FROM PROVING NOTHING.**
  `red_proof_edit_quality` read its mutation blocks from `/tmp`. `/tmp` clears;
  the proof then reports `anchor 0x` forever while every other leg reads green.
  Fixtures a proof depends on live in the repo, next to the proof.

- **A WORKTREE HAS ITS OWN COPY OF EVERY TRACKED FILE.** A fix applied in the
  parent checkout does not reach the worktree that reads it — the smoke went on
  failing against an unedited Aug-31 copy while the "fix" sat on another branch.
  Tightest form of *an edit above a rebinding is not an edit*: same name, same
  content, wrong tree. And the parent checkout is `zero-reject-routing`, so that
  edit was also outside the assigned region.

## Standing rules earned 2026-09-08

- **Correct parts, wrong wiring — test the COMPOSITION, not only the pieces.**
  A distinct shape from every false green in this file. Those were checks that
  could not fire; this was three checks firing CORRECTLY on a system that was
  wrong. `alpha_paint_box` returned the right box, `region_psnr` computed a
  correct PSNR of the rectangle it was given, `region_effect_delta` subtracted
  correctly — and the verdict read 44.85 dB on a region whose real PSNR was
  9.45, because `crop` takes `w:h:x:y` and the box is `(x,y,w,h)`. Every unit
  behaved exactly as specified. **Unit-correct is not system-correct, and a
  smoke that only ever calls the parts separately will never see the seam.** Run
  the shipped functions composed, against real inputs, and pin the composed
  result — that run is what found it.

- **A temp copy of a mounted module belongs in the scratchpad, never beside the
  original.** I aborted rounds 37 and 38 for writes under `src/remotion` and
  then blocked round 43 with my own `_rb_tmp.mjs` — a path-rewritten copy of
  `remotion_batch.mjs`, put next to the original because that is where module
  resolution works. Both reasons were true and neither is a justification. The
  shipped module already defers its heavy imports and carries a run-as-main
  guard precisely so a smoke can import it without a copy. Builder-1's launch
  pre-flight caught it before any spend, which is where this guard has to live:
  `mount_scratch_check` only helps if someone remembers to run it, the
  pre-flight runs at the moment that matters.

- **A measurement with a free parameter is not a mechanism.** A normaliser was
  proposed to cancel content out of the zoom scale-fit bar, justified as
  mechanism rather than curve-fitting: the delta's other term IS the source's
  intrinsic responsiveness, so subtracting it should remove the variable that
  broke the two previous bars. It was refuted by the first population outside
  the fitted range — and the refutation nearly failed, because the two lanes
  disagreed about the intrinsic value by 6.6 dB while the margin at stake was 5.
  **Whichever number is right, a term whose value moves that far with a sampling
  choice cannot be the thing that cancels anything.** Before a normaliser is a
  mechanism, its INPUT must be well-defined; that source read 7.18-7.20 across
  the window the arms render and carried a 19.36 outlier from a later scene, so
  "its intrinsic" was never one number.

- **Settle a disagreement by reproducing the other number, not by defending
  yours.** Seven plausible sampling methods spanned 7.07-10.21 and NONE produced
  13.80. That mattered more than the argument for 7.19: across the whole
  reproducible range the normaliser was either unseparable or worse than the raw
  measurement, so the conclusion held without anyone having to win. **Test the
  verdict across the range of the disputed quantity — if it survives everywhere,
  the dispute was never load-bearing.**

- **A term that separates identically-behaving populations is injecting, not
  cancelling.** v2-geometry's raw reals (-3.54..+0.59) sit almost exactly where
  Zac's real footage sits (-3.89..+1.88) — the same behaviour — while their
  intrinsics differ by 12 dB. Adding intrinsic drove them apart. When a
  correction moves two things that measured the same, it is adding a difference
  the raw measurement did not have.

- **Educate rather than validate applies to SHAPES, not just rules.** Three
  rounds built zero cards because the agent invented prop names. It had never
  been told any component's props: `card_props` said "in the shape its catalogue
  entry shows", and reading the catalogue costs a turn no agent spends. A
  refusal that is correct still is not the fix. The prop table is now GENERATED
  into the schema from the same constant the builder enforces and the cert
  derives from the components — one chain, no hand-written third copy.

- **WHEN WE ADVERTISE A SHAPE, THE ACCEPTOR MUST TAKE THE SHAPE WE ADVERTISED.**
  (Ruled by Zac 2026-09-08 on Builder-2's proposal, after the third instance.)
  The rule has a DIRECTION: the acceptor moves, not the caller. This is the
  shape half of *educate rather than validate* — if a surface publishes a form,
  that form must parse.

  Three instances, two lanes, one week, and all three were read as the model
  being careless:
    * `card_props` described its payload as "in the shape its catalogue entry
      shows" — a shape reachable only by spending a `read_knowledge` turn no
      agent spends. The agent invented `heroNumber`, the builder correctly
      refused, and THREE ROUNDS BUILT ZERO CARDS.
    * `_asset_inventory.json` advertises `sfx.files` WITH extensions
      (`boom.mp3`, `money-ching.mp3`) while `place_sfx` sanitised with
      `re.sub(r"[^A-Za-z0-9_-]", "", name)`, which strips the dot. The agent
      sent the name it was SHOWN and got `'boommp3' is not in the catalogue`:
      unmatchable by construction, 2 of 4 ruled sfx lost in one run.
    * What actually built cards was NOT the 25-type prop table but the one
      sentence offering the `card_hero`/`card_label` shorthand — the shape the
      agent already reaches for. The table has still never been exercised
      (round 42: `CARD PROPS: [StatCard label+value (shorthand)] x3`) and is
      either a prerequisite for a non-StatCard component or dead weight. It is
      recorded UNVALIDATED rather than credited for what the shorthand did.

  **A REFUSAL THAT IS TECHNICALLY CORRECT STILL LOSES THE PLACEMENT**, and it
  fails silently: the family simply arrives short, every gate passes, and the
  log reads like a judgement call the model made.

  The check is cheap and it is mandatory with any published catalogue: assert
  every shape the surface PUBLISHES resolves through the acceptor, driven by the
  shipped catalogue so a new entry is covered the day it lands.
  `smoke_sfx_name_shapes.py` does exactly this — 15 sounds x 2 shapes, both the
  advertised form and its stem, with traversal still refused.

- **WHEN YOU RESOLVE A CONFLICT IN CODE UNDER MUTATION TEST, RE-VERIFY THE
  MUTATIONS STILL APPLY.** (Ruled by Zac 2026-09-08.) A merge is where a
  mutation silently stops applying, and the silence is total.

  Two overlay mutations in `red_proof_edit_quality.py` targeted the literal
  `"[0:v][cap]overlay=0:0:eof_action=pass[outv]"`. Resolving a conflict moved
  that string INTO `alpha_composite_filter()`. The mutations were checked and
  still applied — but had they not, a 7/7 red proof would really have been 5/7
  with two mutations that changed nothing, and **a passing baseline and a
  passing restore look identical either way**, so no output would have differed.
  The proof would have gone on reporting 7/7 forever.

  This is *a mutation that does not mutate proves nothing* with a specific
  trigger: not a typo in the mutation, but a legitimate refactor moving the
  target out from under it. Hoisting an inline string into a function, renaming
  a constant, reindenting a block, taking `ours` in a conflict — every one of
  them can orphan a mutation while every test still passes. A red proof whose
  mutations do not apply is the purest false green available — a check that has
  stopped being a check while still saying the words.

  **THE CHECK, NAMED: `mut()`'s anchor guard in `red_proof_edit_quality.py`** —
  `if src.count(old) != 1: HARNESS FAILURE` — which refuses the mutation instead
  of reporting a pass. RED-PROVEN by orphaning a mutation the way a refactor
  does: the harness printed `HARNESS FAILURE [...] anchor 0x`, the tally fell to
  `6/7 RED-proven`, and it exited non-zero. Every red-proof harness carries that
  guard, and an ad-hoc mutation run that merely prints `[SKIP]` and continues
  does NOT satisfy this rule — printing a skip and passing anyway is the failure
  wearing the notice.

- **A CHECKOUT IS A CLAIM ABOUT THE PAST, NOT THE PRESENT.** (Ruled by Zac
  2026-09-08.) *Commit truth is not truth*, one level down.

  Builder-2 reported that `alpha_composite_filter` "does not exist in
  agentic_editor_app.py". It exists at line 3235 and is called at 6538. It did
  not exist in ITS WORKING COPY, which was 35 commits behind — so a property of
  the FILE was asserted from the state of a CHECKOUT.

  What it cost: the same defect was fixed twice on two branches, and the second
  fix was written up as a SECOND INDEPENDENT PRODUCER of the truncation. That
  reached the reliability pillar, where it changed what a round could close — a
  green round would have looked like half a fix standing. `git merge-base
  --is-ancestor` settled it in one command: one producer, one line, two
  branches.

  Before asserting that a symbol, a path or a behaviour is absent, ask what your
  checkout is behind. The absence of a thing is exactly the claim a stale tree
  makes most convincingly, because a missing symbol looks identical whether it
  was never written or merely not yet fetched. Same shape as `.last_deployed
  _commit` and *never trust origin/main for what is running*: ask the system that
  holds the truth, not the copy that once agreed with it.

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
