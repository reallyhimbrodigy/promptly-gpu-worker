# LANE-SEAM → HARNESS: golden obedience cases for the Step-3 surgical ops

Two new tweak ops exist dark behind `PROMPTLY_SURGICAL_V2` (per-job override:
`input_data.surgical_v2_test = true`). Each needs a golden obedience case in
the corpus. Specs below are exact; HARNESS owns where they live in `golden/`.
Deterministic validators back both ops (surgical_ops.py, certified by
cert_surgical_ops.py 6/6), so the golden bar is obedience-marker presence,
not model luck.

## Case S3-A — caption-text override (the job-2026-07-24 class)

- Input: any golden talking-head job whose transcript contains the word
  `rise`; mode=tweak with `change_request = "change 'rise' to 'ryze'"` and
  `surgical_v2_test = true`.
- GREEN when ALL of:
  1. plan-diff classifies `tweak` (not needs_clarification).
  2. `new_plan.caption_text_overrides` contains
     `{"find": "rise", "replace": "ryze"}` (validator guarantees find matches
     the transcript or the entry is dropped WITH a note — a dropped entry
     here is a RED).
  3. rendered caption tokens display `ryze` and never `rise` at that slot
     (display layer only: transcript words, cuts, and timings byte-identical
     to the parent).
  4. Everything the ask didn't touch: byte-identical (ops-merge guarantee).
- RED marker: an applied plan with neither the override entry NOR a note —
  the silent-drop class.

## Case S3-B — add-transition-at-seam

- Input: a golden tweak job; `change_request = "add a DipToBlack after
  '<word>'"` where `<word>` is the last word before a real cut whose silence
  gap fits DipToBlack's natural frames (TRANSITION_DURATION_FRAMES); flag on.
- GREEN when:
  1. classification `tweak`; `new_plan.transitions` gains exactly
     `{"after_word_index": K, "type": "DipToBlack"}`.
  2. no pre-existing transition was touched (validator never judges old
     entries).
- Negative twin (same corpus entry, second request): ask for a
  `CrossfadeZoom` at a seam whose gap is too small → the transition is
  ABSENT from the plan AND `human_summary` carries the "skipped rather than
  squeezed" note. A squeezed/shortened transition or a silent absence is RED
  (natural-duration law).

## Flag-off byte-identity (both cases)

Same requests with `surgical_v2_test` absent: the ops schema enum excludes
`caption_text_overrides` and the prompt carries the historical refusal bullet
byte-identical (fingerprinted in cert_surgical_ops.py) — outputs must match
pre-Step-3 behavior exactly.
