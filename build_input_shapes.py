#!/usr/bin/env python3
"""The INPUT-SHAPE corpus — abnormal inputs, each with a stated expectation.

The five real sources cover normal cases and found three production defects.
This set covers the ABNORMAL ones: five sources say the pipeline works, this
says what it does when it does not.

REAL WHERE REAL EXISTS. Probing the 41 objects under sources/ and Zac's five
reference files first was not ceremony — it changed the list. Already covered by
real footage, so NOT synthesised here:

    VFR              motion: r_frame_rate 59.94 vs ACTUAL 35.94 fps. Genuine
                     phone VFR, in the corpus since round 42, undetected.
    mono             motion and car_short are both 1-channel.
    16:9 landscape   screen_recording, 3826x2160.
    huge vertical    IMG_5428, 2160x3840.
    sub-HD           car_short 720x1272; six uploads at 320x568.
    HEVC             eight uploads.
    no audio at all  two uploads (one 1620x2880 with 0 channels).
    60fps declared   thirteen uploads.
    under 4s         eleven uploads at 3.6-3.7s.

A CAVEAT ON sources/ THAT MATTERS. It looks like test material, not organic user
media: 27 objects at EXACTLY 59.0s / 30fps / 1080x1920 / bt709, eleven at 3.7s,
six at 320x568. So it is used here as a source of real FILE SHAPES, and never
cited as evidence about what users upload.

EVERY CASE STATES ITS EXPECTATION, because "it did not crash" is not a result.
The three permitted outcomes are ACCEPT (a user would take it), WRONG (it
produced something a user would not), and LOUD (it refused with a message). The
one forbidden outcome is SILENT — a crash, a truncated output, or silence.

  python3 build_input_shapes.py --dry      probe + manifest, no upload
  python3 build_input_shapes.py --upload   build, probe, stage to S3
"""
import json
import os
import subprocess
import sys

V4 = "ab-sources/input-shapes-v1"
BUCKET = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
WORK = "/tmp/input_shapes"

# ── SYNTHESISED CASES ────────────────────────────────────────────────────────
# ffmpeg recipes, one per shape real footage does not supply. `expect` is the
# ruling BEFORE the batch runs, so a surprising result cannot be rationalised
# afterwards — the same discipline as a pre-registration.
SYNTH = [
    ("square_1x1", "1:1 square, 8s",
     "testsrc=size=720x720:rate=30:duration=8",
     "sine=frequency=330:duration=8",
     "ACCEPT — pad or blur-fill to 1080x1920; nothing cropped away"),
    ("ultrawide_21x9", "2560x1080 ultrawide, 8s",
     "testsrc=size=2560x1080:rate=30:duration=8",
     "sine=frequency=330:duration=8",
     "ACCEPT — a 9:16 crop keeps 21% of the width, so blur-fill or fit"),
    ("dur_3s", "exactly 3.0s — at the 2.0s reject floor",
     "testsrc=size=1080x1920:rate=30:duration=3",
     "sine=frequency=440:duration=3",
     "ACCEPT — above the 2.0s floor, so it must produce a video"),
    ("dur_200s", "200s — over the 3-minute mark, under the 300s ceiling",
     "testsrc=size=1080x1920:rate=30:duration=200",
     "sine=frequency=220:duration=200",
     "ACCEPT — under the 300s reject ceiling; watch cost and wall time"),
    ("fps_24", "24fps, 8s",
     "testsrc=size=1080x1920:rate=24:duration=8",
     "sine=frequency=330:duration=8",
     "ACCEPT — output should be a consistent rate, not 24"),
    ("fps_120_slowmo", "120fps slow-motion, 6s",
     "testsrc=size=1080x1920:rate=120:duration=6",
     "sine=frequency=330:duration=6",
     "ACCEPT — 720 frames must not become 720 frames at 30fps (4x too long)"),
    ("audio_one_channel_silent", "stereo, LEFT silent, 8s",
     "testsrc=size=1080x1920:rate=30:duration=8",
     "sine=frequency=440:duration=8[a];anullsrc=channel_layout=mono:duration=8[b];"
     "[b][a]join=inputs=2:channel_layout=stereo",
     "ACCEPT — transcription must not read the silent channel and call it mute"),
    ("audio_longer_than_video", "4s video, 12s audio",
     "testsrc=size=1080x1920:rate=30:duration=4",
     "sine=frequency=440:duration=12",
     "LOUD or ACCEPT — must NEVER deliver 4s of video against 12s of audio; "
     "this is the round-43 defect arriving as an INPUT"),
    ("still_frame", "a single colour that never moves, 10s",
     "color=c=0x2b2b3d:size=1080x1920:rate=30:duration=10",
     "sine=frequency=200:duration=10",
     "ACCEPT — zero motion and zero shot changes; beats must still exist "
     "(a clean zero here is the beat extractor failing, not the video)"),
    ("single_hard_cut", "two colours, one cut at 5s",
     "color=c=black:size=1080x1920:rate=30:duration=5[a];"
     "color=c=white:size=1080x1920:rate=30:duration=5[b];[a][b]concat=n=2:v=1:a=0",
     "sine=frequency=200:duration=10",
     "ACCEPT — exactly one shot change; the detector must find 1, not 0 or many"),
    ("pathologically_dark", "near-black noise, 8s",
     "color=c=0x050508:size=1080x1920:rate=30:duration=8,noise=alls=7:allf=t",
     "sine=frequency=200:duration=8",
     "ACCEPT — MEASURED mean luma 21.0/255. No black-frame gate exists in this "
     "pipeline, so what this actually probes is the motion curve: a near-black "
     "source must still yield beats, and a clean zero here is the extractor "
     "failing rather than a video with nothing in it"),
]

# Colour/rotation cases need their own encoder flags rather than a filter alone.
TAGGED = [
    ("hdr_pq", "HDR10 / PQ (smpte2084) — what an iPhone shoots by default",
     ["-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30:duration=8",
      "-f", "lavfi", "-i", "sine=frequency=330:duration=8",
      "-c:v", "libx265", "-tag:v", "hvc1", "-pix_fmt", "yuv420p10le",
      "-color_primaries", "bt2020", "-color_trc", "smpte2084",
      "-colorspace", "bt2020nc", "-c:a", "aac", "-shortest"],
     "ACCEPT — must not deliver washed-out or grey output; tone-map or convert"),
    ("hlg", "HLG (arib-std-b67) 10-bit",
     ["-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30:duration=8",
      "-f", "lavfi", "-i", "sine=frequency=330:duration=8",
      "-c:v", "libx265", "-tag:v", "hvc1", "-pix_fmt", "yuv420p10le",
      "-color_primaries", "bt2020", "-color_trc", "arib-std-b67",
      "-colorspace", "bt2020nc", "-c:a", "aac", "-shortest"],
     "ACCEPT — same as PQ; colour must survive"),
    ("rotate_90_metadata", "1920x1080 with rotation metadata, NOT baked",
     ["-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=30:duration=8",
      "-f", "lavfi", "-i", "sine=frequency=330:duration=8",
      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-metadata:s:v",
      "rotate=90", "-c:a", "aac", "-shortest"],
     "ACCEPT — must honour the rotation; a pipeline that ignores it delivers "
     "a sideways video, which reads as correct to every dimension check"),
]

# ── REAL FILES ALREADY IN S3, claimed rather than rebuilt ────────────────────
REAL = [
    ("real_vfr_mono", "ab-sources/reliability-fixtures-v3/motion-31fa2646.mp4",
     "VFR: declared 59.94fps, ACTUAL 35.94. Mono. Real phone footage.",
     "ACCEPT — and the output rate must be consistent, not 59.94 while every "
     "other fixture is 30"),
    ("real_landscape_16x9", "ab-sources/reliability-fixtures-v3/screen_recording-12c3bb18.mp4",
     "3826x2160 landscape, 90.46s, silent, readable text throughout.",
     "ACCEPT — a centre crop loses 68.2% of the width and makes the text "
     "unreadable, so fit or blur-fill"),
    ("real_huge_vertical", "ab-sources/reliability-fixtures-v3/car_mid-0643be1c.mp4",
     "2160x3840 — 4x the delivery pixel count.",
     "ACCEPT — downscale, no OOM, no timeout"),
]


def sh(args, timeout=1800):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def probe(path):
    r = sh(["ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", path])
    if r.returncode != 0:
        return None
    try:
        i = json.loads(r.stdout)
    except Exception:
        return None
    v = next((s for s in i["streams"] if s.get("codec_type") == "video"), {})
    a = next((s for s in i["streams"] if s.get("codec_type") == "audio"), None)
    nb, du = int(v.get("nb_frames") or 0), float(v.get("duration") or 0)
    return {"width": v.get("width"), "height": v.get("height"),
            "vcodec": v.get("codec_name"), "pix_fmt": v.get("pix_fmt"),
            "color_trc": v.get("color_transfer") or None,
            "declared_fps": v.get("r_frame_rate"),
            "actual_fps": round(nb / du, 2) if nb and du else None,
            "video_s": round(du, 3) if du else None,
            "audio_s": round(float((a or {}).get("duration") or 0), 3) if a else None,
            "channels": (a or {}).get("channels") if a else 0,
            "duration": round(float(i.get("format", {}).get("duration") or 0), 2),
            "size_mb": round(os.path.getsize(path) / 1e6, 2)}


def build():
    os.makedirs(WORK, exist_ok=True)
    made = []
    for name, desc, vfilt, afilt, expect in SYNTH:
        p = os.path.join(WORK, f"{name}.mp4")
        r = sh(["ffmpeg", "-y", "-v", "error",
                "-f", "lavfi", "-i", vfilt, "-f", "lavfi", "-i", afilt,
                "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                "-pix_fmt", "yuv420p", "-c:a", "aac"]
               + ([] if name == "audio_longer_than_video" else ["-shortest"])
               + [p])
        made.append((name, desc, expect, p, r.returncode))
    for name, desc, args, expect in TAGGED:
        p = os.path.join(WORK, f"{name}.mp4")
        r = sh(["ffmpeg", "-y", "-v", "error"] + args + [p])
        made.append((name, desc, expect, p, r.returncode))
    return made


def main():
    upload = "--upload" in sys.argv
    made = build()
    rows, failed_build = [], []
    print(f"{'case':28} {'WxH':11} {'dur':>7} {'v_s':>7} {'a_s':>7} {'fps':>12} {'ch':>3} {'trc':10}")
    for name, desc, expect, path, rc in made:
        if rc != 0 or not os.path.exists(path):
            failed_build.append(name)
            print(f"  {name:26} BUILD FAILED (ffmpeg exit {rc})")
            continue
        m = probe(path)
        if not m:
            failed_build.append(name)
            print(f"  {name:26} UNPROBEABLE")
            continue
        print(f"  {name:26} {str(m['width'])+'x'+str(m['height']):11} "
              f"{m['duration']:>7} {str(m['video_s']):>7} {str(m['audio_s']):>7} "
              f"{str(m['declared_fps']):>12} {str(m['channels']):>3} "
              f"{str(m['color_trc'] or '-'):10}")
        rows.append({"case": name, "shape": desc, "expect": expect,
                     "origin": "synthesised", "local": path,
                     "s3_key": f"{V4}/{name}.mp4", **m})
    for name, key, desc, expect in REAL:
        rows.append({"case": name, "shape": desc, "expect": expect,
                     "origin": "real — already staged", "s3_key": key})
        print(f"  {name:26} REAL -> {key.split('/')[-1]}")

    man = os.path.join(WORK, "manifest.json")
    json.dump(rows, open(man, "w"), indent=1)
    print(f"\n  {len(rows)} case(s); {len(failed_build)} build failure(s) "
          f"{failed_build or ''}")
    print(f"  manifest -> {man}")
    if not upload:
        print("  DRY RUN — nothing uploaded. Re-run with --upload.")
        return 1 if failed_build else 0

    import boto3
    s3 = boto3.client("s3")
    for r in rows:
        if r.get("origin") != "synthesised":
            continue
        s3.upload_file(r["local"], BUCKET, r["s3_key"],
                       ExtraArgs={"ContentType": "video/mp4"})
        print(f"  uploaded {r['s3_key']}")
    s3.put_object(Bucket=BUCKET, Key=f"{V4}/manifest.json",
                  Body=json.dumps(rows, indent=1).encode(),
                  ContentType="application/json")
    print(f"  uploaded {V4}/manifest.json")
    return 1 if failed_build else 0


if __name__ == "__main__":
    sys.exit(main())
