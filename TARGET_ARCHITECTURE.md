# TARGET ARCHITECTURE — 60–90s end to end, at quality

Written 2026-08-23. Every number here is measured on production traffic since
the editorial flip (n=76 editorial jobs, p50 unless stated). Nothing in this
document is an estimate dressed as a fact; where a number is unknown it says so
and names the measurement that would settle it.

This is not a refactor proposal. It is where the pipeline is going, so that each
piece of work can be judged by whether it moves us there instead of by whether
it makes something locally faster.

---

## 1. What we spend today

```
total                          271.0s
  normalize_transcribe_upload   74.5s     27%
    edit_plan                   68.5s     (nested inside the above)
      gemini_call               30.4s     (nested inside edit_plan)
  render                       174.2s     64%
    render_remotion            ~80-85% of render
      remotion:micro-NN        ~97s each, 4-way CONCURRENT  <-- the bottleneck
      remotion:overlay          72.0s, runs INSIDE the micro window
    render_composite           ~13s
    render_prep                 3-9%
  upload_export                  4.5s      2%
  download                       1.1s      <1%
source_duration                 29.2s
```

p50 wall 193–271s depending on cut; p95 485s. Target is 60–90s. **We are 3–4×
away, and 64% of the gap is one stage.**

---

## 2. What is already ruled out

These were each tested and are not the answer. Recording them so nobody spends
the week I spent re-deriving them.

| candidate | verdict | evidence |
|---|---|---|
| source duration drives render | **no** | r = 0.132 (n=70) |
| component count drives render | **no** | r = 0.224; a 4-component job took 632s, another took 32.5s |
| cut count drives render | **no** | r = 0.064 |
| upload / HLS / exports | **no** | 1% of the dark time; 4.5s p50 |
| render prep + pre-extracts | **no** | 3% on a 4K source with 5 zoom extracts |
| ladder retries | **no** | `render_attempts = 1` on every instrumented render |
| prompt size | **no** | cutting 9.3% of the prompt bought 3.7% of tokens; the prompt is already implicitly CACHED |
| overlay/base sequencing | **already done** | composite chunk K starts on ITS overlay chunk, not the global one |

**Nothing the planner controls predicts render time.** That is the single most
useful negative result we have: it means the fix is in the renderer's own
structure, not in asking the model for less.

---

## 3. The target shape

### 3.1 Stage classes

Every stage is exactly one of:

- **PARALLEL** — runs concurrently with its siblings, no ordering
- **CONDITIONAL** — runs only when it will produce something
- **STREAMING** — produces partial output its consumer can start on
- **BLOCKING** — everything waits (should be almost nothing)

```
download                    BLOCKING   1.1s      nothing can start without bytes
├─ normalize (canonical)    PARALLEL   10.0s     needed by render only
├─ transcribe (Deepgram)    PARALLEL   ~15s      needed by plan only
└─ proxy encode + upload    PARALLEL   ~10s      needed by plan only
                                       └─ all three overlap; the leg is max(), not sum()

edit_plan                   STREAMING  target 30s   <-- today BLOCKING at 68.5s
  gemini_call               30.4s      token-bound, not compute-bound

render                      target 40s   <-- today 174.2s
├─ micro segments           CONDITIONAL + PARALLEL   <-- THE BOTTLENECK
├─ overlay (alpha)          CONDITIONAL + PARALLEL   off the critical path already
└─ composite (ffmpeg)       STREAMING per chunk      already pipelined

upload / HLS / exports      PARALLEL   4.5s
```

### 3.2 The floor, derived

The floor is the longest chain that cannot be removed or overlapped:

```
download            1.1s     irreducible (network)
normalize          10.0s     ffmpeg transcode of the source; scales with resolution
gemini_call        30.4s     model latency; token-bound (see 4.2)
render             ~25s      IF micro is fixed (see 4.1)
upload_export       4.5s     irreducible (network)
                   -----
FLOOR              ~71s      with transcribe/proxy fully hidden under normalize
```

**60–90s is reachable, but only just, and only if the render drops to ~25s.**
There is no slack: every stage above is already at or near its own floor except
the render. This is why the render is the whole programme and everything else is
housekeeping.

---

## 4. The three things that have to change

### 4.1 Micro segments — the bottleneck (64% of the gap)

Measured: 4 micro chunks, ~97s each, running concurrently, union ≈ 103.4s ≈ the
whole `render_remotion` span. Output was **21.5s**. That is ~4.5× realtime for
windows that are supposed to be short.

Micro segments render transitions (11 types) + composite-effect zooms
(FocusWindow / LetterboxPush / DepthPull). They are already emptiness-guarded,
so this is not a skip — it is that each chunk is expensive.

**THE OPEN QUESTION THAT DECIDES THE FIX** — and it is the one blocking
measurement worth having:

- **Fixed per chunk** (~10s process startup × N) → the fix is FEWER chunks, and
  splitting harder makes it worse.
- **Per frame** → the fix is fewer frames: render only the transition/zoom
  windows rather than the segments containing them, the same span-limiting the
  overlay wants.

`read_chunk_split.py` answers this from ≥3 production jobs of differing output
length. n=1 today. **No micro work should start before that number exists** —
the two fixes are opposites, and I have already once optimised the wrong layer
by assuming.

### 4.2 The editorial call — token-bound, and the video is the cost

Measured fit across 21 jobs:

```
prompt_tokens ≈ 60,540 + 1,255 × source_seconds
                 ^ prompt text, CACHED      ^ the video, UNCACHED, paid every call
```

At 30s of source the video is ~38% of input and it grows linearly; at 155s it is
76%. The prompt is already implicitly cached, so **prompt cutting is capped at
~39% of input tokens and touches the cheap half**. This is why the exemplar cut
bought nothing.

2fps + `MEDIA_RESOLUTION_LOW` is live (v569/v570): −36% prompt tokens, −60%
uncached, with emphasis placement inside the A-vs-A noise floor. Cohort read
pending, cut by the per-job persisted `proxy_sample_fps`.

**Structural target: STREAMING the plan.** Today `edit_plan` blocks for 68.5s
and the render cannot start. The plan is a list of independent per-window
decisions; if it streamed, chunk 0 could render while the model is still
deciding chunk 3. That converts a 68.5s blocking stage into ~10s of latency plus
overlap. This is the largest structural win after micro, and it is untouched.

### 4.3 Conditional everywhere — skip what produces nothing

Already applied: zoom pre-extract, transition pre-extract, micro render.
**Not applied: the overlay**, which renders the full output duration regardless
of whether any layer paints. On 14% of jobs all six families
(captions, MG, text overlays, tight-cut, generated scenes, b-roll) are empty.

Sized honestly: the overlay is **off the critical path** (72.0s inside a 103.4s
micro window), so this is a **cost and correctness** change, not a latency one.
It pays in full only on jobs with no micro segments — which are already the fast
ones. Worth doing; not worth selling as speed.

---

## 5. What this means for quality

The 90s law and the quality law are usually posed as a trade. On this
architecture they mostly are not:

- Micro cost is **per window**, not per component, so more emphasis moments do
  not linearly cost more render — the correlation is r=0.224 and near zero.
- The overlay is off the critical path, so **richer overlays are free** in
  latency terms until they exceed the micro window.
- Streaming the plan makes the model's *thinking time* overlap the render, so a
  longer, better-reasoned plan costs less wall than it does today.

The one real trade is video sampling: 2fps is 9× fewer video tokens and it is
the only lever measured to touch output (emphasis count 5→4, thumbnail index
moves). That is a genuine quality-for-cost trade and it is now made explicitly,
with a per-job record of which arm ran.

---

## 6. Sequence

1. **Micro fixed-vs-slope** (watcher, blocking nothing) — decides 4.1
2. **Empty-canvas overlay skip** — correctness/cost, buildable now
3. **Plan streaming** — largest structural win after micro; needs a design pass
4. **Micro fix** — per 4.1's answer
5. Re-derive the floor; 60–90s or a written reason why not

---

## 7. What is NOT in this document

- **L1/L2 orchestrator split**: measured at ~$570–760/yr, 6–8× below the
  ranking that scheduled it. Cost work, not latency work.
- **Premium routes** (moodreel/hype) — 36.3% of traffic, and they write **no
  timeline at all**. A moodreel job renders for 204s and is as blind as the
  editorial tail was before v566. Instrumenting them is a prerequisite to
  saying anything about the product's real p50, and nobody has.
