#!/usr/bin/env python3
"""THE WIDER FIELD — other people's videos, watched the same way.

Marked apify_field, never zac_reference. The synthesis is told which is which
and refuses to average them.

Signed URLs are minted HERE and the container fetches; the service-role key
stays on this machine. A URL is good for one hour, so the batch is chunked and
each chunk signs immediately before it runs — a 103-video run outlives a single
signature.
"""
import concurrent.futures as cf
import json
import os
import sys
import time
import urllib.request

import modal

ENV = "/Users/zaclibman/content-studio/.env.local"
BUCKET = "trend-videos"
OUT = "/tmp/craft_out_field"
os.makedirs(OUT, exist_ok=True)


def env():
    out = {}
    for line in open(ENV, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def sign(e, path, secs=7200):
    req = urllib.request.Request(
        f"{e['SUPABASE_URL']}/storage/v1/object/sign/{BUCKET}/{path}",
        data=json.dumps({"expiresIn": secs}).encode(),
        headers={"Authorization": f"Bearer {e['SUPABASE_SERVICE_ROLE_KEY']}",
                 "Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())
    return e["SUPABASE_URL"] + "/storage/v1" + r["signedURL"]


def rows(e):
    """EVERY trend video, not a flag-selected subset. `analyzed` was diagnosed
    FALSE on all 103 and selecting on it once silently ran the wrong cohort."""
    req = urllib.request.Request(
        f"{e['SUPABASE_URL']}/rest/v1/trend_videos?select=id,video_file_url",
        headers={"apikey": e["SUPABASE_SERVICE_ROLE_KEY"],
                 "Authorization": f"Bearer {e['SUPABASE_SERVICE_ROLE_KEY']}"})
    out, skipped = [], 0
    for r in json.loads(urllib.request.urlopen(req, timeout=60).read()):
        u = r.get("video_file_url") or ""
        if f"/{BUCKET}/" in u:
            out.append((r["id"], u.split(f"/{BUCKET}/", 1)[1]))
        else:
            skipped += 1
    if skipped:
        print(f"  *** {skipped} rows carry no {BUCKET} path — NOT analysed, "
              f"and not counted as absent by accident")
    return out


def measured(path):
    """A file on disk is not a result. Only MEASURED counts as done — a cached
    FAILED would be skipped forever and silently shrink the corpus the
    synthesis reads."""
    import json as _j
    import os as _o
    if not _o.path.exists(path):
        return False
    try:
        return _j.load(open(path))["state"] == "MEASURED"
    except Exception:                                             # noqa: BLE001
        return False


def main():
    limit = None
    for i, a in enumerate(sys.argv):
        if a == "--limit":
            limit = int(sys.argv[i + 1])
    e = env()
    todo = [(vid, path) for vid, path in rows(e)
            if not measured(f"{OUT}/{vid}.json")]
    if limit:
        todo = todo[:limit]
    print(f"PRICE STATED: {len(todo)} field videos through Gemini 2.5 Pro "
          f"video-in. At the reference rate (~$0.033/video measured on the "
          f"ten) this is ~${len(todo) * 0.033:.2f}. No GPU.")
    if not todo:
        print("  nothing to do")
        return 0

    fn = modal.Function.from_name("promptly-craft-pass", "analyse")

    def one(vid, path):
        u = sign(e, path)
        t0 = time.time()
        r = fn.remote(b"", vid, "apify_field", url=u)
        r["_client_wall_s"] = round(time.time() - t0, 1)
        r["storage_path"] = path
        json.dump(r, open(f"{OUT}/{vid}.json", "w"))
        return vid, r

    t0 = time.time()
    n_ok = 0
    CHUNK = 20                       # re-sign every chunk; URLs expire
    for c in range(0, len(todo), CHUNK):
        part = todo[c:c + CHUNK]
        with cf.ThreadPoolExecutor(max_workers=3) as ex:
            futs = [ex.submit(one, v, p) for v, p in part]
            for fut in cf.as_completed(futs):
                try:
                    vid, r = fut.result()
                except Exception as ex_:                          # noqa: BLE001
                    print(f"  *** CLIENT FAILED {type(ex_).__name__}: {ex_}")
                    continue
                n_ok += r["state"] == "MEASURED"
                print(f"  {r['state']:9s} {vid[:12]} {r['detail'][:56]:58s} "
                      f"{r['_client_wall_s']}s")
        print(f"  --- {c + len(part)}/{len(todo)} dispatched, {n_ok} MEASURED, "
              f"{time.time() - t0:.0f}s ---")

    states = {}
    for n in os.listdir(OUT):
        if n.endswith(".json"):
            states[n] = json.load(open(f"{OUT}/{n}"))["state"]
    ok = sum(1 for v in states.values() if v == "MEASURED")
    print(f"\n  {ok}/{len(states)} MEASURED (the synthesis reads {ok})")
    bad = {k: v for k, v in states.items() if v != "MEASURED"}
    for k, v in sorted(bad.items())[:20]:
        print(f"  *** NOT MEASURED: {k} -> {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
