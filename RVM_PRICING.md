# COMPONENT C — pricing the RVM pass, and gating it conditional `[§3.1/§4.1]`

**Before C is committed.** Two questions: what does the second GPU app cost in
**seconds** and **dollars**, and how is it kept off the critical path.

---

## 1 — WHAT IS ACTUALLY KNOWN (and what is not)

From `matting/matting_app.py` on `behind-layer-phase1`:

| | |
|---|---|
| app | `promptly-matting` — a **separate** Modal app, own GPU image |
| entrypoints | `matte_windows_t4` (`gpu="T4"`) · `matte_windows_l4` (`gpu="L4"`) |
| memory | 16384 MB · timeout 1200s |
| model | RVM `mobilenetv3` (fast) / `resnet50` (best), weights **baked into the image** |
| downsample | fast 0.25 · best 0.375 |
| lead-in | **1.0s before every window** — recurrent state must settle |

**Seconds: UNMEASURED.** The app instruments itself (`dl_s`, `load_s`, `t_all`)
but **no benchmark result was ever recorded** in the repo — the July spike
recorded *matte quality* (bite/lag, edge bias), never throughput. There are also
no Modal GPU rates in `MODAL_SPEND_LEDGER.md`.

So I will not quote a $/pass figure. Under the cost law — *measured, never
estimated* — the only honest statement today is: **unpriced, and here is exactly
what it costs to price it.**

### The three cost terms, named so none is forgotten

1. **Download + decode** the source (`dl_s`) — the matting app fetches the video
   itself, so this is paid **again**, in addition to the render worker's copy.
2. **Model load + cold start** (`load_s`) — weights are baked in, so no network
   pull, but the container still cold-starts per job unless kept warm.
3. **Inference** — per matted window, plus **1.0s of lead-in per window** that
   produces no output frames.

Term 3 is the one that scales with the *plan*, and term 1 is the one people
forget. A 2-window edit pays the lead-in twice.

## 2 — THE MEASUREMENT, PRICED

**One run, T4 and L4, on a durable constructed source — $0.05 ceiling.**

- ~2 min of T4 + ~2 min of L4 at published list rates is a few cents; the ceiling
  is set at **$0.05** and the run refuses past it, same pattern as First Light.
- Source: a constructed durable clip (never user media), per the A/B law.
- Reports: `dl_s`, `load_s`, inference s/window, total wall, at both quality
  rungs and both GPUs → **s/pass and $/pass, measured**.

**Not yet run.** It needs `behind-layer-phase1` merged and re-certed against
current HEAD first (the branch predates ~2 weeks of worker changes), which is
work item 3 on the build sheet.

## 3 — CONDITIONAL BY CONSTRUCTION — the design ruling

> **The matte pass runs only when the plan actually places text behind the
> subject. It is never a default leg.**

This is not an optimisation, it is a §4.1 requirement. The budget arithmetic:

```
120s editing law
 -70s Lumen scene budget (LUMEN_PHASE2_DESIGN)
 ────
 ~50s left for EVERYTHING else — render, upload, delivery
```

An unconditional matte pass spends that remainder on a component **most edits do
not use**, and §4.1 gives it **no carve-out**: text-behind-subject is an *editing*
effect, not a generative one. A default leg would break the law for every user to
serve a minority composition.

### The gate

```
plan → does ANY overlay carry behind_subject: true ?
        │
        ├── no  (the common case) → matting app is NEVER INVOKED.
        │                            Zero seconds, zero dollars, zero cold start.
        │
        └── yes → windows = ONLY the spans that need it, merged
                  → one matte call carrying all windows
                  → composite via alphamerge/maskedmerge (already solved)
```

Three properties that follow, each closing a named failure:

1. **Windows, not the whole video.** The app already takes a window list. Matting
   a 60s source to place text behind 4s of it is 15× the necessary work.
2. **One call carrying N windows**, never N calls. Each call pays download and
   cold start again; the lead-in is per window either way.
3. **Merge adjacent windows** before submitting — two windows 0.5s apart cost two
   1.0s lead-ins to save 0.5s of inference.

### Law 4 — it may not fail the render

The matte is an **enhancement**, so it obeys the same rule as a scene: if it does
not resolve inside its budget, the overlay renders **in front of** the subject
and the edit ships. A missing matte is a lesser composition; a blocked render is
a failure. It must also carry an honest note only when the artifact exists (§4.6)
— never "we put text behind you" attached to a flat composite.

### The `.spawn()` orphan hazard

A sibling app invoked per job is a second scaling surface, and this project has
been bitten before: `.spawn()`ed containers outlive the local orchestrator, and a
batch is only dead when `modal app list` shows 0 tasks. The matte call must be
**synchronous within the render's own budget** (`.remote()` with a hard timeout),
never spawned-and-awaited-later.

## 4 — WHAT THIS CHANGES ABOUT C's STATUS

C is **not quota-blocked** — that was my error, corrected in
`golden/first-light/README.md`. RVM is deterministic and touches no image
generation. C's blockers are exactly three, and after this document two of them
have an answer:

| blocker | status |
|---|---|
| **latency** | **answered by design** — conditional, so the common path pays 0s |
| **concurrency** | **answered by design** — synchronous `.remote()`, never `.spawn()` |
| **cost** | **still open** — needs the $0.05 measurement above |
