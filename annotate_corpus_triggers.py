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
    # CASE-SENSITIVE, DELIBERATELY (fixed 2026-08-17). This pattern was matched
    # with re.I, which makes [A-Z] match lowercase — so "I'm paying", "I'm sure"
    # and "I'm not" all scored as self-introductions. Measured on the component
    # candidates: EVERY "spoken name" hit was a false positive. A corpus built on
    # that would have reported "brand_copy declined 0/11" on sources where no
    # name is ever spoken — manufacturing exactly the decline this file exists to
    # prevent. The third tuple element is `ignorecase`; only patterns that do not
    # depend on capitalisation may set it True.
    "brand_copy": [
        (r"\b(?:I'?m|My name is|This is|I am)\s+[A-Z][a-z]+", "self-introduction", False),
        (r"\b(founder|ceo|co-?founder|partner|director|manager|coach|attorney|owner|"
         r"realtor|trainer|therapist)\b", "stated role", True),
        (r"\b(?:here at|welcome to|we at|at)\s+[A-Z][A-Za-z]{2,}", "brand/company", False),
        (r"@\w{2,}|\b[a-z0-9-]+\.(?:com|io|co|app)\b", "handle or URL", True),
    ],
    # generated_scenes: "a STATED NUMBER or stat" / "a NAMED CONCEPT or OBJECT
    # the words make concrete" / "a CLAIM the footage cannot show"
    "scenes": [
        (r"\$[\d,.]+|\b\d[\d,.]*\s*(?:million|billion|thousand|percent|%|k\b|x\b)|"
         r"\b\d{2,}\b", "stated number/stat", True),
        (r"\b(lock|key|folder|graph|chart|map|door|ladder|bridge|clock|scale|"
         r"mountain|puzzle)\b", "named concrete object", True),
        (r"\b(before and after|used to|now i|compared to|instead of|imagine)\b",
         "claim the footage cannot show", True),
    ],
    # payoff zoom: a build that RESOLVES — the arc needs a landing
    "payoff": [
        (r"\b(and that'?s why|so that'?s|the point is|here'?s the thing|"
         r"which means|that'?s how)\b", "resolution phrase", True),
    ],
    # broll_clips (CUTAWAYS). Added 2026-08-24: the corpus annotated brand_copy,
    # scenes and payoff but had NO cutaway trigger, so no source could honestly
    # be called "trigger-bearing" for the mixed cutaway arm. Picking one anyway
    # risks the exact failure this file exists to prevent — an empty broll_clips
    # that is a CORRECT decline, read as an arm that produced nothing.
    #
    # Mirrors the directive's own cutaway language (the coupling above is
    # deliberate): "the concrete nouns named during build are the cutaway
    # candidates", and a SINGLE NAMED REAL ENTITY — "a named place, landmark,
    # city, real object, or real event the dialogue points at" — which the
    # directive calls "often the single most valuable cutaway in the video".
    #
    # DELIBERATELY NOT A TRIGGER: the directive's mode (4) says an ABSTRACT word
    # ("quality", "value", "powerful", "easy", "simple") HOLDS on the speaker.
    # Matching those would manufacture a trigger where the correct behaviour is
    # to stay on the face.
    "broll": [
        # A named real entity: a capitalised word that is NOT sentence-initial,
        # so it is a name rather than a sentence start. CASE-SENSITIVE, and the
        # reason is the scar on brand_copy above — matching this with re.I makes
        # [A-Z] match lowercase, and EVERY hit becomes a false positive.
        # MEASURED ON THE REAL CORPUS BEFORE TRUSTING IT (2026-08-24): the first
        # cut of this pattern matched "in November", "in The" and "to App" —
        # a month, an article and a truncation. Three of five candidates were
        # false positives, which is the brand_copy scar repeating: a trigger
        # that fires on a month sends the arm to a source with no cutaway
        # candidate and then reads the correct decline as a failure.
        # The stoplist is therefore part of the pattern, not a filter bolted on.
        (r"(?<![.!?]\s)(?<!^)\b(?:in|to|from|at|visit|across|around)\s+"
         r"(?!(?:The|A|An|I|My|Our|Your|His|Her|Their|It|This|That|These|Those|"
         r"January|February|March|April|May|June|July|August|September|October|"
         r"November|December|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|"
         r"Sunday|God|English|Spanish|Hindi|Arabic)\b)"
         r"[A-Z][a-z]{3,}", "named place the dialogue points at", False),
        # Concrete physical objects — things a stock clip can literally show.
        # Kept to nouns whose visual is unambiguous; an abstract noun would be a
        # mode-(4) hold, not a cutaway.
        (r"\b(coffee|kitchen|laptop|phone|camera|car|bike|dog|cat|garden|"
         r"whiteboard|notebook|receipt|invoice|package|toolbox|workbench|"
         r"guitar|piano|barbell|treadmill|passport|suitcase)\b",
         "named concrete object", True),
        # Physical ACTION the footage can show — the directive's "physical-action
        # beat" ("real hands working with hand-tools").
        (r"\b(building|cooking|running|driving|writing|typing|filming|"
         r"lifting|painting|packing|shipping|hiking|climbing|welding|"
         r"sanding|planting)\b", "physical action beat", True),
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
            hits = [label for pat, label, ic in pats
                    if re.search(pat, text, re.I if ic else 0)]
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
