# FILING — the canonical flag set lives in four places

**Status: FILED, not fixed.** A track that discovers a defect files it and does
not chase it, unless it is actively harming users right now. This is not:
the equality of the two load-bearing mirrors is already gate-enforced, and the
gate caught the drift it exists to catch on 2026-08-17, in the same hour it was
introduced. This filing is about the cost of the arrangement, not an outage.

---

## The four surfaces, as measured 2026-08-17

| # | surface | keys | role | who catches drift |
|---|---|---|---|---|
| 1 | `validate_deploy.CANON` | **30** | asserted values; the declared truth | itself, at deploy |
| 2 | `validate_deploy.CANON_PENDING` | **2** | live, unasserted, decision filed with the owner (`PROMPTLY_SILENT_TO_MOODREEL`, `PROMPTLY_STRUCTURE_ABORT`) | the no-unregistered-flag check |
| 3 | `modal_app._CANON_FLAGS` | **30** | the DAILY drift sentinel reads this | ast-compared against #1 at deploy |
| 4 | `secret_flags_readback.FLAG_KEYS` | **26** | vestigial: a minimum-presence floor only | nothing — and it does not need to |
| — | the live `promptly-lang-flags` secret | **32** | what production actually runs | #1 + #2, at deploy only |

30 + 2 = 32 reconciles exactly against the live secret. **Nothing is currently
wrong.** The counts agree, the mirrors are equal, and `FLAG_KEYS` is documented
as a floor rather than an enumeration.

## What it has cost, twice

**2026-08-11** — `FLAG_KEYS` declared 26 keys while the secret held 31. The
documented flip procedure built its restate from that list, so
`modal secret create --force` would have **deleted five live production flags**
while reporting success. Fixed by making the readback report every `PROMPTLY_*`
key the container actually receives; `FLAG_KEYS` was demoted to a floor.

**2026-08-17** — Step B registered `PROMPTLY_EDITORIAL_MODEL` in #1 and the
deploy failed on #3: two hand-maintained copies of one value set. The gate did
its job. But the fix was to type the same line into a second file, which is the
definition of a mirror rather than a source.

Both are the same shape as the three `extra="forbid"` schema mirrors and the
`types.ts` caption mirror: **a value with more than one home drifts, and the only
question is whether a gate is watching the moment it does.**

## Proposal — one source, two readers

Move the asserted values into a single data file (`canon_flags.json`), read by
both #1 and #3.

```
canon_flags.json          <- the ONLY hand-edited home
  ├── validate_deploy.py  reads it for the deploy-time gate
  └── modal_app.py        reads it for the daily drift sentinel
```

**Why this is not a two-minute change, and why it is filed rather than done:**

1. `modal_app.py` is the **deployed image's entrypoint**. Adding a file read at
   import time means the file must be mounted into the image, and a missing
   mount becomes a startup failure on every container rather than a red gate.
   The deferred-import → image-mount law applies directly.
2. The daily sentinel runs inside `prewarm_janitor`, so the read must survive a
   container that has the secret but may not have the repo layout the local gate
   assumes.
3. It touches the deploy gate and the deployed app **in one change**, which is
   exactly the shape that wants its own quiet window and its own RED proof
   rather than riding an unrelated batch.

**The check that would make the regression impossible** (Rule 1, so it is named
before the work starts): the existing ast-comparison stays, and gains a third
assertion — that neither file contains a *literal* flag dict at all, so a future
edit cannot reintroduce a hand-maintained copy alongside the shared one. Without
that, consolidation just adds a fifth surface.

## Recommended disposition

**Low priority, non-blocking.** The equality is gate-enforced and the gate has a
100% catch record on this class (2 for 2). The real win is removing the
hand-copy step from a procedure that touches production secrets — worth doing on
a quiet window with nothing else in the batch, not worth interrupting the
editorial-flip sequence for.

`FLAG_KEYS` (#4) should be **deleted** in the same change: it is the surface that
caused the only genuinely dangerous incident of the three, it no longer
enumerates anything, and a floor that lags by 6 keys is not a floor.
