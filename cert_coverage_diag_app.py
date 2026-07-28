"""Coverage-gate over-fire diagnostic — is the trip from SCATTERED sub-0.7s word-gaps
(false positive: cutter never trims them, _MIDSENTENCE_STALL_S=0.70) or a FEW LARGE
contiguous untranscribed spans (genuine: the cutter deletes them wholesale)?

For each source: transcribe (multi) + VAD → contiguous unworded-SPEECH spans. Report the
span histogram + two metrics: the CURRENT gate sum (all bins) vs a CONTIGUOUS metric
(only spans >= a trim threshold). Boundary clips should show many tiny spans (deletable~0);
genuine clips should show few large spans (deletable~high)."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-coverage-diag", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]

SOURCES = [
    {"label": "BOUNDARY_10pct_A", "url": "https://d1iax8jos987n3.cloudfront.net/sources/0b958738-3378-4d11-bc80-f921a774b54b/1785196596030-0D2D6E0A-EB8A-42A5-AB5F-8E77DB1F8051_L0_001.mp4"},
    {"label": "GENUINE_62pct",    "url": "https://d1iax8jos987n3.cloudfront.net/sources/400e9c2f-83da-43fa-a299-00b3fb51475e/1785192532742-5706C3FE-1AD9-45D6-8011-C44F877454B9_L0_001.mp4"},
]


@app.function(secrets=SECRETS, cpu=8.0, memory=16384, timeout=1200)
def run_arm(arm: dict) -> dict:
    import time, uuid, tempfile, subprocess, traceback, urllib.request
    if arm.get("stagger_s"):
        time.sleep(float(arm["stagger_s"]))
    sys.path.insert(0, "/")
    import handler as H
    t0 = time.time()
    try:
        d = tempfile.mkdtemp()
        src = os.path.join(d, "src.mp4")
        urllib.request.urlretrieve(arm["url"], src)
        # duration
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", src], capture_output=True, text=True)
        dur = float(json.loads(p.stdout)["format"]["duration"])
        # transcribe (same path as the handler)
        tr = H.transcribe_audio(src, language="multi")
        words = (tr or {}).get("words") or []
        # VAD silence → speech complement
        silence = H._detect_silence_regions_vad(src, min_silence_s=0.30)
        sil = sorted((float(a), float(b)) for a, b in silence)
        wrd = sorted((float(w.get("start") or 0), max(float(w.get("end") or 0), float(w.get("start") or 0)))
                     for w in words if str(w.get("word") or w.get("punctuated_word") or "").strip())

        def _iniv(iv, t):
            for a, b in iv:
                if a - 1e-6 <= t <= b + 1e-6:
                    return True
                if a > t:
                    break
            return False

        BIN = 0.1
        nb = int(dur / BIN) + 1
        # mark each bin: speech-without-word
        flags = []
        speech = 0.0
        for i in range(nb):
            t = i * BIN + BIN / 2.0
            if _iniv(sil, t):
                flags.append(False); continue
            speech += BIN
            flags.append(not _iniv(wrd, t))
        # coalesce contiguous True runs into spans (durations)
        spans = []
        run = 0
        for f in flags:
            if f:
                run += 1
            elif run:
                spans.append(run * BIN); run = 0
        if run:
            spans.append(run * BIN)
        total_unwd = round(sum(spans), 1)
        # histogram by span size
        buckets = {"<0.7s": 0.0, "0.7-1.5s": 0.0, "1.5-3s": 0.0, ">=3s": 0.0}
        for s in spans:
            if s < 0.7: buckets["<0.7s"] += s
            elif s < 1.5: buckets["0.7-1.5s"] += s
            elif s < 3.0: buckets["1.5-3s"] += s
            else: buckets[">=3s"] += s
        buckets = {k: round(v, 1) for k, v in buckets.items()}
        deletable_07 = round(sum(s for s in spans if s >= 0.7), 1)
        deletable_15 = round(sum(s for s in spans if s >= 1.5), 1)
        return {"label": arm["label"], "dur": round(dur, 1), "words": len(words),
                "speech_s": round(speech, 1), "total_unworded_s": total_unwd,
                "current_frac": round(total_unwd / speech, 3) if speech else 0,
                "n_spans": len(spans), "largest_span_s": round(max(spans), 1) if spans else 0,
                "span_buckets_s": buckets,
                "deletable_ge0.7s": deletable_07, "deletable_ge1.5s": deletable_15,
                "deletable_frac_ge1.5": round(deletable_15 / speech, 3) if speech else 0,
                "wall_s": round(time.time() - t0, 1)}
    except Exception as e:
        return {"label": arm["label"], "error": f"{type(e).__name__}: {str(e)[:200]}",
                "tb": traceback.format_exc()[-500:], "wall_s": round(time.time() - t0, 1)}


@app.local_entrypoint()
def main():
    arms = [{**s, "stagger_s": i * 12} for i, s in enumerate(SOURCES)]
    print("=== COVERAGE OVER-FIRE DIAGNOSTIC (scattered gaps vs large contiguous spans) ===")
    out = list(run_arm.map(arms))
    assert out, "no measurement produced"
    for r in out:
        print(f"\n--- {r['label']} (wall {r.get('wall_s')}s) ---")
        if r.get("error"):
            print("  ERROR:", r["error"]); print("  tb:", r.get("tb")); continue
        print(f"  dur={r['dur']}s words={r['words']} speech={r['speech_s']}s")
        print(f"  CURRENT metric: total_unworded={r['total_unworded_s']}s frac={r['current_frac']} → "
              f"{'TRIP' if (r['total_unworded_s']>=2.0 and r['current_frac']>=0.10) else 'pass'}")
        print(f"  spans: n={r['n_spans']} largest={r['largest_span_s']}s buckets={r['span_buckets_s']}")
        print(f"  CONTIGUOUS metric: deletable(>=0.7s)={r['deletable_ge0.7s']}s "
              f"deletable(>=1.5s)={r['deletable_ge1.5s']}s frac={r['deletable_frac_ge1.5']}")
    print("\nREAD: boundary clip should be dominated by <0.7s spans (deletable~0 → false positive);")
    print("      genuine clip should be dominated by >=3s spans (deletable~high → correct reject).")
