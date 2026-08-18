# FILING — `emphasis_moments` derives a timestamp the validator calls "outside video" when it isn't

**Status: FILED, not chased.** Not harming users *today*: editorial is suppressed
on live traffic (`PROMPTLY_EDITORIAL_LIVE` off), so no user's job reaches this
path. **It becomes a user-facing defect the moment Step C flips that flag**, so
it is a Step-C precondition rather than a background item.

---

## The observation

Component-corpus probe, 2026-08-17, 3.7-flash @ thinking=2048, production config,
**serial** (so concurrency is excluded as an explanation):

```
RECIPE_INVALID: emphasis_moments[4] derived t=73.217s
                (from word_indices[0]=80) is outside video
  -> safe-edit fallback
```

| | |
|---|---|
| source | `comp_brand_copy_scenes_fe0d64fb` |
| source duration | **74.8s** |
| rejected timestamp | **73.217s** |
| rate in this corpus | **1 of 11 cells** |

**73.217 < 74.8.** The timestamp is inside the source, and the validator rejected
it as outside. Either the message is wrong or the bound is.

## Why this was invisible until now

The plan came back carrying `notes: "safe-edit fallback"` and nothing else, so
this looked identical to a capacity timeout. It is legible only because
`_mark_safe_edit()` shipped hours earlier and made every fallback name its own
door — this is that instrument's **first live catch**, and it separated a schema
failure from the capacity story I had wrongly told about Step A.

## The two candidate causes, neither yet confirmed

1. **CLOCK MISMATCH.** `emphasis_moments` are derived from `word_indices`, which
   index the *source* transcript, while the bound may be the *output* duration
   after cuts. On a 74.8s source cut down, a source-time of 73.2s legitimately
   falls outside the output — in which case the DERIVATION is wrong, not the
   plan, and the model is being blamed for our arithmetic.
2. **OFF-BY-ONE / TAIL BOUND.** `word_indices[0]=80` is a late word; the check
   may use a tail margin (last-word release, trailing pad) that makes the
   effective ceiling lower than the container duration.

These have different fixes and the message cannot distinguish them, which is the
same shape as the fallback-reason hole itself: a rejection that does not print
the bound it compared against.

## What to do, in order

1. **Make the message name its own bound** — print the compared ceiling and
   which clock it came from (`source` vs `output`). One line, and it converts
   the next occurrence from an argument into a read. Cheap, do it first.
2. Then decide which of the two causes it is, on evidence rather than reasoning.
3. **The check (Rule 1), named before the work:** a cert asserting every
   emphasis-moment bound check compares against a clock it names, so a future
   bound cannot be added that rejects a plan without saying what it measured
   against.

## Why it is not being fixed in this turn

The task in flight is the trigger-bearing Lumen render. Chasing this now would
mean editing the recipe validator while a render is queued against it, which is
exactly the tree-dirty mistake the freeze guard already caught once today. It is
filed with its reproduction, its corpus entry, and its named check.

**Blocking status: Step C should not flip until item 1 is done and the cause is
known.** A 1-in-11 silent downgrade to safe-edit is a quality regression that
would be invisible in production for the same reason it was invisible here.
