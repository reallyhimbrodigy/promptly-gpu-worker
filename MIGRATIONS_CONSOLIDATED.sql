-- ============================================================================
-- PROMPTLY — CONSOLIDATED MIGRATION BLOCK          (assembled by TRUTH, 2026-08-11)
--
-- All three pending migrations, in one idempotent paste, with a verification
-- query at the tail. Safe to run repeatedly: every statement is
-- `if not exists`. No existing column is altered, retyped, or dropped, and no
-- data is written or deleted.
--
--   1. JUDGE    supabase/migrations/20260810_fulfillment_scores.sql
--   2. JUDGE    supabase/migrations/20260810_daily_scoreboard.sql
--   3. DELIVERY migrations/20260810_completion_delivery.sql
--
-- WHY IT IS NEEDED: the code for all three is ALREADY LIVE in production and
-- soft-failing by design. Until this runs, two watches are blind —
-- DELIVERY's delivery-mechanism mix (the 900s-wall instrument writes nothing)
-- and JUDGE's daily scoreboard row (falls back to a JSONL file on Render's
-- ephemeral disk).
--
-- HOW TO RUN: paste the whole thing into the Supabase SQL editor and execute.
-- Expected runtime: well under a second. (No psql/pg/pooler password exists on
-- the deploy machine — verified three ways, incl. probing for an exec_sql RPC.)
-- ============================================================================

begin;

-- ── 1. JUDGE — per-job fulfillment judgments ────────────────────────────────
create table if not exists public.fulfillment_scores (
  job_id uuid primary key,
  judged_at timestamptz not null default now(),
  judge_model text not null,
  judge_version int not null default 1,
  is_preset boolean not null,
  route text,                      -- standard_editorial | minimal | minimal_speech_uncut | moodreel | hype
  n_asks int not null,
  n_honored int not null,
  n_dropped_with_note int not null,
  n_dropped_silently int not null,
  n_unsupported int not null,
  honor_rate numeric,              -- honored / n_asks
  asks jsonb not null,             -- [{text, class, verdict, noted, evidence}]
  flags jsonb,
  vibe_input text,
  created_at timestamptz,          -- the JOB's created_at (scoreboard filters by day on this)
  change_request text
);
create index if not exists fulfillment_scores_judged_at_idx
  on public.fulfillment_scores (judged_at);
create index if not exists fulfillment_scores_route_idx
  on public.fulfillment_scores (route);

-- ── 2. JUDGE — the four-number daily scoreboard ─────────────────────────────
create table if not exists public.daily_scoreboard (
  day date primary key,
  computed_at timestamptz not null default now(),
  -- 1. fulfillment
  fulfillment_honor_rate numeric,
  fulfillment_dropped_silently_rate numeric,
  fulfillment_n_jobs int,
  -- 2. latency (e2e = completed_at - created_at; the user's wait)
  latency_p50_s numeric,
  latency_p90_s numeric,
  latency_p99_s numeric,
  latency_premium_p50_s numeric,   -- standard_editorial route only
  callback_gap_jobs int,           -- e2e - worker_total > 120s (the ~900s artifact)
  latency_n_jobs int,
  -- 3. export / conversion
  exports int,
  result_views int,
  export_per_viewed numeric,
  purchases int,
  -- 4. defect rate (populated when HARNESS emits it)
  defect_rate numeric,
  defect_n int
);

-- ── 3. DELIVERY — which mechanism settled each job, + real worker-start ─────
-- completion_delivery values: callback | webhook | durable_poll | fallback_timer
--                             | reconciler | orphan_callback | sync
-- First-stamp-wins. The 41-jobs-at-the-900s-wall class was invisible for weeks
-- because a fallback settlement looked identical to a normal completion.
alter table video_jobs add column if not exists completion_delivery text;

-- worker_started_at: the "a worker actually ran" signal. started_at stamps the
-- dispatch ATTEMPT, which poisons every completion denominator (a job that
-- never reached a worker still carries started_at). NULL here = never picked up.
alter table video_jobs add column if not exists worker_started_at timestamptz;

commit;

-- ============================================================================
-- VERIFICATION — run this after the block. Expect EXACTLY 4 rows, all `ok`.
-- Anything reading `MISSING` means that object did not get created.
-- ============================================================================
select 'table  public.fulfillment_scores' as object,
       case when to_regclass('public.fulfillment_scores')  is not null then 'ok' else 'MISSING' end as status
union all
select 'table  public.daily_scoreboard',
       case when to_regclass('public.daily_scoreboard')    is not null then 'ok' else 'MISSING' end
union all
select 'column video_jobs.completion_delivery',
       case when exists (select 1 from information_schema.columns
                          where table_name = 'video_jobs'
                            and column_name = 'completion_delivery') then 'ok' else 'MISSING' end
union all
select 'column video_jobs.worker_started_at',
       case when exists (select 1 from information_schema.columns
                          where table_name = 'video_jobs'
                            and column_name = 'worker_started_at') then 'ok' else 'MISSING' end
order by 1;

-- ============================================================================
-- WHAT HAPPENS NEXT (TRUTH runs these; no action needed from you)
--   • DELIVERY's instrument starts writing immediately on the next completion.
--     TRUTH confirms rows are actually FLOWING before starting the 48h watch
--     clock — a migration that ran is not the same as an instrument that works.
--       select completion_delivery, count(*) from video_jobs
--        where status in ('completed','failed')
--          and created_at > now() - interval '1 day'
--        group by 1 order by 2 desc;
--   • JUDGE back-fills the catalogue (scripts/load-scores-to-table.js) and the
--     15:00Z cron writes a real table row instead of the JSONL fallback.
-- ============================================================================
