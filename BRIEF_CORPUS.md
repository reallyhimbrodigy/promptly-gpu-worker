# The brief corpus — 5,943 distinct requests, clustered across users

Built 2026-09-11 from `video_jobs.vibe_input`, the production request table.
The five test clips are fixtures for the RENDER; this is the fixture corpus for
the REQUEST, and the fidelity standard now has real briefs to run against
instead of invented ones.

**Population.** 11,722 rows, **5,943 distinct briefs**, 7,958 users,
2026-06-25 → 2026-09-12. `change_request` (the re-edit instruction) has only
**90 distinct values** across the same window — the re-edit path is ~66x
narrower than the first-edit path, which is worth knowing before anyone spends
on it.

**Counted across USERS, not occurrences** (Rule 7), with the brief count beside
it — a cluster that is large by brief and small by user is a handful of people
iterating, not a demand signal.

| cluster | users | % users | briefs | % briefs |
|---|---:|---:|---:|---:|
| viral / unspecific | 3,833 | **48.2%** | 1,657 | 27.9% |
| sound & music | 1,782 | 22.4% | 1,697 | 28.6% |
| zoom | 1,412 | 17.7% | 1,282 | 21.6% |
| graphic / card | 1,216 | 15.3% | 994 | 16.7% |
| caption | 1,035 | 13.0% | 1,315 | 22.1% |
| cut / trim | 942 | 11.8% | 1,172 | 19.7% |
| pace | 860 | 10.8% | 923 | 15.5% |
| transition | 568 | 7.1% | 707 | 11.9% |
| text overlay | 431 | 5.4% | 497 | 8.4% |
| format / platform | 405 | 5.1% | 479 | 8.1% |
| **negative constraint** | **338** | **4.2%** | **425** | **7.2%** |
| language | 268 | 3.4% | 300 | 5.0% |
| b-roll | 212 | 2.7% | 264 | 4.4% |

Clusters overlap: one brief can ask for zooms and forbid captions, and it is
counted in both. That is the same property that broke the family classifier on
the 66 knowledge sentences — **a request is not one family, and a taxonomy that
forces it to be produces a confident wrong answer.**

## The number that matters most for fidelity

**48.2% of users write a brief with no declared family scope.** `spec_fidelity`
returns UNSCOPED for every one of them — by design, because there is nothing to
judge against. So the standard, as it stands, has an opinion about at most half
the traffic, and the half it judges is the half that was already specific.

That is not a defect to fix by guessing a scope. It is the denominator that has
to sit beside any fidelity rate anyone quotes.

## The negative-constraint class — MEASURED, and it was unjudgeable

Zac's figure was 6.8%; measured here at **7.2% of distinct briefs (425) and
4.2% of users (338)**, defining the class as a negation or exclusivity applied
to an editing family. A looser pattern — any "no"/"only" anywhere — gives 16.0%
of briefs and 9.5% of users, and includes "no problem" and "just make it pop".
The tight definition is the class; the loose one is a word search.

**The pipeline had never been tested on one, and could not have passed.**
`set_spec` had no field to carry an exclusion, so the commonest shape in this
class went through as an ordinary full_edit:

```
brief:  "viral and engaging no captions in video"
spec:   mode=full_edit, families=[]
result: UNSCOPED — "no declared family scope, so fidelity cannot be judged"
```

Nothing objected while the pipeline burned the captions the user had just
refused. Under `targeted_change` it happened to read OVERREACHED, but only
because captions were not in `families` — right by accident, and only on the
minority shape.

### What shipped

- `forbidden` on `set_spec`: the families this request says NOT to do, **in any
  mode**. Explicitly not the opposite of `families`, explicitly not
  targeted_change-only, and explicitly still required when the rest of the brief
  is vague — "the vagueness of the rest does not soften the one thing they were
  specific about".
- `FIDELITY_FORBIDDEN`, a fifth state, checked BEFORE the mode gate so a
  full_edit cannot escape it, and failing loudly as `fidelity_forbidden`.
  SHORT and OVERREACHED are misjudged scope; this is an instruction disobeyed.
- Exclusive phrasing is named in the field description: "only zooms" forbids
  every family except zoom.

### Real shapes this class takes, from the corpus

Verbatim user text, held as DATA. Four distinct shapes, and only the first was
ever going to be caught:

1. **positive + exclusion** — "add zooms. no text on screen or captions"
2. **whole-video + exclusion** — "viral and engaging no captions in video",
   "make it a viral engaging video with no captions on it", "clean and engaging
   and no captions". *This is the shape that returned UNSCOPED.*
3. **exclusive** — "just add visual zooms and transitions nothing else no
   trimming no cutting anything", "only captions"
4. **out of this pipeline's scope entirely** — "dont change face", "remove
   crust and imperfections on feet, do not edit face". These are
   `change_in_frame`, the unsupported class, and they must route rather than be
   half-obeyed. A `forbidden: ["face"]` would be a lie: the pipeline does not
   touch faces either way, and recording it as honoured would claim credit for
   an absence.

Shape 4 is the one to watch. **A negative constraint about something the
pipeline never does is satisfied by construction, and counting it as a pass
would inflate the class's success rate with cases nobody could fail.**

## What this does not answer

Whether the AGENT populates `forbidden` correctly from these briefs. That is a
round, and it is Builder-1's. The rule is testable without one; the extraction
is not.
