#!/usr/bin/env python3
"""THE ONLY CORPUS THAT CAN ANSWER THE SCENE QUESTION. `[Rule 5]`

FOUR selection failures on this one question, each of which scored a CORRECT
DECLINE as a defect:

  REF-2                 already fully edited — declining to decorate finished
                        work is judgment, not a defect (owner ruling 08-17)
  editorial_eng_* pair  no spoken name, no stated number: brand_copy 0/4 was N/A
                        and emitting anything would have been FABRICATION
  frozen goldens        scenes testable on 0 of 12 sources
  component corpus      scenes trigger present, but the source carries its OWN
                        B-ROLL — measured 2026-08-19, the model's decline read
                        "Video contains embedded training B-roll in source",
                        which is CORRECT: the footage already shows the claim

A scene is a composed graphic for a claim THE FOOTAGE CANNOT SHOW. So a source
can only falsify "the model will not emit a scene" if it satisfies all three:

  1. A STATED CLAIM        a number, stat, or named concrete thing, IN THE
                           TRANSCRIPT, recorded verbatim so a decline can be
                           checked against a real trigger
  2. NO B-ROLL IN SOURCE   near-single-shot. Embedded cutaways mean the source
                           already illustrates itself, and declining is right
  3. NO VISUAL PROOF       proxied by (2) + a continuous talking head: if the
                           frame never cuts away, the claim is not being shown

(2) CANNOT BE READ FROM THE DATABASE — analysis_data is empty on stored rows and
no shot-change signal is persisted — so it is PROBED with ffmpeg scdet. That is
the whole reason the previous corpora shipped with this property unchecked.

    python3 build_scene_corpus.py [--limit 40] [--probe 12] [--out scene_corpus_manifest.json]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

ENV = "/Users/zaclibman/content-studio/.env.local"
# A stated claim: a digit, or a spelled number, or a percent/currency figure.
# A STATED CLAIM, not a grammatical artifact. The first version matched "one of
# the most important", "Eu não sou 1 cara" (indefinite article) and "20 August"
# (a date) — and a corpus built on those hands the model beats that do not earn a
# scene, so its CORRECT declines get scored as defects. That is the fifth time
# this exact error would have been made, this time inside the tool written to
# prevent it.
#
# So: a number must carry a UNIT, a MAGNITUDE, or a comparison. A bare digit
# never qualifies.
_NUM = re.compile(
    r"\b\d[\d,\.]*\s*(?:%|percent|per cent|k\b|m\b|bn\b|x\b|times|dollars?|"
    r"euros?|pounds?|reais|rupees?|years?|months?|weeks?|days?|hours?|minutes?|"
    r"seconds?|pounds?|kilos?|kg\b|lbs?\b|miles?|km\b|clients?|customers?|"
    r"users?|people|subscribers?|followers?|sets?|reps?|steps?)"
    r"|[$€£₹]\s?\d[\d,\.]*"
    r"|\b\d[\d,\.]*\s*(?:million|billion|thousand|hundred)\b"
    r"|\b(?:two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|"
    r"fifty|hundred|thousand|million|billion)\s+(?:\w+s\b|percent|times)", re.I)
# A claim the footage cannot show — comparative//promise language.
_CLAIM = re.compile(
    r"\b(?:before and after|used to|now i|instead of|versus|vs\.?|compared to|"
    r"the difference|turns out|the result|which means|that means|so that)\b", re.I)


def _latin_share(text):
    """Fraction of letters in Latin script — a cheap language proxy.

    LANGUAGE IS A CORPUS PROPERTY, NOT AN ACCIDENT. The first build kept 3
    non-English sources of 4 purely by what surfaced. That is defensible (the
    product's traffic IS multilingual and lang routing is live) but it must be a
    STATED choice: on a non-English source I cannot eyeball whether a scene
    SHOULD have fired, so a zero there rests entirely on the transcript match.
    """
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    latin = sum(1 for ch in letters if ord(ch) < 0x250)
    return latin / len(letters)


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


def _shot_changes(video_url, dur):
    """Count scene cuts with ffmpeg scdet. THE PROPERTY NO PREVIOUS CORPUS
    CHECKED: a source with cutaways already illustrates its own claims, so a
    decline there is correct and scoring it as a defect manufactures a signal.

    Returns (count, ok). ok=False means the probe FAILED — which is NOT the same
    as zero cuts, and a failed probe must never be read as 'single shot'
    (project_probe_collapse_class).
    """
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


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--probe", type=int, default=12)
    ap.add_argument("--out", default="scene_corpus_manifest.json")
    a = ap.parse_args(argv)
    url, key = _creds()

    rows = _get(url, key,
                "video_jobs?select=id,user_id,created_at,video_url,source_duration,"
                "transcript,vibe_input&status=eq.completed&transcript=not.is.null"
                f"&video_url=not.is.null&order=created_at.desc&limit={a.limit * 6}")
    print(f"  scanned {len(rows)} completed jobs with transcripts")

    cands = []
    for r in rows:
        d = float(r.get("source_duration") or 0)
        if not (15.0 <= d <= 90.0):          # the product's own band
            continue
        t = r.get("transcript") or {}
        text = t.get("text") if isinstance(t, dict) else (t if isinstance(t, str) else "")
        if not text or len(text) < 80:
            continue
        nums = _NUM.findall(text)
        claims = _CLAIM.findall(text)
        if not nums and not claims:
            continue
        # A DATE IS NOT A STAT. "20 August" carries a unit-shaped token but makes
        # no claim a graphic could show.
        if nums and not claims and re.search(
                r"\b\d+\s*(?:January|February|March|April|May|June|July|August|"
                r"September|October|November|December)\b", text, re.I) \
                and len(nums) <= 1:
            continue
        # THE TRIGGER, VERBATIM. A decline is only checkable against the exact
        # phrase that should have triggered a scene.
        m = _NUM.search(text) or _CLAIM.search(text)
        i = max(0, m.start() - 60)
        cands.append({
            "id": r["id"], "video_url": r["video_url"],
            "duration_s": round(d, 1), "vibe": r.get("vibe_input"),
            "trigger_kind": "stated_number" if nums else "claim_not_shown",
            "trigger_verbatim": text[i:m.end() + 60].strip(),
            "n_numerals": len(nums), "n_claims": len(claims),
            "latin_share": round(_latin_share(text), 2),
            "likely_english": _latin_share(text) > 0.85,
        })
    print(f"  {len(cands)} carry a stated claim in the product's duration band")

    kept, rejected = [], []
    for c in cands[:a.probe]:
        n, ok = _shot_changes(c["video_url"], c["duration_s"])
        c["shot_changes"], c["shot_probe_ok"] = n, ok
        if not ok:
            # A FAILED PROBE IS NOT A ZERO. Excluded, and said so.
            c["reject"] = "shot probe FAILED — not counted as single-shot"
            rejected.append(c)
        elif n > 2:
            c["reject"] = f"{n} shot changes — the source carries its own B-roll"
            rejected.append(c)
        else:
            kept.append(c)
        print(f"    {c['id'][:8]}  {c['duration_s']:5.1f}s  cuts={n if ok else 'PROBE-FAIL'}"
              f"  {'KEEP' if 'reject' not in c else 'reject: ' + c['reject'][:44]}")

    out = {"built": "2026-08-19", "criteria": {
        "stated_claim": "numeral or claim-not-shown language, recorded verbatim",
        "no_broll": "<=2 scene cuts (ffmpeg scdet), PROBED not assumed",
        "duration_band": "15-90s",
    }, "why": (
        "Four prior corpora scored CORRECT DECLINES as defects: REF-2 (already "
        "edited), the editorial_eng pair (no trigger at all), the frozen goldens "
        "(scenes testable on 0/12), and the component corpus (source carries its "
        "own B-roll — the model said so). A scene answers a claim the footage "
        "CANNOT show, so only a source with a claim and no cutaway can falsify "
        "'the model will not emit a scene'."
    ), "sources": kept, "rejected": rejected}
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=1)
    _eng = [k for k in kept if k.get("likely_english")]
    print(f"\n  KEPT {len(kept)} / probed {len(kept) + len(rejected)}  -> {a.out}")
    print(f"  ENGLISH share: {len(_eng)}/{len(kept)}"
          f"{'' if not kept else f'  ({100.0 * len(_eng) / len(kept):.0f}%)'}")
    if kept and len(_eng) * 2 < len(kept):
        print("  *** FEWER THAN HALF ENGLISH. This is a STATED finding, not an "
              "oversight: on a non-English source I cannot eyeball whether a "
              "scene SHOULD have fired, so a zero there rests on the transcript "
              "match alone. Either raise --probe until the English share is "
              "half, or read the result knowing it.")
    if len(kept) < 3:
        print("  *** FEWER THAN 3 USABLE SOURCES. Do not run the arm on this: a "
              "corpus this small cannot separate 'will not emit' from 'this "
              "particular source did not need one'. Raise --probe and re-run.")
    for k in kept[:6]:
        print(f"    {k['id'][:8]} [{k['trigger_kind']}] \"{k['trigger_verbatim'][:80]}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
