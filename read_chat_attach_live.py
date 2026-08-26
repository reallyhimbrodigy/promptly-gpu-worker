#!/usr/bin/env python3
"""DID SERVER-SIDE CHAT ATTACH ACTUALLY EXECUTE? — the production counter. `[Rule 2, Rule 5, Rule 7]`

THE STANDARD (owner, 2026-08-18): "a fix isn't reportable as shipped until a
production counter proves it executed."

═══ THE COUNTER EXISTS BY CONSTRUCTION, WHICH IS WHY IT CAN BE TRUSTED ═══

A server-reconstructed chat is not marked by a column or a log line that could
go missing — its PRIMARY KEY *is* the proof. lib/chat-attach.js derives it as
uuidv5("chat:" + job_id) under a fixed namespace precisely so that creation is
idempotent, and that same determinism means anyone can recompute it later and
ask the database directly: does the chat the server WOULD have made exist?

    server_reconstructed  a chat exists whose id == uuidv5("chat:"+job_id)
    client_attached       the render is in some OTHER chat (the client's PATCH
                          landed, which is the normal, healthy path)
    ORPHANED              the render is in no chat at all — the defect

The python uuid5 here was verified byte-identical to the JS implementation that
writes these ids, on two independent inputs, BEFORE this read was trusted. A
mismatch would have made every count read a confident zero forever.

═══ WHY IT IS CUT AT THE DEPLOY BOUNDARY ═══

Renders that completed before the server could attach cannot have been attached
by it, so mixing them in would dilute the rate with jobs the fix never had a
chance at. The window starts at the deploy; the same measurement over the window
BEFORE it is printed alongside as the baseline, so the two are read together and
neither is quoted alone.

    python3 read_chat_attach_live.py [--since <iso>] [--limit 300]
"""
import argparse
import collections
import json
import sys
import urllib.parse
import urllib.request
import uuid

ENV = "/Users/zaclibman/content-studio/.env.local"
# MUST match CHAT_ATTACH_NAMESPACE in content-studio lib/chat-attach.js.
NS = uuid.UUID("7c9e5a41-3f2b-5d18-9a6e-2b4c8d1f0e73")
# 96a5787 went live with gate stamp 2026-08-18T20:36:05Z; the service starts
# shortly after the build, so the boundary is rounded UP. A job created before
# the server was actually running could not have been attached by it, and
# counting it here would blame the fix for a window it did not exist in.
DEPLOY = "2026-08-18T20:37:00Z"   # 96a5787 — server chat attach live


def _creds():
    env = {}
    with open(ENV) as fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return (env["SUPABASE_URL"].rstrip("/"),
            env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY"))


def _get(url, key, path):
    req = urllib.request.Request(f"{url}/rest/v1/{path}",
                                 headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def reconstructed_chat_id(job_id):
    return str(uuid.uuid5(NS, f"chat:{job_id}"))


def measure(url, key, since, until, limit, label):
    """Membership for every completed render in [since, until)."""
    q = (f"video_jobs?select=id,user_id,created_at&status=eq.completed"
         f"&rendered_video_url=not.is.null&created_at=gte.{urllib.parse.quote(since)}")
    if until:
        q += f"&created_at=lt.{urllib.parse.quote(until)}"
    q += f"&order=created_at.desc&limit={limit}"
    jobs = _get(url, key, q)

    print(f"\n  ── {label} ──  [{since} .. {until or 'now'})")
    if not jobs:
        # NON-VACUITY. No renders means the probe saw nothing, not that nothing leaked.
        print("     0 completed renders in this window — nothing to measure, and")
        print("     that is 'not observed', never 'no orphans'.")
        return None

    buckets = collections.Counter()
    users = collections.defaultdict(set)
    orphans = []
    for j in jobs:
        f = urllib.parse.quote(json.dumps([{"jobId": j["id"]}]))
        hits = _get(url, key, f"chats?select=id&user_id=eq.{j['user_id']}&messages=cs.{f}&limit=2")
        if not hits:
            kind = "ORPHANED"
            orphans.append(j)
        elif any(h["id"] == reconstructed_chat_id(j["id"]) for h in hits):
            kind = "server_reconstructed"
        else:
            kind = "client_attached"
        buckets[kind] += 1
        users[kind].add(j["user_id"])

    tot = len(jobs)
    tot_users = len({j["user_id"] for j in jobs})
    print(f"     denominator: {tot} completed renders / {tot_users} users")
    for kind in ("client_attached", "server_reconstructed", "ORPHANED"):
        n = buckets[kind]
        print(f"     {kind:22} {n:5} jobs ({100.0*n/tot:5.1f}%)   "
              f"{len(users[kind]):4} users ({100.0*len(users[kind])/tot_users:5.1f}%)")
    if orphans:
        print(f"     orphaned job ids: {', '.join(o['id'][:8] for o in orphans[:12])}")
    return {"total": tot, "users": tot_users, "buckets": dict(buckets),
            "orphan_users": len(users["ORPHANED"])}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=DEPLOY)
    ap.add_argument("--limit", type=int, default=300)
    a = ap.parse_args(argv)
    url, key = _creds()

    print(f"  SERVER CHAT ATTACH — did it execute, and did the leak stop?")
    print(f"  A server-reconstructed chat is identified by its DERIVED primary key")
    print(f"  (uuidv5 of the job id), so this counts the fix's own writes, not a log.")

    # The baseline is at least as wide as the live window and never narrower
    # than 6h, so it holds enough renders to be a rate rather than a coin flip.
    # Both widths are PRINTED — an unequal comparison stated is honest; an
    # unequal comparison quoted as one number is not.
    from datetime import datetime, timedelta, timezone
    since_dt = datetime.fromisoformat(a.since.replace("Z", "+00:00"))
    live_width = datetime.now(timezone.utc) - since_dt
    width = max(live_width, timedelta(hours=6))
    before = (since_dt - width).isoformat().replace("+00:00", "Z")
    print(f"  windows: baseline {width.total_seconds()/3600:.1f}h  |  "
          f"live {max(live_width.total_seconds(),0)/3600:.2f}h since the deploy")

    pre = measure(url, key, before, a.since, a.limit, "BEFORE the deploy (baseline)")
    post = measure(url, key, a.since, None, a.limit, "AFTER the deploy (the fix's cohort)")

    print("\n  ── VERDICT ──")
    if not post:
        print("     no post-deploy renders yet. NOT a zero — re-run when traffic lands.")
        return 0
    orph = post["buckets"].get("ORPHANED", 0)
    made = post["buckets"].get("server_reconstructed", 0)
    if made == 0 and orph == 0:
        print(f"     0 orphans / {post['total']} renders, and the server never had to")
        print(f"     reconstruct — every client PATCH landed in this window. The fix is")
        print(f"     DEPLOYED and UNEXERCISED: this window does not prove it executed.")
    elif made > 0:
        print(f"     EXECUTED: the server reconstructed {made} chat(s) that would")
        print(f"     otherwise have been orphaned renders.")
    if orph:
        print(f"     *** {orph} render(s) across {post['orphan_users']} user(s) are STILL")
        print(f"     in no chat after the deploy — the inline attach or the sweep is not")
        print(f"     holding. Check the [ALERT] render-in-no-chat lines.")
    if pre:
        print(f"     baseline orphan rate: {pre['buckets'].get('ORPHANED',0)}/{pre['total']}"
              f"   ->   after: {orph}/{post['total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
