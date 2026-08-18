#!/usr/bin/env python3
"""HEAL THE ROWS THAT HOLD A FINISHED VIDEO AND SAY THEY FAILED. `[Law 2, Rule 7]`

THE COHORT. 114 jobs across 90 USERS reached status='failed' while carrying a
rendered_video_url. Every one of those users has a playable video and was told
"Something went wrong." That is worse than a failure: it is a lie about work we
successfully did, and we paid for the render anyway.

STAGED, DELIBERATELY. The earlier 34-row batch caught a real contradiction on
its FIRST THREE: the row flipped to completed while `error_message` still read
"This render hit our time limit" and `result` still carried
`error_code`/`reaped`. A completed job that also says it timed out is a
contradiction THE USER READS, and a lingering `result.error_code` is exactly
what breaks a `_delivered` predicate downstream. Clearing status without
clearing the story is half a heal.

So the verification checks all three TOGETHER — status, copy, and
result.error_code — and this cohort is three times larger than the one that
taught us that.

    python3 heal_terminal_invariant.py                  # report only
    python3 heal_terminal_invariant.py --apply --limit 3  # first batch
    python3 heal_terminal_invariant.py --apply            # the rest
"""
import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone

ENV = "/Users/zaclibman/content-studio/.env.local"
_ERR_KEYS = {"error", "error_code", "error_class", "error_where", "error_detail",
             "user_message", "reaped", "reason", "retryable", "http_status",
             "error_cause", "error_subcode", "error_frame", "error_frames"}


def _creds():
    env = {}
    with open(ENV) as fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return (env["SUPABASE_URL"].rstrip("/"),
            env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY"))


def _req(url, key, path, method="GET", body=None, prefer=None):
    h = {"apikey": key, "Authorization": f"Bearer {key}",
         "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    r = urllib.request.Request(f"{url}/rest/v1/{path}", method=method,
                               data=json.dumps(body).encode() if body else None,
                               headers=h)
    with urllib.request.urlopen(r, timeout=120) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw.strip() else []


def deliverable(row):
    d = row.get("rendered_video_url") or row.get("result_url") or row.get("hls_manifest_url")
    if d:
        return d
    res = row.get("result")
    if isinstance(res, dict):
        return res.get("video_url") or res.get("rendered_video_url")
    return None


def healed_result(result):
    src = result if isinstance(result, dict) else {}
    out = {k: v for k, v in src.items() if k not in _ERR_KEYS}
    frm = src.get("error_code") or src.get("error")
    if frm:
        out["healed_from"] = frm
    out["healed_at"] = datetime.now(timezone.utc).isoformat()
    return out


def verify(url, key, ids):
    """All three cleared TOGETHER, and the video still there."""
    rows = _req(url, key, f"video_jobs?select=id,status,error_message,result,"
                          f"rendered_video_url,completion_delivery"
                          f"&id=in.({','.join(ids)})")
    ok = True
    print(f"  {'job':10}{'status':11}{'err_msg':9}{'result.error_code':19}{'video':7}  verdict")
    for r in rows:
        res = r.get("result") or {}
        s_ok = r.get("status") == "completed"
        m_ok = not r.get("error_message")
        e_ok = not res.get("error_code")
        v_ok = bool(deliverable(r))
        good = s_ok and m_ok and e_ok and v_ok
        ok &= good
        print(f"  {r['id'][:8]:10}{str(r.get('status')):11}"
              f"{('CLEAR' if m_ok else 'SET!'):9}"
              f"{(str(res.get('error_code')) if res.get('error_code') else 'CLEAR'):19}"
              f"{('yes' if v_ok else 'NO!'):7}  {'consistent' if good else '*** CONTRADICTION ***'}")
    return ok


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    url, key = _creds()

    rows = _req(url, key, "video_jobs?select=id,user_id,status,error_message,result,"
                          "rendered_video_url,result_url,hls_manifest_url,completed_at,"
                          "completion_delivery&status=eq.failed"
                          "&rendered_video_url=not.is.null&limit=2000")
    bad = [r for r in rows if deliverable(r)]
    users = {r["user_id"] for r in bad}
    print(f"  VIOLATIONS: {len(bad)} rows / {len(users)} users "
          f"[Rule 7: the user count is the one that matters]")
    if not bad:
        print("  nothing to heal.")
        return 0
    if not a.apply:
        print("  (report only — pass --apply, and stage it: --limit 3 first)")
        return 0

    batch = bad[:a.limit] if a.limit else bad
    print(f"  APPLYING to {len(batch)} row(s)...")
    done = []
    for r in batch:
        patch = {
            "status": "completed", "current_step": "complete", "progress": 100,
            "step_message": "Your video is ready!",
            # ALL THREE TOGETHER — status, copy, and the result's error story.
            "error_message": None,
            "result": healed_result(r.get("result")),
            "completion_delivery": r.get("completion_delivery") or "invariant_heal",
            "completed_at": r.get("completed_at") or datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            _req(url, key, f"video_jobs?id=eq.{r['id']}&status=eq.failed",
                 method="PATCH", body=patch, prefer="return=minimal")
            done.append(r["id"])
        except Exception as e:
            print(f"    {r['id'][:8]} FAILED to heal: {type(e).__name__}: {e}")
    print(f"  healed {len(done)}/{len(batch)}")
    if done:
        print("\n  VERIFY — status, copy and result.error_code together:")
        good = verify(url, key, done)
        print(f"\n  {'ALL CONSISTENT' if good else '*** STOP — a row reads contradictory ***'}")
        return 0 if good else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
