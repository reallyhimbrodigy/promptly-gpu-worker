#!/usr/bin/env python3
"""build_reference_records.py — REFERENCE_CORPUS_SPEC.md §3, made real.

Pass A (ffmpeg) finds the cuts. Pass B (Claude) describes the beats. They are
separate on purpose: a model asked to find cuts AND describe them will describe
cuts it invented, and there is no way afterwards to tell an invented cut from a
missed one.

WRITES JSON FIRST, NOT SUPABASE. The tables are DDL and DDL is owner-run here.
Emitting records to a file proves the SHAPE without waiting on a migration, and
a record that cannot be written to a file was never going to survive a schema.

    python3 build_reference_records.py <video.mp4> [--transcript t.json] [--price-only]

Cost is PRINTED BEFORE the call and again after, measured from the response's
own usage block with cache hit/miss stated. The estimate and the measurement are
both shown because they have disagreed before.
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.request

MODEL = "claude-sonnet-5"

# The two golden references, by sha256. Anything matching is INSIDE the
# instrument that 3.5/s was calibrated on and cannot be independent evidence
# about it.
_GOLDEN_SHAS = {
    # Cut counts CORRECTED 2026-08-29 with the pipeline's own detector
    # (scdet=7). The old figures came from the select-filter at 0.30 and
    # were low by ~half on the vertical reference.
    "7392d2b42f281921",   # ref2-viral-creator-doc-vertical  43.2s / 15 cuts (was recorded 8)
    "22ef7a120c76722c",   # ref1-legalsoft-corporate-landscape 52.6s / 23 cuts (was recorded 21)
}
# THE SAMPLE RATE IS AN ARM. 2 matches the live proxy arm (proxy_sample_fps=2)
# and is what the shipped 153-beat corpus was read at. Override to compare.
FPS = float(os.environ.get("REFCORPUS_FPS", "2"))
WIDTH = 512             # matches MEDIA_RESOLUTION_LOW's effective vertical width
# scdet threshold on ffmpeg's 0-100 scale — THE SAME CONSTANT
# handler.detect_shot_changes passes (7.0, chosen against production sweep
# data). The old SCENE_THRESHOLD=0.30 was a different filter on a 0-1
# scale and under-counted vertical UGC by 30-70%.
SCDET_THRESHOLD = 7.0

# FRAMES PER VIDEO, and it must clear the LONGEST reference at the HIGHEST rate
# this script is run at, because the cap truncates rather than subsamples (see
# extract_frames). Longest reference is 59.5s; at 5 fps that is 298 frames.
FRAME_LIMIT = int(os.environ.get("REFCORPUS_FRAME_LIMIT", "400"))

# OUTPUT CAP. Raised 8000 -> 16000 when the two densest references returned
# EXACTLY out=8000; raised again 16000 -> 32000 on 2026-09-11 when a 23-cut
# reference at 5 fps returned EXACTLY out=16000. Beat count scales with cut
# count AND with how much the annotator can see, so raising the sample rate
# raises the output too. The cap has to clear the densest reference at the
# HIGHEST rate this is run at, not the median one at the lowest.
MAX_TOKENS = int(os.environ.get("REFCORPUS_MAX_TOKENS", "32000"))

# Claude bills an image at roughly (w*h)/750 tokens. A 512-wide vertical frame is
# ~512x910. Stated as a CONSTANT rather than a guess inside a print, so the
# estimate is auditable and can be corrected in one place when it is wrong.
TOK_PER_FRAME = int(512 * 910 / 750)     # ~621
USD_IN_PER_MTOK = 3.00
USD_OUT_PER_MTOK = 15.00


def probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return None


def pass_a_shots(path):
    """ffmpeg scene detection. THE MODEL DOES NOT DO THIS.

    Returns cut timestamps in seconds. An empty list is a RESULT — a video with
    no cuts is exactly the counter-example the spec exists to capture, and it
    must not be indistinguishable from a failed probe (hence the None return).
    """
    # USE THE PIPELINE'S OWN DETECTOR (corrected 2026-08-29). This ran
    # `select='gt(scene,0.30)'` under a comment claiming it was "the same value
    # the render pipeline uses". It is not: handler's detect_shot_changes uses
    # `scdet=threshold=7.0`, a DIFFERENT filter on a DIFFERENT scale (0-100, not
    # 0-1), and 7.0 was itself chosen against production sweep data after 0.30
    # was found wrong.
    #
    # MEASURED on the reference set — the two disagree, and worst on exactly the
    # content that matters:
    #     v09044g4…  tool 5   pipeline 17
    #     1e5eb227…  tool 8   pipeline 15     <- a GOLDEN reference
    #     v24044gl…  tool 41  pipeline 60
    #     56ba632…   tool 21  pipeline 23     <- the landscape ref, the only close one
    # Vertical UGC — 8 of the 10 references — under-counts by 30-70%.
    #
    # These timestamps are handed to the model as GROUND TRUTH for beat
    # segmentation. A record built on a cut list missing two-thirds of the cuts
    # describes an edit that does not exist. And the purpose of the record is to
    # extract rules for OUR pipeline, so the cut truth must be what OUR pipeline
    # sees — not a second opinion from a different filter.
    try:
        p = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", path,
             "-vf", f"scdet=threshold={SCDET_THRESHOLD}", "-an", "-f", "null", "-"],
            capture_output=True, text=True, timeout=300)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return sorted({round(float(m), 3)
                   for m in re.findall(r"lavfi\.scd\.time:\s*([0-9.]+)",
                                       p.stdout + p.stderr)})


def extract_frames(path, fps=FPS, width=WIDTH, limit=FRAME_LIMIT):
    """Sample at the proxy's own rate. Returns [(t_seconds, jpeg_bytes)].

    THE CAP TRUNCATED THE VIDEO, IT DID NOT SUBSAMPLE IT. This was
    `sorted(...)[:limit]` — the FIRST `limit` frames — so a video longer than
    limit/fps seconds was annotated only up to that point and the tail was
    never seen. At FPS=2 the cap never bound (200 frames = 100s, longer than
    every reference), so it was invisible for the life of the corpus. At 5 fps
    it binds on 5 of the 10 references and cuts the longest to its first 40
    SECONDS of 59.5.

    The timestamps are computed from the frame INDEX, so the truncated prefix
    would have carried correct-looking times and the missing tail would have
    looked like a video that simply had no beats there. A rate comparison built
    on that would have read truncation as an effect of the rate.

    So it RAISES rather than truncates. A cap that silently drops the end of
    the evidence is the absence-as-result class; a cap that stops the run names
    itself.
    """
    d = "/tmp/_refcorpus_frames"
    subprocess.run(["rm", "-rf", d], check=False)
    os.makedirs(d, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={fps},scale={width}:-2",
         "-q:v", "4", f"{d}/f_%05d.jpg"], check=False)
    files = sorted(os.listdir(d))
    if len(files) > limit:
        raise SystemExit(
            f"  FRAME CAP would TRUNCATE: {len(files)} frames at {fps} fps "
            f"exceeds limit={limit}, and the cap keeps the FIRST {limit} — "
            f"i.e. only the first {limit/fps:.1f}s of a "
            f"{len(files)/fps:.1f}s video. Raise FRAME_LIMIT; do not sample "
            f"a prefix and call it the video.")
    return [(round(i / fps, 2), open(os.path.join(d, f), "rb").read())
            for i, f in enumerate(files)]


SCHEMA_INSTRUCTION = """You are building a REFERENCE RECORD of how this video is EDITED.

You are watching an edit a professional made. Two jobs: say WHAT IS THERE, in
your own words, and say WHAT MAKES IT GOOD.

Return JSON only, matching exactly:

{
  "hook_structure": "<the hook named as a STRUCTURE, not a label. e.g. 'curiosity-gap + insider hook: secret framing -> loss/threat framing'>",
  "first_visual_change_s": <float or null>,
  "what_makes_this_good": "<2-4 sentences. What would a professional editor point at in this video and say 'that is why this works'? Be specific to THIS video: the thing that makes it feel expensive, elegant, deliberate — or the thing that makes it feel cheap, if that is the honest answer. Not a summary of the content.>",
  "signature_moves": [
    {
      "move": "<a move this editor uses REPEATEDLY in this video, your own words>",
      "what_it_does": "<the observable effect on the viewer or the screen>",
      "where": "<beat indices, e.g. '2, 7, 11'>"
    }
  ],
  "beats": [
    {
      "beat_index": <int>,
      "t_start": <float>, "t_end": <float>,
      "purpose": "hook|claim|evidence|turn|payoff|close|breath",
      "speaker_on_screen": <bool>,
      "caption_layer": "running"|"absent",
      "treatment": [
        {
          "name": "<what this IS, in your own words>",
          "what_it_does": "<the observable effect — what changes on screen or in the ear>"
        }
      ],
      "cutaway_subject": "<what the b-roll literally SHOWS>" or null,
      "card_text": "<verbatim on-screen text>" or null,
      "craft": "<what makes THIS moment work, or null if nothing here stands out. Why it feels professional, elegant, expensive. A beat that is merely competent gets null — do not manufacture craft.>",
      "read": "<one sentence: why this treatment, here>"
    }
  ]
}

RULES THAT MATTER:

- `treatment` IS AN OPEN VOCABULARY. Name whatever you actually notice, in your
  own words. It is NOT a menu. Earlier versions of this schema shipped a closed
  enum of six — cut, punch_in, cutaway, card, text_placement, sfx — and the
  corpus it produced recorded ZERO transitions across 153 beats, not because
  there were none but because the annotator had no word for one. An enum is a
  HYPOTHESIS about what exists; this pass exists to find out what actually does.
  If you see a speed ramp, a colour shift, a held frame, a match cut, a sound
  that carries across a cut, a freeze, a reframe, a text kinetic, a
  masked reveal, a J-cut, a beat that lands on the music — say so, in the words
  that describe it. The families above are worth knowing as COMMON cases. They
  are not the permitted set and you are not scored on using them.

- ANYTHING NAMED MUST SAY WHAT IT DOES. `what_it_does` is required on every
  treatment. A name with nothing behind it is not a finding — it is a label,
  and this corpus has been read as measurement before. If you cannot say what
  a thing does on screen or in the ear, do not name it.

- DO NOT INFLATE. An open vocabulary is an invitation to find something at every
  beat, which would be worth less than the zero it replaces. Name what is
  ACTUALLY there. A beat where the editor did nothing but hold is the most
  common choice in a good edit and must be recorded as such.

- CAPTIONS ARE NOT A TREATMENT. `caption_layer` records whether word-by-word
  captions are running under this beat. They usually are, for the whole video —
  that is a property of the edit, NOT a per-beat decision. Recording them as a
  treatment made every beat non-bare and made restraint unmeasurable: on one
  pass over 10 references, 126 of 175 beats carried a caption treatment and ZERO
  beats came back bare. Put running captions in `caption_layer` and leave them
  out of `treatment`. A DISCRETE text event — a title, a callout, a label that
  appears for this beat and is not part of the running caption track — IS a
  treatment and you should name it.

- `treatment: []` is a REAL AND EXPECTED ANSWER, and on a well-edited video it
  should be COMMON — the editor holding on the speaker with only captions
  running is a deliberate act of restraint. A bare beat still requires a `read`
  saying WHY it is bare — what made holding correct there.

- `craft` IS THE POINT OF THIS PASS AND IT IS NOT A SECOND `read`. `read` says
  why this treatment is HERE. `craft` says what makes it GOOD — the timing that
  makes a cut feel inevitable, the restraint that makes the next thing land, the
  detail that costs money. Most beats have no craft worth naming and get null.
  A record where every beat has craft is a record where none of it means
  anything.

- `first_visual_change_s` is when ANYTHING first changes on screen — a cut, a
  cutaway, a card, a title. If nothing changes for the whole video, return null.
  Null is a finding, not a failure.

- Describe ONLY what is visible in the frames, or audible if you are told about
  audio. Do not infer a cut you cannot see. Cut timestamps detected mechanically
  are supplied below; treat them as ground truth for WHERE cuts are.

- Per-word caption treatment is in scope and valuable: if a specific word is
  styled (colour, italic, size) note it in `card_text` and `read`.
"""


def build_request(frames, shots, transcript, duration):
    content = [{"type": "text", "text": SCHEMA_INSTRUCTION}]
    ctx = {"duration_s": duration,
           "mechanical_cut_timestamps_s": shots if shots is not None else "PROBE_FAILED",
           "transcript": (transcript or "")[:6000]}
    content.append({"type": "text",
                    "text": "CONTEXT:\n" + json.dumps(ctx, indent=1)})
    for t, jpg in frames:
        content.append({"type": "text", "text": f"t={t}s"})
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/jpeg",
            "data": base64.standard_b64encode(jpg).decode()}})
    return content


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--transcript", default=None)
    ap.add_argument("--price-only", action="store_true")
    ap.add_argument("--out", default="reference_record.json")
    a = ap.parse_args()

    dur = probe_duration(a.video)
    if dur is None:
        print("ffprobe failed — UNMEASURED, not a zero-length video")
        return 2
    shots = pass_a_shots(a.video)
    frames = extract_frames(a.video)

    est_in = len(frames) * TOK_PER_FRAME + 2000
    est_usd = est_in / 1e6 * USD_IN_PER_MTOK + 1500 / 1e6 * USD_OUT_PER_MTOK
    print(f"  source     {os.path.basename(a.video)}  {dur:.1f}s")
    print(f"  pass A     {'PROBE FAILED' if shots is None else str(len(shots)) + ' cuts detected by ffmpeg'}")
    print(f"  frames     {len(frames)} @ {FPS}fps {WIDTH}px")
    print(f"  ESTIMATE   ~{est_in:,} input tok  ->  ~${est_usd:.3f}")
    if a.price_only:
        print("  --price-only: no call made")
        return 0

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        for line in open(os.path.expanduser("~/content-studio/.env.local")):
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("'\"")
    if not key:
        print("  no ANTHROPIC_API_KEY — UNMEASURED")
        return 2

    tx = open(a.transcript).read() if a.transcript and os.path.exists(a.transcript) else None
    body = json.dumps({
        # 16000, not 8000. The two densest references (19 and 41 cuts) returned
        # EXACTLY out=8000 — the cap, not a model failure — and truncated JSON
        # is unparseable, so both were lost with the tokens already paid for.
        # Beat count scales with cut count; the cap has to clear the densest
        # reference, not the median one.
        "model": MODEL, "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user",
                      "content": build_request(frames, shots, tx, dur)}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    # READ THE ERROR BODY. A 400 with no body is a failed measurement that cannot
    # explain itself — the PROBE COLLAPSE class. The API states exactly what it
    # rejected; throwing that away turns a fixable input error into a mystery.
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:600]
        print(f"  HTTP {e.code} — the API said:\n    {detail}")
        return 2

    u = resp.get("usage", {})
    # CACHE HIT/MISS STATED, always — a cost figure without it is not comparable
    # across arms, which is the standing rule for every model A/B here.
    ci = u.get("cache_creation_input_tokens", 0)
    cr = u.get("cache_read_input_tokens", 0)
    inp, out = u.get("input_tokens", 0), u.get("output_tokens", 0)
    usd = (inp + ci) / 1e6 * USD_IN_PER_MTOK + out / 1e6 * USD_OUT_PER_MTOK
    print(f"  MEASURED   in={inp:,} cache_write={ci:,} cache_read={cr:,} out={out:,}")
    print(f"             cache: {'MISS (cold)' if not cr else f'HIT ({cr:,} read)'}"
          f"  ->  ${usd:.3f}  (estimate was ${est_usd:.3f})")

    txt = "".join(p.get("text", "") for p in resp.get("content", []) if p.get("type") == "text")
    m = re.search(r"\{[\s\S]*\}", txt)
    if not m:
        print("  no JSON in response — record NOT written")
        return 1
    # SAVE THE RAW RESPONSE BEFORE PARSING (2026-08-29). A malformed JSON body
    # used to raise straight out of main(), losing a response that was already
    # PAID FOR — v09044g4 died at char 6009 and left nothing behind, so the
    # failure could not be diagnosed without buying the call again. The record is
    # the product; the response is the evidence. Keep both.
    _raw_path = a.out + ".raw.txt"
    try:
        with open(_raw_path, "w", encoding="utf-8") as _fh:
            _fh.write(txt)
    except Exception:
        pass
    try:
        rec = json.loads(m.group(0))
    except json.JSONDecodeError as _je:
        # A CAP HIT IS NOT A PARSE ERROR. out == max_tokens means the response was
        # TRUNCATED, and truncated JSON is unparseable — so the cap arrives wearing
        # a parser's clothes and the fix looks like "the model emitted bad JSON"
        # when it is "raise the cap". It has now happened twice, at 8000 and at
        # 16000, and both times the symptom was read before the cause.
        if out >= MAX_TOKENS:
            print(f"  OUTPUT CAP HIT: out={out:,} == max_tokens={MAX_TOKENS:,}. "
                  f"The response was TRUNCATED, which is why it will not parse. "
                  f"This is a FAILED measurement, not a malformed one — raise "
                  f"REFCORPUS_MAX_TOKENS and re-run this video.")
        print(f"  JSON PARSE FAILED ({_je}) — raw response kept at {_raw_path}")
        print(f"  This is a FAILED EXTRACTION, not an empty one. Do not read the")
        print(f"  missing record as 'this reference has no beats'.")
        return 1
    # PROVENANCE ON THE ROW. records-not-aggregates already makes one bad
    # reference a single DELETABLE ROW rather than a contaminated mean — but only
    # if the row names its source. Without this the deletion is untargetable and
    # the whole guarantee is theatre.
    import hashlib
    _sha = hashlib.sha256(open(a.video, "rb").read()).hexdigest()
    # IN_INSTRUMENT: two of the owner's ten are byte-identical to the goldens
    # MOTION_DENSITY_TARGET_EVPS = 3.5 was calibrated on. Their density records
    # CANNOT be evidence about that target — measuring a target against the
    # videos that produced it is circular. Tagged so the query can exclude them.
    rec["provenance"] = {
        "source_file": os.path.basename(a.video),
        "sha256": _sha,
        "bytes": os.path.getsize(a.video),
        "duration_s": dur,
        "selected_by": "owner",
        "in_instrument": _sha[:16] in _GOLDEN_SHAS,
        "analyzer_model": MODEL, "fps": FPS, "width": WIDTH,
        "mechanical_cuts": shots,
        "cuts_per_s": round(len(shots) / dur, 3) if (shots and dur) else 0.0,
    }
    # ANYTHING NAMED MUST SAY WHAT IT DOES — ENFORCED, NOT REQUESTED.
    # transition_kind's discipline, generalised to an open vocabulary. With a
    # closed enum the name carried the meaning; with free naming a bare label
    # is worth nothing and would still be COUNTED, which is how a corpus turns
    # into rates that mean nothing. A treatment with no `what_it_does` is
    # DROPPED AND NAMED, never silently kept and never silently discarded.
    _ungrounded = []
    for _b in (rec.get("beats") or []):
        _keep = []
        for _t in (_b.get("treatment") or []):
            if isinstance(_t, str):
                # A bare string is the old closed-enum shape. It carries no
                # effect, so it is ungrounded by construction.
                _ungrounded.append((_b.get("beat_index"), _t, "bare string"))
                continue
            if not isinstance(_t, dict):
                _ungrounded.append((_b.get("beat_index"), repr(_t)[:40],
                                    "not an object"))
                continue
            _nm = str(_t.get("name") or "").strip()
            _wd = str(_t.get("what_it_does") or "").strip()
            if not _nm:
                _ungrounded.append((_b.get("beat_index"), "(no name)", "unnamed"))
                continue
            if not _wd:
                _ungrounded.append((_b.get("beat_index"), _nm, "no what_it_does"))
                continue
            _keep.append({"name": _nm, "what_it_does": _wd})
        _b["treatment"] = _keep
    if _ungrounded:
        print(f"  UNGROUNDED  {len(_ungrounded)} treatment(s) dropped — a name "
              f"with nothing behind it is a label, not a finding:")
        for _bi, _nm, _why in _ungrounded[:12]:
            print(f"     beat {_bi}: {_nm!r} ({_why})")
    rec["ungrounded_dropped"] = [{"beat": b, "name": n, "why": w}
                                 for b, n, w in _ungrounded]

    json.dump(rec, open(a.out, "w"), indent=1)
    beats = rec.get("beats") or []
    bare = sum(1 for b in beats if not (b.get("treatment") or []))
    print(f"\n  RECORD     {len(beats)} beats · {bare} BARE (treatment: [])"
          f" · first_visual_change_s={rec.get('first_visual_change_s')}")
    print(f"  hook       {str(rec.get('hook_structure'))[:100]}")
    print(f"  written    {a.out}")
    # THE RECORD, FOR REVIEW. A good video can still produce a wrong reading, so
    # what gets approved is this — not the file it came from.
    print(f"\n  ── RECORD FOR REVIEW ── {rec['provenance']['source_file']}"
          f"{'   [IN_INSTRUMENT]' if rec['provenance']['in_instrument'] else ''}")
    print(f"  hook: {rec.get('hook_structure')}")
    print(f"  first_visual_change_s: {rec.get('first_visual_change_s')}   "
          f"cuts/s: {rec['provenance']['cuts_per_s']}")
    print(f"  what makes it good: {str(rec.get('what_makes_this_good'))[:300]}")
    for _sm in (rec.get("signature_moves") or []):
        print(f"   SIGNATURE  {_sm.get('move')} -> {_sm.get('what_it_does')} "
              f"(beats {_sm.get('where')})")
    for b in beats:
        tr = [t.get("name", "?") for t in (b.get("treatment") or [])]
        print(f"   {b.get('t_start'):>6}-{b.get('t_end'):<6} {str(b.get('purpose')):<9}"
              f" {('[' + ','.join(tr) + ']') if tr else '[] BARE':<40} {str(b.get('read'))[:60]}")
        if b.get("craft"):
            print(f"          craft: {str(b.get('craft'))[:120]}")
    _craft = sum(1 for b in beats if b.get("craft"))
    print(f"\n  CRAFT      {_craft} of {len(beats)} beats carry a craft note "
          f"({100.0*_craft/len(beats) if beats else 0:.0f}%)")
    _names = sorted({t.get("name") for b in beats
                     for t in (b.get("treatment") or []) if t.get("name")})
    print(f"  VOCABULARY {len(_names)} distinct treatment name(s) on this video:")
    for _n in _names:
        print(f"     {_n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
