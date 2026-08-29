"""WHAT ARE THE 47% OF MGs FAILING ON? — and is drop_unsnapped a real coupling?

THE PREDICATE. _mg_grounding_fraction (handler.py:1508) scores card text against
the dialogue's known tokens; below _MG_GROUNDING_THRESHOLD = 0.6 the card is
dropped. A token grounds three ways:
    1. contains a digit                      -> always passes
    2. exact variant match against known
    3. TWO-WAY PREFIX, but only when
           len(tok) >= 4 AND min(len(k), len(tok)) >= 4

RULE 3 IS STRUCTURALLY UNAVAILABLE TO SHORT TOKENS. "YRS" is 3 characters, so it
can never prefix-match "years" no matter how obviously it abbreviates it — the
observed drop was literally `text " YRS" fails grounding`. The docstring's own
examples (MINS<->minutes, TEMP<->temperature, AUTO<->automatically) are ALL >=4,
so the floor was calibrated on cases that hide the failure. The 2-3 char display
abbreviation is exactly what a designer writes on a StatCard: YRS HRS MIN SEC
PCT AVG MAX KG LB FT MPH AM PM MO WK QTR.

If that class dominates, the biggest MG lever available is a threshold, not a
model change.

ALSO: shot_change_snap:drop_unsnapped ran lean 0.72 vs control 2.23 — 3x the MG
effect with no plausible mechanism connecting per-moment prose to shot snapping.
Either a real coupling or a confound in the arm split. Tested here by checking
whether the arms differ on things they CANNOT cause: source duration, word
count, language, route.

  ./run_modal.sh probe_mg_grounding_failures_app.py --since 2026-08-27
"""
import os
import re
import statistics as st
from collections import Counter

import modal

app = modal.App("probe-mg-grounding")
image = modal.Image.debian_slim().pip_install(["supabase", "boto3"])
S = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=S, timeout=1800)
def scan(since: str) -> list:
    import json
    import boto3
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    r = (sb.table("video_jobs").select("id,result,demo").gte("created_at", since)
         .eq("status", "completed").order("created_at", desc=True).limit(600).execute())
    out = []
    for x in (r.data or []):
        if x.get("demo"):
            continue
        res = x.get("result") if isinstance(x.get("result"), dict) else {}
        stt = res.get("stage_timings") if isinstance(res.get("stage_timings"), dict) else {}
        rec = {"id": x.get("id"), "arm": str(stt.get("lean_arm") or ""),
               "src_s": stt.get("source_duration_s"),
               "lang": str((stt.get("lang_bundle") or {}).get("transcript_script")
                           if isinstance(stt.get("lang_bundle"), dict) else ""),
               "detlang": str((stt.get("lang_bundle") or {}).get("detected_language")
                              if isinstance(stt.get("lang_bundle"), dict) else ""),
               "route": str(res.get("route") or "std-editorial"),
               "drops": [], "n_unsnap": 0, "words": None}
        tr = res.get("transcript")
        if isinstance(tr, str):
            rec["words"] = len(tr.split())
        try:
            body = s3.get_object(Bucket=bucket,
                                 Key=f"divergences/{rec['id']}.jsonl")["Body"].read()
            for line in body.decode("utf-8", "replace").split("\n"):
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("action") == "drop_ungrounded_text":
                    o = ev.get("original") or {}
                    rec["drops"].append({"type": str(o.get("type") or "?"),
                                         "text": str(o.get("text") or "")})
                elif ev.get("action") == "drop_unsnapped":
                    rec["n_unsnap"] += 1
        except Exception:
            pass
        out.append(rec)
    return out


@app.local_entrypoint()
def main(since: str = "2026-08-27"):
    rows = scan.remote(since)
    ab = [r for r in rows if r["arm"] in ("lean", "control")]
    drops = [d for r in ab for d in r["drops"]]
    print(f"\n=== MG GROUNDING FAILURES — {len(drops)} drops across {len(ab)} A/B jobs ===")
    if not drops:
        print("  none captured — absent read, not a zero.")
        return

    STOP = {"a", "an", "the", "of", "to", "in", "on", "for", "and", "or"}

    def content_toks(t):
        # UNICODE-AWARE, unlike the predicate. My first classifier split on
        # [^0-9A-Za-z.]+ — the SAME ASCII-only rule the predicate uses — so pure
        # Devanagari / Tamil / Arabic card text produced ZERO tokens and fell
        # into a bucket I then mislabelled "no readable text in the ledger".
        # The ledger records text at all three drop sites; the READER was blind
        # in exactly the way the thing it was measuring is blind.
        out = []
        for raw in str(t).split():
            for p in re.split(r"[^\w]+", raw, flags=re.UNICODE):
                p = p.strip(".").lower()
                if p and p not in STOP:
                    out.append(p)
        return out

    def is_ascii(tok):
        return all(ord(c) < 128 for c in tok)

    print(f"\n  [1] TRUE SPLIT — script first, then token length")
    buckets = Counter()
    shorts = Counter()
    for d in drops:
        toks = [t for t in content_toks(d["text"]) if not any(c.isdigit() for c in t)]
        if not toks:
            buckets["EMPTY / numeric-only text"] += 1
            continue
        if not all(is_ascii(t) for t in toks):
            # The PREDICATE splits on [^0-9A-Za-z.]+ too, so non-Latin never
            # sub-splits and can ground only by whole-string match.
            buckets["NON-LATIN text (splitter is ASCII-only)"] += 1
            continue
        m = min(len(t) for t in toks)
        if m <= 3:
            buckets["SHORT TOKEN <=3 chars (prefix rule unavailable)"] += 1
            for t in toks:
                if len(t) <= 3:
                    shorts[t] += 1
        else:
            buckets["GENUINELY UNGROUNDED (ascii, all >=4)"] += 1
    for k, n in buckets.most_common():
        print(f"      {n:>4}  ({100.0*n/len(drops):>5.1f}%)  {k}")

    print(f"\n  [2] THE SHORT TOKENS THEMSELVES")
    for t, n in shorts.most_common(18):
        print(f"      {n:>4}  {t!r}")

    print(f"\n  [3] BY COMPONENT")
    for t, n in Counter(d["type"] for d in drops).most_common(8):
        print(f"      {n:>4}  {t}")
    print(f"\n  [4] SAMPLE FAILING TEXTS")
    for d in drops[:14]:
        print(f"      {d['type']:>14}  {d['text']!r}")

    print(f"\n=== drop_unsnapped — real coupling or confound? ===")
    L = [r for r in ab if r["arm"] == "lean"]
    C = [r for r in ab if r["arm"] == "control"]
    print(f"  unsnap/job: lean {sum(r['n_unsnap'] for r in L)/len(L):.2f}  "
          f"control {sum(r['n_unsnap'] for r in C)/len(C):.2f}")
    print(f"\n  Things the arm CANNOT cause (a difference here means a confound):")
    for lbl, key in (("source_duration_s", "src_s"), ("transcript words", "words")):
        a = [r[key] for r in L if isinstance(r.get(key), (int, float))]
        b = [r[key] for r in C if isinstance(r.get(key), (int, float))]
        if a and b:
            print(f"      {lbl:>18}: lean median {st.median(a):.1f} (n={len(a)})   "
                  f"control {st.median(b):.1f} (n={len(b)})")
    print(f"      {'script':>18}: lean {dict(Counter(r['lang'] for r in L).most_common(4))}")
    print(f"      {'':>18}  control {dict(Counter(r['lang'] for r in C).most_common(4))}")
    print(f"      {'detected_language':>18}: {dict(Counter(r['detlang'] for r in ab).most_common(3))}")
