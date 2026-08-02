# VARIANT CACHES — scoped and priced (prompt agent, 2026-08-02)

**Ask:** 3–4 fixed prompt variants keyed on a coarse content class, each with a
filtered catalogue, cached separately. *"The only path to 2-3× on what the model
READS without deleting capability."*

**Finding: it reaches 1.08–1.12×, not 2-3×.** The reason is structural, and it is
the same reason every other lever capped — measured below, not asserted.

---

## 1. HOW MUCH OF THE PREFIX IS EVEN CLASS-SEPARABLE

The catalogue is already organised by moment shape (`── WHEN X ──`), so those
groups are the natural class boundary. Splitting the prefix on it:

| | tok | share |
|---|---:|---:|
| **class-separable** — the 8 moment-shape groups (the component entries) | **5,743** | **14.2%** |
| shared MG doctrine — anchor law, components intro, entry shape | 2,111 | 5.2% |
| universal doctrine — cut pass, preamble, emphasis/zoom, captions, SFX, b-roll, thumbnail, response format, overlays, global, intent, seam | 32,070 | 79.2% |

| variants | each carries | ratio |
|---|---:|---:|
| 2 | 37,601 | **1.08×** |
| 3 | 36,644 | **1.10×** |
| 4 | 36,166 | **1.12×** |

**85.8% of the prefix is universal.** A storytime video needs the same cut
doctrine, the same window rule, the same caption system, the same b-roll gate as
an explainer. Only the component *entries* are content-specific, and they are
14.2% of the prefix. Filtering them can't move the total.

To get 2-3× you would have to fork the **doctrine** per class — and the doctrine
is the product.

---

## 2. WHAT THE CLASSES WOULD BE

Mapping the 8 moment-shape groups onto coarse content classes:

| class | groups it keeps | components |
|---|---|---|
| **TEACH / EXPLAINER** | A NUMBER LANDS · STEPS ENUMERATED · TIME OR SEQUENCE | StatCard, ProgressBar, BarRace, RankedList, StickyNotes, PillCluster, PillMarquee, DropBanner, DropCard, Timeline, TimelineRoadmap, StepDivider, SectionDivider |
| **STORY / PERSONAL** | SOCIAL PROOF OR A MESSAGE · NAMED OR REVEALED · VERDICT OR STAMP | TweetBubble, InstagramComment, TikTokComment, IMessageBubble, ChatThread, Notification, PullQuote, EditorialQuote, Stamp |
| **PRODUCT / DEMO** | THE SCREEN OR APP · A REGION NEEDS POINTING AT | RecordingFrame, MouseDrag, AnnotationArrow, Reticle (+ StatCard, Stamp as shared) |

---

## 3. HOW THE ROUTER PICKS — AND WHY IT IS THE WEAK POINT

The variant must be chosen **before Call 2**, so the only signals available are:
the Deepgram transcript, the user's vibe string, and source metadata.

**It cannot see the video.** But moment shape is a property of the *footage* —
whether the speaker points at a screen, quotes a message, or enumerates steps.
Call 2 exists precisely because that read needs the video. So the router would be
guessing the thing the call was built to determine, from text alone.

---

## 4. WHAT BREAKS IF THE ROUTER PICKS WRONG

**(a) Silent capability loss.** The model cannot reach an instrument the moment
needs. There is no error — the beat just goes unserved. My usage audit already
shows 9/26 components never firing with the *full* catalogue present; narrowing
makes more unreachable, and the failure is invisible, exactly like the
`minimal_speech_uncut` class.

**(b) Dangling cross-references — 12 of them, measured.** The catalogue's
FITS/FIGHTS lines route *between* groups. Each of these breaks if its two groups
land in different variants:

```
DropBanner       → Timeline           MouseDrag      → Reticle, AnnotationArrow
PullQuote        ⇄ EditorialQuote      Stamp          → Notification
Timeline         → StickyNotes, ProgressBar
TimelineRoadmap  → ProgressBar         SectionDivider → EditorialQuote, PullQuote
Reticle          → RecordingFrame
```

The model would be told "a scenic winding-path version → TimelineRoadmap" while
TimelineRoadmap is not in its catalogue. That is worse than absence — it is a
pointer to nothing, and it sits inside the exact discrimination lines I just
rewrote to fix the six unreachable components.

**(c) Cache-entry multiplication.** The prefix *already* forks by
(premium × vibe-policy × source-language); each combination is a separately
created and billed Vertex entry, and ledger §8G flagged that a rare combination
may never amortise its creation cost. Multiplying that by 3–4 content classes
multiplies the entry count, and a changed system_instruction is a cold cache
(R3: same schema 32,658 cached / 3.6 s; different 0 cached / 52.5 s). Low-traffic
combinations would pay creation cost repeatedly and cache-hit rarely.

**(d) It targets the cheap half.** The cached prefix bills at 0.25×; the uncached
input already costs more per call (12,765 × 1.0 vs 41,344 × 0.25). Shrinking the
cached prefix by 8–12% moves the smaller term.

---

## 5. VERDICT

Variant caches are a real mechanism and would work as designed. They just reach
**1.08–1.12×**, because the thing they can filter is 14.2% of the prefix.

**This is the fifth independent measurement to land in the same place:**

| lever | ratio |
|---|---:|
| caveman rewording | 1.29× (unshippable max) |
| taxonomy classification | 1.12× |
| WHY-class deletion | ~1.01× |
| block deletion menu | 1.15× |
| **variant caches** | **1.12×** |

Five different mechanisms, five answers between 1.01× and 1.29×. The prompt is
~40k tokens because it carries a component catalogue, a pace system, a movement
system and a few-shot — and 86% of it applies to every video regardless of class.

**Recommendation: close the size workstream.** The remaining prompt-side value is
discrimination (making the model reach for what it has) and the silent-failure
detector, both of which serve goals that are still movable.
