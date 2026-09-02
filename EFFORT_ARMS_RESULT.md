# EFFORT ARMS — 2026-09-01, both with C1-C6 in the prompt

Same source (`625dfdc5-73s.mp4`), same brief, knowledge=ON, `claude-sonnet-5`.
One variable: `output_config.effort`. Sonnet 5 runs **adaptive thinking when
`thinking` is omitted**, which this app does — so `effort` is the lever on it.

| | effort=medium | effort=high (default) |
|---|---|---|
| **wall** | **158.4s** | **371.5s** |
| cost | $0.4748 | $0.8900 |
| turns | 15 | 29 |
| shell commands | 10 | 25 |
| **kept_ratio** | **0.889** (OK) | **0.813** (OK) |
| **placements declared** | **6** | **15** |
| text /25s (ref 7.56) | 2.1 (n=5) | **5.53 (n=13)** |
| **cards /25s (ref 2.57)** | **0.0 (n=0)** | **0.43 (n=1)** |
| method | 6 ffmpeg / 0 remotion | 14 ffmpeg / **1 remotion** |
| remotion renders ran | 0 | **1 (probe comp)** |
| output share of cost | 40.2% | 39.0% |
| failure ledger | 0 | 0 |

## The trade is real — medium is NOT free

`effort=medium` more than halves wall (−57%) and nearly halves cost (−47%), but
it costs **placement density**: 6 declared vs 15, text 2.1 vs 5.53 per 25s, and
**zero cards vs one**. On the axis this lane exists to move — a DIRECTED edit,
not cuts-plus-captions — high is the better editor and medium is the cheaper one.

`kept_ratio` moves the other way (0.889 medium vs 0.813 high): the high arm cut
more aggressively. Both pass the ≥0.8 bar, both VERDICT OK.

**Against the 262s baseline: medium is −39.5%, high is +41.8%.** I do not have
the baseline run's `effort`, so that comparison cannot be attributed cleanly to
one variable — it is reported as given, not as an ablation.

## The arm did NOT move the term it targeted

Output share was ~42% before and is **40.2% / 39.0%** across both arms — noise.
The share is structural, not a thinking-depth artifact. At effort=medium:

| term | $ | share |
|---|---|---|
| output | 0.1910 | 40.2% |
| **cache_write** | **0.1592** | **33.5%** |
| cache_read | 0.1246 | 26.2% |
| input | 0.0001 | 0.0% |

Output bills at 5x input, so it stays the largest single term at any effort.
**The next cost lever is cache_write (33.5%)** — the rolling breakpoint
re-writing the tail every turn — not thinking depth. Caching itself is already
working: 415,223 of 415,253 input tokens were cache reads (99.99%).

## C1-C6: EXERCISED AND CLEAN at effort=high, NOT exercised at medium

The medium arm placed no component at all, so its clean ledger says nothing
about the constraints — absence rendered as success. The high arm actually ran
the path:

- `remotion render` ran once, on a **probe** composition (`probe_comp: 1`).
- **C2 followed, observed in the command log**: `colorkey=0x808080` present,
  `mg_keyed` written and composited, `qtrle` encode. The grey field was keyed
  out — the failure this constraint exists to prevent did not happen.
- **C3 followed**: zero occurrences of `--codec=prores` / `yuva444p10le`.
- **C1 not violated** — `c1_violation_60fps_probe` did not fire.

**LIMIT, stated: I cannot confirm from the log WHICH probe composition ran.**
The command-log printout truncates at 112 chars (`_one[:112]`) and cuts the
composition name off. `c1_violation` not firing is consistent with either
`MGCraftProbe30` (C1 obeyed) or `FrameCompProbe` (which C1 does not govern).
Fix the instrument before the next arm: log the composition explicitly.

## The escape hatch is still open — and it is the real finding

C1-C6 govern **HOW** to render a card. **Nothing makes the card exist.** The
mandatory rule is conditioned — *"if you place a CARD whose hero is a NUMBER"* —
and the agent can decline to ever place one. At medium it declared 5/5
`overlay_text` including `'3 YEARS UNEMPLOYED'` and `'INSURANCE FROM THE 1700s'`,
both quoting numbers the speaker said. At high it managed exactly one card
against a reference of 2.57/25s.

Fixing HOW did not fix WHETHER. That is the next problem, and it is a prompt
problem, not a constraints problem.
