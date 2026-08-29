"""THE SPLITTER CHANGE, BOTH DIRECTIONS — recovery AND false-pass, simulated.

THE CANDIDATE. _mg_grounding_fraction splits card text on `[^0-9A-Za-z.]+` —
ASCII ONLY. Devanagari/Tamil/Arabic never sub-split, so they fall to
whole-string matching and any designer compression fails. That class is 30 of 56
real MG drops (53.6%), the largest single lever on MG density, and Hindi is 51%
of the transcript cohort.

WHY THIS IS NOT A ONE-LINE CHANGE. Making the splitter unicode-aware also lets
non-Latin card tokens reach the PREFIX rule, and Devanagari words are routinely
4+ characters, so the >=4 prefix gate that keeps English honest is nearly free to
clear in Devanagari. The abbreviation floor just shipped closes the
long-card-on-short-dialogue direction ('OFFICIAL' on 'off'); the splitter can
reopen an analogous one inside a script the floor was never calibrated against.

SO BOTH DIRECTIONS ARE MEASURED, against each job's OWN transcript:
  RECOVERY   — of the 30 non-Latin drops, how many ground under the new
               splitter? Those are cards the pipeline is losing today.
  FALSE-PASS — of the 13 ASCII genuinely-ungrounded drops, how many START
               passing? Those are cards that SHOULD drop and would ship.
               Expected 0 (ASCII tokenisation is unchanged), and measuring it is
               how that expectation stops being an assumption.

THE REAL PREDICATE IS USED, not a reimplementation: handler is imported and
_mg_grounding_fraction is called directly, with the splitter monkeypatched for
the variant arm. A reimplementation would drift from the thing being changed.

  ./run_modal.sh probe_splitter_falsepass_app.py --since 2026-08-27
"""
import os
import sys

sys.path.insert(0, "/")
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("probe-splitter-falsepass", image=image)
SECRETS = [modal.Secret.from_name(n) for n in (
    "promptly-secrets", "promptly-cloudfront", "gemini-vertex",
    "promptly-lang-flags", "promptly-elevenlabs")]


@app.function(secrets=SECRETS, cpu=8.0, memory=16384, timeout=1800)
def run(since: str) -> dict:
    import json
    import re
    import boto3
    from supabase import create_client
    sys.path.insert(0, "/")
    import handler as H

    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"

    r = (sb.table("video_jobs").select("id,result,demo").gte("created_at", since)
         .eq("status", "completed").order("created_at", desc=True).limit(600).execute())

    def is_ascii(s):
        return all(ord(c) < 128 for c in s)

    # THE VARIANT: unicode-aware token split. Everything else in the predicate is
    # untouched, so any delta is attributable to the splitter alone.
    _orig_fraction = H._mg_grounding_fraction

    def _fraction_unicode(text, known_tokens):
        content = []
        for raw in str(text).split():
            subs = [t for t in re.split(r"[^\w.]+", str(raw), flags=re.UNICODE) if t]
            joined = H._mg_norm_token(raw)
            pieces = subs if len(subs) > 1 else ([joined] if joined else [])
            for piece in pieces:
                tok = H._mg_norm_token(piece)
                if tok and tok not in H._MG_STOPWORDS:
                    content.append(tok)
        if not content:
            return 1.0
        hits = 0
        for tok in content:
            if any(ch.isdigit() for ch in tok):
                hits += 1
            elif H._mg_token_variants(tok) & known_tokens:
                hits += 1
            elif any((len(tok) >= getattr(H, "_MG_ABBREV_MIN_CHARS", 4)
                      and len(k) >= 4 and k.startswith(tok))
                     or (len(tok) >= 4 and len(k) >= 4 and tok.startswith(k))
                     for k in known_tokens):
                hits += 1
        return hits / len(content)

    THR = H._MG_GROUNDING_THRESHOLD
    out = {"recovery": [], "falsepass": [], "n_jobs": 0, "no_transcript": 0}
    for x in (r.data or []):
        if x.get("demo"):
            continue
        res = x.get("result") if isinstance(x.get("result"), dict) else {}
        # result.transcript is a DICT {text, words, utterances,
        # detected_language} — not a string. Reading it as a string filtered
        # every job and produced "0 jobs with drops", a clean zero that was a
        # reader bug, not a measurement.
        _tro = res.get("transcript")
        tr = ""
        if isinstance(_tro, dict):
            tr = str(_tro.get("text") or "")
            if not tr and isinstance(_tro.get("words"), list):
                tr = " ".join(str(w.get("word") or "") for w in _tro["words"]
                              if isinstance(w, dict))
        elif isinstance(_tro, str):
            tr = _tro
        if not tr.strip():
            out["no_transcript"] += 1
            continue
        try:
            body = s3.get_object(Bucket=bucket,
                                 Key=f"divergences/{x['id']}.jsonl")["Body"].read()
        except Exception:
            continue
        drops = []
        for line in body.decode("utf-8", "replace").split("\n"):
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("action") == "drop_ungrounded_text":
                o = ev.get("original") or {}
                t = str(o.get("text") or "")
                if t:
                    drops.append((str(o.get("type") or "?"), t))
        if not drops:
            continue
        out["n_jobs"] += 1
        # KNOWN SET from this job's own transcript, normalised the way the
        # predicate normalises. Approximates _mg_known_sets' kept-transcript leg;
        # vibe/identity are not in `result` so the set is a LOWER BOUND — which
        # makes the recovery number conservative and the false-pass number
        # conservative in the SAME direction (fewer hits, not more).
        known = set()
        for w in re.split(r"\s+", tr):
            for piece in re.split(r"[^\w.]+", w, flags=re.UNICODE):
                nt = H._mg_norm_token(piece)
                if nt:
                    known.add(nt)
        for typ, text in drops:
            cur = _orig_fraction(text, known)
            new = _fraction_unicode(text, known)
            toks = [p for p in re.split(r"[^\w]+", text, flags=re.UNICODE) if p]
            nonlatin = bool(toks) and not all(is_ascii(t) for t in toks)
            rec = {"type": typ, "text": text[:60], "cur": round(cur, 2),
                   "new": round(new, 2), "nonlatin": nonlatin}
            if nonlatin and cur < THR and new >= THR:
                out["recovery"].append(rec)
            elif nonlatin and cur < THR:
                out.setdefault("nonlatin_still_drops", []).append(rec)
            elif (not nonlatin) and cur < THR and new >= THR:
                out["falsepass"].append(rec)
    return out


@app.local_entrypoint()
def main(since: str = "2026-08-27"):
    d = run.remote(since)
    rec = d["recovery"]
    fp = d["falsepass"]
    still = d.get("nonlatin_still_drops", [])
    print(f"\n=== UNICODE SPLITTER — both directions, {d['n_jobs']} jobs with drops ===")
    print(f"\n  RECOVERY (non-Latin, currently dropped, would now ground): {len(rec)}")
    for x in rec[:16]:
        print(f"      {x['type']:>13}  {x['cur']:.2f} -> {x['new']:.2f}   {x['text']!r}")
    print(f"\n  NON-LATIN STILL DROPPING after the change: {len(still)}")
    for x in still[:10]:
        print(f"      {x['type']:>13}  {x['cur']:.2f} -> {x['new']:.2f}   {x['text']!r}")
    print(f"\n  FALSE-PASS (ascii, should drop, would now ship): {len(fp)}")
    for x in fp[:16]:
        print(f"      {x['type']:>13}  {x['cur']:.2f} -> {x['new']:.2f}   {x['text']!r}")
    if not fp:
        print("      NONE — ascii tokenisation is unchanged by the splitter, as")
        print("      expected. Measured rather than assumed.")
    _tot = len(rec) + len(still)
    print(f"\n  VERDICT")
    if _tot:
        print(f"      non-Latin recovery {len(rec)}/{_tot} = "
              f"{100.0*len(rec)/_tot:.0f}% of currently-dropped non-Latin cards")
    print(f"      false-pass cost: {len(fp)} card(s)")
    print(f"      A SCRIPT-AWARE THRESHOLD is only needed if recovery is high AND")
    print(f"      false-pass is non-zero. If false-pass is 0 the universal change")
    print(f"      is safe; if recovery is low the splitter is not the lever.")
