# CLIP-BRAIN — PARKED PERMANENTLY, and why no rule survives

Written 2026-09-03, answering the standing question: *turn the clip-brain
findings into rules the agent reads, or say plainly that the corpus is too thin
and park it.*

**Verdict: park it permanently. It produces no rule for this editor.** Not
"needs more data" — the two findings it produced are both NEGATIVES, and the one
statement that survives describes a stage this editor does not perform.

---

## 1. Both findings are refutations, not rules

A rule is something the agent can act on. Neither finding is.

**Position is HOUSE STYLE, not a law.** Early/mid/late distribution of the
performing moment, per creator:

| creator | early | mid | late | % early |
|---|---|---|---|---|
| DOAC `@doac.clips` | 0 | 4 | 2 | **0%** |
| MW `@chriswillx` | 11 | 13 | 7 | 35% |
| MFM `@myfirstmilpod` | 7 | 4 | 2 | **54%** |
| HZ `@ahormozi` | n=1 | | | — |

Three usable creators, three different distributions, spanning 0% to 54%. There
is no "the good bit is buried" rule to encode. Encoding *any* position prior
would be fitting one creator's editor and calling it a law.

**`selection_ratio` is DURATION-CONFOUNDED.** DOAC p50 0.0078 and MW p50 0.0085
looked like replication until MFM came in at p50 0.0287 (max 0.1092). MFM's
episodes run ~47min against DOAC's ~100min — the same 60s clip is 2.1% of one
and 1.0% of the other. The ratio is downstream of source duration. Two creators
agreeing was a coincidence of two similarly-long shows.

What survives is one sentence: *a performing clip is a small single-digit-percent
slice of its source, and LOCATING it is the work.*

## 2. That surviving sentence is about a stage this editor does not have

This is the decisive point, and it is measurable rather than arguable.

The agentic editor receives `/work/source.mp4` — already short — and trims
filler, silence and false starts. Its own instrument says so:

```
kept_ratio = 1.0 - (len(missing) / max(1, len(src_words)))
```

Measured across the two most recent arms: **0.889** and **0.813**. The editor
**keeps ~85% of the source speech**, and a run below 0.5 is failed outright as
"most of the speech is gone".

Clip-brain describes selecting **1–3%** of a 47–100 minute source. That is a
different operation, on a different input, at a different stage:

| | clip-brain | agentic editor |
|---|---|---|
| input | 47–100 min long-form | ~73 s source |
| output share of input | 1–3% | **~85%** |
| the work | LOCATE the moment | TREAT the moment |

Handing the editor a moment-selection prior is handing it an answer to a
question it is never asked. Its source arrives pre-selected.

## 3. So what would it take, and why it is still not worth it

Clip-brain would matter to a **long-form → short** pipeline that ingests a
podcast episode and picks the moment. That pipeline does not exist. If it is
ever built, this is what would have to be true first:

- **A performance-scored corpus, freshly scraped.** The existing 10
  `reference_videos` are all `selected_by='owner'` with no `views`, `author` or
  `source_url`, and the filenames are TikTok CDN ids, so they cannot be upgraded
  in place. Craft records, not performance data.
- **More than three usable creators.** Three gave three position distributions.
  A fourth (`@ahormozi`, 2.6% match) turned out not to clip from his own
  long-form at all — "creator posts long-form" does not imply "the clips come
  from it".
- **An invariant expressed in CLIP LENGTH, not ratio**, since ratio is
  confounded by source duration.

Cost is not the blocker — plain scrape is $0.001/40 clips. **Relevance is.**

## 4. What is kept

`clip_brain/match.py` + `cert_match.py` stay in the tree. The matcher held up on
real data: every match ≥0.91 confidence, no marginal middle, and it returns
`UNMATCHED` rather than force-fitting when the source is absent. It is the
correct component for that job whenever the job exists. It is simply not wired
into the editor, and this file is the record of that being a decision.

`agentic_editor_app.py` records `inputs.clip_brain.status = "parked_permanently"`
in the ledger of every run, so the absence is visible in the artifact rather
than being rediscovered as an omission.

## 5. What this cost, honestly

The clip-brain work produced two refuted hypotheses and one weak surviving
statement, for $0.477 of scraping. Both refutations were real and worth having —
"position is house style" in particular would have become a selection rule
someone believed. But it never reached the render path because there is no path
for it to reach, and that was knowable from `kept_ratio` before the scrape.

**The lesson worth keeping: check that the consumer performs the stage your
finding is about, before you gather data about the stage.**
