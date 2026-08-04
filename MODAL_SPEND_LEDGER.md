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
| 2026-08-02 | smoothness | *(MG attack re-measure, both arms — local)* | 0 | 0 | $0.00 | $0.00 |
| 2026-08-03 | quality | **promptly-gpu-worker DEPLOY** (image rebuild) | 1 | ~309s build | ~$0.10 est | ~$0.10 |
| 2026-08-02 | smoothness | *(SafeImg + crossfade degrade proofs — local)* | 0 | 0 | $0.00 | $0.00 |
| 2026-08-02 | smoothness | *(MG frame-draw profile, 6 renders — local)* | 0 | 0 | $0.00 | $0.00 |

## Session notes

**quality (was smoothness), 2026-08-03 — FIRST DEPLOY.** `./deploy.sh` →
`fe15996` live, 309s image rebuild (src/remotion changed, so the prebundle step
reran and the Remotion changes actually shipped). Build compute only, no renders.
Estimated ~$0.10; Modal bills the build, so it is logged rather than assumed free.
The first attempt FAILED before deploying — `models/rife-v4.18/` is gitignored and
absent from this worktree — so there was no partial-deploy state. Copied 22MB of
model assets from the main worktree and redeployed.

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

## ITEMISED — quality agent, 2026-08-03/04

**RENDERS FIRED ON MODAL: ZERO.** Every Modal charge below is an image build
from `./deploy.sh`. No job, no cert, no A/B ran on Modal all session.

| # | commit | build | what the deploy bought |
|---|---|---|---|
| 1 | `fe15996` | **309s** (full rebuild — `src/remotion` changed, so prebundle reran) | SafeImg `<Img>` hang fix + all 15 tag sites + entrance/zoom caps + transition pre-extract + RENDERCLOCK + six-MG discrimination |
| 2 | `bbff11a` | 61s (Python only) | removed the two FALSE taste signals (`pacing`/`color_effect`) from every returning user's prompt |
| 3 | `2e65292` | 65s (Python only) | export-weighted style profile — taste from videos users KEPT |
| 4 | `8360a93` | ~60s (Python only) | the mid-word fix: 37% of Hindi jobs were ending mid-word |
| 5 | `6b3ece7` | ~60s (Python only) | clamp that snap to the source duration |

**~560s of build compute, 5 deploys, 0 renders.** I have been quoting ~$0.10 per
deploy as an ESTIMATE and I do not have Modal's build pricing to hand — so the
honest statement is *5 builds totalling ~9 minutes*, not a dollar figure I made
up. The per-app breakdown is on Modal and is the speed agent's to read.

### What was verified FREE (the default, per Zac 2026-08-04)

- 37% mid-word rate — DB query + pure function over word timings
- the overlap bug in my own fix — pure function replayed over 73 real jobs
- language split (hi 34.0% vs en 7.7%, z=4.81) — DB query
- Spanish edges-not-dropout correction — DB query
- export rate by route and by vibe cluster — DB join
- `_lang_bundle` inert (0/3000 rows) — DB query
- degen spirals, re-roll success, the +144s edit_plan gap — DB query
- rendered-vs-plan duration equality — `ffprobe` on the CDN URL, no render
- 89 Remotion renders for the velocity-cap / SafeImg / crossfade proofs — **all
  on the laptop, zero Modal**

Nothing this session needed pixels that were not already sitting in a delivered
video I could download.
