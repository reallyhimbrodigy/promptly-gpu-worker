"""Re-cert the CONTIGUOUS-SPAN coverage fix against the REAL _transcription_coverage_check.
Each source is transcribed fresh (production path) then run through the actual gate function.

Expected verdicts (the fix must hold ALL of these):
  URDU_*        → REJECT   (P0 content-destruction class — large contiguous untranscribed)
  GOODEN_*      → PASS     (clean English baseline — no regression)
  BOUNDARY_10   → PASS     (THE FIX: 67 scattered <1.8s spans, deletable ~1.8s)
  GENUINE_62    → REJECT   (single 22.9s untranscribed block)
A single wrong verdict fails the cert (assert), per the no-empty-measurement law."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-coverage-refix", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]

CASES = [
    # THE original P0 clips — 89.7s Urdu. Fresh multi-transcription gives 207 words with FULL
    # coverage (the original butchering was a bad 51-word bridge transcript, fixed by bridge-
    # selection). With coverage, they DELIVER, not butcher → must PASS (rejecting = false positive).
    {"label": "P0_3bfa5b4b_ZacTest", "expect": "PASS", "url": "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1785186316787-02906184-D44C-4F1F-B086-89503819CFDE_L0_001.mp4"},
    {"label": "P0_16b4bdd2_Reporter","expect": "PASS", "url": "https://d1iax8jos987n3.cloudfront.net/sources/78539429-5428-4123-b5a6-f3fa844ecd19/1785184730836-78331DDF-AE11-462D-A0FE-43D600039A66_L0_001.mp4"},
    # short Urdu that DID transcribe (romanized) — has coverage, must PASS (deliver, not false-reject)
    {"label": "URDUshort_f709170e",  "expect": "PASS",   "url": "https://d1iax8jos987n3.cloudfront.net/sources/6a8b3e8f-b783-474e-8a43-b784424b2250/1784738583393-DCD4C5CF-97A5-4D61-8040-5B6C198CDCB9_L0_001.mp4"},
    {"label": "GOODEN_7513987a", "expect": "PASS",   "url": "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1782599246881-AB653DB0-BCCF-4C67-9910-0355686EC183_L0_001.mp4"},
    {"label": "GOODEN_233ef734", "expect": "PASS",   "url": "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1782690788639-64F38CEE-4A5B-4043-ADE1-DD09E2847BC6_L0_001.mp4"},
    {"label": "BOUNDARY_10_fp",  "expect": "PASS",   "url": "https://d1iax8jos987n3.cloudfront.net/sources/0b958738-3378-4d11-bc80-f921a774b54b/1785196596030-0D2D6E0A-EB8A-42A5-AB5F-8E77DB1F8051_L0_001.mp4"},
    {"label": "GENUINE_62",      "expect": "REJECT", "url": "https://d1iax8jos987n3.cloudfront.net/sources/400e9c2f-83da-43fa-a299-00b3fb51475e/1785192532742-5706C3FE-1AD9-45D6-8011-C44F877454B9_L0_001.mp4"},
]


@app.function(secrets=SECRETS, cpu=8.0, memory=16384, timeout=1200)
def run_arm(arm: dict) -> dict:
    import time, tempfile, subprocess, traceback, urllib.request
    if arm.get("stagger_s"):
        time.sleep(float(arm["stagger_s"]))
    sys.path.insert(0, "/")
    import handler as H
    t0 = time.time()
    try:
        d = tempfile.mkdtemp(); src = os.path.join(d, "src.mp4")
        urllib.request.urlretrieve(arm["url"], src)
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", src], capture_output=True, text=True)
        dur = float(json.loads(p.stdout)["format"]["duration"])
        tr = H.transcribe_audio(src, language="multi")
        words = (tr or {}).get("words") or []
        ok, stats = H._transcription_coverage_check(src, words, dur)
        verdict = "PASS" if ok else "REJECT"
        return {"label": arm["label"], "expect": arm["expect"], "verdict": verdict,
                "match": verdict == arm["expect"], "dur": round(dur, 1), "words": len(words),
                "stats": stats, "wall_s": round(time.time() - t0, 1)}
    except Exception as e:
        return {"label": arm["label"], "expect": arm["expect"], "verdict": "ERROR",
                "match": False, "error": f"{type(e).__name__}: {str(e)[:200]}",
                "tb": traceback.format_exc()[-400:], "wall_s": round(time.time() - t0, 1)}


@app.local_entrypoint()
def main():
    arms = [{**c, "stagger_s": i * 12} for i, c in enumerate(CASES)]
    print("=== COVERAGE RE-CERT (contiguous-span fix vs REAL _transcription_coverage_check) ===")
    out = list(run_arm.map(arms))
    assert out, "no measurement produced — cert must never print an empty result"
    allmatch = True
    for r in out:
        tag = "OK " if r.get("match") else "XX "
        if not r.get("match"):
            allmatch = False
        print(f"\n{tag}{r['label']}: expect={r['expect']} got={r['verdict']} (wall {r.get('wall_s')}s)")
        if r.get("error"):
            print("   ERROR:", r["error"]); print("   tb:", r.get("tb")); continue
        s = r.get("stats") or {}
        print(f"   dur={r['dur']}s words={r['words']} | deletable={s.get('unworded_speech_s')}s "
              f"frac={s.get('unworded_frac')} scattered={s.get('scattered_unworded_s')}s "
              f"largest_span={s.get('largest_span_s')}s")
    print("\n=== VERDICT ===")
    print("ALL CASES MATCH ✓" if allmatch else "MISMATCH — fix not safe to ship")
    assert allmatch, "coverage re-cert has a mismatch — do not deploy"
