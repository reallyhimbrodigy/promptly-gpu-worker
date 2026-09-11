#!/usr/bin/env python3
"""THE REAL COMPONENT, BOTH ARMS, SAME CONTAINER — pixels and time.

WHAT THE LAST PROBE COULD NOT ANSWER. It compared the shipped composition
against a hand-written <Img> component, so its PSNR (12.1 avg) measured a
LINEAR RAMP against a SPRING — my probe's easing, not the source kind. The
speed number survived that (3.9x on real footage) because timing does not care
which curve you draw; the pixel number did not.

SO THIS RUNS SnapReframe ITSELF ON BOTH ARMS. Identical component, identical
events, identical spring; the only difference is whether its source pixels
arrive as an h264 <Video> or as a JPEG sequence through <Img>. A PSNR from
this is attributable to the source kind and to nothing else, which is the
question that decides whether the 3.9x is a trade Zac can look at.

SAME CONTAINER, BOTH ARMS (CLAUDE.md 2026-09-11) — identical work has run
1.6-2.2x apart between containers, so a cross-run comparison cannot see a
lever this size.

STATES, NOT BARE NUMBERS. The batch's own per-job verdict is read: a previous
version divided a CRASH by 66 frames and reported 174 ms/frame with rc=0.
"""
import os

import modal

from agentic_editor_app import IMG as _IMG                        # noqa: E402

image = _IMG.add_local_file("agentic_editor_app.py",
                            "/root/agentic_editor_app.py", copy=True)
app = modal.App("promptly-zoom-real-component")


@app.function(image=image, cpu=8, memory=16384, timeout=2400)
def both_arms(source_url: str = "", seconds: float = 2.2,
              ztype: str = "SnapReframe", scale_to: float = 1.25) -> dict:
    import json
    import re
    import subprocess
    import time

    R = "/promptly-remotion"
    PUB = os.path.join(R, "public")
    os.makedirs(PUB, exist_ok=True)
    out = {"state": "FAILED", "detail": "", "ztype": ztype}

    def run(cmd, **kw):
        return subprocess.run(cmd, capture_output=True, text=True, **kw)

    src_name = "rc_src.mp4"
    src = os.path.join(PUB, src_name)
    if source_url:
        r = run(["ffmpeg", "-y", "-v", "error", "-t", f"{seconds}",
                 "-i", source_url, "-an",
                 "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,"
                        "crop=1080:1920",
                 "-c:v", "libx264", "-crf", "16", "-preset", "veryfast",
                 "-pix_fmt", "yuv420p", src])
    else:
        return dict(out, detail="no source_url — a synthetic source reads 2.0x "
                                "where real footage reads 3.9x, so this probe "
                                "refuses to run on one")
    if r.returncode != 0:
        return dict(out, detail=f"source: {(r.stderr or '')[-200:]}")
    n = int(round(seconds * 30))

    seqdir_name = "rc_seq"
    seqdir = os.path.join(PUB, seqdir_name)
    os.makedirs(seqdir, exist_ok=True)
    for _f in os.listdir(seqdir):
        os.remove(os.path.join(seqdir, _f))
    t0 = time.time()
    r = run(["ffmpeg", "-y", "-v", "error", "-i", src, "-q:v", "2",
             os.path.join(seqdir, "f%04d.jpg")])
    extract_s = round(time.time() - t0, 2)
    got = len(os.listdir(seqdir))
    if r.returncode != 0 or got < n:
        return dict(out, detail=f"sequence: wrote {got} of {n}")
    seq_mb = round(sum(os.path.getsize(os.path.join(seqdir, x))
                       for x in os.listdir(seqdir)) / 1e6, 1)

    def plan(use_frames):
        clip = {"id": "z0", "src": src_name, "startFromFrames": 0,
                "playbackRate": 1.0, "durationInFrames": n,
                "zoomEffect": {"type": ztype,
                               "events": [{"startMs": 0,
                                           "durationMs": int(seconds * 1000),
                                           "scale": scale_to,
                                           "originX": 0.5, "originY": 0.4}]}}
        if use_frames:
            # THE ONLY DIFFERENCE BETWEEN THE ARMS.
            clip["frames"] = {"dir": seqdir_name, "count": n, "pad": 4,
                              "ext": "jpg"}
        return {"input": {"sourceUrl": src_name, "fps": 30, "width": 1080,
                          "height": 1920, "totalDurationInFrames": n,
                          "segments": [{"type": "zoom_clip",
                                        "outputStartFrame": 0,
                                        "durationInFrames": n, "clip": clip}]}}

    def batch(tag, use_frames):
        pf = f"/tmp/rc-{tag}.json"
        json.dump(plan(use_frames), open(pf, "w"))
        qf = f"/tmp/rc-jobs-{tag}.json"
        json.dump([{"id": tag, "composition": "PromptlyMicroSegments",
                    "propsFile": pf, "out": f"/tmp/{tag}.mp4"}], open(qf, "w"))
        t = time.time()
        rr = run(["node", "remotion_batch.mjs", qf], cwd=R, timeout=2000)
        wall = round(time.time() - t, 2)
        job = {}
        for ln in ((rr.stdout or "") + "\n" + (rr.stderr or "")).splitlines():
            if ln.startswith("JOB "):
                try:
                    job = json.loads(ln[4:])
                except Exception:                                 # noqa: BLE001
                    pass
        return {"wall_s": wall, "rc": rr.returncode, "job": job,
                "ms_per_frame": (round(job["ms"] / n, 1)
                                 if job.get("ms") else None),
                "stderr_tail": (rr.stderr or "")[-300:]}

    a = batch("arm_video", False)
    b = batch("arm_frames", True)
    res = dict(out, frames=n, extract_s=extract_s, seq_mb=seq_mb,
               video=a, frames_arm=b)
    for nm, arm in (("video", a), ("frames", b)):
        if arm["job"].get("ok") is False or arm["job"].get("ok") is None:
            return dict(res, state="FAILED",
                        detail=f"the {nm} arm did not render — "
                               f"{str(arm['job'].get('error'))[:200] or 'no JOB line'}"
                               f". Its wall clock is the time to fail.")
    if not all(os.path.exists(f"/tmp/{t}.mp4")
               for t in ("arm_video", "arm_frames")):
        return dict(res, state="ABSENT", detail="an arm produced no file")
    p = run(["ffmpeg", "-v", "info", "-i", "/tmp/arm_video.mp4",
             "-i", "/tmp/arm_frames.mp4", "-lavfi", "psnr", "-f", "null", "-"])
    m = re.search(r"average:([0-9.]+|inf)", p.stderr or "")
    mn = re.search(r"min:([0-9.]+|inf)", p.stderr or "")
    speed = (a["ms_per_frame"] / b["ms_per_frame"]) if b["ms_per_frame"] else None
    return dict(res, state="MEASURED",
                psnr_avg=(m.group(1) if m else None),
                psnr_min=(mn.group(1) if mn else None),
                speedup=round(speed, 2) if speed else None,
                detail=f"{ztype}: video {a['ms_per_frame']} vs frames "
                       f"{b['ms_per_frame']} ms/frame "
                       f"({round(speed, 2) if speed else '?'}x), "
                       f"PSNR avg {m.group(1) if m else '?'}")


@app.local_entrypoint()
def main():
    u = os.environ.get("PROBE_SOURCE_URL", "")
    z = os.environ.get("PROBE_ZTYPE", "SnapReframe")
    print("PRICE STATED: one cpu=8 container, two renders of 66 frames of the "
          "REAL component plus a psnr pass. ~$0.06.")
    r = both_arms.remote(source_url=u, ztype=z)
    print(f"  state={r['state']}  {r.get('detail')}")
    for k in ("frames", "extract_s", "seq_mb", "speedup", "psnr_avg", "psnr_min"):
        if r.get(k) is not None:
            print(f"    {k}: {r[k]}")
    for arm in ("video", "frames_arm"):
        if r.get(arm):
            print(f"    {arm}: {r[arm]}")
