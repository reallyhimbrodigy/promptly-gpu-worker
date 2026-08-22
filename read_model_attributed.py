#!/usr/bin/env python3
"""read_model_attributed.py — DOES A REAL JOB NAME ITS MODEL? [Rule 2]

v567 (751712c) persists editorial_model/utility_model into stage_timings.
Before it, 48 of 48 editorial jobs carried NO model string at all.

The value matters as much as the presence: the code DEFAULT is
gemini-3.1-pro-preview while the secret sets gemini-3.7-flash, and the two
differ by roughly an order of magnitude in input price. A field that reports the
default would be worse than no field — it would look authoritative and be wrong.
"""
import json, os, sys, urllib.parse, urllib.request, collections
import promptly_read as P

V567 = "2026-08-22T20:43:00Z"


def _creds():
    env = {}
    with open(os.path.expanduser("~/content-studio/.env.local")) as fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return (env["SUPABASE_URL"].rstrip("/"),
            env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY"))


url, key = _creds()
r = urllib.request.Request(
    url + "/rest/v1/video_jobs?select=id,created_at,stage_timings,result"
    "&status=eq.completed&created_at=gte." + urllib.parse.quote(V567)
    + "&order=created_at.desc&limit=1000",
    headers={"apikey": key, "Authorization": f"Bearer {key}"})
rows = json.loads(urllib.request.urlopen(r, timeout=90).read())
ed = [x for x in rows if P.route(x) == "EDITORIAL"]
print(f"  editorial jobs since v567: {len(ed)}")
if not ed:
    print("  EMPTY — not confirmed. An empty window is a failed read.")
    sys.exit(2)
models = collections.Counter()
missing = 0
for x in ed:
    m = P.stage_timings(x).get("editorial_model")
    if m:
        models[str(m)] += 1
    else:
        missing += 1
print(f"  editorial_model present : {len(ed)-missing}/{len(ed)}")
print(f"  values                  : {dict(models)}")
if missing:
    print(f"  NOT CONFIRMED: {missing} job(s) still carry no model.")
    sys.exit(1)
if "gemini-3.1-pro-preview" in models:
    print("  ** REPORTS THE CODE DEFAULT, not the secret override — the field is "
          "authoritative-looking and WRONG. **")
    sys.exit(1)
print("  CONFIRMED ON REAL TRAFFIC: every editorial job names its model, and it "
      "is the secret's value, not the code default.")
