"""WHEN DOES THE MODEL REACH FOR A CUTAWAY? Positives vs negatives, free.

Authoring is the b-roll bottleneck — 10 of 12 fixture runs author none, both
completed renders authored none, and delivered organic sits at 0.04/25s against
a reference 3.32/25s. Every downstream instrument this session built (Pexels
outcome, match floor, overlap drop) has near-zero throughput because almost
nothing enters the funnel.

So: what is different about the jobs that DO author?

THE PROMPT'S OWN THEORY, worth testing rather than assuming. It tells the model
to run a REFERENT MINE — "walk the kept transcript once and list every concrete
noun, visible scene, number, name, brand, quoted line, phone event, and story
turn" — and says "the concrete nouns named during build are the cutaway
candidates". If that is what drives authoring, the positives should be dialogue
DENSE IN DEPICTABLE REFERENTS, and length/shot-count should not separate them.

The fixture that authors is the Arabic real-estate source, whose keywords came
back as "modern residential buildings in jumeirah village circle dubai",
"dubai skyline downtown burj khalifa" — named places and concrete objects.

MEASURED PER JOB, positives = delivered >=1 b-roll:
    source_duration_s, output seconds, transcript words
    shot changes (proxy: cuts in the delivered recipe)
    PROPER NOUNS  — capitalised mid-sentence tokens, a crude named-entity proxy
    CONCRETE-NOUN RATE — a small depictable-noun lexicon per 100 words
Crude on purpose: a cheap separator that either shows a gap or does not.

  ./run_modal.sh probe_broll_authored_when_app.py --since 2026-08-27
"""
import os
import re
import statistics as st

import modal

app = modal.App("probe-broll-when")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]

DEPICTABLE = {
    "phone", "screen", "app", "car", "house", "home", "building", "office",
    "city", "street", "road", "door", "desk", "laptop", "computer", "camera",
    "food", "coffee", "water", "money", "cash", "card", "book", "gym", "beach",
    "kitchen", "room", "apartment", "shop", "store", "product", "box", "bag",
    "dog", "cat", "tree", "sky", "sun", "table", "chair", "window", "clothes",
    "shoes", "watch", "bike", "train", "plane", "boat", "hotel", "restaurant",
}


@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> list:
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    r = (sb.table("video_jobs").select("id,result,demo").gte("created_at", since)
         .eq("status", "completed").order("created_at", desc=True)
         .limit(600).execute())
    out = []
    for x in (r.data or []):
        if x.get("demo"):
            continue
        res = x.get("result") if isinstance(x.get("result"), dict) else {}
        if str(res.get("route") or "std-editorial") != "std-editorial":
            continue
        rc = res.get("edit_recipe")
        rc = rc.get("plan") if isinstance(rc, dict) and isinstance(rc.get("plan"), dict) else rc
        if not isinstance(rc, dict):
            continue
        cuts = [c for c in (rc.get("cuts") or []) if isinstance(c, dict)
                and isinstance(c.get("source_start"), (int, float))
                and isinstance(c.get("source_end"), (int, float))
                and c["source_end"] > c["source_start"]]
        if not cuts:
            continue
        tr = res.get("transcript")
        text = ""
        if isinstance(tr, dict):
            text = str(tr.get("text") or "")
        elif isinstance(tr, str):
            text = tr
        stt = res.get("stage_timings") if isinstance(res.get("stage_timings"), dict) else {}
        out.append({
            "id": x.get("id"),
            "broll": len(rc.get("broll_clips") or []),
            "out_s": sum((c["source_end"] - c["source_start"]) / (c.get("speed") or 1)
                         for c in cuts),
            "src_s": stt.get("source_duration_s"),
            "n_cuts": len(cuts),
            "text": text[:4000],
            "script": str((stt.get("lang_bundle") or {}).get("transcript_script") or "")
            if isinstance(stt.get("lang_bundle"), dict) else "",
        })
    return out


@app.local_entrypoint()
def main(since: str = "2026-08-27"):
    rows = scan.remote(since)
    for r in rows:
        # SCRIPT-AWARE. The first version counted [A-Za-z']+ — ASCII ONLY — so a
        # Telugu/Devanagari transcript scored ZERO words by construction
        # (5787785c: 0 by that count, 50 in truth). And the proper-noun proxy
        # used t[:1].isupper(), which is meaningless in scripts without case;
        # what it actually detected in the non-Latin positives was CODE-MIXED
        # ENGLISH ("film", "Astrology"), not named entities. 4 of 6 positives are
        # non-Latin, so both separators were artifacts.
        toks = r["text"].split()
        r["words"] = len(toks)                       # whitespace, script-neutral
        r["latin"] = sum(1 for t in toks if re.search(r"[A-Za-z]", t))
        r["latin_p100"] = 100.0 * r["latin"] / max(1, r["words"])
        # Capitalised Latin tokens mid-sentence — kept, but named honestly for
        # what it is: a CODE-MIX / Latin-caps proxy, not a named-entity count.
        r["caps"] = sum(1 for i, t in enumerate(toks)
                        if i > 0 and t[:1].isupper() and t[:1].isascii()
                        and not toks[i - 1].endswith((".", "!", "?")))
        r["caps_p100"] = 100.0 * r["caps"] / max(1, r["words"])
        r["depict"] = sum(1 for t in toks if t.lower().strip(".,!?") in DEPICTABLE)
        r["depict_p100"] = 100.0 * r["depict"] / max(1, r["words"])
        r["wps"] = r["words"] / max(1.0, r["out_s"])   # words per output second

    pos = [r for r in rows if r["broll"] >= 1]
    neg = [r for r in rows if r["broll"] == 0]
    print(f"\n=== WHEN IS B-ROLL AUTHORED — {len(rows)} std-editorial jobs ===")
    print(f"  positives (>=1 delivered b-roll): {len(pos)}")
    print(f"  negatives: {len(neg)}")
    if not pos:
        print("\n  NO POSITIVES — nothing to compare. Absent read, not a zero.")
        return

    def med(rs, k):
        v = [x[k] for x in rs if isinstance(x.get(k), (int, float))]
        return st.median(v) if v else None

    print(f"\n  {'':>18} {'POSITIVE':>9} {'NEGATIVE':>9}  separates?")
    for lbl, k in (("source_duration_s", "src_s"), ("output_s", "out_s"),
                   ("cuts in recipe", "n_cuts"), ("transcript words", "words"),
                   ("words/output_sec", "wps"),
                   ("latin tokens/100w", "latin_p100"),
                   ("caps-latin/100w", "caps_p100"),
                   ("depictable/100w (ASCII-only, unreliable)", "depict_p100")):
        a, b = med(pos, k), med(neg, k)
        if a is None or b is None:
            print(f"  {lbl:>18} {'—':>9} {'—':>9}")
            continue
        ratio = (a / b) if b else float("inf")
        sep = "YES" if (ratio >= 1.5 or ratio <= 0.67) else "no"
        print(f"  {lbl:>18} {a:>9.2f} {b:>9.2f}  {sep} ({ratio:.2f}x)")

    from collections import Counter
    print(f"\n  script: positives {dict(Counter(r['script'] for r in pos))}")
    print(f"          negatives {dict(Counter(r['script'] for r in neg).most_common(4))}")
    print(f"\n  THE POSITIVES:")
    for r in pos:
        print(f"    {r['id'][:8]}  broll={r['broll']}  {r['out_s']:.0f}s out  "
              f"{r['words']}w  {r['wps']:.2f}w/s  "
              f"latin/100w={r['latin_p100']:.0f}  caps/100w={r['caps_p100']:.1f}")
        print(f"      {r['text'][:150]!r}")
    print(f"\n  n={len(pos)} positives is THIN. A separator here is a lead to test,")
    print(f"  not a finding — and the fixture spec it implies must be validated")
    print(f"  by authoring b-roll before it is used to measure the overlap arm.")
