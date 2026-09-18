#!/usr/bin/env python3
"""The face question gets an ANSWER per placement, or a named absence.

WHY THIS EXISTS. `acceptance_lines` had a MEASURED branch that said only "the
detector ran on this source". That is a report of the instrument's existence,
not of the thing it measured — the same shape as a count with no denominator —
and an agent reading it still had to judge every placement by eye. The merged
single-agent path additionally never CALLED a detector, so every graphic this
lane placed shipped with face clearance judged by eye while the criteria said
a detector had run.

AND THE DANGEROUS HALF: `face_occupied_bands(None, ...)` returns an EMPTY SET.
So MEASURED with no trajectory rendered as "the face occupies no band" — a
clearance nobody measured, wearing the words of one that was. That is absence
rendered as a value, in the function whose own docstring calls that the most
dangerous bug this lane shipped.

IT DRIVES THE SHIPPED FUNCTION. Every leg calls `chatcut_gate.acceptance_lines`
itself; nothing here restates the rule, because a smoke that reimplements the
logic proves the reimplementation.
"""
import sys

sys.path.insert(0, ".")
import chatcut_gate as G                                       # noqa: E402

FPS = 30.0
SPANS = [(0.0, 10.0, 0, 300)]          # one kept span, source==timeline


def traj_at(cy, t0=0.0, t1=10.0, step=0.25):
    """A face trajectory parked at one vertical centre. cy=960 -> center band,
    cy=400 -> top band (600px window, handler.py's rule, via face_bands)."""
    n = int((t1 - t0) / step) + 1
    return [{"t": round(t0 + i * step, 2), "found": True, "cy": float(cy)}
            for i in range(n)]


def ruling(fam, where, t=2.0, hold=1.0):
    return {"beat": 3, "treatment": [fam], "where": where, "src_t0": t,
            "hold_s": hold, "text_content": "SEVENTY PERCENT"}


def lines(rulings, **kw):
    return G.acceptance_lines(rulings, SPANS, FPS, **kw)


FAILS = []


def leg(name, got, needle, absent=None):
    body = "\n".join(got)
    ok = needle in body and (absent is None or absent not in body)
    if not ok:
        FAILS.append("%s: wanted %r%s in:\n%s"
                     % (name, needle,
                        ("" if absent is None else " and NOT %r" % absent),
                        "\n".join("      | " + l for l in got)))
    print("  %-34s %s" % (name, "ok" if ok else "FAIL"))
    return ok


def main():
    print("FACE CLEARANCE IS ANSWERED")

    # FLOOR. Every leg below reads lines out of a placement list; if that list
    # is empty each leg tests nothing and all of them pass. 26 of 27 red proofs
    # in this repo once passed on an empty population.
    base = lines([ruling("text", "middle")], face_state="MEASURED",
                 face_traj=traj_at(960))
    if not base or "no placements carry acceptance criteria" in "\n".join(base):
        print("  FLOOR: acceptance_lines produced NO placements — every leg "
              "below would assert nothing")
        return 1
    print("  %-34s %d line(s)" % ("floor: placements exist", len(base)))

    # 1. The face is in CENTER and the text is ruled INTO center.
    leg("face center, text in center", base, "COLLISION")
    # 2. Same face, text ruled into the TOP band — the free one.
    leg("face center, text in top",
        lines([ruling("text", "upper_third")], face_state="MEASURED",
              face_traj=traj_at(960)), "CLEAR", absent="COLLISION")
    # 3. The band the face sits in must be NAMED, not merely counted.
    leg("the occupied band is named",
        lines([ruling("text", "upper_third")], face_state="MEASURED",
              face_traj=traj_at(960)), "center")
    # 4. A face in the TOP collides with a top-ruled placement, not a middle
    #    one — proves the comparison reads the trajectory, not a constant.
    leg("face top, text in top", 
        lines([ruling("text", "upper_third")], face_state="MEASURED",
              face_traj=traj_at(400)), "COLLISION")
    leg("face top, text in center",
        lines([ruling("text", "middle")], face_state="MEASURED",
              face_traj=traj_at(400)), "CLEAR", absent="COLLISION")
    # 5. ABSENT still says nobody looked.
    leg("absent says nobody looked",
        lines([ruling("text", "middle")], face_state="ABSENT"),
        "Nobody looked", absent="CLEAR")
    # 6. THE DANGEROUS ONE. MEASURED with no evidence must refuse to answer.
    leg("measured without a trajectory",
        lines([ruling("text", "middle")], face_state="MEASURED",
              face_traj=None), "NO TRAJECTORY ARRIVED", absent="CLEAR")
    # 6b. FAILED IS NOT MEASURED. A detector that could not load must take the
    #     NOT CHECKED branch — `startswith("MEASURED")` is the whole guard, and
    #     a state named "FAILED (cv2 missing)" passing it would print a
    #     clearance derived from an empty trajectory.
    #     ISOLATED FROM THE NO-TRAJECTORY GUARD ON PURPOSE. Passing
    #     face_traj=None here would trip BOTH arms, and a case that trips both
    #     arms of a two-arm rule proves neither — measured: the mutation
    #     admitting FAILED to the measured branch came back NOT RED, because
    #     the no-trajectory guard caught it first. A trajectory WITH a FAILED
    #     state is the state check standing alone, and it is reachable: a
    #     detector that loads and then raises part-way could carry partial
    #     points under a FAILED state.
    leg("FAILED never reads as measured",
        lines([ruling("text", "middle")],
              face_state="FAILED — cv2 or the res10 model is missing",
              face_traj=traj_at(960)), "NOT CHECKED", absent="CLEAR")

    # 6c. THE PRODUCER AGREES WITH THE CONSUMER. region_states is what supplies
    #     face_state, and a missing detector there must say FAILED, not ABSENT
    #     and not an empty trajectory. Exercised for real: cv2 is not installed
    #     on a developer machine, so this is the live case, not a simulated one.
    try:
        import subprocess as _sp
        import os as _os
        import chatcut_job_app as _J
        _tiny = "/tmp/tiny_face_probe.mp4"
        if not _os.path.exists(_tiny):
            _sp.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                     "testsrc=size=320x240:rate=10:duration=2", "-y", _tiny],
                    check=True, timeout=120)
        _rs = _J.region_states(_tiny)
        _ok = _rs["face_state"] in ("MEASURED", "FAILED")
        if _rs["face_state"] == "FAILED" and not _rs.get("face_why"):
            _ok = False
        print("  %-34s %s (%s)"
              % ("region_states names its state", "ok" if _ok else "FAIL",
                 _rs["face_state"]))
        if not _ok:
            FAILS.append("region_states returned %r — a detector that could "
                         "not load must say FAILED and say why, never ABSENT "
                         "with an empty trajectory" % _rs["face_state"])
    except Exception as _pe:                                  # noqa: BLE001
        print("  %-34s SKIP (%s)" % ("region_states names its state",
                                     str(_pe)[:60]))

    # 7. A cutaway replaces the picture; a face under it is covered by design.
    leg("cutaway is exempt",
        lines([{"beat": 4, "treatment": ["cutaway"], "where": "full_frame",
                "src_t0": 2.0, "hold_s": 1.0}],
             face_state="MEASURED", face_traj=traj_at(960)),
        "covered by", absent="COLLISION")

    if FAILS:
        print("\n%d LEG(S) FAILED" % len(FAILS))
        for f in FAILS:
            print("  " + f)
        return 1
    print("\nall legs green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
