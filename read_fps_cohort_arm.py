#!/usr/bin/env python3
"""read_fps_cohort_arm.py — THE fps A/B, CUT BY ARM INSTEAD OF BY CLOCK.

read_fps_cohort.py cuts POST-FLIP on `created_at >= FLIP`. That is a MIXTURE, not
a cohort. Modal mounts secrets at CONTAINER START, so after a flip production runs
BOTH arms simultaneously — cold-start containers on the new value, snapshot-restored
ones on the frozen old one. A timestamp cut sweeps in jobs that ran the OLD arm and
reports the blend as the new one.

MEASURED 2026-08-24, which is why this file exists:

    proxy_sample_fps persisted:  {2: 96, absent: 245}
    media_resolution persisted:  {MEDIA_RESOLUTION_LOW: 96, absent: 245}

96 jobs are LABELLED. The old reader's POST cohort was 99 by clock. Those are not
the same population, and nothing in its output said so.

HOW THIS CUTS, and why each side is clean:

  PRE   created_at < FLIP.  Clean BY CONSTRUCTION — before the flip every
        container held 18fps, so there is no other arm to contaminate it.
  POST  proxy_sample_fps == 2.  Clean BY LABEL — the job itself records which
        arm ran, which is exactly what cert_model_attributed clause 1b persists
        it for. `absent` is NOT the 18fps arm; it is UNMEASURED (the attribution
        deploy landed after the flip), and conflating the two is the same error
        as reading a missing column as an empty one.

SOURCE DURATION IS REPORTED AND NORMALISED, because it is the confound that
already produced one false read: prompt_tokens ~= 60,540 + 1,255 x source_seconds,
so a cohort whose sources got shorter shows a token drop that has nothing to do
with fps. A window read once produced -34.3% against a predicted -36% and was
pure confound. The old reader computed `src` and never printed it.

    python3 read_fps_cohort_arm.py
"""
import json
import os
import statistics as st
import sys
import urllib.parse
import urllib.request

FLIP = "2026-08-22T22:30:00Z"
PRE_LO = "2026-08-21T18:47:00Z"

# The pre-registration. Stated BEFORE the flip; reproduced here so the finding is
# read against it rather than against whatever the numbers turn out to be.
PREDICTED = {"tok": -36.0, "unc": -60.0, "leg": -41.0}


def _creds():
    env = {}
    with open(os.path.expanduser("~/content-studio/.env.local")) as fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return (env["SUPABASE_URL"].rstrip("/"),
            env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY"))


def main():
    url, key = _creds()
    req = urllib.request.Request(
        url + "/rest/v1/video_jobs?select=id,created_at,stage_timings,result"
        "&status=eq.completed&created_at=gte." + urllib.parse.quote(PRE_LO)
        + "&order=created_at.desc&limit=1000",
        headers={"apikey": key, "Authorization": f"Bearer {key}"})
    rows = json.load(urllib.request.urlopen(req, timeout=120))

    def rec(r):
        stg = r.get("stage_timings") or {}
        if not isinstance(stg, dict):
            return None
        tok = stg.get("gemini_tokens") or {}
        if not isinstance(tok, dict):
            tok = {}
        p, c = tok.get("prompt"), tok.get("cached")
        if not isinstance(p, (int, float)) or not p:
            return None
        return {
            "arm": stg.get("proxy_sample_fps"),
            "at": str(r.get("created_at")),
            "tok": float(p),
            "unc": float(p) - float(c or 0),
            "leg": stg.get("gemini_call"),
            "src": stg.get("source_duration_s"),
        }

    recs = [x for x in (rec(r) for r in rows) if x]
    pre = [x for x in recs if PRE_LO <= x["at"] < FLIP]
    post = [x for x in recs if x["arm"] == 2]
    unmeasured = [x for x in recs if x["at"] >= FLIP and x["arm"] != 2]

    def p50(rs, k):
        v = [x[k] for x in rs if isinstance(x.get(k), (int, float))]
        return st.median(v) if v else None

    print(f"\n  PRE  (clock < FLIP; clean BY CONSTRUCTION)   n={len(pre)}")
    print(f"  POST (proxy_sample_fps == 2; clean BY LABEL)  n={len(post)}")
    print(f"  post-FLIP but UNLABELLED (excluded, NOT assumed 18fps) n={len(unmeasured)}")
    if len(pre) < 15 or len(post) < 15:
        print("\n  TOO FEW on one side. Unmeasured, not null.")
        return 2

    print(f"\n  {'':<14}{'PRE':>12}{'POST':>12}{'delta':>10}{'predicted':>11}")
    for k, lbl in (("tok", "prompt tok"), ("unc", "uncached tok"), ("leg", "gemini leg s")):
        a, b = p50(pre, k), p50(post, k)
        if a is None or b is None:
            print(f"  {lbl:<14}{'—':>12}{'—':>12}")
            continue
        d = (b - a) / a * 100
        pr = PREDICTED.get(k)
        pred = f"{pr:.1f}%" if pr is not None else "—"
        print(f"  {lbl:<14}{a:>12.0f}{b:>12.0f}{d:>8.1f}%{pred:>11}")

    # THE CONFOUND, SHOWN. Tokens scale with source seconds, so a cohort whose
    # sources shifted produces a token delta that is not an fps effect.
    sa, sb = p50(pre, "src"), p50(post, "src")
    print(f"\n  {'source dur s':<14}{sa if sa else float('nan'):>12.1f}{sb if sb else float('nan'):>12.1f}"
          f"{((sb - sa) / sa * 100) if (sa and sb) else float('nan'):>9.1f}%   <- the confound")
    if sa and sb:
        # tokens per source-second strips the duration term from the comparison
        ta, tb = p50(pre, "tok"), p50(post, "tok")
        print(f"  {'tok / src s':<14}{ta / sa:>12.0f}{tb / sb:>12.0f}"
              f"{((tb / sb) - (ta / sa)) / (ta / sa) * 100:>9.1f}%   <- duration-normalised")
        if abs((sb - sa) / sa) > 0.15:
            print("\n  ⚠  SOURCE DURATION MOVED >15% BETWEEN ARMS. The raw token delta is")
            print("     contaminated; read the duration-normalised row, not the raw one.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
