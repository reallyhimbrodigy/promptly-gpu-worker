"""PR-δ word-release padding — boundary geometry per splice class.

Drives the REAL build_clips_from_words. Word pitch 0.5s: word i spans
[i*0.5, i*0.5+0.4] → 0.1s inter-word gap when adjacent.
"""
import contextlib
import io
import sys

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

def words(n=12, pitch=0.5, dur=0.4):
    return [{"word": f"w{i}", "punctuated_word": f"w{i}",
             "start": round(i * pitch, 3), "end": round(i * pitch + dur, 3)}
            for i in range(n)]

def unwrap(ret):
    return ret[0] if isinstance(ret, tuple) else ret

def run(remove, n=12, video_duration=30.0, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        clips = unwrap(H.build_clips_from_words(words(n, **kw), remove,
                                                video_duration=video_duration))
    return clips, buf.getvalue()

R, Hd = H._RELEASE_PAD_S, H._HEAD_PAD_S

print("=== D1: word-removal splice — release + head pads, core protected ===")
# remove word 5 [2.5, 2.9]; boundary: w4 ends 2.4, w6 starts 3.0; mid=2.7
clips, o = run([{"word_index": 5}])
check("two clips", len(clips) == 2, str(len(clips)))
e0 = clips[0]["source_end"]; s1 = clips[1]["source_start"]
check(f"release pad applied (2.4 -> 2.4+{R})", abs(e0 - (2.4 + R)) < 1e-6, str(e0))
check(f"head pad applied (3.0 -> 3.0-{Hd})", abs(s1 - (3.0 - Hd)) < 1e-6, str(s1))
check("removed word CORE untouched (pads stop at half-span 2.7)",
      e0 <= 2.7 <= s1)
check("divergence cut_pad logged with applied values",
      "action=cut_pad" in o and f"applied_release={R:.3f}" in o
      and f"applied_head={Hd:.3f}" in o, o[-300:])
check("no overlap invariant intact", e0 < s1)

print("\n=== D2: zero-room clamp — tiny removed span + tight gap ===")
# words at pitch 0.41, dur 0.4 → gaps 0.01s; remove word 5
clips, o = run([{"word_index": 5}], pitch=0.41, dur=0.4)
if len(clips) == 2:
    e0, s1 = clips[0]["source_end"], clips[1]["source_start"]
    w4e, w6s = 4 * 0.41 + 0.4, 6 * 0.41
    rm_mid = (5 * 0.41 + (5 * 0.41 + 0.4)) / 2
    check("release clamped to divider", e0 <= rm_mid + 1e-9 and e0 >= w4e - 1e-9, str((e0, rm_mid)))
    check("head clamped to divider", s1 >= rm_mid - 1e-9 and s1 <= w6s + 1e-9, str((s1, rm_mid)))
    check("still no overlap", e0 <= s1)
else:
    check("two clips", False, str(len(clips)))

print("\n=== D3: dead-air pair (consecutive anchors) — pads breathe into silence ===")
# words 0..5 normal, then a 3s silence gap before word 6
ws = words(10)
for i in range(6, 10):
    ws[i]["start"] = round(ws[i]["start"] + 3.0, 3)
    ws[i]["end"] = round(ws[i]["end"] + 3.0, 3)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    clips = unwrap(H.build_clips_from_words(
        ws, [{"after_word_index": 5, "before_word_index": 6, "reason": "dead_air"}],
        video_duration=30.0))
o = buf.getvalue()
check("split at the dead-air pair", len(clips) == 2, str(len(clips)))
if len(clips) == 2:
    e0, s1 = clips[0]["source_end"], clips[1]["source_start"]
    w5e, w6s = 5 * 0.5 + 0.4, 6 * 0.5 + 3.0
    check("full release pad into the silence", abs(e0 - (w5e + R)) < 1e-6, str(e0))
    check("full head pad from the silence", abs(s1 - (w6s - Hd)) < 1e-6, str(s1))

print("\n=== D4: plosive-tail synthetic — the release survives ===")
# 'stop' ends at 2.4 per Deepgram but its audible release runs ~80ms past;
# the removed filler word follows. The clip must retain source past 2.4.
clips, _ = run([{"word_index": 5}])
release_end = clips[0]["source_end"]
check("clip retains 120ms past Deepgram end (>=80ms release)",
      release_end >= 2.4 + 0.08, str(release_end))

print("\n=== D5: first-clip head pad + final tail pad both present ===")
clips, o = run([{"word_index": 5}])
check("first clip starts head-pad early", abs(clips[0]["source_start"] - (0.0 - 0.0)) < 1e-9
      or clips[0]["source_start"] < 0.0 + 1e-9)
# word0 starts at 0.0 → head room 0 → clamped to 0
check("head pad clamps at t=0", clips[0]["source_start"] == 0.0)
ws2 = [{**w, "start": round(w["start"] + 1.0, 3), "end": round(w["end"] + 1.0, 3)} for w in words()]
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    clips2 = unwrap(H.build_clips_from_words(ws2, [{"word_index": 5}], video_duration=30.0))
check("first clip head pad applied when room exists",
      abs(clips2[0]["source_start"] - (1.0 - Hd)) < 1e-6, str(clips2[0]["source_start"]))
last_word_end = 11 * 0.5 + 0.4 + 1.0
check("final tail pad (0.5s) still present",
      abs(clips2[-1]["source_end"] - (last_word_end + 0.5)) < 1e-6, str(clips2[-1]["source_end"]))

print("\n=== D6: no removals -> single clip, only first-head + final-tail pads ===")
clips, o = run([])
check("one clip", len(clips) == 1)
check("zero interior cut_pad lines",
      o.count("action=cut_pad") == 0 or (o.count("action=cut_pad") == 1 and "first_clip_head" in o))

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL CUT-PADDING CASES PASS")
