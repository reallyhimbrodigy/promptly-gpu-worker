# The 66 — rules naming no value this lane rules on, for Zac's ruling

Swept body-first 2026-09-11. These are rule-shaped sentences that name **no**
enum value this lane rules on. They are not translation work: each needs a
decision about whether this pipeline should let the agent choose that family
at all.

## Mechanical family assignment FAILED, and that is itself the finding

A first-match classifier put a transition sentence under `caption` and a caption
sentence under `sfx`, because **these sentences span families** — "a transition
firing at a cut boundary plus a zoom landing on the adjacent peak word is one
composed event" is about transitions, cuts and zooms at once. 29 of 66 fell
into `other`.

So they are grouped by DOCUMENT, which is reliable, with every family word each
sentence mentions listed beside it. That is the generalisation of the
`build` finding: one enum value governed by two families' rules becomes one
SENTENCE governing several, and a taxonomy that assigns each to one owner
produces a confident wrong answer.

## 01_cut_pass.md (13)

- **[cut]** ** Under a cleanup-request vibe this pass works HARDEST on the three redundancy classes; under 'keep every pause / don't cut anything' emit [].
- **[zoom]** Out-of-order thinking — picking a zoom before naming the arc — produces decisions that don't reference the spine.
- **[zoom]** **key_moments and emphasis_moments are 1:1** — this list is the ground truth for what gets a zoom.
- **[zoom]** To add a zoom, expand this list first; only zoom peaks you can justify here.
- **[overlay/MG, transition]** • The audio under an overlay is the speaker continuing — don't cut, transition, or crossfade across it.
- **[overlay/MG]** • Don't place your MGs or text overlays during an overlay window — decoration on decoration dilutes both.
- **[overlay/MG]** The tell: a real shot change replaces the underlying camera (different angle/room/pose/lighting); an overlay edge keeps the underlying frame identical and only toggles a layer.
- **[caption, overlay/MG]** Manual changes exist for exactly two cases (text_overlay windows and face-position windows); full procedure in CAPTIONS.
- **[overlay/MG, zoom]** ** zoom_effect and motion_graphic are required fields on every emphasis_moment — emit null only when the moment genuinely has no zoom/MG.
- **[zoom]** By default every emphasis carries a zoom; null is the exception.
- **[caption, sfx, zoom]** The camera is the default instrument and the zoom punctuates the moment that earned it; when the camera is held still, a committing sound and a held caption carry that same weight across.
- **[transition]** **MEASURED 2026-08-04: transitions fire on only 4.
- **[overlay/MG, zoom]** If the zoom is the punctuation, an MG on top is two effects fighting for one moment.

## 05_motion_graphics.md (13)

- **[no family word]** The placement test is one question: **what specifically is the speaker referencing?
- **[caption, cutaway]** upper_third_safe works when face clearly center-or-lower; card touching face from above → use lower_third_safe with captions flipped top, or B-roll window.
- **[caption, overlay/MG]** Anchor preference, MG: 1) **upper_third_safe** — default · 2) **center** — only under THE ANCHOR LAW · 3) **lower_third_safe — LAST RESORT ONLY** (bottom MG forces captions off their lower-third home to top, scatters frame; genuinely footer-like content only, when upper and center both taken).
- **[caption]** Plainer treatment landing the same moment with more confidence — caption held a beat longer, clean emphasis, speaker's own face given the frame — is the more produced choice.
- **[transition]** Text echoing the speaker's wording → viewer reads screen and voice as one thing, moment lands twice; drift into paraphrase or generic stock label → screen and voice split, viewer feels the seam.
- **[overlay/MG]** Emit it HERE, as a motion_graphic, when the three items ARE the referent the speaker points at off-camera; emit the text_overlay instead when the three items MARK STRUCTURE.
- **[no family word]** " **FITS:** MOMENT SHAPE — use as ambient texture when the speaker rattles off MANY related keywords or hashtags and you want a continuous ticker feel, the STREAM itself the texture, rather than a tidy group ("mindset, focus, discipline, habits, growth…") — 6+ tags read best.
- **[no family word]** " Use when one spoken sentence is the punchline and deserves the full frame ("most people quit right before the breakthrough") — pass the line as text and the 1–2 hit words as keywords.
- **[no family word]** **FITS:** any vibe — a REAL quoted tweet in the story is the gate; the card texture leans viral/casual/commentary.
- **[no family word]** **FIGHTS:** as non-diegetic decoration where no tweet is referenced; the social texture only *discourages* in corporate/cinematic, it never blocks a genuine reference.
- **[no family word]** **FITS:** any vibe — a real quoted text message is the gate; leans casual/viral/storytelling.
- **[no family word]** **FIGHTS:** as decoration; a consumer-chat texture only *discourages* in formal-corporate/cinematic when no message is quoted.
- **[no family word]** **FITS:** any vibe — a real phone event (paid/texted/called) is the gate; leans casual/viral/product.

## 06_emphasis_zoom.md (9)

- **[zoom]** "Free", "professional", "done" can each be semantically central and still earn NO zoom if the delivery just states them.
- **[zoom]** EMPHASIS zooms map 1:1 to key_moments — they are the ledger of the video's loudest beats, and every one carries its moment.
- **[sfx]** Pick each emphasis by the AUDIENCE REACTION it earns with sound on: laugh = punchline, gasp = revelation, nod = statement, empathy = reaction, lean-in = question.
- **[caption, sfx, zoom]** **Zoom personality by arc position** — the arc position names the JOB the move must do; the VIBE picks the REGISTER it does it in (punchy vs calm), exactly as the vibe scopes a caption style or a sound.
- **[zoom]** For each peak independently: "what camera move would a real editor pick if this were the ONLY zoom in the video?
- **[zoom]** Emit originX/originY ONLY when zooming a NON-face element (a prop, a gesture, a whiteboard); emit durationMs/scale only when a specific beat genuinely wants a non-default feel (rare).
- **[zoom]** **Per-clip zoom spacing:** the camera must fully play each move (in → hold → out) before the next, so emphasis zooms sharing a clip must sit ≥ the type's natural duration apart (space the anchor words).
- **[no family word]** Specialty: only when a detail AND its context genuinely matter simultaneously.
- **[zoom]** If the moment has only ONE emphasis word, use a NORMAL zoom (SmoothPush/SnapReframe), never this.

## 08_broll.md (7)

- **[cutaway]** ** A second Gemini call sees the candidate clips' thumbnails plus the dialogue line AND this `reason` as the required content for the cutaway, and keeps only clips that visually satisfy it — vibe-match alone falls short, so the `reason` you write is the contract the picker holds clips to.
- **[no family word]** **App-input beats hold on the speaker — the downstream picker answers NONE for them short of a clip showing the actual app screen, so the hold is the move that survives.
- **[no family word]** The trap is forcing the beat into mode (1) and grabbing the literal object the WORD rhymes with — "quality" → a camera lens, "value" → a stack of cash, "powerful" → a roaring engine, "results" → a finish-line tape — none of which is what the speaker meant; each is noun-rhyme clutter.
- **[no family word]** **Abstract-attribute beats hold on the speaker — the picker's coincidental-noun-match rule resolves them to NONE downstream, so the hold is the read that ships.
- **[no family word]** Start from the VERB; add subject and setting (concrete noun + motion + mood + production tier); one subject doing one thing; context words only to disambiguate ("cinematic lighting" to filter cartoons).
- **[no family word]** The broadening rule applies ONLY to a GENERIC subject that has no name: keep THAT broad (a countdown timer, a hundred-dollar bill, a doorstep package — not "a glowing digital stopwatch at 00:25 in a parking garage") and pile the look/quality adjectives on top of it.
- **[no family word]** Named real entity → emit as-is; unnamed generic → keep broad; composite stack of constraints → the real NONE trap, avoid.

## 00_job_and_arc.md (6)

- **[transition]** One to three transitions is the natural budget of a lean edit; most boundaries play straight, and that IS the polish.
- **[caption, cut, overlay/MG, transition]** • **Cleanup requests** ('edit out the dead space', 'cut the retakes/filler', 'clean it up', 'tighten it', 'just make it postable') → the request IS the edit: cutting works at maximum aggression (see YOUR CUT PASS), and the decoration layer drops to the lean floor — captions run, 1-3 earned emphasis beats, transitions and MGs only where a 
- **[no family word]** quickness is the texture you want; it reads as momentum.
- **[zoom]** A genuine peak → a zoom candidate.
- **[overlay/MG, zoom]** Zooms, MGs, and overlays choose their own beats — they move to an adjacent window or drop.
- **[transition, zoom]** ** A transition firing at a cut boundary plus a zoom landing on the adjacent peak word is one composed event, not a stack — the transition is the doorway into the beat.

## 03_captions.md (5)

- **[no family word]** The footage's surfaces pick the palette's contrast: keyword colors that sit near the scene's dominant tones read as texture, and the strong choice separates from what the frame is made of.
- **[caption]** **Keywords:** 5 of 9 styles highlight words in `caption_keywords` with their signature treatment; 4 ignore keywords (the animation IS the effect).
- **[caption]** Nothing downstream reads the field on these four styles (the renderer passes it only to the caption component, and theirs discards it), so words listed there are written and thrown away.
- **[sfx]** Default is bottom at word 0; bottom is the resting state, and every move away from it gets a matching move back when the trigger ends.
- **[caption]** This is the one place in the video captions go quiet on purpose — everywhere the face leads, they run.

## 14_card_text_placement_rules.md (4)

- **[no family word]** Scoped to CARDS and TEXT because those are the families confirmed reachable.
- **[no family word]** **Card almost never runs alone: 39 of 40 (97.
- **[no family word]** That is the only place text is genuinely wrong.
- **[no family word]** **Text is the default, and its absence is the decision.

## 15_ffmpeg_placement_recipes.md (3)

- **[no family word]** NEVER hardcode an x — text width varies.
- **[no family word]** drawbox first, drawtext second — order is the z-order.
- **[no family word]** motion is the entire reason to use a component instead of drawtext.

## 07_sound_effects.md (2)

- **[sfx, transition, zoom]** The graphics, zooms, and transitions this plan adds are the edit's answer to those same moments — when a sound and a component land on the same word, each earned it from the footage independently: the graphic renders the fact, the sound punctuates the delivery.
- **[sfx, transition]** **FIGHTS:** corporate, clean, professional, educational; and cinematic/story climaxes — a boom PUNCHES (sharp attack) where a cinematic climax SWELLS, so a story climax reaches for transition-sfx or a swell, never boom's punch.

## 02_intent_standard.md (1)

- **[no family word]** That question is the whole standard.

## 04_text_overlays.md (1)

- **[caption, overlay/MG]** Geometry: captions sit at bottom, the face sits in the upper-middle band, so the upper third is the natural overlay home.

## 09_seam_treatments_transitions_tight_.md (1)

- **[caption, sfx, zoom]** Same-scene splices need nothing from you: the hard cut owns them, and their energy goes where it belongs — a mask-zoom on the first word back, a caption that leans in, an SFX that lands the beat.

## 13_placement_findings.md (1)

- **[sfx]** Text is the dominant family and emphasis/SFX are the rare ones.

## What Zac's own corpus already says about one of them

**Transitions are 0 of 153 reference beats.** Eight of these 66 are transition
craft, and the reference corpus never places one — so that family likely stays
closed, and wiring its rules would be teaching a choice the references never
make. The other families have no such signal either way from here.

