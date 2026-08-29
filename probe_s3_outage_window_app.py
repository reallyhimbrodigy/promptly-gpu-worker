"""DID THE AWS SUSPENSION HURT REAL USERS? Find the window, size it, name them.

Zac's AWS account was briefly suspended during a free-tier-to-paid transition
(now resolved). The worker's key returned InvalidAccessKeyId while it was down.
Two things follow and BOTH need answering before anything else runs:

  1. Did organic jobs fail because S3 was unreachable? Those are real users
     whose jobs died for a cause that is NOT a pipeline defect.
  2. If so, they are inflating the error board with someone else's cause, and
     every rate cut over that window is contaminated (Rule 5 — state the window
     and why it is clean, or say plainly that it is not).

METHOD. The suspension window is NOT known in advance, so it is DERIVED, not
assumed: bucket every failure by hour, and mark the hours where an S3-signature
failure appears. The signature set is deliberately broad (InvalidAccessKeyId,
AccessDenied, NoSuchKey, 403, S3, download/upload failures) because a credential
outage surfaces under several codes — UPLOAD_STALLED when the source cannot be
HEADed, DOWNLOAD/RENDER when a fetch dies mid-pipeline.

SEPARATED FROM __round__ ON PURPOSE. The v584 regression already accounts for a
large block of failures in the same period; counting them as S3 damage would
double-blame and overstate the outage. Both are reported, apart.

Rule 7: per-USER first — a user who retried five times is one lost user.

  ./run_modal.sh probe_s3_outage_window_app.py --since 2026-08-25
"""
import os
from collections import Counter, defaultdict

import modal

app = modal.App("probe-s3-outage-window")
image = modal.Image.debian_slim().pip_install("supabase")
S = [modal.Secret.from_name("promptly-secrets")]

# SPECIFIC ON PURPOSE — the first version was broad and was WRONG.
#
# It included bare "s3" and "403". "403" matched a LINE NUMBER inside
# `error_where` (handler.py:403…) and flagged two jobs that have nothing to do
# with AWS: a 2.0s clip hitting the designed <2.0s rejection, and a
# `TypeError: stat: path should be string` in the degrade ladder. It would have
# told Zac two users were harmed by the suspension when zero were.
#
# That is the documented short-token class — validate_deploy has a meta-check
# that FAILS any assertion matching a token of <=6 chars against raw text, for
# exactly this reason ("500" inside "max 500 tokens", "chrome" inside a healthy
# startup line). A wrong attribution is worse than `unclassified`: it sends
# people to the wrong cause with false confidence.
#
# Every signature below is a distinctive AWS/botocore error string that cannot
# occur in ordinary prose or a line number.
S3_SIGNS = ("invalidaccesskeyid", "accessdenied", "access denied", "nosuchkey",
            "invalidclienttokenid", "signaturedoesnotmatch", "tokenrefresherror",
            "expiredtoken", "requesttimetooskewed", "nocredentialserror",
            "botocore", "endpointconnectionerror", "did not arrive on s3",
            "s3 client not initialized", "could not download", "download failed",
            "upload failed")


@app.function(image=image, secrets=S, timeout=900)
def scan(since: str) -> dict:
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    rows, page, PAGE = [], 0, 1000
    while True:
        r = (sb.table("video_jobs")
             .select("id,user_id,status,created_at,error_message,result,demo")
             .gte("created_at", since).order("created_at", desc=True)
             .range(page * PAGE, page * PAGE + PAGE - 1).execute())
        d = r.data or []
        rows.extend(d)
        if len(d) < PAGE:
            break
        page += 1
        if page > 25:
            break
    return {"rows": rows, "since": since}


@app.local_entrypoint()
def main(since: str = "2026-08-25"):
    d = scan.remote(since)
    rows = [r for r in d["rows"] if not r.get("demo")]

    def _res(r):
        v = r.get("result")
        return v if isinstance(v, dict) else {}

    def _blob(r):
        # error_where is DELIBERATELY EXCLUDED: it is "handler.py:<lineno> in
        # <fn>", and matching error TEXT against a line number is how "403"
        # produced two false attributions. Frames are for reading, not matching.
        return (str(_res(r).get("error_detail") or "") + " "
                + str(r.get("error_message") or "")).lower()

    failed = [r for r in rows if str(r.get("status")) in ("failed", "error")]
    done = [r for r in rows if str(r.get("status")) == "completed"]
    rnd = [r for r in failed if "__round__" in _blob(r)]
    # S3-signature failures, EXCLUDING the v584 __round__ block so the two
    # causes are never conflated into one inflated number.
    s3 = [r for r in failed if r not in rnd
          and any(s in _blob(r) for s in S3_SIGNS)]

    print(f"\n=== window {d['since']} onward — organic only ===")
    print(f"  {len(rows)} jobs / {len({r.get('user_id') for r in rows})} users")
    print(f"  completed {len(done)}  |  failed {len(failed)}")
    print(f"  of the failures: {len(rnd)} __round__ (v584 regression, MINE)")
    print(f"                   {len(s3)} S3-signature (candidate AWS-suspension damage)")
    print(f"                   {len(failed) - len(rnd) - len(s3)} other")

    if s3:
        print(f"\n  ── S3-SIGNATURE FAILURES: {len(s3)} jobs / "
              f"{len({r.get('user_id') for r in s3})} USERS ──")
        by_hour = defaultdict(list)
        for r in s3:
            by_hour[str(r.get("created_at"))[:13]].append(r)
        print("  hour (UTC)        jobs  users  codes")
        for hr in sorted(by_hour):
            g = by_hour[hr]
            cs = ",".join(sorted({str(_res(x).get('error_code')) for x in g}))
            print(f"  {hr}Z  {len(g):>5}  {len({x.get('user_id') for x in g}):>5}  {cs}")
        _hrs = sorted(by_hour)
        print(f"\n  DERIVED OUTAGE WINDOW: {_hrs[0]}Z → {_hrs[-1]}Z "
              f"({len(_hrs)} distinct hour(s))")
        print(f"\n  AFFECTED USERS (these people's jobs failed for AWS's reason, "
              f"not ours):")
        for u, n in Counter(r.get("user_id") for r in s3).most_common():
            print(f"      {u}  — {n} job(s)")
        print("\n  SAMPLES:")
        for r in s3[:5]:
            print(f"      {r.get('created_at')} {_res(r).get('error_code')}"
                  f":{_res(r).get('error_subcode')}")
            print(f"        {str(_res(r).get('error_detail') or r.get('error_message'))[:200]}")
    else:
        print("\n  NO S3-SIGNATURE FAILURES FOUND in organic traffic.")
        print("  Read this as: the suspension did not reach user jobs in this")
        print("  window — the main delivery route PUTs to a caller-supplied")
        print("  presigned URL and needs no AWS creds. It is NOT proof that S3")
        print("  was up; it is proof no user job died with an S3 signature.")

    # CONTAMINATION NOTE for anything cut over this window.
    print(f"\n  COHORT HYGIENE: any rate cut over {d['since']}+ must exclude "
          f"{len(rnd)} __round__ jobs (v584, fixed in v586)"
          + (f" and {len(s3)} S3-outage jobs (not ours)." if s3 else "."))
