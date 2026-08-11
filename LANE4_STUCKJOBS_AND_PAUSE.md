# LANE 4 — stuck-jobs answer (TRUTH b384e1c) + true-pause filing (2026-08-11)

## Part 1 — The PGRST204 question, answered LOUDLY

**Q (Zac/TRUTH): is the missing column failing the whole UPDATE?**
**A: NO — exonerated, with evidence — and the migration would NOT have saved
these two jobs. But it IS load-bearing for telemetry, and the real stuck-job
mechanism is uglier: a silent HANG class, now bounded + instrumented.**

Evidence chain [all MEASURED 2026-08-11]:
1. PGRST204 fires live: `[job-status] worker_started_at stamp soft-failed …
   PGRST204` in worker logs. It is an ISOLATED single-column write (by design,
   exactly so a missing column can never bounce a shared patch) — the same
   container rendered, uploaded MP4+HLS+thumbnail, and logged `JOB … COMPLETE
   157.2s` AFTER the soft-fail. Nothing else shares its patch, on either side
   (deployed-diff verified: no lane bundles the new columns into shared
   updates; JUDGE's 2 migrations create TABLES, their code JSONL-fallbacks).
2. The two stuck jobs' actual anatomy:
   - `ef093b1f`: worker completed FULLY, TWICE (original + re-spawn), video on
     CDN both times — row frozen non-terminal; run-2's progress landed 18:55:59
     but the status flip did not. Still `processing` at last read.
   - `19dd793b`: half-landed row (progress=100, current_step='complete',
     phase="Your video is ready!", status='processing', empty result) →
     terminalized **failed** by the 15-min net at 18:59:16. A user waited 15
     minutes and got a FAILURE for a completed render.
   - `36f2a3c1` (same window): callback orphaned at 18:45:40 → **my orphan
     handler repaired it** — row completed. The new instrumentation caught its
     first real fish.
3. Why the 75s poller couldn't save them: the poller settles FROM the durable
   terminal row. Here the terminal write itself is what went missing — no
   terminal, nothing to poll. Different disease than the callback-miss class.
4. The failure left ZERO error logs. A lost write that ERRORS logs
   `[job-status] write failed`. Silence + frozen `updated_at` mid-pipeline is
   the signature of a HANG: the postgrest client had NO timeout, and every
   write_job_status runs under `_JOB_STATUS_LOCK` — one wedged socket freezes
   every later durable write in the process, blocks handler-return, which
   blocks the completion POST, and the container bills to its full 1200s
   timeout. [INFERRED mechanism — bounded + instrumented regardless, below.]

Shipped on `lane/delivery` (worker) + `lane/delivery-2` (content-studio):
- **15s hard timeout on the worker's postgrest client** — a hang becomes a
  logged, fail-open error; the lock can no longer be held forever.
- **Wedge detector + terminal-write receipt**: every terminal write now logs
  `matched=N elapsed_ms result_bytes`; >5s under the lock logs SLOW. The next
  lost terminal names itself in one grep.
- **Server-side `terminal_flip_lost` event** in /api/modal-progress for both
  half-landed mechanisms (complete-step-with-bad-pct; zero-rows-on-nonterminal).
- The migration stays REQUIRED (telemetry + stops the worker-side PGRST204
  noise) but is NOT the stuck-job cure.

## Part 2 — TRUE PAUSE filing (dark-period burn → ~zero)

**Census [MEASURED 2026-08-11 ~19:10Z, simultaneous]: 9 Modal tasks vs 2
in-flight DB jobs** (one of the 2 a zombie `queued` row that never dispatched).
≈7 excess containers — the standing class memory calls "prewarm/ASGI, 6-11
tasks".

What is ALREADY at zero [CODE-verified]:
- No `min_containers`/`keep_warm` anywhere in modal_app.py (PrewarmWorker's
  was removed v60).
- Dispatcher scaledown_window=30s, pipeline 45s (minimums that still work).
- Server-side prewarm FROZEN (`PREWARM_ENABLED` unset) + the dispatcher
  `warmup()` endpoint neutered (returns immediately).
- promptly-matting: 0 tasks.

So the dark-period burn is NOT config idle. It is:
1. **The hang class above** — a stuck completion bills ~1000+s of cpu=16/12GiB
   ≈ $0.55-0.70/job doing nothing. Two hit today. The timeout fix kills this.
2. **Per-editor-open dispatcher spins** (cpu=8 × ~30s per warmup ping, iOS
   fires them at editor-open/composer-focus/dispatch). Server can't stop the
   client calling; the neutered endpoint already minimizes the container's
   work. Client-half item (owner's iOS build: stop calling warmup during the
   dark period / entirely — it buys nothing since the funnel A/B).
3. **Exit tails** (~30s/container, known ThreadPool class — separate memory).

**Burn before/after protocol (owner/TRUTH — the dashboard has what the CLI
does not):** Modal dashboard → Usage → filter app promptly-gpu-worker → by
function, note $/day for the 3 days pre-fix vs post-fix. My census command for
spot checks: `modal app list` task count vs
`video_jobs?status=in.(queued,processing)` count — excess ≈ hung/idle. The
$87/day non-job figure (Aug-3 comment) is the historical "before"; expect the
post-fix number to be dominated by real job compute only.

**Requested TRUTH actions:** deploy worker `lane/delivery` (timeout + wedge
detector + retry/lang_bundle already queued there), then the owner reads the
dashboard before/after. No flag flips required. `modal app stop promptly-matting`
optional (0 tasks — cosmetic).
