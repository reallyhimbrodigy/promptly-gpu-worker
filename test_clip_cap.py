"""Pre-freeze F3: intake duration cap — honest fast reject before spend for
sources past the boundary-probed editorial-path limit."""
import re

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


print("=== C1: classify_error — CLIP_TOO_LONG class, verbatim message ===")
c = H.classify_error(RuntimeError(
    "CLIP_TOO_LONG: source is 149.9s; the intake cap is 120s (boundary-probed editorial-path limit)."))
check("error_code", c["error_code"] == "CLIP_TOO_LONG")
check("user_message verbatim (N from the cap constant)",
      c["user_message"] == "Promptly currently edits clips up to %s minutes — trim and resubmit."
      % H._clip_cap_minutes_label())
check("not retryable (same clip will always reject)", c["retryable"] is False)
check("requires a different (trimmed) video", c["requires_new_video"] is True)

print("\n=== C2: N label formatting ===")
check("120s → '2'", H._MAX_SOURCE_DURATION_S != 120.0 or H._clip_cap_minutes_label() == "2")
check("label is clean (no trailing zeros)", not H._clip_cap_minutes_label().endswith("0")
      or "." not in H._clip_cap_minutes_label())
check("message reads in minutes", "minutes" in c["user_message"] and "trim and resubmit" in c["user_message"])

print("\n=== C3: the boundary evidence brackets the cap (clean-window verdicts) ===")
check("known-PASSING towel anchor (74.9s) is inside the cap", 74.9 <= H._MAX_SOURCE_DURATION_S)
check("known-PASSING 90.4s probe is inside the cap", 90.4 <= H._MAX_SOURCE_DURATION_S)
check("known-PASSING 110.4s probe is inside the cap", 110.4 <= H._MAX_SOURCE_DURATION_S)
check("known-FLOORING 149.9s burn-in probe is outside the cap", 149.9 > H._MAX_SOURCE_DURATION_S)

print("\n=== C4: outer rescue never touches an input reject ===")
check("CLIP_TOO_LONG in _OUTER_RESCUE_DENY", "CLIP_TOO_LONG" in H._OUTER_RESCUE_DENY)

print("\n=== C5: raise-site placement (source pins) ===")
src = open("handler.py").read()
i_probe = src.find("source_duration = probe_duration(source_path) or 0\n")
i_raise = src.find("CLIP_TOO_LONG: source is", i_probe)
i_client = src.find("_get_genai_client()  # ensures client is ready", i_probe)
i_pool = src.find("mega_pool = concurrent.futures.ThreadPoolExecutor", i_probe)
check("cap fires right after the duration probe", 0 < i_probe < i_raise < i_probe + 1600)
check("cap fires BEFORE the Gemini client init (pre-spend)", i_raise < i_client)
check("cap fires BEFORE the mega-parallel pool (pre-spend)", i_raise < i_pool)
m = re.search(r'if mode == "full" and source_duration > _MAX_SOURCE_DURATION_S:', src)
check("FRESH INTAKE ONLY gate; fail-open on probe=0", m is not None)

print("\n=== C6: the gate logic, executed ===")
def gate(mode, dur, cap=H._MAX_SOURCE_DURATION_S):
    return mode == "full" and dur > cap
check("under-cap full job proceeds", gate("full", 110.4) is False)
check("at-cap job proceeds (boundary inclusive)", gate("full", H._MAX_SOURCE_DURATION_S) is False)
check("over-cap FRESH job rejects", gate("full", 149.9) is True)
check("re-edit rails exempt — over-cap guided_redraft still delivers (pre-cap videos stay re-editable)",
      gate("guided_redraft", 149.9) is False)
check("re-edit rails exempt — over-cap reinterpret still delivers", gate("reinterpret", 149.9) is False)
check("render_only replay never rejects", gate("render_only", 149.9) is False)
check("failed probe (0.0) proceeds — fail-open", gate("full", 0.0) is False)

print("\n=== C7: classify precedence — no greedy class absorbs the sentinel ===")
raw = ("CLIP_TOO_LONG: source is 149.9s; the intake cap is 120s "
       "(boundary-probed editorial-path limit).")
check("sentinel wins over generic classes", H.classify_error(RuntimeError(raw))["error_code"] == "CLIP_TOO_LONG")

print(f"\n{'='*60}\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
