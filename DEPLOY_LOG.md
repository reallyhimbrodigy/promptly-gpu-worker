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

| **W5 — NEXT** | DELIVERY | lane/delivery @ `12bed65` | **THE HANG FIX — current worst user-facing defect class.** Root cause of the 2 users I measured today being told a *completed* render FAILED: a postgrest client with NO timeout hanging under `_JOB_STATUS_LOCK`, freezing every later durable write, blocking handler-return (so no completion POST) and billing the container its full 1200s. Fix: 15s hard timeout (a hang becomes a logged fail-open), terminal writes RECEIPT themselves (matched/elapsed_ms/result_bytes, >5s under lock logs SLOW = wedge detector). Also carries the HLS_COPY flip filing + fps/media-res corpus A/B (staged, NOT flipped). | ✅ clean (917+/1− vs true merge base `31c2dd7`; **zero TRUTH-owned**) | ✅ 0 conflicts | **MERGED, gates green (362/362 + no-regress), WAITING on quiet window** |
| W5 ✅ DEPLOYED 19:32Z | DELIVERY | `cba0f6d` → **v526** | THE HANG FIX (postgrest 15s timeout + terminal-write receipts + wedge detector) | ✅ | ✅ | no-regress green, auth-ping 200, main FF'd |
| W6 | HARNESS | lane/harness @ `8daeab4` | golden corpus infra (manifest 25 sources, freeze app, differ, offline cert). **The staged `golden/validate_deploy_addition.py` is deliberately NOT merged into validate_deploy.py** — it fails loudly on an unfrozen corpus by design; it merges after the freeze. | ✅ clean | ✅ merged | rides W5 |

### content-studio queue

| # | lane | branch @ sha | what | status |
|---|---|---|---|---|
| C0 ✅ DEPLOYED 16:42Z | TRUTH + JUDGE | lane/truth + lane/judge → main @ 99cf92d | **batched**: gate wiring (Render build + blocking CI) + CHECKOUTS/LANE_OWNERSHIP/DEPLOY_LOG/OWNER_ACTIONS/sentinel spec, plus JUDGE's 5 scripts, 2 migrations, daily-scoreboard cron. Batched because both carry **zero request-path runtime risk** and their watches are independent (gate = build log; JUDGE = the 15:00 UTC row) — one orphan window instead of two. | WAITING for quiet window |
| **C2 — ⛔ HELD (see BLOCKER_C2_EXPORT_FFMPEG.md)** | DELIVERY | lane/delivery-2 @ `bd594fb` | export server half DARK (alias route + watermark-at-export v1) + the stuck-job signature becomes a named event. Ships **dark**; the two export flags flip later per DELIVERY's four-step order (see `LAUNCH_DAY.md` §6d). Carries an in-container ffmpeg watermark proof that runs in the gate, so "does the watermark pass work in THIS container" is answered on every deploy, never by the first paying customer. | **HELD**: its watermark smoke shells to ffmpeg with no presence check; MEASURED `spawnSync ffmpeg ENOENT` on a box without it ⇒ fails the gate ⇒ fails the Render build ⇒ **blocks every future content-studio deploy**. Render's Node image has no ffmpeg and render.yaml installs none. Filed to DELIVERY: skip loudly + gate the FLIP on the smoke having run, not the BUILD. |
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

| 2026-08-11 18:01Z | TRUTH | `9ee9e6d` | **v522** | **W0 RECONCILIATION** — one worker deploy lineage at last; deploy-truth semantics; CANON 26/26 + drift sentinel | in-flight 0 → **0 orphans** |
| 2026-08-11 18:29Z | TRUTH | `f0b0c0c` | **v523** | **W1 + W4** — DELIVERY worker (completion-POST retry, `"jobs"` landmine ×5, lang_bundle NameError, worker_started_at) + the held-out component-crash fix (`asText` ×9 components) | in-flight 0 → **0 orphans** |
| 2026-08-11 18:36Z | TRUTH | `c008aed` | **v524** | **SEAM worker** (3 dark seams: adapter / unified-core / surgical-v2) | in-flight 0 → **0 orphans** |
| 2026-08-11 18:41Z | TRUTH | `df62d2b` | **v525** | **SEAM worker current** (+MG_OBEY, CAPTION_TRANSLATE, UPSCALE_NEGOTIATE — SEAM had advanced past the branch I first merged) | in-flight 0 → **0 orphans** |
| 2026-08-11 18:42Z | TRUTH | `fd0b9e1` (cs) | Render | **SEAM content-studio** — chat-actions route + the one-line mount | in-flight 0 → **0 orphans** |

### Phase A verification [MEASURED]

- **Every worker deploy**: post-deploy TOCTOU no-regress green, auth-ping 200,
  `.last_deployed_commit` written from `modal app history`. `main`
  fast-forwarded after each.
- **CS deploys** sha-verified live via `/api/health` `rev`; gate 22/22 smokes.
- **Dark-deploy pass condition met**: `POST /api/chat/actions` returns **404**
  on production with the flag unset — the route does not exist to any client.
- **All 6 SEAM flags verified to default ABSENT=dark**, and no secret was
  touched. CANON registration deliberately deferred: CANON is compared against
  the LIVE secret readback, so adding keys the secret lacks would fail the gate
  on every deploy for every lane. The keys join CANON at flip time, with the
  secret change, on an owner GO naming them.

### Gates that did real work this session (not rubber stamps)

1. `predeploy_no_regress` fired on `_lang_bundle` vanishing → verified against
   both trees, confirmed DELIVERY's deliberate rename, documented in
   `INTENTIONAL_REMOVALS`. **Not forced.**
2. Two lang_bundle checks failed → they had been **green for weeks while the
   field was null on 218/218 jobs**, asserting a mechanism that did not work.
   Repointed at the working chain + a negative assert.
3. `_plan_diff_add_vocabulary` failed on SEAM's merge → verified
   `TRANSITION_REFUSAL_BULLET` is **byte-identical** to the old inline text,
   then made the check *stronger* (both flag arms).
4. The quiet-window gate blocked three deploy attempts on live user jobs and
   released each time on its own terms.

### W1 watch — INCONCLUSIVE, and honestly so

`lang_bundle` is **still null** on the first post-v523 completion. That does
**not** falsify the fix: the job took `minimal_speech_uncut` /
`transcription_incomplete`, a light route that exits *before* the coverage gate
where the bundle is computed — its `stage_timings` carries no `lang_bundle` key
at all. The correct cohort is **standard-editorial jobs reaching the coverage
gate**, and the Vertex outage has eliminated that cohort entirely. **Re-run this
watch after billing is restored.** Reported as inconclusive rather than as
either a pass or a regression.

### ⚠️ FINDING for DELIVERY — the missed-callback class RECURRED with only the CS half live

**2 jobs / 2 distinct users** (lead with users, Rule 7), 2026-08-11:

| job | created | died | outcome |
|---|---|---|---|
| `34729736` | 18:09:24Z | 18:24:32Z | failed + **refunded**, `hls_manifest_url` present |
| `d3517793` | 18:12:19Z | 18:27:23Z | failed + **refunded**, no artifacts |

Both were observed BY ME, live, at `progress: 100, current_step: complete,
status: processing` — the worker had finished. Both then sat ~15 minutes (the
fallback timer), and were terminalised as **failed** with the user-facing
*"We had trouble reaching the render service."* Both were auto-refunded, so
this is not silent loss — but two users were told their finished video failed.

**Attribution — these are NOT deploy orphans** [MEASURED]: created *after*
v522 (18:01) and died *before* v523 (18:29). They died of the missed-callback
class itself, in the window between deploys.

**The uncomfortable part:** C1 — DELIVERY's durable-row 75s poller, whose whole
purpose is "a missed callback now costs ≤75s, not 900" — **was already live**
(deployed 16:57Z) and did not save either job. Either the poller does not cover
this path, or it failed silently. The worker half (W1, completion-POST retry
with backoff) only went live at 18:29Z, *after* both died, so the pair was
never tested together until now.

**WATCH (open):** does this class recur on jobs created after **18:29Z**, now
that both halves are live? Query:
```sql
select id, created_at, updated_at, error_message
from video_jobs
where status='failed' and created_at > '2026-08-11T18:29:00Z'
  and error_message ilike '%trouble reaching the render service%';
```
Expected with both halves live: **zero**. Any hit is a DELIVERY defect to file,
not a deploy artifact. (The `completion_delivery` column would name the settle
path directly — another reason the migration matters.)

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

### ✅ MIGRATION 01 APPLIED — 2026-08-11 19:49Z, detected automatically

The owner ran `2026-08-11 — RUN NOW — 01 …sql` from the Desktop folder. **No
paste-back**: `owner_sql_watch.py` probed, found all four objects, and flipped
`_STATUS.md` to APPLIED by itself.

- `public.fulfillment_scores` ✅ · `public.daily_scoreboard` ✅ ·
  `video_jobs.completion_delivery` ✅ · `video_jobs.worker_started_at` ✅
- **Instrument FLOWING, not merely created** [MEASURED]: first stamped row at
  19:49:55Z (`completion_delivery='reconciler'`). DDL running and an instrument
  working are different claims; this is the second one.

**DELIVERY's 48h watch clock STARTED 2026-08-11 19:49Z.**

**Clean cohort — stated before any number is reported:** jobs that **SETTLE at
or after 19:49Z**. Of 177 terminal jobs today, 176 carry NULL simply because the
column did not exist when they settled. Those are **not misses** and counting
them would repeat the exact contamination that once inflated an orphan count
from 7 to 51. Watch armed on the clean cohort only.

Watching for: `fallback_timer` → ~0, p99 leaving the ~900s wall, and zero
recurrence of the "trouble reaching the render service" class now that the hang
fix (v526) and both DELIVERY halves are live.

### Open watches

| watch | owner | condition | due |
|---|---|---|---|
| DELIVERY delivery-mix | TRUTH | `completion_delivery=fallback_timer` → ~0; p99 leaves the ~900s wall | 48h **after the migration lands** (blocked: column does not exist) |
| JUDGE daily row | TRUTH | a row lands in `daily_scoreboard` (JSONL fallback retired) | first 15:00Z run **after** migrations are applied |
| C0 no-regress | TRUTH | no scoreboard movement attributable to C0 (it carries zero request-path runtime change) | 24h |

---

## 2026-08-11 20:00Z / 22:2xZ — BUILDER: C2 shipped, and a P0 confirmed on the way

Two content-studio deploys (`e6fb291`, `c071508`), zero worker deploys. Worker
stays at **v526 / `cba0f6d`**.

### C2 shipped — the blocker was real, and there was a second one under it

`BLOCKER_C2_EXPORT_FFMPEG.md` was correct: `__smoke_export_watermark.js` shelled
to ffmpeg with no presence check, inside `render.yaml`'s `buildCommand`, so
ENOENT would have blocked **every future content-studio deploy**. Fixed as
filed — probe, `SKIP(no-ffmpeg)`, exit 0.
[MEASURED both directions] `FFMPEG_PATH=/nonexistent` → was exit 1 "spawnSync
ffmpeg ENOENT"; now exit 0, 21/22 + `skipped:["export_watermark"]`. Guard NOT
weakened: watermark asset removed with ffmpeg present still exits 1.

**Second defect, unfiled:** `lib/gate-receipt.js` shipped as a **reader with no
writer** — `validate_deploy.js` was byte-identical to `main`, nothing emitted
`.gate_receipt.json`. `/api/health .gate` would have read `null` forever, and
`null` means "this build never ran the gate". The instrument built to close the
"did the Render buildCommand arm?" [UNKNOWN] would have shipped stuck in its own
alarm state. Writer added; `clearGateReceipt` first so a failed build can never
serve the last build's pass; SKIPs recorded by name so a skip cannot read as a
pass at flip time.

### ⚠️ FINDING — `/api/health .gate` came back **null** on `e6fb291` [MEASURED]

`render.yaml` declares `buildCommand: npm install --omit=dev && node
validate_deploy.js` on a `runtime: node` service (not Docker, so buildCommand
applies). The deploy shipped, so the command succeeded — yet no receipt exists
at runtime. Two candidate meanings, opposite responses, and **I am not asserting
either**: (a) the live service is not running that buildCommand — a blueprint
that never synced, in which case **the 24 safety smokes are gating nothing on
Render** and only GitHub CI is real; (b) build-time writes do not reach the
runtime filesystem, in which case the receipt is the wrong instrument.

`c071508` shipped the discriminator: an npm `postinstall` marker, which fires on
**any** `npm install` including the old un-synced command.

### 🔴 ANSWERED — the Render buildCommand gate is **NOT ARMED**. [MEASURED]

```
GET /api/health  (rev c071508, 23:12Z)
  "gate":  null
  "build": {"at":"2026-08-11T23:12:44.936Z","node":"v20.20.2"}
```

`build` present ⇒ `npm install` ran on this build, **and** build-time writes DO
survive into the runtime filesystem. `gate` absent from the SAME directory on
the SAME build ⇒ `node validate_deploy.js` **never ran**. (It cannot have run
and failed: a failed gate fails the build, and this build shipped.)

**The live Render service is not running `render.yaml`'s `buildCommand`. The 25
safety smokes are gating NOTHING on Render — only GitHub CI is real.** Every
"the gate blocks the Render build" claim in this estate is false, and has been
since the gate was wired on 2026-08-09.

**OWNER ACTION:** in the Render dashboard, set the `promptly` service's build
command to `npm install --omit=dev && node validate_deploy.js` (or trigger a
blueprint re-sync). Verified by one curl afterwards: `.gate` must go non-null
with `total=25`. This is the standing [UNKNOWN] from the C1 report, now closed
as a **NO** — and it stayed open for two days precisely because it decayed to an
owner build-log eyeball. It is a `curl` from now on.

### 🔴 P0 — 9 USERS TOLD A FINISHED RENDER FAILED. TRUTH's open watch is RED.

`b384e1c` opened: *"does this class recur on jobs created after 18:29Z, now that
both halves are live? Expected: zero. Any hit is a DELIVERY defect."*

**Clean cohort** — jobs created ≥ 18:29:00Z (both DELIVERY halves live; v526
hang fix live 19:32Z). Stated before the numbers, per Rule 5.

| | |
|---|---|
| terminal jobs | 34 / **32 users** |
| "trouble reaching the render service" | 11 jobs / **11 users** |
| …of those, **render actually FINISHED** (`progress=100` + `current_step='complete'`) | 9 jobs / **9 USERS** |
| **rate** | **9 of 32 users = 28%** (9/34 jobs = 26.5%) |

Every one failed **15m04s** after creation — the fallback timer, to the second.
Window 18:44Z → 22:04Z and still open at the time of writing. Lead with users
(Rule 7): **9 lost users**, not 9 failures.

**Mechanism confirmed, n=4 jobs, 100% consistent.** Every occurrence after the
diagnostic went live fired `terminal_flip_lost` **twice** with
`mechanism='zero_rows_nonterminal'` — never `complete_step_bad_pct`. Twice
because the worker retries once and **both attempts lose the transition**. The
completed-status patch matches **0 rows** against
`.not('status','in',(completed,failed,canceled,needs_input))` on a row whose
status reads `processing`.

Neither the hang fix (v526) nor DELIVERY's 75s poller nor the completion-POST
retry saves these. **This is not a deploy orphan** — the jobs are created and
die between deploys, on the fixed image.

### Why `c071508` and not a fix yet

"Zero rows" is still **three** faults with three different responses, and the
update's `error` was being **discarded** — so a failed write and a genuine
zero-match were the same observation. `c071508` captures the error and
classifies: `update_error` / `lost_race_benign` / `row_still_nonterminal`
(unreadable resolves to the **defect**, never the reassuring case). Root-causing
before that lands would be inference, which is what this class has already cost
three rounds of.

**WATCH (open, ~20 min to first data):** `analytics_events.terminal_flip_lost`
→ `props.cause`.
`row_still_nonterminal` ⇒ fix the predicate · `update_error` ⇒ fix the write
(`err_code` rides the event) · `lost_race_benign` ⇒ the class is smaller than it
looks and the count needs re-cutting.

**Also in cohort:** 4 jobs = *"The video didn't reach us — pick it again"* (the
UNS class, B1).

**Also [MEASURED]:** `completion_delivery` is stamped `reconciler` on the 3
completions since the migration but is **NULL on all 3 failures** — so
DELIVERY's delivery-mix instrument cannot see the very failures it most needs to
name. n=6, small; flagged, not concluded.

### Gate + window, both deploys

24/24 then 25/25 smokes green on the exact deploy commit. `preflight_quiet_window.py`
QUIET (0 in-flight, probe non-vacuous) before each merge; one merge was **held
~40 min** on a BUSY window rather than overriding. `PROMPTLY_ALLOW_BUSY_DEPLOY`
unused.

---

## 2026-08-12 00:10Z — BUILDER: the repair SAVED A USER live; the true root is fixed and BLOCKED on permission

### ✅ THE REPAIR WORKED ON REAL TRAFFIC [MEASURED, watched end to end]

Job `72435e45` (1 user), created 23:54:23Z, wedged at the exact signature
(`progress=100` / `current_step='complete'` / `status='processing'`). Watched it
live across its 900s fallback:

```
00:07:46  status=processing  delivery=None     url=—
00:09:16  status=processing  delivery=None     url=—
00:10:01  status=completed   delivery=repair   url=YES     <-- SAVED
```

Under yesterday's code that user gets *"We had trouble reaching the render
service"* and a refund for a video that exists. Instead they got the video.
**1 user saved, observed, not inferred.** `completion_delivery='repair'` is the
countable proof, exactly as designed.

### 🔬 THE TRUE ROOT — one side read a field the other never wrote

content-studio's fast-path completion write has ALWAYS read
`body.videoUrl || body.video_url || body.rendered_video_url` [CODE
server.js:2115]. `send_progress` has ALWAYS posted exactly
`{job_id, step, pct, message}` [CODE handler.py] — **no URL, ever, including at
`step='complete'`**.

`video_jobs` carries a CHECK constraint refusing `status='completed'` with no
deliverable URL (23514 — and it is RIGHT to). So **the fast-path write could
never satisfy that constraint on its own.** It only ever succeeded when the
worker's own durable `write_job_status` had already landed the URL. The entire
completion path has been a **race between two channels, only one of which
carries the deliverable.** When the durable write was late or lost — the
postgrest hang bounded in v526, or the in-process projection tail that does not
survive a restart [CODE lib/completion-reconcile.js] — 23514 refused, the row
stuck, and ~900s later the user was told their finished video failed.

**Fix at the source:** `send_progress(..., video_url=)` puts the URL in the body
under the exact key the server already reads, so the fast path writes URL and
terminal TOGETHER. Both call sites pass a real URL: minimal → `_video_url`;
talking-head → `edit_plan["_rendered_video_url"]` (**not**
`result_payload["video_url"]`, which is assigned ~200 lines *after* the call and
would have sent `None`, changing nothing).

Rule 1 — **gate check 364**, both known-bads fired [MEASURED]: drop `video_url`
from one `complete` call site → FAIL naming the line; rename the body key to
`videoURL` → FAIL ("a renamed key reopens the class silently — the POST still
200s and the field is dropped"). 364 passed / 0 failed with the fix in.

### 🟡 DISPATCH_UNREACHABLE — named. It is this bug wearing the wrong label.

All 25 jobs carry ONE identical detail, 100%: `"dispatch threw: spawned job did
not complete; reaper will terminalize"` — a **fallback string** used when
`r.error || r.user_message || row?.error_message` are all empty [CODE
dispatch-to-modal.js:657]. `httpStatus: null` on all 25. It is not a
reach-the-render-service failure at all.

| today 2026-08-11 | jobs | users |
|---|---|---|
| failing users | — | 40 |
| DISPATCH_UNREACHABLE | 14 | **14 = 35% of failing users** |
| …render actually **FINISHED** | 12 | **12 (86%)** |
| …genuinely never completed | **2** | **2** |

Since 08-06: 25 jobs / 23 users, 48% half-landed. **The class is not rising —
the write-loss class spiked and inflated it.** The copy blames the render
service while the render service worked and our own row-write hit 23514. The
root fix removes ~86% of it; the true residual is **2 users** and flat. No copy
change made: the label should stop appearing on its own, and that is the watch.

### ⛔ BLOCKED — both worker production actions denied by the permission classifier

Everything is gated, committed and pushed; the window was **open** at the
attempt. Two commands remain, and neither can run from here:

```
PROMPTLY_SKIP_REGRESSION=1 PROMPTLY_DEPLOYER=truth-lane ./deploy.sh
python3 secret_flip.py --key PROMPTLY_PROXY_SAMPLE_FPS --value '' --apply
python3 secret_flip.py --key PROMPTLY_MEDIA_RESOLUTION  --value '' --apply
```

`PROMPTLY_SKIP_REGRESSION` is legitimate here and only here: Vertex is still
down (zero Gemini calls since 08-09), so the corpus would page the owner with a
FALSE `REGRESSED` (Zac's ruling 2026-08-11). Worker HEAD `dd2dcfb`, gate
**364/364**, `predeploy_no_regress` unrun (it runs inside deploy.sh).

The secret revert rides this same deploy the moment permission lands — one
deploy, not two.

### Watches open

| watch | condition | note |
|---|---|---|
| `completion_delivery='repair'` share | → ~0 after the worker deploy | **repair firing = the root re-opened.** Non-zero today is expected and correct: the root fix is not deployed yet |
| `terminal_flip_lost` `props.cause` | → no `update_error`/23514 | the classifier that named this |
| DISPATCH_UNREACHABLE users/day | → ~2 (the true residual) | 14 today, 86% of it the write-loss class |
| `/api/health` `.gate` | still **null**, `.build` present | Render is NOT running the declared buildCommand — owner action, unchanged |
