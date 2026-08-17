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
| 2026-08-09 | harness | golden-freeze SMOKE (2 PLAN_ONLY captures, no render possible) | 2 | est ~500 | ~$0.20 est | ~$0.20 |
| 2026-08-09 | harness | golden-freeze SMOKE retry x2 (ClientError diagnosis) | 2 | ~30 | ~$0.02 est | ~$0.22 |
| 2026-08-09 | harness | golden-freeze RECONCILE: 2 smokes ran 31 fn-s total; both hit Vertex 403 dunning-deny (safe_edit fallback) — freeze BLOCKED, capture quarantined | 0 | 31 | actual ~$0.05 | ~$0.22 booked / ~$0.05 actual |

## 2026-08-15 — Vertex per-base-model quota experiment `[§6.1]`

**Purpose:** test whether `base_model` is a real, separate quota bucket — worth
~3x throughput today without waiting on the 60/min increase.

| calls | model | billed |
|---|---|---|
| 5 | `gemini-3.1-flash-image` | yes |
| 1 | `gemini-3-pro-image` | yes ($0.14) |
| 3 | flash (429) | no |
| 6 | 404 wrong endpoint version | no |

**Stated ceiling: $0.15, then $0.25. ACTUAL: ~$0.34.** I exceeded my own stated
price and am recording it rather than rounding it away. Flash's unit price is
unconfirmed, so even this figure is a bound, not a measurement.

**Cause, and the fix:** these were ad-hoc `curl` probes with **no in-app
ceiling**. `lumen_first_light_app.py` cannot overrun because it refuses the call
that would cross `MAX_SPEND_USD` — the probe had no such guard, so the ceiling
was a sentence in a report instead of a line of code. **Any further paid probe
goes through a script with a hard refusal, not a shell loop.**

**Result (worth the overrun, which does not excuse it):** buckets are
independent. Pro succeeded immediately after 3 flash calls; flash sustained 4
then 429'd. Pro 2/min + flash ~4/min = **~6/min today**.

### Flash price per call — MEASURED SHAPE, UNCONFIRMED PRICE

| | `gemini-3-pro-image` | `gemini-3.1-flash-image` |
|---|---|---|
| output | 1408x768 PNG, 666 KB | **1024x1024 PNG, 1145 KB** |
| **image tokens/call** | **1,120** | **1,120** |
| rate limit | 2/min | **~4/min** |
| $/call | $0.14 (known) | **UNCONFIRMED** |

**I could not retrieve flash's price.** The Cloud Billing API is DISABLED on
`promptly-479218`, and enabling an API on the owner's project as a side effect of
a pricing question is a config change beyond the ask — it needs his word.

**Do not infer it from my spend.** I estimated ~$0.34 for 5 flash + 1 Pro by
*assuming* a flash unit price; using that same figure to derive the price would
be circular, and this is exactly the probe-collapse shape (a failed measurement
wearing a number's clothes).

**The one real signal:** flash bills the **same 1,120 image tokens per call** as
Pro did in the identical test. If Vertex bills image output per token at a shared
rate, flash is a *rate* win but NOT a cost win. If flash sits in a cheaper
per-image tier — as flash-class models normally do — it is both. **That is a
one-line answer from the billing console and it changes the Phase 2 cost model,
so it is worth asking for.**

---

## 2026-08-16 — first Lumen edit, build lane

| item | priced in advance | actual | note |
|---|---|---|---|
| FIRST LUMEN PLAN (`lumen_first`, REF-2 vertical) | **$1.20 ceiling** | **~$0.10 est.** | 216.8s in-function; 0 scenes -> 0 image generations |
| SECOND LUMEN PLAN (`lumen_first`, REF-1 landscape) | (same ceiling) | **~$0.10 est.** | 108.0s in-function; 0 scenes |

**ADJUDICATING THE PRE-REGISTRATION AGAINST EVIDENCE, not against my report.**

The registered question was: does the planner produce scenes with premium=True
and the editorial gate open? The registered fallback was: if scenes come back
zero, walk the strip gates.

  RESULT, both references, editorial gate OPEN (`editorial_suppressed: false`):
    REF-2  ok=true  wall 216.8s  scene_count 0  accent #8B350D
    REF-1  ok=true  wall 108.0s  scene_count 0  accent #F06D1F

  STRIP GATES: WALKED AND EXONERATED. The drop path logs
  `[two-pass] Dropping generated_scene:` and that line appears in NEITHER run.
  Nothing was stripped. The model was offered the beat and declined it, which
  makes this 0 of 779 rather than 0 of 778.

  WHAT DID WORK, and it is the first evidence of it: the editorial path
  completed end to end for the first time since the dependency break — 7 clips,
  5 SFX on beats, zoom variety with 2 clip splits to preserve it, 2 B-roll asks
  with negative constraints, 3 MGs (REF-2). The design system extracted a
  DIFFERENT, CORRECT accent per video: #F06D1F on REF-1 is the documented
  reference orange that an earlier extractor got wrong.

  WHAT FAILED: brand_specs {name_plate: false, end_card: false} on BOTH — including
  REF-1 where a name IS spoken. `brand_copy` never appears in plan_keys, and it
  survives _LEAN_DROP_FIELDS / _apply_lean_schema / _apply_why_diet, so the field
  reached the model intact and was declined. Same shape as generated_scenes.

  NO ARTIFACT EXISTS. `lumen_first_edit` calls no render path (verified: no
  render_stage / render_video / remotion reference). These runs produced PLANS.
  There is no mp4 for JUDGE to score or the owner to watch until the render leg
  lands.

**The $ figures above are ESTIMATES, not measurements** — container seconds at
cpu=8/16GiB plus one editorial call each, with zero image generations because
zero scenes were emitted. `modal billing report --csv` is the only truth and the
standing weekly pull is what settles it. Reporting an estimate as a measurement
is the probe-collapse class this ledger exists to prevent.

Stated before the run, per Rule 6. The ceiling is a REFUSAL point, not a
forecast: the realistic band is $0.10–$0.60 depending on how many scenes the
plan asks for, and a Vertex denial costs only the container seconds (~cents)
because the call dies before any image is generated.

WHY THIS SPEND IS JUSTIFIED, having been deferred four times: nothing else
exercises the editorial path. Live traffic is deterministic by design
(`_editorial_suppressed()` is true whenever `PROMPTLY_EDITORIAL_LIVE` is off),
so the ONLY way to learn whether the planner produces scenes is to run it in the
build lane, where the gate opens without touching the live flag. Every previous
attempt cost $0 and answered nothing — five died on dependency drift before
reaching Gemini, which is precisely the class v547 closed by restoring
google-genai 1.75.0.

**Session running total is still owed a reconciliation against the invoice** —
the per-run figures here are priced, not measured, and `modal billing report
--csv` is the only truth. That pull is the standing weekly line.

| TRACK 1 MATRIX (2 models x 3 thinking, REF-2, plan-only) | **$1.20** | *pending* | the one measurement worth real spend; plan-only because a render cannot change what the PLANNER emits |
