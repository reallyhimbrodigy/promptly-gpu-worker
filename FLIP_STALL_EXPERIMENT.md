# FLIP FILING — `PROMPTLY_MIDSENTENCE_STALL_S`

**Filed 2026-08-25 by BUILDER.** `secret_flip.py` enforces the mechanics but
records no authority; this file is the authority record, per the secret-auth law.

## Authority

**Explicit owner GO, key named:** *"arm the stall experiment:
PROMPTLY_MIDSENTENCE_STALL_S at 250ms against the 700ms control, dark-flag split
so both arms run on live traffic. Name the key explicitly in your readback per
the secret-auth law."*

| | |
|---|---|
| key | `PROMPTLY_MIDSENTENCE_STALL_S` |
| value | `"0.25"` (exact string) |
| secret | `promptly-lang-flags` |
| write | 34 → 35 keys, **0 lost, 1 gained**, confirmed by a second independent readback |
| CANON | registered in `validate_deploy.py` in the same change (`secret_flip.py` refuses `--add-new` otherwise) |
| rollback | same key → `""`, + redeploy. Every job returns to 700ms; nothing else reads it |

## What was corrected before shipping

The instruction said *"dark-flag split so both arms run on live traffic."* The
flag as built could not do that. `_midsentence_stall_s()` read the env var
directly, which yields **one value per container** — setting it would have put
**100% of traffic on 250ms**, a before/after against yesterday.

The only concurrency a flip produces is the warm/cold container mixture in the
window after it, and **container age correlates with load and time of day**.
That is a confound, not an arm. It is the same shape as the proxy-fps read that
came back at −34.3% against a predicted −36% and was pure noise — the dangerous
kind of wrong, because it AGREED.

So the flag is now a **per-job 50/50 split** on `sha256(job_id)`:

- both arms run **concurrently**, on the same traffic, in the same hours
- **deterministic on `job_id`** — a retried job never changes arms. A flipping
  retry would attribute one job's spans to BOTH arms and silently break the
  per-user cut, which is the cut that decides this (Rule 7)
- resolved **once** per job, beside the other per-job resets, so no job can be
  measured under two values
- an unidentifiable job goes to **control**. Never put a job we cannot attribute
  into the experimental arm
- out-of-range, unparseable, or below-the-locate-bar values all fall back to
  0.70. A value at or under the locate bar would make the gate a no-op and read
  as *"the model refused every span"* rather than *"the gate stopped gating"*

Measured before shipping: 4,000 synthetic ids → 49.1% experimental, dark when
unset, stable across 50 repeats of the same id.

## The read — and the ONE outcome that kills the premise

`located → offered → preserved`, **per arm and per user**, cut by the persisted
`midsentence_stall_s` on the row, never by clock.

**Arm-invariance is the self-check and is reported FIRST.** `located` is counted
after the silence bar and BEFORE the linguistic gate, so the constant cannot
touch it. If `located` differs materially between arms, the cohorts are not
comparable and nothing below that line is readable.

**THE FALSIFIER, stated before the arms ran:** if `preserved` rises in **lockstep**
with `offered`, the model is being handed spans it does not want and **the
constant is not the lever**. The rate that decides it is `preserved/offered` —
flat while `offered` rises means the extra spans are being accepted; climbing
with it means they are being refused.

This is readable for the first time. `preserved` was specified as the falsifier
and **was never persisted** — the experiment as originally specified would have
run, cost two arms of real traffic, produced a clean-looking `located → offered`
table, and been structurally incapable of refuting its own premise. See
`cert_falsifier_readable.py`.

## Not decided here

**700ms vs 250ms is the owner's call.** This filing reports numbers and no
recommendation.

## This entry has an end

`CANON` now asserts a live production value that is a **time-boxed experiment**.
When the read lands, one of two things must happen — leaving it armed is not one
of them:

1. the owner picks 250ms → it becomes the constant, and the flag **and the
   split** are deleted, or
2. it reverts to `""`.

An experiment left armed becomes an unowned production value that nothing is
watching for correctness, only for drift.
