=== TEXT OVERLAYS ===
═══════════════════════════════════════════════════════════════════════════

A text overlay is a short editorial card on screen for 1.5-4 seconds — a hook label, a topic eyebrow, an act-break marker, three parallel items. Captions show what's being said; an overlay shows framing — two different jobs on two different layers. **An overlay's text is editorial — words about the moment; the transcript already lives in the captions.** If the candidate text duplicates what captions are about to show, rewrite it as a label ("THE NAME", "WHO?") or skip it. And if the candidate text could fit any video in this genre, rewrite it from video_identity's specifics.

An overlay marks structure. It tells the viewer where they are in the video: a cold-open hook frame that names the promise, a chapter eyebrow at a genuine pivot, an attributed third-party quote, three parallel items the speaker enumerates. The anchor summons the overlay — chapter turn, act shift, hook eyebrow — so read the script for its turns, and where the video changes chapters, let the overlay say so. A video with clear structural turns wants an overlay at each one; a video that runs as one continuous thought lets the captions carry it.

Geometry: captions sit at bottom, the face sits in the upper-middle band, so the upper third is the natural overlay home. Keep captions at bottom during overlay windows (see CAPTIONS procedure).

Entry shape:
  {{
    "variant": "sticky_note" | "caption_match",
    "start_word_index": int,
    "duration_seconds": float,        # 1.5-4.0s typical
    ...variant-specific props
  }}

────────────────────────────────────
sticky_note — pins to the upper third
────────────────────────────────────
Three colored square notes (~300px) pinned left/center/right; handwritten Caveat Brush, ≤4 words per note; left note carries a checkmark, center plain, right italic+underlined. Notes slam in with spring physics, staggered ~150ms.
Use when the dialogue gives you THREE PARALLEL ITEMS of equal weight — three rules, three takeaways, "first… second… third…". Each note is a complete standalone thought; fragments of one running sentence read as a broken sentence in three boxes. Warm, casual craft texture — fits educational/process/how-to tone. The three-note rhythm is the moment — the stagger, the slam, the three ideas landing as one. It lands where the dialogue gives three parallel items of equal weight.
**ONE COMPONENT, TWO HOMES — route it, never duplicate it.** This renders the IDENTICAL component as the StickyNotes motion graphic; same pixels either way. Emit it HERE, as a text_overlay, when the three items MARK STRUCTURE — the video's own three rules, three takeaways, three chapters, the framing the speaker is laying over the moment. Emit it as a motion_graphic instead when the three items ARE the referent the speaker is pointing at off-camera — three things on a list they are reading, three notifications, three names. Structure is an overlay; evidence is a graphic. NEVER emit both for one moment.

Required props:
{{
  "notes": [
    {{"text": "MOVE FAST",   "color": "#FFE066", "rotation": -3}},
    {{"text": "BREAK STUFF", "color": "#FFB3C1", "rotation": 1}},
    {{"text": "FIX LATER",   "color": "#A8E6CF", "rotation": 4}}
  ]
}}


────────────────────────────────────
caption_match — position "top" or "center"
────────────────────────────────────
A short label (≤6 words) rendered in the SAME font/style as the running captions — a structural marker that visually belongs. Topic eyebrows ("PART 1", "Q1"), brand tags, cold-open hook labels. Strongest on edits where the caption style IS the visual identity. It reads as structure because it looks like the captions — a marker in the video's own typographic voice, landing where the video turns.
**On centered talking-head — the vast majority of footage — position is "top".** 'top' keeps the face clear on centered talking-head, which is most footage. 'center' is the choice when the frame belongs to the overlay — the speaker off-camera for the window, the face confirmed non-center by the FACE VERTICAL ZONE signal, or a deliberate full-screen takeover where the screen IS the moment.

Required props:
{{
  "text": "PART 1: THE SETUP",   # ≤6 words
  "position": "top" | "center"   # default "top"
}}

═══════════════════════════════════════════════════════════════════════════