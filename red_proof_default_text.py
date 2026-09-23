#!/usr/bin/env python3
"""RED proof for smoke_default_text.py — two sources, one property.

The checks it defends sit on OPPOSITE sides of a seam, so the mutations do
too: three go into bake_registry.py (the detector and the population it is
scoped to) and three into chatcut_registry_baked.json (the artifact ChatCut
actually reads). A proof that only mutated the detector would say nothing
about whether the artifact still carries what the detector is looking for —
that is the producer/consumer law, applied to a red proof.

EVERY MUTATION NAMES THE LEG IT MUST REDDEN, and a red whose output does not
contain that leg's FAIL line is reported NOT RED. A mutant that crashes or
stops parsing exits non-zero too, and a red that is not about the property is
exactly as wrong as a green that is not.
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_default_text.py")
BAKE = os.path.join(HERE, "bake_registry.py")
ART = os.path.join(HERE, "chatcut_registry_baked.json")
BODY = os.path.join(HERE, "port", "bodies", "DeviceMockup.jsx")


def _env():
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


def _detector_fires():
    """Precondition helper: does the shipped detector name an injected default?"""
    sys.path.insert(0, HERE)
    import importlib
    bk = importlib.import_module("bake_registry")
    importlib.reload(bk)
    reg = json.load(io.open(ART, encoding="utf-8"))["components"]
    props = [dict(p) for p in reg["TweetBubble"]["properties"]]
    for p in props:
        if p["key"] == "statLikes":
            p["defaultValue"] = "1.2K"
    return len(bk.default_text_offenders("TweetBubble", props)) == 1


MUTATIONS = [
    # ── the detector ──────────────────────────────────────────────────────
    # IT STOPS DETECTING. L1 reads zero offenders today and would read zero
    # with the detector blinded — a clean zero and a blind check are
    # indistinguishable in a tally, which is exactly why L6 drives it on a
    # known-bad input instead of asserting today's artifact.
    ("detector_goes_blind", BAKE,
     '        and p["defaultValue"].strip() != ""',
     '        and False',
     "L6 the_refusal_actually_fires",
     _detector_fires),
    # THE SCOPING WIDENS TO EVERY TEXT DEFAULT. This is the failure the rule
    # was written around: fifteen chrome defaults — textShadow's rgba(),
    # StickyNotes' "5%", StepDivider's "STEP" — all light up, the check
    # arrives as a wave of red on working components, and it is reverted the
    # same day for being right about nothing.
    ("scoping_widens_to_all_text", BAKE,
     '        if p["key"] in keys',
     '        if True',
     "L1 no_flattened_slot_carries_a_default",
     None),
    # THE POPULATION EMPTIES. Every leg below iterates the keys flatten
    # created; if that set came back empty they would all pass over nothing.
    ("population_goes_empty", BAKE,
     '    spec = flatten_spec.FLATTEN.get(name)\n    if not spec:\n        return set()',
     '    spec = flatten_spec.FLATTEN.get(name)\n    if True:\n        return set()',
     "L0 flattened_slots_are_a_real_population",
     None),
    # ── the artifact ChatCut reads ────────────────────────────────────────
    # A DEFAULT COMES BACK. The exact regression the refusal exists for: a
    # well-formed property, indistinguishable from every other, drawing our
    # number on every placement that leaves the field alone.
    ("a_default_comes_back", ART,
     '"key": "statLikes",\n     "label": "Likes",\n     "type": "text",\n     "defaultValue": ""',
     '"key": "statLikes",\n     "label": "Likes",\n     "type": "text",\n     "defaultValue": "1.2K"',
     "L2 tweetbubble_stats_are_four_empty_text_props",
     None),
    # THE COUNTS COME BACK BAKED. Both halves of a bake move together — the
    # property existing does not prove the literal left.
    ("the_counts_come_back_baked", ART,
     'stats: { replies: props.statReplies, reposts: props.statReposts, '
     'likes: props.statLikes, views: props.statViews }',
     'stats: {\\"replies\\": 128, \\"reposts\\": 412, \\"likes\\": 1200, \\"views\\": 98000}',
     "L3 no_engagement_count_left_in_the_blob",
     None),
    # THE ROW STOPS CLOSING UP. An empty stat draws an icon with no number
    # beside it — which is the placeholder problem, not the blank one.
    ("the_row_stops_closing_up", ART,
     '.filter((s) => s.label !== \\"\\")',
     '.filter((s) => s.label !== undefined)',
     "L4 empty_draws_nothing_and_the_row_closes_up",
     None),
    # ── AN INJECTED EMPTY STILL ──────────────────────────────────────────
    # Zac's named mutant: put the error message back in the branch that runs
    # when a picture slot is empty. This is a SOURCE mutation, aimed at the
    # half of the rule the registry cannot see.
    ("an_empty_still_draws_an_error_string", BODY,
     "  if (!still) return null;",
     '  if (!still) { return <div style={rootStyle}>NO STILL</div>; }',
     "L8 no_error_string_is_drawn_as_content",
     None),
    # AND A PICTURE SLOT ACQUIRES A DEFAULT — the same defect as a text
    # default, in the field where it would render as someone else's logo on
    # every placement that left it alone.
    ("a_picture_slot_gains_a_default", ART,
     '"key": "logoUrl",\n     "label": "logoUrl",\n     "type": "text",\n     "defaultValue": ""',
     '"key": "logoUrl",\n     "label": "logoUrl",\n     "type": "text",\n     "defaultValue": "https://promptly.video/logo.png"',
     "L9 every_picture_slot_defaults_to_empty",
     None),
]


def run():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True,
                       env=_env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def failed(out, phrase):
    return any(phrase in ln and "FAIL" in ln for ln in out.splitlines())


def main():
    rc, out = run()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-900:])
        return 2
    print("baseline green.\n")

    originals = {f: io.open(f, encoding="utf-8").read() for f in (BAKE, ART, BODY)}
    red, faults, vacuous = 0, 0, []
    for name, src, old, new, phrase, pre in MUTATIONS:
        raw = originals[src]
        if raw.count(old) != 1:
            print("  %-30s HARNESS FAILURE: anchor %dx in %s"
                  % (name, raw.count(old), os.path.basename(src)))
            faults += 1
            continue
        if pre is not None and not pre():
            vacuous.append(name)
            print("  %-30s VACUOUS   precondition false" % name)
            faults += 1
            continue
        io.open(src, "w", encoding="utf-8").write(raw.replace(old, new, 1))
        rc2, out2 = run()
        io.open(src, "w", encoding="utf-8").write(raw)
        named = failed(out2, phrase)
        ok = rc2 != 0 and named
        red += 1 if ok else 0
        print("  %-30s %s   rc=%d named=%s   [%s]"
              % (name, "RED " if ok else "NOT RED", rc2, named,
                 os.path.basename(src)))
        for f, o in originals.items():
            if io.open(f, encoding="utf-8").read() != o:
                print("  HARNESS FAILURE: residue in %s after %s"
                      % (os.path.basename(f), name))
                faults += 1

    for f, o in originals.items():
        io.open(f, "w", encoding="utf-8").write(o)
    print("\n%d/%d RED-proven%s" % (red, len(MUTATIONS),
          ("; VACUOUS: " + ", ".join(vacuous)) if vacuous else ""))
    return 0 if (MUTATIONS and red == len(MUTATIONS) and not faults) else 1


if __name__ == "__main__":
    sys.exit(main())
