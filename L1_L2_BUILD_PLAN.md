# L1 / L2 — the buildable form, and the protocol `[Law 1]`

**Invoice denominator (last 3 days, current config): $35.88/day.**
CPU 72.5% / Memory 27.5%. One deployed app. GPU ~$0. Ephemeral ~$0.01/day.
Dashboard split: **orchestration 72.3%, rendering 9.6%.**

---

## 0 — THE CONSTRAINT THAT RESHAPES BOTH LEVERS

**Modal resources are decoration-time only.** `@app.function(cpu=, memory=)`
accepts them; `Function.remote()` takes only `args/kwargs`. A container's cpu and
memory are fixed for its entire life.

**So "drop the orchestrator to cpu=4 while it waits" is not a config change. It
is a function split.** Both levers are architecture, and pricing them as knobs
was wrong.

This is the same move the render burst already made: the heavy leg moved to its
own function so the light leg stopped paying for cores it wasn't using.

## 1 — L1: SPLIT THE WAITING LEGS OFF THE cpu=16 ORCHESTRATOR

**The waste.** The orchestrator is cpu=16/12 GiB for its whole life, and render
is only **18% of wall**. The other 82% is Deepgram, Gemini, S3 and network wait —
16 cores held to keep a socket open.

**And it gets worse exactly when Lumen lands:** 70s of scene generation is pure
network wait = **70 × 16 = 1,120 core-seconds of idle hold per Lumen render**,
which is why this ships *before* Phase 2 scales, not after.

**Buildable form:**

```
today   run_pipeline_bg(cpu=16, 12GiB)  ── holds 16 cores for the WHOLE job
                                             incl. every network wait

after   plan_leg(cpu=2, 4GiB)     ← transcribe + editorial + scene generation
                                    (network-bound; 2 cores is generous)
        render_leg(cpu=16, 12GiB) ← the CPU-bound remainder, unchanged
```

The plan leg returns a plan; the render leg consumes it. No shared mutable state,
which is what makes the split safe.

### THE HANDOFF, PRICED — net, not gross

My earlier "~$558/mo" was **gross** and it was wrong to quote. The split adds a
**second cold start** (~11s at cpu=16, documented in-body handler import):

```
saving per second of network wait moved 16 → 2 cores   $0.0002012
handoff cost (11s second cold start at cpu=16)         $0.00260 / job
──────────────────────────────────────────────────────────────────
BREAK-EVEN: the wait leg must exceed 12.9s or the split LOSES money
```

| wait leg | net |
|---|---|
| **6.4s** — today's unaccounted slice | **−$7/mo (NEGATIVE)** |
| 12.9s | break-even |
| 25s | +$14/mo |
| **Lumen, +70s of scene generation** | **+$72/mo** |

**So L1 is net-negative at today's job profile and earns its keep almost entirely
from Lumen.** That is the opposite of how I first sold it, and it is the whole
reason for pricing net.

### AND THE DENOMINATOR DOES NOT CLOSE

Orchestration is **$25.94/day** by invoice. My per-job model — 188 jobs × ~30s
wall at cpu=16/12 GiB — is **$1.33/day**, i.e. it explains **5.1%**. The
orchestrator is billed roughly **19× longer than its jobs run**.

So every net figure above rests on a denominator covering a twentieth of the
spend. **L1 is not committed until orchestrator container-seconds are measured**
— the same discipline being applied to L2. The break-even (12.9s) is the one
number here that is denominator-independent: it falls out of the rate card alone.

## 2 — L2: STOP HOLDING THE ORCHESTRATOR THROUGH THE BURST

`handler.py` blocks on `_fn.remote(_payload)`. For that entire call **two
reservations are live for one piece of work**: orchestrator cpu=16 idle, burst
cpu=32 working.

**The invoice says that call is ~335s/job, against a reported render p50 of
4.5–9.5s.** The gap is dispatch, payload upload, queueing and cold start — all
billed at 48 cores and invisible in `stage_timings`.

**This is inferred from the invoice and is NOT yet observed.** The
`burst_double_hold` instrument (shipping this deploy) measures it directly, per
job, in core-seconds. **L2 does not get built until that number is real** — an
architecture change sized off a ratio is exactly the Aug-4 mistake.

**Buildable form (harder, and second):** the orchestrator must *exit* rather than
await, with the burst owning the terminal write. That collides with the
`.spawn()`-orphan class this project has already paid for, so it needs its own
design pass.

## 3 — THE PRE-REGISTERED PROTOCOL

*The Aug-4 revert is the anti-template: the prewarm window was cut 600→30 to free
a ceiling that was never binding (7/100 utilisation); it "bought nothing and cost
~20s latency."* It optimised an unmeasured constraint and paid in the number
users feel.

**Registered BEFORE any change ships:**

| | L1 |
|---|---|
| **primary read** | `promptly-gpu-worker` CPU $/day, 7-day mean, from `modal billing report` |
| **expected direction** | **down**; a move of **<$5/day is a NULL result** and L1 is reverted, not tuned |
| **guard read 1** | job wall p50/p90 **by route** — must not rise >10% |
| **guard read 2** | queue delay p50 / %>60s — must not rise at all |
| **guard read 3** | completion rate by route — must not fall (the cpu 8 cut once crashed it 78.9%→35.7%) |
| **clean cohort** | ≥3 full days each side, no deploy boundary inside, no outage hour, cut by route |
| **revert trigger** | any guard breached → revert same day, no tuning in-window |
| **denominator** | stated before the read: jobs/day per route on both sides |

**The cpu=8 precedent is the specific danger.** Cutting cores once crashed
completion 78.9% → 35.7% because a 480p proxy encode was CPU-starved. **The plan
leg must contain no encode.** That is a build-time assertion, not a hope: the
split is only safe if every ffmpeg/Remotion call stays on the render leg.

## 4 — WHAT SHIPS IN WHICH ORDER

1. **`burst_double_hold` instrument** — this deploy. Turns L2's 335s from an
   inference into a measurement.
2. **L1 split** — next, because 1,120 core-seconds per Lumen render of pure idle
   hold arrives with Phase 2 and the split must precede it.
3. **L2** — only after the instrument reports, and with its own `.spawn()`-orphan
   design pass.
4. **Prewarm (~$195/mo, §5)** — separate, and it is the Aug-4 surface, so it goes
   last or not at all.

## 5 — THE THIRD SURFACE, FOUND BY ARITHMETIC

The bill is **27.5% memory**. Solving with the dashboard split — orchestration
72.3% (which alone would produce 11.3% memory) and rendering 9.6% (25.3%) — the
remaining **18.1% of spend must be ~93.6% memory**. Only one surface has that
shape:

| surface | memory share it would produce alone |
|---|---|
| orchestrator 16c/12G | 11.3% |
| burst / fanout 32c/64G | 25.3% |
| **prewarm 0.125c/4G** | **84.4%** |
| validator 4c/2G | 7.8% |

### SUPERSEDED BY THE DASHBOARD — use these

| surface | **dashboard, cycle-to-date** | my inference | error |
|---|---|---|---|
| PromptlyPrewarmWorker | **$74.19** | ~$97 (15d) | overstated ~1.3× |
| validator (UNS upload path) | **$75.33** | ~$33 (15d) | **understated ~2.3×** |
| together | **$149.52 = 17.0% of the $878.10 cycle** | — | total was close |

**The attribution was wrong even though the total was near.** I solved the
27.5%-memory residual assuming **ONE** surface, got 93.6%, matched it to the
prewarm shape (84.4%), and concluded the validator "cannot be the term". In fact
**two surfaces of nearly equal size sum to it** — and a two-term sum is not
recoverable from one blended ratio. The single-surface assumption was the error,
and it produced a confident exclusion of the validator that was simply false.

The validator is the **UNS upload-validation path** and is now the **larger** of
the two at $75.33 cycle-to-date.
