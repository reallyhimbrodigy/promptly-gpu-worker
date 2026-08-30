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
FPS = 2                 # matches the live proxy arm (proxy_sample_fps=2)
WIDTH = 512             # matches MEDIA_RESOLUTION_LOW's effective vertical width
# scdet threshold on ffmpeg's 0-100 scale — THE SAME CONSTANT
# handler.detect_shot_changes passes (7.0, chosen against production sweep
# data). The old SCENE_THRESHOLD=0.30 was a different filter on a 0-1
# scale and under-counted vertical UGC by 30-70%.
SCDET_THRESHOLD = 7.0

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


def extract_frames(path, fps=FPS, width=WIDTH, limit=200):
    """Sample at the proxy's own rate. Returns [(t_seconds, jpeg_bytes)]."""
    d = "/tmp/_refcorpus_frames"
    subprocess.run(["rm", "-rf", d], check=False)
    os.makedirs(d, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={fps},scale={width}:-2",
         "-q:v", "4", f"{d}/f_%05d.jpg"], check=False)
    files = sorted(os.listdir(d))[:limit]
    return [(round(i / fps, 2), open(os.path.join(d, f), "rb").read())
            for i, f in enumerate(files)]


SCHEMA_INSTRUCTION = """You are building a REFERENCE RECORD of how this video is EDITED.

Return JSON only, matching exactly:

{
  "hook_structure": "<the hook named as a STRUCTURE, not a label. e.g. 'curiosity-gap + insider hook: secret framing -> loss/threat framing'>",
  "first_visual_change_s": <float or null>,
  "beats": [
    {
      "beat_index": <int>,
      "t_start": <float>, "t_end": <float>,
      "purpose": "hook|claim|evidence|turn|payoff|close|breath",
      "speaker_on_screen": <bool>,
      "caption_layer": "running"|"absent",
      "treatment": ["cut"|"punch_in"|"cutaway"|"card"|"text_placement"|"sfx"],
      "cutaway_subject": "<what the b-roll literally SHOWS>" or null,
      "card_text": "<verbatim on-screen text>" or null,
      "read": "<one sentence: why this treatment, here>"
    }
  ]
}

RULES THAT MATTER:
- CAPTIONS ARE NOT A TREATMENT. `caption_layer` records whether word-by-word
  captions are running under this beat. They usually are, for the whole video —
  that is a property of the edit, NOT a per-beat decision. Recording them as a
  treatment made every beat non-bare and made restraint unmeasurable: on a first
  pass over 10 references, 126 of 175 beats carried "overlay_text" and ZERO beats
  came back bare. Put running captions in `caption_layer` and leave them out of
  `treatment`.
- `text_placement` is a DISCRETE text event only — a title, a callout, a label
  that appears for this beat and is not part of the running caption track.
- `treatment: []` is a REAL AND EXPECTED ANSWER, and on a well-edited video it
  should be COMMON — the editor holding on the speaker with only captions running
  is the most frequent choice in the corpus. A beat that received nothing beyond
  captions is a deliberate act of restraint and must be recorded as such. Do NOT
  invent a treatment to avoid an empty list. A bare beat still requires a `read`
  saying WHY it is bare — what made holding correct there.
- `first_visual_change_s` is when ANYTHING first changes on screen — a cut, a
  cutaway, a card, a title. If nothing changes for the whole video, return null.
  Null is a finding, not a failure.
- Describe ONLY what is visible in the frames. Do not infer a cut you cannot see.
  Cut timestamps detected mechanically are supplied below; treat them as ground
  truth for WHERE cuts are.
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
        "model": MODEL, "max_tokens": 16000,
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
    rec = json.loads(m.group(0))
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
    for b in beats:
        tr = b.get("treatment") or []
        print(f"   {b.get('t_start'):>6}-{b.get('t_end'):<6} {str(b.get('purpose')):<9}"
              f" {('[' + ','.join(tr) + ']') if tr else '[] BARE':<26} {str(b.get('read'))[:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
