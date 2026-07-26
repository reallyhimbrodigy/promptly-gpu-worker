# PROGRESSIVE DELIVERY CONTRACT — moved (2026-07-26)

This doc was consolidated to avoid two-contracts-drift (the exact failure a contract
exists to prevent). The **canonical, cross-repo contract** now lives in content-studio:

> **content-studio/docs/PROGRESSIVE_PLAYBACK_CONTRACT.md**

It covers all six seams (client → server → worker → DB → server → client), all three kill
switches (`PROGRESSIVE_PLAYBACK_ENABLED`, `PROMPTLY_PROGRESSIVE`, `PROMPTLY_PREVIEW_PERSIST`),
the safety invariants, and — the lesson this bug taught — the **column TYPES**, not just
field names (`video_jobs.preview` is JSONB; the 2026-07-26 outage was it created BOOLEAN, so
the worker's JSONB write threw and took `hls_manifest_url` down with it in the same UPDATE).

Worker-side quick reference (authoritative details in the canonical doc):
- Gate: `_progressive_enabled(input_data)` → publishes iff `input_data.supports_progressive`
  truthy (or `progressive_test`), unless `PROMPTLY_PROGRESSIVE` kill switch is off.
- Emit: `_persist_preview` writes `video_jobs.preview` (JSONB) + early `hls_manifest_url`
  (preview manifest) once ≥1 chunk playable; terminal completion write overwrites with final.
- Observability (v369): every job logs `[progressive] GATE job=<id> supports_progressive=<v>
  -> enabled=<b>` and records a `progressive`/`progressive_gate` divergence (queryable).
