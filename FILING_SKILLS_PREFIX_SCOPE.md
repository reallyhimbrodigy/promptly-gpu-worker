# Scoping skills into the cached prefix — measured, before building

**Recommendation: do not push the skills. Almost none of it is ruling-time
material, and the audit was wrong to file skills and knowledge as one gap.**

## What is actually mounted

`_SKILLS_SRC = ~/.claude/skills`, `add_local_dir` with an ignore list.
What survives it, markdown only:

    remotion-official           427.2 KB   135 files
    remotion-best-practices     290.6 KB    81
    remotion-markup             171.3 KB    44
    karpathy                     33.1 KB     6
    remotion-captions             10.5 KB     4
    remotion-interactivity         7.4 KB     1
    remotion-multimedia            4.9 KB     4
    remotion-create/-render/-docs/-studio   7.8 KB
    ──────────────────────────────────────────────
    TOTAL                       952.9 KB  ~243,900 tokens

**29x the entire current prefix (~8,367 tokens).** Not a budget question — a
category question.

## What it IS

**93% of it is the Remotion API documentation** (official + best-practices +
markup = 889 KB). That is reference for AUTHORING A COMPONENT — which is what
`search_skills` and the component-writing tool exist for.

`karpathy` (33 KB) is "Karpathy-Inspired Claude Code Guidelines": advice for
coding agents. It is in the image because it was in the skills folder and not on
the ignore list. It has nothing to do with editing video.

**Zero KB of it is editorial material about when a placement earns its moment.**

## So the audit's fourth column was right and its diagnosis was wrong

I filed "skills and knowledge are mounted and ignored" as one gap. They are two,
with opposite answers:

    skills      NOT ruling-time material. Correctly unread at ruling time.
                Read only when authoring a Remotion component, and that path has
                not been exercised in rounds 44-46 — search_skills: 0 calls.
                The mounting is the RIGHT mechanism for on-demand reference.
    knowledge   IS ruling-time material — the intent standard, placement
                findings, the card/text FITS-FIGHTS rules — and it IS unread.
                That gap is real and the mechanism is wrong.

Lumping them cost the reader a wrong conclusion, which is worse than the gap.

## The knowledge docs, since they are the ones that might warrant the prefix

    05_motion_graphics.md      9,168 tok      01_cut_pass.md      6,710
    00_job_and_arc.md          5,544          11_thumbnail.md     5,134
    06_emphasis_zoom.md        5,051          08_broll.md         4,495
    07_sound_effects.md        3,097          03_captions.md      2,706
    15_ffmpeg_recipes.md       2,083          14_card_text_rules  1,288
    04_text_overlays.md        1,254          13_placement_find.    923
    02_intent_standard.md        362          09_seam_treatments    213
    ────────────────────────────────────────────────────────────────────
    TOTAL                     48,033 tokens

Also too large whole — 5.7x the current prefix. But the distribution is the
finding: **the two documents that are purely ruling-time judgement are the two
smallest.**

    02_intent_standard.md          362 tok   "name what it does for the viewer
                                             at that instant — that question is
                                             the whole standard"
    13_placement_findings.md       923 tok   where the families actually LAND,
                                             from the reference records
    14_card_text_placement_rules 1,288 tok   FITS/FIGHTS, evidence on every rule
    09_seam_treatments             213 tok
    ────────────────────────────────────────
    2,786 tokens for all four

**That is the budget shape.** ~2,800 tokens against the reference retrieval's
~989, into a prefix that writes once (`1:w11k/r0k`, then `w0k` for all 18
remaining turns).

The large documents are catalogues and recipes — 05_motion_graphics is the
component catalogue, 15_ffmpeg is command recipes, 11_thumbnail is a different
product surface. Those are genuine lookup material and belong exactly where they
are.

## What I would build, if told to

Not skills. The four ruling-time knowledge documents, ~2,786 tokens, into the
cached prefix beside the reference examples — same mechanism, same economics,
and it is the material that answers "when does a placement earn its moment"
rather than "how do I write a Remotion component".

## What I would NOT do

- Push 244,000 tokens of Remotion documentation into every run.
- Push the catalogues. `05_motion_graphics.md` at 9,168 tokens is a reference
  work; a derivation reads it, an agent mid-ruling does not.
- Remove the skills mount. It is the right mechanism for its actual purpose, and
  the component-authoring path being unexercised is a separate observation, not
  a reason to unmount its reference.

## The honest version of Zac's framing

He offered: "if it's 200KB, the honest answer is that most of it was never
ruling-time material and the mounting was the wrong mechanism from the start."

It is 953KB, and the first half is right — almost none of it was ever
ruling-time material. The second half is not: mounting is correct for on-demand
API reference. What was wrong was my audit reporting it in the same row as the
knowledge docs, which made a correctly-unread reference look like a failure.

**Not started. Reporting first, as asked.**
