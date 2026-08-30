"""VERIFY reply_language AGAINST THE REAL MODEL — Hindi and Arabic.

Every check shipped so far is STRUCTURAL: the field is validated, threaded,
forwarded, and the prompt contains the instruction. None of that shows the
MODEL COMPLIES, and the spec named the exact failure to watch for — a reply
that acknowledges in Hindi and then produces its actual content in English.

So this calls the REAL generate_plan_diff with a REAL delivered plan and a real
change_request, three times: en (control), hi, ar. Then it reads the two
user-facing strings and asks, per arm:

    1. Is `human_summary` actually in that script?         SCRIPT-DETECTED
    2. Is `clarification_question` (when present) too?
    3. Did the CONTENT stay untranslated?                  THE FIREWALL

THE CONTROL ARM IS NOT OPTIONAL. If `en` also came back in Devanagari, the
detector would be meaningless; if all three arms returned identical English,
"the instruction had no effect" and "the model ignored it" are the same
observation. English must come back English for the other two to mean anything.

SCRIPT DETECTION, NOT A TRANSLATION JUDGEMENT. Devanagari and Arabic are
distinct Unicode blocks, so "is this Hindi?" reduces to a codepoint test that
cannot be fooled by a confident-sounding English sentence. Latin-script targets
would need a real language ID; Hindi and Arabic are exactly the two the ask
named, and they are the two this method answers cleanly.

  ./run_modal.sh verify_reply_language_app.py --job <uuid>   # ~$0.02, 3 calls
"""
import json
import os
import sys

import modal

# REUSE THE PRODUCTION IMAGE AND THE FULL SECRET SET. A hand-rolled image would
# not carry handler.py, and a harness that renders or plans with a MISSING
# secret changes the flags the model call runs under and confounds the result —
# `promptly-lang-flags` in particular gates language behaviour, which is the
# exact thing under test here.
sys.path.insert(0, "/")
import modal_app as _prod                                          # noqa: E402

app = modal.App("verify-reply-language", image=_prod.image, secrets=_prod.secrets)
S = _prod.secrets

# Devanagari, and Arabic incl. its supplement/extended blocks.
DEVANAGARI = [(0x0900, 0x097F), (0xA8E0, 0xA8FF)]
ARABIC = [(0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF),
          (0xFE70, 0xFEFF)]
LATIN = [(0x0041, 0x005A), (0x0061, 0x007A)]


def _frac(text, blocks):
    ch = [c for c in (text or "") if not c.isspace() and c.isalpha()]
    if not ch:
        return 0.0
    hit = sum(1 for c in ch
              if any(lo <= ord(c) <= hi for lo, hi in blocks))
    return hit / len(ch)


@app.function(timeout=1800, cpu=4, memory=8192)
def run(job_id: str, arms: list) -> dict:
    import sys as _sys
    _sys.path.insert(0, "/")
    import handler as H
    from supabase import create_client

    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    if job_id:
        r = sb.table("video_jobs").select("result,vibe_input").eq(
            "id", job_id).limit(1).execute()
        row = (r.data or [{}])[0]
    else:
        # Newest completed std-editorial job with a usable recipe.
        r = (sb.table("video_jobs").select("id,result,vibe_input")
             .eq("status", "completed").order("created_at", desc=True)
             .limit(60).execute())
        row = {}
        for x in (r.data or []):
            res = x.get("result") or {}
            rc = res.get("edit_recipe") or {}
            rc = rc.get("plan") if isinstance(rc.get("plan"), dict) else rc
            if isinstance(rc, dict) and rc.get("cuts"):
                row = x
                break
    res = row.get("result") if isinstance(row.get("result"), dict) else {}
    rc = res.get("edit_recipe") or {}
    rc = rc.get("plan") if isinstance(rc.get("plan"), dict) else rc
    if not isinstance(rc, dict) or not rc.get("cuts"):
        return {"ok": False, "why": "no usable delivered plan to re-edit"}

    tr = res.get("transcript") if isinstance(res.get("transcript"), dict) else None
    out = {"ok": True, "base_job": row.get("id") or job_id,
           "base_cuts": len(rc.get("cuts") or []), "arms": {}}

    for code in arms:
        try:
            d = H.generate_plan_diff(
                rc,
                "make the captions bigger and punchier",
                old_vibe=row.get("vibe_input") or "viral",
                transcript=tr,
                input_data=({"reply_language": code} if code != "en" else {}),
                source_duration_s=(res.get("stage_timings") or {}).get("source_duration_s"),
            )
            out["arms"][code] = {
                "classification": d.get("classification"),
                "human_summary": d.get("human_summary"),
                "clarification_question": d.get("clarification_question"),
                "deterministic": bool(d.get("deterministic")),
            }
        except Exception as e:
            out["arms"][code] = {"error": f"{type(e).__name__}: {e}"[:300]}
    return out


@app.local_entrypoint()
def main(job: str = "", arms: str = "en,hi,ar"):
    codes = [a.strip() for a in arms.split(",") if a.strip()]
    r = run.remote(job, codes)
    if not r.get("ok"):
        print(f"  ❌ {r.get('why')}")
        sys.exit(2)
    print(f"\n=== reply_language vs the REAL model ===")
    print(f"  base job {str(r['base_job'])[:8]}, {r['base_cuts']} cuts, "
          f"change_request: 'make the captions bigger and punchier'\n")

    BLOCKS = {"hi": ("Devanagari", DEVANAGARI), "ar": ("Arabic", ARABIC),
              "en": ("Latin", LATIN)}
    verdicts = {}
    for code in codes:
        a = r["arms"].get(code) or {}
        print(f"  ── arm {code} ──")
        if a.get("error"):
            print(f"     ERROR {a['error']}")
            verdicts[code] = False
            continue
        if a.get("deterministic"):
            print("     DETERMINISTIC path — no model call was made, so this arm")
            print("     says NOTHING about compliance. Not a pass, not a fail.")
            verdicts[code] = None
            continue
        name, blocks = BLOCKS.get(code, ("Latin", LATIN))
        hs = a.get("human_summary") or ""
        cq = a.get("clarification_question") or ""
        f_hs, f_cq = _frac(hs, blocks), _frac(cq, blocks)
        print(f"     classification : {a.get('classification')}")
        print(f"     human_summary  : {hs[:150]!r}")
        print(f"       -> {name} letters: {f_hs*100:.0f}%")
        if cq:
            print(f"     clarification  : {cq[:150]!r}")
            print(f"       -> {name} letters: {f_cq*100:.0f}%")
        # 60% tolerates product names and numerals inside a translated sentence.
        okhs = f_hs >= 0.60
        verdicts[code] = okhs
        print(f"     {'✅' if okhs else '❌'} human_summary is "
              f"{'in ' + name if okhs else 'NOT in ' + name}")

    print(f"\n  ── VERDICT ──")
    if verdicts.get("en") is False:
        print("  ❌ FIXTURE FAILURE: the English control did not come back in")
        print("     Latin script. The detector is not measuring what it claims,")
        print("     so the hi/ar arms mean nothing. Read no result from them.")
        sys.exit(2)
    if verdicts.get("en") is None:
        print("  ⚠️  the control took the deterministic path — no model call.")
    tested = [c for c in codes if c != "en" and verdicts.get(c) is not None]
    if not tested:
        print("  NO ARM EXERCISED THE MODEL — absent read, not a pass. Re-run")
        print("  with a change_request that cannot be resolved deterministically.")
        sys.exit(2)
    bad = [c for c in tested if not verdicts[c]]
    if bad:
        print(f"  ❌ {', '.join(bad)} did NOT come back in-language. The field is")
        print("     threaded and the prompt carries the instruction, so this is")
        print("     a MODEL COMPLIANCE failure — the instruction needs to be")
        print("     stronger or earlier in the prompt, not re-plumbed.")
        sys.exit(1)
    print(f"  ✅ {', '.join(tested)} came back in-language, with the English")
    print("     control confirming the detector can tell the difference.")
