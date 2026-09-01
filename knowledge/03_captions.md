=== CAPTIONS ===
═══════════════════════════════════════════════════════════════════════════

Captions render every spoken word and run the entire video, continuous from first word to last. One style runs the whole video; only position shifts per segment. Caption_style is one of the 2-3 loudest signals about what the video IS to someone scrolling past — it's the video's typographic voice. Pick by the specific character of THIS video — its pace, its voice, its energy; the genre is just the room it stands in.

**Style rotation:** the user's style profile shows their recent caption styles. Whatever they used in their last 2-3 videos is off the candidate list — same style every video reads as template, not voice.

The footage's surfaces pick the palette's contrast: keyword colors that sit near the scene's dominant tones read as texture, and the strong choice separates from what the frame is made of.

**Keywords:** 5 of 9 styles highlight words in `caption_keywords` with their signature treatment; 4 ignore keywords (the animation IS the effect). For keyword styles, density carries the identity — roughly 1 keyword every 3-4 spoken words (≈18-25 for a 30s video, 35-50 for 60s), spread across the WHOLE transcript (a back half with no keywords goes flat exactly when the viewer decides whether to rewatch). Earns a keyword: concrete nouns, emotional verbs, vivid adjectives, names, places, brands, numbers, prices, punchline and reveal words. Keyword status goes to content words — the nouns, verbs, and numbers that carry the beat; articles, prepositions, conjunctions, auxiliaries, and pronouns stay plain (a pronoun that IS the punchline earns the exception). Lowercase, dictionary form, letters only.

──────────────────────────────────────────
THE {_n_styles} STYLES
──────────────────────────────────────────

The caption style governs the CAPTION LAYER — the type, its animation, its keyword treatment. It does not set how much else the video carries. A quiet typeface on footage with four real scene changes still takes four transitions; a loud one on a single continuous shot still takes none. Density comes from the footage and the moments, never from the caption's voice. Each style's Fits/Fights below is about what DELIVERY the typography suits, never about the edit.


1. **Prime** — two-tier: white Inter body; keywords break out onto their own line in oversized italic Playfair (~66pt) with cyan tint (#5ED4E8). Spring entrance. Keywords: USED. Signal: two-tier typographic hierarchy — the oversized italic keyword breaks above the plain body line and carries the visual weight. Fits: aspirational, self-improvement, and premium-branding delivery registers; speech with clear keyword peaks the breakout line can lift onto. Fights: casual speakers; flat, even-weight delivery where no single word peaks, leaving the two-tier hierarchy nothing to elevate.

2. **TypewriterReveal** — Space Mono, character-by-character reveal with blinking cursor; schemes: classic (white), terminal (green CRT), amber (phosphor). Keywords: IGNORED. Signal: typed in real time. Fits: tech/coding, documentary narration, hacker or retro-CRT registers, slow deliberate delivery. Fights: high-energy delivery; speech faster than the typing animation.
   Optional extraProps: {{ "scheme": "classic" | "terminal" | "amber" }}

3. **Cove** — bold Montserrat body; keywords swap to ~2x oversized italic Playfair with warm ethereal glow. Keywords: USED. Signal: keywords held up with reverence — the oversized glowing italic serif treats each keyword as precious. Fits: premium/luxury and wellness registers, brand storytelling, slow deliberate delivery — the register the warm italic-serif keyword treatment suits. Fights: aggressive, high-energy delivery and casual, offhand delivery, where a reverent warm-serif keyword treatment reads as mismatched.

4. **Lumen** — Montserrat body; keywords swap to Playfair with amber glow (#D4A24C) and a gold shine sweep (an angled lens-flare strip across the word). Keywords: USED. Signal: keywords gilded — money and brand words get the amber-glow, gold-underline stamp. Fits: hustle, motivational, money/business/success delivery registers whose keywords are value words (numbers, prices, named brands) for the gold treatment to gild. Fights: understated or melancholic delivery (the loud gold clashes with a quiet register); delivery with no money or value words for the keyword treatment to key off (the gold reads arbitrary).

5. **Pulse** — words appear in synchronized PAIRS, one above one below, crisp opacity fades; keywords go coral (#FF6B4A). Keywords: USED. Signal: rhythmic pulse — paired words fade on and off in sync. Fits: sung or musical delivery, rapid dialogue, the doubled cadence of a lyric video. Fights: contemplative, unhurried delivery needing per-word breath; adjacent words of very different length.

6. **Quintessence** — ONE word at a time, centered, large Playfair with dramatic vertical stretch (scaleY 1.6), gold (#E8D44D), quick fade in/out. Keywords: IGNORED. Signal: each word made monumental, one alone in the frame; art-house register. Fits: delivery built on dramatic pauses — poetry, mantras, slow deliberate dialogue. Fights: dense or fast dialogue, where the spring in/out turns to stutter.
    Optional extraProps: {{ "stretchY": 1.6 }} default · 2.0 extreme · 1.3 subtle

7. **TwoTone** — big stacked all-caps words two lines deep: a white top line over an accent-color bottom line, each word a chunky 3D "sticker" block (thick dark contour + downward extrude) that slams in oversized and settles; the page splits across the two lines automatically. Keywords: IGNORED. Signal: two words, two colors — a two-line white-over-accent split. Fits: short, shouted, two-part hooks — a line that breaks cleanly into two beats to fill the two stacked words ("STOP / SCROLLING", "THIS CHANGES / EVERYTHING"); loud, exclamatory delivery. Fights: long sentences that will not compress into two words; calm, quiet, or contemplative delivery; warm serif registers.
8. **CleanCut** — one plain crisp word on screen at a time, centered, with a subtle rise-and-settle and a soft legibility shadow. No color, no flair — the deliberate no-style style; long words wrap and stay inside the safe margins. Keywords: IGNORED. Signal: plain, unstyled legibility — the word carries no typographic voice of its own. Fits: serious, restrained, or cinematic-register delivery; measured, deliberate speech that reads well under neutral type with no stylistic accent coloring it. Fights: hype or high-energy delivery, and any moment that wants a decorated or keyword-accented word — plain type reads flat where punch is wanted.

9. **Gadzhi** — Montserrat 700 uppercase, left-aligned tight two-word lines; words slide up from below with a smooth ease-out, settling gray → white with keywords landing in gold (#F5C518). Keywords: USED. Signal: a confident, self-assured money-talk voice — hard uppercase, named numbers and money terms landing in gold. Fits: business/hustle and SMMA-style delivery; product pitches that name numbers, where figures and money terms suit the gold keyword treatment. Fights: warm serif registers; soft, gentle, or playful delivery, where the hard uppercase money-talk voice clashes.

Keyword styles: Prime, Cove, Lumen, Pulse, Gadzhi — these are the ONLY styles that read `caption_keywords`. Keyword-ignoring: TypewriterReveal, Quintessence, TwoTone, CleanCut — for these, emit `caption_keywords: []`. Nothing downstream reads the field on these four styles (the renderer passes it only to the caption component, and theirs discards it), so words listed there are written and thrown away.

──────────────────────────────────────────
CAPTION POSITION — collision procedure
──────────────────────────────────────────

caption_position_changes entries: {{"word_index": int, "position": "top" | "center" | "bottom"}} — captions move at that word and stay until the next change. Default is bottom at word 0; bottom is the resting state, and every move away from it gets a matching move back when the trigger ends. Each position holds ≥1.5s (≈4-6 words); shorter reads as flicker.

**The pipeline owns caption position during MG and B-roll windows** — it force-flips captions away from any motion graphic's zone, and to the lower third during B-roll (clear of the b-roll subject, whose face sits upper-center), frame-precisely. The pipeline's force-flip owns those windows and handles them frame-precisely — caption_position_changes apply everywhere else on the timeline. You emit manual changes for exactly TWO cases:

1. **text_overlay windows.** The pipeline does not auto-resolve text_overlay/caption collisions. sticky_note occupies the upper third, caption_match its position prop. Captions default to bottom, so most overlay placements need no change — but if anything has moved captions to top or center, return them to bottom for the overlay's word range, or place the overlay at a different time.
2. **Face-position windows.** When the FACE VISIBILITY signal shows the speaker's face in the bottom band (looking down, low framing), emit "top" at the start of that window and "bottom" when the face returns up.

The most common mistake: emitting a change that moves captions INTO a zone an upcoming text_overlay occupies. Before emitting any change to "top" or "center", scan text_overlays for overlapping word ranges in that zone.

**When a graphic becomes the text, the captions rest.** A movement led by a full graphic — a built list, a structured teach card — already carries its words on screen, large and deliberate. Letting captions run underneath puts two text layers in one eyeline and the viewer's reading splits between them; the graphic loses the room it needs to lead. So for the span a takeover graphic owns, the captions step aside and let it carry the words, and they return the moment the speaker's face is the frame again. This is the one place in the video captions go quiet on purpose — everywhere the face leads, they run.

═══════════════════════════════════════════════════════════════════════════