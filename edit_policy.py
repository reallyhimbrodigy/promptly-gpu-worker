"""Phase 1 — the EditPolicy spine (with the two-tier feature taxonomy).

STANDALONE. Not imported by the live render path yet (handler.py does NOT import
this in Phase 1). Consumers (recipe prompt, always-on gates, enforcement pass)
wire in Phase 2 after the shape + extraction prompt are reviewed.

ARCHITECTURE: the cheap LLM emits INTENT (mode + which expressive features were
named in "only X", + which features were explicitly excluded). The resolution
then DETERMINISTICALLY DERIVES the on/off features using the explicit tier
constants below — so the tier rule ("allow_list zeroes only unnamed EXPRESSIVE
features; BASELINE stays on unless explicitly excluded") is a code guarantee, not
a thing we hope the model gets right.

SAFETY POSTURE (load-bearing): bias to "on". A feature is suppressed ONLY on an
explicit, confident instruction. Any ambiguity, any extraction failure, any empty
vibe -> full default behavior. Over-keeping is recoverable; over-removing is not.
"""
from __future__ import annotations

import os
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# ── The two-tier taxonomy (explicit grouping, per the approved decision) ──────
# EXPRESSIVE = the visible, attention-drawing layer. Under "only X" (allow_list)
# every expressive feature NOT named resolves to off.
EXPRESSIVE_FEATURES = (
    "captions", "zoom", "broll", "motion_graphics", "sfx", "transitions", "text_overlays",
)
# BASELINE = invisible polish that "edited" implies (the absence of which — raw,
# shaky, dead-air footage — is almost never wanted). Stays ON through allow_list;
# flips off ONLY on an explicit exclusion ("keep my pacing", "no stabilization",
# "leave the audio raw"), which routes through the normal deny path.
BASELINE_FEATURES = ("filler_trim", "stabilize", "audio_denoise")

FEATURE_NAMES = EXPRESSIVE_FEATURES + BASELINE_FEATURES  # all 10

# Each feature -> the recipe array / stage it will gate in Phase 2 (lookup, not
# translation): captions->caption_style/keywords/positions, zoom->emphasis_moments,
# broll->broll_clips, motion_graphics->motion_graphics, sfx->sound_effects,
# transitions->transitions(+scene-floor gate), text_overlays->text_overlays,
# filler_trim->compute_mechanical_cuts (always-on), stabilize->vidstab (always-on),
# audio_denoise->audio_denoise bool.

OnOff = Literal["on", "off"]


class EditPolicyFeatures(BaseModel):
    # Every feature defaults "on" — bias-to-on baked into the type.
    captions: OnOff = "on"
    zoom: OnOff = "on"
    broll: OnOff = "on"
    motion_graphics: OnOff = "on"
    sfx: OnOff = "on"
    transitions: OnOff = "on"
    text_overlays: OnOff = "on"
    filler_trim: OnOff = "on"
    stabilize: OnOff = "on"
    audio_denoise: OnOff = "on"


class EditPolicy(BaseModel):
    language_hint: Optional[str] = None
    mode: Literal["default", "allow_list", "deny_list"] = "default"
    features: EditPolicyFeatures = Field(default_factory=EditPolicyFeatures)
    intensity: Literal["minimal", "default", "heavy"] = "default"
    notes: str = ""
    reasoning: str = ""   # the model's short explanation of the parse — logged, not consumed

    def off_features(self) -> list:
        return [f for f in FEATURE_NAMES if getattr(self.features, f) == "off"]


DEFAULT_POLICY = EditPolicy()


# ── Extraction prompt (THE artifact to review) ───────────────────────────────
EXTRACTION_SYSTEM_PROMPT = """\
You convert a short-form video editor's instruction (the "vibe") into editing INTENT. \
The vibe may be in ANY language (English, Portuguese, Spanish, French, German, Japanese, …). \
Emit ONLY via the emit_intent tool. You do NOT decide the final on/off features — you report \
what the user NAMED and what they EXPLICITLY EXCLUDED; deterministic code derives the rest.

There are two tiers of features:
  • EXPRESSIVE (the visible layer): captions, zoom, broll, motion_graphics, sfx, transitions, \
text_overlays.
  • BASELINE (invisible polish that "edited" implies): filler_trim (trimming silences/filler/dead-air), \
stabilize (shaky-footage stabilization), audio_denoise (background-noise removal).

mode + what to emit:
  • "allow_list" — the vibe scopes to a set: "only X" / "just X" / "nothing but X". Put the EXPRESSIVE \
features the user wants in `allowed`. Code turns every OTHER expressive feature off. IMPORTANT: "only X" \
does NOT strip the baseline — filler_trim/stabilize/audio_denoise stay on (the user means "no zooms/b-roll/\
SFX/graphics, just captions", not "leave in every dead-air pause and the camera shake"). Only put a \
baseline feature in `excluded` if the user EXPLICITLY says so. "only X" / "just X" / "nothing but X" / "nothing else" are ALL allow_list scoping of the EXPRESSIVE layer: set mode=allow_list and list the named EXPRESSIVE features in `allowed`. `allowed` is EMPTY when the user named only a baseline edit ("just remove the silences", "nothing but the trim") — and then EVERY expressive feature goes off while the baseline stays on. This scoping NEVER strips the baseline; baseline comes off only when the vibe explicitly names it (raw, unedited, keep every pause, no stabilization, leave the audio raw).
  • "deny_list" — the vibe says "no X" / "without X" / "don't add X". Put the excluded features in \
`excluded`. Everything else stays on.
  • "default" — the vibe gives no include/exclude scoping (atmospheric/aesthetic only, e.g. "make it \
punchy", "cinematic", or it's silent). `allowed` and `excluded` both empty.

`excluded` is the deny path and applies in ANY mode. An explicit baseline exclusion goes here: \
"keep my pacing" / "don't cut anything" / "keep every pause" -> filler_trim. "no stabilization" -> \
stabilize. "leave the audio raw" -> audio_denoise. "leave it totally raw / unedited" -> all three baseline.

SAFETY — DEFAULT TO KEEPING. Only name a feature in `excluded` (or scope with `allowed`) when the vibe \
EXPLICITLY and confidently says so. If the vibe doesn't clearly address a feature, do NOT exclude it and \
do NOT switch to allow_list — leave it to default-on. When unsure, keep it. Over-keeping is safe; \
over-removing destroys the user's work.

intensity: "minimal" for subtle / clean / invisible / professional / understated; "heavy" for punchy / \
maximal / chaotic / high-energy; otherwise "default". (A vibe can carry mood AND an instruction — e.g. \
"calm morning feel, no captions" is mode=deny_list, excluded=[captions], intensity=minimal.)

language_hint: ISO-639-1 code of the vibe's language if confident, else null. Phrasing maps across ALL \
languages, not just the examples — "keine Untertitel" / "字幕なし" / "sin subtítulos" all mean captions \
excluded; reason from meaning, not keyword matching.

reasoning: one or two sentences explaining your parse — which features you scoped/excluded and why. \
notes: any aesthetic/creative direction the main recipe model should still honor (in the vibe's language). \
Empty string if none."""


def _tool_schema() -> dict:
    feat_enum = list(FEATURE_NAMES)
    return {
        "type": "object",
        "properties": {
            "reasoning": {"type": "string", "description": "1-2 sentences explaining the parse"},
            "mode": {"type": "string", "enum": ["default", "allow_list", "deny_list"]},
            "allowed": {"type": "array", "items": {"type": "string", "enum": feat_enum},
                        "description": "expressive features the user explicitly wants (only X). empty unless allow_list"},
            "excluded": {"type": "array", "items": {"type": "string", "enum": feat_enum},
                         "description": "features the user explicitly excluded (deny path, any tier)"},
            "intensity": {"type": "string", "enum": ["minimal", "default", "heavy"]},
            "language_hint": {"type": ["string", "null"]},
            "notes": {"type": "string"},
        },
        "required": ["reasoning", "mode", "allowed", "excluded", "intensity", "language_hint", "notes"],
    }


def _derive_features(mode: str, allowed: list, excluded: list) -> dict:
    """Deterministic tier derivation. allow_list zeroes only UNNAMED EXPRESSIVE
    features; BASELINE stays on; explicit `excluded` (the deny path) turns off any
    named feature in any mode."""
    feats = {f: "on" for f in FEATURE_NAMES}              # bias-to-on
    if mode == "allow_list":
        for f in EXPRESSIVE_FEATURES:
            feats[f] = "on" if f in (allowed or []) else "off"   # baseline untouched -> stays on
    for f in (excluded or []):                            # deny path, any mode/tier
        if f in feats:
            feats[f] = "off"
    return feats


EXTRACTION_MODEL = "claude-haiku-4-5-20251001"   # confirmed on the key; bare alias not exposed


def _extract_intent_llm(vibe: str, api_key: str, model: str, timeout_s: float) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key, timeout=timeout_s)
    resp = client.messages.create(
        model=model, max_tokens=1024, system=EXTRACTION_SYSTEM_PROMPT,
        tools=[{"name": "emit_intent",
                "description": "Emit the editing intent parsed from the user's vibe.",
                "input_schema": _tool_schema()}],
        tool_choice={"type": "tool", "name": "emit_intent"},
        messages=[{"role": "user", "content": f"VIBE:\n{vibe}"}],
    )
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "emit_intent":
            return block.input
    raise ValueError("no emit_intent tool_use block in response")


def resolve_edit_policy(
    vibe: Optional[str], *, api_key: Optional[str] = None,
    model: str = EXTRACTION_MODEL, timeout_s: float = 20.0,
) -> EditPolicy:
    """Resolve the vibe into an EditPolicy. NEVER raises — every failure path
    returns DEFAULT_POLICY. Skips the LLM call entirely on an empty/absent vibe."""
    if not vibe or not str(vibe).strip():
        return DEFAULT_POLICY
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("[edit-policy] no ANTHROPIC_API_KEY -> default (extraction skipped)", flush=True)
        return DEFAULT_POLICY
    try:
        intent = _extract_intent_llm(str(vibe), key, model, timeout_s)
        mode = intent.get("mode", "default")
        feats = _derive_features(mode, intent.get("allowed"), intent.get("excluded"))
        policy = EditPolicy(
            language_hint=intent.get("language_hint"),
            mode=mode if mode in ("default", "allow_list", "deny_list") else "default",
            features=EditPolicyFeatures(**feats),
            intensity=intent.get("intensity") if intent.get("intensity") in ("minimal", "default", "heavy") else "default",
            notes=str(intent.get("notes") or ""),
            reasoning=str(intent.get("reasoning") or ""),
        )
        print(f"[edit-policy] mode={policy.mode} off={policy.off_features()} "
              f"intensity={policy.intensity} lang={policy.language_hint}", flush=True)
        return policy
    except Exception as e:
        print(f"[edit-policy] extraction failed ({type(e).__name__}: {str(e)[:160]}) -> default", flush=True)
        return DEFAULT_POLICY
