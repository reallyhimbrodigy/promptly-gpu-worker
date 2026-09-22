#!/usr/bin/env python3
"""lane_contract.live_set() is the ONE accessor for the live set.

WHY IT NEEDS A CHECK AT ALL. Builder 1 asked for "the 47 by name" and the honest
answer was a list in a message — a second copy of a fact, which is what
lane_contract exists to stop. The accessor replaces the message; these legs are
what make the accessor trustworthy enough to replace it.

THE LEG THAT MATTERS MOST IS L6. An empty components map must come back FAILED,
never MEASURED with an empty list: every caller reads `components` and a clean []
says "production uses no components", which is a lost ruling wearing a
measurement's clothes. That is this repo's oldest defect class and it would land
here in its purest form.
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lane_contract as lc                                     # noqa: E402

FAILS = []


def leg(name, ok, got):
    print("  %-34s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    r = lc.live_set()
    print("live_set(): %s" % r.get("why", r.get("state")))

    leg("L1 state_measured", r["state"] == lc.MEASURED, r["state"])
    # The counts are pinned because a SILENT DRIFT is the failure here — a merge
    # that drops rows leaves a smaller, perfectly well-formed library.
    leg("L2 n_is_47", r.get("n") == 47, "n=%s" % r.get("n"))
    leg("L3 renderable_is_27", r.get("n_renderable") == 27, "n=%s" % r.get("n_renderable"))

    fams = r.get("by_family") or {}
    rend = set(r.get("renderable") or [])
    sfx, styles = set(fams.get("sfx") or []), set(fams.get("caption style") or [])
    leg("L4 no_sfx_in_renderable", bool(sfx) and not (sfx & rend),
        "%d sfx, %d leaked" % (len(sfx), len(sfx & rend)))
    leg("L5 no_style_in_renderable", bool(styles) and not (styles & rend),
        "%d styles, %d leaked" % (len(styles), len(styles & rend)))

    # L5b THE TWO-HOME LEG, ON A FIXTURE — because the real population cannot
    # exercise it. StickyNotes is a motion graphic AND a text overlay, and
    # NEITHER home is picture-free, so it stays renderable under any spelling of
    # the rule. Asserting it here would be a leg that cannot fail: the property
    # is "one picture-bearing home is enough", and today no component has one
    # home of each kind. So the fixture supplies the case the library lacks —
    # a component that is both an sfx and a motion graphic must stay renderable,
    # and one that is only an sfx must not.
    fx = {"_library": {"components": {
        "BothHomes": {"families": ["sfx", "motion graphic"]},
        "SoundOnly": {"families": ["sfx"]},
    }}}
    fxp = os.path.join(lc.HERE, "_smoke_live_set_twohome.json")
    open(fxp, "w").write(json.dumps(fx))
    try:
        t = lc.live_set("_smoke_live_set_twohome.json")
        trend = set(t.get("renderable") or [])
        leg("L5b two_home_kept",
            trend == {"BothHomes"},
            "renderable=%s (want {'BothHomes'})" % sorted(trend))
    finally:
        os.remove(fxp)
    leg("L5c stickynotes_present", "StickyNotes" in rend,
        "StickyNotes in renderable=%s" % ("StickyNotes" in rend))

    # L6 the floor. An empty map is a lost ruling, not a measurement.
    empty = {"_library": {"components": {}}}
    tmp = os.path.join(lc.HERE, "_smoke_live_set_empty.json")
    open(tmp, "w").write(json.dumps(empty))
    try:
        e = lc.live_set("_smoke_live_set_empty.json")
        leg("L6 empty_is_FAILED", e["state"] == lc.FAILED and "components" not in e,
            "state=%s components_key=%s" % (e["state"], "components" in e))
    finally:
        os.remove(tmp)

    # L7 a library with no ruling published is ABSENT, not FAILED and not empty.
    noscope = os.path.join(lc.HERE, "_smoke_live_set_noscope.json")
    open(noscope, "w").write(json.dumps({"zoom": ["StepZoom"]}))
    try:
        a = lc.live_set("_smoke_live_set_noscope.json")
        leg("L7 no_ruling_is_ABSENT", a["state"] == lc.ABSENT, "state=%s" % a["state"])
    finally:
        os.remove(noscope)

    # L8 the partition: nothing is lost between the two subsets, and nothing is
    # counted twice. A component that fell out of both would be invisible.
    nop = set((r.get("no_picture") or {}).keys())
    leg("L8 partition_exact",
        (rend | nop) == set(r.get("components") or []) and not (rend & nop),
        "%d + %d = %d of %d" % (len(rend), len(nop), len(rend | nop), r.get("n") or -1))

    # ── the menu is not the scope, and this is where that is enforced ──────
    menu, await_ = set(r.get("menu") or []), set(r.get("awaiting_picture") or [])
    dr = r.get("draws") or {}
    stills = json.load(open(os.path.join(lc.HERE, "measured", "inventory_stills.json")))

    # L9 THE LOAD-BEARING LEG. Nothing reaches the menu without a picture. A
    # place-schema derived from the menu then cannot advertise what the kitchen
    # refuses — which is the defect one level up from the one it already fixed.
    unproven_on_menu = sorted(n for n in menu if dr.get(n) != "DRAWS")
    leg("L9 menu_is_frame_proven_only", not unproven_on_menu,
        "%d on menu, %d unproven %s" % (len(menu), len(unproven_on_menu), unproven_on_menu or ""))

    # L10 FILE_ONLY is NOT-YET-EVIDENCE. A sha is a file, not a verdict, and
    # this is the leg that stops one being promoted into the other.
    # L10 IS DELETED AND THE GAP IS STATED INSTEAD OF WIDENED.
    # The property — a FILE_ONLY row must never be read as DRAWS — is real and
    # still enforced in the resolution. But it can no longer be TESTED against
    # this data: after today's looking, every remaining FILE_ONLY row belongs to
    # an out-of-scope component, and live_set only resolves `draws` for the 47
    # in scope. So the population is empty, and BOTH spellings of the leg passed
    # vacuously — first "none are on the menu" (an empty intersection), then
    # "none are read as DRAWS" (an empty map lookup). Two rewrites, both green,
    # both asserting nothing; the red proof is what showed it, by mutating the
    # rule away and watching nothing go red.
    # A leg over an empty population is not a weaker check, it is not a check.
    # L9 covers what reaches the menu and L15 covers currency; this one waits
    # for an in-scope component to be FILE_ONLY again.

    # L11 the partition again, one level down: every renderable component is
    # either offerable or waiting. One that fell out of both would be invisible
    # — never offered and never photographed.
    leg("L11 menu_partitions_renderable",
        (menu | await_) == set(r.get("renderable") or []) and not (menu & await_),
        "%d + %d = %d of %d" % (len(menu), len(await_), len(menu | await_), r.get("n_renderable") or -1))

    # L12 RETICLE STAYS IN SCOPE. This leg used to assert it was in scope AND
    # OFF THE MENU, which was true and is no longer: a frame settled its picture
    # and it was promoted. That half was defending a DECISION, not a property —
    # the class this repo calls a check that encodes a reversed decision — and it
    # went red on a correct promotion, which is exactly how such a check
    # announces itself. Kept here as the reason rather than quietly rewritten.
    #
    # The half that IS a property is the one worth holding: Reticle was dropped
    # from SCOPE on a verdict its own author retracted, and that was the error.
    # Whether it is on the menu is the frame's business and changes; whether it
    # is in the worklist at all must not regress. L9 already holds the other
    # half — nothing reaches the menu without a picture.
    leg("L12 reticle_stays_in_scope",
        "Reticle" in (r.get("renderable") or []),
        "renderable=%s menu=%s draws=%s" % ("Reticle" in (r.get("renderable") or []),
                                            "Reticle" in menu, dr.get("Reticle")))

    # L13 BYTES_ONLY IS EVIDENCE AND IS NOT A PICTURE. A PNG that encoded four
    # times longer than the empty control proves SOMETHING rendered; it cannot
    # say what, or where, or whether it was right. It is named so it is not lost
    # into UNKNOWN, and it is kept off the menu so it is not promoted into a
    # look. Both halves matter — the state exists to hold that distinction.
    bytes_only = sorted(n for n in (r.get("renderable") or []) if dr.get(n) == "BYTES_ONLY")
    leg("L13 bytes_only_named_not_on_menu",
        bool(bytes_only) and not (set(bytes_only) & menu),
        "%d BYTES_ONLY, %d leaked onto menu" % (len(bytes_only), len(set(bytes_only) & menu)))

    # L14 NOTHING WITH A NAMED PICTURE PROBLEM REACHES THE MENU. DEFECT draws
    # and draws WRONG; PASSTHROUGH_SUSPECT and UNDECIDABLE are honest about not
    # knowing. All three are verdicts, and none of them is "yes".
    bad = sorted(n for n in menu
                 if dr.get(n) in ("DEFECT", "PASSTHROUGH_SUSPECT", "UNDECIDABLE", "STALE_BODY"))
    leg("L14 no_named_problem_on_menu", not bad, "leaked: %s" % (bad or "none"))

    # L15 THE BODY BINDING, asserted as a PROPERTY rather than a state name:
    # every component on the menu has a still whose recorded body sha equals the
    # sha of the body on disk right now. This is what makes editing a component
    # invalidate its picture without anyone remembering to.
    # THE FIRST VERSION OF THIS LEG WAS A TAUTOLOGY AND IS KEPT HERE AS THE
    # REASON. It iterated the MENU asking whether each member's sha matched —
    # but a drifted sha is exactly what REMOVES a component from the menu, so
    # the drifted case could never appear in the population being checked. It
    # passed with the mechanism intact and it would have passed with the
    # mechanism deleted. A check that asserts nothing, written while building
    # the thing it was meant to assert.
    #
    # Asked the right way round: for every row whose recorded sha DIFFERS from
    # the body on disk, live_set must refuse to call it DRAWS. Population today
    # is the seven zooms I re-authored, so the leg has something to bite on.
    drifted = [n for n, v in (stills.get("components") or {}).items()
               if v.get("body_sha256_16") and v["body_sha256_16"] != lc._body_sha(n)]
    still_drawing = sorted(n for n in drifted if dr.get(n) == "DRAWS")
    leg("L15 drifted_body_refuses_DRAWS",
        bool(drifted) and not still_drawing,
        "%d drifted, %d still read DRAWS %s" % (len(drifted), len(still_drawing),
                                                still_drawing or ""))

    # L16 the staleness check must be LIVE, not decorative. At least one row has
    # to be carrying a real pre-change sha, or L15 is passing over a population
    # where nothing could ever drift and is asserting nothing.
    # Asserted on what live_set DERIVES, not on what the record declares — and
    # that distinction is the whole repair. This leg first read the record for a
    # hand-written STALE_BODY, which is precisely the shadowing that left the
    # sha binding with no population and the mechanism dead. The record says
    # what was SEEN; STALE_BODY is a conclusion, and a conclusion nobody derives
    # is a conclusion nobody can check.
    derived_stale = sorted(n for n in (r.get("renderable") or []) if dr.get(n) == "STALE_BODY")
    leg("L16 staleness_is_reachable", len(derived_stale) >= 1,
        "%d component(s) DERIVED STALE_BODY %s" % (len(derived_stale), derived_stale or ""))

    # L17 THE DRAWS READING CARRIES A STATE, not just a number.
    # An unreadable instrument and a clean result must not render identically.
    leg("L17 draws_reading_has_a_state",
        r.get("draws_state") in (lc.MEASURED, lc.ABSENT, "PARTIAL")
        and "/" in str(r.get("bodies_readable")),
        "draws_state=%s bodies_readable=%s" % (r.get("draws_state"), r.get("bodies_readable")))

    # L18 THE PHOTOGRAPHER IS NOT GATED ON HAVING PHOTOGRAPHED.
    # `menu` is renderable AND frame-proven, and a frame-proof is what a
    # photographing run PRODUCES — so a harness that reads `menu` can never
    # shoot the component that most needs shooting. `to_photograph` is
    # `renderable`, and a STALE_BODY component must be IN it while being OFF
    # the menu. That pair is the whole fix and this leg pins both halves.
    tp = set(r.get("to_photograph") or [])
    stale = sorted(n for n in (r.get("renderable") or []) if dr.get(n) == "STALE_BODY")
    leg("L18 stale_body_is_photographable",
        tp == set(r.get("renderable") or []) and bool(stale) and set(stale) <= tp
        and not (set(stale) & menu),
        "%d to_photograph == %d renderable; %d STALE_BODY, all shootable, none on menu"
        % (len(tp), len(r.get("renderable") or []), len(stale)))

    # L19 THE ABSENT BRANCH IS DRIVEN, not asserted about.
    #
    # The real tree always has bodies, so the container case cannot be reached
    # by reading it — and a leg that merely checks "a state is reported" passes
    # under the very mutation that would break the branch, which is what
    # happened on the first attempt. So this CALLS live_set with `_body_sha`
    # forced to None: the container, in process.
    #
    # The property: an unreadable instrument returns None, never []. A caller
    # can test None; [] reads as "nothing qualified", and that is the lie the
    # whole branch exists to stop.
    _real = lc._body_sha
    try:
        lc._body_sha = lambda _name: None
        a = lc.live_set()
    finally:
        lc._body_sha = _real
    leg("L19 unreadable_bodies_return_None_not_empty",
        a.get("draws_state") == lc.ABSENT
        and a.get("menu") is None and a.get("n_menu") is None
        and a.get("awaiting_picture") is None and a.get("draws") is None
        and a.get("n_renderable") == 27
        and a.get("to_photograph") and len(a["to_photograph"]) == 27,
        "state=%s menu=%r n_menu=%r renderable=%s to_photograph=%s"
        % (a.get("draws_state"), a.get("menu"), a.get("n_menu"),
           a.get("n_renderable"), len(a.get("to_photograph") or [])))

    print("%d/%d legs ok" % (19 - len(FAILS), 19))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
