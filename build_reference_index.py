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

# THE LEGACY SUPABASE PATH ONLY. `reference_beats` holds rows produced by the
# CLOSED-ENUM annotator — six names, no transition — so an index built from that
# table can only ever contain these, and a reader with only the counts cannot
# tell "never offered" from "offered and never chosen". That is the confusion
# that made `transition: 0 of 153` read as behaviour for the life of the corpus.
#
# THE RECORDS PATH DOES NOT USE THIS. build_reference_records.py now names
# freely and cluster_reference_vocabulary.py discovers the families, so the
# vocabulary is a RESULT and is written from vocabulary.json. A constant there
# would be the enum coming back through the side door.
CORPUS_VOCABULARY = {"cut", "punch_in", "cutaway", "card", "overlay_text", "sfx"}


def fetch(url, key, path):
    req = urllib.request.Request(
        f"{url}/rest/v1/{path}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def from_records(d, fam_of=None, arm=""):
    """Build the index from a directory of per-video records. Same shape.

    ONE BUILDER, TWO SOURCES — not a second script. The Supabase path needs
    credentials this lane does not hold, and a re-read that cannot be turned
    into an index is a re-read nobody can act on. The row shape is the same
    either way, so the only thing that differs is where the beats come from.

    STATE IS READ, NOT INFERRED. A FAILED video is NAMED and excluded; it must
    never shrink the corpus silently, because an index built from 8 of 10
    videos that reports itself as the corpus is exactly the partial-index
    failure `beats_in_corpus` exists to prevent.
    """
    out, used, skipped = [], [], []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".mp4.json"):
            continue
        try:
            rec = json.load(open(os.path.join(d, fn), encoding="utf-8"))
        except Exception as e:                                    # noqa: BLE001
            skipped.append((fn, f"UNREADABLE: {type(e).__name__}"))
            continue
        if rec.get("state") != "MEASURED":
            skipped.append((fn, rec.get("state") or "NO STATE"))
            continue
        beats = (rec.get("record") or {}).get("beats") or []
        if not beats:
            skipped.append((fn, "MEASURED but no beats — treat as FAILED"))
            continue
        used.append(fn)
        for b in beats:
            t0, t1 = b.get("t_start"), b.get("t_end")
            # TWO VOCABULARIES ON EVERY BEAT, AND THEY ARE NOT THE SAME THING.
            # `treat_raw` is what the annotator actually said, in its own words,
            # with no family list in front of it. `treat` is the DISCOVERED
            # family that observation was clustered into by pass 2. Keeping only
            # the family would throw away the evidence the family was derived
            # from; keeping only the raw names would give the decision surface
            # 150 names it cannot aggregate. Both, always.
            raw = [t.get("name") for t in (b.get("treatment") or [])
                   if isinstance(t, dict) and t.get("name")]
            out.append({
                "i": b.get("beat_index"),
                "purpose": b.get("purpose"),
                "dur": round(float(t1) - float(t0), 2)
                       if (t0 is not None and t1 is not None) else 0.0,
                "treat": sorted({fam_of.get(n, n) for n in raw}) if fam_of
                         else sorted(set(raw)),
                "treat_raw": raw,
                # WHAT EACH ONE DOES, kept beside the name. An open vocabulary
                # whose names arrive without their effect is a list of labels,
                # and this corpus has been read as measurement before.
                "does": {t["name"]: t.get("what_it_does", "")
                         for t in (b.get("treatment") or [])
                         if isinstance(t, dict) and t.get("name")},
                "spk": str(b.get("speaker_on_screen")).lower() == "true",
                "card_text": (b.get("card_text") or None),
                "read": b.get("read") or "",
                # WHY IT IS GOOD, not just why it is there. The material a
                # six-value enum structurally could not hold.
                "craft": (b.get("craft") or None),
                # WHICH READER SAW THIS. Provenance survives the derivation, the
                # way treat_raw sits beside treat.
                "arm": arm,
            })
    return out, used, skipped


def main():
    if "--from-records" in sys.argv:
        # MULTIPLE DIRS = MULTIPLE ARMS, AND BOTH ARE CARRIED. The ten videos
        # were read twice: once from silent frames (richer on visual craft) and
        # once from the clip with audio (the only arm that can hear). Neither is
        # a superset — collapsing to one throws away whichever half the winner
        # is weaker at, and the half the silent arm is missing is SOUND, which
        # is in 10 of 10 videos.
        #
        # Both arms' beats go in, each tagged. A family two independent readers
        # both found then counts higher at a purpose WITHOUT anyone asserting
        # that it should — the corroboration emerges from the data.
        dirs = []
        _i = sys.argv.index("--from-records") + 1
        while _i < len(sys.argv) and not sys.argv[_i].startswith("--"):
            dirs.append(sys.argv[_i]); _i += 1
        d = dirs[0]
        # THE DISCOVERED FAMILIES, if pass 2 has run. Without them the index
        # carries raw names only and says so, rather than silently presenting
        # 150 one-off observations as a vocabulary.
        fam_of, vocab = {}, None
        vp = os.path.join(d, "vocabulary.json")
        # EVERY ARM'S VOCABULARY, not just the first. A name from arm B with no
        # entry in fam_of would fall through to itself and then have no
        # builds_as entry — vanishing silently from the surface, which is
        # exactly how the first open-vocabulary index emptied it.
        for _vd in dirs[1:]:
            _vp2 = os.path.join(_vd, "vocabulary.json")
            if os.path.exists(_vp2):
                _v2 = json.load(open(_vp2, encoding="utf-8"))
                for _f in _v2.get("families") or []:
                    for _m in _f.get("members") or []:
                        fam_of[_m] = _f["family"]
                for _s2 in _v2.get("singletons") or []:
                    fam_of[_s2] = _s2
        if os.path.exists(vp):
            vdoc = json.load(open(vp, encoding="utf-8"))
            for f in vdoc.get("families") or []:
                for m in f.get("members") or []:
                    fam_of[m] = f["family"]
            for sgl in vdoc.get("singletons") or []:
                fam_of[sgl] = sgl
            vocab = sorted(set(fam_of.values()))
            # THE CAPABILITY CLAIM TRAVELS WITH THE CORPUS. Which harness
            # family can BUILD each discovered one, or null. Written down, not
            # inferred: the first index built from the open-vocabulary pass
            # returned {} from offered_treatments and marked all six families
            # unmeasurable, because the corpus names changed underneath a
            # silent `.get()` and nothing said so. A mapping that lives in a
            # default is a mapping nobody can review.
            bp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "reference_builds_as.json")
            if os.path.exists(bp):
                builds_as = json.load(open(bp, encoding="utf-8"))["builds_as"]
                # SINGLETONS DEFAULT TO UNBUILDABLE, and that is a claim too: a
                # move one editor used once has no family here by definition.
                for sgl in vdoc.get("singletons") or []:
                    builds_as.setdefault(sgl, None)
                _unmapped = sorted(set(vocab) - set(builds_as))
                if _unmapped:
                    print(f"  *** {len(_unmapped)} discovered famil(ies) have "
                          f"no entry in reference_builds_as.json — they would "
                          f"vanish silently from the decision surface:")
                    for u in _unmapped[:10]:
                        print(f"        {u}")
                    return 2
            else:
                print("  *** reference_builds_as.json is missing — every "
                      "discovered family would read as unbuildable")
                return 2
            print(f"  clustered vocabulary: {len(vdoc.get('families') or [])} "
                  f"famil(ies) + {len(vdoc.get('singletons') or [])} singleton(s)")
        else:
            print(f"  NO vocabulary.json in {d} — the index will carry the "
                  f"annotator's RAW names. Run cluster_reference_vocabulary.py "
                  f"first or the decision surface has nothing to aggregate.")
        out, used, skipped = [], [], []
        for _d in dirs:
            _o, _u, _sk = from_records(_d, fam_of, arm=os.path.basename(
                _d.rstrip("/")))
            out.extend(_o); used.extend(_u); skipped.extend(_sk)
            print(f"  arm {os.path.basename(_d.rstrip('/')):22} "
                  f"{len(_u)} video(s), {len(_o)} beats")
        # TEN VIDEOS READ TWICE IS NOT TWENTY VIDEOS. `used` counts
        # arm-video pairs; printing it as a video count would put a doubled
        # denominator into every rate derived from this index, which is the
        # two-numbers-with-the-same-name failure with the same name reused
        # across arms.
        _distinct = len({u.rsplit(".mp4", 1)[0] for u in used})
        print(f"  {_distinct} distinct video(s) x {len(dirs)} reading(s) = "
              f"{len(used)} record(s), {len(out)} beats")
        for fn, why in skipped:
            print(f"  EXCLUDED {fn}: {why}")
        if skipped:
            print("  *** the index below is PARTIAL — it does not carry the "
                  "whole corpus and must not be shipped as though it did")
            return 2
        globals()["READINGS"] = len(dirs)
        globals()["DISTINCT_VIDEOS"] = _distinct
        return write(out, vocab, builds_as)

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
    return write(out, sorted(CORPUS_VOCABULARY), None)


READINGS = 1
DISTINCT_VIDEOS = None


def write(out, vocab=None, builds_as=None):
    # PER-FAMILY CORPUS COUNTS, recorded here so a PARTIAL index can never
    # report its own size as the corpus's. A seeded index saying "only 4
    # examples of sfx in the whole corpus" when the corpus has 14 is precisely
    # the absence-misreported-as-a-finding this feature exists to prevent.
    fam_counts = {}
    for b in out:
        for t in (b.get("treat") or []):
            fam_counts[t] = fam_counts.get(t, 0) + 1
    # THE VOCABULARY THE ANNOTATOR COULD WRITE, recorded beside what it did
    # write. Counts alone cannot tell "offered and never chosen" from "never
    # offered", and that gap cost a whole claim: the decision surface told the
    # agent "never here: transition" at all seven purposes because
    # transition: 0 of 153 read as behaviour when it was the shape of a closed
    # six-value enum with no transition in it. A re-read at any sample rate
    # would have reproduced the zero.
    doc = {"beats_in_corpus": len(out), "family_counts_in_corpus": fam_counts,
           "readings": READINGS, "distinct_videos": DISTINCT_VIDEOS,
           "vocabulary": vocab if vocab is not None
                         else sorted(CORPUS_VOCABULARY),
           "builds_as": builds_as or {},
           "beats": out, "source": "reference_beats"}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=0)
    print(f"wrote {OUT}: {len(out)} beats, {os.path.getsize(OUT)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
