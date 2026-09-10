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

## Standing rules earned 2026-09-09

- **`or 0` ON A VALUE THAT MIGHT NOT EXIST IS A PROHIBITION WHEREVER A NUMBER
  REACHES A REPORT.** (Ruled by Zac 2026-09-09, after the second instance.)
  This is *probe collapse* — a failed measurement published as a confident
  number — reduced to its smallest possible form: seven characters, on the line
  that prints.

  Two instances, both in the same week and both on numbers headed for a round
  report. `paint_ms or 0` reported `paint 0.0s` against 458.6s of wall for six
  rounds — a paint that was never measured, reading as *instant* and
  indistinguishable from a real zero.
  My own two edit-quality lines carried the same idiom on the distributions I
  was about to publish. Neither was a typo; both were the ordinary defensive
  reflex, applied to the one category of value where the default is a lie.

  **THE RULE IS NOT "BAN `or 0`" — IT IS A DISTINCTION, AND THE DISTINCTION IS
  THE WHOLE RULE.** `execute_plan_calls or 0` is a COUNTER: absent genuinely
  means zero, nothing happened, the default is TRUE. `paint_ms or 0` is a
  MEASUREMENT: absent means *unknown*, and zero is a claim the instrument never
  made. A check that bans the idiom outright gets suppressed within a week
  because most of its hits are counters, sums and divisor guards. Ten instances
  are pinned by owner and reason for exactly this reason — a pin is an argument
  on the record, not an exemption.

  **THE CHECK, NAMED: `smoke_no_absent_as_zero.py`** (RED-proven by
  `red_proof_no_absent_as_zero.py`), and its scope took three attempts, each
  wrong in a way worth keeping:
    * inside `print()` only — too narrow, and it missed MY OWN instance, which
      was an assignment one line above the print;
    * any function containing a print — too wide: 17 innocents inside the
      3,000-line `edit`, which is how a check earns its own deletion;
    * **def-use into a print** — the value's path, not its neighbourhood.

  And the mutation lesson underneath it: **both RED mutations were defeated by a
  `str(...)` wrapper.** `str(paint_ms or 0)` is the identical defect and the
  naive matcher saw a call, not a fallback. Walk the WHOLE assigned expression;
  a disguise one node deep is not a different bug.

  Where a value can be absent, say which: MEASURED / ABSENT / FAILED, the same
  three states `alpha_layer_state` returns. A report that cannot say *absent*
  will say *zero*, and a tidy zero is the most expensive result to trust.

- **A DEFAULT ON A FIELD THAT NEVER EXISTED IS THE SAME DEFECT WITH NO IDIOM TO
  GREP FOR.** `source_fps` was read off every fixture and was never a key any
  producer wrote — so every fixture silently took the 30fps floor, and a VFR
  source, which has no floor at all, took it too. Nothing was wrong at the read
  site; the field simply did not exist. Assert the KEY is present before
  defaulting its value, or the default becomes the measurement for 100% of the
  population and reads perfectly plausible while doing it.

- **LAUNDERING: A DEFAULT AT THE PRODUCER MAKES EVERY CONSUMER-SIDE CHECK
  STRUCTURALLY BLIND.** (Named by Zac 2026-09-09, found by the rule above one
  commit after it was written, in its own pin table.) The third shape in this
  family and the one no downstream guard can catch.

  `float(meta['format'].get('duration') or 0)` converts *absent* into a
  **present, well-typed 0.0** and writes it to the ledger. Downstream, the key
  is there, the type is right, the value is fabricated, and nothing — no `is
  None` test, no three-state read, no wider def-use scope — can tell it from a
  measurement, because by then there is nothing left to tell. My own pinned
  `source_duration_s` was the print at the END of that chain: removing its
  `or 0` would have changed nothing and closed the item.

  The consequences run past reports and into behaviour. The same idiom binds
  `_vdur`, which is printed twice as a source duration AND passed as the SPAN to
  `segment_beats_visual` and `cover_unnarrated_edges` — so an unreadable
  duration segments a **0-second video** and the visual route returns no beats:
  a silent total failure on 46.5% of traffic, from a missing key. It degrades a
  plan rather than raising, which is the failure mode the boundary contract
  already forbids for out-parameters, arriving here through a different door.

  **THE FIX IS ALWAYS AT THE PRODUCER, AND A DOCSTRING STATING THE GAP BEATS
  WIDENING THE SCOPE.** Def-use resolves within a function; laundering crosses
  functions by design. A check that grew until it claimed to cover this would be
  claiming something it cannot do — say the gap, and put the guard where the
  absence is still visible.

- **A STALE COMMENT IS READ AS FACT BY THE NEXT PERSON, INCLUDING THE PERSON WHO
  WROTE IT.** (Ruled by Zac 2026-09-09.) A pin, a justification, a note beside a
  constant — each is an ARGUMENT ON THE RECORD, and a plausible wrong one is
  worse than none, because it is what gets re-derived next time instead of
  checked. `"duration": "ffprobe duration into arithmetic, guarded downstream"`
  was mine, was wrong, and described a divisor guard that was actually the beat
  span for the whole visual route.

  So when a note turns out to be wrong, **keep it in place as the correction**
  rather than replacing it with a clean one. The wrong sentence is the evidence
  that the class recurs; a silent overwrite leaves the next reader with a tidy
  note and no reason to distrust the next tidy note.

- **SEMANTIC VACUITY: A MUTATION CAN STOP MUTATING WITHOUT ITS ANCHOR MOVING.**
  (Found by Builder-1 2026-09-09, in Builder-2's retrieval proof.) The second
  kind of *a mutation that does not mutate*, and `mut()`'s occurrence guard is
  blind to it — every previous instance in this file was an anchor that stopped
  matching, which counting catches.

  The mutation removed an unbuildable-family filter to prove the filter filters.
  Once cutaway shipped, `_unbuildable` was EMPTY — so removing an empty filter
  changed nothing. The anchor matched, the edit applied, the mutant was
  byte-different and behaviourally identical, and the proof read NOT RED with
  nothing wrong in the code. **A vacuous mutation and a blind check are
  indistinguishable in a tally**, which is the same shape as *a failed
  measurement and a clean result are indistinguishable once you are only reading
  numbers*.

  **THE SECOND GUARD, NAMED: a PRECONDITION per mutation.** The anchor guard
  asks *does the target exist*; the precondition asks *does the target DO
  anything*. Every mutation that WEAKENS OR REMOVES something declares a
  callable over the unmutated source, evaluated BEFORE the edit — the filter's
  operand is non-empty, the guard is present and reachable, the branch is taken
  by something. A mutation that INJECTS a defect declares `None` and says so:
  new material cannot be vacuous in this way, and a precondition that is always
  true is noise that teaches the next reader to skip the field.

  When a mutant passes, the precondition is what separates the two diagnoses.
  Implemented in `red_proof_source_duration_state.py`: it prints VACUOUS,
  refuses to count the mutation, and exits non-zero. RED-proven by falsifying a
  precondition — 7/7 fell to 6/7 with VACUOUS named and exit 1.

  It is a per-mutation obligation rather than a free rule, and that is its
  honest cost. The alternative is a proof that goes on reporting a number.

- **A BROKEN FILE THAT NOTHING MOUNTS BREAKS NOTHING UNTIL IT BREAKS
  EVERYTHING.** `ff9311f` committed three `git stash pop` conflict blocks into
  handler.py — the main pipeline worker — and it went unnoticed for a day
  because every consequence landed where nobody was looking: handler.py is not
  one of the ten mounted paths, so no round could fail on it; ~20 certs went red
  at once, which reads as *the handler certs are red again* rather than as one
  file; and the deploy branch never carried it, so nothing live broke. A
  landmine for whoever merged a lane, not an outage.

  Two things generalise. **A commit's diff is not confined to the file it is
  about** — that commit was card-contract work and had no business in
  handler.py, which is precisely why nobody looked. And **when many checks go
  red together, find the one cause before reading any of them as findings**;
  a class of failures is a single fact wearing a crowd.

  **THE CHECK, NAMED: `smoke_tree_parses.py`** — every tracked file, no conflict
  markers at line start, every tracked `.py` compiles. Repo-wide deliberately:
  scoped to *the files this lane touches* it would be a population fitted to
  today's lane, and this landed in a file its own commit was not editing.
  RED-proven 2/2 with the real block shape, including one leg whose markers sit
  inside a string literal so the file still parses — proving the marker scan and
  the parse scan are independent and neither is carrying the other.

  A note on the repair: taking the `Updated upstream` side of all three blocks
  reproduced `ff9311f~1:handler.py` BYTE-IDENTICALLY. That is what made fixing a
  file outside my region a revert of an accident rather than a choice between
  two versions — and it is the check to run before touching anyone else's file.

- **A CHECK THAT IS ALWAYS RED STOPS BEING READ, INCLUDING THE PART THAT IS
  TRUE.** (Named by Zac 2026-09-09, on two instances in one day in two lanes.)
  `smoke_modal_app_preflight` has been failing on a clean tree for days
  (`lumen_first_edit_app.py:53`, a different app, awaiting a ruling), and
  handler.py's ~20 red certs were read as *the handler certs are red again*
  rather than as one broken file. Both are the same mechanism: a permanent red
  becomes furniture, and the next real failure arrives inside it wearing the
  same colour.

  This is the twin of *a check that has never failed is not yet a check*. One
  fails to fire; the other fires constantly and stops being heard. A red that
  will not be fixed today must be either **fixed, quarantined with an owner and
  a date, or deleted** — never left to accumulate a second meaning.

- **A MUTATION CAN BE RE-TARGETED BY PROSE, AND THE COUNT GUARD CANNOT SEE IT.**
  (Found 2026-09-09.) The third way a mutation stops mutating, and the one with
  the nastiest cause: **documenting a defect silently re-targets the mutation
  that hunts it.**

  `red_proof_ruling_time_knowledge` leg 7 anchored on `.strip() != "1"`.
  Rewriting `prefix_material_enabled` removed that predicate AND REPLACED IT
  WITH A DOCSTRING SENTENCE QUOTING IT — the sentence recording the defect for
  the next reader. The anchor still matched EXACTLY ONCE, `count != 1` passed,
  the mutation edited a comment, and the proof printed NOT RED with nothing
  wrong in the code.

      anchor 0x                 a refactor moved it        count guard
      anchor lands in prose     a comment now owns it      _match_is_prose
      operand is empty          the edit is a no-op        precondition

  **THE CHECK, NAMED: `_match_is_prose`** — tokenize the file, collect STRING
  and COMMENT character spans, refuse a mutation whose single match sits wholly
  inside one. RED-proven by aiming a mutation at the prose-only anchor: refused,
  8/9, exit 1; restored 8/8, exit 0.

  Two traps in building it, both mine. The first version blanked string
  CONTENTS, which refused 7 of 8 legs — almost every anchor legitimately
  contains a literal, and the question is not whether the anchor has quotes but
  **where the match lands**. The second computed line offsets inside the token
  loop, O(n^2) on 45,000 lines, and did not finish in 120s: *a guard nobody can
  afford to run is not a guard.*

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
