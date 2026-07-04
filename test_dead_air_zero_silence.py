"""Zero-silence branch battery (the 5912 class, 2026-07-04).

A pre-edited/tight upload makes silero return ZERO regions >=150ms; the
visibility-warning line then dereferences kept[-1] — which is an INT index
into words by construction — and crashed every such job at intake
(AttributeError: 'int' object has no attribute 'get'; user 048c366f x2).
This battery drives the REAL detect_dead_air with the VAD stubbed to the
zero-region result and pins the intended semantics: no crash, the loud
warning on real-length sources, zero mechanical dead-air cuts (full video
flows to Gemini).
"""
import contextlib
import io
import sys

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


def words_span(n, end_s):
    """n evenly spaced dict words ending at end_s — the real transcript shape."""
    step = end_s / n
    return [{"word": f"w{i}", "punctuated_word": f"w{i}",
             "start": round(i * step, 3), "end": round((i + 1) * step - 0.01, 3)}
            for i in range(n)]


def with_vad(regions, fn):
    saved = H._detect_silence_regions_vad
    H._detect_silence_regions_vad = lambda *a, **k: regions
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            out = fn()
    finally:
        H._detect_silence_regions_vad = saved
    return out, buf.getvalue()


print("=== Z1: zero regions on a real-length source — the crash class ===")
out, logs = with_vad([], lambda: H.detect_dead_air(words_span(424, 88.0), set(), "src.mp4"))
check("no crash and zero dead-air cuts", out == [], repr(out))
check("loud inactive warning fired", "dead-air" in logs and "zero regions" in logs, logs[-200:])

print("\n=== Z2: zero regions, short source (<10s) — quiet, still no crash ===")
out, logs = with_vad([], lambda: H.detect_dead_air(words_span(12, 8.0), set(), "src.mp4"))
check("no crash and zero cuts", out == [], repr(out))
check("no warning below the 10s floor", "zero regions" not in logs, logs[-200:])

print("\n=== Z3: zero regions with removals — kept is a strict index subset ===")
out, logs = with_vad([], lambda: H.detect_dead_air(words_span(40, 30.0), {0, 1, 39}, "src.mp4"))
check("index subset path clean", out == [], repr(out))

print("\n=== Z4: regression — a real VAD region still produces a cut ===")
w = words_span(10, 20.0)
w[4]["end"] = 8.0
w[5]["start"] = 10.0  # 2s true gap, VAD-confirmed
out, logs = with_vad([(8.05, 9.95)],
                     lambda: H.detect_dead_air(w, set(), "src.mp4"))
check("dead-air cut still detected on the normal path", len(out) >= 1, repr(out))

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL ZERO-SILENCE CASES PASS")
