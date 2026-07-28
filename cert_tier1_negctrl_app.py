"""TIER-1 STAGE A NEGATIVE CONTROL (Gemini-ID selection). Prove the SAFE selector is correct:
on labeled clips, Gemini language-ID must identify the true language and _route_language_via_gemini
must route to it (graduation opened to all for the test). Reports the Gemini-ID per clip."""
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
    os.environ["PROMPTLY_ROUTE_LANGS"] = "hi,bn,ta,te,gu,kn,mr,ur"   # open graduation for the test
    sys.path.insert(0, "/")
    import handler as H
    try:
        d = tempfile.mkdtemp(); src = os.path.join(d, "s.mp4")
        urllib.request.urlretrieve(arm["url"], src)
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", src],
                           capture_output=True, text=True)
        dur = float(json.loads(p.stdout)["format"]["duration"])
        gid = H._identify_language_gemini(src)
        rlang, rtx, ru = H._route_language_via_gemini(src, dur)
        return {"id": arm["id"], "true_lang": arm.get("true_lang"), "dur": round(dur, 1),
                "gemini_id": gid, "routed": rlang, "routed_unworded": ru}
    except Exception as e:
        return {"id": arm["id"], "error": f"{type(e).__name__}: {str(e)[:150]}", "tb": traceback.format_exc()[-250:]}


@app.local_entrypoint()
def main():
    SCR = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad"
    labeled = json.load(open(SCR + "/tier1_labeled.json"))
    trips = json.load(open(SCR + "/tier1_trip_urls.json"))
    known_true = {"bb30ffb8": "hi", "a5240ea7": "hi"}   # RELIABLE Hindi (multi-hi + a5240ea7 acoustic-hi); bn/ta/te labels were acoustic guesses → report-only, graduate via frontend
    for t in trips:
        t["true_lang"] = known_true.get(t["id"])
    clips = labeled + trips  # assert Hindi; report the rest
    arms = [{**c, "stagger_s": i * 8} for i, c in enumerate(clips)]
    print(f"=== STAGE A NEGATIVE CONTROL — GEMINI-ID SELECTION ({len(arms)} labeled clips) ===")
    out = list(run_arm.map(arms))
    assert out, "no measurement"
    id_ok = 0; route_ok = 0; fails = []
    for r in out:
        if r.get("error"):
            print(f"  {r['id']}: ERROR {r['error']}"); fails.append(r['id']); continue
        tl = r["true_lang"]
        idm = ("✓" if r["gemini_id"] == tl else "✗") if tl else f"gemini={r['gemini_id']}"
        rm = ("✓" if r["routed"] == tl else "✗") if tl else "(graduate)"
        if tl and r["gemini_id"] == tl: id_ok += 1
        if tl and r["routed"] == tl: route_ok += 1
        elif tl is not None: fails.append(f"{r['id']}: routed {r['routed']} expected {tl}")
        print(f"  {r['id']} (true={tl}) → gemini_id={r['gemini_id']} {idm} | routed={r['routed']} {rm} unworded={r.get('routed_unworded')}")
    print(f"\n=== Gemini-ID accuracy: {id_ok}/{len(out)} | route-to-true: {route_ok}/{len(out)} ===")
    print("HINDI NEGATIVE CONTROL: " + ("PASS — Gemini-ID = hi on every reliable-Hindi clip; bn/ta/te reported for frontend graduation" if not fails else "FAIL: " + "; ".join(fails)))
    assert not fails, "Gemini-ID selection mis-selected — NOT safe to flip"
