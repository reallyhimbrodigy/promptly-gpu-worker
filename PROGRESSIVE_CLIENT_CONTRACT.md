# PROGRESSIVE DELIVERY — TWO-SIDED CONTRACT (client · server · worker)
Traced from live code 2026-07-26 during the "no preview on device" debug. Backend + frontend read this.

## THE FOUR SEAMS (a job flows through all four; break any one → no preview)
```
(a) CLIENT  ──supports_progressive:true──▶ (b) SERVER ──supports_progressive──▶ (c) WORKER ──preview+hls_manifest──▶ (d) CLIENT
    219 app, per dispatch                     content-studio                      promptly-gpu-worker                   219 app reads
```

### (a) CLIENT → SERVER  [frontend owns]
The 219 app POSTs the dispatch body with **`supports_progressive: true`** (a strict boolean `true`).
Commit 309cc9c "send supports_progressive capability per dispatch (flip sequencing)". **VERIFY:** the
client actually sets this to boolean `true` on the dispatch request (not a string, not omitted, not gated
off by a local capability handshake). The server check is `=== true` (strict) — anything else = no preview.

### (b) SERVER → WORKER  [content-studio, origin/main — CONFIRMED wired]
- `server.js:4130`: `supportsProgressive = body?.supports_progressive === true && progressivePlaybackEnabled()`
- `progressivePlaybackEnabled()` = `PROGRESSIVE_PLAYBACK_ENABLED` env (Render), accepts `1|true|yes|on`.
- `dispatch-to-modal.js:577`: payload `supports_progressive: !!supportsProgressive` — TOP LEVEL of the
  Modal payload (alongside `public_url`, `vibe`, `user_id`).
- So the worker gets `supports_progressive:true` IFF (client sent `true`) AND (flag on). Either false → false.

### (c) WORKER  [promptly-gpu-worker, v368+ — CONFIRMED wired]
- `run_job(body)` → (SPAWN_MODE) `run_pipeline_bg.spawn(body)` → `handler({"input": body})` →
  `input_data = body`, so `input_data.get("supports_progressive")` reads the top-level payload field. ✓
- `_progressive_enabled(input_data)`: returns True if `supports_progressive` truthy (or `progressive_test`),
  UNLESS `PROMPTLY_PROGRESSIVE=0` (backend kill switch). Default: per-job capability drives it.
- When enabled + the render is multi-composite-chunk, the publisher publishes preview chunks to
  `{base}-preview-hls/` and persists the payload to `video_jobs.preview` from segment 1.
- **SEAM-TRACE (new, v369): every job logs `[progressive] GATE job=<id> supports_progressive=<v> -> enabled=<b>`
  AND records a `progressive`/`progressive_gate` divergence** — queryable per job to prove (b)→(c).

### (d) WORKER → CLIENT  [the fields the client reads]
- **`video_jobs.hls_manifest_url`** is written EARLY with the PREVIEW manifest once a chunk is playable
  (`segments_published >= 1`, not final/superseded); the terminal completion write OVERWRITES it with the
  FINAL manifest. So a client polling `hls_manifest_url` gets the preview first, then the final.
- **`video_jobs.preview`** (jsonb) carries the richer payload: `{preview_hls_url, segments_published,
  plan_summary, first_frame_url, final, superseded}`. `final:true`/`superseded:true` = swap to the final.
- Preview prefix `-preview-hls/` is ALWAYS distinct from final `-hls/`. Preview EVENT playlist has no
  ENDLIST until finalized. A/V skew ≤56ms per segment. Final is byte-equivalent to a non-progressive
  render within the render's own run-to-run noise (publisher never re-renders, no write path to the final).

## DEBUGGING A "NO PREVIEW" JOB (use the seam trace)
1. Query `video_jobs` for the job: `preview` object-shaped? `hls_manifest_url` a `-preview-hls/` URL early?
   If `preview` is `false`/null and hls is only the final → the worker never published → go to step 2.
2. Grep the worker's `[progressive] GATE job=<id>` log, or query the `progressive_gate` divergence:
   - `supports_progressive=false/None` → break is UPSTREAM (a client didn't send `true`, or b flag off).
     The server+worker are correct; fix is client-side or the Render flag.
   - `supports_progressive=true, enabled=true` but no preview published → the render was single-chunk
     (publisher inert — short/minimal jobs have no composite chunks) OR the publisher tripped its loud
     fallback (check `progressive_publish_fallback` divergence). Not a contract break.
3. If the worker got `true` and published but the client showed nothing → seam (d): confirm the client
   reads `hls_manifest_url` (early) or `preview.preview_hls_url` — the worker writes BOTH.

## CURRENT KNOWN STATE (device test job c24ab2b6, 2026-07-26 21:35Z)
`preview=false`, `hls_manifest_url=final only` → the worker NEVER PUBLISHED a preview on a 371s TH
(multi-chunk) render → it received `supports_progressive` falsy. Server (3458d86) + worker (v368) were
BOTH deployed before the job (3458d86 @20:51Z, v368 @21:10Z, job @21:35Z). So seams b/c are wired; the
break is (a)/flag. The v369 seam trace will show the exact received value on the next test.

## FLIP STATE
- `PROMPTLY_PROGRESSIVE` (worker) = UNSET (kill switch inactive) → per-job `supports_progressive` gating.
- `PROGRESSIVE_PLAYBACK_ENABLED` (Render) = set by Zac → server forwards when client sends true.
- Both halves deployed. The remaining unknown is seam (a): does the 219 client send `supports_progressive:true`?
