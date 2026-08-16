"""guidance_registry.py — additive guidance profiles for the unified editorial
core (LANE-SEAM Step 2, 2026-08-09).

THE RULING THIS ENCODES (Zac, Jul-31): one editorial core, a UNIVERSAL toolbox,
and route-shaped GUIDANCE — never a fork that strips tools. A profile shapes
HOW the model uses the toolbox; it can never remove a tool from availability.
That law is STRUCTURAL here: GuidanceProfile has no field that could express a
tool allowlist/denylist, so a profile that removes capability is unrepresentable
(the same trick as ZOOM_ARC_HOMES' import-time tiling assert — make the illegal
state unwritable, don't police it).

ROUTER CONSERVATISM (standing ruling): when selection is uncertain, MORE
guidance loads, never less — ambiguity may cost tokens, never capability.
Unknown route → the full-core default profile, never an error, never a
stripped prompt.

CACHE ECONOMICS (measured, E23: cached prefix ≈42K tok; naive prompt
relocation once cost 2.1x): profiles are APPENDED AFTER the base system
instruction, in REGISTRY order (not caller order), so the base block stays a
stable cache prefix and each (base, stack) pair is itself a stable, cacheable
text per route.

CONTRADICTION LAW (build-time RED, not runtime surprise): every profile
declares its editorial spine as `axis:value` markers. Two profiles that pin
the same axis to different values cannot stack — validate_stack raises
GuidanceContradiction at composition time, before any model call.

Python 3.9-compatible.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

__all__ = [
    "GuidanceProfile", "GuidanceContradiction", "PROFILES",
    "profiles_for_route", "validate_stack", "compose_suffix",
    "DEFAULT_PROFILE",
]


class GuidanceContradiction(RuntimeError):
    """Two stacked profiles pin the same editorial axis to different values.
    Raised at composition time — a contradiction between loaded profiles is a
    build-time RED, never a prompt the model has to arbitrate."""


@dataclass(frozen=True)
class GuidanceProfile:
    """One additive guidance block. `guidance` is appended after the BASE
    system instruction verbatim. `axes` pins editorial spine axes
    (axis → value); stacking two profiles that disagree on an axis raises.
    There is deliberately NO tools field of any kind — see module docstring.
    """
    name: str
    kind: str                      # "route" | "intent"
    guidance: str                  # "" is legal (the base IS the doctrine)
    axes: Dict[str, str] = field(default_factory=dict)


# ── The registry ─────────────────────────────────────────────────────────────
# Route-shaped profiles carry the doctrine of the forked planners they retire,
# re-voiced as ADDITIVE guidance over the universal base (which already holds
# the full toolbox definitions, the FITS/FIGHTS lines, and the hard laws).
# The hype/moodreel text is adapted from the authored standalone prompts
# (hype_editor.build_hype_prompt / moodreel_editor.build_moodreel_prompt) so
# the unified core can IMITATE the fork before it improves on it.

PROFILES: Dict[str, GuidanceProfile] = {}


def _register(p):
    if p.name in PROFILES:
        raise RuntimeError("duplicate guidance profile %r" % p.name)
    PROFILES[p.name] = p
    return p


DEFAULT_PROFILE = "premium_full"

_register(GuidanceProfile(
    name="premium_full",
    kind="route",
    # EMPTY on purpose: the base system instruction IS the full editorial
    # doctrine. This is what makes unified-core-ON on the main route
    # byte-identical by construction (certified) — the seam exists with
    # zero text change until a lean route proves its profile through the
    # PLAN_ONLY differ.
    guidance="",
    axes={"spine": "transcript-arc"},
))

_register(GuidanceProfile(
    name="hype_pacing",
    kind="route",
    guidance="""=== GUIDANCE PROFILE: HYPE / MUSIC PACING ===
RE-ANCHORING FOR THIS JOB: this clip has NO usable speech — no transcript, no
word indices, no dialogue arc. The music already inside the clip IS the
structure. Everything the toolbox section above says about WHAT each tool is
for still holds; this block re-anchors WHERE things land.

THE SPINE IS THE BEAT GRID, not a word arc. Anchor every decision to the beat
times (source seconds) provided in the job signals. Cuts land ON beats.
Emphasis — a punch-zoom, a hard transition — lands on the STRONG beats:
downbeats, the drop, a section change (scene cuts are section hints).

HOW THE TOOLBOX LEANS HERE:
- CUTS + SPEED: cut the timeline to the beat. Tighten dead sections; let a
  great shot breathe for a bar. A speed ramp INTO a drop reads as momentum.
  Do not strobe — a cut on every single beat for 30s is nausea, not hype.
- PUNCH-ZOOMS: a snap/step/staged push LANDS its scale peak ON a strong beat.
  2-4 across a 20-30s clip, on the beats that actually hit — overuse deflates.
- TRANSITIONS: the HARD CUT is this format's default joint — restraint IS the
  style. A transition appears ONLY at a moment the footage or music MOTIVATES
  (the drop, a true section change, a subject/location change). ZERO is a
  strong, common answer; one is typical; two is the ceiling.
- MOTION GRAPHICS: sparse kinetic text for a title card or a callout the
  footage can't say. Never caption what's already on screen.

HARD RULES OF THIS PROFILE:
- Anchor in SECONDS on the source; cuts fall on (or within ~50ms of) a beat.
- NEVER add music, a soundtrack, or reference adding one. The audio is the
  user's own.
- The edit stays within the source duration. Do not invent time.""",
    axes={"spine": "beat-grid", "pace": "driving", "zoom-register": "punch"},
))

_register(GuidanceProfile(
    name="moodreel_aesthetic",
    kind="route",
    guidance="""=== GUIDANCE PROFILE: CINEMATIC MOOD REEL ===
RE-ANCHORING FOR THIS JOB: this is a posed/aesthetic NON-speech clip with no
confident music driving it. No transcript, no beat grid to obey — the footage
is the music. Everything the toolbox section above says about WHAT each tool
is for still holds; this block re-anchors HOW to compose.

THE SPINE IS VISUAL RHYTHM: the motion curve, composition changes, and light.
Where hype cuts TO the beat, you cut WITH the motion.

THE THREE LAWS OF THE MOOD REEL:
1. A LINGERING SHOT EARNS ITS LENGTH. Hold 3-6s ONLY while something in the
   frame is still developing — a turn completing, light crawling, a pose
   settling. The moment the frame stops giving, cut.
2. CUTS LAND WHERE MOTION RESOLVES. Cut in the valley just AFTER a motion
   peak — the gesture completes, breathes, then the cut. Never on the rise
   (that is hype grammar), never mid-gesture.
3. THE PACE IS THE GRADE. Long-held frames and slow drift read moody and
   expensive; fast even cuts read like a slideshow.

HOW THE TOOLBOX LEANS HERE:
- CUTS: few and deliberate — 4-8 shots across 15-25s; most 2.5-5s, ONE allowed
  to run long while it keeps developing. Metronomic spacing is a slideshow.
- ZOOMS: slow push-ins and drift ONLY — the camera leans in to look closer, it
  never punches. 1-3 per reel, on the most composed frames; never on a shot
  already moving.
- SPEED: 1.0 is the pulse. A shot MAY float at 0.85-1.0 when its motion arc is
  smooth and worth savoring. NEVER above 1.0 — nothing in a mood reel hurries.
- TRANSITIONS: ALMOST NEVER. At most ONE dissolve at a TRUE mood shift (day to
  dusk, motion to stillness). ZERO is the expected answer.
- MOTION GRAPHICS: default NONE. At most a single restrained stamp placed low,
  never on the subject, never explaining what the image already says.
- OUTRO: end with intention — close on the most settled frame and let it fall
  away, or let the final hard frame BE the ending. Running out of footage is a
  failure.

HARD RULES OF THIS PROFILE:
- Anchor in SECONDS; use the motion RESOLVE times as cut landing zones.
- NEVER add music or reference adding it; the clip's own audio — or its
  silence — is the bed.
- The edit stays within the source duration. Do not invent time.""",
    axes={"spine": "motion-resolve", "pace": "lingering", "zoom-register": "drift"},
))

_register(GuidanceProfile(
    name="minimal_restraint",
    kind="route",
    guidance="""=== GUIDANCE PROFILE: MINIMAL / CLEAN DELIVERY ===
RE-ANCHORING FOR THIS JOB: this clip reached the editor through a route where
the safest great edit is a RESTRAINED one — the content carries itself, or the
signals an aggressive edit needs (a confident transcript, a beat grid, a
motion arc) are absent or unreliable. Everything the toolbox section above
says still holds — every tool remains available — but the bar each tool must
clear here is HIGHER.

THE DOCTRINE OF RESTRAINT:
- The clip's own rhythm leads. Clean cuts at natural boundaries; no cut exists
  to prove the editor was here.
- Decoration must EARN the frame: a zoom, graphic, or sound lands only where
  the content unambiguously calls for it. When in doubt, the clean frame wins.
- Deliver the content intact — the user's material, breathing, at 1.0x.

HARD RULES OF THIS PROFILE:
- The edit stays within the source duration. Do not invent time.
- NEVER add music or reference adding it.""",
    axes={"pace": "source-led", "decoration": "earn-the-frame"},
))

_register(GuidanceProfile(
    name="speech_preservation",
    kind="intent",
    guidance="""=== GUIDANCE PROFILE: SPEECH PRESERVATION ===
This clip carries HUMAN SPEECH that could not be fully transcribed. The
standing law (the Urdu-class lesson): destroyed content is worse than an
honest failure. Every second of speech is load-bearing until proven
otherwise.
- NEVER cut inside speech you cannot read. Untranscribed speech is preserved
  VERBATIM — cuts may live only in confirmed non-speech spans.
- Do not caption speech you cannot read, and never partially: patchy captions
  are a defect, not a degrade.
- Visual treatments that leave the audio intact (a drift zoom, a restrained
  graphic in a non-speech span) remain fully available.""",
    axes={"cuts": "preserve-speech"},
))

_register(GuidanceProfile(
    name="brand_identity",
    kind="intent",
    # SHORT ON PURPOSE. These two components were built, mounted, called and
    # counted, and were still unrequestable because nothing ever told the model
    # they existed [Rule 2, the built-not-wired class]. The cure is the smallest
    # block that closes that — WHAT the two are, WHEN each earns its place, and
    # the one hard rule. Everything else about them (colour, type size, safe
    # zones, hold duration, placement) is derived from the palette in
    # brand_components.py, so there is nothing else for the model to author and
    # nothing else worth spending prompt on.
    guidance="""=== GUIDANCE PROFILE: SPEAKER + BRAND IDENTITY ===
Two identity components can ride this edit. You author only their WORDS, in
`brand_copy` — colour, size, safe zones and hold all come from the palette
already derived from THIS footage, so there is nothing to style and no
placement to pick.
- NAME-PLATE — a lower third naming the speaker, held ~3s, ONCE, early.
  **FITS:** a talking head whose CREDIBILITY carries the claim — an expert, a
  founder, a title that changes how the line lands. **FIGHTS:** a casual or
  personal clip, a face the audience already knows, a name never stated.
- END-CARD — the held closing frame, so the edit ENDS rather than stops.
  **FITS:** a close that hands the viewer an owner or an ask — a business, a
  handle, a site. **FIGHTS:** a clip that lands on its own punchline, with
  nothing to hand over.

OBSERVED ONLY, NEVER INVENTED — the one hard rule. Fill a `brand_copy` field
only from what this video itself states: the speaker says their name, role or
brand, or it is legible on screen (an existing lower third, a slide, a
wordmark, a handle). A name guessed from a face, a voice or a topic is a
fabrication printed on a real person's video. Omit the field instead — omitted
is CORRECT, renders nothing, and has no placeholder.""",
    # A NEW axis, deliberately: `brand-copy` is pinned by no other profile, so
    # this block stacks with every route (premium, hype, moodreel, minimal,
    # speech-preservation) without ever raising GuidanceContradiction. Pinning
    # an existing axis — pace, spine, decoration — would make identity copy
    # mutually exclusive with an editorial register it has nothing to do with.
    axes={"brand-copy": "observed-only"},
))


# ── Deterministic router ─────────────────────────────────────────────────────
# route name (the zero-reject router's vocabulary, H35) → profile stack.
# Unknown/uncertain → DEFAULT_PROFILE (full core): conservatism means the FULL
# doctrine loads, never a stripped one, and never an exception.
_ROUTE_STACKS: Dict[str, Tuple[str, ...]] = {
    "premium": ("premium_full",),
    "full": ("premium_full",),
    "__premium__": ("premium_full",),
    "hype": ("hype_pacing",),
    "moodreel": ("moodreel_aesthetic",),
    "minimal": ("minimal_restraint",),
    "minimal_speech_uncut": ("minimal_restraint", "speech_preservation"),
    # The full route PLUS the identity block. A SEPARATE KEY, not an edit to
    # "full": cert_unified_core asserts select_stack("full") composes to the
    # base object UNCHANGED, and that byte-identity is the entire safety
    # argument for flipping the seam on the main route. Arming identity copy is
    # a real prompt change and goes through the PLAN_ONLY differ like every
    # other one — it does not get to ride in on a route key that is certified
    # to change nothing.
    "full_brand": ("premium_full", "brand_identity"),
}


def profiles_for_route(route_name):
    """Deterministic route→stack selection. Never raises, never strips:
    an unrecognized route gets the full-core default."""
    key = (route_name or "").strip().lower()
    return list(_ROUTE_STACKS.get(key, (DEFAULT_PROFILE,)))


def validate_stack(names):
    """Resolve profile names → GuidanceProfile list, enforcing the
    contradiction law. Raises KeyError on an unknown name (a typo'd profile is
    a build error, not a silent no-op) and GuidanceContradiction when two
    profiles pin the same axis differently."""
    profiles = []
    pinned = {}   # axis -> (value, profile_name)
    for name in names:
        if name not in PROFILES:
            raise KeyError(
                "unknown guidance profile %r (registry: %s)"
                % (name, sorted(PROFILES)))
        p = PROFILES[name]
        for axis, value in p.axes.items():
            if axis in pinned and pinned[axis][0] != value:
                raise GuidanceContradiction(
                    "profiles %r and %r pin axis %r to %r vs %r — this stack "
                    "cannot load" % (pinned[axis][1], p.name, axis,
                                     pinned[axis][0], value))
            pinned[axis] = (value, p.name)
        profiles.append(p)
    return profiles


def compose_suffix(names):
    """The additive text appended AFTER the base system instruction.
    Registry-ordered (not caller-ordered) so the same stack always composes
    to the same bytes — per-route cache stability. Empty stacks and the
    empty premium_full profile compose to "" (no text change at all)."""
    profiles = validate_stack(names)
    order = {n: i for i, n in enumerate(PROFILES)}
    blocks = [p.guidance for p in
              sorted(profiles, key=lambda p: order[p.name]) if p.guidance]
    if not blocks:
        return ""
    return "\n\n" + "\n\n".join(blocks)
