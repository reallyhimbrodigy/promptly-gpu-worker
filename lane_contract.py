"""ONE PLACE for the things both lanes were each keeping a copy of.

Ruled by Zac 2026-09-21. Every leg this replaces existed to police AGREEMENT
between two copies of one fact. That is a real class of defect and the legs were
right — but a check that two copies agree is a worse answer than not having two
copies, and it costs a leg, a fixture and a reader's attention forever.

WHAT WAS COSTING WHAT, before this file:

  * `export.state` was a constant in my reader and a literal in the writer. They
    disagreed — the reader tested "OK", which the writer has never emitted — and
    a PERFECT export read ABSENT. The fix was a leg asserting the reader's
    constant appears in the writer. One definition removes the leg AND the bug.
  * A component's name was in the library on one side of a lane boundary and in
    PORTED_PROPS on the other, so a rename landed in two commits with a resolver
    and two legs bridging the gap. One registry removes the gap.
  * Four zoom property tables existed in a JSON file and in the harness, with
    the harness winning silently. A leg asserted they agreed. One place removes
    the leg.

STATES ARE THE REPO'S THREE-STATE RULE, NAMED ONCE. A measurement has three
outcomes and a delivery has four; writing them as bare strings in each reader is
how "OK" happened.
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ── record states ──────────────────────────────────────────────────────────
MEASURED = "MEASURED"     # the thing was read and is what it says
ABSENT = "ABSENT"         # nothing to read — NEVER the same as a measured zero
FAILED = "FAILED"         # the read was attempted and errored
WITHHELD = "WITHHELD"     # a terminal fired; nothing was produced
REFUSED = "REFUSED"       # a floor refused it before it ran

RECORD_STATES = (MEASURED, ABSENT, FAILED, WITHHELD, REFUSED)

# The state an EXPORT carries when the bytes exist. Not "OK" — the writer has
# never emitted that, and a reader comparing against it silently never matches.
EXPORT_DELIVERED = MEASURED

# ── the record schema a reader may key on ──────────────────────────────────
# Named here so a reader does not invent a field. `timeline_sample.end_s` was
# invented once and is not in any record, which made every run read ABSENT.
RECORD_FIELDS = {
    "export.state": "one of RECORD_STATES; MEASURED means the bytes exist",
    "export.why": "the reason, when it is not MEASURED",
    "timeline_sample.items[].itemType": "caption|audio|video|effect|motion-graphic",
    "timeline_sample.items[].timelineRange": "{fromFrame,toFrame} — FRAMES",
    "timeline_sample.items[].sourceRange": "{start,end} — MICROSECONDS, not seconds",
    "shape.calls[].in": "the write call's JSON, whose `adds` length is the tell for dropped items",
    "fault_class_progress.classes": "{class: [count per refused call, in turn order]}",
    "fault_class_progress.stuck": "classes raised and never fallen",
}

# itemType -> the family it counts as, for any per-family tally.
FAMILY_OF_ITEM_TYPE = {
    "caption": "text", "audio": "sfx", "video": "cut",
    "effect": "zoom", "motion-graphic": "card",
}


def _read(name, default=None):
    p = os.path.join(HERE, name)
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return default


def registry(library="library_73.json"):
    """-> {state, components, placements, families, two_home, by_family, why}

    THE ONE COUNT. A component in two families occupies two family placements
    and is still one component, so both numbers are returned and neither is
    called "the total".
    """
    lib = _read(library)
    if not isinstance(lib, dict) or not lib:
        return {"state": FAILED, "why": "no library at %s" % library}
    fams = {k: v for k, v in lib.items()
            if isinstance(v, list) and not k.startswith("_")}
    two_home = set(lib.get("_two_home") or [])
    names = sorted({n for v in fams.values() for n in v})
    placements = sum(len(v) for v in fams.values())
    return {"state": MEASURED, "components": names, "n_components": len(names),
            "placements": placements, "families": len(fams),
            "two_home": sorted(two_home), "by_family": {k: sorted(v) for k, v in fams.items()},
            "why": "%d component(s) in %d famil(ies), %d placement(s), %d two-home"
                   % (len(names), len(fams), placements, len(two_home))}


# ── the live set ───────────────────────────────────────────────────────────
# WHY THIS IS NOT registry(). `registry()` answers "what is in the library
# file" — 79 components across 80 placements, every one this lane ever ported.
# `live_set()` answers "what does PRODUCTION use", which is the question the
# menu is built from, and the two differ by 33. Builder 1 asked for the list
# and I nearly sent him 46 names in a message; a list in a message is a second
# copy of a fact, which is the exact thing this file exists to stop.
#
# NOT EVERY MEMBER HAS A PICTURE, and that distinction is load-bearing for
# anyone building stills. Of the 46, thirteen are SOUNDS and seven are CAPTION
# STYLES — a style is a property of a caption item, not a registered component
# with code of its own. Neither can be registered, placed and photographed the
# way the other 26 can. A stills run that takes all 46 as its worklist reports
# 20 failures that are not failures, and the honest zero is indistinguishable
# from a broken renderer once it is in the tally.
_NO_PICTURE_FAMILIES = {
    "sfx": "a sound has no frame to photograph",
    "caption style": "a style is a property of a caption item, not a registered component",
}


def _body_sha(name):
    """sha256[:16] of the component's authored body, or None if it has none.

    Read from disk EVERY TIME rather than trusted from a record: the whole point
    is to notice when the file has moved out from under a still.
    """
    f = os.path.join(HERE, "port", "bodies", "%s.jsx" % name)
    try:
        with open(f, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except OSError:
        return None


def live_set(library="library_73.json"):
    """-> {state, components, renderable, menu, awaiting_picture, draws, ...}

    THE LIVE SET, derived from production over 30d and cut at 10 users reached.

    THREE SETS, AND THEY ARE NOT INTERCHANGEABLE:
      components       what production uses. SCOPE.
      renderable       the subset with a picture at all — the STILLS WORKLIST.
                       Sounds and caption styles are excluded; they cannot be
                       registered, placed and photographed.
      menu             renderable AND frame-proven — the OFFERABLE set, the one
                       a place-schema may advertise.
    `awaiting_picture` is renderable minus menu: in scope, needs a photograph,
    must not be offered yet. Iterate `renderable` to take pictures; derive a
    schema from `menu`.
    """
    lib = _read(library)
    if not isinstance(lib, dict) or not lib:
        return {"state": FAILED, "why": "no library at %s" % library}
    scope = lib.get("_library")
    if not isinstance(scope, dict):
        return {"state": ABSENT, "why": "%s carries no _library — the scope ruling "
                "has not been published to this file" % library}
    comps = scope.get("components")
    # A CLEAN ZERO IS GUILTY UNTIL PROVEN INNOCENT. An empty components map is a
    # reader or a merge that lost the ruling, never a library with nothing in it,
    # and returning [] here would read to every caller as "production uses none".
    if not isinstance(comps, dict) or not comps:
        return {"state": FAILED, "why": "_library.components is empty or not a map "
                "— a library with no components is a lost ruling, not a measurement"}
    by_family = {}
    for name, row in comps.items():
        for fam in (row.get("families") or ["(unfamilied)"]):
            by_family.setdefault(fam, []).append(name)
    no_picture, renderable = {}, []
    for name, row in comps.items():
        fams = row.get("families") or []
        blocking = [f for f in fams if f in _NO_PICTURE_FAMILIES]
        # A component in TWO families with one picture-bearing home is renderable
        # — StickyNotes is a motion graphic and a text overlay and draws either
        # way. Only a component whose every home is picture-free drops out.
        if fams and len(blocking) == len(fams):
            no_picture[name] = _NO_PICTURE_FAMILIES[blocking[0]]
        else:
            renderable.append(name)
    placements = sum(len(v) for v in by_family.values())

    # ── the picture verdict, and why it is SEPARATE from scope ──────────────
    # SCOPE says production uses it. THE MENU says we can offer it. They are
    # different questions and collapsing them breaks in both directions:
    # dropping an unproven component from scope means it never gets
    # photographed, and offering one means the menu advertises what the kitchen
    # may refuse. Reticle is the worked example — removed from scope on a BLANK
    # its own author later retracted, which cost it its place in the worklist.
    #
    # A STILL IS NOT A VERDICT. inventory_stills carries FILE_ONLY for a row
    # with a sha and no recorded look; that is NOT-YET-EVIDENCE and must not
    # reach the menu. Absence of a row is UNKNOWN, never BLANK.
    stills = (_read(os.path.join("measured", "inventory_stills.json")) or {})
    stills = stills.get("components") or {}
    # BYTES_ONLY IS A REAL STATE AND FOLDING IT INTO UNKNOWN LOSES INFORMATION
    # (Builder 1's correction, 2026-09-21, and he was right). The asymmetry is
    # the argument: a false BLANK is cheap — content supplied only as a
    # propertyOverride never arrives and the frame is legitimately empty — while
    # a false DRAWS is dear, because something must have rendered to change the
    # output at all. So "a comparison cleared and nobody read the frame" is
    # WEAKER evidence, not absent evidence, and it earns its own name.
    #
    # BUT THE NAME IS BYTES_ONLY, NOT PIXELS_ONLY, AND THE DIFFERENCE IS THE
    # POINT. catalogue_stills.json compares `bytes` against
    # `empty_control_bytes` — PNG FILE LENGTH. No pixel is read anywhere in that
    # record. It cannot say WHERE something drew, and it cannot tell a component
    # that drew the RIGHT thing from one that drew the wrong thing at the right
    # size. Calling it a pixel diff is how it got trusted as a verdict.
    catalogue = _read("catalogue_stills.json") or {}

    # ── IS THE INSTRUMENT EVEN READABLE? ───────────────────────────────────
    # `_body_sha` reads port/bodies BESIDE THIS MODULE. In a container where the
    # bodies are deliberately not in the image it returns None for every
    # component — so every recorded sha mismatches, every still reads
    # STALE_BODY, and the menu comes back as an EMPTY LIST while state says
    # MEASURED. Builder 1 hit exactly that: `0 menu components` beside
    # `27 renderable`, state MEASURED, and his harness then announced "the spec
    # and the menu have drifted" — a confident diagnosis of the wrong thing,
    # about a population that was empty. Nothing had drifted.
    #
    # That is this session's most expensive shape, in my own contract: a failed
    # measurement and a clean result rendering identically once you are only
    # reading the number. So the reading gets a STATE, and where the state is
    # ABSENT the menu is None rather than [] — a caller can test None, and
    # cannot mistake it for "nothing qualified".
    _present = [n for n in renderable if _body_sha(n) is not None]
    _bodies_expected = len(renderable)
    if not _bodies_expected:
        draws_state = MEASURED
    elif not _present:
        draws_state = ABSENT
    elif len(_present) < _bodies_expected:
        draws_state = "PARTIAL"
    else:
        draws_state = MEASURED

    draws = {}
    for name in comps:
        declared = (comps[name] or {}).get("draws")
        row = stills.get(name) or {}
        if declared in ("BLANK", "DISPUTED", "UNKNOWN"):
            draws[name] = declared
        elif row.get("body_sha256_16") and _body_sha(name) is None:
            # ABSENT IS NOT CHANGED. A body that cannot be read says nothing
            # about whether the code moved, and calling that STALE_BODY invents
            # a finding — it reads as "somebody edited this" when the truth is
            # "this tree has no bodies in it".
            draws[name] = "BODY_UNREADABLE"
        elif (row.get("body_sha256_16")
              and row["body_sha256_16"] != _body_sha(name)):
            # EVERY VERDICT FROM LOOKING IS ABOUT THE BODY THAT DREW THE FRAME,
            # NOT ONLY THE GOOD ONES. This first guarded DRAWS alone, which was
            # exactly half a rule: I fixed SlideOver and LightLeakOverlay the
            # same afternoon, and both went on reporting DEFECT — a verdict
            # about code that no longer exists, keeping a repaired component
            # condemned on the strength of a frame of the broken one. A stale
            # acquittal and a stale conviction are the same error.
            draws[name] = "STALE_BODY"
        elif row.get("state") == "DRAWS":
            # A PICTURE IS EVIDENCE ABOUT THE CODE THAT DREW IT AND NO OTHER CODE.
            # The body sha is recomputed HERE, at read time, against the file on
            # disk — so re-authoring a component invalidates its still the
            # instant the body changes, with nobody needing to remember. Four
            # stills went stale this way in one afternoon and every one of them
            # still looked perfectly good, which is why this cannot be a
            # convention.
            # currency is settled above, for every state; this branch is only
            # reached when the sha still matches.
            draws[name] = "DRAWS"
        elif row.get("state") in ("DEFECT", "PASSTHROUGH_SUSPECT", "UNDECIDABLE", "STALE_BODY"):
            draws[name] = row["state"]
        elif (catalogue.get(name) or {}).get("state") == "MEASURED":
            draws[name] = "BYTES_ONLY"
        else:
            draws[name] = "UNKNOWN"
    # THE MENU TAKES ONLY "DRAWS". BYTES_ONLY does not reach it — a file that
    # got bigger is not a picture somebody looked at, and the whole reason the
    # menu exists is that the two were being treated as one.
    menu = sorted(n for n in renderable if draws.get(n) == "DRAWS")
    awaiting = sorted(n for n in renderable if draws.get(n) != "DRAWS")

    # ── WHAT A PHOTOGRAPHING HARNESS MUST READ, AND WHY IT IS NOT `menu` ────
    # THE MENU GATES THE PHOTOGRAPHER ON HAVING PHOTOGRAPHED (Builder 1,
    # 2026-09-21, found by building against this). `menu` is renderable AND
    # frame-proven, and a frame-proof is exactly what an inventory build
    # PRODUCES. So a component whose body is re-authored leaves the menu on the
    # currency rule — correctly — and if the photographer reads `menu` it is
    # then never allowed to shoot it. It can never come back.
    #
    # It happened inside an hour. My EmojiCard poster fix moved the body sha,
    # the still went STALE_BODY, the menu fell 12 -> 11, and EmojiCard was
    # excluded from the one run that would have re-proven it.
    #
    # `to_photograph` is the answer and it is `renderable`, deliberately not
    # `awaiting_picture`: re-shooting a component that is already proven costs
    # one clip, and refusing to shoot one that is not proven is a deadlock. The
    # asymmetry decides it.
    to_photograph = sorted(renderable)

    if draws_state == ABSENT:
        # None, never []. A caller can test None; [] reads as "nothing
        # qualified", which is the lie this whole block exists to stop.
        draws, menu, awaiting = None, None, None

    return {"state": MEASURED,
            "components": sorted(comps), "n": len(comps),
            "renderable": sorted(renderable), "n_renderable": len(renderable),
            "no_picture": no_picture, "n_no_picture": len(no_picture),
            "draws": draws,
            "draws_state": draws_state,
            "bodies_readable": "%d/%d" % (len(_present), _bodies_expected),
            "menu": menu, "n_menu": (None if menu is None else len(menu)),
            "awaiting_picture": awaiting,
            "n_awaiting_picture": (None if awaiting is None else len(awaiting)),
            "to_photograph": to_photograph, "n_to_photograph": len(to_photograph),
            "by_family": {k: sorted(v) for k, v in sorted(by_family.items())},
            "cut_users_30d": scope.get("_cut_users_30d"),
            "source": scope.get("_source"),
            "why": ("%d component(s) in %d famil(ies), %d placement(s); %d renderable; "
                    "DRAWS READING IS %s (%d/%d bodies readable) so menu is None — "
                    "an unreadable instrument does not report an empty menu"
                    % (len(comps), len(by_family), placements, len(renderable),
                       draws_state, len(_present), _bodies_expected))
                   if draws_state == ABSENT else
                   ("%d component(s) in %d famil(ies), %d placement(s); %d renderable "
                    "(%d frame-proven ON THE MENU, %d awaiting a picture), "
                    "%d with no picture (%d sound, %d caption style); "
                    "draws reading %s, %d/%d bodies readable"
                    % (len(comps), len(by_family), placements, len(renderable),
                       len(menu), len(awaiting), len(no_picture),
                       len(by_family.get("sfx") or []),
                       len(by_family.get("caption style") or []),
                       draws_state, len(_present), _bodies_expected))}
