# DEPLOY LOG — quality agent

Zac 2026-08-04: **every push to main orphans the jobs in flight.** So each deploy
is announced here with its window, and the orphans inside it are attributed to
the deploy rather than counted as a mystery class.

## My deploys, 2026-08-03/04 (8, and 5 of them inside 56 minutes — too fast)

| commit | deploy ≈ (UTC) | carried | orphans |
|---|---|---|---|
| `fe15996` | 00:18 | SafeImg, 15 tag sites, entrance+zoom caps, pre-extract, RENDERCLOCK | 0 |
| `bbff11a` | 01:01 | removed the two false taste signals | 0 |
| `2e65292` | 03:37 | export-weighted style profile | 1 |
| `8360a93` | 06:05 | mid-word fixed-point snap | 1 |
| `6b3ece7` | 06:22 | source clamp on the snap | 1 |
| `c830895` | 06:41 | two-lists diagnostic | 3 |
| `baac8aa` | 06:52 | **merge of zero-reject-routing** (109 commits) | 1 |
| `8bb72c7` | 07:01 | truncate-never-pad + gate | 1 |

**7 jobs / 7 users plausibly orphaned**, against 54 failed / 406 jobs since
00:00Z (50 distinct users failed). So my cadence accounts for **7 of tonight's
50 failing users — 14%.** Real, and mine.

⚠️ My first cut of this said **51**. It was contaminated: `completed_at` is NULL
on failed jobs, so "in flight" swept in every past failure and grew
monotonically across the windows — the accumulating-set signature. The clean
cohort requires the job to have STARTED within 20 minutes before the deploy and
to have died AT OR AFTER the deploy instant.

## The rule I am now on

1. **Batch.** One deploy carrying three fixes, not three deploys. The four
   deploys between 06:05 and 07:01 should have been one.
2. **Announce the window** before pushing, so the orphans are attributed.
3. `6b3ece7`, `c830895`, `baac8aa`, `8bb72c7` were each individually justified
   and collectively indefensible. The merge was genuinely urgent; the other
   three were not, and could have ridden with it.
