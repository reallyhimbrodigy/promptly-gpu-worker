#!/usr/bin/env python3
"""Put a round's finished videos in front of Zac, with each one's truth beside it.

THE QUALITY PILLAR HAS NO INSTRUMENT. Three of the four pillars are measured:
reliability by the gate, speed by the stage clock, cost by the token ledger.
Quality is "Zac's eye on a finished video from this pipeline", and that has never
happened — not once in 44 rounds. Frames have been pulled and looked at, which
found the invisible cards and the unreadable crop, but a still is not an edit.

WHAT THIS PRINTS BESIDE EACH LINK, and why each one is there rather than being
taken on trust:

    video_s / audio_s   the round-43 defect delivered 9.267s of video against
                        30.960s of audio, and the CONTAINER duration — the only
                        number the pipeline printed — said 30.96s. Per-stream or
                        it is not a measurement.
    WxH                 two round-42 outputs shipped at source resolution.
    fps                 output rate FOLLOWS THE SOURCE: round 43 delivered motion
                        at 59.94 while every other fixture came out at 30. Not
                        yet fixed, so it is reported.
    placements          what the agent actually put on screen, so a video that
                        looks empty can be told from one that IS empty.

EVERY FIGURE IS ffprobed FROM THE DELIVERED OBJECT, never read from the log. The
log is what the pipeline believes; these are links to what it produced, and the
gap between those two is the entire history of this lane.

  python3 deliver_round.py <round> [--days 7]
"""
import json
import os
import re
import subprocess
import sys

BUCKET = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
import agentic_editor_app as _app   # the SHARED stream-length verdict


def ffprobe(url):
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
                        "-show_format", "-show_streams", url],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return None
    try:
        i = json.loads(r.stdout)
    except Exception:
        return None
    v = next((s for s in i["streams"] if s.get("codec_type") == "video"), {})
    a = next((s for s in i["streams"] if s.get("codec_type") == "audio"), None)
    nb, du = int(v.get("nb_frames") or 0), float(v.get("duration") or 0)
    return {"w": v.get("width"), "h": v.get("height"),
            "video_s": round(du, 2) if du else None,
            "audio_s": round(float((a or {}).get("duration") or 0), 2) if a else None,
            "fps": round(nb / du, 2) if nb and du else None,
            "mb": round(int(i.get("format", {}).get("size") or 0) / 1e6, 1)}


def _recover_key(s3, fixture, log):
    """The newest agentic-editor object whose name carries this fixture.

    Used ONLY when the log has no out-key. Provenance is inferred from the
    filename and recency rather than read from the run, and every caller labels
    it as such — a recovered artifact is evidence a video exists, not evidence
    that THIS run produced it.
    """
    try:
        r = s3.list_objects_v2(Bucket=BUCKET, Prefix="agentic-editor/")
        cands = [(o["LastModified"], o["Key"]) for o in r.get("Contents", [])
                 if f"-{fixture}-" in o["Key"] and o["Key"].endswith(".mp4")]
        return max(cands)[1] if cands else None
    except Exception:
        return None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    rnd = sys.argv[1]
    days = 7
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    d = f"/tmp/fixtures/round{rnd}"
    if not os.path.isdir(d):
        print(f"no such round: {d}")
        return 2

    import boto3
    s3 = boto3.client("s3")
    rows = []
    for name in sorted(os.path.splitext(f)[0] for f in os.listdir(d)
                       if f.endswith(".log") and ".cancelled" not in f):
        log = open(os.path.join(d, f"{name}.log"), encoding="utf-8",
                   errors="ignore").read()
        m = re.search(r"agentic-editor/\d+-[^\s\"']+\.mp4", log)
        origin = "log"
        if not m:
            # ABSENCE IN THE LOG IS NOT ABSENCE IN THE WORLD, and the first
            # version of this line said "this fixture produced no deliverable" —
            # which was FALSE for round 45's screen_recording. Its container
            # finished and uploaded at 20:47; the CLI then hung for ~1h50m, the
            # function was stopped, and the log never reached its summary. So the
            # out-key was missing from the LOG while the artifact sat in S3,
            # correct: 34.400s video, 34.460s audio, 1080x1920.
            #
            # A tool that reports a delivered video as undelivered costs the one
            # reading nobody else can give. So look for it, and LABEL the
            # provenance: recovered by name and recency is INFERRED, not read
            # from the run that made it.
            key = _recover_key(s3, name, log)
            if not key:
                rows.append((name, None, None,
                             "no out-key in the log AND nothing matching in S3 "
                             "— absent as far as can be established"))
                continue
            origin = "RECOVERED from S3 by name+recency (provenance INFERRED, "
            m = None
        else:
            key = m.group(0)
        url = s3.generate_presigned_url("get_object",
                                        Params={"Bucket": BUCKET, "Key": key},
                                        ExpiresIn=days * 86400)
        sig = re.search(r"RUN SIGNATURE   : turns \d+\s+cost \$[\d.]+\s+"
                        r"placements (\d+)\s+\[([^\]]*)\]", log)
        # SPAN COUNT FROM EITHER LINE. CUT DECISION is the normal source, but a
        # run that never reached its summary has no CUT DECISION — and the count
        # is ALSO carried in the STREAM LENGTH line the gate printed mid-run.
        # Without this fallback screen_recording fell back to the tight
        # unknown-spans bar and a CORRECT 4-span video was flagged TRUNCATED,
        # which is the tool telling Zac a good edit is broken.
        _sp = (re.search(r"across (\d+) span\(s\)", log)
               or re.search(r"tolerance [\d.]+ frames \([\d.]+s at [\d.]+fps, "
                            r"(\d+) span\(s\)\)", log))
        _note = (f"{sig.group(1)} placements [{sig.group(2)}]" if sig
                 else "no run signature — the run did not reach its summary")
        if origin != "log":
            _note = origin + _note + ")"
        _info = ffprobe(url)
        if _info is not None:
            _info["spans"] = int(_sp.group(1)) if _sp else None
        rows.append((name, url, _info, _note))

    print(f"ROUND {rnd} — {len(rows)} finished video(s), links valid {days} day(s)\n")
    bad = 0
    for name, url, info, note in rows:
        if not url:
            print(f"  {name:17} MISSING — {note}")
            bad += 1
            continue
        if not info:
            print(f"  {name:17} UNPROBEABLE at the link — the object may not be "
                  f"readable")
            bad += 1
            continue
        # A/V mismatch is called out HERE too, because a link handed over with a
        # silently truncated video is the failure this whole day was about.
        flag = ""
        # ONE INSTRUMENT, NOT TWO. This carried its own 0.05s threshold and
        # therefore its own opinion — and it flagged round 45's
        # screen_recording, a CORRECT 4-span output whose 0.060s deficit is
        # 1.80 frames against a 5.0-frame bound. A second copy of a constant is
        # a second thing to get wrong, and a false flag on a good video costs
        # exactly the reading this tool exists to enable.
        _st, _det = _app.stream_length_verdict(
            info["video_s"], info["audio_s"], None,
            fps=info["fps"] or 30.0, spans=info.get("spans"))
        if _st != "OK":
            flag = f"  <-- {_st}: {_det[:96]}"
            bad += 1
        if (info["w"], info["h"]) != (1080, 1920):
            flag += f"  <-- NOT 1080x1920: {info['w']}x{info['h']}"
            bad += 1
        print(f"  {name:17} {info['w']}x{info['h']}  v={info['video_s']}s "
              f"a={info['audio_s']}s  {info['fps']}fps  {info['mb']}MB  {note}{flag}")
        print(f"    {url}")
    print(f"\n  {len(rows) - bad} clean, {bad} flagged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
