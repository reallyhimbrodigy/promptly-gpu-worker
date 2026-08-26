# NEXT SESSION — first two items, in order

Filed 2026-08-25. Both are small, both measure themselves, and both came out of
the dead-air three-field split on its first render.

---

## (1) `_MIDSENTENCE_STALL_S` — a FLAGGED EXPERIMENT, not a silent change

**The finding.** Exactly one gate sits between `dead_air_spans_located` and
`dead_air_spans_offered`:

```python
_DEAD_AIR_LOCATED[0] += 1
if (_punctuated and not _sentence_final_word(words[a])
        and silence_in_gap < _MIDSENTENCE_STALL_S):
    continue
out.append({...})
```

```
_WITHIN_CLIP_TRIM_TRIGGER_S = 0.03   (30ms)   LOCATED bar
_MIDSENTENCE_STALL_S        = 0.70   (700ms)  OFFERED bar, mid-sentence only
```

A sentence-final pause qualifies at **30ms**; a mid-sentence pause must reach
**700ms** — a **23x** difference. Natural mid-sentence pauses run 100-400ms and
sit entirely inside that dead zone. Measured on a fully-punctuated English
source: **13 of 20 spans dropped, 65%**, never reaching the model.

This is NOT the Arabic gate. `_punctuated` was TRUE, so the gate was fully
armed. The Arabic fix DISARMS it when an ASR does not punctuate; on punctuated
transcripts it fires at full strength. That is why edits come out thin.

**The build.** `PROMPTLY_MIDSENTENCE_STALL_S`, DARK, defaulting to 0.70 so the
deploy is inert. Arms: **700ms (control) vs 250ms**.

**It measures itself — the counters already exist.** Report per arm:

```
located -> offered -> preserved
```

`located` is arm-invariant (it is counted before the gate), so it is the
denominator that proves the arms differ for the RIGHT reason. `offered` should
rise on the 250ms arm; if `preserved` rises in lockstep, the model is being
handed spans it does not want and the constant is not the lever.

**Do NOT change the constant silently.** 700ms is a taste call about how much
mid-sentence breathing to remove, and the reference corpus can now inform it
(`cuts_per_s`, `first_visual_change_s` per reference) instead of it being
guessed. The experiment produces the number; the owner makes the call.

---

## (2) `ladder_exhausted` subcode + its gate assertion

**The finding.** `RuntimeError @ handler.py:33716 in _render_degrade_ladder`,
message *"degrade ladder exhausted with no input-differing rung"* —
**5 users, 12 jobs, 2.4 jobs/user.**

That is the ladder COMPLETING its designed sequence and finding nothing left to
try. It is not a crash. Filed today as `RENDER_FATAL / unclassified`, which
inflates the crash rate with a design outcome and hides the real question: why
the ladder runs out on those inputs.

**2.4 jobs per user is the worst retry multiplier in the entire failure set**
(everything else is 1.0-1.3). Five users each hitting it repeatedly is the
signature of someone retrying into a DETERMINISTIC DEAD END — a worse experience
than a clean failure, because the product looks flaky rather than honest.

**The build.**
- Distinct `error_subcode = "ladder_exhausted"` at that raise site.
- Re-run the by-users ranking and confirm `RENDER_FATAL / unclassified` drops to
  its residue rather than staying flat (which would mean the subcode is not
  reaching the row).
- **A gate assertion**, because this class silently merging back into
  `unclassified` is exactly how it hid for a week. Rule 1: name the check or the
  fix is not finished.
- The user-facing half is separate and worth stating: a deterministic dead end
  should stop inviting a retry. That is a product decision, not a subcode.

---

## Context: the full failure ranking that produced both (7d, by USERS)

```
UPLOAD_NEVER_STARTED                 94 users  116 jobs  1.2   72% of affected users
INTEGRITY_TRIP / freeze              11         13       1.3
WORKER_DIED                           9          9       1.0
RENDER_FATAL / unclassified           5         12       2.4   <- (2) lives here
INTEGRITY_TRIP / dead_moment          3          5
CLIP_TOO_SHORT                        3          3
UNKNOWN / unclassified                2          3
INTEGRITY_TRIP / black                2          3
JOB_STALLED · RECIPE_INVALID · RENDER_REMOTION/component_crash
  · EDITOR_GENERIC · DISPATCH_UNREACHABLE       1 user each

13.7% of jobs failed · 131 of 1027 users hit a failure
```

`result.error_class` and `result.error_where` were populated the whole time —
"RuntimeError, 39 across 26 users" was never one family but **seven distinct
raising sites**, five of them inside `render_stage` at different lines. Nobody
had read the field.
