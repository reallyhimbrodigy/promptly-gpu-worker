# LANE 4 — DELIVERY: handoff (2026-08-10)

Branches ready for TRUTH's queue. Every claim tagged. **Two of the brief's
premises were overturned by measurement — read "Corrected map" first.**

## Corrected map (vs the Aug-9 recon brief)

1. **The worker's durable status layer is LIVE, not dark.** [MEASURED]
   `phase="Done"` + full worker result envelope on fresh completed rows;
   `modal_app.py:495` sets `PROMPTLY_JOB_TABLE=video_jobs` and
   `JOB_STATUS_WRITES_ENABLED` ON since directive #6 (2026-07-02). The brief
   read the CODE DEFAULT (`"jobs"`, flag off) — that default was a landmine,
   not the live state. The p99 wall is therefore purely: *the 15-min timer was
   the only trigger for a recovery whose data landed at ~205s*.
2. **The RevenueCat webhook is ALIVE and applying events.** [MEASURED]
   22 applied-event mirrors Jul 21 → Aug 9 (INITIAL_PURCHASE, CANCELLATION,
   EXPIRATION, BILLING_ISSUE), incl. a purchase applied minutes before this
   session measured it. `rc_last_event_ms` NULL everywhere ≠ webhook dead —
   events applied without the stamp (likely `event_timestamp_ms` absent → the
   ordering guard is skipped; benign). **No renewal has ever been observed
   because every weekly subscriber so far CANCELLED within days** — not
   because the pipe is broken.
3. **`/sync` is the broken half.** [MEASURED] Every `reconcile_result` row ever
   written says `NO_RC_CUSTOMER` — including one 16 s after a webhook-applied
   purchase. That is the wrong-project-id signature on the v2 REST path
   [INFERRED, now instrumented to prove itself: reason `RC_CONFIG_SUSPECT`].

## The 900s-wall decomposition (Aug 2–9, 2,952 completed) [MEASURED]

41 jobs in e2e∈[870,920], 41 distinct users:
- 27 = one burst, Aug 3 06:05–08:06Z — the MODAL_CALLBACK_SECRET enforcement
  flip (job 42f89b95, the flip marker, is in the list). One-time, already fixed.
- 7 = worker itself took 850–900s (slow pipeline, delivery worked).
- ~3 + ~2/day drip = true missed callbacks (push claim fired only at the
  fallback tail). In ~31/41 the user WAS pushed on time via the worker's
  progress-complete POST; only completed_at + enrichment waited for the timer —
  the wall is part measurement artifact, part enrichment lag, and ~3 real
  late-to-user deliveries/week.

## What shipped (commits)

### worker `lane/delivery` @ 4efa2d2 (base: live 1601ae0)
- Completion POST: 4 attempts, 5/15/45s backoff; ALL-failed persists the
  per-attempt reason to `result->callback_post` (queryable). [handler unchanged;
  modal_app.py run_pipeline_bg]
- `lang_bundle` 0/218 ROOT CAUSE fixed: `edit_plan["_lang_bundle"]=` ran on the
  recipe THREAD before the enclosing scope bound `edit_plan` → NameError every
  job, swallowed. Now a `_lang_bundle_holder` channel defined before the thread.
- `worker_started_at` stamped at pipeline pickup (isolated single-column write;
  no-ops until migration).
- `PROMPTLY_JOB_TABLE` default `"jobs"` → `"video_jobs"` at all 5 sites.
- `cert_delivery_static.py` — AST gate for all four laws (caught 3 extra
  `"jobs"` defaults on first run). **TRUTH: please wire into validate_deploy.**

### content-studio `lane/delivery` @ 88e412c (base: origin/main 324d907)
- `completion_delivery` stamped on every settle path and persisted to a new
  column (first-stamp-wins): callback / webhook / durable_poll / fallback_timer
  / reconciler / orphan_callback / sync.
- **Durable-row early poll (75 s)** while dispatch awaits the callback — a
  missed callback now costs ≤75 s, not 900. Settle-once race-proof; needs_input
  and uncoded-failed rows deliberately left to the timer (ask-back + respawn
  stay owners). Coded-failed rows settle in the callback's exact envelope shape
  (honest copy + refund path, not the generic catch).
- Orphaned-callback handling on `settled=false` (the every-deploy-orphans law):
  analytics row + completed_at backfill + marker + claim-guarded push.
- `rc_webhook_received` counter on EVERY webhook hit (incl. 401/503).
- `/sync`: RC project probe distinguishes `NO_RC_CUSTOMER` vs
  `RC_CONFIG_SUSPECT`; narrowest-predicate revoke (RC_NOT_ACTIVE + RC-sourced
  pro + pro_until already past + never comped).
- `migrations/20260810_completion_delivery.sql` + `lib/__smoke_completion_delivery.js`.
- Gate: 20/20 smokes green (`node validate_deploy.js`).

## TRUTH deploy queue (order matters)

1. **Migration first** (safe anytime — code soft-fails without it): paste
   `migrations/20260810_completion_delivery.sql` into the Supabase SQL editor.
   Two `alter table ... add column if not exists` on video_jobs. No writes break
   if it's late; the marker/run-signal just stay null.
2. **content-studio `lane/delivery`** → merge to main (Render autodeploys).
   Batch + announce per the deploy-cadence law; in-flight jobs at deploy time
   will produce the first `orphan_callback` rows — that is the instrument
   working, attribute them to the deploy window.
3. **worker `lane/delivery`** → speed-worktree merge → `validate_deploy.py` +
   `deploy.sh`. Independent of (2); either order OK.
4. **No flag flips required for any of the above.** All changes are live-on-
   deploy and inert-negative (worst case = today's behavior).

## Flip requests (one at a time, 24 h JUDGE watch each)

1. `PROMPTLY_HLS_COPY=1` [CODE handler.py:31742] — ~72 s re-encode → ~1 s copy
   on the critical path. Before flip: one real delivery checked for client
   preview→final swap (the docstring's own bar). Watch: upload_export stage
   timing + any HLS playback complaint.
2. `PROMPTLY_PROXY_SAMPLE_FPS=2` **+** `PROMPTLY_MEDIA_RESOLUTION=MEDIA_RESOLUTION_LOW`
   [CODE handler.py:13265, 12308] — the value must be the FULL enum string;
   bare `LOW` goes verbatim into the genai call and fails the plan leg.
   A/B evidence: **INCONCLUSIVE — do not flip yet.** One run executed
   (2026-08-10, ~$0.06–0.12 actual, app ap-9CoM9B1yBizMU49dxwGOkV): BOTH arms
   fell to `recipe:safe_edit_fallback` (n_calls=0, Gemini leg 0 s) on the
   harness's single source — the Gemini leg the lever targets never ran, so
   token/wall/quality deltas are unmeasured [MEASURED: the fallback, not the
   lever]. The harness needs a source that reaches the plan leg (or the
   safe-edit cause diagnosed) + HARNESS's ~10-source corpus before this lever
   is flip-eligible. Overrides plumbing itself is verified present
   [CODE handler.py:37552-37557]. Budget note: $0.06–0.12 spent of the
   pre-approved $5; the corpus re-run fits comfortably.
   Bonus from the same run: the lang_bundle fix executed on a REAL pipeline
   (the `language_bundle:lang_bundle` divergence recorded — impossible under
   the old NameError, which threw before that line).

## JUDGE scoreboard lines (SQL over PostgREST or SQL editor)

```sql
-- delivery mechanism distribution (the lane's headline)
select completion_delivery, count(*) from video_jobs
 where status in ('completed','failed') and created_at > now() - interval '1 day'
 group by 1 order by 2 desc;

-- p99 off the wall: completed e2e percentiles
select percentile_cont(0.5) within group (order by extract(epoch from completed_at-created_at)) p50,
       percentile_cont(0.99) within group (order by extract(epoch from completed_at-created_at)) p99
  from video_jobs where status='completed' and created_at > now() - interval '1 day';

-- callback misses now name themselves
select id, result->'callback_post' from video_jobs
 where result->'callback_post' is not null and created_at > now() - interval '7 days';

-- worker-ran denominator
select count(*) filter (where worker_started_at is not null) worker_ran, count(*) total
  from video_jobs where created_at > now() - interval '1 day';

-- lang_bundle live again (was 0/218)
select count(*) from video_jobs
 where result->'stage_timings'->'lang_bundle' is not null
   and created_at > now() - interval '1 day';

-- RC: received vs applied
select props->>'outcome', count(*) from analytics_events
 where event='rc_webhook_received' and created_at > now() - interval '7 days' group by 1;
```

## OWNER (Zac) — RevenueCat checklist + the renewal watch

**The webhook config is CORRECT — do not touch it.** [MEASURED: events apply]

The broken half is the REST pair used by `/sync`/self-heal. In Render env for
content-studio:
1. `REVENUECAT_PROJECT_ID` must be the **V2 project id** (starts `proj…`) from
   RC dashboard → Project settings → General. The signature of it being wrong
   is exactly what we measure: every `/sync` → `NO_RC_CUSTOMER`, even for
   active subscribers.
2. `REVENUECAT_SECRET_KEY` must be a **V2 secret API key** (`sk_…`) created in
   THAT project (Project settings → API keys). A v1 key or another project's
   key 404s identically.
3. After the next deploy, a wrong pair logs `[RevenueCat] CONFIG SUSPECT …`
   once per process and `/sync` events start reading `RC_CONFIG_SUSPECT`
   instead of `NO_RC_CUSTOMER` — that's the confirmation the probe works.

**Renewal watch — time-critical [MEASURED]:** subscriber `02fd66aa` (weekly,
bought Aug 3, NEVER cancelled) hits the first-ever real renewal at
**Aug 10 ~12:32 UTC**. If the webhook applies it: `subscription_renewal`
mirror event appears + `pro_until` advances to ~Aug 17 — the renewal path is
PROVEN and exit criterion 3 closes. If by Aug 10 18:00 UTC nothing landed:
check RC dashboard → the customer → events, and the webhook delivery log for
that event id. Second watch: `decc42df` renews ~Aug 16. (`9661ff11` cancelled
Aug 5 → will EXPIRE ~Aug 11 — expect a normal EXPIRATION, not a renewal.)

Cohort truth (all paying subs ever, n=8 with any pro state): 4 comped/manual,
1 yearly trial lapsed cleanly, 5 weekly purchasers of which 4 cancelled inside
their first week (1aa24c33, 669b5654, 9661ff11, c86582f1 — churn signal for
product, not a billing bug), 1 still active + uncancelled (02fd66aa), 1 bought
Aug 9 (decc42df). Nobody is stranded on a stale grant. [MEASURED]

## Deviations from the brief

- Step 3's "point write_job_status at video_jobs + flip the flag" was already
  live in prod via env; shipped as a default-fix + cert so it can't regress.
- Step 2's "retry the POST" ships, but retry can NOT fix the deploy-orphan
  class (the POST succeeds against the wrong process) — the poller + orphan
  handler are the root fix for that class.
- Exit criterion 5 (24 h watches) needs elapsed time + TRUTH's flips; staged,
  not claimable from this session.
- Modal spend this session: one PLAN_ONLY A/B run (~$0.20–0.40 stated in
  advance; actual in the lane report) + ~45 s of `modal app logs` streaming
  (free). `modal app list` verified clean of orphans after the run.
