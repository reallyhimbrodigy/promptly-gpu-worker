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

---

# BUILD STATUS — 2026-08-25, all three items built and gated

## (1) Stall experiment — BUILT, DARK, committed `e20ef03`

`PROMPTLY_MIDSENTENCE_STALL_S`, default **0.70 = unchanged**. Bounded to
`_WITHIN_CLIP_TRIM_TRIGGER_S < v <= 2.0`, so a value under the locate bar
cannot silently turn the gate into a no-op and read as "the model refused
everything". Verified dark: unset/0.02/9.9/garbage all resolve to 0.70.

**Scoped to TWO sites, and that is the design.** `_MIDSENTENCE_STALL_S` has
four read sites; only two are the SAME DECISION — the detector's offer gate
(11096) and the downstream trim filter (27306), which re-applies an identical
test. Moving only the first raises `offered` while the cut still never happens:
the experiment reads as a null for a wiring reason and we conclude the constant
is not the lever. The connector-word rule (10400/10401, dead air on BOTH sides)
is a different question and stays on the fixed constant, so the arms differ in
exactly one way.

**The third number now exists.** `dead_air_spans_preserved` was NOT persisted —
only located and offered were. Without it the pre-registered falsifier ("if
preserved rises in lockstep with offered, the model is being handed spans it
doesn't want") could not be evaluated at all. Counted from the PARSED set, not
`len(preserved_silences)`: a duplicate or unparseable entry would inflate the
raw list while changing nothing downstream.

**The arm is on the row** (`midsentence_stall_s`). Modal mounts secrets at
CONTAINER START, so after a flip production runs both arms at once and a cut by
timestamp is a mixture, not a cohort.

Read with `./run_modal.sh query_stall_arms_app.py`. It reports the
arm-invariance self-check FIRST (`located` must not move between arms; if it
does, nothing below the line is readable), then `offered/located` and
`preserved/offered` per arm, per job AND per user, excluding pre-deploy rows
explicitly rather than folding them in as a control.

## (2) `ladder_exhausted` — BUILT

A ladder exhausting itself is a design outcome, not a crash. It was landing in
`RENDER_FATAL/unclassified`, the top unnamed class by users.

**Ordering is the whole design.** The ladder's terminal raise embeds the
underlying error inside its own message, so every named mechanism is reachable
THROUGH the ladder prefix — two of `validate_deploy`'s pinned real jobs
(`frame_grid`, `no_video_stream`) arrive carrying it. Placed anywhere but LAST,
`ladder_exhausted` steals them and reports a design outcome where a real cause
was sitting in the same string. Those two pinned jobs are the RED-proof:
promoting the subcode breaks them.

**It carries its cause** (`ladder_exhausted:TypeError`). A bare subcode would
absorb every never-before-seen render failure into a name we already understand
and silence the unnamed-shape detector this file explicitly relies on — while
reading as an improvement.

## (3) `offthreadVideoThreads` — the evidence path, BUILT

It was never unreadable. `render-full.mjs` prints the value it used, but that
print lands in the BURST container while the orchestrator's tee captures the
orchestrator — twice the instrument was pointed at the wrong process, and twice
"no evidence" was indistinguishable from "no effect". The value was in
`_r.stdout` the whole time; `subprocess.run` captures it.

It is now parsed onto the job row as `render_offthread_threads` /
`render_concurrency` / `render_legs_reporting`, nested under `stage_timings`
(which is in the write allowlist). A DB question on every job forever, with a
denominator, instead of a log hunt that has now failed twice. A `2` in that
column means the lever is NOT in force — which is the reading this settles.

## The twelfth built-not-wired instance, found while doing the above

Six certs — 77 assertions — were registered NOWHERE: not in `validate_deploy`,
not in `deploy.sh`. They only ever ran when an agent typed the filename. Rule 1
says every fix ships a check that makes its regression impossible, and a cert
nobody runs makes nothing impossible. Now registered in the gate with their
PASS COUNTS asserted, so a check deleted to make a red cert green fails the
deploy instead of reading as a fix.


---

## FIELDS THIS PRE-REGISTRATION READS

Declared because prose describing a falsifier looks identical whether or not
anything writes the field — which is how `preserved` was specified, costed into
a two-arm design, and never persisted. `cert_falsifier_readable.py` refuses any
field here that handler.py does not actually WRITE (checked against the AST of
the persist site, not a grep: `_v2_counts` was computed, certified, and eaten in
transit by a `k.startswith("_")` sanitiser).

```reads
stage_timings.dead_air_spans_located
stage_timings.dead_air_spans_offered
stage_timings.dead_air_spans_preserved
stage_timings.midsentence_stall_s
```

`located` is the arm-invariance self-check, `offered/located` is the gate the
constant moves, `preserved/offered` is the FALSIFIER, and `midsentence_stall_s`
is the arm the cohort is cut by — without it a post-flip window is a mixture of
both arms, not a cohort.
