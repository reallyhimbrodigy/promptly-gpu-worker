#!/usr/bin/env python3
"""read_fps_cohort.py — DID 2fps+LOW DO WHAT THE A/B PREDICTED?

Flipped 2026-08-22: PROMPTLY_PROXY_SAMPLE_FPS=2, PROMPTLY_MEDIA_RESOLUTION=
MEDIA_RESOLUTION_LOW. LAUNCH_DAY 6 had ruled the pair INCONCLUSIVE because both
arms fell to safe_edit_fallback during the outage; the controlled A/B since
resolved it.

PRE-REGISTERED, so the answer cannot be chosen after the data arrives:
    prompt tokens        -36%  (A-vs-A noise was +2.0%, so this is the real one)
    uncached delta       -60%  (the video term — paid in full every call)
    gemini_call wall     -41%  (A-vs-A noise was +19%, so read this cautiously)

THE TWO RESIDUALS, and why they are the watch items rather than footnotes: both
REPEATED across independent runs, so unlike the placement divergence they are
probably real effects and not model noise.
    emphasis count        5 -> 4   (A gave 5 twice, B gave 4 twice)
    thumbnail_word_index  moves    (93 -> 12 in both pairs)
MG placement stays UNTESTED — MG was 0 in every arm of every run.

A REVERT TRIGGER, stated up front: emphasis density is a QUALITY term and this
lever is a COST lever. Quality wins over speed. If emphasis-per-output-second
drops materially against the pre-flip cohort, the tokens do not buy it back.

    python3 read_fps_cohort.py
"""
import json, os, statistics as st, sys, urllib.parse, urllib.request
import promptly_read as P

FLIP = "2026-08-22T22:30:00Z"      # v569 window; refined from modal app history
PRE_LO, PRE_HI = "2026-08-21T18:47:00Z", FLIP


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
    "&status=eq.completed&created_at=gte." + urllib.parse.quote(PRE_LO)
    + "&order=created_at.desc&limit=1000",
    headers={"apikey": key, "Authorization": f"Bearer {key}"})
rows = json.loads(urllib.request.urlopen(r, timeout=90).read())

def cut(rs, label):
    out = []
    for x in rs:
        if P.route(x) != "EDITORIAL":
            continue
        stg = P.stage_timings(x)
        gt = P.gemini_tokens(x)
        rec = P.edit_plan(x)
        if gt is P.MISSING or rec is P.MISSING:
            continue
        cuts = rec.get("cuts") or []
        outs = sum(max(0.0, float(c.get("source_end", 0) or 0) - float(c.get("source_start", 0) or 0))
                   for c in cuts)
        em = rec.get("emphasis_moments") or []
        out.append({
            "tok": gt.get("prompt"), "unc": gt.get("uncached_delta"),
            "leg": stg.get("gemini_call"), "src": stg.get("source_duration_s"),
            "out_s": outs, "emph": len(em),
            "thumb": rec.get("thumbnail_word_index"),
            "mg": len([e for e in em if isinstance(e, dict) and e.get("motion_graphic")]),
        })
    print(f"\n  {label}: n={len(out)}")
    if not out:
        print("    EMPTY — not a result.")
        return None
    def p50(k):
        v = [d[k] for d in out if isinstance(d.get(k), (int, float))]
        return st.median(v) if v else None
    d = {k: p50(k) for k in ("tok", "unc", "leg", "src", "out_s", "emph", "mg")}
    # emphasis DENSITY, not count — a shorter output legitimately carries fewer
    dens = [d2["emph"] / d2["out_s"] for d2 in out if d2["out_s"] > 0]
    d["emph_per_s"] = st.median(dens) if dens else None
    for k in ("tok", "unc", "leg", "out_s", "emph", "emph_per_s", "mg"):
        v = d.get(k)
        print(f"    {k:<12} {('%.4f' % v) if isinstance(v,float) and v<1 else v}")
    return d

pre = cut([x for x in rows if PRE_LO <= str(x["created_at"]) < PRE_HI], f"PRE-FLIP  (< {FLIP})")
post = cut([x for x in rows if str(x["created_at"]) >= FLIP], f"POST-FLIP (>= {FLIP})")

if pre and post:
    print("\n  ── AGAINST THE PRE-REGISTRATION ──")
    for k, pred in (("tok", -36), ("unc", -60), ("leg", -41)):
        a, b = pre.get(k), post.get(k)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a:
            print(f"    {k:<6} {a:>10.0f} -> {b:>10.0f}   {(b-a)/a*100:+6.1f}%   "
                  f"(predicted {pred:+d}%)")
    print("\n  ── THE RESIDUALS (quality; this is a COST lever) ──")
    for k in ("emph", "emph_per_s", "mg"):
        a, b = pre.get(k), post.get(k)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a:
            print(f"    {k:<12} {a:.3f} -> {b:.3f}   {(b-a)/a*100:+.1f}%")
    ea, eb = pre.get("emph_per_s"), post.get("emph_per_s")
    if isinstance(ea, float) and isinstance(eb, float) and ea:
        drop = (eb - ea) / ea * 100
        print(f"\n  VERDICT: emphasis density {drop:+.1f}%. "
              + ("QUALITY REGRESSION — quality wins over speed; the tokens do "
                 "not buy this back." if drop <= -15 else
                 "within tolerance on this sample."))
else:
    print("\n  Cannot compare — one side is empty. Not a result.")
