#!/usr/bin/env python3
"""Adapter #2 (MULTI_CLIP) cert — offline, $0, the resolution contract enforced.

"Combine my clips" is top-tier demand and fully buildable without Gemini. The
socket was frozen before the capability existed (adapter_contract.py) precisely
so the build could be checked against a written contract instead of a memory of
one. This asserts that contract, both directions.

THE ONE LAW THAT MATTERS: N clips resolve to ONE video on ONE clock. Word
timings are re-clocked onto the stitched timeline as a single index space, so a
plan's word indices mean exactly what they mean on adapter #1. A second clock
here would be the same class of defect the shared-clock law exists to prevent,
and it would be invisible until captions drifted on the second clip.

  python3 cert_multi_clip.py
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
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import adapter_contract as A

    R = A.FootageRef
    c1 = R(local_path="/tmp/a.mp4", kind="video", duration_s=10.0, source_url="s3://a")
    c2 = R(local_path="/tmp/b.mp4", kind="video", duration_s=5.0, source_url="s3://b")
    c3 = R(local_path="/tmp/c.mp4", kind="video", duration_s=2.5)
    w1 = [{"word": "hello", "start": 1.0, "end": 1.4},
          {"word": "there", "start": 1.5, "end": 1.9}]
    w2 = [{"word": "again", "start": 0.5, "end": 0.9}]

    print("=== ARM 1: structural refusal (degrade allowed, silence is not) ===")
    for label, args in (
        ("zero attachments", ([],)),
        ("one attachment (that is adapter #1)", ([c1],)),
    ):
        try:
            A.adapt_multi_clip("x", args[0])
            check(f"refuses {label}", False, "no raise")
        except ValueError:
            check(f"refuses {label}", True)
        except Exception as e:
            check(f"refuses {label}", False, f"wrong type {type(e).__name__}")
    try:
        A.adapt_multi_clip("x", [c1, R(local_path="", kind="video", duration_s=3)])
        check("refuses a clip with no path", False, "no raise")
    except ValueError:
        check("refuses a clip with no path", True)
    try:
        A.adapt_multi_clip("x", [c1, R(local_path="/tmp/z.mp4", kind="video", duration_s=0)])
        check("refuses an unmeasured duration", False, "no raise")
    except ValueError:
        check("refuses an unmeasured duration", True)
    try:
        A.adapt_multi_clip("x", [c1, c2], word_timings_per_clip=[w1])
        check("refuses non-parallel word_timings", False, "no raise")
    except ValueError:
        check("refuses non-parallel word_timings", True)

    print("\n=== ARM 2: the envelope keeps ALL N refs, in timeline order ===")
    env = A.adapt_multi_clip("combine these", [c1, c2, c3],
                             word_timings_per_clip=[w1, w2, None],
                             stitched_path="/tmp/stitched.mp4")
    check("source_kind is MULTI_CLIP", env.source_kind == A.MULTI_CLIP)
    check("all 3 refs kept", len(env.footage_refs) == 3)
    check("order preserved", [r.local_path for r in env.footage_refs]
          == ["/tmp/a.mp4", "/tmp/b.mp4", "/tmp/c.mp4"])
    check("clip 0 primary, rest supplementary",
          [r.role for r in env.footage_refs] == ["primary", "supplementary", "supplementary"])
    check("provenance preserved", env.footage_refs[0].source_url == "s3://a")
    check("vibe carried", env.intent_hints.get("vibe") == "combine these")
    # The caller's objects must not be mutated — that would be a transform.
    check("caller's FootageRef NOT mutated", c2.role == "primary", f"c2.role={c2.role}")

    print("\n=== ARM 3: ONE CLOCK — words re-clocked onto the stitched timeline ===")
    ws = env.word_timings
    check("words concatenated across clips", len(ws) == 3, repr(len(ws)))
    check("clip 0 words unshifted", ws[0]["start"] == 1.0 and ws[0]["end"] == 1.4)
    # clip 1 starts at 10.0 (clip 0's duration): 0.5 -> 10.5
    check("clip 1 words shifted by clip 0's duration",
          ws[2]["start"] == 10.5 and ws[2]["end"] == 10.9,
          f"got {ws[2]['start']}/{ws[2]['end']}")
    check("per-word provenance recorded",
          [w["_clip_index"] for w in ws] == [0, 0, 1])
    check("word text untouched", ws[2]["word"] == "again")
    check("monotonic across the seam", all(ws[i]["start"] <= ws[i + 1]["start"]
                                           for i in range(len(ws) - 1)))
    # A SILENT clip contributes no words but MUST still advance the offset —
    # dropping its time slides every later word early, the off-by-a-clip drift.
    env2 = A.adapt_multi_clip("x", [c1, c3, c2],
                              word_timings_per_clip=[w1, None, w2],
                              stitched_path="/tmp/s2.mp4")
    check("a SILENT middle clip still advances the clock",
          env2.word_timings[2]["start"] == 13.0,
          f"got {env2.word_timings[2]['start']} (expect 10.0 + 2.5 silent + 0.5)")

    print("\n=== ARM 4: core_inputs — one video, one clock, summed duration ===")
    path, vibe, dur, words = A.core_inputs(env)
    check("core gets the STITCHED path", path == "/tmp/stitched.mp4", repr(path))
    check("core gets the vibe", vibe == "combine these")
    check("duration is the SUM of all clips", abs(dur - 17.5) < 1e-6, repr(dur))
    check("core gets the re-clocked words", words is ws)
    # No stitched file => refuse loudly. A core reading clip 0 alone while the
    # user attached three is a silent wrong answer.
    try:
        A.core_inputs(A.adapt_multi_clip("x", [c1, c2],
                                         word_timings_per_clip=[w1, w2]))
        check("refuses to run the core with no stitched file", False, "no raise")
    except ValueError:
        check("refuses to run the core with no stitched file", True)

    print("\n=== ARM 5: adapter #1 is untouched (no regression on the live path) ===")
    e1 = A.adapt_single_video("punchy", [c1], word_timings=w1)
    check("single_video still maps", A.core_inputs(e1)[0] == "/tmp/a.mp4")
    check("single_video word list is the SAME OBJECT (identity guarantee)",
          A.core_inputs(e1)[3] is w1)
    check("single_video stitched_path is None", e1.stitched_path is None)
    check("single_video duration is the clip's, not a sum",
          A.core_inputs(e1)[2] == 10.0)

    print("\n=== ARM 6: DARK by default ===")
    os.environ.pop("PROMPTLY_ADAPTER_V1", None)
    check("adapter routing off unless the flag is set", A.enabled({}) is False)
    check("per-job test override still works", A.enabled({"adapter_v1_test": True}) is True)

    print()
    if FAILURES:
        print(f"MULTI-CLIP CERT: {len(FAILURES)} FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("MULTI-CLIP CERT: ALL PASS (structural refusal, N refs ordered, ONE clock "
          "re-clocked with provenance, silent clip advances time, summed duration, "
          "adapter #1 identity intact)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
