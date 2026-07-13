"""PEXELS COVERAGE PROBE (Gap 3 diagnosis, Zac 2026-07-13). Is Pexels-video-only
enough for NAMED PLACE / landmark coverage, or is it thin? Probes the real API for
a spread of places — global landmarks, big cities, mid cities, and a deliberately
obscure one — and reports total + PORTRAIT-usable (h>w, h>=720) video counts, the
same filter fetch_broll_clip applies. Answers the build question with data.

  modal run pexels_coverage_probe.py
"""
import modal
try: from modal_app import image
except ModuleNotFoundError: image=None
app=modal.App("promptly-pexels-probe",image=image,
              secrets=[modal.Secret.from_name("promptly-secrets")])

PLACES=[
    # landmarks (should be rich)
    "Eiffel Tower","Times Square","Golden Gate Bridge","Sagrada Familia","Taj Mahal",
    # big global cities
    "Tokyo","Mumbai","Dubai","London",
    # the actual Video-2 request + Indian cities (the real test — non-Western named places)
    "Ahmedabad","Jaipur","Kolkata",
    # mid/obscure — where coverage likely thins
    "Boise Idaho","Ahmedabad street market","Ahmedabad old city",
]

@app.function(timeout=300)
def probe():
    import os, requests, json, concurrent.futures as cf
    key=os.environ.get("PEXELS_API_KEY")
    if not key: return json.dumps({"err":"no PEXELS_API_KEY"})
    def one(q):
        try:
            r=requests.get("https://api.pexels.com/videos/search",
                headers={"Authorization":key},
                params={"query":q,"per_page":15,"orientation":"portrait","size":"large"},timeout=25)
            r.raise_for_status()
            vids=r.json().get("videos") or []
        except Exception as e:
            return {"place":q,"err":str(e)[:120]}
        # apply fetch_broll_clip's portrait filter: h>w, h>=720
        portrait=0
        for v in vids:
            for f in (v.get("video_files") or []):
                h=f.get("height") or 0; w=f.get("width") or 0
                if h>w and h>=720:
                    portrait+=1; break
        # also probe LANDSCAPE (any orientation) to see if footage exists at all
        try:
            r2=requests.get("https://api.pexels.com/videos/search",
                headers={"Authorization":key},params={"query":q,"per_page":15,"size":"large"},timeout=25)
            any_total=len(r2.json().get("videos") or [])
        except Exception:
            any_total=-1
        return {"place":q,"portrait_usable":portrait,"portrait_returned":len(vids),"any_orientation_total":any_total}
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        rows=list(ex.map(one, PLACES))
    return json.dumps(rows)

@app.local_entrypoint()
def main():
    import json
    rows=json.loads(probe.remote())
    print("\n=== PEXELS PLACE COVERAGE (portrait_usable = passes fetch_broll_clip's h>w,h>=720 filter) ===")
    print(f"{'PLACE':<26}{'PORTRAIT_USABLE':>16}{'PORTRAIT_RET':>14}{'ANY_ORIENT':>12}")
    for r in rows:
        if r.get("err"): print(f"{r['place']:<26}  ERR: {r['err']}"); continue
        print(f"{r['place']:<26}{r['portrait_usable']:>16}{r['portrait_returned']:>14}{r['any_orientation_total']:>12}")
