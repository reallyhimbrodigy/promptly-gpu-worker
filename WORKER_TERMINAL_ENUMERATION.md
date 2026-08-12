# WORKER TERMINAL-STATE ENUMERATION (SPEED half) — 2026-08-03

Canonical list of every terminal state the WORKER code can produce, classified
against 30 days of `video_jobs` traffic (n=1262 completed, 1828 failed, 25
canceled) and a clean last-2d cohort (excludes the 07-30/31 dispatch-404 spike).

**Source of truth:** `classify_error()` (handler.py:28495) maps exceptions →
38 codes; 2 more (`MISSING_FIELDS`, `TIER_CONCURRENCY`) are written at the entry
gate. `video_jobs` stores only the *user message*, not the code — codes below
are mapped back from the message text.

Buckets: **F+H** FIRES+HANDLED · **F+NH** FIRES+NOT-HANDLED · **NF** NEVER-FIRES
(reachable, 0/30d) · **CF** CANNOT-FIRE (no live trigger / retired path).

---

## A. SUCCESS
| state | 30d j/u | 2d | bucket |
|---|---|---|---|
| `completed` | 1262 | active | F+H |

## B. DESIGNED REJECTIONS (zero-reject-law compliant: honest message, refund where ours)
| code | 30d j/u | 2d | bucket | note |
|---|---|---|---|---|
| NO_SPEECH | 197/150 | 0 | F+H | no speech detected |
| NO_SPEECH_NONENGLISH | 47/35 | 0 | F+H | non-English (Tier-1 route candidate) |
| CLIP_TOO_SHORT | 45/42 | 3 | F+H | <2.0s — a *permitted* reject |
| NO_SPEECH_FACE | 30/28 | 0 | F+H | face present, speech unclear |
| NO_AUDIO_TRACK | 27/22 | 0 | F+H | no audio track |
| NOT_TALKING_HEAD (+compilation) | ~19/17 | 0 | F+H | not talking-head |
| CLIP_TOO_LONG | ~16/15 | 0 | F+H | >cap — a *permitted* reject (dynamic cap msg) |
| TRANSCRIPTION_INCOMPLETE | 38/27 | 0 | F+H | partial transcript coverage |
| INVALID_FORMAT | 7/6 | 1 | F+H | unreadable file |
| TIER_CONCURRENCY | 2/2 | 0 | F+H | plan concurrency (1/day) |
| WRONG_ORIENTATION | 0 | 0 | NF | reachable, 0 traffic |

## C. REAL ERRORS — ours, refunded + `_fire_render_alert` (alerting)
| code | 30d j/u | 2d | bucket | note |
|---|---|---|---|---|
| INTEGRITY_TRIP | 32/20 | 6/3u | F+H | post-render defect gate; refund+alert |
| RENDER_FATAL | 26/20 | 11/7u | F+H | render ladder exhausted |
| RENDER_REMOTION | 21/8 | 12/3u | F+H | Remotion rc=1 (3 users, ~4× retry) |
| UNKNOWN | 16/15 | **0** | F+H | catch-all; **0 recent = every recent failure IS classified** |
| RENDER_TOO_SHORT | 4/3 | 0 | F+H | output below floor |
| RECIPE_INVALID | 2/1 | 2/1u | F+H | recipe validation exhausted |
| TRANSCRIPTION | 2/2 | 0 | F+H | transcription error |

## D. DISPATCH FAILURES — SPEED-owned, surface in content-studio
| class | 30d j/u | 2d | bucket | note |
|---|---|---|---|---|
| **DISPATCH_MODAL_404** (run_job) | **1057/519** | **0** | **F+NH** | HISTORICAL spike 07-30 (776) / 07-31 (224); raw `Modal error: 404` leaked to 519 users; mechanism UNNAMED |
| **RENDER_UNAVAILABLE: Modal 404** | 64/33 | 0 | F+NH | HISTORICAL; render-service 404, raw message |
| "trouble reaching the render service" | 37/25 | **12/?** | F+NH? | **ACTIVE**; render-reach failure |
| DISPATCH_OTHER (Modal non-404) | 7/4 | 7/4u | F+NH? | **ACTIVE**; fetch got non-2xx≠404 |
| `re-dispatch aborted` (re-spawn-once) | 1/1 | 1 | F+H | the dispatch-loss guard firing |
| DISPATCH_UNREACHABLE (fetch *throws*, :731) | (subset above) | ? | ? | the genuine unowned remnant — the throw-after-retries class |

## E. PRE-DISPATCH / UPLOAD — SPEED-owned, **NEVER ALERT (invisible to Zac's phone)**
| class | 30d j/u | 2d | bucket | note |
|---|---|---|---|---|
| **"The video didn't reach us"** (UPLOAD_NEVER_STARTED / EMPTY_UPLOAD) | 28/28 | **28/28u** | **F+NH** | **BIGGEST ACTIVE class; 1 job/user; silent — fires before any render-alert** |
| **UPLOAD_STALLED** | 98/38 | **51/21u** | **F+NH** | ACTIVE; silent; 2.4× retry per user |
| MISSING_FIELDS | 0 | 0 | NF | entry-gate validation |
| UPLOAD_TIMEOUT | 0 | 0 | NF | reachable, 0 traffic |

## F. NEVER-FIRES in 30d (defined + reachable via raise or substring match; 0 traffic)
CONTAINER_TEARDOWN · EDITOR_GENERIC · EMPTY_UPLOAD · INVALID_SOURCE_URL ·
NETWORK · PLATFORM_TIMEOUT (catchable branch; the reaper writes it server-side) ·
RATE_LIMIT · RENDER_FFMPEG · S3_ACCESS · S3_GENERIC · SAFE_EDIT_FAILED ·
EDITOR_TIMEOUT · TRANSCRIPTION_EMPTY

## G. CANNOT-FIRE candidates (0 traffic + no live explicit trigger; likely retired) — NEEDS per-code raise-site audit to confirm
BROLL (b-roll is non-fatal now) · EMPTY_EDIT · EDITOR_PARSE · PLAN_INVALID ·
PLAN_VALIDATION — these share user-messages with live codes and/or have no
trigger outside `classify_error`; each needs its raise site confirmed dead.

---

## SPEED ACTION ITEMS (from this enumeration)
1. **DISPATCH_MODAL_404 (1057/519u)** — biggest 30d class, HISTORICAL (0/2d) but
   mechanism UNNAMED and it leaked a raw `Modal error: 404` to users (F+NH).
   Owe: name why the run_job endpoint 404'd on 07-30/31 + a gate so it can't recur
   silently, + a friendly classified message for any dispatch non-2xx.
2. **Pre-dispatch upload failures (video-didn't-reach-us 28u + UPLOAD_STALLED 21u,
   both active, both SILENT)** — the never-alerting class. Owe: an alert leg for
   pre-dispatch terminal failures so they stop being invisible to Zac's phone.
3. **DISPATCH_UNREACHABLE** — isolate the fetch-throws subset (:731) from the
   non-2xx subset (:741); confirm which is currently active.
4. **CANNOT-FIRE audit (bucket G)** — confirm the 5 retired-path codes are dead
   and either delete or document them, so the taxonomy has no phantom entries.

## HAND-OFFS
- **ERRORS** owns the content-studio half (the reconciler, double-loss, the
  server-side reaper that writes PLATFORM_TIMEOUT). Worker finding for the
  double-loss race: `run_pipeline_bg` POSTs to /api/modal-complete WITHOUT
  checking the response status (modal_app.py:826) — a 401/403/late response logs
  `completion POSTed` regardless, so the worker cannot tell "delivered" from
  "rejected." That is the timing signal the callback-vs-sweep question needs.
- **SECURITY**: iOS calls the worker DIRECTLY on `validate` + `warmup`
  (APIService.swift:145,305); `prewarm` + main dispatch are server-routed.
