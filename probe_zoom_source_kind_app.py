#!/usr/bin/env python3
"""SAME CONTAINER, BOTH ARMS: does an image sequence remove the zoom's decode?

THE MEASUREMENT THIS SETTLES. build_zoom is 94% paint and its paint runs
2,051 ms/frame while captions — same container, same run, no <Video> mounted —
run 68-186. PromptlyMicroSegments is the only composition that mounts the
source, so the delta is attributable to the video element and to nothing else.
This renders the SAME zoom job twice in ONE container, changing only where the
pixels come from:

    video  the shipped path: <Video src="zsrcN.mp4">
    frames an image sequence of the identical window, mounted as <Img>

SAME CONTAINER IS THE WHOLE POINT (CLAUDE.md, 2026-09-11). Identical work ran
1.6x and 2.2x slower between two rounds on the container with MORE cores, so a
cross-round comparison cannot see anything below 2x and this lever is claimed
at ~20x. Both arms here share one container, one bundle and one machine.

IT COMPARES PIXELS, NOT ONLY TIME. Moving off <Video> re-baselines output
bytes, so the arms are frame-diffed and the worst frame's PSNR is reported
with the timing. A speed number without the pixel number would be half an
answer to a question about quality.
"""
import os

import modal

from agentic_editor_app import IMG as _IMG                        # noqa: E402

image = _IMG.add_local_file("agentic_editor_app.py",
                            "/root/agentic_editor_app.py", copy=True)
app = modal.App("promptly-zoom-source-kind")

_TSX = r'''
import React from "react";
import {AbsoluteFill, useCurrentFrame, useVideoConfig, staticFile, Img} from "remotion";
export const Comp: React.FC<{dir: string; n: number; scaleTo: number}> = ({dir, n, scaleTo}) => {
  const f = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const p = durationInFrames > 1 ? f / (durationInFrames - 1) : 1;
  const scale = 1 + (scaleTo - 1) * p;
  const idx = String(Math.min(n, f + 1)).padStart(4, "0");
  return (
    <AbsoluteFill style={{overflow: "hidden"}}>
      <Img src={staticFile(`${dir}/f${idx}.jpg`)}
           style={{width: "100%", height: "100%", objectFit: "cover",
                   transform: `scale(${scale})`, transformOrigin: "50% 50%"}} />
    </AbsoluteFill>
  );
};
'''


@app.function(image=image, cpu=8, memory=16384, timeout=1800)
def both_arms(seconds: float = 2.2, scale_to: float = 1.25,
              source_url: str = "") -> dict:
    """Returns {video: {...}, frames: {...}, psnr: ...}. States, not bare numbers."""
    import json
    import os
    import re
    import subprocess
    import time

    R = "/promptly-remotion"
    PUB = os.path.join(R, "public")
    os.makedirs(PUB, exist_ok=True)
    out = {"state": "FAILED", "detail": ""}

    def run(cmd, **kw):
        return subprocess.run(cmd, capture_output=True, text=True, **kw)

    # ONE SOURCE for both arms: a 1080x1920 clip, the shape every zoom source
    # already is (build_cut normalises before zoom runs).
    src = os.path.join(PUB, "probe_src.mp4")
    if source_url:
        # REAL FOOTAGE, re-encoded exactly as the shipped pre-extract does
        # (crf 16, veryfast, pinned threads) — synthetic testsrc is trivially
        # compressible and may not decode like a real zoom source.
        r = run(["ffmpeg", "-y", "-v", "error", "-t", f"{seconds}",
                 "-i", source_url, "-an",
                 "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,"
                        "crop=1080:1920",
                 "-c:v", "libx264", "-crf", "16", "-preset", "veryfast",
                 "-pix_fmt", "yuv420p", src])
    else:
        r = run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                 "-i", f"testsrc=s=1080x1920:r=30:d={seconds}",
                 "-pix_fmt", "yuv420p", src])
    if r.returncode != 0:
        return dict(out, detail=f"source: {r.stderr[-200:]}")
    n = int(round(seconds * 30))

    # arm B's input: the identical window as JPEGs
    seqdir = os.path.join(PUB, "probe_seq")
    os.makedirs(seqdir, exist_ok=True)
    t0 = time.time()
    r = run(["ffmpeg", "-y", "-v", "error", "-i", src, "-q:v", "3",
             os.path.join(seqdir, "f%04d.jpg")])
    extract_s = round(time.time() - t0, 2)
    got = len([x for x in os.listdir(seqdir) if x.endswith(".jpg")])
    if r.returncode != 0 or got < n:
        return dict(out, detail=f"sequence: wrote {got} of {n}; {r.stderr[-200:]}")
    seq_bytes = sum(os.path.getsize(os.path.join(seqdir, x))
                    for x in os.listdir(seqdir))

    open(os.path.join(R, "src", "ProbeImgZoom.tsx"), "w").write(_TSX)
    root = os.path.join(R, "src", "Root.tsx")
    _root = open(root).read()
    if "ProbeImgZoom" not in _root:
        _root = _root.replace(
            'import React', 'import {Comp as ProbeImgZoom} from "./ProbeImgZoom";\nimport React', 1)
        _root = _root.replace(
            "</>", f'<Composition id="ProbeImgZoom" component={{ProbeImgZoom}} '
                   f'durationInFrames={{{n}}} fps={{30}} width={{1080}} height={{1920}} '
                   f'defaultProps={{{{dir: "probe_seq", n: {n}, scaleTo: {scale_to}}}}} />\n</>', 1)
        open(root, "w").write(_root)

    def batch(jobs):
        qf = "/tmp/probe-jobs.json"
        json.dump(jobs, open(qf, "w"))
        t = time.time()
        rr = run(["node", "remotion_batch.mjs", qf], cwd=R, timeout=1500)
        return round(time.time() - t, 2), rr

    # ARM A — the shipped path, through the real composition
    # THE SHIPPED PLAN SHAPE, field for field. The first version omitted
    # totalDurationInFrames and the segment's type/outputStartFrame, and the
    # composition threw `TypeError: durationInFrames prop` — rc was still 0,
    # the batch reported ok:false, and the 174 ms/frame I read off the wall
    # clock was the time to FAIL. A number that looked plausible and measured
    # a crash. Copied from execute_plan rather than written from memory.
    plan = {"input": {
        "sourceUrl": "probe_src.mp4", "fps": 30, "width": 1080, "height": 1920,
        "totalDurationInFrames": n,
        "segments": [{
            "type": "zoom_clip", "outputStartFrame": 0, "durationInFrames": n,
            "clip": {"id": "z0", "src": "probe_src.mp4",
                     "startFromFrames": 0, "playbackRate": 1.0,
                     "durationInFrames": n,
                     "zoomEffect": {"type": "SnapReframe",
                                    "events": [{"startMs": 0,
                                                "durationMs": int(seconds * 1000),
                                                "scale": scale_to,
                                                "originX": 0.5,
                                                "originY": 0.4}]}}}]}}
    pf = "/tmp/probe-plan.json"
    json.dump(plan, open(pf, "w"))
    a_s, a_r = batch([{"id": "arm_video", "composition": "PromptlyMicroSegments",
                       "propsFile": pf, "out": "/tmp/arm_video.mp4"}])
    b_s, b_r = batch([{"id": "arm_frames", "composition": "ProbeImgZoom",
                       "propsFile": pf, "out": "/tmp/arm_frames.mp4"}])

    def jobline(rr):
        """remotion_batch emits one `JOB {json}` line per entry — the verdict
        the batch itself reached. Reading the filesystem instead is how the
        first run of this probe reported ABSENT while both arms had rc=0."""
        for ln in ((rr.stdout or "") + "\n" + (rr.stderr or "")).splitlines():
            if ln.startswith("JOB "):
                try:
                    return json.loads(ln[4:])
                except Exception:                                 # noqa: BLE001
                    pass
        return {}

    res = {"frames": n, "extract_s": extract_s, "seq_mb": round(seq_bytes / 1e6, 1),
           "video": {"wall_s": a_s, "rc": a_r.returncode,
                     "ms_per_frame": round(a_s * 1000 / n, 1),
                     # the batch's OWN per-job ms is the paint; the wall clock
                     # includes bundle and process start, and on a failed job
                     # it is the time to crash.
                     "err": (a_r.stderr or "")[-240:] if a_r.returncode else ""},
           "frames_arm": {"wall_s": b_s, "rc": b_r.returncode,
                          "ms_per_frame": round(b_s * 1000 / n, 1),
                          "err": (b_r.stderr or "")[-240:] if b_r.returncode else ""}}
    res["video"]["job"] = jobline(a_r)
    res["frames_arm"]["job"] = jobline(b_r)
    res["video"]["stderr_tail"] = (a_r.stderr or "")[-400:]
    res["frames_arm"]["stderr_tail"] = (b_r.stderr or "")[-400:]
    for _nm, _key in (("video", "video"), ("frames", "frames_arm")):
        _j = res[_key].get("job") or {}
        if _j.get("ok") is False:
            return dict(res, state="FAILED",
                        detail=f"the {_nm} arm did NOT render — "
                               f"{str(_j.get('error'))[:160]}. Its wall clock "
                               f"is the time to fail, not to paint.")
    if a_r.returncode or b_r.returncode:
        return dict(res, state="FAILED",
                    detail="one arm did not render — no comparison exists")
    _missing = [p for p in ("/tmp/arm_video.mp4", "/tmp/arm_frames.mp4")
                if not os.path.exists(p)]
    if _missing:
        return dict(res, state="ABSENT",
                    detail=f"no file at {_missing} — the batch's own verdicts "
                           f"are in .job; rc was 0 for both, so the render "
                           f"either wrote elsewhere or never selected")
    p = run(["ffmpeg", "-v", "info", "-i", "/tmp/arm_video.mp4",
             "-i", "/tmp/arm_frames.mp4", "-lavfi", "psnr", "-f", "null", "-"])
    m = re.search(r"average:([0-9.]+)", p.stderr or "")
    mn = re.search(r"min:([0-9.]+)", p.stderr or "")
    return dict(res, state="MEASURED",
                psnr_avg=float(m.group(1)) if m else None,
                psnr_min=float(mn.group(1)) if mn else None,
                detail=f"video {res['video']['ms_per_frame']} ms/frame vs "
                       f"frames {res['frames_arm']['ms_per_frame']} ms/frame")


@app.local_entrypoint()
def main():
    print("PRICE STATED: one cpu=8 container, two renders of ~66 frames plus a "
          "psnr pass. ~$0.05.")
    # AN ENV VAR, NOT sys.argv. Under `modal run file.py` the process argv
    # belongs to the Modal CLI: argv[1] is the literal string "run", which
    # this passed to ffmpeg as a filename — "source: run: No such file or
    # directory". Reading a position that belongs to someone else, again.
    _u = os.environ.get("PROBE_SOURCE_URL", "")
    if _u:
        print(f"  real source: {_u[:80]}")
    r = both_arms.remote(source_url=_u)
    print(f"  state={r['state']}  {r.get('detail')}")
    for k in ("frames", "extract_s", "seq_mb", "psnr_avg", "psnr_min"):
        if r.get(k) is not None:
            print(f"    {k}: {r[k]}")
    for arm in ("video", "frames_arm"):
        if r.get(arm):
            print(f"    {arm}: {r[arm]}")
