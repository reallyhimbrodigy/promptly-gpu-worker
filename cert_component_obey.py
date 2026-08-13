#!/usr/bin/env python3
"""COMPONENT_OBEY cert — offline, $0, both legs, both directions.

JUDGE's DISHONOR_ROUTE_VERDICT (2026-08-11) settled where the dishonor cluster
lives, and it is not where the unified-core flip was aimed:

    cluster silent-drop, pre-outage clean cohort [MEASURED]
      lean      94.0% (n=215)   <- 20.1% of lean jobs carry a cluster ask
      premium   63.5% (n=178)
      standard  54.5% (n=749)
    motion_graphics alone: 96% silent on lean vs 37% on premium.

So the lever is a generalized component-ask override with two legs — HONOR where
the route's toolbox has the component, NOTE where it does not — and the note leg
is the one that reaches the 94%, because lean routes never call the editorial
model at all. A prompt-side fix cannot reach them by construction.

This cert is pure-python: it imports the predicates directly and asserts
behaviour on both arms. It costs nothing and runs in the deploy gate, so the
paid 3-arm PLAN_ONLY A/B (cert_mg_honoring_planonly_app.py) is reserved for the
one question only real Gemini can answer: does the HONOR leg change the plan.

  python3 cert_component_obey.py
"""
import os
import sys

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  [PASS] {label}")
    else:
        FAILURES.append(f"{label}{(' — ' + detail) if detail else ''}")
        print(f"  [FAIL] {label}{(' — ' + detail) if detail else ''}")


def main():
    # Import with the flag DARK so the byte-identity arm is honest.
    os.environ.pop("PROMPTLY_COMPONENT_OBEY", None)
    os.environ.pop("PROMPTLY_MG_OBEY", None)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import handler as H

    print("=== ARM 1: flag DARK — must be byte-identical to today ===")
    check("no directive when dark", H._mg_request_directive("add motion graphics") == "")
    check("no notes when dark", H._component_unmet_notes("add motion graphics", "minimal") == [])
    check("no notes when dark, multi-ask",
          H._component_unmet_notes("add b-roll and transitions", "minimal") == [])

    print("\n=== ARM 2: detector precision (the negation guard is load-bearing) ===")
    P = H._parse_component_requests
    check("motion graphics detected", "motion_graphics" in P("please add motion graphics"))
    check("transitions detected", "transitions" in P("add some transitions"))
    check("text overlay detected", "text_overlay" in P("add text overlays"))
    check("multi-ask detected",
          {"motion_graphics", "transitions"} <= P("add motion graphics and transitions"))
    check("plain edit asks for nothing", P("make it punchy and viral") == set())
    # Negatives belong to _parse_off_features (the deterministic strip). A
    # negation arriving here as a REQUEST would make us 'honour' the opposite of
    # what the user said — the exact failure the obedience law names.
    check("negation NOT a request: no motion graphics",
          "motion_graphics" not in P("no motion graphics please"))
    check("negation NOT a request: without transitions",
          "transitions" not in P("clean cut without transitions"))
    check("negation NOT a request: remove text",
          "text_overlay" not in P("remove the text overlays"))

    os.environ["PROMPTLY_COMPONENT_OBEY"] = "1"

    print("\n=== ARM 3: LEG B — NOTE where the toolbox cannot (the 94% lever) ===")
    n = H._component_unmet_notes("add motion graphics", "minimal")
    check("lean route + MG ask -> exactly one note", len(n) == 1, repr(n))
    check("the note NAMES the ask", n and "motion graphics" in n[0].lower(), repr(n))
    check("the note names what would change it",
          n and "speaking to camera" in n[0].lower(), repr(n))
    n2 = H._component_unmet_notes("add b-roll and motion graphics", "minimal")
    check("multi-ask -> ONE combined note, not a pile", len(n2) == 1, repr(n2))
    check("combined note names BOTH", n2 and "b-roll" in n2[0].lower()
          and "motion graphics" in n2[0].lower(), repr(n2))
    check("uncut route says 'uncut', not 're-pace'",
          "uncut" in (H._component_unmet_notes("add transitions", "minimal_speech_uncut")
                      or [""])[0].lower())

    print("\n=== ARM 4: LEG A owns what the toolbox CAN do — no double-speak ===")
    # standard_editorial can build all four: nothing is 'unmet', so no note.
    check("standard editorial + MG ask -> NO unmet note (leg A honours it)",
          H._component_unmet_notes("add motion graphics", "standard_editorial") == [])
    check("standard editorial + all four -> NO unmet note",
          H._component_unmet_notes("add motion graphics, b-roll, transitions and text overlays",
                                   "standard_editorial") == [])
    # hype/moodreel can do transitions but not the rest — the note must be
    # PARTIAL, naming only what is genuinely unmet.
    nh = H._component_unmet_notes("add transitions and motion graphics", "hype")
    check("hype: transitions ARE buildable -> not named as unmet",
          nh and "transition" not in nh[0].lower(), repr(nh))
    check("hype: motion graphics ARE unmet -> named",
          nh and "motion graphics" in nh[0].lower(), repr(nh))
    check("hype + transitions only -> NO note at all",
          H._component_unmet_notes("add transitions", "hype") == [])

    print("\n=== ARM 5: LEG A — the directive arms cluster-wide when armed ===")
    check("MG ask arms the directive", H._mg_request_directive("add motion graphics") != "")
    check("transitions ask arms it too (cluster-wide, the generalization)",
          H._mg_request_directive("add some transitions") != "")
    check("b-roll ask arms it", H._mg_request_directive("add b-roll of the city") != "")
    check("a plain edit still arms NOTHING (byte-identical prompt)",
          H._mg_request_directive("make it punchy") == "")
    check("a NEGATIVE never arms the directive",
          H._mg_request_directive("no motion graphics") == "")

    print("\n=== ARM 5b: NEGOTIATED-NEVER [§4.5/§4.8] — the ask outlives the feature ===")
    # §4.8 removed the music machinery entirely. §4.5 is unconditional, so the
    # 72 people who asked for music must still get an honest answer. These
    # assertions exist because deleting a feature is exactly when its users go
    # silent by accident.
    os.environ.pop("PROMPTLY_COMPONENT_OBEY", None)
    check("the ask is still DETECTED after the feature is gone",
          H._parse_music_ask("can you add background music") is True)
    check("negation still guarded ('no music' is a negative)",
          H._parse_music_ask("no music please") is False)
    n = H._negotiated_never_notes("add some background music")
    check("an honest note fires with NO flag set (a flag would reintroduce the "
          "silent drop by accident)", len(n) == 1, repr(n))
    check("silent when nobody asked", H._negotiated_never_notes("make it punchy") == [])
    check("the note does NOT say 'yet' — a decision is not a roadmap",
          n and "yet" not in n[0].lower(), repr(n))
    check("it names what the product DOES do with audio instead of dangling a future",
          n and "your own audio" in n[0].lower(), repr(n))
    check("the music MACHINERY is gone (§4.8: dead-purpose code does not stay dark)",
          not hasattr(H, "_music_filter_chain") and not hasattr(H, "_music_pick_bed")
          and not hasattr(H, "_MUSIC_BED_LUFS"),
          "music machinery still importable")

    print("\n=== ARM 6: MG_OBEY still works alone (predecessor unbroken) ===")
    os.environ.pop("PROMPTLY_COMPONENT_OBEY", None)
    os.environ["PROMPTLY_MG_OBEY"] = "1"
    check("MG_OBEY alone still arms the MG directive",
          H._mg_request_directive("add motion graphics") != "")
    check("MG_OBEY alone does NOT arm the note leg (that is COMPONENT_OBEY's)",
          H._component_unmet_notes("add motion graphics", "minimal") == [])
    check("MG_OBEY alone does not arm a transitions-only ask",
          H._mg_request_directive("add some transitions") == "")

    print()
    if FAILURES:
        print(f"COMPONENT-OBEY CERT: {len(FAILURES)} FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("COMPONENT-OBEY CERT: ALL PASS (dark byte-identical, negation-guarded, "
          "note-where-not, honor-where-toolbox, partial toolbox, MG_OBEY intact)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
