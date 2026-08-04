# FOUR CUTS BY LANGUAGE — Zac's complaint is real, and it is 5×

Hindi is **51% of the transcript cohort** (132 of 257). This is the majority
population, and the aggregate was hiding it.

| lang | n | **mid-word %** | keep-ratio med | keep<0.6 | export % | src dur med |
|---|---|---|---|---|---|---|
| **hi** | 132 | **37.1%** (49/132) | 0.90 | 10% | 15.9% | 16.3s |
| en | 81 | **7.4%** (6/81) | 0.85 | 23% | 16.0% | 22.4s |
| es | 7 | 0.0% | **0.41** | **71%** | 14.3% | 9.6s |

**Hindi cuts mid-word 5.0× more often than English. z = 4.81 — decisive, not
noise.** That is precisely the defect Zac describes, named in one query.

## BUT ONE HALF OF THE COMPLAINT IS REFUTED

*"or cut out HALF the video"* — **not for Hindi.** Hindi keeps **90%** of the
source, better than English's 85%, and only 10% of Hindi jobs keep under 60%
versus **23% of English**.

**The half-the-video problem is real but it belongs to English and Spanish.**
Spanish keeps a median of **41%** with 71% of jobs under 60% — the worst cell in
the table by a wide margin (n=7, so it needs confirming, but it is stark).

## AND THE MECHANISM IS NOT WHAT WAS ASSUMED

**It is not transcription quality.** Deepgram's Hindi is as confident as its
English:

| lang | words | median confidence | conf<0.5 | median word dur | zero-gap between words |
|---|---|---|---|---|---|
| hi | 8,889 | **0.994** | 2% | 0.320s | **94%** |
| en | 5,282 | **0.998** | 3% | 0.320s | 90% |
| ru | 336 | 0.849 | 17% | 0.400s | 93% |

Identical confidence, identical word durations. **"Deepgram is weak on Hindi" is
not visible in the data.**

**What IS visible: 94% of Hindi words have ZERO gap to the next word.** Speech is
contiguous, so there is no inter-word gap for a cut to land in — any boundary
that is not exactly on a word edge lands *inside* a word. English is 90%, so
this raises the stakes for both, but it does not by itself explain 5×.

### The likelier cause, from the earlier evidence

Clean videos end **0.50s past** the last word — the tail-pad signature. Broken
ones end **short**. So the real question is *why the tail-pad path runs for
English and not for Hindi*, and the strongest candidate is that
**language-routed jobs take a different cut path that never reaches the
word-aligned final-end handling.** Not proven; named as the next thing to read.

### On the mislabelling hypothesis — untested, not refuted

Within the `hi` bucket, purely-tagged jobs are the WORST (40.5% mid-word) and
mixed-tag jobs the best. That looks like it clears mislabelling — **but it does
not**, because confident mislabelling is indistinguishable from correct
labelling by tag purity. A Bengali clip tagged 100% "hi" scores as pure. The
structural cause stands as plausible and needs a real language ID to test.

## THE FIX IS ALREADY WRITTEN

`d5e466e` (committed, **not yet deployed**) enforces: the final cut end may sit
before a word, after a word, or at the true video end — **never strictly inside
one** — snapping outward to the word end and recording the correction. It is
language-agnostic by construction, so it closes the 37% and the 7.4% together.

**It disproportionately helps the majority-language population**, which is the
point of cutting by language rather than reporting an aggregate.

## Method + limits

Language = modal per-word `language` tag (`transcript.detected_language` is NULL
on all 600 rows). Mid-word = final cut's `source_end` strictly inside a word's
[start, end]. Keep-ratio = summed clip output ÷ `source_duration_s`. Export from
`analytics_events.export_completed`.

⚠️ Only standard-editorial jobs store a transcript, so this is measured where one
exists. `vad_coverage` is NOT persisted in `result` on any sampled row — cut 3
of the four could not be run.
