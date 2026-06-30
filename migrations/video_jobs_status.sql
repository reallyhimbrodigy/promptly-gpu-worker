-- Durable job-status / progress columns for `video_jobs` (worker-written).
--
-- PREREQUISITE for the durable-progress feature. The worker (handler.py
-- write_job_status) patches these columns; PostgREST SILENTLY DROPS writes to
-- columns that don't exist, so the feature is INERT until this runs. Apply it on
-- the Supabase project, THEN set JOB_STATUS_WRITES_ENABLED=1 (modal_app.py) and
-- redeploy.
--
-- `status` already exists (the concurrency gate reads it). The new columns:

alter table video_jobs add column if not exists progress         integer;        -- 0..100, weighted, monotonic
alter table video_jobs add column if not exists phase            text;           -- human label of the current stage
alter table video_jobs add column if not exists updated_at       timestamptz default now();
alter table video_jobs add column if not exists result           jsonb;          -- {video_url,...} on complete; {error_code,...} on failed
-- Reserved (no behavior yet — added now so Phase D / cancel are additive, not a re-migration):
alter table video_jobs add column if not exists partial_state    jsonb;          -- Phase D ask-back: the paused plan/transcript
alter table video_jobs add column if not exists cancel_requested boolean default false;  -- cancel-render: set by the app, checked at phase boundaries

-- Optional: index the poll path if the frontend reads by id heavily (id is the PK,
-- so a PK lookup is already indexed — this is only needed for non-PK filters).

-- ── status VALUES ────────────────────────────────────────────────────────────
-- The worker writes status in: queued | running | processing | needs_input |
-- complete | failed | canceled. If `video_jobs.status` is plain TEXT, no change
-- is needed. If it is a Postgres ENUM, ensure every value exists, e.g.:
--   alter type video_job_status add value if not exists 'processing';
--   alter type video_job_status add value if not exists 'needs_input';
--   alter type video_job_status add value if not exists 'complete';
--   alter type video_job_status add value if not exists 'failed';
--   alter type video_job_status add value if not exists 'canceled';
-- (Adapt the type name to your schema.)
--
-- ── status OWNERSHIP ─────────────────────────────────────────────────────────
-- Today the JS server writes video_jobs.status. With this feature on, the WORKER
-- also writes it (processing during the run; complete/failed/needs_input at the
-- end). Coordinate so the two don't fight: either let the worker own the terminal
-- status, or have the server stop writing status for worker-handled jobs. The
-- progress/phase/result columns are additive-safe; status is the contended one.
