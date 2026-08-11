# FLIP FILING — `PROMPTLY_HLS_COPY=1` (filed 2026-08-11, Lane 4 → TRUTH)

**GO authority:** Zac, 2026-08-11, naming the key explicitly ("File the
HLS_COPY flip today: it's render-path only, fully measurable on outage
traffic"). Satisfies the secret-auth law (owner GO naming the key).
**Executor:** TRUTH only. Not live until the post-change redeploy (Rule 2 —
memory snapshots freeze env at deploy).

## What it does

`_hls_copy_enabled()` [CODE handler.py:31742-31752]: replaces the 4-rendition
libx264 HLS re-encode of the finished MP4 with a single-rendition `-c copy`
segmentation (master.m3u8 + fMP4 segments preserved; the client swap contract
unchanged). Render-path only; no editorial dependency — safe during the Vertex
outage.

## Procedure (the 9-flag-secret landmine, spelled out)

The flag lives in the **`promptly-lang-flags` Modal Secret**. A
`modal secret create … --force` REPLACES the whole secret — any key not
restated is DROPPED. The live secret holds exactly these **31 keys**
[MEASURED 2026-08-11 via key-name probe, values not read]:

PROMPTLY_ASR_SCRIBE, PROMPTLY_BROLL_GATE, PROMPTLY_BURNED_TEXT,
PROMPTLY_CAPTION_ALIGN, PROMPTLY_COVERAGE_GATE, PROMPTLY_DELIVERY_FPS,
PROMPTLY_EDIT_IN_LANGUAGE, PROMPTLY_HLS_COPY, PROMPTLY_HQ_RESAMPLE,
PROMPTLY_HYPE_MODE, PROMPTLY_LANG_ROUTING, PROMPTLY_LEVER3,
PROMPTLY_MEDIA_RESOLUTION, PROMPTLY_MIN_OUTPUT_RATIO, PROMPTLY_MOODREEL,
PROMPTLY_MOTION_BLUR, PROMPTLY_OUTCOME_GATE, PROMPTLY_PLAN_CAPTURE,
PROMPTLY_POST_THINKING_BUDGET, PROMPTLY_PROXY_SAMPLE_FPS,
PROMPTLY_RENDER_BURST, PROMPTLY_RENDER_FANOUT, PROMPTLY_ROUTE_LANGS,
PROMPTLY_SCRIPT_DENYLIST, PROMPTLY_SHAPE_ABORT, PROMPTLY_SILENT_TO_MOODREEL,
PROMPTLY_SMOOTH_GRAPHICS, PROMPTLY_SPAWN_MODE, PROMPTLY_STRUCTURE_ABORT,
PROMPTLY_WHY_DIET, PROMPTLY_ZERO_REJECT

`PROMPTLY_HLS_COPY` already EXISTS as a key (currently off) — this is a
one-value change: restate all 31 keys with current values, `PROMPTLY_HLS_COPY=1`,
then redeploy through the normal queue (quiet-window gate = DB in-flight jobs,
not `modal app list`).

## Measurement (by cohort — the honest version of "~70s off p50")

- **Outage traffic (current, safe-edit/minimal routes)** [MEASURED n=289,
  Aug 9-11]: `stage_timings.upload_export` p50 **4.4s**, mean 6.0s, p90
  **10.4s**, max 55.8s (≈10% of worker total p50 44.5s). Expected post-flip:
  p50/p90 → ~1-2s. **The ~70s p50 win does NOT show on this cohort** — outputs
  are short and the heavy editorial routes are extinct during the Vertex
  outage.
- **Recovery traffic (std-editorial/premium, returns with Zac's GCP billing
  fix)**: the 77s 4-rendition re-encode [CODE comment handler.py:31743,
  measured Aug 1] → ~1s. This is where "~70s off p50 on its own" materializes —
  flipping NOW means recovery day inherits the win pre-verified.

Scoreboard line (JUDGE):
`select percentile_cont(0.5) within group (order by (result->'stage_timings'->>'upload_export')::float) from video_jobs where status='completed' and created_at > now() - interval '1 day';`

## Post-flip verification (Lane 4 runs it, same day)

1. upload_export p50 on post-flip completions vs the 4.4s baseline.
2. **Playback check on one real delivery**: fetch the newest completed job's
   `hls_manifest_url` → assert master.m3u8 lists the single rendition → fetch
   the first segment 200 + non-trivial bytes. (Progressive-swap risk is
   currently minimal: observed dispatches carry `supports_progressive=False`.)

## Revert trigger

Any playback failure, client HLS complaint, or upload_export NOT dropping →
restate secret with `PROMPTLY_HLS_COPY=` (empty) + redeploy. One-value revert,
same 31-key procedure.
