# DEPLOY LOG — quality agent

Zac 2026-08-04: **every push to main orphans the jobs in flight.** So each deploy
is announced here with its window, and the orphans inside it are attributed to
the deploy rather than counted as a mystery class.

## My deploys, 2026-08-03/04 (8, and 5 of them inside 56 minutes — too fast)

| commit | deploy ≈ (UTC) | carried | orphans |
|---|---|---|---|
| `fe15996` | 00:18 | SafeImg, 15 tag sites, entrance+zoom caps, pre-extract, RENDERCLOCK | 0 |
| `bbff11a` | 01:01 | removed the two false taste signals | 0 |
| `2e65292` | 03:37 | export-weighted style profile | 1 |
| `8360a93` | 06:05 | mid-word fixed-point snap | 1 |
| `6b3ece7` | 06:22 | source clamp on the snap | 1 |
| `c830895` | 06:41 | two-lists diagnostic | 3 |
| `baac8aa` | 06:52 | **merge of zero-reject-routing** (109 commits) | 1 |
| `8bb72c7` | 07:01 | truncate-never-pad + gate | 1 |

**7 jobs / 7 users plausibly orphaned**, against 54 failed / 406 jobs since
00:00Z (50 distinct users failed). So my cadence accounts for **7 of tonight's
50 failing users — 14%.** Real, and mine.

⚠️ My first cut of this said **51**. It was contaminated: `completed_at` is NULL
on failed jobs, so "in flight" swept in every past failure and grew
monotonically across the windows — the accumulating-set signature. The clean
cohort requires the job to have STARTED within 20 minutes before the deploy and
to have died AT OR AFTER the deploy instant.

## The rule I am now on

1. **Batch.** One deploy carrying three fixes, not three deploys. The four
   deploys between 06:05 and 07:01 should have been one.
2. **Announce the window** before pushing, so the orphans are attributed.
3. `6b3ece7`, `c830895`, `baac8aa`, `8bb72c7` were each individually justified
   and collectively indefensible. The merge was genuinely urgent; the other
   three were not, and could have ridden with it.

## FOR THE SPEED LANE — output duration rose, and it is not a regression

`199c686` (edge content preservation, live 2026-08-04) can only INCREASE output
duration. Measured over 532 real jobs as an upper bound:

| | p50 | p90 | p99 | max |
|---|---|---|---|---|
| added seconds | **+0.9s** | **+6.3s** | **+20.6s** | **+44.8s** |
| ...of which HEAD | +0.16s | +1.92s | +9.2s | +20.3s |
| ...of which TAIL | +0.45s | +4.46s | +17.5s | +32.8s |

**Concentrated on long sources** — the median job barely moves; the tail of the
distribution is where the seconds are. `a8e0d0f` then capped the HEAD at 0.5s,
which removes roughly a third of the increase.

**So render-time movement in the next window has a known non-regression cause.**
Longer output = more frames = more render. If render p50 rises by ~1s and p99 by
~15-20s, that is this change, not a fault. Anything larger is not.

---

# TRUTH-owned deploy queue (standing, from 2026-08-09)

**Only the TRUTH lane deploys — both repos.** Queue rules: one deploy at a
time · quiet window (Modal tasks polled; every deploy orphans in-flight jobs,
so batch + announce + attribute) · validate gate green · predeploy_no_regress
green (incl. lineage ancestry) · diff-vs-ownership check (`LANE_OWNERSHIP.md`)
· secret readback after every worker deploy · entry here (who, what, sha,
version).

## Standing rules — codified 2026-08-11 (Zac's rulings)

1. **Quiet window = ZERO IN-FLIGHT USER JOBS by the DB probe, not zero Modal
   tasks.** `modal app list` counts prewarm + persistent fastapi_endpoint
   containers; prewarm fires while the user is mid-upload, *before* a job row
   exists. It showed 6-11 "tasks" for 3+ hours against a measured **0**
   in-flight and would have blocked the queue indefinitely. Now EXECUTABLE, not
   remembered: `deploy.sh` runs `preflight_quiet_window.py` first (exit 1 BUSY /
   2 UNKNOWN), and validate_deploy check `_quiet_window_gate_wired` fails any
   deploy that unwires it. A zero is only believed if the probe can also see
   recent rows — the non-vacuity leg.
2. **NO ZERO IS BELIEVED UNTIL THE SAME PROBE FIRES ON THE KNOWN-BAD
   WINDOW.** (Zac 2026-08-11 — promoted to a standing law for **every lane**,
   not just deploys.) A probe that matches nothing returns a confident zero that
   is indistinguishable from good news. This has now bitten repeatedly: during
   the outage investigation, searching `video_jobs.result` for
   `safe_edit_fallback` AND for `gemini_n_calls` both returned clean zeros —
   and both markers appear in **no window at all**, including the known-bad one
   (they live in the HARNESS capture output, not the DB). The rule is
   mechanical: before reporting any zero, re-run the identical probe against a
   window where the thing is KNOWN to be present. If it does not fire there,
   the zero is VACUOUS and means nothing. Enforced in code for the deploy gate
   by `preflight_quiet_window.py` (refuses to call a zero "quiet" unless it can
   also see recent rows) and asserted by validate_deploy `_quiet_window_gate_wired`.

3. **`PROMPTLY_SKIP_REGRESSION` is outage-only.** Legitimate solely while Vertex
   403s (the corpus's Gemini calls would fail spuriously and fire a FALSE
   `REGRESSED` page). The moment the owner confirms GCP billing, the regression
   corpus is the **FIRST verification run, before any further worker deploy.**
4. **Drain order once the deploy permission lands:** W0 reconciliation (must
   verify behaviourally no-op) → DELIVERY worker rebased (+ W4, the named crash
   fix) → SEAM full package, both halves together. One at a time, each with its
   watch.

## Queue

Every package below was **conflict-tested against the reconciled branch on
2026-08-09 22:0x** [MEASURED]: all merge clean, and none except JUDGE touches a
TRUTH-owned file (JUDGE's is a declared `render.yaml` cron append at EOF, which
composes with TRUTH's `buildCommand` hunk at line 4).

### Worker queue

| # | lane | branch @ sha | what | ownership | merge test | status |
|---|---|---|---|---|---|---|
| W0 | TRUTH | zero-reject-routing @ 4c4ead8 | RECONCILIATION: live v521 lineage (d9c6e4d) + deploy-truth semantics (8ee0e30) + CANON pinning & drift sentinel (3a00caa) + STATE_AUDIT. Delta vs live = `cff8ccd` (byte-identical at cpu≥16) + the daily drift sentinel. | — | — | **WAITING for quiet window** (traffic 6–11 tasks all evening) |
| W1 | DELIVERY | lane/delivery @ 31c2dd7 | completion-POST retry+backoff w/ persisted reason, `"jobs"`-default landmine fix ×5 + cert, lang_bundle NameError, `worker_started_at`. handler.py + modal_app.py only. | ✅ clean | ✅ 0 conflicts | after W0 verifies no-op |
| W2 | HARNESS | lane/harness @ d098f48 | merge `golden/validate_deploy_addition.py` into validate_deploy.py (staged as a separate file with placement notes — correct discipline). | ✅ clean | ✅ 0 conflicts | **GATED**: HARNESS says do not merge until `golden/plans/` is frozen; freeze needs Vertex, which needs the billing fix |
| W3 | SEAM | lane/seam @ e6ab8f1 | 4 dark flags (adapter/unified-core/surgical-v2), 3 certs, flags OFF. | ✅ clean | ✅ 0 conflicts | after W1; CANON registration needs an owner GO naming the new keys (secret-auth law) |
| W4 | smoothness | agent/smoothness @ `d9543d6` | **THE HELD-OUT CRASH FIX — named per Zac 2026-08-11, to ship with W1.** See the block below. | — | — | ride with W1 |

#### W4 — what the held-out commit is, and why it was held

**`d9543d6` — "component_crash: a missing string killed the whole render —
Vertex omits optional fields and TypeScript cannot see it."**

- **What it fixes:** Vertex AI **omits optional fields** rather than sending
  them null (the standing optional-omission crash class). When an optional
  string was absent, a Remotion component threw and **the entire render died** —
  one missing string, whole job lost. The fix adds a shared `asText.ts` coercion
  and applies it across **9 components** (TypewriterReveal, DropBanner, DropCard,
  EditorialQuote, PullQuote, SectionDivider, StepDivider, StickyNotes) plus
  `PromptlyRender.tsx`, and ships its own `validate_deploy.py` assertion.
- **Why it was held (2026-08-09):** it sits **past the live image** on
  `agent/smoothness`. The reconciliation deploy (W0) had to be verifiable as a
  **behavioural no-op** — that is the entire point of W0. Folding a real
  render-behaviour fix into it would have destroyed that property and left us
  unable to tell a reconciliation problem from a component-fix problem. So it
  was held **explicitly and in writing**, never dropped.
- **Its sibling `8dd3954`** (retires a gate assertion + touches
  `.last_deployed_commit`) is **partly superseded** — TRUTH untracked that file
  on 2026-08-09, so only its gate-assertion half still applies. Review that half
  on merge rather than taking it wholesale.
- **⚠️ ITS CRASH CLASS REACTIVATES THE MOMENT GEMINI RETURNS** (Zac
  2026-08-11). The bug is *caused by Vertex omitting optional fields*. While
  Vertex is 403ing, no Gemini response is produced, so the class is **dormant —
  masked by the outage, not fixed**. Restoring billing re-arms it on live
  traffic. **Therefore W1 (carrying W4) follows the billing fix IMMEDIATELY
  once the permission rule lands** — the window between "Gemini returns" and
  "W4 is live" is a window in which one missing optional string can again kill
  a whole render.
- **Risk note:** this is a *real* runtime change to render components, so it
  must NOT ride W0. It ships with W1 and carries W1's watch.

### content-studio queue

| # | lane | branch @ sha | what | status |
|---|---|---|---|---|
| C0 ✅ DEPLOYED 16:42Z | TRUTH + JUDGE | lane/truth + lane/judge → main @ 99cf92d | **batched**: gate wiring (Render build + blocking CI) + CHECKOUTS/LANE_OWNERSHIP/DEPLOY_LOG/OWNER_ACTIONS/sentinel spec, plus JUDGE's 5 scripts, 2 migrations, daily-scoreboard cron. Batched because both carry **zero request-path runtime risk** and their watches are independent (gate = build log; JUDGE = the 15:00 UTC row) — one orphan window instead of two. | WAITING for quiet window |
| C1 ✅ DEPLOYED 16:57Z | DELIVERY | lane/delivery → main @ 8f54923 | server.js +140, dispatch-to-modal.js +145, modal-webhook, 75s durable poller, `completion_delivery` migration, RC `/sync` probe. **Deployed alone** — it is the only package that changes the request path, and its 48h watch must not be confounded. | after C0 |

## BLOCKED — 2026-08-10 06:25Z, W0 deploy attempt

`./deploy.sh` was **denied by the Claude Code permission classifier** before any
execution. Verified no partial deploy: live is still **v521 = `1601ae0`**
[MEASURED, `modal app history`] and no-regress is still green. Not worked
around — invoking `modal deploy modal_app.py` directly would bypass the very
gates deploy.sh exists to run (validate, no-regress, post-deploy TOCTOU
re-check, auth ping).

**Unblock:** owner adds a Bash permission rule for `./deploy.sh` (worker) and
`git push origin main` (content-studio). Everything else is staged and green;
each deploy is then a single command.

### Quiet-window finding — the task-count signal was a FALSE blocker [MEASURED]

`modal app list` showed 6–11 "tasks" continuously for 3+ hours, which would
have blocked deploys indefinitely. The DB says otherwise: **0 in-flight user
jobs**. Over the trailing 6h there were 69 job rows, every one terminal
(`completed` 61 / `failed` 7 / `canceled` 1) — no non-terminal row exists.
Probe proven non-vacuous before the zero was trusted (the standing
probe-collapse rule), and `completed_at` is NULL on failed rows, so
"no completed_at" must never be read as "in flight" — that exact contamination
inflated an earlier orphan count from 7 to 51.

The Modal tasks are **prewarm + persistent FastAPI endpoint containers**.
Prewarm fires while the user is mid-upload, *before* a job row exists, so
container count is not a measure of user work at risk.

**Standing rule for this queue: the quiet-window gate is the DB in-flight
count, not the Modal task count.** Probe: `scratchpad/inflight.js`.

### Ready-to-fire (all pre-checks green as of 06:24Z)

| # | command | pre-checks |
|---|---|---|
| W0 | `PROMPTLY_DEPLOYER=truth-lane PROMPTLY_SKIP_REGRESSION=1 ./deploy.sh` | validate 358/358 ✅ · no-regress ✅ · in-flight **0** ✅ · tree clean ✅ |
| C0 | merge `lane/truth` + `lane/judge` → `main`, push | merges clean ✅ · 20/20 smokes ✅ · CI red proven ✅ |

**Why `PROMPTLY_SKIP_REGRESSION=1` on W0:** the zero-spend rule, and the
regression corpus makes Gemini calls that would 403 during the active Vertex
outage — it would fire a **false** `REGRESSED` page at the owner. Re-enable on
the first deploy after billing is restored.

## Deploys

| when (UTC) | who | sha | version | carried | window/orphans |
|---|---|---|---|---|---|
| 2026-08-11 16:42Z | TRUTH | `99cf92d` (content-studio main) | Render autoDeploy | **C0**: gate wiring (Render buildCommand + blocking CI) + LANE_OWNERSHIP/CHECKOUTS/DEPLOY_LOG/OWNER_ACTIONS/sentinel-spec, **batched with JUDGE** (5 scripts, 2 additive migrations, daily-scoreboard cron) | in-flight user jobs at T-0: **0** [MEASURED] → **0 orphans** |

### C0 verification [MEASURED]

- **Deployed sha matches exactly**: `/api/health` `rev` =
  `99cf92dc9fd1bb761dfa5e9a645526b7037e939e` = pushed `main`. Not "pushed" —
  *observed running in prod*.
- **CI gate armed and green on the real deploy commit**: the step
  `Safety smokes (validate_deploy.js) — blocking` = **success**. Combined with
  the earlier demonstrated **red** (scratch PR #2 broke the GLOBAL_HALT surge
  floor → that exact step failed), the CI half is proven in both directions.
- **Render build half: [UNKNOWN].** The build succeeded, but that is equally
  consistent with Render still using the OLD `buildCommand` (blueprint changes
  can need a manual sync — this repo has a prior "blueprint sync failed"
  incident on env vars). No Render API key on this machine, so I cannot read
  the build log. Owner: confirm one line, `OWNER_ACTIONS.md` item 4.
- Same open question for JUDGE's new `daily-scoreboard` cron service — a
  blueprint addition, so it may need the same sync.

| 2026-08-11 16:57Z | TRUTH | `8f54923` (content-studio main) | Render autoDeploy | **C1**: DELIVERY — durable-row 75s poll (missed callback now costs ≤75s, not 900), every settle path names itself in `completion_delivery`, orphan-callback handling, RC `/sync` project probe, additive migration, new smoke | in-flight at T-0: **0** [MEASURED] → **0 orphans** |

| 2026-08-11 17:21Z | TRUTH | `935b89a` (content-studio main) | Render autoDeploy | **C2**: docs only — the gate-receipt request filed to DELIVERY. Held ~20min from its original slot because a user job was in flight; pushed when `preflight_quiet_window.py` returned OK. Live sha-verified in ~80s. | in-flight at T-0: **0** [MEASURED] → **0 orphans** |

### C1 verification [MEASURED]

- **Live sha match** in 40s: `/api/health` `rev` = `8f54923…` = pushed `main`.
- **CI green** on the deploy commit; gate ran **20/20** smokes (19 + DELIVERY's
  new `__smoke_completion_delivery.js`).
- **Migration NOT yet applied** — confirmed directly: a query on
  `completion_delivery` returns *"column does not exist"*. This is the designed
  state (DELIVERY: *"no writes break if it's late"*), and jobs kept completing
  across the deploy [MEASURED: 9 completed / 1 failed / 1 processing in the
  surrounding window]. **Until the migration lands, the delivery-mechanism
  instrument writes nothing — the 48h watch cannot start.**
- **REAL-TRAFFIC PROOF**: the first job created after the deploy **completed
  in 41s e2e** [MEASURED] — a delivery observed end-to-end on the new server
  code, not merely a service that boots.
- **Migration path re-confirmed absent**: probed for a SQL-executing RPC
  (`exec_sql`/`execute_sql`/`sql`/`run_sql`) — all 404. Third independent
  confirmation that DDL is owner-only.
- Deployed **without** its worker half (W1), which is permission-blocked.
  DELIVERY's own handoff says the two halves are independent and either order
  is fine, and all changes are "inert-negative (worst case = today's
  behavior)". The CS half is the safety net, so it is the more valuable half to
  have live first.

### ANSWERED EXACTLY, per Zac's ask 2026-08-11 — the Render half is NOT confirmed

**Q: did TRUTH ever confirm the Render `buildCommand` gate actually armed, and
that JUDGE's `daily-scoreboard` cron service exists?**

**A: NO. Both are [UNKNOWN] and both are still on the owner's list.** Stated
plainly so the board is exact:

| thing | status | why it is unknown |
|---|---|---|
| CI smoke gate | ✅ **CONFIRMED ARMED** [MEASURED] | ran **green on the real deploy commit** `99cf92d` AND proven **red** on a broken invariant (scratch PR #2). Both directions. |
| Render `buildCommand` gate | ❌ **[UNKNOWN]** | the build succeeded — but that is equally consistent with Render still using the OLD buildCommand. Blueprint changes can need a manual sync (this repo has a prior "blueprint sync failed" incident on env vars). No Render API key on this machine → cannot read the build log. |
| JUDGE `daily-scoreboard` cron service | ❌ **[UNKNOWN]** | same blueprint-sync question. It is a NEW service in `render.yaml`. It leaves no DB trace either way right now, because both its tables are un-migrated, so it would fall back to a JSONL file on Render's ephemeral disk. **Absence of evidence here is not evidence of absence.** |

I attempted to make this self-proving without crossing lanes and could not:
there is no served static directory on `main` (`public/` does not exist there),
so a build-written receipt has nothing to serve it. **The durable fix is filed
to DELIVERY** (they own `server.js` handlers) as
`reports/REQUEST_DELIVERY_GATE_RECEIPT.md`: have the build write a receipt and
expose it on `/api/health` beside `rev`, so "did the build gate run" becomes a
permanent `curl`, exactly as `rev` made "is prod running my commit" a permanent
`curl`. Until that ships, this stays an owner eyeball.

### Open watches

| watch | owner | condition | due |
|---|---|---|---|
| DELIVERY delivery-mix | TRUTH | `completion_delivery=fallback_timer` → ~0; p99 leaves the ~900s wall | 48h **after the migration lands** (blocked: column does not exist) |
| JUDGE daily row | TRUTH | a row lands in `daily_scoreboard` (JSONL fallback retired) | first 15:00Z run **after** migrations are applied |
| C0 no-regress | TRUTH | no scoreboard movement attributable to C0 (it carries zero request-path runtime change) | 24h |
