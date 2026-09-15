#!/usr/bin/env python3
"""SMOKE — the plan does not tell the agent to skip what the spec ruled.

MEASURED, not suspected. On the blue-shirt run the spec said

    families: ["caption", "cut"]        (the brief said "Burn readable captions")

and the plan this translator emitted said, unconditionally:

    NO CAPTIONS. They are not in the brief.

The export came back with no captions — and that was not a wiring gap, it was
an INSTRUCTION TO SKIP. The producer contradicted the ruling it was translating.

The cause: captions are ruled ONCE for the whole edit, in set_spec's `families`,
while text/card/zoom/sfx are ruled per beat. `families_in(rows)` reads the beat
rows, so it could never see a caption, and the section was written as prose
around that blind spot rather than as a question about the spec.

BOTH DIRECTIONS ARE CHECKED. A section that appears whatever the spec says is
the same defect wearing the other face.
"""
import copy
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan_for_chatcut as P                                   # noqa: E402


def _beat(t0, t1):
    return {"treatment": ["none"], "src_t0": t0, "src_t1": t1, "cut": "keep",
            "purpose": "hook", "why": "smoke", "text_content": None}


BASE = {
    "ledger": {"keep_spans": [[0.0, 10.0]], "source_duration_s": 10.0,
               "spec": {"mode": "targeted_change", "families": ["cut"]}},
    "plan": [_beat(0.0, 10.0)],
}


def emit(plan):
    fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(plan, fh)
    fh.close()
    try:
        return P.render(fh.name, staged=True, allow_drop=True)
    finally:
        os.unlink(fh.name)


def legs():
    bad = []

    with_caps = copy.deepcopy(BASE)
    with_caps["ledger"]["spec"]["families"] = ["caption", "cut"]
    t = emit(with_caps)
    if "NO CAPTIONS" in t:
        bad.append("spec ruled caption and the plan still says NO CAPTIONS")
    if "THE CAPTIONS" not in t:
        bad.append("spec ruled caption and the plan carries no caption section")
    for call in ('edit_captions action:"enable"', "read_captions",
                 "set_max_characters"):
        if call not in t:
            bad.append("caption section omits the verified call `%s`" % call)
    if "DO NOT PICK A STYLE PRESET" not in t:
        bad.append("caption section does not say the style mapping is unmade")

    without = copy.deepcopy(BASE)
    t2 = emit(without)
    if "THE CAPTIONS" in t2:
        bad.append("spec did NOT rule caption and a caption section appeared")
    if "NO CAPTIONS" not in t2:
        bad.append("spec did NOT rule caption and the plan does not say so")
    return bad


if __name__ == "__main__":
    bad = legs()
    for b in bad:
        print("  [FAIL] %s" % b)
    if not bad:
        print("  [ok] spec rules caption -> the plan carries the verified calls")
        print("  [ok] spec omits caption -> the plan says NO CAPTIONS")
        print("  [ok] the plan never contradicts the spec in either direction")

    # RED PROOF — restore the hardcoded assertion and the leg must fire.
    print("\n  RED PROOF")
    _real = P.render

    def _hardcoded(path, **kw):
        out = _real(path, **kw)
        return (out.replace("## 4. THE CAPTIONS", "## 4. (removed)")
                + "\n  NO CAPTIONS. They are not in the brief.\n")
    P.render = _hardcoded
    red = legs()
    P.render = _real
    print("    the old unconditional line -> %d leg(s) red" % len(red))

    ok = not bad and bool(red)
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
