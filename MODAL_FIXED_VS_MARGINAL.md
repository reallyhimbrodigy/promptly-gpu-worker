# MODAL COST — FIXED + MARGINAL, not blended `[Law 1]`

**Rate: $0.0000131/core-s (owner-supplied), $0.00000222/GiB-s (Modal list).**
Traffic **measured**: 183 jobs/day, inter-arrival p50 **312s**, mean 473s.

A blended $/render was the wrong shape. Warm containers are a **monthly line
item** — their cost depends on the calendar, not on how many renders ran.

---

## 1 — THE FIXED TERM HAS A HARD CEILING

A warm surface cannot cost more than being up 24/7. That is a **ceiling**, not an
estimate:

| surface | spec | 24/7 ceiling |
|---|---|---|
| prewarm `@app.cls` (600s) | default cpu / 4 GiB | $0.91/day |
| endpoint A (300s) | cpu=4 / 2 GiB | **$4.91/day** |
| endpoint B (300s) | cpu=2 / 1 GiB | $2.46/day |
| **CEILING** | | **$8.28/day = ~$248/mo** |

**Measured container-up fractions** (union of `[arrival, arrival+window]` over
real arrivals — this is why the traffic measurement was needed):

| window | surface | UP % of wall-clock |
|---|---|---|
| 45s | orchestrator tail | **8.8%** |
| 300s | the two endpoints | **45.0%** |
| 600s | prewarm | **68.7%** |

→ **today's fixed term ≈ $5.74/day (~$172/mo), which is 69% of the ceiling.**

## 2 — THE MARGINAL TERM

**$0.0222/render** — container lifetime (cold start + wall + tail), measured over
n=277 full-envelope completions.

## 3 — THE MODEL, AND WHY THE RANKING FLIPS

| jobs/day | fixed $/day | marginal $/day | total | marginal share |
|---|---|---|---|---|
| **183 (today)** | 5.74 | 4.06 | **9.80** | **41%** |
| 500 | 8.28 | 11.10 | 19.38 | 57% |
| 1,830 | 8.28 | 40.63 | 48.90 | 83% |
| 10,000 | 8.28 | 222.00 | 230.28 | 96% |

**The fixed term dominates today and is irrelevant by ~1,800 jobs/day.** It is
capped at ~$248/mo forever. **L1/L2 act on the marginal term — the one that
scales with the product**, and on the premium path (70s of pure wait) marginal
grows further.

So the honest ranking is **horizon-dependent**, and my two previous rankings were
both wrong for the same reason — each asserted one lever was "the biggest" from a
single unverified anchor:

- *"L1/L2 are the biggest lever we own"* — wrong at today's volume.
- *"L1/L2 optimise ~4% of the bill"* — that came from the **$87/day** figure,
  which see below.

## 4 — I CANNOT REPRODUCE THE $87/DAY FIGURE

`modal_app.py:674` records *"~$87/day of NON-JOB warmup/prewarm/idle."* Summing
**every** warm surface in the app at its measured up-fraction gives **$5.74/day —
6.6% of it**, and even the 24/7 ceiling of all of them is $8.28/day.

Two possibilities, and I cannot separate them from here:

1. **The figure is stale.** It predates the removal of `min_containers=1`
   (documented ~$35/mo saved), the cpu 64→16 cut, and the memory cuts. Most
   likely.
2. **There is a surface I have not enumerated** — something outside
   `modal_app.py`'s decorators.

**Either way it must not be used to justify a cut**, and it has now misled the
lever ranking once. **This is the single strongest reason the invoice split is
required before anything is changed.**

## 5 — THE BEFORE/AFTER PROTOCOL

The Aug-4 prewarm revert is the template for how *not* to do this: the window was
cut 600→30 to "free container budget", the ceiling was never binding
(utilisation 7/100), and it "bought nothing and cost ~20s latency"
(`modal_app.py:1382`). It optimised an unmeasured constraint and paid in the one
number users feel.

Any cut ships only with all five:

1. **PRE-REGISTER the read.** Name the number, the direction, and the size of
   move that counts — *before* the change. A cut with a post-hoc read cannot be
   falsified.
2. **BOTH axes, always: cost AND latency.** The Aug-4 revert happened because
   only cost was watched. Queue delay (p50/p90/%>60s) and job wall are on the
   board for exactly this.
3. **CLEAN COHORT, stated first** (Rule 5): the window, and why it is clean —
   no deploy boundary, no outage hour, no mixed traffic inside it.
4. **A REVERT TRIGGER, pre-agreed**, with the latency regression that fires it.
5. **BY ROUTE** (Rule: never blended) — `minimal` and `minimal_speech_uncut` have
   different walls and will not respond alike.

### The candidate cuts, ranked by measured prize

| cut | prize | risk | pre-registered read |
|---|---|---|---|
| **endpoint A 300s → 90s** | up to **$3.4/mo × 30 ≈ $100/mo** | cold start on a user-facing validate call | endpoint p95 latency must not rise >200ms |
| endpoint B 300s → 90s | ~$50/mo | same, lighter | same |
| prewarm 600s → 300s | ~$10/mo | **this is the Aug-4 revert** — do LAST or not at all | dispatch latency unchanged; the 2026-08-04 note says the cut bought nothing |
| orchestrator 45s tail | ~$59/mo | reuse is already only 11.6% of gaps | job wall unchanged |

**None of these should be executed before the invoice confirms the surface.**
Total enumerated prize is **~$172/mo**, against an unexplained ~$87/day
($2,610/mo) in the repo's own note. Cutting $172/mo of confirmed surface while a
$2,400/mo discrepancy sits unexplained is optimising the part we can see because
we can see it.
