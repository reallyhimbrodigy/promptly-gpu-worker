# 37% OF DELIVERED VIDEOS END MID-WORD

Zac noticed this by watching. It is real, it is measurable directly, and it is
not rare.

## THE MEASUREMENT

For every recent delivered video that stored word timings, take the FINAL cut's
`source_end` and ask where it lands in the transcript.

| | |
|---|---|
| videos checked | **27** |
| final cut lands **mid-word** | **10 (37%)** |
| ...inside a word that was deliberately REMOVED (correct) | **0** |
| ...inside a word the edit **KEPT** (defect) | **10** |

The removed-word control matters: the tail-pad extends past the last KEPT word,
so a cut landing inside a *removed* word would be correct behaviour. None of
them are. And 22 of the 27 jobs had no word removals at all, so there is nothing
to explain them away.

### The ten

| job | cut ends | straddles | |
|---|---|---|---|
| 92a38ffe | 11.96s | `आते` | |
| e634883c | 42.33s | `weekend` | |
| c37ec328 | 44.63s | `लेना` | |
| af3f6f45 | 86.06s | `छोड़ा` | |
| 8b64c69a | 6.70s | `दी` | |
| 42f89b95 | 19.47s | `लगेंगे` | |
| 083148dc | 29.16s | `letters` | |
| bb60521e | **20.00s** | `है` | round number — smells like an imposed limit |
| 516ca462 | 45.90s | `अब` | |
| 00deb10f | 42.77s | `videos` | |

## WHAT SEPARATES THE GOOD ONES FROM THE BAD ONES

The clean videos all end **0.50s PAST** their last word. The broken ones all end
**0.05–1.22s SHORT** of where the source speech ends.

| | median output | source speech left after the cut | last word ends a sentence? |
|---|---|---|---|
| clean (17) | 19.7s | **−0.50s** (pad applied) | **YES, 12/12 sampled** |
| mid-word (10) | 32.1s | **+0.30s** (speech abandoned) | **no, 0/8 sampled** |

That −0.50s is `_FINAL_TAIL_PAD_S` (handler.py:22262). It exists precisely for
this: *"the VIDEO's last word loses ~0.3-0.5s of audible release (cuts off the
last word)"*. On the clean videos it fires. On these ten it does not.

## WHY THE TAIL-PAD DOES NOT SAVE THEM

The pad extends from `raw_clips[-1]["padded_end"]`, which is the last KEPT
word's END. If the pad were the thing setting the final boundary, the cut could
not land mid-word — it would always sit on a word edge plus 0.5s.

So on these ten the final clip's end is being set **somewhere other than a word
boundary**, and the pad only ever extends (`if _new_end > _cur_end`) — it never
corrects a boundary that was already wrong.

`bb60521e` ending at exactly **20.00s** with 1.22s of speech remaining is the
tell: that is an imposed number, not a phoneme boundary. Candidate mechanisms to
check next, in order: a duration cap, `maxlength_violation`, and the
out-of-range clip path.

## WHY THIS OUTRANKS THE REST OF THE QUALITY LIST

A video that stops mid-thought is unpostable no matter how good the rest is.
It is also the cheapest class to be certain about — unlike caption legibility or
density, this one is *decidable*: a cut either lands on a word boundary or it
does not.

**Proposed invariant:** the final clip's end must land on a KEPT word's end plus
the tail-pad, or on the true video end — never inside a kept word. That is
gateable, and it is the Rule-1 check this fix should ship with.

## Method, and its one limit

`video_jobs.transcript.words` (Deepgram start/end per word) against
`edit_recipe.plan.cuts`, taking the cut with the greatest `source_end`. Both are
in source-time seconds, so they are directly comparable — no inference.

⚠️ Limit: only standard-editorial jobs store a transcript, so this is measured on
the routes that HAVE one. The light routes store no transcript at all and cannot
be checked this way. This is a timing measurement, not a listening test — it
proves the cut lands inside a spoken word, which is the thing Zac heard.
