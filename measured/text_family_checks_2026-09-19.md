# Two checks on the text family — both answered

## 2. A malformed entry FAULTS and WITHHOLDS — proven

    MALFORMED ENTRY  FAULT FIRED — the read-back named 1 unreadable entr(ies);
                     the export is withheld while any stands
        a1a26291 (StickyNotes): notes entry 1 ('|#FFE066|-3') has no text

Planted deliberately, placed on a real timeline, caught at the read-back, named by
item and by component. **It took four runs to get here and the first three were all
the same class of defect**, each one a check that could not fail:

| run | reported | actual cause |
|---|---|---|
| 1 | NO FAULT | component refused — a **fifth** validator rule: a property read into a binding that is never USED |
| 2 | NO FAULT | read each item's own `propertyOverrides`; the read-back does not carry it |
| 3 | NO FAULT → **ABSENT** | the three-state change worked; the inspect call produced nothing and the reason was swallowed |
| 4 | **FAULT FIRED** | properties parsed out of inspect_item's PROSE |

The values were never in a JSON key. `inspect_item` answers with
`_links/_meta/_text/content` and puts them in the text, under a
`Motion Graphic Effective Props:` block and a `propertyOverrides:` line. **This repo
already had that written down from an earlier round and I wrote the same bug
underneath it.**

The error no longer renders into the frame. It is a fault at the rewatch, where the
agent can still fix it, and at the read-back, which withholds.

## 1. Which variant is plain / medium / middle?

**CaptionMatch at medium/middle produces that shape** — see
`text_CaptionMatch_medium_middle.jpg`: white sans-serif words, centred, no card, no
strip, no background, a soft shadow for legibility. The other four cannot: torn
paper is two slammed strips, sticky notes are coloured paper, the quote card is a
bordered serif panel, the lower third is a broadcast bar.

**BUT IT PRODUCES THAT SHAPE BY NOT DOING ITS JOB.** The old spec defines
caption_match as rendering *in the same style as the main captions* — mono-brand,
"use ONLY where matching the caption IS the brand". Measured against the port:

    reads the project caption style?   NO
    uppercases?                        NO
    renders a card or background?      NO
    font weight requested               900

It renders a fixed sans-serif and never consults the caption style. So the plain
shape is on the menu **under a name that promises something it does not do** — and
the moment the port learns to inherit the caption style, the plain shape leaves the
menu with it.

**That is the honest state: the shape is present, the component is not what it
claims, and those two facts are in tension.** The resolution is Zac's — either
CaptionMatch stays plain and is renamed for what it is, or it learns the caption
style and a sixth component carries the workhorse plain/medium/middle.
