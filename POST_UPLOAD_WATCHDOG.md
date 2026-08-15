# POST-UPLOAD WATCHDOG — spec `[Law 1, Law 2]`

**Root-independent by design.** It captures the cost and the latency of the hang
class **without knowing why the worker hangs**, so it ships now rather than
waiting on a root cause that may take another week.

---

## THE STATE IT FIRES ON

Exactly one, and both conditions are required:

```
the rendered artifact IS confirmed in S3      (the user's video exists)
AND the terminal write has NOT landed         (the row still says processing)
AND that has been true for N seconds
```

That is precisely the envelope-loss cohort: **180/180 had `worker_started_at`,
180/180 had a delivery column, and 0/180 carried the worker's envelope.** The
render succeeded; only the write is missing.

## WHY EXITING IS SAFE — the recovery path already exists

Force-exiting a container that has not written its terminal would normally orphan
the job. It does not here, because the **evidence-triggered repair shipped on
2026-08-15** already handles exactly this row:

> a NON-terminal row that has gone quiet, with a playable render in S3, is
> repaired immediately — `completion_delivery='repair'`, URL and terminal written
> together, and the dispatcher's pending promise settled.

So the watchdog hands off to a recovery path that is already live and already
gated. **The artifact-in-S3 precondition is what makes the exit safe** — without
it, exiting would strand a user with nothing.

## WHAT IT DOES, IN ORDER

```
1. after the upload confirms the artifact in S3, arm a timer for N seconds
2. the terminal write lands  -> disarm. Normal path, no log, no exit.
3. N seconds elapse, no terminal:
     a. LOG LOUDLY, grep-stable:
        [post-upload-watchdog] job=<id> artifact=<key> waited=<N>s
        terminal=NOT-LANDED — forcing exit; the row is repairable from S3
     b. emit analytics_events `post_upload_watchdog_fired`
        {job_id, waited_s, artifact_key, last_stage, container_age_s}
     c. NO last-chance terminal write — see below; the deploy gate killed it
     d. os._exit(0) — immediate, no atexit, no thread join
```

**`os._exit`, not `sys.exit`.** A hung worker is hung *somewhere*; a normal exit
runs interpreter shutdown, joins threads and can block on the very thing that is
stuck. The ThreadPool exit-tail class is already on the record here: a 30s billed
tail that `shutdown(wait=False)` and daemon threads did **not** fix, because the
tail was a BUSY worker. `os._exit` is the only exit that cannot be blocked.

**Exit code 0, deliberately.** The render succeeded and the artifact exists —
this is a *write* failure being contained, not a render failure. A non-zero exit
would make Modal retry semantics and the failure taxonomy read a successful
render as a crash.

### THE LAST-CHANCE WRITE WAS REMOVED, AND THE GATE IS WHY

This spec originally had the watchdog fire one last
`write_job_status(status="completed")` before exiting. On implementation,
validate_deploy's existing **"minimal completed write lost its route contract"**
check failed immediately — and it was right.

The timer thread has **no access to `result_payload`**, so the only completion it
could write is a **bare** one: no `route`, no `route_reason`, no floor markers,
no vocab. **The watchdog would have manufactured the exact thin-envelope defect
it was built to cap.**

It now records `terminal_write_attempted: false` with the reason, and leaves
recovery to the repair path, which writes the URL and the terminal together from
S3 evidence. A pre-existing gate, written for a different reason, caught a
new defect in the thing meant to fix that class.

## CHOOSING N

| candidate | argument |
|---|---|
| 60s | aggressive; risks cutting a slow-but-working terminal write |
| **120s** | **proposed** — 30 missed 4s heartbeats, the same bar the quiet-row repair already uses, so the two agree by construction |
| 300s | safe but leaves ~5 min × 16 cores of the very waste being targeted |

**120s**, matching `QUIET_ROW_REPAIR_MS`. Two mechanisms firing on the same
threshold cannot disagree about whether a row is quiet.

## THE PRIZE, AND ITS HONEST BOUND

If the hang fit holds (60 jobs/day × ~900s at cpu=16), capping at 120s recovers
roughly **(900 − 120) / 900 ≈ 87%** of that waste:

| | |
|---|---|
| hang class, if the fit holds | ~$14.7/day ≈ $440/mo |
| recovered by a 120s cap | **~$12.7/day ≈ $380/mo** |
| latency, same cohort | 304s / 904s → **~120s + repair** |

**The fit is not yet confirmed** — `worker_envelope_write` at n≥100 and the
container-lifetime sample are the confirming reads. But the watchdog is worth
shipping *even if the fit is wrong*, because its cost when the class is rare is
zero: it never fires on a healthy job.

## RULE 1 — THE CHECKS

1. **Never fires without the artifact.** No S3 object → no exit, no log. A
   watchdog that exits on a job with nothing in S3 destroys the user's render.
2. **Never fires after the terminal lands.** Disarm must be unconditional.
3. **`os._exit` specifically** — asserted by source, because a well-meaning
   refactor to `sys.exit` silently restores the blocked-shutdown failure.
4. **Exit code 0** — asserted, so a write failure is never classified as a crash.
5. **N is bounded** — ≥60s (many missed heartbeats) and < the container timeout
   it exists to pre-empt.
6. **RED-proven via `red_proof.py`**, so the proof cannot pass for the wrong
   reason.

## WHAT IT IS NOT

**It is not the fix.** It is a cost and latency *cap* on a class whose root is
still open. When the root lands, the watchdog should stop firing on its own —
and its `post_upload_watchdog_fired` rate is exactly the meter that proves the
real fix worked.


---

# JUDGE'S QUESTION, ANSWERED FROM THE ROWS — 2026-08-15

**"What distinguishes a job that settles at 180-240s via reconciler from one that
settles at ~904s via repair, given both are 100% envelope-absent?"**

**Answer: nothing in the rows does.** Measured on the clean post-migration
cohort (reconciler n=156, repair n=24), every persisted field is identical:

| field | reconciler | repair |
|---|---|---|
| `current_step` | complete 156/156 | complete 24/24 |
| `progress` | 100 | 100 |
| `render_frames` | **null 156/156** | **null 24/24** |
| `partial_state` | null | null |
| `rendered_video_url` | 156/156 | 24/24 |
| queue delay p50 | 145s | 157s |
| **settle p50** | **304s** | **904s** |

Queue delay is not the discriminator (145 vs 157s), confirming JUDGE's read.

## The one real signal: `phase`

- reconciler: **156/156** `"Your video is ready!"` — perfectly uniform
- repair: 21/24 the same, but **3/24** stuck at `"Finalizing your video"` /
  `"Finalizing"`

Those three workers **died earlier in the pipeline**. The other 21 reached the
final progress push and still never wrote a durable result.

## What this means, and it is structural

`phase` is the worker's last *progress* push; the durable result is a *separate*
write. So 153 of 156 reconciler jobs and 21 of 24 repair jobs got their **last
progress message out** and then failed on the **result write specifically** —
not on rendering, not on uploading, not on progress.

The two clusters are therefore the same worker failure, separated only by
**which recovery layer reached them first**:

- **reconciler at ~304s** — the completion POST landed, so the dispatcher's tail
  wrote the row, and the `_delivered` shape bug then stamped it `reconciler`.
- **repair at ~904s** — nothing landed, so the 15-minute timer fired and the
  repair wrote the row from S3.

**The discriminator is the completion POST, and it leaves no trace on the row** —
which is exactly why the rows cannot separate them, and why `render_frames` being
**null in 180/180** is the loudest fact here: the frame watcher never wrote
either, on any of them.

## What will separate them

- `worker_envelope_write` — an **absent** event means the worker never reached
  its result write at all.
- the watchdog's **`last_stage`** field — designed for precisely this question,
  and it reports the stage the worker was in when it stopped.

Both are live. Neither needed a new instrument invented for JUDGE's question;
the question named what the existing ones already measure.


---

# CORRECTION 2026-08-15 — the watchdog as first shipped could not fire

**The disarm was placed BEFORE `write_job_status`, not after.** So a terminal
write that HANGS — the exact failure this exists for — had already cancelled the
watchdog. It passed every "is it wired?" check while being unable to fire on its
own target.

```
BEFORE (broken)              AFTER (correct)
  disarm()                     write_job_status(...)   <- may hang
  write_job_status(...)        disarm()                <- only once it RETURNS
```

**It keys on the WORKER'S OWN terminal-write state, never on the row's.** That
distinction is load-bearing: if it keyed on the row, the reconciler rescuing a
job at ~304s would silently disarm the watchdog on a container that is still
hung, and the cost would keep burning with the watchdog reporting success.

**Gated by AST**: no disarm may immediately precede a terminal
`write_job_status(status="completed")`, and every one must have a disarm within
six lines *after* it returns. RED-proven by moving a disarm back to the
pre-write position — gate exit 1, naming the line.

## Also corrected: `render_frames` is vestigial

Dropped from the analysis. It is null in **0/293** and **0/183** — it never
writes on any job, healthy or not, so its absence in the envelope-lost cohort
distinguishes nothing. I cited it as "the loudest fact"; it was noise.

## The two-channel instrument

Progress pushes (HTTP → content-studio) LAND while direct DB writes (HTTPS →
Supabase/PostgREST) do not, **on the same job, from the same container**.
Different channel, different outcome — so the worker's DB client is the suspect
and now reports on itself:

| field | why |
|---|---|
| `db_write_ms` | a write that dies after 30s and one that dies instantly leave the SAME row |
| `db_write_slow` | >5s, the existing wedge bar |
| `is_timeout` / `is_connection` | names the channel failure instead of leaving it to be grepped out of `error_detail` |

The timer is hoisted above the `try` so the **except** path can time a failed
call too — otherwise the only writes we could measure would be the ones that
worked.
