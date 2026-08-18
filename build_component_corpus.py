#!/usr/bin/env python3
"""A CORPUS SELECTED FOR THE COMPONENT UNDER TEST. `[Rule 5, feedback_ab_durable_sources]`

WHY THIS EXISTS. Three corpora in a row were chosen on properties unrelated to
what was being measured, and every one of them would have read as a component
failure:

  REF-2            an already-EDITED video. The planner declined scenes and
                   brand copy with sound judgement ("already contains bespoke
                   3D motion graphics"). Refusing to decorate finished work is
                   GOOD, so a finished source cannot measure decoration.
  editorial_eng_*  raw, but NEITHER contains a spoken name or a stated number,
                   so brand_copy 0/4 was N/A — a planner emitting brand copy
                   there would be FABRICATING, which the directive forbids.
  golden/*         measured 2026-08-17: of 12 editorial goldens, brand_copy is
                   testable on ONE, scenes on ZERO, payoff on ZERO. The goldens
                   were selected for route/language coverage and they are
                   excellent at that; as a COMPONENT instrument they are closed.

A component with no trigger in the source is a CORRECT decline. Counting it as
a defect manufactures a signal out of nothing, and the fix is SELECTION, not
inspection after the fact.

DURABLE SOURCES, NOT USER MEDIA. Every entry is pinned by s3_key + sha256 +
etag + bytes in our own bucket, exactly like golden/manifest.json. An A/B run
on drifted bytes compares two different things.

    python3 build_component_corpus.py            # report what is selectable
    python3 build_component_corpus.py --write    # write the manifest
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request

from annotate_corpus_triggers import TRIGGERS

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = "/Users/zaclibman/content-studio/.env.local"
BUCKET = "thisismybucketagainwooo"
OUT = os.path.join(HERE, "component_corpus_manifest.json")
# Enough to separate a real decline from noise per component, small enough that
# a 2-arm plan-only matrix stays ~$0.20/cell * 2 * N.
TARGET_PER_COMPONENT = 6
# THE PRODUCT'S OWN BAND. The cap is 120s and the latency law is 90s end-to-end,
# so a 171s source measures a regime users do not have. Big files also cost real
# per-cell time for no extra signal.
MIN_DUR_S, MAX_DUR_S = 15.0, 90.0
MAX_BYTES = 150_000_000


def _creds():
    env = {}
    with open(ENV) as fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return env


def _q(env, path):
    k = env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY")
    r = urllib.request.Request(f"{env['SUPABASE_URL'].rstrip('/')}/rest/v1/{path}",
                               headers={"apikey": k, "Authorization": f"Bearer {k}"})
    return json.load(urllib.request.urlopen(r, timeout=300))


def _text(t):
    if isinstance(t, dict):
        return t.get("text") or ""
    if isinstance(t, list):
        return " ".join((s.get("text") or "") for s in t if isinstance(s, dict))
    return ""


def s3_key_of(video_url):
    """Same derivation golden/build_manifest.py uses."""
    m = re.search(r"(sources/[^?]+)", video_url or "")
    return m.group(1) if m else None


def head(key):
    r = subprocess.run(["aws", "s3api", "head-object", "--bucket", BUCKET, "--key", key],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        j = json.loads(r.stdout)
        return {"bytes": int(j.get("ContentLength") or 0),
                "etag": str(j.get("ETag") or "").strip('"')}
    except Exception:
        return None


def probe(path):
    """True duration + the audio level, because source_duration is 0.0 on every
    one of these rows and a corpus that lies about length mis-sizes every run."""
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
    dur = float(d) if d and d[0].isdigit() else 0.0
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "volumedetect",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", err)
    return dur, (float(m.group(1)) if m else None)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--limit", type=int, default=14, help="max sources to freeze")
    a = ap.parse_args(argv)
    env = _creds()

    REAL = "transcript=neq.%7B%7D&transcript=neq.%5B%5D&transcript=not.is.null"
    rows = []
    for page in range(4):
        r = _q(env, f"video_jobs?select=id,created_at,video_url,vibe_input,"
                    f"edit_recipe->>route,transcript&status=eq.completed&{REAL}"
                    f"&order=created_at.desc&limit=1000&offset={page*1000}")
        rows += r
        if len(r) < 1000:
            break

    # DEDUPE BY SOURCE, NOT BY JOB. Three rows in the raw pull carried identical
    # 156-word transcripts and identical triggers — one user re-running one
    # video. Counting them as three sources would triple-weight one opinion.
    seen, cand = {}, []
    for r in rows:
        tx = _text(r["transcript"])
        if len(tx.split()) < 15 or not r.get("video_url"):
            continue
        h = hashlib.sha256(tx.encode()).hexdigest()[:16]
        if h in seen:
            seen[h]["dupe_jobs"] += 1
            continue
        hits = {c: [lab for pat, lab in pats if re.search(pat, tx, re.I)]
                for c, pats in TRIGGERS.items()}
        if not any(hits.values()):
            continue
        e = {"job_id": r["id"], "created_at": r["created_at"][:10],
             "video_url": r["video_url"], "route": r["route"],
             "vibe": (r.get("vibe_input") or "")[:90],
             "words": len(tx.split()), "text_hash": h, "dupe_jobs": 0,
             "triggers": {k: v for k, v in hits.items() if v}}
        seen[h] = e
        cand.append(e)

    print(f"  deduped trigger-bearing sources: {len(cand)}  "
          f"(collapsed {sum(x['dupe_jobs'] for x in cand)} duplicate jobs)")
    for c in TRIGGERS:
        print(f"     can test {c:12}: {sum(1 for x in cand if x['triggers'].get(c)):3}")

    # SELECT: richest first, but guarantee per-component coverage so no component
    # is represented by a single source (the failure this file exists to end).
    def rich(x):
        return -sum(len(v) for v in x["triggers"].values())
    # SELECTION AND VETTING ARE ONE PASS. Choosing first and filtering after
    # closed the quota against sources that were then rejected for length or
    # size — 10 picked, 2 survived, and every component landed THIN. A candidate
    # only consumes its quota once it has actually passed every gate.
    need = {c: TARGET_PER_COMPONENT for c in TRIGGERS}
    print(f"\n  vetting richest-first; a source consumes quota only after it PASSES")

    frozen, _media_seen = [], {}
    for x in sorted(cand, key=rich):
        if len(frozen) >= a.limit or not any(v > 0 for v in need.values()):
            break
        if not any(need.get(c, 0) > 0 for c in x["triggers"]):
            continue   # every component it could serve is already satisfied
        k = s3_key_of(x["video_url"])
        if not k:
            print(f"    {x['job_id'][:8]} SKIP — video_url is not an s3 sources/ key")
            continue
        h = head(k)
        if not h:
            print(f"    {x['job_id'][:8]} SKIP — object missing from {BUCKET} (not durable)")
            continue
        p = f"/tmp/cc_{x['job_id'][:8]}.mp4"
        try:
            if not os.path.exists(p):
                urllib.request.urlretrieve(x["video_url"], p)
        except Exception as e:
            print(f"    {x['job_id'][:8]} SKIP — fetch failed {type(e).__name__}")
            continue
        sha = hashlib.sha256(open(p, "rb").read()).hexdigest()
        dur, db = probe(p)
        if dur <= 0:
            print(f"    {x['job_id'][:8]} SKIP — unprobeable duration")
            continue
        if not (MIN_DUR_S <= dur <= MAX_DUR_S):
            print(f"    {x['job_id'][:8]} SKIP — {dur:.1f}s outside the product band "
                  f"{MIN_DUR_S:.0f}-{MAX_DUR_S:.0f}s")
            continue
        if h["bytes"] > MAX_BYTES:
            print(f"    {x['job_id'][:8]} SKIP — {h['bytes']/1e6:.0f}MB over cap")
            continue
        # DEDUPE ON THE MEDIA, NOT THE TRANSCRIPT. Two ASR runs of ONE video
        # yield different transcript text and therefore different text hashes,
        # so the text-hash pass let an identical 47.4s/305MB source through
        # twice. The bytes are the identity.
        if sha in _media_seen:
            print(f"    {x['job_id'][:8]} SKIP — identical media to "
                  f"{_media_seen[sha][:8]} (sha256 match)")
            continue
        _media_seen[sha] = x["job_id"]
        labs = sorted({l for v in x["triggers"].values() for l in v})
        e = dict(x)
        e.update({"id": f"comp_{'_'.join(sorted(x['triggers']))[:24]}_{x['job_id'][:8]}",
                  "s3_key": k, "sha256": sha, "bytes": h["bytes"], "etag": h["etag"],
                  "duration_s": round(dur, 1), "mean_dbfs": db})
        frozen.append(e)
        for c in x["triggers"]:
            need[c] = max(0, need.get(c, 0) - 1)
        print(f"    {e['id'][:44]:46}{dur:6.1f}s {h['bytes']/1e6:6.1f}MB  {labs}")

    print(f"\n  FROZEN: {len(frozen)} sources, byte-pinned by sha256+etag in {BUCKET}")
    cov = {c: sum(1 for f in frozen if f["triggers"].get(c)) for c in TRIGGERS}
    print(f"  coverage: {cov}")
    thin = [c for c, n in cov.items() if n < 2]
    if thin:
        print(f"  THIN (<2 sources, a single source cannot separate decline from noise): {thin}")

    if a.write:
        json.dump({"built": "2026-08-17",
                   "why": "the goldens are closed as a component instrument: of 12 "
                          "editorial goldens, brand_copy is testable on 1, scenes on 0, "
                          "payoff on 0. Selection, not inspection.",
                   "selection": "deduped by transcript hash; >=1 directive trigger; "
                                "durable s3 source pinned by sha256+etag",
                   "trigger_patterns_mirror": "annotate_corpus_triggers.TRIGGERS, which "
                                              "mirrors the directives' own trigger language",
                   "coverage": cov, "sources": frozen}, open(OUT, "w"), indent=1, sort_keys=True)
        print(f"  WROTE {os.path.basename(OUT)}")
    else:
        print("  (report only — pass --write)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
