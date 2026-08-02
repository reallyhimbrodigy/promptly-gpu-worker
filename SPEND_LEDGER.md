# Modal Spend Ledger (Rule 8 — SHARED BUDGET, Zac 2026-08-02)

**Rule 8:** Before ANY agent fires Modal work it states the cost AND the running
cross-agent session total here. No agent spends past **$5/session** without Zac's
explicit OK. One ledger, appended by every agent. `.spawn()` survives a local
stop — verify `modal app list` = 0 tasks after any batch.

Idle infra note: no deployed app carries `min_containers`/`keep_warm` (all scale
to zero) — idle apps do NOT bill; spend is active runs only.

Format: `YYYY-MM-DD HH:MMZ | agent | run | est$ | running-session-total$`

## Session 2026-08-01 → 08-02

### speed agent — self-reported total (estimate; exact = Modal dashboard)
- **Full renders fired: ~18** (15 render_burst canary render_stage runs across 5
  canaries @12/30/73s + ~3 CAP/DWELL renders, some stopped mid-run at the freeze)
- **Plan-only (Gemini) runs: 64** (LEAN/DWELL plan A/B — Zac-authorized "~$4-6")
- **Encode-only benchmarks: 12** (x264 thread-pin bench, cpu16 + cpu48)
- **Reads/queries: ~8** (raw-rows, REST probe, config readback, gemini_call
  historical, stage decompose)
- **Deploys: ~11** (build infra, ~100s each)
- **Container-seconds: ~13,000s compute + ~1,100s build**
- **ESTIMATED $: ~$12–18** (LEAN A/B ~$5 dominant; renders ~$4–8; deploys/reads
  ~$2) — uncertain; needs the Modal per-app dashboard to confirm.
- **FROZEN 2026-08-02: all speed apps at 0 tasks (verified).**

<!-- other agents: append your total below, keep the running cross-agent sum -->
