# PHASE 2 — the scene vocabulary, deterministic/generated split `[§3.1/§6.1]`

**Budget: ~70s of Lumen wall-clock, parallel by construction, prefetch during
transcription.** Every number is from `golden/first-light/` — measured in-run.

**Quota, now exact AND multiplied.** The metric
`GenContentImageGenRequestsPerMinutePerProjectPerBaseModelGlobal` is dimensioned
**per base_model**, and that dimension is a real, separate bucket — proven by
experiment 2026-08-15:

| model | measured limit | evidence |
|---|---|---|
| `gemini-3-pro-image` | **2/min** | documented; serial calls 429 |
| `gemini-3.1-flash-image` | **~4/min** | 4 rapid calls OK, 5th-7th 429 |
| **combined** | **~6/min** | **Pro succeeded immediately after 3 flash calls** — if the bucket were shared it would have 429'd |

**That is 3x today's effective rate, available now, with no dependency on the
60/min increase** (`promptly-image-gen-60rpm`, still `granted: 2`).

---

## 1 — THE SPLIT, AND IT IS LOPSIDED

| # | component | deterministic or generated | quota cost |
|---|---|---|---|
| **A** | keyword captions + number glorification | **deterministic** — caption renderers | 0 |
| **B** | **insert scenes** | **GENERATED — the only one** | 1 image each |
| **C** | text-behind-subject | **deterministic** — RVM matte on the user's own footage | 0 |
| **D** | name-plate | **deterministic** — design-system type | 0 |
| **E** | b-roll | **deterministic** — stock, live today | 0 |
| **F** | end-cards + palette lock | **deterministic** — `extract_palette`, $0 | 0 |
| **G** | rhythm law | **deterministic** — measured in the gate | 0 |
| — | landscape canvas | **deterministic** — 2 literals + a zone doctrine | 0 |
| ~~H~~ | ~~music bed~~ | **struck** `[§4.8]` — machinery removed | — |

**One of eight needs pixels from a model.** That is the re-plan: the scene budget
should buy generated scenes *only* where the frame genuinely cannot be
constructed, and everything else should never touch the quota.

### A correction I owe on Component C

I reported C as "blocked on rate headroom, not code." **That was wrong.** C is
text behind the *user's real subject*, which `SEGMENTATION_SPIKE.md` settles as
**RVM** — a deterministic temporal matte, zero image generation. What I measured
failing 2/2 was the **alpha/hero** path, which mattes a *generated* subject; that
is a B-family concern, not C.

C's real blockers are the three unpriced items in the spike §4 — **latency**
(matting is an *editing* effect, so §4.1 gives it no carve-out), **cost** (a
second GPU app per job), and **concurrency** (a sibling `.spawn()` surface).
Quota is not among them.

## 2 — THE SCENE CEILING, UNDER EACH QUOTA

Admission window = prefetch window (~30–45s, during transcription) + main budget
(~25–40s) ≈ **~75s of wall in which calls may be admitted**.

| configuration | admissions in ~75s | **generated scenes/edit** | binding constraint |
|---|---|---|---|
| Pro only, 2/min | 2.5 | **2** | quota |
| **Pro + flash, ~6/min (TODAY)** | **7.5** | **4** | **latency** |
| 60/min granted | 75 | **4+** | latency |

**The two-model split reaches the 4-scene target today.** The Google grant is
still worth having — it removes the flash dependency and raises the ceiling
beyond 4 — but Phase 2 no longer *waits* on it.

**Under today's quota the ceiling is 2 generated insert scenes per edit**, and a
two-call hero scene consumes the entire budget by itself.

**But the edit is not thereby thin.** Captions (A), b-roll (E), name-plate (D),
end-card + palette (F), rhythm (G), landscape, and text-behind-subject (C) all
render at **zero quota cost**. A 2-scene Lumen edit can still carry the full
deterministic vocabulary — which is precisely why the split matters more than the
quota does.

At 60/min the constraint flips back to latency, and the pacer below is what
turns ~4×18s of serial work into a parallel ~18–36s.

*(Scene timing convention: the ledger reports **nearest-rank** percentiles — p50
**17.9s**, p90 23.5s, max 32.4s. The harness prints 18.73s for the same data
under a different convention. Rounding to ~18s here so the arithmetic does not
imply precision the convention does not support.)*

### Which family goes to which model

Flash returns **1024x1024** (1.1 MB PNG); Pro returned **1408x768** at the same
1120 image tokens. Both are real, usable output — the split is by *demand*, not
by whether flash works.

| scene family | model | why |
|---|---|---|
| icon composition, flat infographic card, stat callout, evidence card | **flash** | geometric, few elements, no photographic subject — 4/min is where the volume belongs |
| hero / subject-bearing scenes, anything needing the 2-call matte | **Pro** | quality carries the frame, and its 2/min is reserved for the scenes that justify it |

This is also why the alpha/hero path stops being hopeless: moving the simple
families onto flash **frees Pro's entire 2/min** for the two-call reservation
that currently never wins twice in a row.

## 3 — PREFETCH, AS SPECIFIED

**Transcript-independent scenes only. One shared pacer. Two-call scenes reserve
both admissions.**

```
scene specs (independent, order-free)
        │
        ▼
  ONE global pacer ── PER-MODEL buckets: R_pro = 2/min, R_flash = 4/min
                      (they are independent; one pacer, two counters)
        ├── prefetch lane  opens at DISPATCH, runs during transcription
        └── main lane      opens when the transcript lands
        │
        ▼
  every scene resolves INDEPENDENTLY — Law 4: any one may fail alone
```

**Prefetchable** (specifiable at dispatch from brief + vibe + palette + aspect,
no transcript): **end-card (F)**, **name-plate (D)**, **brand frame**. Note these
are *deterministic* — so under a 2/min quota the prefetch lane costs **nothing**
and the whole admission budget stays available for B.

**Not prefetchable:** stat callouts, evidence cards, anything quoting the
speaker. A speculative prefetch that gets discarded spends the very quota it was
meant to save.

**Why one pacer:** today each call carries its own retry ladder, so N concurrent
calls each discover the 2/min limit independently and back off together — one
limit converted into N failures. That is the alpha path's exact death.

**Two-call rule:** a hero scene **reserves both admissions before leg 1 fires**;
if the pacer cannot promise both, it degrades to a single-call scene. Spending
leg 1 on an attempt that structurally cannot finish is the $0.28 already burned.

## 4 — WHAT THIS REFUSES

- **No speculative over-generation** — generate 8, keep 4 costs 2× and buys
  nothing against a rate limit.
- **No retry-as-answer** (standing law). The pacer prevents the 429.
- **No scene on the critical path** — Law 4. A scene unresolved when the render
  is ready is **dropped, not waited for**.

## 5 — OPEN

- **R under a pacer is unmeasured.** 2/min is the documented limit; the safe
  admission rate needs one cheap calibration run.
- **$/render**: 2 scenes × $0.14 = **$0.28/edit** today; 4 × $0.14 = **$0.56** at
  60/min. Both sit under the $1 law — but only once a scene count per edit is
  real rather than assumed.
- **Nothing here is built.** This is the design the measured envelope supports.
