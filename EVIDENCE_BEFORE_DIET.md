# EVIDENCE BEFORE THE DIET

Zac: *"Rules with their evidence survive compression. Rules without it get cut —
and nobody will know why they were there. Apply it before the diet, not after."*

## THE AUDIT

Over the editorial prompt's normative lines:

| | count | share |
|---|---|---|
| normative lines (MUST / NEVER / ONLY / cap / at most …) | **97** | |
| carrying evidence (a measurement, count, %, date, cert) | **6** | **6.2%** |
| bare | **91** | **93.8%** |

But 93.8% overstates the problem, and the split is the useful part:

| bare rule kind | count | needs evidence? |
|---|---|---|
| **CONTRACT** — "user says X → emit Y" | 17 | **No.** Definitional. Evidence would be meaningless: the rule *is* the contract. |
| **EMPIRICAL** — a cap, density, threshold or taste claim | **74** | **Yes.** Each could be simply wrong and nobody would know. |

**74 is the real backlog.** Those are the lines a 2,500→500 diet would cut blind.

## THE PATTERN, AND WHY IT IS NOT JUST DOCUMENTATION

A rule carrying its measurement is doing three jobs at once:

1. **It survives the diet** — a compressor can see what the line bought.
2. **It tells the model the stakes**, which is the part that changes behaviour:
   "33 of the 53 rationales that mentioned b-roll sat on a plan with ZERO
   b-roll" is an instruction *and* a demonstration that the failure is real and
   common.
3. **It makes the rule falsifiable.** A cap with a number attached can be shown
   wrong later. A bare cap can only be argued about.

## APPLIED WHERE THE EVIDENCE ALREADY EXISTS

Annotated now, because each number is also a delete-or-fix decision:

| rule | evidence attached |
|---|---|
| `cut_refinements` | **empty on 159 of 159 plans** — the pass produces nothing |
| `generated_scenes` | **0 of 778 planned jobs** — never once used |
| `transitions` | **4.9% of jobs (38 of 778), mean 0.05/25s** — "the few" became "almost none" |
| `edit_rationale` | 33 of 53 b-roll mentions on zero-b-roll plans |
| `caption_keywords` | 1,372 written and discarded across 267 jobs |

Gated: **EVIDENCE RIDES THE RULE** fails the deploy if any of those numbers is
stripped. Without the number the rule is an opinion and the next diet cuts it.

⚠️ Note the direction the first three point: they are evidence for **deleting or
fixing the instrument**, not for keeping the rule. That is the pattern working —
attaching the measurement made the decision obvious instead of arguable.

## THE 74 — WHAT TO DO WITH THEM

Do **not** invent evidence to keep a line. The honest states are:

- **MEASURED** → annotate with the number (5 done above).
- **MEASURABLE, NOT YET MEASURED** → most of the 74. Each is a query. Examples
  already queued: the one-dominant-event window cap (measurable against MG
  density, which currently says we fire at *half* Zac's reference rate — that
  is evidence the cap may be too tight, i.e. AGAINST the rule); the
  payoff single-peak rule (`ZOOM_ARC_HOMES['payoff']` was slow-only, 0/253 in
  production).
- **TASTE** → say so explicitly and mark it Zac's call, so a diet knows it is
  not cuttable on evidence grounds because there will never be any.

**The diet should not start until every one of the 74 is in one of those three
buckets.** Cutting a MEASURABLE-but-unmeasured rule is the same mistake as
cutting a measured one — the difference is only that nobody has looked yet.

## Method and cost

Regex classification over the editorial prompt span in `handler.py`, normative
and evidence patterns as above. **Spend: zero.**

---

# RANKED BY "COULD THIS BE WHY THE OUTPUT IS THIN?"

Zac: rank them, don't treat them uniformly — start with every density, cap and
"at most" rule, because those can only ever reduce output.

## THE SUPPRESSIVE SET: 16 matches, and 7 of them are ONE doctrine

| # | rule | |
|---|---|---|
| 1 | **"A window holds at most one dominant event."** | the doctrine |
| 2 | "one window carries one event" — stacked ⇒ keep one, drop the rest | restatement |
| 3 | "One dominant thing at a time stays true everywhere" | restatement |
| 4 | "Composed pairs are one event" | restatement |
| 5 | **breather windows get ZERO events by design** | restatement |
| 6 | "payoff_word_index — ONE peak only" | restatement |
| 7 | "Doubling up dilutes… an MG on top is two effects fighting" | restatement |

The other 9 matches are component descriptions ("Quintessence — ONE word at a
time") that the pattern caught but which suppress nothing.

**So the suppressive surface is not 16 rules. It is ONE doctrine stated seven
times, with no evidence behind any of the seven.** A diet would compress the
seven into one and change nothing, because the doctrine is the thing doing the
work.

## AND THE BLAME CANNOT BE PUT ON CODE — I CHECKED

The obvious rebuttal is that density is culled downstream anyway, so the prompt
is not the constraint. **That rebuttal is false for these families**, and this is
the measurement that decides it:

| family | code cap | what the PLAN actually emits | cap utilisation |
|---|---|---|---|
| **transitions** | `_TRANSITION_CAP_PER_30S = 4.0` | **0.06 per 30s** | **1.5%** |
| motion_graphics | *no per-30s cap in code* | 0.82 per 30s | — |
| text_overlays | *no per-30s cap in code* | 0.98 per 30s | — |
| tight_cut_overlays | *no per-30s cap in code* | 0.79 per 30s | — |

Transitions run at **one and a half percent** of the cap the code allows. Three
successive culls exist (`drop_overlay_collision`, `drop_too_close` at 3.0s
spacing, `drop_over_cap`) and **not one of them can be binding at 0.06/30s.**

⚠️ Two scope limits, stated: the plan I measured is PRE-cull (`transitions_out`
is built fresh at handler.py:25335, so the render never mutates the persisted
plan) — so this is what Gemini emits, before any culling. And zooms/emphasis are
NOT covered: `_VISUAL_REFRACTORY_S = 2.0` downgrades zooms for spacing, so that
family may genuinely be code-bound, which matches the earlier E1 finding that the
emphasis ceiling was architectural. **The claim here is only about transitions,
MGs and overlays.**

## THE COUNTER-EVIDENCE ALREADY ON THE BOARD

MG density measured against Zac's own reference: **7.76 vs 16.7 per 25s — we cut
at HALF his rate**, and 63% of standard-editorial jobs carry ZERO motion
graphics. The only measurement bearing on the one-event doctrine points AGAINST
it.

## THE DELETE TEST IS THE RIGHT INSTRUMENT (Zac, item 2)

Three for three so far: `pacing`, `color_effect` and the six MG components were
all convicted by removal, not by argument. A rule whose removal changes nothing
was never doing anything.

**The test to run: remove the window doctrine — all seven statements — behind a
dark variant, and measure events per 25s against control.** It is the highest-
ranked bare rule on the board, the only counter-evidence available says it is
too tight, and no code-side cap can absorb the result.

Two outcomes, both worth having:
- **density rises** → the doctrine was suppressing quality, and it has been
  doing so on every standard-editorial job.
- **density unchanged** → the doctrine is inert prose and the diet deletes seven
  statements for free.
