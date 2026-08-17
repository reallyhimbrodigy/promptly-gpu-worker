#!/usr/bin/env python3
"""ANNOTATE THE A/B CORPUS WITH TRIGGER PRESENCE. `[Rule 5]`

WHY THIS EXISTS — two corpora in a row chosen for the wrong property.

  REF-2   picked because it is a golden reference. It is an ALREADY-EDITED video,
          so the planner declined scenes and MGs with sound judgment
          ("already contains bespoke 3D motion graphics... declined extra scenes
          to prevent clutter"). A finished source cannot measure whether the
          planner will decorate a raw one.

  editorial_eng_*  picked on route + language + duration. Both are raw, but
          NEITHER contains a spoken name, role, brand or handle, and neither
          states a number. So `brand_copy: 0/4` is N/A, NOT a decline — a planner
          emitting brand copy there would be FABRICATING, which the directive
          explicitly forbids.

Both times the sources were selected on properties that had nothing to do with
the component under test, and both times the result would have read as a
component failure. A component with no trigger in the source is a CORRECT
decline; counting it as a defect manufactures a signal out of nothing.

THE FIX IS SELECTION, NOT INSPECTION. Checking triggers after the fact (which is
how both were caught) still wastes the run. Annotating the manifest lets a
harness pick sources BECAUSE they contain what is being measured.

FREE. Transcripts already live in video_jobs.transcript for corpus job_ids —
no transcription, no Modal, no model call.

    python3 annotate_corpus_triggers.py           # report
    python3 annotate_corpus_triggers.py --write   # write trigger blocks into the manifest
"""
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "fps_ab_corpus_manifest.json")
ENV = "/Users/zaclibman/content-studio/.env.local"

# Each pattern set mirrors the DIRECTIVE's own trigger language, so "has a
# trigger" means the same thing here as it does in the prompt. If a directive's
# triggers change, these must change with it — that coupling is deliberate.
TRIGGERS = {
    # _BrandCopy: "the speaker SAYS their own name, or introduces themselves by
    # role" / "a BRAND, COMPANY OR HANDLE is spoken or legible"
    "brand_copy": [
        (r"\b(?:i'?m|my name is|this is|i am)\s+[A-Z][a-z]+", "self-introduction"),
        (r"\b(founder|ceo|co-?founder|partner|director|manager|coach|attorney|owner|"
         r"realtor|trainer|therapist)\b", "stated role"),
        (r"\b(?:here at|welcome to|we at|at)\s+[A-Z][A-Za-z]{2,}", "brand/company"),
        (r"@\w{2,}|\b[a-z0-9-]+\.(?:com|io|co|app)\b", "handle or URL"),
    ],
    # generated_scenes: "a STATED NUMBER or stat" / "a NAMED CONCEPT or OBJECT
    # the words make concrete" / "a CLAIM the footage cannot show"
    "scenes": [
        (r"\$[\d,.]+|\b\d[\d,.]*\s*(?:million|billion|thousand|percent|%|k\b|x\b)|"
         r"\b\d{2,}\b", "stated number/stat"),
        (r"\b(lock|key|folder|graph|chart|map|door|ladder|bridge|clock|scale|"
         r"mountain|puzzle)\b", "named concrete object"),
        (r"\b(before and after|used to|now i|compared to|instead of|imagine)\b",
         "claim the footage cannot show"),
    ],
    # payoff zoom: a build that RESOLVES — the arc needs a landing
    "payoff": [
        (r"\b(and that'?s why|so that'?s|the point is|here'?s the thing|"
         r"which means|that'?s how)\b", "resolution phrase"),
    ],
}


def _creds():
    env = {}
    with open(ENV) as fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return (env.get("SUPABASE_URL"),
            env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY"))


def main(argv):
    man = json.load(open(MANIFEST))
    srcs = man["sources"]
    url, key = _creds()
    ids = [s["job_id"] for s in srcs if s.get("job_id")]
    req = urllib.request.Request(
        f"{url.rstrip('/')}/rest/v1/video_jobs?select=id,transcript&id=in.({','.join(ids)})",
        headers={"apikey": key, "Authorization": f"Bearer {key}"})
    rows = {r["id"]: r for r in json.load(urllib.request.urlopen(req, timeout=90))}

    n_annot = 0
    print(f"{'id':28} {'brand':>6} {'scenes':>7} {'payoff':>7}  evidence")
    for s in srcs:
        row = rows.get(s.get("job_id")) or {}
        tr = row.get("transcript") or {}
        text = (tr.get("text") if isinstance(tr, dict) else "") or ""
        if not text:
            # NO TRANSCRIPT IS NOT "NO TRIGGERS". Recording it as unknown keeps a
            # missing measurement distinguishable from a measured absence — the
            # distinction this project keeps paying to relearn.
            s.setdefault("triggers", {})["_status"] = "unknown_no_transcript"
            print(f"{s['id']:28} {'?':>6} {'?':>7} {'?':>7}  (no transcript stored)")
            continue
        found = {}
        for comp, pats in TRIGGERS.items():
            hits = [label for pat, label in pats
                    if re.search(pat, text, re.I)]
            found[comp] = hits
        s["triggers"] = {k: v for k, v in found.items()}
        s["triggers"]["_status"] = "measured"
        s["triggers"]["_transcript_words"] = len(text.split())
        n_annot += 1
        print(f"{s['id']:28} {str(bool(found['brand_copy'])):>6} "
              f"{str(bool(found['scenes'])):>7} {str(bool(found['payoff'])):>7}  "
              f"{','.join(found['brand_copy'] + found['scenes'])[:52]}")

    print(f"\n  annotated: {n_annot}/{len(srcs)}  (transcript present)")
    for comp in TRIGGERS:
        ok = [s["id"] for s in srcs
              if s.get("triggers", {}).get("_status") == "measured"
              and s["triggers"].get(comp)]
        print(f"  sources that can TEST {comp:12}: {len(ok)}  {ok[:4]}")
    print("\n  A source with NO trigger for a component is N/A for that component —")
    print("  a correct decline, never a defect. Selecting on this is what makes the")
    print("  next A/B answer the question it was run to answer.")

    if "--write" in argv:
        man["trigger_annotation"] = {
            "added": "2026-08-17",
            "why": "two corpora in a row were selected on properties unrelated to "
                   "the component under test; a source without a trigger is N/A, "
                   "not a decline",
            "patterns_mirror": "the directives' own trigger language in handler.py "
                               "(_BrandCopy docstring, GENERATED SCENES block)",
        }
        json.dump(man, open(MANIFEST, "w"), indent=1, sort_keys=True)
        print(f"\n  WROTE trigger blocks into {os.path.basename(MANIFEST)}")
    else:
        print("\n  (report only — pass --write to annotate the manifest)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
