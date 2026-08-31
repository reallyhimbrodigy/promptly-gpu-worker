"""Are UPLOAD_NEVER_STARTED and picker_asset_unresolved the SAME users?

Both are large, both sit at the very first interaction, and both are consistent
with one root: the client cannot materialise the picked asset. UNS jobs report
NO provenance at all (source_type 0/111, source_duration 0/111) while jobs that
proceed report it 655/809 — so the UNS client never completed the step that
produces a file.

CONVICTION TEST: do the same USERS appear in both? A high overlap makes one root
likely; a low overlap REFUTES it and they are two problems. Reported against the
base rate, because in a small user population any two sets overlap somewhat —
the comparison is overlap vs. what chance would give.
"""
import os
from collections import Counter

import modal

app = modal.App("probe-uns-picker-overlap")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> dict:
    from supabase import create_client
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    uns, allu, done = set(), set(), set()
    page = 0
    while page < 24:
        r = (sb.table("video_jobs").select("user_id,result,demo,status,created_at")
             .gte("created_at", since).order("created_at", desc=True)
             .range(page * 500, page * 500 + 499).execute())
        d = r.data or []
        for x in d:
            if x.get("demo") or not x.get("user_id"):
                continue
            res = x.get("result") if isinstance(x.get("result"), dict) else {}
            allu.add(x["user_id"])
            if str(x.get("status")) == "completed":
                done.add(x["user_id"])
            if str(res.get("error_code") or "") == "UPLOAD_NEVER_STARTED":
                uns.add(x["user_id"])
        if len(d) < 500:
            break
        page += 1
    ev = {}
    for name in ("picker_asset_unresolved", "picker_result", "picker_opened"):
        s, page = set(), 0
        while page < 12:
            r = (sb.table("analytics_events").select("user_id,props,created_at")
                 .eq("event", name).gte("created_at", since)
                 .order("created_at", desc=True)
                 .range(page * 500, page * 500 + 499).execute())
            d = r.data or []
            for x in d:
                if x.get("user_id"):
                    s.add(x["user_id"])
            if len(d) < 500:
                break
            page += 1
        ev[name] = s
    return {"uns": list(uns), "all": list(allu), "done": list(done),
            "ev": {k: list(v) for k, v in ev.items()}}


@app.local_entrypoint()
def main(since: str = "2026-08-24"):
    d = scan.remote(since)
    uns, allu = set(d["uns"]), set(d["all"])
    pau = set(d["ev"]["picker_asset_unresolved"])
    popened = set(d["ev"]["picker_opened"])
    print(f"\n=== UNS vs picker_asset_unresolved — same users? (since {since}) ===")
    print(f"  users with a job          : {len(allu)}")
    print(f"  users with UNS            : {len(uns)}")
    print(f"  users with picker-drop    : {len(pau)}")
    print(f"  users who opened a picker : {len(popened)}")
    if not uns or not pau:
        print("\n  one side is EMPTY in this window — no conviction test possible.")
        return
    ov = uns & pau
    # Base rate: if picker-drop users were spread at random over everyone who
    # opened a picker, how many UNS users would we expect to hit by chance?
    base = len(pau) / max(1, len(popened)) if popened else 0
    exp = base * len(uns & popened)
    print(f"\n  OVERLAP: {len(ov)} of {len(uns)} UNS users also dropped a pick "
          f"({100.0*len(ov)/max(1,len(uns)):.0f}%)")
    print(f"  base rate: {100*base:.0f}% of picker-openers drop a pick, so chance")
    print(f"  alone predicts ~{exp:.0f} of the {len(uns & popened)} UNS users who")
    print(f"  opened a picker in this window.")
    if exp and len(ov) > exp * 1.5:
        print(f"\n  -> {len(ov)} observed vs ~{exp:.0f} expected: ENRICHED. One root is")
        print(f"     plausible and worth the next measurement.")
    elif exp:
        print(f"\n  -> {len(ov)} observed vs ~{exp:.0f} expected: NOT enriched. The two")
        print(f"     classes are largely DIFFERENT users, which REFUTES one shared")
        print(f"     root and means they need separate fixes.")
    print(f"\n  activation: {len(uns - set(d['done']))}/{len(uns)} UNS users never "
          f"completed anything")
