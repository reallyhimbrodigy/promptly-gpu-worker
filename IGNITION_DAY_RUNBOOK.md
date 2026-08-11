# IGNITION DAY — the cascade, pre-planned (TRUTH, staged 2026-08-11)

**Trigger:** the owner says *"billing is fixed."* Nothing here needs a planning
pause; every step has its gate, its watch, and its abort condition already
decided.

**There are TWO Google billing surfaces and they fail independently.** Confirm
which one was fixed before running anything:

| surface | used by | failure seen | fix confirmed by |
|---|---|---|---|
| **Vertex AI** service account, GCP project `promptly-479218` | worker editorial + route detection | 403 PERMISSION_DENIED ("dunning decision is deny") | moodreel/hype reappear in `result.route` |
| **Gemini API key** (AI Studio prepay) | content-studio `/api/chat` + `/api/chat/stream` | 429 RESOURCE_EXHAUSTED ("prepayment credits are depleted") | `/api/internal/gemini-diag` `real_chat_test.http` = 200 |

Fixing one does **not** fix the other. Run the matching column.

---

## STEP 0 — PRECONDITION, already satisfied

`W1+W4` must be LIVE before Vertex returns. W4 (`d9543d6`) fixes the
optional-omission component crash, which is **dormant only because Gemini is
down** — it re-arms the moment plans start coming back. Deployed 2026-08-11.
**If for any reason W1+W4 is not live when billing is restored, deploy it
first, before anything else in this document.**

## STEP 1 — T+0 to T+60min: VERIFY, don't celebrate

Run at T+15, T+30, T+60 (traffic is ~10–30 completions/hour, so one hour is a
real denominator).

**Vertex column:**
```sql
select result->>'route' as route, count(*)
from video_jobs
where status='completed' and created_at > now() - interval '1 hour'
group by 1 order by 2 desc;
```
- **PASS:** `moodreel` and/or `hype` > 0, with **no deploy**. One incident,
  closed. Record the exact recovery timestamp in `OUTAGE_ROUTE_COLLAPSE.md`.
- **FAIL (still 0 after a full hour with n ≥ 10):** **declare a second P0
  immediately — stuck fail-safe.** Say so in the same hour; do not wait longer
  to be sure. The route detector is then failing for a reason other than
  billing, and the 4-day silent degradation continues.

**Gemini-API column:**
```
curl -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
     https://usepromptly.app/api/internal/gemini-diag
```
- **PASS:** `real_chat_test.http` = 200. Then confirm on real traffic:
  `usage_events` rows with `kind='chat'` resume (baseline: ~997/day across
  ~548 users on Aug 7; Aug 8–11 totalled **3**).
- **FAIL:** chat still 502s to every user. Separate P0, separate owner action.

## STEP 2 — REGRESSION CORPUS FIRST (codified rule)

**Before any further worker deploy.** `PROMPTLY_SKIP_REGRESSION` was legitimate
only for the outage window; the corpus's Gemini calls now work, and it is the
cheapest proof that the fixed-defect classes survived four days of blind
deploys.

```
python3 preflight_quiet_window.py && PROMPTLY_DEPLOYER=truth-lane ./deploy.sh
```
(no skip flag). Cost ~$0.50–0.90, declared. Verdict lands in Modal logs as
`[REGRESSION-CORPUS] ALL GREEN` or `REGRESSED:` — a REGRESSED self-alerts to the
owner. **Abort the cascade on REGRESSED.**

## STEP 3 — HARNESS FREEZE (HARNESS runs it; TRUTH never does)

HARNESS's own precondition #1 is *"Vertex must be healthy"* — they must run one
smoke capture and assert `gemini_n_calls > 0` **before** freezing, or the corpus
canonises fallback plans. That assertion is the gate; it is theirs to run.

When they report the freeze complete, TRUTH merges
`golden/validate_deploy_addition.py` into `validate_deploy.py` (paste ABOVE the
GATE INTEGRITY runner block per their placement note — a `@check` below the
runner is dead code and breaks the declared==ran counter). Confirm the corpus
check + differ self-test run green in the gate, then deploy on a quiet window.

## STEP 4 — DIFFER, one route at a time (SEAM's gate, ≤$10 pre-approved)

Per `SEAM_FLIP_PACKAGE.md`: for each of hype / moodreel / minimal /
minimal_speech_uncut, compose `base + profile`, PLAN_ONLY call on that route's
golden inputs, hand plans to the HARNESS differ. **Per-route target: GREEN vs
that route's golden envelope.** Any obedience-marker miss = hard stop + report.
Premium route is byte-identical by construction (cert), so its run is a
confirmation, not a risk.

## STEP 5 — FLIPS, one at a time, 24h watch each

**TRUTH does not flip flags on its own initiative.** Each flip needs the owner's
GO naming the key (standing secret-auth law), and a secret change is not live
until a redeploy (memory-snapshot law).

Order (SEAM's, unchanged):
1. `PROMPTLY_ADAPTER_V1`
2. `PROMPTLY_UNIFIED_CORE` (per-route progressive)
3. `PROMPTLY_SURGICAL_V2`
4. `PROMPTLY_CHAT_ACTIONS` — **only after the iOS router change ships**

Watch per flip: 24h JUDGE scoreboard, plus zero scoreboard movement as the pass
condition for anything claiming to be dark.

DELIVERY's latency levers are separate and ride the same one-at-a-time rule, on
DELIVERY's explicit per-lever request:
- `PROMPTLY_HLS_COPY=1` — needs one real delivery checked for preview→final swap.
- `PROMPTLY_PROXY_SAMPLE_FPS=2` + `PROMPTLY_MEDIA_RESOLUTION=MEDIA_RESOLUTION_LOW`
  — **INCONCLUSIVE, do not flip.** Both A/B arms fell to `safe_edit_fallback`
  (the outage), so the lever's own leg never ran. Needs a re-run on a source
  that reaches the plan leg. The enum must be the FULL string; bare `LOW` fails
  the plan leg verbatim.

## QUIET WINDOWS — how they are assigned

**Not by clock — by the gate.** `preflight_quiet_window.py` is the only
authority: zero in-flight user jobs (`processing|pending|queued`), with a
non-vacuity check that refuses to call a zero quiet unless it can also see
recent rows. Observed 2026-08-11: windows open **many times per hour**; the
longest wait all day was ~20 minutes. So every step below is simply
"gate-then-go", and none of them needs to be scheduled in advance:

```
python3 preflight_quiet_window.py && <the step>
```

Deploy cadence still applies — **batch, announce, attribute**. Steps 2, 3 and 5
are separate deploys by necessity (each needs its own clean watch); steps
within the same category ride together.

## ABORT CONDITIONS (any one stops the cascade)

- Regression corpus reports `REGRESSED`.
- `predeploy_no_regress.py` fires and the loss is not a reviewed, documented
  intentional removal. **Never force it** — STOP and report.
- Route distribution does not recover within one hour of billing (that is P0 #2,
  and it outranks the rest of this document).
- Any differ route comes back RED, or an obedience marker is missed.
