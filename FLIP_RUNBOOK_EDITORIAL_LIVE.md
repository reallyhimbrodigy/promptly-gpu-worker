# THE FLIP PACKAGE — editorial goes live, on 3.7-flash (STAGED, **NOT EXECUTED**)

**Status: PREPARED. Nothing in this file has been run.** The secret change needs
an explicit GO naming the key, per the standing law that a live-secret VALUE
change never rides along with a deploy.

---

## 0. What is actually true right now (observed, not inferred)

| fact | evidence |
|---|---|
| editorial reached **0 of 60 jobs, 0 of 60 users** post-v550 | `edit_recipe->>route` on the 100%-recipe-coverage cohort |
| `_editorial_suppressed()` is `(not _build_lane()) and (not _editorial_live_enabled())` | handler.py:14406 |
| `PROMPTLY_EDITORIAL_LIVE` defaults **OFF**, and needs a **redeploy** to take effect | handler.py:14345, memory-snapshot law |
| the editorial model was a **hardcoded constant** until v552 | handler.py:123 |
| `gemini-3.7-flash` is **callable on Vertex** | probe 2026-08-17: 4/4 incl. the known-good control |
| ASR diversion runs **68–74%** of traffic, on the clean cohort | Aug 16–17, 100% recipe coverage |

**The arithmetic the owner named.** ASR-reason diversions are 82% of diverted
jobs but the non-ASR remainder (`too_short`, `no_audio`, `plan_collapsed`,
`not_talking_head`) is ~32% of live traffic — so ASR cannot account for the gap
between 39.2% editorial (Aug 10–11) and 0.6% (Aug 16–17). A suppressed gate
explains a **zero**; a degraded ASR explains only a **decline**. The observed
value is zero.

---

## 1. Already shipped, DARK (v552 candidate — inert until the secret says otherwise)

`GEMINI_EDITORIAL_MODEL` now reads `PROMPTLY_EDITORIAL_MODEL`, **defaulting to
the model production plans on today**. Shipping it changes nothing: it only
makes an arm selectable.

- check: `cert_editorial_model_pinned.py`, wired into `validate_deploy`
- 4 mutations RED-proven (override removed · `-latest` alias · default silently
  re-pointed · startup log reverts to a constant)

---

## 2. Step order — the differ runs BEFORE the flag, never after

§4.7 is `change dark → differ verdict in HOURS → keep or kill`. The model arm
and the live flag are **two separate decisions** and must not be flipped in one
motion, or a regression cannot be attributed to either one.

```
Step A  differ: 3.7-flash vs 3.1-pro-preview on the FROZEN goldens
        (golden/manifest.json, frozen_at_commit 1601ae0), build lane only.
        _build_lane() is true there, so _editorial_suppressed() is already
        false — the differ needs NO secret change. THIS COSTS NO USER A VIDEO.

        RED IS HELD, NEVER TUNED IN-WINDOW. A differ GREEN means "the corpus
        saw no regression" — NOT proof of improvement. Improvement is a taste
        call on pixels, and it is the owner's, not mine.

Step B  ONLY on a GREEN: set PROMPTLY_EDITORIAL_MODEL=gemini-3.7-flash in the
        Modal secret + the canonical-values gate (same commit), redeploy in a
        quiet window. Still zero live editorial jobs — the flag is still off.

Step C  ONLY on an explicit GO naming the key: PROMPTLY_EDITORIAL_LIVE=1,
        same commit as its canonical gate entry, quiet-window deploy, verify
        the live sha, then the pre-registered read below.
```

**Rollback is one flag**, and it is the same flag in every step: unset
`PROMPTLY_EDITORIAL_LIVE`, redeploy. Every job falls back to the deterministic
path it takes today. No user loses a deliverable — they lose an *upgrade*.

---

## 3. THE PRE-REGISTERED READ — first 50 editorial jobs

**Written before a single editorial job exists, so none of it can be tuned to
the result.** The metrics, the thresholds, and the revert triggers are fixed
here and now.

### Cohort (Rule 5)
Jobs with `edit_recipe->>route IS NULL` **and** `created_at >= the v55x deploy
timestamp` **and** `status='completed'`. Pre-flip jobs and the deploy minute
itself are excluded. Cut **by route** — a blended number across a mixed route
population is not a product metric.

### Reported per USER as well as per job (Rule 7)
A user who fails five times is **one lost user, not five failures**. Both
numbers get reported; the user count leads.

| # | metric | source | threshold | why this number |
|---|---|---|---|---|
| 1 | editorial **share** of completions | `route IS NULL` / completions | **≥ 25%** | Aug 10–11 ran 39.2%; ASR diversion has risen since, so 25% is the honest floor, not a target |
| 2 | editorial **failure rate**, per user | `status='failed'` in cohort | **< 5%** | above this the flip is costing users videos |
| 3 | **p50 / p95 wall**, editorial only | `stage_timings.total` | p50 **≤ 120s** | the latency law; 3.7-flash was chosen partly for this |
| 4 | **$/job**, editorial only | cost meter | **≤ $0.10** | the cost law, cut by route |
| 5 | **UNKNOWN error class** | `result.error_class` | **0** | a named failure is survivable; an unnamed one is not |
| 6 | **component reach** | design-system + MG counters | **non-zero** | Rule: no component counts as shipped until a production counter moves |
| 7 | `asr_diagnostics` **coverage** | `result.asr_diagnostics` | **> 95%** | the denominator for every claim above; if this is low, nothing else here is readable |

### What makes me revert early, stated before looking
- any **UNKNOWN** terminal class (#5) — revert immediately, diagnose after
- editorial failure rate **> 10% per user** at n≥20, without waiting for 50
- **p95 wall > 300s** — that is the standing rejection ceiling, not a soft target
- **$/job > $0.25** on the editorial route at any n — spend outruns the read

### What does NOT trigger a revert
- a lower editorial share than 39.2%. ASR diversion legitimately rose, and
  re-litigating that here would confound two changes.
- a differ GREEN that the owner dislikes on pixels. That is a taste call and it
  outranks the differ — but it is a **kill of the model arm**, not of the flag.

### The read is one command
```
python3 read_editorial_flip.py --since <deploy-ts>    # to be written WITH step C
python3 read_asr_diagnostics.py --since <deploy-ts>   # already shipped, v551
```

---

## 4. Cost, priced in advance (Rule 6)

The differ (Step A) is the only spend before any flag moves.

| arm | what | priced |
|---|---|---|
| Step A differ | 2 models × frozen goldens, **plan-only** (a render cannot change what the PLANNER emits) | **~$0.80** |
| Step C first 50 | 50 live editorial jobs at the $0.10 law | **~$5.00**, and it is user-job spend, not build capital |

Step A is build capital and is the same shape as the Track-1 matrix already
ledgered. **No synthetic Modal spend beyond it**; Step C is watched real traffic.

---

## 5. The two things I will not do without being told

1. **Flip `PROMPTLY_EDITORIAL_LIVE`.** It needs an explicit GO naming the key.
2. **Change the editorial model default.** The cert pins it by name precisely so
   that re-pointing the live planner is a visible, reviewed edit.
