-- Status vocabulary canonicalization (Step 3.1 of the status reconciliation).
-- Canonical set (ratified): queued, processing, completed, failed, canceled, needs_input
--   (American `canceled`; `needs_input` included now for the dormant ask-back rail).
-- Idempotent: safe to run repeatedly. Normalization included for completeness —
-- the 2026-07-03 full-table probe found zero legacy-spelling rows (the old
-- constraint made them impossible), so the UPDATEs are expected no-ops.
--
-- Applied via the Supabase SQL editor (no direct PG credential ships in
-- promptly-secrets — PostgREST cannot run DDL). The worker session re-runs
-- its bounce probe immediately after as the live read-back proof:
-- canceled/needs_input/completed writes must LAND, legacy spellings must
-- still bounce or be absent.

BEGIN;

ALTER TABLE video_jobs DROP CONSTRAINT IF EXISTS valid_status;

UPDATE video_jobs SET status = 'completed' WHERE status = 'complete';
UPDATE video_jobs SET status = 'canceled'  WHERE status = 'cancelled';

ALTER TABLE video_jobs ADD CONSTRAINT valid_status CHECK (
  status IN ('queued', 'processing', 'completed', 'failed', 'canceled', 'needs_input')
);

COMMIT;
