=== RESPONSE FORMAT ===
═══════════════════════════════════════════════════════════════════════════

Output is a bare JSON object — the response is JSON-parsed and the parser is the only reader; the first character is `{{` and the last is `}}`.

{{
  "video_identity": "<2-3 sentences: what makes this video specifically THIS video. Include a proper noun or named object from the dialogue, a specific moment from the story, and a detail that would surprise someone hearing it described. Phrase it as THIS video's specific identity — the concrete subject and stake; a genre-shaped phrasing ('a personal story about...') describes a thousand videos, and this field describes one.>",
  "existing_caption_region": "none" | "bottom" | "top" | "other",  ← "none" unless burned-in word captions are clearly visible as synced text across multiple sampled moments
  "source_text_regions": ["top" | "center" | "bottom", ...],  ← bands the source's own NON-caption text occupies (watermark, UI, existing overlays); omit when the frame is clean
  "video_plan": {{
    "what_happens": "<1-2 sentences: literal narrative summary>",
    "hook_word_index": int,
    "payoff_word_index": int,
    "close_word_index": int,
    "key_moments": [
      {{
        "word_index": int,
        "what_lands": "<one short sentence>",
        "why_emphasis": "<one short sentence>",
        "what_i_saw": "<one short phrase on what's visible in the proxy at this word. Example: 'eyes widen, head tilts back'>",
        "viewer_feeling": "<one specific phrase: the feeling this moment produces>"
      }},
      ... {_peak_count_ref}; count what the footage actually has — the honest count is the deliverable ...
    ],
    "story_shape": "<one sentence: hook → setup → development → payoff → close>",
    "arc_segments": [
      {{"start_word_index": int, "end_word_index": int, "position": "hook" | "build" | "mid_peak" | "payoff" | "breather" | "close", "intensity": float}}
    ],
    "movements": [
      {{"start_word_index": int, "end_word_index": int, "job": "<one phrase: what this movement is doing>", "energy": "hot" | "deep" | "calm", "lead_instrument": "kinetic_captions" | "annotation" | "takeover_graphic" | "clean_frame", "captions": "run" | "rest"}}
    ],
    "editorial_vision": "<ONE specific sentence committing to HOW you'll cut THIS video. Every component below flows from it.>"
  }},
  "thumbnail_word_index": int,

  "caption_style": {_caption_enum},  // "none" only when the user's vibe excluded captions
  "caption_keywords": ["<word>", ...],   // lowercase, dictionary form
  "cut_refinements": [
    {{
      "start_word_index": int,                  // KEPT-space, inclusive range (single word: start == end)
      "end_word_index": int,
      "reason": "<≤10 words naming what's cut>"
    }}
  ],

  "caption_position_changes": [
    {{"word_index": int, "position": "top" | "center" | "bottom"}}
  ],

  "audio_denoise": bool,
  "outro": "none" | "fade_black" | "fade_white",
  "aspect_ratio": "9:16",
  "notes": "<≤50 words>",

  "emphasis_moments": [
    {{
      "word_indices": [int, ...],
      "type": "punchline" | "revelation" | "statement" | "reaction" | "question",
      "intensity": "high" | "medium",
      "duration": float,                          // 1.5-3.0 output-seconds
      "viewer_feeling": "<one specific phrase>",
      "zoom_effect": {{
        "arc_position": "hook" | "build" | "mid_peak" | "payoff" | "breather" | "close",   // your claim — the position this zoom serves; each offers its own types (build/breather: ONLY the mask form)
        "type": <the claimed position's offering — the schema knows>,
        "originX": float, "originY": float         // ONLY for non-face zoom targets; omit for faces — the face-lock aims. durationMs/scale likewise omitted unless a beat genuinely wants a non-default feel.
      }} | null,
      "sound": <one of the 16 sounds, or "voice">,   // REQUIRED — the signed choice; see THE SOUNDS
      "motion_graphic": {{ "type": <MG type>, "anchor": <semantic zone>, "props": {{...}} }} | null   // almost always null
    }}
  ],

  "text_overlays": [
    {{
      "variant": "sticky_note" | "caption_match",
      "start_word_index": int,
      "duration_seconds": float,
      "why": "<≤12 words: the moment that asked for this>"
      // ...variant-specific required props per the TEXT OVERLAYS section
    }}
  ],

  "broll_clips": [
    {{
      "keyword": "<13-18 words evoking what the speaker is describing>",
      "start_word_index": int,
      "end_word_index": int,
      "reason": "<one short sentence telling the picker what the clip must SHOW beyond the keyword — the specific visual that makes it right or wrong (e.g., 'must show an app's text-input field on screen, not a person holding a phone'). The picker reads this as an editor's note when choosing between candidate clips.>"
    }}
  ],

  "motion_graphics": [
    {{
      "type": {_mg_enum},
      "why": "<≤12 words: the moment that asked for this>",
      "start_word_index": int,
      "end_word_index": int,
      "duration_seconds": float | null,
      "anchor": "upper_third_safe" | "center" | "lower_third_safe",
      "props": {{...}}
    }}
  ]
}}

Every anchor field references the kept-only index space [0..M-1] shown in the transcript below. Word indices are your entire time vocabulary — Python derives all timestamps from them and translates back to source-time at render.