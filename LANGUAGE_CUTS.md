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

---

# CORRECTION (2026-08-03, after Zac's caveat 3): SPANISH IS NOT DROPOUT

I claimed "half the video has no transcribed words at all" and implied a
transcription failure. Checking WHERE the missing time sits refutes that.

| lang | n | LEADING | TRAILING | INTERIOR gaps | total missing |
|---|---|---|---|---|---|
| hi | 48 | 0.01 | 0.02 | **0.06** | 0.08 |
| en | 36 | 0.01 | 0.03 | **0.09** | 0.13 |
| **es** | 5 | **0.15** | **0.31** | **0.05** | 0.51 |

Spanish's missing 51% is **46% at the EDGES** and only **5% interior** — a lower
interior gap than English. Widened on the metric that needs no
`source_duration_s`:

| lang | n | gap frac of span | largest gap | words/sec in span |
|---|---|---|---|---|
| hi | 235 | 0.043 | 0.024 | 2.63 |
| en | 161 | 0.079 | 0.025 | 2.49 |
| **es** | 12 | 0.104 | **0.021** | **2.59** |
| ru | 5 | **0.281** | **0.096** | **1.63** |

**Within the speech span Spanish is normal** — same word density, same largest
gap, no dropout. The words are not missing; there is no speech there. Spanish
clips carry long non-speech heads and tails.

**The claim downgrades** from *"transcription destroys Spanish content"* to
*"these clips are ~46% non-speech at the edges and we drop it"*. Whether that is
correct (silence, rightly trimmed) or destruction (music/visuals the user wanted)
is exactly what VAD answers.

**RUSSIAN is the one that still looks like real dropout** — 0.281 gap fraction,
0.096 largest gap, 1.63 words/sec, all ~3× worse than every other language.
n=5, so a lead, not a finding.

## THE BLOCKER IS WORSE THAN "NOT PERSISTED"

`vad_coverage` **is** computed. `handler.py:33918` builds the three-field
language bundle — `detected_language`, `transcript_script`,
`vad_coverage_frac`, `vad_speech_s` — and its own comment says coverage
*"previously lived ONLY inside the coverage-gate trigger, unqueryable"* and that
the bundle *"flows into the success result payload"*.

**It does not. 0 of 3000 stored rows contain `_lang_bundle` or `vad_coverage`.**
It is written to `edit_plan` at line 33926 and **read by nothing** — grep returns
three hits, all writes. The plan is finalised ~17,000 lines earlier, so the
mutation almost certainly lands after the recipe has been persisted.

A feature built to make coverage queryable, which left it unqueryable, and whose
comment asserts a data flow nobody verified.
