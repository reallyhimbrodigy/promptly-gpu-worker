# PHASE 2 — the scene vocabulary, designed to a 70s wall `[§3.1/§6.1]`

**Budget: ~70s of Lumen wall-clock, parallel by construction, prefetch during
transcription.** Every number below is from `golden/first-light/` — measured
in-run, not estimated.

---

## THE FINDING THAT DECIDES THE DESIGN

**Parallelism buys almost nothing at the current quota, and the arithmetic says
so plainly.**

| | |
|---|---|
| uncontended call | **17.9s** |
| serial throughput | **~3.4 images/min** |
| observed limit | binds **below 3.4/min** — serial calls still 429'd |

A 70s budget at 18.7s/scene holds **~3.7 scenes serially**. The rate limit
independently allows **~3.4–4 images/min**. **Those are the same number.** Firing
6 scenes concurrently does not produce 6 scenes in 19s; it produces 429s, retry
ladders, and a *longer* wall than serial — which is exactly what happened to the
alpha path, the only two-call-in-a-row workload in the run, and it failed 2/2.

So the honest design constraint is:

> **~4 generated scenes per edit is the ceiling, and it is imposed by quota, not
> by the 70s budget.** Raising the wall to 120s does not buy a 5th scene. A
> Vertex quota increase does.

Designing for 6–8 scenes today would be designing for a provider we do not have.

## THE BUDGET

| stage | budget | note |
|---|---|---|
| **prefetch window** (during transcription) | **~30–45s, free** | see below |
| scene generation, remaining | ~25–40s | 1–2 scenes if not prefetched |
| composition + render integration | ~10s | deterministic, no provider |
| **total added wall** | **≤70s** | |

### Prefetch during transcription is the whole trick

Transcription (Deepgram) occupies **30–45s** during which **zero image calls are
in flight** — the quota sits completely idle. That window is free throughput, and
it is the only place to get more scenes without more quota.

At ~3.4 images/min, a 40s idle window is worth **~2.2 images**. Prefetching two
scenes there means the post-transcript budget only has to cover ~2 more —
**bringing 4 scenes inside 70s without exceeding the rate limit at any instant.**

**What can be prefetched before the transcript exists:** scenes whose content
derives from things known at dispatch — the user's brief/vibe, the source
footage's palette (`design_system.extract_palette`, already deterministic and
$0), aspect ratio, and brand/name-plate material. Concretely: **end-card (F),
name-plate (D), and brand-frame** scenes are all specifiable without a word of
transcript.

**What cannot:** stat callouts, evidence cards, and anything quoting the speaker.
Those need the transcript and belong in the post-transcript budget.

That split is not a convenience — it is what makes the prefetch *correct* rather
than speculative. A prefetch that guesses at transcript content would be thrown
away, which spends the very quota it was meant to save.

## PARALLEL BY CONSTRUCTION — with an admission-controlled pacer

"Parallel by construction" cannot mean "fire N at once" here. It means the scene
set is expressed as **independent units with no ordering dependency**, submitted
to one **shared pacer** that admits calls at the measured safe rate.

```
scene specs (independent, order-free)
        │
        ▼
  ONE global pacer  ── admits ≤ R req/min, R measured not guessed
        │                 (starts at 3, tuned by observed 429 rate)
        ├── prefetch lane  (opens at dispatch, runs during transcription)
        └── main lane      (opens when the transcript lands)
        │
        ▼
  each scene resolves INDEPENDENTLY — Law 4: any one may fail with no
  effect on the edit or on its siblings
```

Three properties this buys:

1. **The pacer is the single place the rate limit is known.** Today the retry
   ladder is per-call, so N concurrent calls each discover the limit
   independently and all back off together — a thundering herd that converts one
   limit into N failures.
2. **Prefetch and main share one budget.** Without a shared pacer they would
   compete, and the prefetch would starve the transcript-dependent scenes that
   actually carry the edit.
3. **It scales the day quota is raised** — R is one number.

## THE ALPHA/HERO PATH NEEDS A SEQUENCING RULE, NOT MORE RETRIES

A hero scene is two calls that must both land. At this quota it is 0/2 because
leg 2 arrives while the quota is recovering from leg 1.

**Rule: a two-call scene reserves BOTH admissions from the pacer before leg 1
fires.** If the pacer cannot promise both, the hero scene is not attempted at all
— it degrades to a single-call scene. Spending leg 1's money on an attempt that
structurally cannot finish is the failure mode we already paid $0.28 for.

## WHAT THIS DESIGN REFUSES TO DO

- **No speculative over-generation.** Generating 8 and keeping 4 costs 2× and
  buys nothing at a rate limit.
- **No retry-as-answer** (standing law). The pacer prevents the 429; it does not
  absorb it.
- **No scene on the critical path.** Law 4: every scene independently optional.
  A scene that has not resolved when the render is ready is **dropped, not
  waited for** — the 70s is a budget, not a promise the edit blocks on.

## OPEN, AND HONEST ABOUT IT

- **R is not yet measured under a pacer.** 3.4/min is a serial-run *upper bound*;
  the real admission rate needs one cheap calibration run.
- **$/render is still unmeasurable** — 4 scenes × $0.14 = **$0.56/edit** at the
  ceiling, which fits the "well under $1" law, but only once a scene *count per
  edit* is real rather than assumed.
- **Nothing here is built.** This is the design the measured envelope supports;
  it is not a claim that any of it exists.
