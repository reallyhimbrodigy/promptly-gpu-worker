"""surgical_ops.py — the two cheapest surgical-vocabulary holes, closed
(LANE-SEAM Step 3, 2026-08-09). DARK behind PROMPTLY_SURGICAL_V2.

Hole 1 — CAPTION-TEXT OVERRIDE (the job-2026-07-24 class: "change 'rise' to
'ryze'"). The deterministic vibe-parser (_parse_caption_text_overrides) already
honors QUALIFIED asks ("change the caption 'X' to 'Y'") and the caption builder
already applies a display-layer map (_apply_caption_text_overrides). What was
inexpressible is the BARE ask routed through tweak — no op could carry it. This
module adds the persistent plan list `caption_text_overrides`
([{"find": str, "replace": str}]) to the ops vocabulary, VALIDATES every entry
against the transcript (a find-text that matches no consecutive transcript
words is rejected loudly — the model may never fabricate), and merges valid
entries into the render-transient dict the existing applicator consumes. The
display layer, the audio, and the transcript indices are untouched — this is a
spelling map, not a transcript edit.

Hole 2 — ADD-TRANSITION-AT-SEAM. _apply_plan_ops could always append to
`transitions`; only the tweak prompt refused. With the flag on, the prompt
teaches the add op, and EVERY added transition passes a deterministic
validator: type ∈ VALID_TRANSITION_TYPES, integer seam anchor inside the
transcript, no second transition on the same seam, and the natural-duration
room law (Zac: transitions render at per-type natural duration; they are
SKIPPED, never shortened) — the seam's silence gap must fit the type's frames.
An entry that fails is dropped WITH a user-facing note (a silently-dropped ask
is the exact failure the fulfillment judge counts).

Enforcement ordering (the obedience law): the model proposes, this code
disposes — validation runs AFTER the model, deterministically, regardless of
what the prompt said. Python 3.9-compatible.
"""

import os
import re
from typing import Dict, List, Optional, Tuple

from type_registries import VALID_TRANSITION_TYPES

CAPTION_TEXT_LIST_KEY = "caption_text_overrides"


def enabled(input_data=None):
    """DARK by default. PROMPTLY_SURGICAL_V2=1 arms the two new tweak ops
    globally; input_data.surgical_v2_test is the per-job override for the
    pre-flip cert (burned_text_test pattern — inert for real traffic)."""
    if input_data and input_data.get("surgical_v2_test"):
        return True
    return os.environ.get("PROMPTLY_SURGICAL_V2", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def caption_text_ops_enabled(input_data=None):
    """THE SPLIT (owner ruling 2026-08-18). Caption text swap, ALONE.

    WHY THIS FLAG EXISTS. `PROMPTLY_SURGICAL_V2` reads like a caption flag and
    is not: at the call site it gates THREE changes at once —

      1. caption_text_overrides in the op enum        (MECHANICAL, wanted now)
      2. TRANSITION_ADD_BULLET replacing the refusal  (CREATIVE capability)
      3. OPS_VOCAB_ADDENDUM in the prompt             (teaches op 1)

    Flipping it to ship the text swap would also hand the model the ability to
    ADD TRANSITIONS on re-edit, where it currently refuses. That is a second
    variable inside a one-variable change, and it is how a regression gets
    attributed to the wrong cause.

    Text swap is the single most common small request there is ("you spelled my
    name wrong"), it is purely mechanical, and it is the first user-visible proof
    that the diff path works at all. It gets its own key so that proof carries
    ONE variable.

    PROMPTLY_SURGICAL_V2 stays dark until transition-add gets its own read.
    Either flag arms the caption op; only SURGICAL_V2 arms transition-add.
    """
    if input_data and input_data.get("caption_text_ops_test"):
        return True
    if os.environ.get("PROMPTLY_CAPTION_TEXT_OPS", "").strip().lower() in (
            "1", "true", "yes", "on"):
        return True
    # SURGICAL_V2 is a superset: if the broad flag is on, the caption op is too.
    return enabled(input_data)


def caption_override_anchor(entry):
    """_DIFF_LIST_ANCHORS anchor for caption_text_overrides: the find-text."""
    return entry.get("find") if isinstance(entry, dict) else None


def _norm_word(w):
    return "".join(ch for ch in str(w or "").lower() if ch.isalnum())


def validate_caption_overrides(entries, dg_words):
    """Split model-emitted override entries into (valid, rejected).

    Valid = {"find": str, "replace": str} where find's words match a
    CONSECUTIVE run of transcript words (alnum-normalized, case-insensitive
    — the same matching the display applicator uses, so a validated entry is
    guaranteed to land). rejected = [(entry, reason)] for the loud note —
    never silently dropped, never fabricated onto the captions.
    """
    valid, rejected = [], []
    norm_stream = [_norm_word((w or {}).get("word")) for w in (dg_words or [])]
    for e in (entries or []):
        if not isinstance(e, dict):
            rejected.append((e, "not an object"))
            continue
        find = str(e.get("find") or "").strip()
        replace = str(e.get("replace") or "").strip()
        if not find or not replace:
            rejected.append((e, "find/replace missing"))
            continue
        key = [_norm_word(p) for p in re.split(r"\s+", find) if _norm_word(p)]
        if not key:
            rejected.append((e, "find has no matchable words"))
            continue
        L = len(key)
        hit = any(norm_stream[i:i + L] == key
                  for i in range(0, max(0, len(norm_stream) - L + 1)))
        if not hit:
            rejected.append((e, "'%s' not found in the transcript" % find))
            continue
        valid.append({"find": find, "replace": replace})
    return valid, rejected


def overrides_dict_from_plan(plan):
    """Plan-level [{"find","replace"}] → the render-transient dict shape the
    existing display applicator consumes: {tuple(find words): replace}."""
    out = {}
    for e in ((plan or {}).get(CAPTION_TEXT_LIST_KEY) or []):
        if not isinstance(e, dict):
            continue
        find = str(e.get("find") or "").strip().lower()
        replace = str(e.get("replace") or "").strip()
        key = tuple(w for w in re.split(r"\s+", find) if w)
        if key and replace:
            out[key] = replace
    return out


def _transition_anchor(entry):
    return entry.get("after_word_index") if isinstance(entry, dict) else None


def validate_added_transitions(new_plan, old_plan, dg_words,
                               duration_frames_map, fps=30.0):
    """Deterministically validate every transition PRESENT in new_plan but
    ABSENT from old_plan (by seam anchor). Mutates new_plan in place; returns
    (dropped_notes, kept_count).

    Checks, in order, each with an honest user-facing reason:
      1. type ∈ VALID_TRANSITION_TYPES
      2. after_word_index is an integer inside the transcript
      3. no other transition already occupies that seam
      4. natural-duration room law — the silence gap after the anchor word
         (next word start − word end, source time) must fit the type's
         natural frames. Transitions are SKIPPED, never shortened.
    A no-op when nothing was added — safe to run unconditionally.
    """
    if not isinstance(new_plan, dict):
        return [], 0
    new_list = new_plan.get("transitions")
    if not isinstance(new_list, list) or not new_list:
        return [], 0
    old_anchors = {_transition_anchor(e)
                   for e in ((old_plan or {}).get("transitions") or [])
                   if _transition_anchor(e) is not None}
    words = dg_words or []
    kept, notes, seen_anchors = [], [], set(old_anchors)
    for e in new_list:
        awi = _transition_anchor(e)
        if awi in old_anchors:
            kept.append(e)          # pre-existing — not ours to judge
            continue
        ttype = str((e or {}).get("type") or "")
        if ttype not in VALID_TRANSITION_TYPES:
            notes.append("a '%s' transition isn't in the toolbox" % (ttype or "?"))
            continue
        if not isinstance(awi, int) or awi < 0 or awi >= len(words):
            notes.append("the %s transition's position couldn't be matched "
                         "to a word in the video" % ttype)
            continue
        if awi in seen_anchors:
            notes.append("two transitions can't share the same cut "
                         "(the %s was skipped)" % ttype)
            continue
        need_frames = duration_frames_map.get(ttype)
        if need_frames:
            try:
                gap_s = (float(words[awi + 1].get("start"))
                         - float(words[awi].get("end"))) \
                    if awi + 1 < len(words) else float("inf")
            except Exception:
                gap_s = 0.0
            if gap_s * fps < float(need_frames):
                notes.append(
                    "a %s needs ~%.1fs of breathing room and that cut only "
                    "has %.1fs — it was skipped rather than squeezed"
                    % (ttype, float(need_frames) / fps, max(0.0, gap_s)))
                continue
        seen_anchors.add(awi)
        kept.append(e)
    new_plan["transitions"] = kept
    return notes, len(kept)


# ── Prompt fragments (consumed by generate_plan_diff when the flag is on) ────
# Kept here so the teaching text and the enforcement above version together.

TRANSITION_ADD_BULLET = (
    "  • 'add a transition at the chapter break' / 'add a DipToBlack after the setup'\n"
    "      → append a new transitions entry: {\"after_word_index\": K, \"type\": T} where K is\n"
    "        the LAST word before the cut the user means and T is a valid transition type.\n"
    "        The pipeline validates the seam and the type's natural-duration room — a\n"
    "        transition that can't fit is skipped with an honest note, never squeezed.\n"
)

TRANSITION_REFUSAL_BULLET = (
    "  • 'add a transition at the chapter break' / 'add a DipToBlack after the setup'\n"
    "      → transitions are authored in the dedicated seam pass — not addable here;\n"
    "        acknowledge the ask in notes and leave the plan's transitions untouched.\n"
)

CAPTION_TEXT_BULLET = (
    "  • 'change ''rise'' to ''ryze''' / 'the caption says X, it should say Y' / 'spell it Z'\n"
    "      → a CAPTION SPELLING fix: append a caption_text_overrides entry\n"
    "        {\"find\": \"<exact transcript word(s)>\", \"replace\": \"<display text>\"}.\n"
    "        This changes ONLY what the caption displays — audio, timing, and cuts are\n"
    "        untouched. find MUST be word(s) that appear in the transcript (the pipeline\n"
    "        verifies; a find that matches nothing is skipped with a note). Use this\n"
    "        whenever the user corrects a word's spelling/branding, even without the word\n"
    "        'caption' — a substitution of displayed text is what they mean.\n"
)

OPS_VOCAB_ADDENDUM = (
    "  caption_text_overrides is a list like the others: anchor for remove/replace is the\n"
    "  entry's find-text; add appends {\"find\", \"replace\"}.\n"
)
