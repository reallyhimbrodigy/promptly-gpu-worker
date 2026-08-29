"""OUTCOME-GATE REJECT RATE ON ORGANIC TRAFFIC — and does it change the edit?

WHAT THE MARKER ACTUALLY IS. I logged "salvaged post-cuts plan" as a DEGRADE
marker and reported 10/18 runs as "rescued — a rescued plan is not the arm".
That was wrong twice over:

  1. The string fires from ONE site (handler.py:14838), the Phase-4 OUTCOME
     GATE, which runs on EVERY parsed plan — not only repaired ones. The word
     "salvaged" is hardcoded in the message regardless of whether anything was
     salvaged.
  2. PROMPTLY_OUTCOME_GATE defaults to "shadow", and shadow LEDGERS THE VERDICT
     AND CHANGES NOTHING. Only mode "enforce" turns the verdict into a retry.
     So no plan was rescued, nothing was degraded, and the paired arms were
     never contaminated.

WHAT IT REALLY MEASURES: the plan parsed as JSON but failed strict
`PostCutPlan.model_validate` — a required field missing, or a nested shape
broken — and SHIPPED ANYWAY, because downstream consumers read the dict
directly rather than through the pydantic model.

THREE QUESTIONS, one read:
  1. ORGANIC RATE. 56% came from three fixtures through PLAN_ONLY. If organic
     is materially lower the fixtures are unrepresentative; if comparable, every
     density number in this campaign describes a population where half the plans
     are off-contract.
  2. THE TAXONOMY. The divergence carries the pydantic error, so the failures
     can be counted by cause instead of guessed at.
  3. DOES IT CHANGE THE EDIT? Split delivered family mix by rejected vs clean.
     If the mixes match, the gate is noise on a decorative field. If rejected
     plans are thinner, the density numbers describe the fallback, not the brain.

  ./run_modal.sh probe_outcome_gate_app.py --since 2026-08-27
"""
import os
import statistics as st
from collections import Counter

import modal

app = modal.App("probe-outcome-gate")
image = modal.Image.debian_slim().pip_install(["supabase", "boto3"])
S = [modal.Secret.from_name("promptly-secrets")]

FAM = ("emphasis", "mg", "overlay", "transition", "tight_ovl", "sfx", "broll")


@app.function(image=image, secrets=S, timeout=1800)
def scan(since: str) -> dict:
    import json
    import boto3
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"

    rows, page, PAGE = [], 0, 500
    while True:
        r = (sb.table("video_jobs")
             .select("id,user_id,created_at,result,demo")
             .gte("created_at", since).eq("status", "completed")
             .order("created_at", desc=True)
             .range(page * PAGE, page * PAGE + PAGE - 1).execute())
        d = r.data or []
        rows.extend(d)
        if len(d) < PAGE:
            break
        page += 1
        if page > 10:
            break
    rows = [r for r in rows if not r.get("demo")]

    out = []
    for r in rows:
        jid = r.get("id")
        rec = {"id": jid, "ledger": None, "reject": None, "errs": []}
        try:
            body = s3.get_object(Bucket=bucket,
                                 Key=f"divergences/{jid}.jsonl")["Body"].read()
            rec["ledger"] = True
            n_rej = 0
            for line in body.decode("utf-8", "replace").split("\n"):
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if str(ev.get("action")) == "outcome_gate_reject":
                    n_rej += 1
                    rec["errs"].append(str(ev.get("reason") or "")[:400])
            rec["reject"] = n_rej > 0
        except Exception as e:
            rec["ledger"] = False
            rec["err"] = f"{type(e).__name__}"
        # family counts from the DELIVERED recipe
        res = r.get("result") if isinstance(r.get("result"), dict) else {}
        rc = res.get("edit_recipe")
        rc = rc.get("plan") if isinstance(rc, dict) and isinstance(rc.get("plan"), dict) else rc
        if isinstance(rc, dict):
            cuts = [c for c in (rc.get("cuts") or []) if isinstance(c, dict)
                    and isinstance(c.get("source_start"), (int, float))
                    and isinstance(c.get("source_end"), (int, float))
                    and c["source_end"] > c["source_start"]]
            outs = sum((c["source_end"] - c["source_start"]) / (c.get("speed") or 1)
                       for c in cuts)
            if cuts and outs > 0:
                rec["m"] = {
                    "out_s": outs,
                    "emphasis": sum(1 for c in cuts if c.get("_zoom_effect")),
                    "transition": sum(1 for c in cuts if c.get("transition_out")
                                      and c["transition_out"] != "none"),
                    "mg": len(rc.get("motion_graphics") or []),
                    "overlay": len(rc.get("text_overlays") or []),
                    "sfx": len(rc.get("sound_effects") or []),
                    "broll": len(rc.get("broll_clips") or []),
                    "tight_ovl": len(rc.get("tight_cut_overlays") or []),
                }
        out.append(rec)
    return {"rows": out, "since": since}


@app.local_entrypoint()
def main(since: str = "2026-08-27"):
    d = scan.remote(since)
    rows = d["rows"]
    have = [r for r in rows if r.get("ledger")]
    print(f"\n=== OUTCOME-GATE on organic traffic since {d['since']} ===")
    print(f"  {len(rows)} completions; {len(have)} with a readable divergence ledger")
    if not have:
        print("  NO LEDGERS READABLE — an absent read, not a zero.")
        return

    rej = [r for r in have if r.get("reject")]
    print(f"\n  [1] REJECT RATE: {len(rej)}/{len(have)} = "
          f"{100.0*len(rej)/len(have):.1f}%   (fixtures measured 56% at n=18)")

    print(f"\n  [2] FAILURE TAXONOMY (pydantic error head):")
    import re as _re
    _fields = Counter()
    for r in rej:
        for x in r["errs"]:
            # pydantic v2 renders "N validation errors for Model\nfield\n  msg"
            for _f in _re.findall(r"\n([A-Za-z_][\w.]*(?:\.\d+)?(?:\.[\w]+)*)\n", x):
                _fields[_f.split(".")[0]] += 1
    for e, n in _fields.most_common(12):
        print(f"      {n:>4}  {e}")
    print("\n      VERBATIM sample:")
    for x in (rej[0]["errs"][:1] if rej else []):
        for _ln in x.split("\n")[:14]:
            print(f"        {_ln[:110]}")

    print(f"\n  [3] DELIVERED FAMILY MIX — rejected vs clean")
    A = [r["m"] for r in have if r.get("reject") and r.get("m")]
    B = [r["m"] for r in have if not r.get("reject") and r.get("m")]
    print(f"      rejected n={len(A)}   clean n={len(B)}")
    if not A or not B:
        print("      one side is empty — no comparison possible.")
        return
    print(f"      {'family':>11} {'REJECTED':>10} {'CLEAN':>8} {'ratio':>7}")
    for f in FAM:
        a = st.mean([25.0 * m[f] / m["out_s"] for m in A])
        b = st.mean([25.0 * m[f] / m["out_s"] for m in B])
        print(f"      {f:>11} {a:>10.2f} {b:>8.2f} "
              f"{(a/b if b else float('inf')):>7.2f}x")
    ta = sum(st.mean([25.0 * m[f] / m["out_s"] for m in A]) for f in FAM)
    tb = sum(st.mean([25.0 * m[f] / m["out_s"] for m in B]) for f in FAM)
    print(f"      {'TOTAL':>11} {ta:>10.2f} {tb:>8.2f} "
          f"{(ta/tb if tb else float('inf')):>7.2f}x")
    print(f"\n      If these mixes match, the gate is noise on a decorative field.")
    print(f"      If rejected plans are thinner, the campaign's density numbers")
    print(f"      describe the fallback rather than the editorial brain.")
