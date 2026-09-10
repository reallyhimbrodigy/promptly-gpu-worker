#!/usr/bin/env python3
"""GENERATE reference_index.json from the reference corpus. Never hand-written.

Zac, 2026-09-09: "Generate it from the corpus, don't hand-write it, so it can't
drift from what the examples actually do, and so it regenerates when the corpus
grows."

RUN IT WHERE THE CREDENTIALS ARE:
    SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 build_reference_index.py

It writes reference_index.json beside itself. The file is MOUNTED into the image
and read at brief time — no network, no model turn, no agent decision.

WHY A FILE AND NOT A QUERY. The whole corpus is 36,875 bytes, smaller than one
knowledge doc. There is no retrieval infrastructure to build: the index ships
with the image and the match is a sort.

WHAT IT RECORDS PER BEAT, and each field earns its place in the match:
    purpose      the join key — the corpus's vocabulary (hook|claim|turn|
                 evidence|payoff|close|breath) against which the agent already
                 answers arc position for zoom
    dur          beat duration; a 0.82s breath and a 3.98s close are different
                 moments and want different treatment
    treat        WHAT WAS PLACED — the answer being retrieved
    spk          speaker on screen; cards land with the speaker OFF
    card_text    what was on the card, when there was one
    read         WHY IT LANDED THERE. The craft. This is the payload.

COMPLETENESS IS REPORTED, NOT ASSUMED. `beats_in_corpus` is what the corpus
holds; `beats` is what this file carries. If they differ the retrieval says so
rather than presenting a partial index as the corpus.
"""
import json
import os
import sys
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference_index.json")


def fetch(url, key, path):
    req = urllib.request.Request(
        f"{url}/rest/v1/{path}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
    if not (url and key):
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required — this "
              "script regenerates the index and cannot invent it.", file=sys.stderr)
        return 2
    beats = fetch(url, key,
                  "reference_beats?select=beat_index,duration_s,purpose,treatment,read,raw"
                  "&order=reference_id,beat_index")
    out = []
    for b in beats:
        raw = b.get("raw") or {}
        out.append({
            "i": b.get("beat_index"),
            "purpose": b.get("purpose"),
            "dur": round(float(b.get("duration_s") or 0), 2),
            "treat": b.get("treatment") or [],
            "spk": str(raw.get("speaker_on_screen")).lower() == "true",
            "card_text": (raw.get("card_text") or None),
            "read": b.get("read") or "",
        })
    # PER-FAMILY CORPUS COUNTS, recorded here so a PARTIAL index can never
    # report its own size as the corpus's. A seeded index saying "only 4
    # examples of sfx in the whole corpus" when the corpus has 14 is precisely
    # the absence-misreported-as-a-finding this feature exists to prevent.
    fam_counts = {}
    for b in out:
        for t in (b.get("treat") or []):
            fam_counts[t] = fam_counts.get(t, 0) + 1
    doc = {"beats_in_corpus": len(out), "family_counts_in_corpus": fam_counts,
           "beats": out, "source": "reference_beats"}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=0)
    print(f"wrote {OUT}: {len(out)} beats, {os.path.getsize(OUT)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
