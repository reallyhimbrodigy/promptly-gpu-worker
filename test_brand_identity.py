"""GAP 2 — brand identity (Zac 2026-07-12). Promptly is ALWAYS Promptly; Gemini (or
any underlying model) must never appear in GENERATED on-screen text where it names
the product/itself (a real render leaked "AI model: Gemini"). _scrub_model_identity
replaces self-reference leaks with Promptly, leaving genuine content mentions."""
import sys
import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

# SELF-REFERENCE leaks → Promptly
check("'AI model: Gemini' → 'AI model: Promptly' (the real leak)",
      H._scrub_model_identity("AI model: Gemini") == "AI model: Promptly")
check("'edited by Gemini' → 'edited by Promptly'",
      H._scrub_model_identity("This was edited by Gemini") == "This was edited by Promptly")
check("'powered by Google' → 'powered by Promptly'",
      H._scrub_model_identity("powered by Google") == "powered by Promptly")
check("'the AI is Gemini' → Promptly",
      H._scrub_model_identity("the AI that made this is Gemini") == "the AI that made this is Promptly")

# CONTENT mentions (no identity frame) → untouched
check("content mention 'Google's new Pixel phone' is KEPT (not self-reference)",
      H._scrub_model_identity("Google's new Pixel phone review") == "Google's new Pixel phone review")
check("'my trip to Ahmedabad' untouched (no model name)",
      H._scrub_model_identity("my trip to Ahmedabad") == "my trip to Ahmedabad")

# nested overlay/MG structures scrub only the self-reference field
_n = H._scrub_model_identity({"title": "powered by Gemini", "label": "Google Pixel", "value": 100})
check("nested: identity title scrubbed, content label kept, non-string kept",
      _n == {"title": "powered by Promptly", "label": "Google Pixel", "value": 100}, _n)
check("list scrub", H._scrub_model_identity(["AI model: Gemini", "hello"]) == ["AI model: Promptly", "hello"])
check("non-string passthrough", H._scrub_model_identity(42) == 42)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL BRAND-IDENTITY CASES PASS")
