"""STANDING VIDEO-WATCH CUT: quality metrics BY LANGUAGE (Zac 2026-08-03).

An aggregate hides the population that is worst served, and that population is
most of the traffic — Hindi is ~51% of jobs that store a transcript. Every
quality line in the watch carries language as a first-class dimension from here.

    export $(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' \
        ~/content-studio/.env.local | xargs)
    python3 query_quality_by_language.py [limit]

Reports, per language:
  mid-word %   final cut lands strictly INSIDE a word -> the video stops
               mid-word. Was hi 34.0% vs en 7.7% (z=4.81) before 8360a93.
  keep-ratio   output duration / source duration. "We deleted half the video."
  word span    transcribed span / source duration — the COVERAGE that keep-ratio
               tracks. es measured 0.49, i.e. half the video had no words at all.

NOTE: transcript.detected_language is NULL on every row; language comes from the
modal per-word `language` tag. Only standard-editorial jobs store a transcript.
"""
import json
import os
import statistics as st
import sys
import urllib.request
from collections import Counter, defaultdict

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def fetch():
    q = ("/rest/v1/video_jobs?select=id,transcript,edit_recipe,result"
         f"&transcript=not.is.null&order=created_at.desc&limit={LIMIT}")
    r = urllib.request.Request(URL + q, headers={
        "apikey": KEY, "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(r, timeout=120) as f:
        return json.load(f)


def plan(job):
    er = job.get("edit_recipe") or {}
    p = er.get("plan") if isinstance(er.get("plan"), dict) else er
    return p if isinstance(p, dict) else {}


def main():
    G = defaultdict(lambda: dict(n=0, mid=0, midn=0, keep=[], cov=[], conf=[]))
    for job in fetch():
        t = job.get("transcript") or {}
        ws = [w for w in (t.get("words") or []) if isinstance(w, dict)] \
            if isinstance(t, dict) else []
        if not ws:
            continue
        lang = Counter(str(w.get("language")) for w in ws).most_common(1)[0][0]
        if lang == "None":
            continue
        g = G[lang]
        g["n"] += 1
        p = plan(job)
        cuts = p.get("cuts") or []
        stt = (job.get("result") or {}).get("stage_timings") or {}
        src = float(stt.get("source_duration_s") or 0)
        out = sum((float(c["source_end"]) - float(c["source_start"]))
                  / (float(c.get("speed") or 1) or 1)
                  for c in cuts
                  if float(c.get("source_end", 0)) > float(c.get("source_start", 0)))
        if out > 0 and src > 0:
            g["keep"].append(out / src)
            span = float(ws[-1].get("end") or 0) - float(ws[0].get("start") or 0)
            g["cov"].append(min(span / src, 1.0))
        g["conf"] += [float(w["confidence"]) for w in ws
                      if isinstance(w.get("confidence"), (int, float))]
        if cuts:
            e = max(float(c.get("source_end") or 0) for c in cuts)
            if e > 0:
                g["midn"] += 1
                if any(float(w["start"]) < e < float(w["end"]) for w in ws):
                    g["mid"] += 1

    hdr = (f"{'lang':<7}{'n':>5}{'mid-word %':>12}{'keep med':>10}"
           f"{'keep<0.5':>10}{'word span':>11}{'conf':>8}")
    print(hdr)
    print("-" * len(hdr))
    for lang, g in sorted(G.items(), key=lambda kv: -kv[1]["n"]):
        if g["n"] < 5:
            continue
        k = sorted(g["keep"])
        print(f"{lang:<7}{g['n']:>5}{g['mid'] * 100 / max(g['midn'], 1):>11.1f}%"
              f"{(st.median(k) if k else 0):>10.2f}"
              f"{(sum(1 for x in k if x < 0.5) * 100 // max(len(k), 1)):>9}%"
              f"{(st.median(g['cov']) if g['cov'] else 0):>11.2f}"
              f"{(st.median(g['conf']) if g['conf'] else 0):>8.3f}")


if __name__ == "__main__":
    main()
