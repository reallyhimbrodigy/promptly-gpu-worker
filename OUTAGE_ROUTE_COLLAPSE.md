# LIVE DEGRADATION — both premium routes are extinct, and still are

**Found by TRUTH, 2026-08-11 17:0xZ, while attempting to verify outage recovery.
This is not resolved. It is ongoing as of the most recent completion.**

## The finding [MEASURED]

`moodreel` and `hype` — the two premium routes — went to **exactly zero** on
2026-08-09 and have stayed zero for three days.

| day (UTC) | completions | moodreel | hype | minimal |
|---|---|---|---|---|
| 2026-08-04 | 776 | 180 | 17 | 43 |
| 2026-08-05 | 241 | 69 | 4 | 7 |
| 2026-08-06 | 199 | 74 | 4 | 4 |
| 2026-08-07 | 461 | 132 | 11 | 8 |
| 2026-08-08 | 455 | 73 | 6 | 59 | ← Vertex 403 begins 11:16Z |
| 2026-08-09 | 282 | **0** | **0** | 82 |
| 2026-08-10 | 273 | **0** | **0** | 100 |
| 2026-08-11 | 130 | **0** | **0** | 40 |

**Clean-cohort cut** (pre-outage window ends at the 11:16Z incident start):

- **BEFORE** — Aug 5 → Aug 8 11:16Z: n=1,174 completions, moodreel 346 + hype 25
  = **31.6% of completions were premium routes**.
- **AFTER** — Aug 9 → now: n=685 completions, moodreel **0**, hype **0**.

**Lead with users (Rule 7):** **643 distinct users** had a completion in the
AFTER window; **219 distinct users** received `minimal` (222 jobs). At the
measured 31.6% pre-outage premium share, **roughly 200 users [INFERRED from a
MEASURED share] received a visibly lesser edit than they would have** — a
cinematic mood-reel replaced by the minimal route.

The substitution is near-exact: `minimal` rose from 4–8/day pre-outage to
40–100/day after. Moodreel's traffic is landing in minimal.

## Mechanism [INFERRED, consistent with every measurement]

`PROMPTLY_MOODREEL="1"` and `PROMPTLY_HYPE_MODE="1"` are both **live and
correct** in the secret [MEASURED — 2026-08-09 readback]. So this is not a flag
regression. Route *detection* depends on the Gemini/Vertex leg; with Vertex
returning 403, detection fails and the documented behavior is **"every miss
fail-safes to minimal"**. That is precisely the observed shape, and the cliff
lands on the incident date.

**Prediction to falsify:** the moment GCP billing is restored, moodreel/hype
should reappear within one traffic hour **without any deploy**. If they do NOT,
the cause is *not* billing and this becomes a separate P0 — the fail-safe would
be stuck.

## Why nobody knew

This is the house failure mode in its purest form: **nothing failed.** Every one
of those 685 jobs returned `completed` with a playable video. No error rate
moved. The product silently got worse for ~200 users and the only way to see it
was to cut completions by route.

This is exactly **alarm B** in the sentinel spec already filed to JUDGE
(`reports/SENTINEL_SPEC_FOR_JUDGE.md`): *moodreel completions = 0 over 6h while
moodreel-eligible jobs > 5*. It would have fired on 2026-08-09, three days ago,
instead of being found by hand today. The backtest requirement in that spec is
now a **hard** requirement: the sentinel must fire against this window.

## Probe-collapse warning attached to this finding

My first two attempts to measure recovery were **vacuous** and would have
reported false good news:

1. Substring-searching `result` for `safe_edit_fallback` → 0 matches. Looked
   like recovery. In fact that marker appears in **no** window, including the
   known-bad one — the column does not carry it.
2. Same for `gemini_n_calls` → absent everywhere.

Only after dumping the real `result` keys (`route`, `route_reason`, …) and
re-cutting did the true signal appear. **Every recovery check in this incident
must be validated against the known-bad window before its zero is believed.**
