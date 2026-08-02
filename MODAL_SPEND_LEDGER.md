# MODAL SPEND LEDGER — Rule 8 (Zac 2026-08-01, after the $140 day)

**Before any agent fires Modal work it appends a line here stating the cost AND
the running cross-agent total. No agent spends past $5/session without Zac
saying so explicitly.**

The gap that produced $140: each agent priced its own runs and nobody summed
across agents. This file is the sum. It is worthless unless every agent appends
*before* firing, not after.

Columns: date · agent · app · what · tasks · container-seconds · $ · verified-0-tasks

| date | agent | app | what | tasks | cont-sec | $ | stopped? |
|---|---|---|---|---|---|---:|---|
| 2026-08-01 | prompt | `query-component-usage` ×5 | component-usage + events/25s audit, CPU-only read of `video_jobs.result.edit_recipe` | 5 | ~450 | ~$0.04 | yes (0 tasks) |
| 2026-08-01 | prompt | `plan-ab-propern` (aborted) | failed at LOCAL image build (missing `models/`) — **no containers started** | 0 | 0 | $0.00 | n/a |
| 2026-08-01 | prompt | `plan-ab-propern` | LEAN_SCHEMA re-test, 16 clips × 6 arms, PLAN_ONLY, cpu=8 mem=32GiB | 96 | ~28,800 est | **$8 stated / UNVERIFIED** | yes (0 tasks) |

**prompt agent session total: ~$8.04 by the stated figures.**

## Honest caveat on my own number — this is the Rule-8 gap in miniature

The `$8` for the A/B is the estimate **written in the harness file's docstring**
(`~16x6x$0.08`), which I inherited and repeated. I did not independently derive
it, and I have not reconciled it against Modal's billing.

Recomputing from the actual resource request — 96 tasks × cpu=8.0 ×
32 GiB, at an assumed ~300 s/task — gives ~230k core-seconds and ~922k GiB-seconds.
At cpu=8/32GiB the **memory-time term is large and the per-clip $0.08 figure does
not obviously account for it**, so the true cost may exceed $8. Treat $8 as a
lower bound until someone reads the per-app breakdown off the Modal dashboard.

**Lesson for the rule:** a cost estimate copied from a harness docstring is not a
priced run. Rule 6 says every Modal run carries a stated dollar figure *in
advance* — it has to be one the firing agent derived, from the actual cpu/memory
request and expected duration, or the number is decoration.
