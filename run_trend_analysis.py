#!/usr/bin/env python3
"""Drive the trend re-annotation: sign, analyse on Vertex, write back.

SUPABASE CREDENTIALS STAY HERE. The container gets a signed URL and the prompt
and nothing else — the bucket is PRIVATE and stays private, and no new secret
enters the image for a job the gemini-vertex secret already covers.

ORDER, and it is not negotiable: ONE video first. If its schema does not carry
all twelve stored keys the comparison against the 2026-03-16 rows is
meaningless, and there is no point spending on 103.

  python3 run_trend_analysis.py --one          verify the path end to end
  python3 run_trend_analysis.py --the-19       the overlap, for the agreement number
  python3 run_trend_analysis.py --the-84       the rest
"""
import json
import os
import sys
import urllib.request

ENV = "/Users/zaclibman/content-studio/.env.local"
BUCKET = "trend-videos"
WANT = {"cuts", "hook", "audio", "broll", "speed", "ending", "transitions",
        "text_on_screen", "color_and_grade", "overall_production",
        "framing_and_movement", "video_duration_seconds"}


def env():
    out = {}
    for line in open(ENV, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def sign(e, path, secs=3600):
    req = urllib.request.Request(
        f"{e['SUPABASE_URL']}/storage/v1/object/sign/{BUCKET}/{path}",
        data=json.dumps({"expiresIn": secs}).encode(),
        headers={"Authorization": f"Bearer {e['SUPABASE_SERVICE_ROLE_KEY']}",
                 "Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())
    return e["SUPABASE_URL"] + "/storage/v1" + r["signedURL"]


def rows(e, which):
    """(id, storage_path) for the requested cohort, from the DB."""
    q = {"the-19": "select=id,video_file_url&analyzed=eq.true",
         "the-84": "select=id,video_file_url",
         "one": "select=id,video_file_url&limit=1"}[which]
    req = urllib.request.Request(
        f"{e['SUPABASE_URL']}/rest/v1/trend_videos?{q}",
        headers={"apikey": e["SUPABASE_SERVICE_ROLE_KEY"],
                 "Authorization": f"Bearer {e['SUPABASE_SERVICE_ROLE_KEY']}"})
    out = []
    for r in json.loads(urllib.request.urlopen(req, timeout=60).read()):
        u = r.get("video_file_url") or ""
        if f"/{BUCKET}/" in u:
            out.append((r["id"], u.split(f"/{BUCKET}/", 1)[1]))
    return out


def main():
    which = ("one" if "--one" in sys.argv else
             "the-19" if "--the-19" in sys.argv else
             "the-84" if "--the-84" in sys.argv else None)
    if which is None:
        sys.stderr.write(__doc__)
        return 2
    e = env()
    todo = rows(e, which)
    print(f"  cohort {which}: {len(todo)} video(s)")
    if not todo:
        print("  nothing to do — refusing to report success on an empty set")
        return 1
    import modal
    fn = modal.Function.from_name("promptly-trend-analysis", "analyse")
    ok = bad = 0
    for vid, path in todo:
        url = sign(e, path)
        r = fn.remote(url, vid)
        st = r.get("state")
        if st == "MEASURED":
            missing = WANT - set(r.get("analysis") or {})
            if missing:
                print(f"  {vid[:8]} SCHEMA MISMATCH missing={sorted(missing)}")
                bad += 1
                continue
            ok += 1
            print(f"  {vid[:8]} MEASURED  {r.get('wall_s')}s  {r.get('detail')}")
            if which != "one":
                open(f"/tmp/trend_new_{vid}.json", "w").write(
                    json.dumps(r["analysis"]))
        else:
            bad += 1
            print(f"  {vid[:8]} {st}  {r.get('detail')}")
    print(f"\n  MEASURED {ok}   NOT-MEASURED {bad}   of {len(todo)}")
    return 0 if ok and not bad else 1


if __name__ == "__main__":
    sys.exit(main())
