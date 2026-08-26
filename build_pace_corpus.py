#!/usr/bin/env python3
"""THE PACE CORPUS — sources that HAVE content a lean edit would cut.

WHY THIS IS BUILT BEFORE THE PASS (owner ruling 2026-08-20). Two corpora in this
campaign were measured against sources that could not trigger the thing being
measured — the scene corpus scored EvidenceCard on footage selected for having
no visual proof, and the first grading of the evidence corpus used one frame per
source and misgraded half of it. An arm run on sources with nothing to cut
returns zero and teaches nothing, and a zero from a vacuous corpus is
indistinguishable from a refusal.

THE POPULATION, MEASURED FIRST (179 usable transcripts, 159 distinct users):

    WORDS   median  64   p75 136   p90 210   max 389
    SECONDS median  27   p75  53   p90  88   max 175

    >=150 words:  41 (22.9%)  latin 22  users 33
    >=250 words:   9 ( 5.0%)  latin  5  users  5

READ THAT BEFORE BELIEVING ANY RESULT FROM THIS CORPUS: the MEDIAN user video is
27 seconds and 64 words. There is almost nothing to cut for pace in 27 seconds.
Pace cutting is relevant to roughly the top quartile of traffic — it does not
improve the median video, and this corpus is deliberately built from the tail.

SELECTION
  1. >=150 words          enough content that a cut is even possible
  2. Latin script         so GROUND TRUTH can be marked by READING. Not a claim
                          that redundancy is a Latin-script property — it is an
                          honest limit on what I can judge. Non-Latin sources
                          are recorded as `unjudged`, never as `no redundancy`.
  3. one source per user  five videos from one creator is one opinion measured
                          five times (Rule 7)

MECHANICAL SIGNALS ARE A RANKING, NOT A VERDICT. Repeated n-grams and lexical
repetition SUGGEST redundancy; they cannot tell a deliberate rhetorical callback
from a point made twice by accident. Every candidate is emitted with
`cuttable: UNCONFIRMED` and the transcript text, and a human marks the spans.

GROUND TRUTH IS THE POINT. This corpus records WHERE a human would cut, so the
arm is falsifiable: did the model find the cut a person found? Without that, the
arm can only report a count, and a count cannot be right or wrong.

    python3 build_pace_corpus.py --limit 8
"""
import argparse
import collections
import json
import os
import re
import sys
import urllib.request

OUT = "pace_corpus_manifest.json"


def _creds():
    env = {}
    with open(os.path.expanduser("~/content-studio/.env.local")) as fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return (env["SUPABASE_URL"].rstrip("/"),
            env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY"))


def _q(url, key, path, t=180):
    r = urllib.request.Request(f"{url}/rest/v1/{path}",
                               headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(r, timeout=t) as x:
        return json.loads(x.read().decode())


def _words(tr):
    if isinstance(tr, str):
        try:
            tr = json.loads(tr)
        except Exception:
            return []
    w = tr.get("words") if isinstance(tr, dict) else tr
    return w if isinstance(w, list) else []


def _signals(toks):
    """Ranking signals only. Named so nobody mistakes them for a verdict."""
    low = [re.sub(r"[^\w']", "", t.lower()) for t in toks]
    low = [t for t in low if t]
    n = len(low)
    if n < 20:
        return {}
    grams = collections.Counter(tuple(low[i:i + 4]) for i in range(n - 3))
    repeated4 = sum(c - 1 for c in grams.values() if c > 1)
    ttr = len(set(low)) / n
    # sentence-ish openers repeated: a cheap "said it twice" tell
    opens = collections.Counter(tuple(low[i:i + 3]) for i in range(n - 2))
    return {
        "words": n,
        "repeated_4gram_hits": repeated4,
        "repeated_4gram_rate": round(repeated4 / max(1, n - 3), 4),
        "type_token_ratio": round(ttr, 3),
        "top_repeated_3gram": (" ".join(opens.most_common(1)[0][0])
                               if opens and opens.most_common(1)[0][1] > 1 else None),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--min-words", type=int, default=150)
    ap.add_argument("--scan", type=int, default=400)
    a = ap.parse_args()
    url, key = _creds()
    rows = _q(url, key,
              "video_jobs?select=id,user_id,created_at,video_url,source_duration,"
              f"transcript,vibe_input&status=eq.completed&transcript=not.is.null"
              f"&order=created_at.desc&limit={a.scan}")

    seen, cands, unjudged = set(), [], 0
    for r in rows:
        w = _words(r.get("transcript"))
        toks = [str(x.get("word") or "") for x in w if isinstance(x, dict)]
        if len(toks) < a.min_words:
            continue
        txt = " ".join(toks)
        tot = sum(ch.isalpha() for ch in txt)
        latin = sum(ch.isascii() and ch.isalpha() for ch in txt)
        if not tot or latin / tot <= 0.8:
            unjudged += 1          # RECORDED, never counted as "no redundancy"
            continue
        if r.get("user_id") in seen:
            continue
        seen.add(r.get("user_id"))
        dur = float(r.get("source_duration") or 0) or float(w[-1].get("end") or 0)
        cands.append({
            "id": r["id"], "video_url": r.get("video_url"),
            "duration_s": round(dur, 1),
            "vibe": (r.get("vibe_input") or "Make it viral")[:300],
            "signals": _signals(toks),
            "transcript_text": txt,
            # THE HONEST FIELDS — nothing has read this yet.
            "cuttable": "UNCONFIRMED",
            "ground_truth_spans": [],
        })

    cands.sort(key=lambda c: (-(c["signals"].get("repeated_4gram_rate") or 0),
                              c["signals"].get("type_token_ratio") or 1))
    cands = cands[:a.limit]
    man = {
        "purpose": "sources with enough CONTENT that a pace cut is possible, "
                   "with human-marked ground truth for where a lean edit cuts",
        "population_note": ("median user video is 27s / 64 words; only 22.9% reach "
                            "150 words. Pace cutting does NOT improve the median "
                            "video — this corpus is deliberately the tail."),
        "criteria": {"min_words": a.min_words, "latin_script_only": True,
                     "one_per_user": True,
                     "ranking": "repeated 4-grams + type-token ratio — A RANKING, "
                                "NOT A VERDICT"},
        "non_latin_skipped_unjudged": unjudged,
        "ground_truth": "UNMARKED — read transcript_text and fill "
                        "ground_truth_spans[{unit, verbatim, why}] before any arm",
        "sources": cands,
    }
    with open(OUT, "w") as fh:
        json.dump(man, fh, indent=1, ensure_ascii=False)
    print(f"  scanned {len(rows)}   candidates {len(cands)}   "
          f"non-latin skipped as UNJUDGED (not 'clean'): {unjudged}")
    for c in cands:
        s = c["signals"]
        print(f"    {c['id'][:8]}  {s.get('words'):4}w {c['duration_s']:6.1f}s  "
              f"rep4={s.get('repeated_4gram_rate')}  ttr={s.get('type_token_ratio')}  "
              f"top3={str(s.get('top_repeated_3gram'))[:28]}")
    print(f"\n  wrote {OUT} — ground truth is UNMARKED. Read the transcripts.")
    return 0 if cands else 1


if __name__ == "__main__":
    sys.exit(main())
