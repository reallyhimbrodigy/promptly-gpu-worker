# PROGRESSIVE DELIVERY — CLIENT PLAYBACK CONTRACT (for the 219 frontend agent)
Status: backend APPROVED (Zac watched the swap artifacts, no pop objection, 2026-07-26).
Server cert 3/3 (safety: final byte-equivalent within render noise; publisher reads render
intermediates only, no write path to the final; partial-never-final; A/V ≤56ms; completeness;
prefix). **The flip is COORDINATED: publisher + client go live TOGETHER, never publisher alone**
(a preview no client reads is pure per-job compute for zero benefit). Nothing flips without Zac's word.

## ⚠️ PREREQUISITE #1 — the `video_jobs.preview` column migration (BLOCKER)
The worker persists the preview payload to `video_jobs.preview` (jsonb). That column does NOT exist
yet — the certs show `PGRST204 Could not find the 'preview' column` (now correctly ledgered as an
absent_column_defect). **The client has nothing to read until this column is added.** Required SQL:
```sql
ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS preview jsonb;
```
This must land before the flip. (This is the same class as the demo/post_package migrations.)

## THE DATA CONTRACT — `video_jobs.preview` (jsonb)
Written by the worker during the render (daemon-threaded, fail-open, terminal-fenced except the
stamped terminal payloads). Shape:
```json
{
  "preview_hls_url": "https://<cdn>/<base>-preview-hls/master.m3u8",  // EVENT playlist, GROWS
  "segments_published": 3,               // published chunk-group count so far
  "plan_summary": { "route": "talking_head", "clip_count": 11, "caption_style": "Cove",
                    "broll_count": 4, "edit_rationale": "..." },      // for a loading affordance
  "first_frame_url": "https://<cdn>/<base>-preview-hls/first_frame.jpg", // poster, Phase B
  "final": false,        // true ONCE the preview reached ENDLIST (finalized)
  "superseded": false    // true if the render finished first and the preview was cancelled
}
```
- `final` / `superseded` are the TERMINAL STAMPS — either one means the final artifact is authoritative
  and the client MUST swap to it. Only these stamped payloads are written at/after terminal status;
  in-flight chunk payloads are fenced off before terminal.

## THE FINAL ARTIFACT (unchanged, already live)
On completion, the job's terminal result already carries the FINAL delivery:
- `result.hls_manifest_url` → `https://<cdn>/<base>-hls/master.m3u8` (the fMP4 ladder, distinct
  `-hls/` prefix — NEVER `-preview-hls/`)
- `result.video_url` → the progressive-download MP4
The final ALWAYS replaces the preview. The preview is never a terminal state.

## CLIENT PLAYBACK FLOW
1. **Job dispatched** → poll (or realtime-subscribe to) `video_jobs` for this job.
2. **Preview appears** (`preview.preview_hls_url` non-null): show `first_frame_url` as a poster
   immediately, then begin playing `preview_hls_url`. It is an **EVENT-type HLS playlist that GROWS**
   as chunks publish — treat it as a live stream. It will NOT contain `#EXT-X-ENDLIST` until the whole
   preview is finalized (partial-never-final is cert-guaranteed, so a growing manifest is always
   safe to start).
3. **Final ready** — swap to `result.hls_manifest_url` when ANY of:
   - `status == "completed"` and `result.hls_manifest_url` present (the normal path), OR
   - `preview.final == true` (preview finalized — final ladder is up), OR
   - `preview.superseded == true` (render finished first; preview cancelled; final is authoritative).
   The swap = load the `-hls/` master and seek to the current playback position. Preview→final SSIM
   measured 0.976–0.986, so expect a subtle sharpening, no structural jump (Zac approved the look).
4. **No preview** (short/single-chunk jobs, or progressive OFF): fall back to today's behavior —
   wait for `status==completed` then play `result.hls_manifest_url`. Progressive is TH-only and
   only engages for multi-composite-chunk renders; single-chunk jobs go inert (no preview).

## SEMANTICS THE CLIENT CAN RELY ON (cert-guaranteed)
- Preview prefix `-preview-hls/` is ALWAYS distinct from the final `-hls/`.
- The preview EVENT playlist starts at media-sequence 0 and only grows; ENDLIST appears only when ALL
  chunks are present.
- Every published preview segment has A/V start+end skew ≤ 56ms.
- The final artifact is byte-equivalent to a non-progressive render within the render's own run-to-run
  noise (the publisher never re-renders and has no write path to the final).

## THE COORDINATED FLIP
Backend flip = set `PROMPTLY_PROGRESSIVE=1` (currently env-only dark; the flip promotes it to the
canonical secret + gate). The worker machinery is deployed and cert-passed. **Do not flip the backend
until: (a) the `preview` column migration has landed, and (b) the 219 client can consume this contract.**
When both sides confirm ready, Zac flips on one word. First real iOS-recording confirmation happens
during the 219 TestFlight pass (Zac's approval so far is on the server-side swap artifacts).
