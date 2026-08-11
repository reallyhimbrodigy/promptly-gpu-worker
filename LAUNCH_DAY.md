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

## DOCUMENT OWNERSHIP — docs carry ownership like code

This file is **canonical** and supersedes `IGNITION_DAY_RUNBOOK.md` (removed)
and the co-owned draft on `lane/harness` (redirected to here). Section
ownership is **hard**: edits to a section go through its owner's lane; the
other co-owner reviews, never rewrites.

| section | owner |
|---|---|
| Risk line, Steps 0–3, 6–7, abort matrix, standing rules | **TRUTH** |
| **Step 4–5 Freeze and differ** | **HARNESS** (lane/harness) — reproduced VERBATIM from `8daeab4` §1 |
| Step 6 flip order | **TRUTH**, SEAM consulted |

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

## STEPS 4–5 — FREEZE AND DIFFER — **HARNESS-owned, verbatim from `8daeab4` §1**

> Reproduced without edit. TRUTH does not rewrite this section; corrections
> go through lane/harness. TRUTH's only addition is the merge note at the end.

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

**TRUTH's handoff note (not part of HARNESS's section):** when the freeze
sequence completes, TRUTH merges `golden/validate_deploy_addition.py` into
`validate_deploy.py` — pasted **above** the GATE INTEGRITY runner block, since
a `@check` below it is dead code and breaks the declared==ran counter — then
deploys on a quiet window. **THE HOLD RULE applies to the differ verdicts
above:** a RED route keeps its flag OFF, is recorded in `DEPLOY_LOG.md`, and
the cascade continues with the other routes. No tuning inside the window.

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

### Step 6b — MG_OBEY: the 3-arm cert runs BEFORE its flip

`PROMPTLY_MG_OBEY` does not ride the ordinary flip lane — it has a purpose-built
A/B. Run `cert_mg_honoring_planonly_app.py`: three arms on the SAME source,
captured at `render_multi_clip` (bail before render), one of which is
`ask_obey` with `PROMPTLY_MG_OBEY=1` — the dark directive arm. Measures
standalone `motion_graphics[]` count + types + whys per arm.

Flip only if the obey arm honours the ask **without** the density collapse the
MG diagnosis named. RED ⇒ **hold the flag**, per the hold rule; the rest of the
cascade proceeds. (Prerequisite: Vertex healthy — the arms are PLAN_ONLY Gemini
calls, so this is meaningless during the outage.)

### Step 6c — PAYWALL ORDER — **BLOCKED pending DELIVERY's answer**

DELIVERY's open question (`IOS_FINAL_BUILD.md` §6): *are the package/plan
positions hardcoded inside `TrialWallView` / `PaywallView`, or do those views
already render the RC offering's order?*

- **If hardcoded** → the order must move to a server/RC-driven source (the RC
  offering's package sequence is the natural one), so it is reorderable **from
  the RC dashboard with no build**. That is an iOS build item, and it gates
  this step.
- **If the views already render the offering order** → this is a **no-op**;
  DELIVERY documents it and the step closes.

**TRUTH does not guess which.** The step stays BLOCKED until DELIVERY answers,
and it never blocks the rest of the cascade. The *initial* order is Zac's taste
call at ship time; the engineering item is only "order comes from config, not
code." Context for that call [MEASURED 2026-08-10]: every weekly subscriber to
date cancelled inside week 1.

Acceptance (from DELIVERY's list): *paywall order changes from the RC dashboard
(or config) without a build — or the no-op is documented.*

### Step 6d — EXPORT FLAGS — DELIVERY's four-step order, exactly

Each step is its **own deploy, verified** — never batched:

1. **Server code deploys dark** (`lane/delivery-2`). Nothing changes.
2. **Owner ships the iOS build** with §1–3. Nothing changes — the server still
   501s.
3. **`EXPORT_GATE_ENABLED=1`** → the wall arms for new-build users only. Old
   builds keep the fallback until they upgrade (**known and accepted decay** —
   not a defect to chase).
4. **`EXPORT_WATERMARK_ENABLED=1`** → free-quota exports watermark.

Deliberately NOT built: watermark-instead-of-402 beyond quota — a taste call
for Zac, one env value away if wanted.

**Verification, both required:** `gate_probe` fires in both directions on every
deploy, and `analytics_events.export_watermark_failed` must stay at **0** — any
row means a free export silently shipped clean, which is a defect, not a
degrade.

Note: step 3 and step 4 are flag flips and therefore need the owner's GO naming
each key, like every other flip in this cascade.

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
