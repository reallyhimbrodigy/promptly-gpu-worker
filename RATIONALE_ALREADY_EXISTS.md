# THE "WHY I DID THAT" FIELD ALREADY EXISTS — AND IT IS NOT SAFE TO SURFACE YET

Checked before building, as instructed. The instinct was right on both counts.

## IT EXISTS, IT IS GENERATED, IT IS ALREADY PERSISTED

`edit_rationale` — 1-2 sentences written TO THE USER, `max_length=400`, schema
field at `handler.py:1693`, prompt at `6675`, written to
`video_jobs.edit_rationale` by `_persist_edit_rationale()`.

| | of 779 planned jobs |
|---|---|
| `video_jobs.edit_rationale` column populated | **283 = 36.3%** |
| rationale present in the plan | 282 = 36.2% |
| `post_package` populated | 450 = 57.8% |

It is written in the **user's own language** — one sampled rationale is entirely
in Hindi. So this is plumbing and UI, not a prompt project. Confirmed.

### Per-decision reasoning exists too, but only on three families

| family | items | carrying a why/reason |
|---|---|---|
| tight_cut_overlays | 443 | **100%** (`why`) |
| broll_clips | 75 | **100%** (`reason`) |
| transitions | 47 | **100%** (`why`) |
| cuts | 5,882 | **0%** |
| emphasis_moments | 2,875 | **0%** |
| motion_graphics | 390 | **0%** |
| text_overlays | 398 | **0%** |

The decisions the viewer actually notices — where we cut, what we emphasised —
carry no reasoning at all. The three that do are the rarest.

## 🚨 AND IT WOULD LIE TO THE USER TODAY

The hard constraint is already being violated by the field as it stands.
Measured over the 283 jobs that have a rationale:

| claim in the prose | claims | plan carried NONE | rate |
|---|---|---|---|
| **b-roll / cutaway** | 53 | **33** | **62.3%** |
| a graphic/overlay of any kind | 114 | 23 | ≤20.2% |

**The b-roll number is the real one.** "Added a cutaway to…" on a plan with zero
`broll_clips` is unambiguous, and it happens in nearly two-thirds of the
rationales that mention b-roll.

⚠️ I am marking the decoration figure as an UPPER BOUND, because I checked the
examples and my own regex is wrong on some of them — it counts *negations*
("no distracting graphics or B-roll") and descriptions of the **source** ("the
original video already has burned-in captions and a title card"). My first pass
reported 46.9% for this; the strict cut says ≤20.2% and the truth is lower.

### Separately: the prompt's own rule is broken half the time

The prompt says "**NEVER** an internal component or style name". **139 of 283
(49.1%)** name one anyway — "leaning into the viral 'Prime' caption style",
"using massive TwoTone captions", "Added bold StatCards". One rationale even
narrates the model's own limits to the user: *"While I cannot synthesize a new
kid voice track directly…"*

## WHAT THIS MEANS FOR THE BUILD

1. **Do not surface `edit_rationale` as generated.** At a 62.3% b-roll lie rate
   it would tell the user the product does not know what it made — the exact
   failure named in the brief, already present in the data.
2. **Generate the explanation from the plan that RENDERED.** The field to write
   is not the model's prose but a validated one: take the final plan, drop every
   claim whose family is empty, and let the model narrate only what survived.
3. **The auditability prize is real and available immediately** — a rationale
   whose claims are checked against the rendered plan makes a bad edit visible
   by eye, which is what nothing else on the board does.
4. **Coverage is 36.3%.** Two thirds of planned jobs have no rationale at all,
   before any of the above.

## Method and cost

`video_jobs.edit_rationale` + `result.edit_recipe.plan`, 779 planned completions
since 2026-07-28. Claim detection by regex over the prose, with the strict cut
requiring the whole family to be empty. **Spend: zero.**
