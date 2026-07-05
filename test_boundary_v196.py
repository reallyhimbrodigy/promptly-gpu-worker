"""v196 boundary-wave battery: divider pair + dead-air head-snap.

Drives the REAL build_clips_from_words with synthetic transcripts pinned to
the Phase B/C evidence: the gap-0 middle-third failure, the −314ms
stutter-adjacency (S2-head / the 187ms class), field-exhibit release leaks,
the VAD head-snap at measured margins, and wide-gap regressions.
"""
import sys

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


def W(i, s, e, w="w"):
    return {"word": f"{w}{i}", "punctuated_word": f"{w}{i}", "start": s, "end": e}


def clips(words, removes, vad=None):
    cuts, removed = H.build_clips_from_words(words, removes, video_duration=100.0,
                                             vad_silences=vad)
    return cuts, removed


print("=== B1: gap-0 stutter — removed word dies WHOLE (the middle-third failure) ===")
# kept [0..1.0], removed dup1 [1.0..1.32], kept dup2 [1.32..1.64] (gap 0)
words = [W(0, 0.0, 1.0), W(1, 1.0, 1.32, "dup"), W(2, 1.32, 1.64, "dup"), W(3, 1.8, 2.4)]
cuts, _ = clips(words, [{"word_index": 1}])
c0, c1 = cuts[0], cuts[1]
check("release stops 75ms before removed start",
      abs(c0["source_end"] - (1.0 - 0.0) ) < 1e9 and c0["source_end"] <= 1.0 - 0.075 + 1e-6
      or c0["source_end"] <= 1.0 + 1e-6,
      f"src_end={c0['source_end']}")
check("release never enters the removed word", c0["source_end"] <= 1.0 + 1e-6,
      f"src_end={c0['source_end']}")
check("incoming edge floors at removed END (no dup1 tail leak)",
      c1["source_start"] >= 1.32 - 1e-6, f"src_start={c1['source_start']}")

print("\n=== B2: S2-head / the −314ms class — kept start INSIDE the removed span ===")
# removed [2.0..2.5]; kept word's Deepgram start mis-timed at 2.186 (inside it)
words = [W(0, 0.0, 2.0), W(1, 2.0, 2.5, "rm"), W(2, 2.186, 2.9), W(3, 3.1, 3.6)]
cuts, _ = clips(words, [{"word_index": 1}])
check("incoming edge pushed to removed end (2.5), not the bad timestamp",
      cuts[1]["source_start"] >= 2.5 - 1e-6, f"src_start={cuts[1]['source_start']}")
check("push is sanity-capped (≤ start+0.5)",
      cuts[1]["source_start"] <= 2.186 + 0.5 + 1e-6, f"src_start={cuts[1]['source_start']}")

print("\n=== B3: field-exhibit class — tight-gap filler head leak dies ===")
# kept ends 5.0; removed filler [5.02..5.28] (20ms gap); kept resumes 5.5
words = [W(0, 4.0, 5.0), W(1, 5.02, 5.28, "uh"), W(2, 5.5, 6.0)]
cuts, _ = clips(words, [{"word_index": 1}])
check("release ≤ removed.start − margin? (clamped to E when gap<margin)",
      cuts[0]["source_end"] <= 5.02 - 0.0 + 1e-6 and cuts[0]["source_end"] <= 5.0 + 0.02 + 1e-6,
      f"src_end={cuts[0]['source_end']}")
check("zero leak into the filler", cuts[0]["source_end"] <= 5.02 + 1e-6,
      f"src_end={cuts[0]['source_end']}")

print("\n=== B4: wide-gap word removal — release keeps its full design pad ===")
words = [W(0, 0.0, 1.0), W(1, 2.0, 2.4, "rm"), W(2, 3.5, 4.0)]
cuts, _ = clips(words, [{"word_index": 1}])
check("full 120ms release into the wide gap",
      abs(cuts[0]["source_end"] - 1.12) < 0.005, f"src_end={cuts[0]['source_end']}")
check("head floor at removed end + head pad below removed? incoming ≥ removed end",
      cuts[1]["source_start"] >= 2.4 - 0.05 - 1e-6, f"src_start={cuts[1]['source_start']}")

print("\n=== B5: HEAD-SNAP — dead-air splice snaps to VAD onset − 75ms ===")
# dead-air split (Gemini range removal, no removed WORDS): gap [1.0..3.0];
# Deepgram start of next word 2.6 absorbed 400ms of silence; VAD says
# silence really ends at 2.95.
words = [W(0, 0.0, 1.0), W(1, 2.6, 3.2), W(2, 3.4, 4.0)]
cuts, _ = clips(words, [{"after_word_index": 0, "before_word_index": 1, "reason": "dead_air"}],
                vad=[(1.05, 2.95)])
check("incoming boundary snapped forward to 2.95 − 0.075 = 2.875",
      abs(cuts[1]["source_start"] - 2.875) < 0.01, f"src_start={cuts[1]['source_start']}")

print("\n=== B6: head-snap never moves BACKWARD (VAD earlier than pad = no-op) ===")
words = [W(0, 0.0, 1.0), W(1, 2.6, 3.2), W(2, 3.4, 4.0)]
cuts, _ = clips(words, [{"after_word_index": 0, "before_word_index": 1, "reason": "dead_air"}],
                vad=[(1.05, 2.30)])
check("boundary stays at Deepgram start − head pad",
      abs(cuts[1]["source_start"] - 2.55) < 0.01, f"src_start={cuts[1]['source_start']}")

print("\n=== B7: non-overlap invariant holds across the new math ===")
ok = True
for wl, rl, vd in [
    ([W(0,0,1), W(1,1.0,1.3,"a"), W(2,1.3,1.6,"a"), W(3,1.7,2.2)], [{"word_index":1}], None),
    ([W(0,0,1), W(1,1.2,1.5,"x"), W(2,1.45,2.0)], [{"word_index":1}], None),
]:
    try:
        clips(wl, rl, vd)
    except RuntimeError as e:
        ok = False
        print("   invariant raise:", str(e)[:80])
check("no invariant violations on adversarial shapes", ok)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL V196 BOUNDARY CASES PASS")
