"""ARE THE 119 UNLABELLED JOBS A RECORDING BUG, OR OUT OF SCOPE?

_lean_ab_arm() never returns None — it returns "lean" or "control" always. So an
absent lean_arm is not the resolver failing; it is the job never reaching the
write. Test: is lean_arm absent EXACTLY on the diverted routes (moodreel /
minimal / hype), which never run the post-cuts editorial call and therefore have
no lean schema to be in an arm of?

If yes, the label is correctly SCOPED and the lean/control cut is not provisional.
If no, there is a real recording hole.
"""
import os, modal
from collections import Counter
app = modal.App("probe-lean-label")
image = modal.Image.debian_slim().pip_install("supabase")
S=[modal.Secret.from_name("promptly-secrets")]

@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> list:
    from supabase import create_client
    sb = create_client(os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    r = (sb.table("video_jobs").select("id,result,demo")
         .gte("created_at", since).eq("status","completed")
         .order("created_at", desc=True).limit(500).execute())
    out=[]
    for x in (r.data or []):
        if x.get("demo"): continue
        res = x.get("result") if isinstance(x.get("result"), dict) else {}
        st = res.get("stage_timings") if isinstance(res.get("stage_timings"), dict) else {}
        out.append({"route": str(res.get("route") or "std-editorial"),
                    "arm": str(st.get("lean_arm") or "<ABSENT>"),
                    "ed": str(st.get("editorial_model") or "<ABSENT>")})
    return out

@app.local_entrypoint()
def main(since: str = "2026-08-27"):
    rows = scan.remote(since)
    print(f"\n=== lean_arm labelling by route ({len(rows)} organic completions) ===")
    print(f"  {'route':>22} {'n':>4}  arm distribution")
    by = {}
    for r in rows: by.setdefault(r["route"], []).append(r)
    for rt, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f"  {rt:>22} {len(rs):>4}  {dict(Counter(x['arm'] for x in rs))}")
    std = by.get("std-editorial", [])
    lab = [x for x in std if x["arm"] != "<ABSENT>"]
    div = [x for rt, rs in by.items() if rt != "std-editorial" for x in rs]
    dlab = [x for x in div if x["arm"] != "<ABSENT>"]
    print(f"\n  std-editorial LABELLED : {len(lab)}/{len(std)}")
    print(f"  diverted routes LABELLED: {len(dlab)}/{len(div)}")
    if std and len(lab) == len(std) and not dlab:
        print("\n  VERDICT: correctly SCOPED, not a recording bug. Every job that")
        print("  runs the editorial call carries an arm; the diverted routes never")
        print("  run it, so they have no arm to be in. The lean/control cut stands.")
    else:
        print("\n  VERDICT: a REAL recording hole — labelled std-editorial is not 100%,")
        print("  or a diverted route carries an arm it cannot have.")

