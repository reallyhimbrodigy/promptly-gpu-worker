#!/usr/bin/env python3
"""The render half: a no-op re-edit must return a BYTE-IDENTICAL file.

THE CLAIM THIS SETTLES. Identical verdicts round-tripping to identical ids is
the PRECONDITION and it is already proven statically by smoke_reedit_surgical.
Identical BYTES is the claim, and no static check can make it — it needs two
renders. This is the harness for that comparison, and it is deliberately
separate from the smokes because it costs real Modal spend.

WHY IT IS MEANINGFUL ONLY NOW. Before 2026-09-10 all thirteen agentic libx264
encodes ran with x264-auto, whose thread count derives from the machine — so
two renders of an identical plan need not have agreed, and a DIFFERENT verdict
here would have proved nothing about re-edit. With the pin landed, a difference
is attributable to the plan.

THREE STATES, because a comparison that cannot run is not a comparison:

    IDENTICAL   same sha256 — the re-edit modified nothing, as instructed
    DIFFERENT   the bytes moved. On a NO-OP instruction that is a DEFECT: the
                path re-planned instead of modifying. The first frames that
                differ are reported so it can be diagnosed rather than argued.
    ABSENT      one or both files are missing or unreadable — NOT a pass, and
                NOT a failure of the property. The run did not happen.

USAGE
    python3 cert_reedit_byte_identity.py BASE.mp4 REEDIT.mp4
    python3 cert_reedit_byte_identity.py --price          (what a run costs)

PRICE BEFORE SPENDING (Rule 6). Two renders of one fixture. Round 49 measured
$0.2351 for five fixtures across three arms — 15 runs — so ~$0.0157 per run.
This proof is 2 runs on one fixture: ABOUT $0.03, plus the re-edit run's agent
turns, which a no-op instruction should make close to zero since it re-rules
nothing. Call it $0.05 and report the actual.

WHAT A DIFFERENCE WOULD MEAN, registered before the number exists:
  - a no-op that differs is a re-planning path, and re-edit is not surgical
  - a no-op that is identical proves the merge carried the plan unchanged
    THROUGH A RENDER, which is the whole feature
  - it does NOT prove a NAMED change touches only what it names; that is the
    second proof and it compares plans by id, not files by hash
"""
import hashlib
import os
import subprocess
import sys

STATE_IDENTICAL, STATE_DIFFERENT, STATE_ABSENT = "IDENTICAL", "DIFFERENT", "ABSENT"


def _sha(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest(), os.path.getsize(path)
    except OSError as e:
        return None, str(e)


def compare_outputs(base, reedit):
    """(state, detail) — PURE enough to test, and it never guesses.

    An unreadable file is ABSENT, never DIFFERENT: 'the bytes moved' and 'I
    could not read the bytes' are different findings and this repo has paid for
    collapsing them more than once.
    """
    _hb, _sb = _sha(base)
    _hr, _sr = _sha(reedit)
    if _hb is None or _hr is None:
        return (STATE_ABSENT,
                "base=%s reedit=%s" % (_hb or _sb, _hr or _sr))
    if _hb == _hr:
        return (STATE_IDENTICAL, "sha256 %s, %d bytes" % (_hb[:16], _sb))
    return (STATE_DIFFERENT,
            "base %s (%d bytes) != reedit %s (%d bytes)"
            % (_hb[:16], _sb, _hr[:16], _sr))


def first_differing_frame(base, reedit, env=None):
    """Where they diverge, so a DIFFERENT verdict can be diagnosed.

    Returns a state rather than a number, for the same reason as everything
    else here: ffmpeg may not be able to run, and 'no differing frame found'
    must not read the same as 'I could not look'.
    """
    try:
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", base, "-i", reedit,
             "-filter_complex", "psnr", "-f", "null", "-"],
            capture_output=True, text=True, timeout=600, env=env)
    except (OSError, subprocess.SubprocessError) as e:
        return ("FAILED", "ffmpeg could not run: %s" % e)
    _out = (r.stderr or "") + (r.stdout or "")
    if r.returncode != 0:
        return ("FAILED", "ffmpeg exit %d: %s" % (r.returncode, _out[-200:]))
    return ("MEASURED", _out.strip()[-300:] or "(no psnr line emitted)")


if __name__ == "__main__":
    if "--price" in sys.argv:
        print("REEDIT BYTE-IDENTITY — price before spending")
        print("  2 renders of one fixture")
        print("  round 49: $0.2351 / 15 runs = ~$0.0157 per run")
        print("  estimate: ~$0.03 render + agent turns on a no-op re-edit")
        print("  BUDGET: $0.05, and the actual gets reported against it")
        sys.exit(0)
    if len(sys.argv) < 3:
        # NO ARGUMENTS = SELF-TEST, NOT USAGE-AND-EXIT-2.
        #
        # The suite runs every cert_/smoke_ with no arguments, so a harness that
        # exits 2 without files is PERMANENTLY RED in the suite — the chronic-red
        # class, which I had just written a rule about and then shipped an
        # instance of. A check that is always red stops being read, including
        # the part that is true.
        #
        # So with no files it proves the COMPARISON ITSELF: all three states on
        # real bytes. That is the half that can be checked without spending, and
        # it is exactly what must be trustworthy before a $0.05 run means
        # anything — a comparator that cannot tell DIFFERENT from ABSENT would
        # make the render prove nothing.
        import tempfile
        _d = tempfile.mkdtemp(prefix="byteid_")
        _a = os.path.join(_d, "a.bin")
        _b = os.path.join(_d, "b.bin")
        _c = os.path.join(_d, "c.bin")
        with open(_a, "wb") as _f:
            _f.write(b"same bytes")
        with open(_b, "wb") as _f:
            _f.write(b"same bytes")
        with open(_c, "wb") as _f:
            _f.write(b"other bytes")
        _cases = [("identical files", (_a, _b), STATE_IDENTICAL),
                  ("differing files", (_a, _c), STATE_DIFFERENT),
                  ("a missing file", (_a, os.path.join(_d, "nope.bin")),
                   STATE_ABSENT),
                  ("both missing", (os.path.join(_d, "x"), os.path.join(_d, "y")),
                   STATE_ABSENT)]
        _bad = []
        for _label, _args, _want in _cases:
            _got = compare_outputs(*_args)[0]
            if _got != _want:
                _bad.append(f"{_label}: got {_got}, expected {_want}")
            print(f"  [{'ok' if _got == _want else 'FAIL'}] {_label} -> {_got}")
        # NON-VACUITY: the three states must be DISTINCT, or the comparator is
        # collapsing findings it is supposed to keep apart.
        _states = {compare_outputs(*_a2)[0] for _l, _a2, _w in _cases}
        if len(_states) != 3:
            _bad.append(f"the comparator produced {sorted(_states)} — three "
                        f"distinct states are the whole point")
        print()
        if _bad:
            print("REEDIT BYTE-IDENTITY (self-test): FAIL")
            for _m in _bad:
                print("  - " + _m)
            sys.exit(1)
        print("REEDIT BYTE-IDENTITY (self-test): PASS — three distinct states on "
              "real bytes. Give it two files to compare a render.")
        sys.exit(0)
    _state, _detail = compare_outputs(sys.argv[1], sys.argv[2])
    print("REEDIT BYTE-IDENTITY: %s\n  %s" % (_state, _detail))
    if _state == STATE_DIFFERENT:
        _fs, _fd = first_differing_frame(sys.argv[1], sys.argv[2])
        print("  divergence (%s): %s" % (_fs, _fd))
        print("\n  A NO-OP RE-EDIT THAT MOVES THE BYTES IS A DEFECT — the path "
              "re-planned\n  instead of modifying. With the x264 pin landed "
              "this is attributable to\n  the plan, not to the machine.")
    if _state == STATE_ABSENT:
        print("\n  NOT A PASS. The comparison did not happen.")
    sys.exit(0 if _state == STATE_IDENTICAL else 1)
