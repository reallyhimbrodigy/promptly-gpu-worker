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
