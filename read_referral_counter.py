#!/usr/bin/env python3
"""read_referral_counter.py — THE REFERRAL REWARD AS A PRODUCTION COUNTER.

Reports the reward with its DENOMINATOR (Rule 2): "0 rewards" is meaningless,
"0 rewards / 214 qualifying renders" is a result, and "0 rewards / 0 attempts"
means THE LEG IS NOT RUNNING — three different states that must never look alike.

It also reads the upstream chain, because the numerator cannot move without it:

    get_or_create_referral_code -> claim_referral -> qualify_referral -> grant

MEASURED 2026-08-21: `referrals` = 0 rows and NOTHING calls the first two RPCs,
so granted=0 is the STRUCTURALLY EXPECTED reading, not a defect. This tool says
which of the two zeros it is rather than leaving it to be guessed.

DOUBLE-GRANT WATCH: grant_referral_reward writes real Pro days and its
idempotency is the owner's claim, not an observation (the function body is not
in any repo). A second grant to the same user shows up here as >1 granted event
per user — that line is the whole reason the counter carries user_id.

    python3 read_referral_counter.py --hours 24
"""
import argparse
import collections
import json
import os
import sys
import urllib.parse
import urllib.request


def _creds():
    env = {}
    with open(os.path.expanduser("~/content-studio/.env.local")) as fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return (env["SUPABASE_URL"].rstrip("/"),
            env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY"))


def _q(url, key, path, t=90):
    r = urllib.request.Request(f"{url}/rest/v1/{path}",
                               headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(r, timeout=t) as x:
        return json.loads(x.read().decode())


def _count(url, key, table):
    r = urllib.request.Request(f"{url}/rest/v1/{table}?select=id",
                               headers={"apikey": key, "Authorization": f"Bearer {key}",
                                        "Prefer": "count=exact", "Range": "0-0"})
    with urllib.request.urlopen(r, timeout=60) as x:
        return x.headers.get("content-range", "").split("/")[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-08-21T00:00:00Z")
    a = ap.parse_args()
    url, key = _creds()

    ev = _q(url, key, "analytics_events?select=event,props,created_at"
            "&event=in.(referral_qualify_attempted,referral_reward_granted)"
            f"&created_at=gte.{urllib.parse.quote(a.since)}&limit=2000")
    att = [e for e in ev if e["event"] == "referral_qualify_attempted"]
    grn = [e for e in ev if e["event"] == "referral_reward_granted"]

    def _p(e):
        p = e.get("props")
        if isinstance(p, str):
            try:
                return json.loads(p)
            except Exception:
                return {}
        return p or {}

    qualified = sum(1 for e in att if _p(e).get("qualified"))
    print(f"  ── REFERRAL COUNTER · since {a.since} ──")
    print(f"  qualify attempted (denominator) : {len(att)}")
    print(f"  qualified                       : {qualified}")
    print(f"  REWARDS GRANTED (numerator)     : {len(grn)}")

    if not att:
        print("\n  ATTEMPTED = 0. That is NOT 'no rewards owed' — it means the leg "
              "has\n  not run: either the build carrying it is not deployed, or no "
              "render has\n  completed since it was. Check the deploy before "
              "reading anything else.")
    elif not grn:
        print(f"\n  0 rewards / {len(att)} qualifying renders. Expected while the "
              f"upstream\n  chain is unwired — see below.")

    by_user = collections.Counter(str(_p(e).get("user_id")) for e in grn)
    dupes = {u: n for u, n in by_user.items() if n > 1}
    if dupes:
        print(f"\n  ** DOUBLE-GRANT WATCH: {len(dupes)} user(s) granted MORE THAN "
              f"ONCE **")
        for u, n in sorted(dupes.items(), key=lambda kv: -kv[1])[:8]:
            print(f"     {u} x{n}")
        print("     grant_referral_reward's idempotency is an owner CLAIM, not an\n"
              "     observation. This is what a broken claim looks like.")
    elif grn:
        print(f"\n  double-grant watch: 0 users granted twice ({len(by_user)} "
              f"distinct users)")

    errs = collections.Counter(str(_p(e).get("error")) for e in att
                               if _p(e).get("error"))
    if errs:
        print(f"\n  RPC errors: {dict(errs)}")

    print("\n  ── THE CHAIN (the numerator cannot move without it) ──")
    try:
        refs, rewards = _count(url, key, "referrals"), _count(url, key, "referral_rewards")
        print(f"    referrals rows        : {refs}")
        print(f"    referral_rewards rows : {rewards}")
        if refs == "0":
            print("    -> 0 referrals means claim_referral has NEVER run. Steps 1-2\n"
                  "       (get_or_create_referral_code, claim_referral) have no caller\n"
                  "       in content-studio, so qualify/grant have nothing to act on.\n"
                  "       THE REWARD CANNOT BE NON-ZERO UNTIL A CLAIM SURFACE SHIPS.")
    except Exception as e:
        print(f"    (table read failed: {type(e).__name__})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
