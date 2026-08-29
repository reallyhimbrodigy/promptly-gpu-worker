"""INSTRUMENT CHECK for the '__round__' class — NOT a candidate-site guess.

The campaign has burned five plausible sites (641632a, 9755768). The reason is
that every one was a guess accepted without a refuting check, because the
instrument — the traceback — was believed absent.

But handler.py:44420 ALREADY persists `error_where` (deepest handler.py frame)
on every terminal that reaches the outer except. So before building any bypass,
answer the prior question with data:

  Does the __round__ class carry error_where, or is it empty/missing?

  • POPULATED  → the instrument was never absent. Read the frame. Done.
  • EMPTY      → the frame filter dropped it (raise is outside handler.py, or
                 the traceback was already consumed). Bypass must widen frames.
  • ROW ABSENT → these jobs never reach the outer except at all (reaper /
                 WORKER_DIED / a thread). Bypass must move upstream.

Three mechanisms, three different fixes. This costs ~$0.005 and eliminates two
of them. No renders, one CPU container.
"""
import json, os, modal

app = modal.App("probe-round-class")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=image, secrets=S, timeout=600)
def scan(since: str) -> dict:
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))

    # Pull ALL failed rows in the window, filter locally. Filtering server-side
    # on a jsonb substring would silently exclude rows whose result never got
    # written — which is one of the three hypotheses under test.
    rows, page, PAGE = [], 0, 1000
    while True:
        r = (sb.table("video_jobs")
             .select("id,user_id,status,created_at,error_message,result")
             .gte("created_at", since)
             .order("created_at", desc=True)
             .range(page * PAGE, page * PAGE + PAGE - 1).execute())
        d = r.data or []
        rows.extend(d)
        if len(d) < PAGE:
            break
        page += 1
        if page > 30:
            break

    hits, denom_failed, denom_all = [], 0, len(rows)
    for row in rows:
        res = row.get("result") or {}
        if not isinstance(res, dict):
            res = {}
        st = str(row.get("status") or "")
        if st in ("failed", "error"):
            denom_failed += 1
        blob = (str(res.get("error_detail") or "") + " "
                + str(row.get("error_message") or "") + " "
                + str(res.get("error_class") or ""))
        if "__round__" in blob:
            hits.append({
                "id": row.get("id"),
                "user": row.get("user_id"),
                "at": row.get("created_at"),
                "status": st,
                "code": res.get("error_code"),
                "subcode": res.get("error_subcode"),
                "err_class": res.get("error_class"),
                # THE ANSWER: present / empty-string / key-absent are three
                # different findings and must stay distinguishable.
                "where": res.get("error_where", "<KEY-ABSENT>"),
                "detail": str(res.get("error_detail") or
                              row.get("error_message") or "")[:400],
                "timing_keys": (sorted(res.get("stage_timings").keys())
                                if isinstance(res.get("stage_timings"), dict)
                                else "<none>"),
                "result_keys": sorted(res.keys())[:24],
            })
    return {"hits": hits, "denom_failed": denom_failed, "denom_all": denom_all,
            "since": since}


@app.local_entrypoint()
def main(since: str = "2026-08-20"):
    d = scan.remote(since)
    hits = d["hits"]
    print(f"\n=== __round__ class — window {d['since']} onward ===")
    print(f"denominator: {len(hits)} hits / {d['denom_failed']} failed "
          f"/ {d['denom_all']} jobs total\n")
    if not hits:
        print("NO HITS. A clean zero is guilty until proven innocent — the "
              "string may live in a column this reader does not select, or "
              "these jobs never wrote a result row at all.")
        return

    users = sorted({h["user"] for h in hits if h["user"]})
    print(f"users: {len(users)} | jobs: {len(hits)}   (Rule 7: lead with users)")

    # THE VERDICT LINE — which of the three mechanisms is in play.
    pop = [h for h in hits if h["where"] not in ("<KEY-ABSENT>", "", None)]
    absent = [h for h in hits if h["where"] == "<KEY-ABSENT>"]
    empty = [h for h in hits if h["where"] == ""]
    print(f"\nerror_where: {len(pop)} POPULATED / {len(empty)} EMPTY / "
          f"{len(absent)} KEY-ABSENT  of {len(hits)}")
    if pop:
        print("\n  >>> THE INSTRUMENT WAS NEVER ABSENT. Frames:")
        from collections import Counter
        for w, n in Counter(h["where"] for h in pop).most_common():
            print(f"      {n:>3}x  {w}")

    # THE REFUTING CHECK. 641632a recorded this as a STANDING class since
    # 08-20 ("NOT mine"). If every hit post-dates 15acc4f (2026-08-28 11:33
    # -0700 = 18:33Z), that reading is wrong and this is a same-day regression.
    from collections import Counter
    print("\n  hits by hour (UTC):")
    for hr, n in sorted(Counter(h["at"][:13] for h in hits).items()):
        print(f"      {hr}Z  {'#' * n} {n}")
    _first = min(h["at"] for h in hits)
    print(f"\n  EARLIEST hit: {_first}")
    # v584 (2026-08-28 11:40 PDT = 18:40Z) is the FIRST deploy carrying 15acc4f;
    # v583 (4d32aba) verified clean of it. Bracket the earliest hit against that.
    _verdict = ("ALL hits post-date v584: SAME-DAY REGRESSION, shipped by 15acc4f"
                if _first >= "2026-08-28T18:40"
                else "a hit PRE-dates v584: standing class, 15acc4f not the origin")
    print("  v584 (first deploy carrying 15acc4f): 2026-08-28T18:40Z")
    print("  VERDICT: " + _verdict)

    for h in hits[:12]:
        print(f"\n--- {h['at']} {h['id']}")
        print(f"    status={h['status']} code={h['code']}:{h['subcode']} "
              f"class={h['err_class']}")
        print(f"    where={h['where']}")
        print(f"    detail={h['detail'][:240]}")
        print(f"    timings={h['timing_keys']}")
        print(f"    result_keys={h['result_keys']}")
