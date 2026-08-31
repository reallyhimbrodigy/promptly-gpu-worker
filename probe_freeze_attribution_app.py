"""Whose freeze trips are these? Attribution BEFORE interpretation.

Five INTEGRITY_TRIP:freeze since v598, all demo=true. If they are my own test
dispatches then they are one source re-run N times, NOT a live spike, and the
per-user framing does not apply. If any are someone else's, that is a separate
question and has to be separated before either is read.
"""
import os
from collections import Counter
import modal

app = modal.App("probe-freeze-attribution")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]
V598 = "2026-08-31T02:36:00+00:00"     # v598 deploy, UTC


@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> list:
    from supabase import create_client
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    rows, page = [], 0
    while page < 12:
        r = (sb.table("video_jobs")
             .select("id,user_id,result,demo,created_at,video_url,status")
             .gte("created_at", since).order("created_at", desc=True)
             .range(page * 500, page * 500 + 499).execute())
        d = r.data or []
        rows.extend(d)
        if len(d) < 500:
            break
        page += 1
    out = []
    for x in rows:
        res = x.get("result") if isinstance(x.get("result"), dict) else {}
        if str(res.get("error_code") or "") != "INTEGRITY_TRIP":
            continue
        out.append({"id": x.get("id"), "user": x.get("user_id"),
                    "demo": bool(x.get("demo")), "created": str(x.get("created_at"))[:19],
                    "sub": str(res.get("error_subcode") or ""),
                    "src": str(x.get("video_url") or "")[:80],
                    "detail": str(res.get("error_detail") or "")[:300]})
    return out


@app.local_entrypoint()
def main(since: str = V598):
    rows = scan.remote(since)
    print(f"\n=== INTEGRITY_TRIP since v598 ({since}) — ATTRIBUTION ===")
    print(f"  {len(rows)} trips")
    print(f"  demo=True : {sum(1 for r in rows if r['demo'])}")
    print(f"  demo=False: {sum(1 for r in rows if not r['demo'])}   <- real users")
    print(f"  distinct sources: {len(set(r['src'] for r in rows))}")
    for s, n in Counter(r["src"] for r in rows).most_common(4):
        print(f"      {n:>3}  {s[-52:]}")
    print(f"\n  {'job':<10} {'demo':<6} {'sub':<12} created")
    for r in rows:
        print(f"  {str(r['id'])[:8]:<10} {str(r['demo']):<6} {r['sub']:<12} {r['created']}")
        print(f"      {r['detail'][:150]}")
    real = [r for r in rows if not r["demo"]]
    if real:
        print("\n  VERDICT: %d REAL-USER trip(s) — a separate question from the "
              "demo ones and must not be pooled with them." % len(real))
    else:
        print("\n  VERDICT: ALL demo=True — these are TEST DISPATCHES, not a live")
        print("  spike. One source re-run N times is not N affected users, and the")
        print("  per-user framing does not apply to them.")
