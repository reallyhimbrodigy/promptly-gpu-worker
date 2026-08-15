# THE FOUR-LAW BOARD `[§3.1/§6.1]`

Every number here is **measured**, carries its **denominator**, and names the
**window** it was cut from. A cell with no denominator is not a result.

Last cut: **2026-08-14**. Deploys in force: content-studio `b6eceb7`, worker
**v530** (`5ba82c1`).

---

## LAW 1 — COST · *well under $1/render, measured never estimated*

**First Light, 2026-08-14, measured IN-RUN by the harness — not read back from
`result`.** That distinction is load-bearing: `result` loses its envelope on
38.6% of completions, so any number taken from it would be cut from a corrupted
population. The harness times and prices each call at the call site.

| term | measured | denominator |
|---|---|---|
| $/image (Nano Banana Pro) | **$0.140** | per-call, every call |
| $/scene | **$0.140** (1 image) | 10 scenes |
| $/hero-scene (alpha) | **UNMEASURED — 0/2 succeeded** | 2 attempts, $0.56 spent on failures |
| First Light run total | **$1.96** | 14 images; ceiling $2.00, in budget |

**Open:** $/render for a full Lumen edit is NOT yet measurable — it needs a scene
count per edit, which Phase 2 sets. Reporting a blended $/render before then
would be an estimate wearing a measurement's clothes.

## LAW 2 — LATENCY · *the 2-minute law survives; scenes generate in parallel*

| term | measured | denominator |
|---|---|---|
| s/scene p50 | **18.73s** | 10 scenes |
| s/scene max | **32.43s** | 10 scenes |
| alpha (hero) | **~61s per attempt, 0/2 succeeded** | 2 |
| **6 scenes SERIAL** | **~112s** | 6 x 18.73s — inside 120s with **8s of margin** |
| **7 scenes SERIAL** | **~131s** | breaks the law |

**The conflict MOVED but did not resolve.** At 18.73s/scene the serial break-even
is now 7 scenes rather than 6 — but 8s of margin on a 120s law, for the scene
step *alone* with the entire rest of the edit still to run, is not headroom. Law
2's parallel requirement stands.

**And parallelism is exactly what the quota punishes.** Every failure in both
runs was `429 RESOURCE_EXHAUSTED`. The envelope is **quota-bound, not
compute-bound**, which means buying latency with concurrency is the one move the
provider will not sell us at this tier.

### Delivery latency, by class — clean cohort, post-Migration-01

| class | p50 | n |
|---|---|---|
| envelope FULL | **84s** | 274 |
| envelope LOST × reconciler | **304s** | 156 |
| envelope LOST × repair | **904s** | 24 |

### QUEUE DELAY — new term, 2026-08-14 `created_at → worker_started_at`

The term Lumen will amplify: a Lumen render is longer and heavier, so anything
that makes jobs wait for a worker gets worse, not better, when scenes land.

| date | n | p50 | p90 | **%>60s** |
|---|---|---|---|---|
| 2026-08-11 | 17 | 28s | 215s | 47.1% |
| 2026-08-12 | 182 | 13s | 274s | 41.2% |
| 2026-08-13 | 135 | 11s | 181s | 33.3% |
| 2026-08-14 | 153 | 15s | **324s** | 46.4% |
| **overall** | **489** | **13s** | **271s** (p99 **637s**) | **40.9%** |

**The distribution is BIMODAL and that is the whole point.** The median job
starts in ~13s; ~41% wait over a minute and the p90 tail runs 3–5 minutes. A
single average would report "13s" and hide the entire affected population.

**It tracks envelope loss almost 1:1, day by day:**

| | Aug 12 | Aug 13 | Aug 14 |
|---|---|---|---|
| queue >60s | 41.2% | 33.3% | 46.4% |
| envelope-absent | 38.1% | 34.4% | 45.6% |

**Stated as correlation, not cause** — this identifies the affected POPULATION,
not the trigger. Long-queued jobs are the ones that lose envelopes; *why* a
long-queued job loses its envelope is what `worker_envelope_write` will answer.

### THE HARD-TERMINAL FENCE — REFUTED 2026-08-14 [MEASURED]

The leading candidate is dead. The fence declines a worker write only when the
row is already `failed`/`canceled`, and `repairCompletedRender` never clears
`error_message` — so a row that passed through `failed` keeps its error string
after being flipped to completed. It is a query, not an inference:

| cohort | n | `error_message` non-null |
|---|---|---|
| envelope LOST | 181 | **0 (0.0%)** |
| envelope PRESENT | 278 | 0 (0.0%) |
| refund / fail events | 150 sampled each | 0 / 0 |

**Probe validated on a known-bad window before the zero was believed:** 50/50
rows with `status='failed'` DO carry `error_message`; `render_failed` events DO
carry `job_id` (6/6); only **1** completed row in the entire table has an error
string. The probe can see the thing it reported absent.

**So the LOST rows were never non-processing before the worker's write.** The
fence never fired. That sharpens the remaining space: `matched=0` is only
reachable via the fence, so `worker_envelope_write` must land on
`accepted=true` (→ the envelope landed and a later writer replaced it) or
`raised=true` (→ the write threw; PGRST204 flagged).

**Honesty note on the trend:** `worker_started_at` was created by Migration 01 at
**2026-08-11 19:49Z**, so this series *cannot* extend earlier. There is **no
pre-migration baseline**, and I cannot say queue delay "rose" against one. Within
the window the p90 moves 215 → 274 → 181 → 324s — noisy, not monotonic.

## LAW 3 — QUALITY · *the references calibrate the instruments*

| dimension | bar | state |
|---|---|---|
| rhythm, PRIMARY | **≥3.5 moving samples/s** | both refs pass (3.57, 3.52); gate-enforced |
| rhythm, SECONDARY | **≤3.5s max stillness** | both refs pass; gate-enforced |
| palette accent | REF-1 hue 15–45° (orange) | extracts `#F06D1F`; canon-rule gate |
| foreground contrast | ≥0.45 | 0.88 / 0.91 |

**Canon rule in force:** if a reference fails a dimension, the dimension is
broken. It has already fired twice — the palette extractor returned *green* for a
documented-orange reference, and my own rhythm fixtures failed JUDGE's target
because the fixtures were wrong, not the target.

## LAW 4 — ERRORS · *every scene independently optional; no new component may fail a render*

| term | measured | denominator |
|---|---|---|
| scene failure rate | **0.00** | 10 scenes, 10 ok (prior run 0.20; backoff now absorbs the 429s) |
| **alpha/hero failure rate** | **1.00** | **0 of 2** — both exhausted 4 retries on 429 |
| envelope-absent | **38.6%** | 466 completions, **161 users** |
| double renders | **0** | 60 absent + 60 present, all exactly 1 `render_started` |
| users who lost a video to envelope loss | **0** | 180/180 had a delivery column |

**The failure mode is quota, not correctness** — every failure in both runs was a
429, never a bad image. That makes these *rate limits*, not defect rates, and it
is the same wall Law 2's parallelism requirement runs into.

**The alpha/hero path is the sharp edge and it is currently 0%.** A hero scene
needs TWO sequential calls (white-bg then black-bg, differenced into a matte).
The first lands; the second arrives while the quota is still recovering from the
first and starves through all four retries. Single scenes survive 429s because
one retry ladder is enough; the two-call path has to win twice in a row and
currently never does. **Component C (text-behind-subject) depends on this path**,
so it is blocked on quota headroom, not on code.

---

## WHAT THIS BOARD MAY NOT YET SAY

- **Nothing is verified post-fix.** The delivery fixes deployed today have not
  met a real denominator. `worker_envelope_write` reads at **n≥100**, not before.
- **$/render** — needs Phase 2's scene count.
- **Envelope-loss root cause** — the mechanism of erasure is known; the trigger
  is not. The lifecycle-push lost update was **refuted as the onset cause** (0.0%
  across 2,687 completions Aug 4–11 with the claim running on every one).
- **No worker deploy in the Aug 11–12 window touched the completion write.**
  v522–v526 are docs/cert wiring, v527 is a 9-line canon dict, v528 docs, v529
  post-onset. Migration 01 (19:49Z Aug 11) remains the only schema event in the
  window; PGRST204 is re-opened as a candidate and is now instrumented rather
  than argued.
