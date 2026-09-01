=== PLACEMENT FINDINGS (reference corpus) ===
═══════════════════════════════════════════════════════════════════════════

Where the families LAND, from the reference records. The catalogue sections tell
you what each component IS and which vibes it fits. This tells you where working
editors actually put them.

──────────────────────────────────────────
PLACEMENT
──────────────────────────────────────────

**Cards land with the speaker OFF-SCREEN, and are strongest at the CLOSE.**
A card is not an annotation over a talking head — it takes the frame. Put it
where the speaker is not, and prefer the closing beat over the opening one.

**Text RIDES the speaker, at the CLAIM and the EVIDENCE.**
The opposite placement to cards. Overlay text sits with the speaker on screen
and belongs on the two beats where the argument is carried: the claim being
made, and the evidence given for it.

**Beats are SHARED, not exclusive — 77% of cards and 83% of text placements
share their beat with something else.** A beat carrying a card usually also
carries a cut, a cutaway or a sound. Treating each family as needing its own
clear beat produces a thinner edit than the references.

──────────────────────────────────────────
TARGET FAMILY MIX  (per 25 seconds)
──────────────────────────────────────────

    overlay text  7.56        <- the workhorse, by a wide margin
    cutaway       3.32
    card          2.57
    emphasis      0.5-0.6     <- rare, deliberate
    sfx           0.5-0.6     <- rare, deliberate

Text is the dominant family and emphasis/SFX are the rare ones. An edit whose
emphasis count approaches its text count is inverted against the references.

These are the RATES to aim at, not a quota to fill. A 25s cut carrying two
cutaways and eight text beats is inside the shape; one carrying eight emphasis
zooms is not.

──────────────────────────────────────────
PROVENANCE, AND ONE DISCREPANCY LEFT VISIBLE
──────────────────────────────────────────

The rates above are Zac's, from the nine reference records.

An independent recomputation over the live `reference_beats` table (2026-08-31,
all 10 rows, 153 beats, 426.1s total) gives:

    overlay_text 124  ->  7.28 per 25s     (vs 7.56 stated)
    cutaway       72  ->  4.22 per 25s     (vs 3.32 stated)
    card          40  ->  2.35 per 25s     (vs 2.57 stated)
    sfx           14  ->  0.82 per 25s
    punch_in       6  ->  0.35 per 25s

Text and card reproduce closely. **Cutaway does not**, and no single-record
exclusion reconciles it — dropping any one of the ten leaves cutaway between
3.68 and 3.99, never 3.32. The stated figure is used above because it is the
canonical read; the discrepancy is recorded here rather than averaged away, so
that whoever next touches the corpus knows the two numbers disagree and why the
question is open.

The corpus also carries NO `speaker_on_screen` column, so the "speaker
off-screen" placement rule above is not re-derivable from the table as built.
It is carried from the canonical analysis, not observed here.
