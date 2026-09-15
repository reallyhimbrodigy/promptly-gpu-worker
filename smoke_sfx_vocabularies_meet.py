#!/usr/bin/env python3
"""SMOKE — the planner's sixteen sound PREDICATES and ChatCut's thirty-five
NAMED RECORDINGS meet at a closed, complete, live map.

WHY THIS EXISTS. `sfx_name` is a closed enum of moments ("the speaker throws a
verbal blow"); ChatCut's library is a list of recordings ("Vine Boom Impact").
Neither is a spelling of the other. The first translator matched them by shared
tokens and resolved `whoosh` and `ding` perfectly while returning NOTHING for
`transition-sfx` and `punchsfx` — the only two sounds the real edit ruled. A
matcher that always finds something can never report that it found nothing, and
a matcher tuned on the names it was tested with has learned those names.

So the map is written out and CLOSED, and this smoke asks the three questions a
closed map can fail:

  COMPLETE   every token the planner can emit has a decision — a recording, a
             signed silence, or a named absence. A token with no decision
             resolves ABSENT and the beat is dropped, quietly, forever.
  LIVE       every recording the map names still exists in the fetched library.
             A map pointing at a sound that was renamed is a no-op that reads
             like a mapping.
  HONEST     no token is mapped that the planner cannot emit. Dead entries make
             the map look more complete than it is.

Each leg is RED-proven against a mutated map in the same run.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan_for_chatcut as P                                   # noqa: E402
import agentic_editor_app as A                                 # noqa: E402

PLANNER = set(A.SFX_MOMENTS)            # the enum the agent is actually offered


def legs():
    bad = []
    if not PLANNER:
        # ABSENT IS NOT PASS. An empty enum would make every leg below vacuous.
        return [("complete", "SFX_MOMENTS is empty — the planner's vocabulary "
                             "could not be read, so nothing here was checked")]
    decided = (set(P.SFX_LIBRARY) | P.SFX_MEANS_SILENCE
               | P.SFX_NO_SOUND_IN_LIBRARY)
    for tok in sorted(PLANNER - decided):
        bad.append(("complete", "the planner can rule %r and the map has no "
                                "decision for it" % tok))
    ids = P._sound_ids()
    for tok, slug in sorted(P.SFX_LIBRARY.items()):
        if slug not in ids:
            bad.append(("live", "%r -> %r, which is not in the library" % (tok, slug)))
    for tok in sorted(decided - PLANNER):
        bad.append(("honest", "%r is mapped and the planner cannot emit it" % tok))
    return bad


if __name__ == "__main__":
    bad = legs()
    for kind, why in bad:
        print("  [FAIL] %-8s %s" % (kind, why))
    if not bad:
        print("  [ok] all %d planner tokens have a decision" % len(PLANNER))
        print("  [ok] all %d mapped recordings are in the library"
              % len(P.SFX_LIBRARY))
        print("  [ok] nothing is mapped that the planner cannot emit")

    print("\n  RED PROOF")
    red = True
    _lib, _sil, _abs = (dict(P.SFX_LIBRARY), set(P.SFX_MEANS_SILENCE),
                        set(P.SFX_NO_SOUND_IN_LIBRARY))
    _tok = sorted(P.SFX_LIBRARY)[0]

    P.SFX_LIBRARY.pop(_tok)
    r1 = legs()
    P.SFX_LIBRARY.update(_lib)
    print("    a planner token with no decision -> %d leg(s) red" % len(r1))
    red &= any(k == "complete" for k, _ in r1)

    P.SFX_LIBRARY[_tok] = "sound-that-was-renamed"
    r2 = legs()
    P.SFX_LIBRARY.update(_lib)
    print("    a map entry pointing at nothing  -> %d leg(s) red" % len(r2))
    red &= any(k == "live" for k, _ in r2)

    P.SFX_LIBRARY["not-a-planner-token"] = "mouse-click"
    r3 = legs()
    P.SFX_LIBRARY.pop("not-a-planner-token")
    print("    a dead entry in the map          -> %d leg(s) red" % len(r3))
    red &= any(k == "honest" for k, _ in r3)

    _saved, A.SFX_MOMENTS = A.SFX_MOMENTS, {}
    globals()["PLANNER"] = set()
    r4 = legs()
    globals()["PLANNER"] = set(_saved)
    A.SFX_MOMENTS = _saved
    print("    the planner enum unreadable      -> %d leg(s) red" % len(r4))
    red &= bool(r4)

    ok = not bad and red
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
