#!/usr/bin/env python3
"""THE RANKED CAPABILITY LIST — supply x demand, for every family we cannot build.

SUPPLY  what Zac's ten reference videos DO, from the merged two-arm reading.
        Carried per arm: a family both a silent reader and a hearing reader
        found is CORROBORATED and is stronger evidence than either alone.
DEMAND  how many USERS ask for it by name, from 11,723 real requests.
        Users, not requests — one user asking forty times is a habit.

Written by joining reference_vocabulary_merged.json (supply) with
demand_by_family.json (demand) and an explicit, reviewable build assessment.
"""
import json

SUP = json.load(open("reference_vocabulary_merged.json"))
DEM = json.load(open("demand_by_family.json"))

# status, nearest shipped thing, what building it takes. EXPLICIT because a
# capability claim inferred in a .get() default is one nobody can correct.
BUILD = {
 "Platform outro/end card": ("ROUTE", "EndCard (ships)",
   "Route a ruling to EndCard. No new component."),
 "Cursor/UI callout highlight": ("ROUTE", "Reticle / AnnotationArrow / MouseDrag (ship)",
   "Route + a cursor position per beat. No new component."),
 "Automated progress/loading indicator": ("ROUTE", "ProgressBar (ships)",
   "Route a ruling to ProgressBar. No new component."),
 "Split-screen comparison of two contents": ("ROUTE", "EvidenceCard / DeviceMockup (ship)",
   "Route + two source spans. No new component."),
 "Typed search/URL graphic": ("ROUTE", "Stamp / DropBanner (ship)",
   "Route + the string to type. Closest, not exact."),
 "Simple stat/emoji graphic overlay": ("ROUTE", "EmojiCard (ships)",
   "Route a ruling to EmojiCard. No new component."),
 "Step-by-step caption narration over demo": ("ROUTE", "StepDivider / SectionDivider (ship)",
   "Route + step text per beat. No new component."),
 "Floating labeled UI/graphic elements": ("ROUTE", "PillCluster (ships)",
   "Route a ruling to PillCluster. No new component."),
 "Floating people/location graphic": ("ROUTE", "PillCluster / NamePlate (ship)",
   "Route a ruling. No new component."),
 "Full-screen title/thesis card": ("ROUTE", "EditorialQuote / SectionDivider (ship)",
   "Route a ruling. No new component."),
 "3D icon animation": ("ROUTE?", "DeviceMockup (ships) — not 3D",
   "Nearest ships but is not the same move. Needs a real 3D path."),
 "Escalating counter/stat ticking animation": ("BEHAVIOUR", "StatCard (REACHABLE, static)",
   "Component reachable, wrong behaviour: add a count-up to StatCard."),
 "Dominant kinetic title text synced to speech": ("BUILD", "text family (overlay only)",
   "Frame-dominant kinetic type synced to word timing. New."),
 "Decorative per-word caption styling": ("CAPTION LAYER", "caption layer (runs every job)",
   "Expose per-word style on the existing caption layer."),
 "Colored keyword highlight within captions": ("CAPTION LAYER", "caption layer (runs every job)",
   "Expose per-word colour on the existing caption layer."),
 "Word-by-word caption build": ("CAPTION LAYER", "caption layer (runs every job)",
   "Expose per-word reveal timing on the existing caption layer."),
 "3D perspective UI/gallery browse graphic": ("BUILD", "nothing close",
   "No 3D compositor exists."),
 "Polaroid-style graphic reveal": ("BUILD", "nothing close",
   "No photo-frame component."),
 "Logo idle branding animation": ("BUILD", "nothing close",
   "Needs a brand-asset pipeline (user logo upload)."),
 "Split-screen picture-in-picture": ("BUILD", "nothing close",
   "No PIP compositor."),
 "Whoosh/Pop Accent SFX": ("BUILDABLE NOW", "place_sfx + sfx inventory (SHIP)",
   "Nothing to build. Never placed because the corpus could not hear it."),
 "Click/Interaction SFX": ("BUILDABLE NOW", "place_sfx + sfx inventory (SHIP)",
   "Nothing to build. Same cause."),
}
# ROUTE? sorts INSIDE route — it is the same tier of work with a weaker match,
# not a tier of its own. Giving it an equal TIER value but a different label
# split the ROUTE block in two and printed the header twice.
TIER = {"BUILDABLE NOW": 0, "ROUTE": 1, "ROUTE?": 1, "CAPTION LAYER": 2,
        "BEHAVIOUR": 3, "BUILD": 4}
GROUP = {"ROUTE?": "ROUTE"}

rows = []
for f in SUP["families"]:
    fam = f["family"]
    if fam not in BUILD:
        continue
    st, near, how = BUILD[fam]
    d = DEM.get(fam, {})
    rows.append({
        "family": fam, "status": st, "nearest": near, "how": how,
        "arms": f["arms"], "evidence": f["evidence"],
        "sil": f["videos_silent"], "heard": f["videos_heard"],
        "supply": f["videos_max"],
        "users": d.get("users", 0), "pct": d.get("pct_users", 0.0),
        "reqs": d.get("requests", 0),
    })
rows.sort(key=lambda r: (TIER[r["status"]], -r["users"], -r["supply"]))
json.dump({"corpus": {"jobs": 11723, "users": 7960, "distinct_texts": 5921,
                      "source": "video_jobs.vibe_input, whitespace+case normalised"},
           "reference": {"videos": SUP["n_videos"],
                         "arm_a": SUP["arm_a"], "arm_b": SUP["arm_b"]},
           "rows": rows}, open("CAPABILITY_RANKING.json", "w"), indent=1)

print(f"  SUPPLY  {SUP['n_videos']} reference videos, two arms "
      f"(silent=claude/frames, heard=gemini/clip+audio)")
print(f"  DEMAND  11,723 requests · 5,921 distinct · 7,960 users "
      f"(video_jobs.vibe_input)\n")
hdr = f"  {'users':>6} {'%':>6} │ {'sil':>4} {'heard':>5} {'ev':>6} │ family"
cur = None
for r in rows:
    _g = GROUP.get(r["status"], r["status"])
    if _g != cur:
        cur = _g
        print(f"\n  ══ {cur} ══")
        print(hdr)
    ev = "BOTH" if r["evidence"] == "CORROBORATED" else (
        "heard" if r["arms"] == "heard" else "silent")
    _q = "?" if r["status"] == "ROUTE?" else " "
    print(f"  {r['users']:>6} {r['pct']:>5.1f}% │ {r['sil']:>2}/10 {r['heard']:>3}/10 "
          f"{ev:>6} │{_q}{r['family'][:44]}")
    print(f"  {'':>6} {'':>6} │ {'':>13} │   -> {r['nearest']}")
print(f"\n  written CAPABILITY_RANKING.json ({len(rows)} families)")
