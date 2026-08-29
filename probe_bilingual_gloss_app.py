"""BILINGUAL GLOSS — re-measured under the REAL predicate, no monkeypatch.

WHY RE-MEASURED. The 0.57 / 0.50 figures came from the shattering probe, whose
whole output was an artifact: it split Indic words at combining marks on BOTH
sides so fragments matched fragments. Any number that probe produced is suspect,
including these.

THE HYPOTHESIS, stated so it can fail. A card like
    'வளர்ச்சி முறை\\n(Growth Pattern)'
carries NATIVE text plus an ENGLISH GLOSS. Under the real predicate the text
splits on whitespace into 4 tokens — 2 Tamil, 2 English. The Tamil half grounds
against a Tamil transcript; the English gloss cannot ground against it at all.
2/4 = 0.50, under the 0.60 bar, so a card whose MEANINGFUL half is fully
grounded is dropped by its own translation.

If true, the lever is not the predicate and not the threshold — it is that a
gloss is CHROME, and chrome should not be scored as content.

MEASURED THREE WAYS PER CARD, using H._mg_grounding_fraction unmodified:
    whole      — what production actually scores
    native     — only the non-ASCII tokens
    gloss      — only the ASCII tokens
A card is GLOSS-BLOCKED when native >= threshold but whole < threshold.

  ./run_modal.sh probe_bilingual_gloss_app.py --since 2026-08-27
"""
import os
import sys

sys.path.insert(0, "/")
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("probe-bilingual-gloss", image=image)
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

    def ascii_only(s):
        return all(ord(c) < 128 for c in s)

    def known_from(tr):
        # EXACTLY the production construction (_mg_known_sets' transcript leg).
        out = set()
        for raw in tr.split():
            subs = [t for t in re.split(r"[^0-9A-Za-z.]+", raw) if t]
            j = H._mg_norm_token(raw)
            for p in subs + ([j] if j else []):
                t = H._mg_norm_token(p)
                if t:
                    out.add(t)
        return out

    THR = H._MG_GROUNDING_THRESHOLD
    out = {"mixed": [], "n_drops": 0, "n_jobs": 0}
    for x in (r.data or []):
        if x.get("demo"):
            continue
        res = x.get("result") if isinstance(x.get("result"), dict) else {}
        _t = res.get("transcript")
        tr = str(_t.get("text") or "") if isinstance(_t, dict) else (
            _t if isinstance(_t, str) else "")
        if not tr.strip():
            continue
        try:
            body = s3.get_object(Bucket=bucket,
                                 Key=f"divergences/{x['id']}.jsonl")["Body"].read()
        except Exception:
            continue
        known = known_from(tr)
        got = False
        for line in body.decode("utf-8", "replace").split("\n"):
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("action") != "drop_ungrounded_text":
                continue
            text = str((ev.get("original") or {}).get("text") or "")
            if not text:
                continue
            got = True
            out["n_drops"] += 1
            words = text.split()
            nat = [w for w in words if not ascii_only(w)]
            glo = [w for w in words if ascii_only(w)]
            if not nat or not glo:
                continue          # not a bilingual card
            out["mixed"].append({
                "text": text[:64],
                "whole": round(H._mg_grounding_fraction(text, known), 2),
                "native": round(H._mg_grounding_fraction(" ".join(nat), known), 2),
                "gloss": round(H._mg_grounding_fraction(" ".join(glo), known), 2),
                "n_nat": len(nat), "n_glo": len(glo),
            })
        if got:
            out["n_jobs"] += 1
    out["thr"] = THR
    return out


@app.local_entrypoint()
def main(since: str = "2026-08-27"):
    d = run.remote(since)
    THR = d["thr"]
    mixed = d["mixed"]
    print(f"\n=== BILINGUAL GLOSS — real predicate, {d['n_drops']} drops "
          f"across {d['n_jobs']} jobs ===")
    print(f"  cards mixing native + ascii tokens: {len(mixed)}")
    if not mixed:
        print("\n  NONE. The bilingual-gloss lever does not exist in this window —")
        print("  an absent population, not a zero effect. Withdraw the item.")
        return
    print(f"\n  {'whole':>6} {'native':>7} {'gloss':>6}  {'n':>5}  text")
    blocked = 0
    for m in sorted(mixed, key=lambda z: -z["native"]):
        flag = ""
        if m["native"] >= THR and m["whole"] < THR:
            blocked += 1
            flag = "  <- GLOSS-BLOCKED"
        print(f"  {m['whole']:>6.2f} {m['native']:>7.2f} {m['gloss']:>6.2f}  "
              f"{m['n_nat']}+{m['n_glo']}  {m['text']!r}{flag}")
    print(f"\n  GLOSS-BLOCKED: {blocked}/{len(mixed)} mixed cards "
          f"({blocked} of {d['n_drops']} total drops = "
          f"{100.0*blocked/max(1,d['n_drops']):.1f}%)")
    print(f"\n  A card is GLOSS-BLOCKED when its NATIVE half grounds (>= {THR})")
    print(f"  but the whole text does not — i.e. the card is dropped by its own")
    print(f"  translation. If this count is 0 the lever is not real; if it is")
    print(f"  small, it is not worth a predicate change.")
