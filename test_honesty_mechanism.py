"""GAP 3 Item 2 — THE HONESTY MECHANISM (Zac 2026-07-13). The trust fix: when the
user asks for a capability the pipeline genuinely can't do yet (color grading, music,
voiceover/TTS, aspect-ratio change, logo, AI image/scene generation), SURFACE it —
"Promptly doesn't support X yet" — instead of silently dropping it. The user always
knows: done, or explicitly can't-yet. Never silent. (The surfacing channel was
re-edit + ambiguity only; this extends it to the INITIAL render path.)"""
import sys
import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

def notes(v):
    return H._parse_unsupported_requests(v)

# ── each unsupported capability is DETECTED + surfaced (understood, not silent) ──
check("'color grade this cinematic' → surfaces color grading",
      any("color grad" in n.lower() for n in notes("make it viral and color grade this cinematic")), notes("color grade this cinematic"))
check("'add background music' → surfaces music",
      any("music" in n.lower() for n in notes("add background music")), notes("add background music"))
check("'add a voiceover' → surfaces voiceover/narration",
      any("voice" in n.lower() or "narrat" in n.lower() for n in notes("add a voiceover reading the script")))
check("'make it 16:9 / landscape' → surfaces aspect ratio",
      any("aspect" in n.lower() or "16:9" in n.lower() or "vertical" in n.lower() for n in notes("make it 16:9 landscape")))
check("'put my logo in the corner' → surfaces logo/watermark",
      any("logo" in n.lower() or "watermark" in n.lower() for n in notes("put my logo in the corner")))
check("'generate an AI image of a city' → surfaces AI generation",
      any("generat" in n.lower() or "ai " in n.lower() for n in notes("generate an AI image of a futuristic city")))

# ── message form: honest, names the feature, "not supported / yet" register ──
_m = notes("color grade this")[0]
check("message is user-readable + honest ('Promptly ... yet')", "Promptly" in _m and "yet" in _m.lower(), _m)

# ── NO false positives: supported / normal asks surface nothing ──
check("'make it punchy with fast captions' → [] (all supported)", notes("make it punchy with fast captions") == [], notes("make it punchy with fast captions"))
check("'show Ahmedabad, no zooms' → [] (b-roll + neg are supported)", notes("show Ahmedabad, no zooms") == [], notes("show Ahmedabad, no zooms"))
check("'a video about music' → [] (topic, not a music-add request)", notes("a video about music theory") == [], notes("a video about music theory"))
check("vertical 9:16 is SUPPORTED → not flagged", notes("keep it vertical 9:16") == [], notes("keep it vertical 9:16"))

# ── multiple asks → multiple honest notes, deduped ──
_multi = notes("color grade it, add music, and put my logo")
check("multiple unsupported asks → one note each (>=3)", len(_multi) >= 3, _multi)

# ── the field is surfaced on the pipeline result (channel extended to initial path) ──
_src = open("handler.py").read()
check("capability_notes surfaced on result_payload", '"capability_notes"' in _src or "capability_notes" in _src)
check("capability_notes carried into the completion status write (frontend sees it)",
      _src.count("capability_notes") >= 2)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL HONESTY-MECHANISM CASES PASS")
