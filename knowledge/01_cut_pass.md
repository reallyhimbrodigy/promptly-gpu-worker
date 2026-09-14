=== YOUR CUT PASS (cut_refinements) ===

**MEASURED 2026-08-04: `cut_refinements` came back EMPTY on 159 of 159 plans.** Not rare — never. This whole pass currently produces nothing, so if you have nothing to cut say so by emitting `[]` deliberately, but a lean edit almost always has something: an abandoned start, a weaker take, a filler run.

You watched the footage — cut what a lean edit cuts. Emit `cut_refinements`: KEPT-space inclusive word ranges to remove, each with a `reason` (≤10 words naming what's cut — 'abandoned start', 'weaker first take of the price line'):

  (a) **Phrasal restarts and abandoned starts** — 'so I was— I was going': keep the completed take, cut the abandoned words.
  (b) **Retakes** — when the speaker delivers the same line twice, keep the stronger delivery and name which in `reason`.
  (c) **Filler and dead weight** the detectors' punctuation rules missed — a 'like' or 'you know' the commas hid.

This pass removes only the speaker's own STRUCTURAL REDUNDANCY — the restarts, retakes, and filler above. It does NOT tighten real speech. A complete, meaningful phrase delivered once and fluently is CONTENT, not a drag — never cut it for 'leanness' or pace. "It took five minutes to edit. I did nothing." is not a stretch that drags; "to edit" is the sentence. Leanness comes from the mechanical cuts + these three redundancy classes, never from shortening a fluent sentence.

Rules: ranges are KEPT indices from the transcript below. Protected words (hook / payoff / close / key_moments) are never cut. **AN EDIT ENDS ON THE LAST THING WORTH SEEING.** Leftover app chrome, a dark frame, a held card after the point has landed — all the same loss. If something closes the video it is there because it EARNS the ending, not because the source stopped. The tail is a decision, and a source that ran on is not one. **A PROTECTED POSITION CAN BE BURIED AS WELL AS CUT — nothing is placed in front of the hook.** Protecting a position from removal and then opening on a title card, a logo, a black frame or any other pre-roll delivers the same loss by a different route: the viewer meets the thing that is not the hook first. The hook is the first frame of the edit, and anything you want to say alongside it goes OVER it or AFTER it, never BEFORE. **Content words in a flowing sentence are never removable — the pipeline enforces this: a cut_refinement that is not filler, a verbatim restart, or bounded by real dead air (a sentence-final boundary with a ≥0.70s pause) is rejected and the words are kept.** Under a cleanup-request vibe this pass works HARDEST on the three redundancy classes; under 'keep every pause / don't cut anything' emit []. When unsure whether a pause is dead or dramatic, keep it — the mechanical pass already took the measured silence.

═══════════════════════════════════════════════════════════════════════════

DECISION ORDER — arc first, ALWAYS
═══════════════════════════════════════════════════════════════════════════

Emit the JSON in exactly this order, finishing each stage's reasoning before opening the next. Out-of-order thinking — picking a zoom before naming the arc — produces decisions that don't reference the spine.

**Stage 0 — WHAT'S ALREADY ON THE FRAME.** Before judging anything else, look at the frame itself across several sampled moments: does the footage ALREADY show burned-in word captions — text that changes in sync with the speech? Report it in `existing_caption_region` ("bottom" / "top" / "other" — wherever the band sits; the exhibit class is white synced text mid-frame). A watermark or a single title card is not a caption track; synced dialogue text IS, even when it's small or center-frame. This is the first thing a human editor would notice, and everything downstream (caption layer, band placement) keys off it. When you report a region: caption_style becomes "none" (the video already has its caption layer), keyword emphasis lives in zooms and motion graphics, and the reported band is occupied space your layout respects.

Some sources arrive already edited: burned-in captions, existing text overlays, a watermark. Read the frame for text that is already part of the picture. A source that already carries its own captions keeps them — the caption track takes none, and the video reads as one edit, not two. Screen regions the source already uses for text belong to the source: your overlays and graphics claim the clear regions. Beyond the caption band, report every band the source's own text occupies in `source_text_regions` ("top" / "center" / "bottom") — omit the field when the frame is clean.

**Stage 1 — IDENTITY.** Decide what the video ISN'T before deciding what it is — run YOUR CUT PASS first, so every later judgment reads the footage that will actually render. Emit `video_identity`: 2-3 sentences naming what makes THIS video THIS video. A vague identity ("a personal story about family") yields generic components; a specific one ("the dad shaving when his 6-year-old recites 'Mommy shouldn't kiss Uncle Stelios on the lips'") yields choices that fit this footage. Include: a proper noun or named object from the dialogue, a specific moment from the story, and a detail that would surprise someone hearing the video described. A specific identity is one that could only have been written WITH this footage in front of you. (`existing_caption_region` was Stage 0 — carry that observation forward here.)

**Stage 2 — VIDEO PLAN.** Emit `video_plan` IN FIELD ORDER: what_happens → hook_word_index → payoff_word_index → close_word_index → key_moments → story_shape → arc_segments → movements → editorial_vision. Each later field depends on the earlier ones — the movements fall out of the arc, and the editorial vision speaks to the movements.

  • **what_happens** — 1-2 sentences of literal plot.
  • **hook_word_index** — where the curiosity gap OPENS, not necessarily word 0. On a trivia video the hook is the question; on a story video it's the moment the premise lands. A hook grips — a claim, a stake, a reveal. "Hello, what's your name?" is exposition; the hook starts where the grip starts.
  • **payoff_word_index** — the single strongest moment. ONE peak only.
  • **close_word_index** — the final beat, usually the last or second-to-last kept word.
  • **key_moments** — {_peak_budget}; a flat even-energy stretch may have only 2-3 — the count follows the footage's real peaks, and a shorter honest list beats a padded one. Space peaks ≥2.0s apart in OUTPUT time — two hard visual moves landing closer than that FIGHT each other: the second lands before the eye has processed the first, and the pair reads as an accidental glitch rather than two directed beats. The refractory floor enforces this after the plan — of any two zooms within 2s, the higher arc-ranked beat (payoff > mid_peak > other) KEEPS its zoom and the lower one downgrades (it rides its caption and sound instead) — so the spacing you plan in this list is the spacing that survives, and a zoom you crowd against a stronger one is a zoom you spend for nothing. Each: word_index, what_lands, why_emphasis, what_i_saw, viewer_feeling. **key_moments and emphasis_moments are 1:1** — this list is the ground truth for what gets a zoom. To add a zoom, expand this list first; only zoom peaks you can justify here.
  • **story_shape** — one sentence: how the video moves hook → setup → development → payoff → close.
  • **arc_segments** — THE SPINE. Walk the full kept transcript and tile it into contiguous segments, no gaps, no overlaps, last segment ending on the final kept word. Each segment: position (hook | build | mid_peak | payoff | breather | close) + intensity (0.0-1.0). Component picks begin once this is complete — the committed arc is the frame every pick hangs on.
  • **editorial_vision** — ONE specific sentence committing to HOW you'll cut THIS video. ("I'm leaning into the absurdity with TwoTone captions, pop SFX on every receipt detail, and a slow LetterboxPush when he opens the bag.") Every component below flows from this sentence. The same sentence also names the LOOK the whole video shares — the one color world it lives in, read off the speaker's actual setting and register: a warm low-light confession, a bright clean product demo, a high-contrast hype cut. Once you've named that world, every layer below inherits it: the caption's emphasis color, the motion-graphic accents, and the B-roll's grade all belong to one palette, so the cut reads as a single designed piece rather than parts borrowed from different tools. One palette is not one texture. The movements still rise and fall, one dominant instrument still hands to the next — what holds steady across all of that is the visual FAMILY (the colors, the typographic voice); what moves is the intensity. The aim is one identity spoken LOUD in the hook and QUIET in the breather — the same world at different volumes — which is a different thing from the same look at the same level everywhere.

**Stage 3 — STRUCTURAL REGISTER.** Emit `caption_style`, `thumbnail_word_index`, `outro`, `aspect_ratio`.

**Stage 4 — COMPONENT PLACEMENTS.** Before placing anything, run the REFERENT MINE: walk the kept transcript once and list every concrete noun, visible scene, number, name, brand, quoted line, phone event, and story turn the dialogue contains. That list is your shopping list — each entry is a candidate B-roll, MG, or peak. The mine guarantees every candidate was FOUND; whether each is PLACED is then a judgment against the extend test and its why — an unplaced referent is a decision, not a failure. Then emit: emphasis_moments (each optionally carrying its zoom, sound, and motion_graphic), text_overlays, broll_clips, motion_graphics, caption_keywords, caption_position_changes. Every component looks up its target word's arc position in arc_segments and matches that position's treatment. If a component makes you want to revise the arc — STOP, revise arc_segments first, then place the component against the revised arc. Every component references an arc state you committed to — the committed arc is the vocabulary components draw from.

═══════════════════════════════════════════════════════════════════════════
ARC SPINE — what each position is FOR, and what it gets
═══════════════════════════════════════════════════════════════════════════

Every component decision is judged against: "does this produce the feeling this arc position is supposed to produce?" The components are means; the viewer feelings are ends.

The plan reads the video's phases and sets each phase's energy from the footage: the HOOK is explosive — the grab gets the type-layer energy and usually the video's first hit. The ARGUMENT is kinetic — captions and annotation graphics carry the pace. The TEACH is calm — one clean structural graphic lets the content breathe. The CLOSE lands — the payoff line is the video's reason to exist, and usually its second hit. Density varies BY PHASE; a calm phase in an energetic video is a choice, and so is an explosive one.

  • **hook** (opens at hook_word_index, 1-5 words, intensity 0.7-1.0) — the viewer's thumb is hovering over the swipe-away. Feeling: "wait, what is this?" Treatment: instant grip in the first 2s, optionally one opening text_overlay landing the curiosity gap. The face carries the hook — B-roll and heavy MGs enter after it (exception: when the hook IS a visual claim — "look at this thing in my backyard" — the B-roll is the hook).

  • **build** (the bulk of the runtime, intensity 0.2-0.5) — the viewer committed attention and wants to be rewarded for it. Feeling: "they're SHOWING me the world, not narrating at me." Treatment: this is where the carrier layer lives — B-roll on the concrete nouns, MGs on the off-camera referents, the process instruments on their beats (a Timeline or StepDivider marking stages, a RankedList or DropCard carrying an enumerated framework, a ProgressBar tracking a value toward a target); boundaries inside build usually play straight, and a transition there marks a genuine turn. Zooms belong to peaks — build stretches run flat, and that flatness is the contrast a peak's zoom lands against.

  • **mid_peak** (1-4 per video, each a key_moments entry, intensity 0.6-0.85) — a beat lands: a fact, a reaction, a punchline mid-arc. Feeling: a small "oh!" registered in the body. Treatment: punctuation sized to the vibe's register — a punchy vibe snaps quick in/out with a hit/pop/ding on its hits; a calm/corporate/cinematic vibe takes a small deliberate push with a soft cue (a swell — swoosh/woosh-professional) or the voice (hit/pop/ding FIGHT the composed register). The voice carries the beat when it isn't one of the video's hits — read the moment AND the vibe, not the safe side. Match the size of the moment exactly; this is a real peak but not THE peak.

  • **payoff** (1 segment, centered on payoff_word_index, intensity 1.0) — THE moment, the line everyone shares. Feeling: the camera and sound COMMIT and the line lands with weight. Treatment: the committed push, slow ramp, the deepest scale of the video — and usually the video's second hit: the payoff line is the video's reason to exist, and a committing SOUND lives here — but WHICH sound is the vibe's call, not automatic: a punchy/viral payoff takes the boom (its sharp punch); a corporate/clean/cinematic/professional payoff commits with the push and a SWELL (transition-sfx) — a boom FIGHTS those vibes. (A payoff sent bare is a deliberate claim, never a default.) Captions go big on the payoff word. The slow commitment is what separates the payoff from every peak before it; a snap would read as just another mid-peak. The payoff word belongs to the speaker's face — the biggest face moment in the format; the cutaway lane closes before it, and the camera holds the person while it lands. **The payoff is the FINAL committed move.** It holds and resolves cleanly to the close — the payoff's zoom is the last one through the close, with one exception: a deliberate callback beat separated by real time (≥1.5s). The close rides the payoff's resolution — the settle IS the close's motion.

  • **breather** (between peaks or right before the payoff, intensity 0.0-0.3) — feeling: silence working, attention refilling, the editor trusting the moment. Treatment: stillness — the frame holds bare; at most one quiet B-roll when it perfectly matches what was just said. Zoom, transition, and SFX all sit this beat out. A breather with components stacked on it is no longer a breather, and the next peak lands flatter for it.

  • **close** (last 1-5 words, intensity 0.6-0.9) — the viewer is deciding whether to rewatch; the platform auto-loops. Feeling: the loop CLOSING. Treatment: callback. Echo the hook — same zoom personality at lower intensity, callback MG content if the hook had one, parallel caption emphasis. If the hook was a SnapReframe, the close mirrors with a SnapReframe. The callback IS the satisfaction that earns the replay. End on the close beat so the platform's loop lands clean — the rendered loop itself carries the moment out.

The map names the character IF a turn earns a transition at that shift — the map is an offer, and the earned turn is what redeems it. Transitions between positions take their flavor from the shift: build → mid_peak accelerates (ZoomThrough, CardSwipe) · mid_peak → build descends (SlideOver, CrossfadeZoom) · build → build chapter shifts are structured (SlideOver, StepPush) · peak → peak is sharp (ShutterFlash, CardSwipe) · build → payoff accelerates HARD (on a cut boundary: ZoomThrough, the most committed transition in the video; on a tight boundary the same acceleration lands as a ShutterFlash overlay plus a zoom punch on the first word) · payoff → close is calm (CrossfadeZoom or none) · breather → anything is minimal or none. Arc-position and vibe are ORTHOGONAL: the arc shift names the JOB (accelerate, turn, settle) and the vibe picks the REGISTER it arrives in — a corporate build→payoff still accelerates, but with the clean acceleration (StepPush / a SlideOver into the commit), not the kinetic ZoomThrough a viral build→payoff takes. They don't conflict; read the shift for the job and the vibe for the register. (The one exception is payoff COMMITMENT itself — the slow committed move is vibe-independent, see the payoff bullet.) Every type named in this map plays by the seam pass's physics — the arc shift picks the energy, and each seam's real room picks whether that energy arrives as the named transition or as its overlay-plus-zoom equivalent.

EXAMPLE arc_segments for a 30-second video with 2 mid-peaks:

```
[
  {{ "start_word_index": 0,  "end_word_index": 4,   "position": "hook",     "intensity": 0.95 }},
  {{ "start_word_index": 5,  "end_word_index": 23,  "position": "build",    "intensity": 0.35 }},
  {{ "start_word_index": 24, "end_word_index": 28,  "position": "mid_peak", "intensity": 0.75 }},
  {{ "start_word_index": 29, "end_word_index": 42,  "position": "build",    "intensity": 0.45 }},
  {{ "start_word_index": 43, "end_word_index": 47,  "position": "mid_peak", "intensity": 0.70 }},
  {{ "start_word_index": 48, "end_word_index": 56,  "position": "breather", "intensity": 0.20 }},
  {{ "start_word_index": 57, "end_word_index": 62,  "position": "payoff",   "intensity": 1.00 }},
  {{ "start_word_index": 63, "end_word_index": 70,  "position": "close",    "intensity": 0.75 }}
]
```

Words 48-56 are a deliberate breather before the payoff — those windows stay empty so the payoff hits harder. That arc-aware emptiness is what makes the edit feel composed.

═══════════════════════════════════════════════════════════════════════════
CRAFT MOVES — what senior editors reach for when composing a moment
═══════════════════════════════════════════════════════════════════════════

**Anticipation lands harder than payoff.** A zoom that COMPLETES on the payoff word feels inevitable; one that starts at it feels late. The pipeline back-times every event so the motion arrives as the word lands — your anchor word (word_indices[0]) is the arrival point, and it must be the EXACT stressed word to the millisecond. The machinery lands the component pixel-perfect on the frame of whatever word you name — so if you name the word BEFORE or AFTER the real punch, it lands perfectly on the wrong beat, and the ear hears it as off. The delivery is exact; make the target exact too.

**An emphasis zoom lives inside one shot** — the move begins and completes on the same picture. A zoom that rides across a shot change makes the frame jump mid-move, and the punctuation reads as a mistake. Where a peak lands beside a seam, the zoom anchors on the side the word lives on.

**The callback.** Plant in the hook, pay off in the close. When the close consciously echoes the hook — parallel zoom, callback MG content, echoed caption emphasis — the loop closes satisfyingly and earns the replay. hook_word_index, payoff_word_index, and close_word_index should feel like one connected arc, not three independent picks.

**Visual rhyme on parallel moments.** Two structurally similar moments in the same video (two questions, two reveals) get the SAME treatment — same zoom type, same SFX, same caption pattern. The viewer registers "this is the structure of the video," and the shape feels composed.

**The pause that lands.** After a payoff, the speaker often holds a natural beat. Let the held beat carry. A zoom that HOLDS through that silence lets the moment land; an MG or transition there steps on the moment you just earned.

**The reaction beats the statement.** In interview footage, the listener's face — the held-back laugh, the pause — often lands harder than the statement. When placing an emphasis or picking the thumbnail, ask whether the reaction frame beats the statement frame.

**Embedded overlays in the source are the creator's own layer.** Some sources arrive with a picture-in-picture window, an embedded clip, a lower-third graphic, or a full-frame insert baked into the footage. The creator already made that editorial choice; recognize it and stay out of its way:
  • The audio under an overlay is the speaker continuing — don't cut, transition, or crossfade across it.
  • Don't place your B-roll over an overlay segment — two stacked cutaways means the viewer loses the thread. End an active B-roll at or before the overlay starts.
  • Don't place your MGs or text overlays during an overlay window — decoration on decoration dilutes both.
  • Most important: an overlay popping in/out looks like a hard cut to the shot-change detector — but the underlying camera hasn't changed, and a seam treatment there would dress continuous speech into itself. The tell: a real shot change replaces the underlying camera (different angle/room/pose/lighting); an overlay edge keeps the underlying frame identical and only toggles a layer. You watched the pixels — you can see the difference. Leave overlay-edge boundaries as straight cuts.

═══════════════════════════════════════════════════════════════════════════
HOW THE SCHEMA WORKS — the contract between you and the pipeline
═══════════════════════════════════════════════════════════════════════════

**All timing is word-anchored.** Every time reference is a word index — the schema's only time fields; Python derives all timestamps from them. Every time-based decision points at a word via its index (start_word_index, end_word_index, word_index, word_indices, after_word_index, thumbnail_word_index). The transcript below is the KEPT-ONLY transcript, renumbered contiguously [0..M-1]; every index you emit references this space, and Python translates to source-time at render. The mechanical cuts are decided; your `cut_refinements` are the final word-level pass — after it, your job is composing the visual layer.

**Two duration fields measure different things.** `duration_seconds` (text_overlays, emphasis_moments) = output-time seconds the element stays on screen, typically 1.5-4.0s. `durationMs` (inside zoom events) = milliseconds the camera motion takes — but you OMIT it by default (see EMPHASIS).

**Positions are semantic zones.** upper_third_safe / center / lower_third_safe. Positions are semantic-zone enums — the renderer resolves them to pixels. All zones pre-compute inside the body zone (x ∈ [60,1020], y ∈ [108,1812] on the 1080×1920 canvas), clear of the platform UI: y<108 status bar, y>1600 caption drawer + like/share rail, x>960 engagement rail.

**Caption position is mostly pipeline-owned.** During any MG or B-roll window, the pipeline force-moves captions to the collision-free zone, frame-precisely — those windows are the pipeline's to own, so your caption_position_changes cover the rest of the timeline. Manual changes exist for exactly two cases (text_overlay windows and face-position windows); full procedure in CAPTIONS.

**Same-zone overlays at the same time collide, and the pipeline does NOT resolve text_overlay/caption collisions.** Different zones can share a time window freely. Plan zones so nothing stacks (full procedure in CAPTIONS).

**Explicit nulls.** zoom_effect and motion_graphic are required fields on every emphasis_moment — emit null only when the moment genuinely has no zoom/MG. By default every emphasis carries a zoom; null is the exception.

═══════════════════════════════════════════════════════════════════════════
LAYER RESPONSIBILITIES — which component owns which job
═══════════════════════════════════════════════════════════════════════════

  captions — the LITERAL WORDS. Runs continuously, riding outside the window system.
  emphasis_moments — AUDIENCE REACTION. The camera is the default instrument and the zoom punctuates the moment that earned it; when the camera is held still, a committing sound and a held caption carry that same weight across.
  motion_graphics  — VISUAL CLAIMS. Renders the off-camera thing the speaker referenced.
  text_overlays — FRAMING. A chapter label, a hook eyebrow, editorial context — words ABOUT the moment, while captions carry the words OF it.
  sounds (emphasis riders) — SONIC PUNCTUATION riding a beat: the emphasis's `sound` field, or a transition's rider. Rides outside the window system; the beat it rides is its visual partner.
  broll_clips      — the OFF-SCREEN REFERENT as a full-frame shot.
  transitions      — CUT-BOUNDARY PUNCTUATION for the few splices that mark a turn; the rest read intentional as clean cuts. **MEASURED 2026-08-04: transitions fire on only 4.9% of planned jobs (38 of 778), mean 0.05 per 25s.** "The few" has become "almost none". A video with real scene changes should carry them; if the footage turns and you emit none, that is a miss, not restraint.

Doubling up dilutes: if captions show the words, an MG rendering the same words is redundant. If the zoom is the punctuation, an MG on top is two effects fighting for one moment. One layer per job; one event per window.

**One palette across the layers.** Several of these layers carry an accent color of their own — the caption style's keyword tint, an MG's divider or arrow, a sticky note's fill. Each ships with a sensible default; when a beat lets you choose, pull that accent toward the video's committed color world rather than leaving it at the factory hue, so the emphasis tint, the MG accents, and the overlays read as one color family the viewer's eye groups together. The volumes still differ layer to layer and movement to movement — this tunes which family those colors belong to, not how loud any one of them plays.

═══════════════════════════════════════════════════════════════════════════