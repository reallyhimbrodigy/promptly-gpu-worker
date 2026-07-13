"""GAP 3 — PHENOMENAL b-roll fetch of named places (Zac 2026-07-13). The prompt
told Gemini an 'exact place' over-narrows into NONE (lumped with brand names + exact
times) → a named place was the ONE thing it was told NOT to search → silent speaker
hold. Backwards: a named real place/landmark is a PRECISE, high-value keyword with a
POPULATED stock pool (probe: Ahmedabad/Jaipur/Boise all return full 15-clip pools).

Fix: (1) the prompt distinguishes a NAMED real entity (emit it, high-value) from a
COMPOSITE over-specific subject (brand+time+surface, the real trap); (2) a positive
USER b-roll request ('show Ahmedabad', 'use footage of X') is a HARD obedience signal
that FORCES the fetch — the broad-subject default cannot suppress a user request."""
import sys
import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

# ── parse: positive user b-roll requests → named subjects ──
check("'show Ahmedabad' → ['Ahmedabad']", H._parse_broll_requests("show Ahmedabad") == ["Ahmedabad"],
      H._parse_broll_requests("show Ahmedabad"))
check("'use pictures of the Golden Gate Bridge' → the bridge",
      H._parse_broll_requests("use pictures of the Golden Gate Bridge") == ["the Golden Gate Bridge"],
      H._parse_broll_requests("use pictures of the Golden Gate Bridge"))
check("'add b-roll of Tokyo and Mumbai' → both",
      H._parse_broll_requests("add b-roll of Tokyo and Mumbai") == ["Tokyo", "Mumbai"],
      H._parse_broll_requests("add b-roll of Tokyo and Mumbai"))
check("'include footage of Times Square' → Times Square",
      H._parse_broll_requests("include footage of Times Square") == ["Times Square"],
      H._parse_broll_requests("include footage of Times Square"))
# ── no false positives ──
check("'make it punchy, no zooms' → [] (no b-roll ask)",
      H._parse_broll_requests("make it punchy, no zooms") == [], H._parse_broll_requests("make it punchy, no zooms"))
check("'no b-roll' → [] (a NEGATIVE is not a positive request)",
      H._parse_broll_requests("no b-roll") == [], H._parse_broll_requests("no b-roll"))
check("'show them how it works' → [] (verb phrase, not a subject)",
      H._parse_broll_requests("show them how it works") == [], H._parse_broll_requests("show them how it works"))

# ── directive: names the subjects, marks REQUIRED, OVERRIDES the broad default ──
_d = H._broll_request_directive("show Ahmedabad and use footage of Jaipur")
check("directive lists both subjects", "Ahmedabad" in _d and "Jaipur" in _d, _d)
check("directive marks them REQUIRED + overriding", "REQUIRED" in _d and "OVERRIDE" in _d.upper(), _d)
check("no request → empty directive (no injection)", H._broll_request_directive("make it viral") == "")

# ── prompt (belt): a NAMED real entity is now taught as high-value, distinct from composite ──
_src = open("handler.py").read()
check("prompt distinguishes a NAMED real place/entity as a PRECISE high-value keyword",
      "named real" in _src.lower() and "composite" in _src.lower())
check("the old 'an exact place' over-narrowing trap is reframed (not lumped with brand/time)",
      "an exact place" not in _src or "a NAMED real" in _src)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL BROLL-PLACE-FETCH CASES PASS")
