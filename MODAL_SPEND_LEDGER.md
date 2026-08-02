# MODAL SPEND LEDGER — one file, every agent appends (RULE 8, Zac 2026-08-01)

Forged from the $140/day spike: **each agent priced its own runs and nobody
summed across agents.** That gap is what this file closes.

## The rule

1. **Before** firing any Modal work, append a line stating the cost of that run
   **and the running cross-agent total for the session.**
2. **No agent spends past $5/session without Zac saying so explicitly.**
3. A local stop proves nothing — `.spawn()`ed containers outlive the local
   orchestrator. After any batch, verify `modal app list` shows **0 tasks** for
   every app you created, and stop it with `modal app stop <id>` if not.
4. Harnesses count exactly like user jobs. A cert, a plan-only run, a single
   cheap read — all of it lands here.

## Format

`| date | agent | app | runs | container-s | $ this run | $ session total |`

## Ledger

| date | agent | app | runs | container-s | $ this run | $ session total |
|---|---|---|---|---|---|---|
| 2026-08-01 | smoothness | *(none — all compute local)* | 0 | 0 | $0.00 | $0.00 |
| 2026-08-01 | smoothness | *(freeze-lifted batteries: NOT NEEDED)* | 0 | 0 | $0.00 | $0.00 |
| 2026-08-02 | smoothness | *(SmoothPush pair — local)* | 0 | 0 | $0.00 | $0.00 |

## Session notes

**smoothness, 2026-08-01 — $0.00. Zero Modal work fired, zero apps created.**
Every measurement this session ran on the laptop: 89 local Remotion renders (3
velocity-cap A/B rounds + 3 MG attack batteries × 26 components), local ffmpeg
frame-diff/PSNR/MAD passes, one **free** Supabase read of stored plans, and an
`npm ci`. Verified after the freeze: `modal app list` shows 29 of 30 apps at 0
tasks; the single app with running tasks is `promptly-gpu-worker` (deployed
production, draining real user jobs — not a harness, not mine).

**Freeze-lifted allowance UNUSED.** Zac cleared two local batteries (Reticle +
the StepDivider 3.10 anomaly). Neither was run: both resolved by RE-ANALYSING
renders already on disk. StepDivider's 3.10 was an artifact of my own audit
(steady sampled at 400-700ms, inside a long staged entrance — 0.198 there vs
2.362 settled, a 12x error); against true travel it is 0.24, marginal. Reticle's
0.67 was the same artifact plus a peak that sits at 333ms = the designed LOCK
accent, not the entrance; corrected it reads 0.25 -> 0.20. No component change
was warranted for either, and no render was fired to learn that.

**`cert-cap-rendertime` is NOT mine**, despite the "cap" in the name resembling
the zoom velocity cap. I invoked no `modal` command this session other than the
read-only `modal app list` above. It shows `stopped / 0 tasks`.
