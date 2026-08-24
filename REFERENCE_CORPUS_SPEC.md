# REFERENCE CORPUS — SPEC

Written 2026-08-24. Apify scrape → Claude frame-analysis → structured records in
Supabase, packaged as a **skill** rather than prompt prose.

This has been built once before and retired. Section 1 says what that was and
why the shape here is different; if the difference does not hold, this is the
same path with a new name.

---

## 1. The prior generation, and the one thing it got wrong

`scripts/trend-video-pipeline.js` (Apify `clockworks/tiktok-scraper`, hashtags,
≥500k views, top 50) → Gemini analysis → **one aggregated row** in
`trend_profiles` → injected into the directive as prose by
`format_trend_section`.

It was removed on 2026-08-23 (6,298 characters out of `handler.py`, cron out of
`render.yaml`). Its four scripts sit at `scripts/trend-*.js.deprecated`.

**The defect was not the scrape. It was the aggregation.** A style guide averaged
over 50 videos says "trending videos cut fast and use bold captions." That is
true, unconditional, and useless: it cannot be queried for *this* source, it
cannot be cited, and it cannot be wrong in a way anyone would notice. It was
prose appended to an already-implicitly-cached 60,540-token prompt — measured,
prompt-cutting bought nothing, so adding prose bought nothing either.

**Two rules follow, and they are the whole spec:**

1. **Records, never an aggregate.** One row per reference video, and one row per
   BEAT within it. Averaging happens at query time, if at all — never at write
   time, because an average cannot be un-averaged.
2. **Retrieved, never recited.** The corpus is queried for the case at hand
   ("openings for a 30s single-speaker testimonial"), not pasted wholesale into
   every prompt.

---

## 2. Selection — the property under test, not virality

The retired scrape selected on **hashtags + view count**. That selects for
*reach*, which is a property of distribution, not of craft. It is the same error
`build_component_corpus.py` was written to end: *"three corpora in a row were
chosen on properties unrelated to what was being measured."*

Select for **editing craft that is visible in frames**:

| axis | why it is in the selection, not discovered after |
|---|---|
| single speaker, talking-head base | matches our input class; a multi-cam skit teaches nothing transferable |
| 15–90s | our output range; a 3-minute video has a different beat economy |
| visible cuts ≥ 6 | a video with 2 cuts cannot demonstrate cut craft |
| carries at least one card/overlay | otherwise it cannot demonstrate what we most often decline |
| carries at least one cutaway | same, for b-roll — this is the `broll` trigger added 2026-08-24 |

**A reference with no instance of a component cannot be evidence about that
component.** The trigger discipline that governs our own A/B corpus governs this
one; a reference is admitted for what it *demonstrates*, and its record says
which.

Provenance is pinned per record: `platform`, `source_url`, `author`,
`scraped_at`, `sha256` of the downloaded file, `bytes`. An analysis re-run on
drifted bytes is comparing two different things.

---

## 3. Analysis — Claude, on frames, at the proxy's own sampling

**512px vertical, 2fps** — deliberately identical to the live proxy arm
(`proxy_sample_fps=2`, `MEDIA_RESOLUTION_LOW`, measured cohort n=96). If the
corpus is analysed at a fidelity the production planner never sees, it teaches
craft the planner has no way to perceive.

Two passes, because they answer different questions and must be separable:

**Pass A — segmentation (cheap, mechanical where possible).** Shot boundaries by
`ffmpeg` scene detection, not by the model. A model asked to find cuts *and*
describe them will describe cuts it invented. Emit: `t_start`, `t_end`,
`shot_index`.

**Pass B — per-beat description (Claude, frames + transcript window).** For each
beat emit a **structured record**, not prose:

```
beat_index          int
t_start, t_end      float          the beat's own duration is a first-class field
purpose             enum           hook | claim | evidence | turn | payoff | close | breath
speaker_on_screen   bool
treatment           enum[]         cut | punch_in | cutaway | card | overlay_text | sfx | none
cutaway_subject     string|null    what the b-roll literally SHOWS (null when none)
card_text           string|null    verbatim, when legible
read                string         one sentence: why this treatment, here
```

`purpose` and `t_start/t_end` are the two fields item 2 turns on. `treatment: []`
— a beat that received nothing — **must be storable**, because "this beat was
deliberately left bare" is the single most under-represented fact in our own
planning and the reason density reads as timid.

**Cost is measured, not estimated**, and reported with cache hit/miss stated
per arm — the same discipline the brain A/B carries, and for the same reason:
Claude's explicit `cache_control` and Gemini's implicit cache are not comparable
without it.

---

## 4. Storage — two tables, because one would force an aggregate

```
reference_videos   id · platform · source_url · author · duration_s · sha256
                   bytes · scraped_at · analyzed_at · analyzer_model
                   demonstrates text[]        <- which components it can be evidence about
                   selection_reason text

reference_beats    id · video_id FK · beat_index · t_start · t_end
                   purpose · speaker_on_screen · treatment text[]
                   cutaway_subject · card_text · read
```

One row per beat is what makes retrieval possible: *"beats with
`purpose='payoff'` in videos of 20–40s where `treatment` contains `card`"* is a
query. Against `trend_profiles` it was not a question that could be asked.

Both tables are **derived data** — rebuildable from the pinned sources. No
migration risk, and a bad analyzer version is re-runnable rather than permanent.

---

## 5. Packaging — a skill, not prompt prose

The corpus ships as a skill with a stated contract:

- **Input:** the case at hand — output duration, speaker count, route, and which
  component the caller is deciding.
- **Output:** N matching beat records **with provenance**, plus their `read`
  lines. Never a summary; the caller sees the evidence.
- **Refusal:** when fewer than K records match, it says so and returns nothing.
  A thin match silently returned as guidance is how "trending videos cut fast"
  got into the prompt in the first place.

**Why a skill and not prompt text.** Prose in the directive is unversioned,
untestable, uncitable, and rides in every call whether relevant or not. A skill
is versioned, can be exercised in isolation, and is queried only when it applies
— which is what makes the knowledge live *outside* the model.

---

## 6. What this is expected to change, stated before it is built

- **Density.** 63% of standard-editorial jobs request ZERO motion graphics,
  against a reference density of 16.7 per 25s. If the corpus is doing its job,
  requested placements rise on trigger-bearing sources.
- **The brain A/B becomes smaller.** If taste is retrieved rather than
  memorised, the editorial model is doing less, and model choice should matter
  less. That is a **prediction**, and it is falsifiable: if Gemini-vs-Claude
  differs as much with the corpus as without it, this did not move the knowledge
  out of the model.

## 7. What would make this a failure, said now

- The records are written but nothing queries them — the built-not-wired class,
  which has nine precedents here. **The check is a production counter proving
  retrieval executed**, not the row count.
- Retrieval returns matches for everything, because K is too low. A corpus that
  never refuses is not evidence; it is decoration.
- The analyzer's `read` lines get concatenated into the directive. That is
  `trend_profiles` again, wearing a new schema.
