#!/usr/bin/env python3
"""THE INVERSE CORPUS — sources where EvidenceCard and DeviceMockup CAN fire.

WHY THIS EXISTS, STATED AS THE MISTAKE IT FIXES. The four generation-free
compositions were measured on the SCENE corpus and came back requested 0/3. For
NumberCard that was a real result. For EvidenceCard and DeviceMockup it was
VACUOUS, and the corpus's own selection rule says why:

    scene corpus:  "a scene is a composed graphic for a claim THE FOOTAGE
                    CANNOT SHOW" -> stated_claim + NO B-ROLL + near-single-shot
    cada6a1b:      shot_changes = 0

EvidenceCard's trigger is the EXACT INVERSE — "the proof is a THING and it is
already in the footage". DeviceMockup needs a screen on camera. Scoring them on
sources selected for having no visual proof is scoring a component against a
source that cannot trigger it — the error class this repo already keeps a gate
check for. This corpus inverts the rule.

SELECTION:
  1. SHOT CHANGES PRESENT  >=3 scene cuts, PROBED with ffmpeg scdet, never
     assumed. A failed probe is recorded as FAILED, never as zero
     (project_probe_collapse_class).
  2. DURATION BAND         15-90s, same as the scene corpus, so the two are
     comparable.
  3. VISUAL TRIGGER        an object, screen, or artifact actually on camera.

CLAUSE 3 IS NOT MECHANICALLY DECIDABLE AND THIS SCRIPT DOES NOT PRETEND IT IS.
scdet counts cuts; it cannot tell a receipt from a jump cut between two talking
heads. So every candidate gets FRAMES EXTRACTED to disk for a human (or a vision
pass) to confirm, and the manifest records `visual_trigger: "UNCONFIRMED"` until
someone looks. A corpus that asserts a trigger it never checked is how four
previous corpora were invalidated.

    python3 build_evidence_corpus.py --limit 8
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

ENV = os.path.expanduser("~/content-studio/.env.local")
OUT = "evidence_corpus_manifest.json"
FRAMES = "evidence_corpus_frames"


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


def _shot_changes(video_url):
    """(count, ok). ok=False means the PROBE FAILED — not zero cuts."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-v", "info", "-i", video_url,
             "-vf", "scdet=threshold=10", "-an", "-f", "null", "-"],
            capture_output=True, text=True, timeout=420)
        hits = len(re.findall(r"lavfi\.scd\.score", r.stderr or ""))
        if r.returncode != 0 and hits == 0:
            return -1, False
        return hits, True
    except Exception:
        return -1, False


def _grab(video_url, dur, job_id):
    """Frames at 25/50/75% so clause 3 can be CONFIRMED BY EYE, not assumed."""
    os.makedirs(FRAMES, exist_ok=True)
    got = []
    for frac in (0.25, 0.5, 0.75):
        t = max(0.5, (dur or 30.0) * frac)
        out = os.path.join(FRAMES, f"{job_id[:8]}_{int(frac * 100)}.jpg")
        try:
            r = subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", video_url,
                 "-frames:v", "1", "-vf", "scale=480:-2", out],
                capture_output=True, text=True, timeout=180)
            if r.returncode == 0 and os.path.exists(out):
                got.append(out)
        except Exception:
            continue
    return got


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--min-cuts", type=int, default=3)
    a = ap.parse_args(argv)

    url, key = _creds()
    rows = _get(url, key,
                "video_jobs?select=id,user_id,created_at,video_url,source_duration,"
                "transcript,vibe_input&status=eq.completed&video_url=not.is.null"
                f"&order=created_at.desc&limit={a.limit * 12}")
    print(f"  candidates pulled: {len(rows)}")

    seen_users, out = set(), []
    probe_failed = 0
    for r in rows:
        if len(out) >= a.limit:
            break
        dur = float(r.get("source_duration") or 0)
        if not (15.0 <= dur <= 90.0):
            continue
        # ONE SOURCE PER USER — a corpus that is five videos from one creator is
        # one opinion measured five times (Rule 7).
        if r.get("user_id") in seen_users:
            continue
        n, ok = _shot_changes(r["video_url"])
        if not ok:
            probe_failed += 1
            print(f"    {r['id'][:8]} PROBE FAILED — excluded, NOT counted as 0 cuts")
            continue
        if n < a.min_cuts:
            continue
        seen_users.add(r.get("user_id"))
        frames = _grab(r["video_url"], dur, r["id"])
        out.append({
            "id": r["id"], "video_url": r["video_url"],
            "duration_s": round(dur, 1),
            "vibe": (r.get("vibe_input") or "Make it viral")[:400],
            "shot_changes": n, "shot_probe_ok": True,
            "frames": frames,
            # THE HONEST FIELD. Nothing has looked at these pixels yet.
            "visual_trigger": "UNCONFIRMED",
        })
        print(f"    {r['id'][:8]}  cuts={n:3}  dur={dur:5.1f}s  frames={len(frames)}")

    man = {
        "criteria": {
            "shot_changes": f">= {a.min_cuts} scene cuts (ffmpeg scdet), PROBED",
            "duration_band": "15-90s",
            "one_per_user": True,
            "visual_trigger": "UNCONFIRMED until frames are inspected — clause 3 "
                              "is not mechanically decidable",
        },
        "inverse_of": "scene_corpus_manifest.json (no-broll / claim-not-shown)",
        "purpose": "EvidenceCard + DeviceMockup can only fire where the footage "
                   "HOLDS the proof; the scene corpus selected for the opposite.",
        "probe_failed": probe_failed,
        "sources": out,
    }
    with open(OUT, "w") as fh:
        json.dump(man, fh, indent=1)
    print(f"\n  wrote {OUT}: {len(out)} source(s), {probe_failed} probe failure(s)")
    print(f"  frames -> {FRAMES}/   INSPECT THEM before running any arm: "
          f"visual_trigger is UNCONFIRMED.")
    return 0 if out else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
