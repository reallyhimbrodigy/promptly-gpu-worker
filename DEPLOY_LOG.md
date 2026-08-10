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
| W4 | smoothness | agent/smoothness @ d9543d6 | held-out past-live commits: 8dd3954 (gate retire, partly superseded), d9543d6 (**real crash fix** — Vertex-omitted optional string, asText guard ×9 components). | — | — | ride with W1 |

### content-studio queue

| # | lane | branch @ sha | what | status |
|---|---|---|---|---|
| C0 | TRUTH + JUDGE | lane/truth @ 499511d + lane/judge @ 84f8244 | **batched**: gate wiring (Render build + blocking CI) + CHECKOUTS/LANE_OWNERSHIP/DEPLOY_LOG/OWNER_ACTIONS/sentinel spec, plus JUDGE's 5 scripts, 2 migrations, daily-scoreboard cron. Batched because both carry **zero request-path runtime risk** and their watches are independent (gate = build log; JUDGE = the 15:00 UTC row) — one orphan window instead of two. | WAITING for quiet window |
| C1 | DELIVERY | lane/delivery @ 88e412c | server.js +140, dispatch-to-modal.js +145, modal-webhook, 75s durable poller, `completion_delivery` migration, RC `/sync` probe. **Deployed alone** — it is the only package that changes the request path, and its 48h watch must not be confounded. | after C0 |

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
