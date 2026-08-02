# Modal spend ledger — SHARED, cross-agent (Rule 8, Zac 2026-08-02)

**$140 in a day happened because each agent priced only its own runs and nobody
summed across agents.** This file is the sum. Every agent appends before firing.

## The rule

1. Before any Modal work: append a line here stating the **cost of that run** AND
   the **running session total across all agents** (read the total off this file).
2. **No agent spends past $5/session without Zac saying so explicitly.**
3. After any batch: verify `modal app list` shows **0 tasks** for every app you
   created. A local stop proves nothing — `.spawn()`ed containers outlive the
   orchestrator. Kill with `modal app stop <app-id>`.
4. Agent test spend and user-job spend go in the **same** ledger.

## What counts

| counts as spend | does NOT count |
|---|---|
| `modal run` / `.remote()` / `.spawn()` | `modal app list` / `history` / `logs` (read-only CLI) |
| renders, A/Bs, certs, batteries, PLAN_ONLY runs | Supabase REST queries from a local shell |
| any app you create, incl. `query-*` harnesses | third-party HTTP APIs (log the $ separately) |
| a warm/idle container held by `min_containers` | local ffmpeg / ffprobe / pytest |

## Session ledger — 2026-08-02

| time (PDT) | agent | what | Modal $ | non-Modal $ | running total |
|---|---|---|---|---|---|
| 20:30–23:30 | errors | RENDER_FATAL forensics, dispatch/event fixes, coverage gate — **all local**: Supabase REST over urllib, local pytest, read-only `modal app list/history/logs` | **$0.00** | — | $0.00 |
| 23:00–23:25 | errors | ASR bake-off, 7 engines attempted / 3 completed × 40 clips (33.2 min audio). Local venv + vendor HTTP APIs, **no Modal container** | **$0.00** | $0.56 | $0.00 |
| (pre-freeze, ~08-01 10:00→08-02 00:00) | speed | render_burst canaries ×5 (@12/30/73s), LEAN/DWELL PLAN_ONLY A/B ×64 (Zac-auth "~$4–6"), x264 thread-pin bench ×12, reads ×8, deploys ×11 (~100s each). ~13,000 compute + ~1,100 build container-s | **~$12–18** | — | ~$12–18 |
| 00:04 | speed | worker deploy **v421** (66c1a91: TRANSCRIPTION_EMPTY + prompt −90 tok) — cached build 15.3s | **~$0.02** | — | ~$12–18 |
| 00:1X (PRE-PRICED) | speed | inc2 render_burst **canary** @~50s: orchestrator cpu16/64Gi ~450s + burst sub cpu48/64Gi ~120s + 1 Gemini plan. Proves byte-identity (x264 pin now live) + net-faster before the flip | **~$0.35** | — | ~$12.4–18.4 |

**errors agent Modal session total: $0.00 — 0 renders fired, 0 container-seconds,
0 apps created.**

**speed agent Modal session total: ~$12–18 (pre-freeze, estimate; exact = Modal
dashboard) + ~$0.37 post-freeze (v421 deploy + inc2 canary, Zac-authorised inc2
lift). SPEND_LEDGER.md folded into this file 2026-08-02 (was a duplicate).**

## Open at freeze time (2026-08-02 23:30 PDT)

- `promptly-gpu-worker` (`ap-ApXFiiDkhiRQDQ33Idzw3v`) — **3–4 tasks running.
  These are REAL USER RENDERS** (job `d338a296` observed mid-pipeline). Do **not**
  `modal app stop` this app; that kills paying users' jobs. Freezing agent spend
  is not the same as stopping production.
- Every other app in `modal app list` shows **0 tasks**, including
  `cert-dwell-pair` and `cert-cap-rendertime` (both `stopped`).
- Idle-cost check (`min_containers` / `keep_warm`) is the **speed** agent's item.
