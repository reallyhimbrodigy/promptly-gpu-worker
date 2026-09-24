-- RE-EDITS PER VIDEO, WEEKLY. Read-only.
--
-- COUNTED PER ROOT VIDEO, NOT PER PARENT, AND THAT IS THE WHOLE POINT OF THE
-- RECURSIVE WALK. parent_job_id chains re-edit to re-edit — depth 4 observed
-- in production — so counting DISTINCT parent_job_id splits one video's
-- history across several rows and UNDERSTATES the tail. Measured both ways on
-- 2026-09-24:
--
--                       per PARENT      per ROOT
--     videos re-edited        88            69
--     rate                  2.7%          2.1%
--     p90                      2             3
--     max                      4             6
--
-- The videos a cap is about are precisely the repeatedly-re-edited ones, and
-- those are the ones the per-parent count hides.
--
-- WHY WEEKLY. Instant re-edits are expected to raise usage, so this
-- distribution is a reading and not a settled fact. The cap ruling (10) was
-- made against a window where NOTHING reached 6, let alone 10 — if that
-- changes, the ceiling arithmetic in pricing_model.cost_per_video() is what
-- it changes into.

WITH RECURSIVE roots AS (
  SELECT id, id AS root
  FROM video_jobs
  WHERE parent_job_id IS NULL
    AND created_at > now() - interval '30 days'
  UNION ALL
  SELECT v.id, r.root
  FROM video_jobs v JOIN roots r ON v.parent_job_id = r.id
), per_video AS (
  SELECT root, count(*) FILTER (WHERE id <> root) AS n
  FROM roots GROUP BY root
)
SELECT
  (SELECT count(*) FROM video_jobs
     WHERE parent_job_id IS NULL
       AND created_at > now() - interval '30 days')            AS first_edits,
  sum(n)                                                       AS reedits,
  count(*) FILTER (WHERE n > 0)                                AS videos_reedited,
  round(100.0 * count(*) FILTER (WHERE n > 0) / NULLIF(count(*), 0), 2) AS pct_of_videos,
  round(avg(n) FILTER (WHERE n > 0), 2)                        AS mean_when_reedited,
  percentile_disc(0.50) WITHIN GROUP (ORDER BY n) FILTER (WHERE n > 0) AS p50,
  percentile_disc(0.90) WITHIN GROUP (ORDER BY n) FILTER (WHERE n > 0) AS p90,
  percentile_disc(0.99) WITHIN GROUP (ORDER BY n) FILTER (WHERE n > 0) AS p99,
  max(n)                                                       AS max_per_video,
  -- THE NUMBER THE CAP RULING RESTS ON. It was ZERO on 2026-09-24. A non-zero
  -- here means real users are hitting the cap and the ceiling arithmetic has
  -- stopped being hypothetical.
  count(*) FILTER (WHERE n >= 10)                              AS at_or_over_cap_10
FROM per_video;
