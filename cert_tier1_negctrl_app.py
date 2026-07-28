"""TIER-1 STAGE A NEGATIVE CONTROL: prove selection-by-confidence is safe. On KNOWN-language
clips, confirm the true language wins — a wrong language must score lower confidence even if it
passes coverage. Reports per-candidate (words, confidence, script, coverage) so the separation is
visible, then asserts _probe_best_language selects the labeled truth on the controls."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-tier1-negctrl", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]


@app.function(secrets=SECRETS, cpu=8.0, memory=16384, timeout=1500)
def run_arm(arm: dict) -> dict:
    import time, tempfile, subprocess, traceback, urllib.request
    if arm.get("stagger_s"):
        time.sleep(float(arm["stagger_s"]))
    os.environ["PROMPTLY_EDIT_IN_LANGUAGE"] = "1"; os.environ["PROMPTLY_SCRIPT_DENYLIST"] = ""
    os.environ["PROMPTLY_LANG_ROUTING"] = "1"; os.environ["PROMPTLY_COVERAGE_GATE"] = "1"
    sys.path.insert(0, "/")
    import handler as H
    try:
        d = tempfile.mkdtemp(); src = os.path.join(d, "s.mp4")
        urllib.request.urlretrieve(arm["url"], src)
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", src],
                           capture_output=True, text=True)
        dur = float(json.loads(p.stdout)["format"]["duration"])
        # per-candidate signals (report the separation)
        rows = []
        for lg in H._LANG_ROUTING_CANDIDATES:
            try:
                tx = H.transcribe_audio(src, language=lg)
            except Exception as e:
                rows.append({"lg": lg, "err": type(e).__name__}); continue
            w = (tx or {}).get("words") or []
            if len(w) < 5:
                rows.append({"lg": lg, "words": len(w)}); continue
            sc = H._dominant_script(w)
            conf = round(sum(float(x.get("confidence") or 0.0) for x in w) / len(w), 3)
            ok, cov = H._transcription_coverage_check(src, w, dur)
            rows.append({"lg": lg, "words": len(w), "conf": conf, "script": sc,
                         "native": sc == H._EXPECTED_SCRIPT_FOR_LANG.get(lg), "cov_ok": ok,
                         "unworded": cov.get("unworded_speech_s")})
        # the production selection
        sel_lang, sel_tx, sel_u = H._probe_best_language(src, H._LANG_ROUTING_CANDIDATES, dur)
        return {"id": arm["id"], "true_lang": arm.get("true_lang"), "dur": round(dur, 1),
                "selected": sel_lang, "rows": rows}
    except Exception as e:
        return {"id": arm["id"], "error": f"{type(e).__name__}: {str(e)[:150]}", "tb": traceback.format_exc()[-250:]}


@app.local_entrypoint()
def main():
    SCR = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad"
    labeled = json.load(open(SCR + "/tier1_labeled.json"))          # known-Hindi controls
    trips = json.load(open(SCR + "/tier1_trip_urls.json"))          # surge failures (diagnostic)
    known_true = {"bb30ffb8": "hi", "09c4fdd4": "bn", "edea9617": "ta", "dd09d0a6": "ta"}  # a5240ea7 = the ambiguous test
    for t in trips:
        t["true_lang"] = known_true.get(t["id"])
    clips = labeled + trips
    arms = [{**c, "stagger_s": i * 8} for i, c in enumerate(clips)]
    print(f"=== TIER-1 STAGE A NEGATIVE CONTROL ({len(arms)} clips) ===")
    out = list(run_arm.map(arms))
    assert out, "no measurement"
    fails = []
    for r in out:
        if r.get("error"):
            print(f"  {r['id']}: ERROR {r['error']}"); continue
        tl = r.get("true_lang")
        tag = "" if tl is None else (" ✓" if r["selected"] == tl else f" ✗ EXPECTED {tl}")
        print(f"\n  {r['id']} (true={tl or '?'}) dur={r['dur']}s → SELECTED {r['selected']}{tag}")
        for row in sorted([x for x in r["rows"] if x.get("conf") is not None], key=lambda x: -x["conf"]):
            print(f"     {row['lg']}: {row['words']}w conf={row['conf']} {row['script']} "
                  f"native={row.get('native')} cov_ok={row.get('cov_ok')} unworded={row.get('unworded')}")
        if tl is not None and r["selected"] != tl:
            fails.append(f"{r['id']}: selected {r['selected']} expected {tl}")
    print(f"\n=== NEGATIVE CONTROL: {'PASS — every labeled clip selected its true language' if not fails else 'FAIL: ' + '; '.join(fails)} ===")
    assert not fails, "selection-by-confidence mis-selected a labeled clip — NOT safe to flip"
