# LAUNCH DAY — one compressed window, start to demo

**Single source of truth for launch day.** Supersedes `IGNITION_DAY_RUNBOOK.md`
(TRUTH) and folds in HARNESS's freeze procedure (`golden/README.md`) and SEAM's
flip cascade + six-demo acceptance (`SEAM_FLIP_PACKAGE.md`,
`scripts/seam-acceptance.js`). Assembled by TRUTH 2026-08-11. **It sits ready
for whichever day the owner picks** — nothing here needs a planning pause.

```
payments land → route-recovery check (1 traffic hour) → freeze (old arch, flags OFF)
    → per-route differ → flip cascade → six-demo validation
```

---

## ⚠️ THE ONE RISK LINE — read before starting

**The compressed window has no iteration slack.** There is no room to tune a
route on launch day. Therefore:

> **Anything that fails the differ is HELD, not tuned. Launch does not stall on
> one route.**

A route whose differ comes back RED keeps its **flag OFF** and ships in the
next window; the other routes proceed. The instinct to "just fix it quickly"
is the thing that turns a compressed window into a missed one. Hold, record,
move on.

---

## STEP 0 — PRECONDITIONS (all satisfied as of 2026-08-11)

| precondition | state |
|---|---|
| One worker deploy lineage, live commit an ancestor | ✅ v522+ |
| W4 component-crash fix LIVE **before** Gemini returns (its class re-arms when plans come back) | ✅ v523 |
| DELIVERY both halves live | ✅ v523 + cs `8f54923` |
| SEAM dark package live, all 6 flags absent=dark, `/api/chat/actions` 404s | ✅ v525 + cs `fd0b9e1` |
| Safety gates blocking (CI proven both directions; 362 worker checks) | ✅ |
| **Three migrations applied** | ❌ **owner** — `MIGRATIONS_CONSOLIDATED.sql`, one idempotent paste |

**If the migrations are not applied, launch day still runs** — but the
`completion_delivery` instrument and JUDGE's scoreboard row stay blind, so you
lose the two best watches. Strongly prefer applying them first.

---

## STEP 1 — PAYMENTS LAND (owner)

**Two independent Google billing surfaces.** Fixing one does not fix the other;
confirm which was paid before proceeding.

| surface | pays for | failure signature | confirm fixed by |
|---|---|---|---|
| **Vertex AI** (GCP project `promptly-479218`) | worker editorial + route detection | 403 PERMISSION_DENIED "dunning decision is deny" | moodreel/hype reappear in `result.route` |
| **Gemini API key** (AI Studio prepay) | `/api/chat`, `/api/chat/stream` | 429 RESOURCE_EXHAUSTED "prepayment credits are depleted" | `/api/internal/gemini-diag` → `real_chat_test.http` = 200 |

Also on the owner's list, independent of the above: **RevenueCat**
`REVENUECAT_PROJECT_ID` → the `proj…` v2 id + matching `sk_…` key (per
DELIVERY's checklist; their `/sync` probe self-verifies afterwards).

---

## STEP 2 — ROUTE-RECOVERY CHECK — exactly one traffic hour (TRUTH)

**Do not start the freeze until this passes.** Freezing during the outage
canonises fallback plans — HARNESS's precondition #1, learned on 2026-08-09.

Sample at T+15, T+30, T+60 (traffic runs ~10–30 completions/hour, so an hour
is a real denominator):

```sql
select result->>'route' as route, count(*)
from video_jobs
where status='completed' and created_at > now() - interval '1 hour'
group by 1 order by 2 desc;
```

- **PASS** — `moodreel` and/or `hype` > 0 **with no deploy**. Baseline for
  comparison: premium routes were **31.6%** of completions pre-outage
  (346 moodreel + 25 hype / 1,174, Aug 5 → Aug 8 11:16Z).
- **FAIL** — still 0 after a full hour with n ≥ 10: **declare a second P0
  immediately — stuck fail-safe — and say so in that hour.** The route detector
  is then broken for a reason other than billing. **Launch day stops here**;
  everything downstream depends on real editorial plans.

Chat, in parallel: `real_chat_test.http` = 200 **and** `usage_events(kind='chat')`
rows resuming (baseline ≈ 997/day across ≈ 548 users; Aug 8–11 totalled 3).

---

## STEP 3 — REGRESSION CORPUS FIRST (TRUTH, ~$0.50–0.90)

Standing rule: `PROMPTLY_SKIP_REGRESSION` was outage-only, and the corpus is
**the first verification run once billing is back, before any further worker
deploy.**

```bash
python3 preflight_quiet_window.py && PROMPTLY_DEPLOYER=truth-lane ./deploy.sh
```
(no skip flag). Verdict lands in Modal logs: `[REGRESSION-CORPUS] ALL GREEN`
or `REGRESSED:` — a REGRESSED self-alerts to the owner.
**REGRESSED ⇒ abort the cascade.**

---

## STEP 4 — FREEZE THE GOLDENS: OLD ARCHITECTURE, FLAGS OFF (HARNESS, ~$4–6.5)

The goldens must capture **today's known-good behaviour** — the old
architecture with every SEAM flag OFF — because the differ's entire value is
judging the candidate against *what was true*.

```bash
cd .worktrees/lane-harness      # worktree pinned to the commit being frozen
modal run golden_freeze_app.py --runs 3 --out golden/plans
```

HARNESS's own preconditions, all of which are theirs to run:
1. **Vertex healthy** — one smoke capture asserting `gemini_n_calls > 0`
   *before* freezing. Step 2 above is the coarse version; this is the fine one.
2. Run from the worktree pinned to the frozen commit (the image bundles that
   working tree's `handler.py`).
3. `models/` must exist in the worktree (untracked; copy from the main checkout).
4. Ledger the batch in `MODAL_SPEND_LEDGER.md`; verify `modal app list` shows
   **0 tasks** afterwards (`.spawn()`ed containers outlive the local run).

3 runs per source, because plan generation is stochastic — a single golden
would false-alarm constantly. 25 sources, route-stratified, Hindi-weighted.

**Re-freezing is a deliberate act, never automatic** — only after a change is
approved as *better*, with the owner's sign-off recorded in the commit that
replaces `golden/plans/`. A casually re-frozen golden is a deleted tripwire.

When the freeze completes, TRUTH merges
`golden/validate_deploy_addition.py` into `validate_deploy.py` (paste **above**
the GATE INTEGRITY runner block — a `@check` below it is dead code and breaks
the declared==ran counter) and deploys on a quiet window.

---

## STEP 5 — PER-ROUTE DIFFER (SEAM + HARNESS, ~$0.10/run, ≤$10 pre-approved)

One route at a time: hype → moodreel → minimal → minimal_speech_uncut, then
the editorial/premium arm.

```bash
modal run golden_freeze_app.py --runs 3 --out /tmp/candidate/plans   # candidate, flags ON for that route
python3 harness_plan_diff.py diff --golden golden/plans \
    --candidate /tmp/candidate/plans --manifest golden/manifest.json \
    --out /tmp/candidate/report.json
```

**Verdicts:** `GREEN` = the corpus saw no regression (**not** proof of
improvement). `YELLOW` = read the itemised drift and decide deliberately.
`RED` = do not flip.

**THE HOLD RULE (the risk line, applied):** RED or a missed obedience marker ⇒
that route's flag stays **OFF**, it is recorded in `DEPLOY_LOG.md`, and the
cascade **continues with the other routes**. No tuning inside the window.

Premium is byte-identical by construction (cert_unified_core), so its differ
run is a confirmation, not a risk.

---

## STEP 6 — FLIP CASCADE (owner GO per flag; TRUTH executes)

**Every flip needs the owner's explicit GO naming the key** (secret-auth law),
and **a secret change is not live until a redeploy** (memory-snapshot law).
Registering the keys in CANON happens *with* the secret change, never before —
CANON is compared against the live readback, so a key the secret lacks fails
the gate for every lane.

Order, one at a time, each on a quiet window:

1. `PROMPTLY_ADAPTER_V1`
2. `PROMPTLY_UNIFIED_CORE` (per-route progressive — only routes that went GREEN)
3. `PROMPTLY_SURGICAL_V2`
4. `PROMPTLY_MG_OBEY`
5. `PROMPTLY_CAPTION_TRANSLATE`
6. `PROMPTLY_UPSCALE_NEGOTIATE`
7. `PROMPTLY_CHAT_ACTIONS` — **only after the iOS router change ships**

Watch per flip: 24h JUDGE scoreboard. For anything claiming to be dark, the
pass condition is **zero scoreboard movement**.

DELIVERY's latency levers ride the same one-at-a-time rule, on their explicit
per-lever request:
- `PROMPTLY_HLS_COPY=1` — needs one real delivery checked for preview→final swap.
- `PROMPTLY_PROXY_SAMPLE_FPS=2` + `PROMPTLY_MEDIA_RESOLUTION=MEDIA_RESOLUTION_LOW`
  — **INCONCLUSIVE, do not flip.** Both A/B arms fell to `safe_edit_fallback`
  during the outage, so the lever's own leg never ran. The enum must be the
  FULL string; bare `LOW` fails the plan leg verbatim.

---

## STEP 7 — SIX-DEMO VALIDATION (SEAM's script; TRUTH schedules)

```bash
BASE_URL=https://usepromptly.app SUPABASE_JWT=<demo user bearer> \
TEST_VIDEO_URL=<durable talking-head source containing the word "rise"> \
node scripts/seam-acceptance.js --run
```

| # | demo | capability |
|---|---|---|
| 1 | chat-render | attached video + free text → render via chat |
| 2 | chat-reedit | "make the captions yellow" → re-edit of last job |
| 3 | caption-spelling | "change 'rise' to 'ryze'" → display override |
| 4 | add-transition | "add a DipToBlack after …" → seam transition |
| 5 | caption-translate | "captions in hindi" → translated pages |
| 6 | upscale-negotiate | "Turn into 4k" → truthful negotiation note |

Design laws already built in: **honest SKIPs** (a dark flag reports
`SKIP(flag-dark)`, never FAIL — so it is runnable as a dry-run today and turns
green demo-by-demo as flags arm), **no parallel paths** (real public endpoints
with a real bearer, so quotas and gates hit exactly as production), and
**evidence not vibes** (each PASS names the row/field it read). Spend guard:
`MAX_JOBS` default 6.

Source must be a **constructed durable** asset, never user media.

---

## ABORT / HOLD MATRIX

| condition | action |
|---|---|
| Routes still 0 an hour after billing (n ≥ 10) | **STOP LAUNCH.** Second P0: stuck fail-safe. Say so immediately. |
| Regression corpus `REGRESSED` | **Abort cascade.** Investigate before any flip. |
| `predeploy_no_regress` fires, loss not a documented intentional removal | **STOP. Never force.** Report. |
| A route's differ RED / obedience marker missed | **HOLD that route (flag OFF), continue the others.** No tuning in-window. |
| A demo FAILs (not SKIPs) | Hold that capability's flag; the rest of the demo set stands. |
| Quiet window will not open | `preflight_quiet_window.py` is the only authority. Windows opened many times per hour on 2026-08-11; longest wait ~20 min. |

## STANDING RULES THAT DO NOT RELAX ON LAUNCH DAY

- **Quiet window = zero in-flight USER JOBS by the DB probe**, never Modal task
  count (prewarm/ASGI containers make that a false blocker).
- **No zero is believed until the same probe fires on the known-bad window.**
- Every deploy: gate green · no-regress green · ownership diff · secret readback
  · `DEPLOY_LOG.md` entry with a named watch.
- Report every rate with its denominator, cut **by route**, and lead with
  **users** affected, not job counts.
