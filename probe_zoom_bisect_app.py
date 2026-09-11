#!/usr/bin/env python3
"""WHY DOES A ZOOM FRAME COST 10x A CAPTION FRAME WITH NO VIDEO IN IT?

THE MEASUREMENT THAT MADE THIS THE QUESTION. SnapReframe on an <Img> sequence
— no video element anywhere — still ran 1,217 ms/frame in the same container
where captions run 96-186. So the cost is not the decode, not the source kind,
and not the spring maths. It is something the zoom composition does per frame
that the caption composition does not.

A LADDER, NOT A GUESS. Each rung adds ONE property to the rung below and
renders the same 66 frames of the same source in the same container. The cost
appears between two rungs or it does not appear at all, and either way the
answer is a cause rather than a number. Same discipline that found the card
regression.

    0 baseline   a full-bleed <Img>, natural size, no styling
    1 cover      + objectFit: cover  (resample to fill 1080x1920)
    2 scale      + transform: scale(1.25), CONSTANT — one resample, reused
    3 origin     + transformOrigin 50% 40%
    4 animate    + a per-frame scale (the spring's actual curve)
    5 overflow   + AbsoluteFill overflow:hidden — a compositing layer
    6 real       SnapReframe itself, through PromptlyMicroSegments

SOURCE CLASS IS NAMED WITH THE RESULT (CLAUDE.md 2026-09-11): real footage
reads 3.9x where synthetic testsrc reads 2.0x on the same comparison, so a
number without its source class is not a result.

STATES, NOT BARE NUMBERS. Every rung reads remotion_batch's own per-job
verdict; a rung that did not render reports FAILED rather than dividing a
crash by 66.
"""
import os

import modal

from agentic_editor_app import IMG as _IMG                        # noqa: E402

image = _IMG.add_local_file("agentic_editor_app.py",
                            "/root/agentic_editor_app.py", copy=True)
app = modal.App("promptly-zoom-bisect")

_RUNGS = [
    ("0_baseline", ""),
    ("1_cover", "objectFit: 'cover',"),
    ("2_scale", "objectFit: 'cover', transform: 'scale(1.25)',"),
    ("3_origin", "objectFit: 'cover', transform: 'scale(1.25)', "
                 "transformOrigin: '50% 40%',"),
    ("4_animate", "objectFit: 'cover', transform: `scale(${1 + 0.25 * p})`, "
                  "transformOrigin: '50% 40%',"),
]

_TSX = r'''
import React from "react";
import {AbsoluteFill, useCurrentFrame, useVideoConfig, staticFile, Img} from "remotion";

const W0 = 20.81666;

import {Sequence} from "remotion";
import {SnapReframe} from "./zoom";
import {SmoothGraphicsProvider} from "./motion-graphics/shared/smooth-graphics-flag";
import {ResprungZoomsProvider} from "./zoom/shared/resprung-flag";
import {MotionBlurProvider, MotionBlurWrap} from "./motion-graphics/shared/motion-blur";

export const CompInput: React.FC<{input: {dir: string; n: number; rung: string}}> = ({input}) => (
  <Comp dir={input.dir} n={input.n} rung={input.rung} />
);

export const calcBisect = ({props}: {props: {input: {n: number}}}) => ({
  width: 1080, height: 1920, fps: 30,
  durationInFrames: Math.max(1, props.input.n),
});

export const Comp: React.FC<{dir: string; n: number; rung: string}> = ({dir, n, rung}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = f / fps;
  const p = 1 - (1 + W0 * t) * Math.exp(-W0 * t);   // the real spring, closed form
  const idx = String(Math.min(n, f + 1)).padStart(4, "0");
  const src = staticFile(`${dir}/f${idx}.jpg`);
  const S: React.CSSProperties = {width: "100%", height: "100%"};
  if (rung >= "1") S.objectFit = "cover";
  if (rung >= "2") S.transform = "scale(1.25)";
  if (rung === "4") S.transform = `scale(${1 + 0.25 * p})`;
  if (rung >= "3") S.transformOrigin = "50% 40%";
  const img = <Img src={src} style={S} />;
  if (rung === "7") {
    // THE SEQUENCE WRAPPER ALONE — everything else identical to rung 5.
    return (
      <Sequence from={0} durationInFrames={n}>
        <AbsoluteFill style={{overflow: "hidden"}}>{img}</AbsoluteFill>
      </Sequence>
    );
  }
  if (rung === "8") {
    // THE REAL COMPONENT ALONE — no Sequence, no providers, no
    // PromptlyMicroSegments. Its own spring, its own AbsoluteFill.
    return (
      <SnapReframe
        src={staticFile(`${dir}/f0001.jpg`)}
        frames={{dir, count: n, pad: 4, ext: "jpg"}}
        events={[{startMs: 0, durationMs: Math.round((n / 30) * 1000), scale: 1.25,
                  originX: 0.5, originY: 0.4}]}
      />
    );
  }
  if (rung === "9") {
    const real = (
      <SnapReframe
        src={staticFile(`${dir}/f0001.jpg`)}
        frames={{dir, count: n, pad: 4, ext: "jpg"}}
        events={[{startMs: 0, durationMs: Math.round((n / 30) * 1000), scale: 1.25,
                  originX: 0.5, originY: 0.4}]}
      />
    );
    return (
      <SmoothGraphicsProvider enabled={false}>
      <ResprungZoomsProvider enabled={false}>
      <MotionBlurProvider enabled={false}>
        <AbsoluteFill style={{background: "#000"}}>
          <Sequence from={0} durationInFrames={n}>
            <MotionBlurWrap>{real}</MotionBlurWrap>
          </Sequence>
        </AbsoluteFill>
      </MotionBlurProvider>
      </ResprungZoomsProvider>
      </SmoothGraphicsProvider>
    );
  }
  if (rung >= "5") return <AbsoluteFill style={{overflow: "hidden"}}>{img}</AbsoluteFill>;
  return <AbsoluteFill>{img}</AbsoluteFill>;
};
'''


@app.function(image=image, cpu=8, memory=16384, timeout=3600)
def ladder(source_url: str = "", seconds: float = 2.2) -> dict:
    import json
    import subprocess
    import time

    R = "/promptly-remotion"
    PUB = os.path.join(R, "public")
    os.makedirs(PUB, exist_ok=True)

    def run(cmd, **kw):
        return subprocess.run(cmd, capture_output=True, text=True, **kw)

    if not source_url:
        return {"state": "FAILED",
                "detail": "no source_url — synthetic and real footage differ by "
                          "2x on this family of comparison, so the probe "
                          "refuses to run on a class it cannot name"}
    src = os.path.join(PUB, "bis_src.mp4")
    r = run(["ffmpeg", "-y", "-v", "error", "-t", f"{seconds}", "-i", source_url,
             "-an", "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,"
                           "crop=1080:1920",
             "-c:v", "libx264", "-crf", "16", "-preset", "veryfast",
             "-pix_fmt", "yuv420p", src])
    if r.returncode != 0:
        return {"state": "FAILED", "detail": f"source: {(r.stderr or '')[-200:]}"}
    n = int(round(seconds * 30))
    seqdir = os.path.join(PUB, "bis_seq")
    os.makedirs(seqdir, exist_ok=True)
    for _f in os.listdir(seqdir):
        os.remove(os.path.join(seqdir, _f))
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-q:v", "2",
         os.path.join(seqdir, "f%04d.jpg")])
    if len(os.listdir(seqdir)) < n:
        return {"state": "FAILED", "detail": "sequence short"}

    open(os.path.join(R, "src", "BisectZoom.tsx"), "w").write(_TSX)
    root = os.path.join(R, "src", "Root.tsx")
    _r = open(root).read()
    if "BisectZoom" not in _r:
        _r = _r.replace('import React',
                        'import {Comp as BisectZoom, CompInput as BisectMicro, '
                        'calcBisect} from "./BisectZoom";\nimport React', 1)
        _r = _r.replace("</>", (
            '<Composition id="BisectZoom" component={BisectZoom} '
            f'durationInFrames={{{n}}} fps={{30}} width={{1080}} height={{1920}} '
            f'defaultProps={{{{dir: "bis_seq", n: {n}, rung: "0"}}}} />\n'
            '<Composition id="BisectMicro" component={BisectMicro} '
            f'durationInFrames={{{n}}} fps={{30}} width={{1080}} height={{1920}} '
            f'defaultProps={{{{input: {{dir: "bis_seq", n: {n}, rung: "5"}}}}}} '
            'calculateMetadata={calcBisect} />\n</>'), 1)
        open(root, "w").write(_r)

    def batch(tag, comp, props):
        pf = f"/tmp/bis-{tag}.json"
        json.dump(props, open(pf, "w"))
        qf = f"/tmp/bis-jobs-{tag}.json"
        json.dump([{"id": tag, "composition": comp, "propsFile": pf,
                    "out": f"/tmp/bis_{tag}.mp4"}], open(qf, "w"))
        t0 = time.time()
        _env = dict(os.environ)
        if tag in ("6_real", "9_wrapper"):
            # THE TWO THAT DISAGREE: same component, 5x apart. Only these two
            # carry the cost of verbose logging.
            _env["PROMPTLY_REMOTION_FRAME_TIMING"] = "1"
            _env["PROMPTLY_REMOTION_LOG"] = "verbose"
        rr = run(["node", "remotion_batch.mjs", qf], cwd=R, timeout=3000,
                 env=_env)
        job = {}
        for ln in ((rr.stdout or "") + "\n" + (rr.stderr or "")).splitlines():
            if ln.startswith("JOB "):
                try:
                    job = json.loads(ln[4:])
                except Exception:                                 # noqa: BLE001
                    pass
        _actual = None
        _out_mp4 = f"/tmp/bis_{tag}.mp4"
        if os.path.exists(_out_mp4):
            _pr = run(["ffprobe", "-v", "error", "-count_frames",
                       "-select_streams", "v:0",
                       "-show_entries", "stream=nb_read_frames",
                       "-of", "csv=p=0", _out_mp4])
            try:
                _actual = int((_pr.stdout or "").strip())
            except (TypeError, ValueError):
                _actual = None
        _frames_log, _delay = [], []
        for ln in ((rr.stdout or "") + "\n" + (rr.stderr or "")).splitlines():
            if ln.startswith("FRAME "):
                try:
                    _frames_log.append(json.loads(ln[6:]))
                except Exception:                                 # noqa: BLE001
                    pass
            low = ln.lower()
            if "delayrender" in low or "handle" in low or "timed out" in low:
                _delay.append(ln[:200])
        # ABSENCE IS A STATE. Asking for frame timing and getting none means
        # the hook never fired — not that the frames were evenly spaced.
        _gaps = ("REQUESTED_BUT_ABSENT"
                 if tag in ("6_real", "9_wrapper") and not _frames_log else None)
        if len(_frames_log) > 3:
            _ms = [f["ms"] for f in _frames_log]
            _d = [b - a for a, b in zip(_ms, _ms[1:])]
            _d.sort()
            # WHERE THE TIME IS, not just how it is distributed. A median of
            # 3ms with a max of 5,381 says the total is in a tail; this says
            # how much of it and in how many stalls.
            _big = [x for x in _d if x >= 100]
            _gaps = {"n": len(_d), "median": _d[len(_d) // 2], "max": _d[-1],
                     "p90": _d[int(len(_d) * 0.9)] if len(_d) > 9 else _d[-1],
                     "total_ms": sum(_d),
                     "stalls_over_100ms": len(_big),
                     "stall_ms": sum(_big),
                     "stall_share": (round(sum(_big) / sum(_d), 3)
                                     if sum(_d) else None),
                     "top5": _d[-5:]}
        return {"wall_s": round(time.time() - t0, 2), "job": job,
                "frame_gaps_ms": _gaps,
                "delay_lines": _delay[:6],
                "frames_actual": _actual,
                "ms_per_frame": (round(job["ms"] / n, 1)
                                 if job.get("ok") and job.get("ms") else None),
                "ms_per_actual_frame": (round(job["ms"] / _actual, 1)
                                        if job.get("ok") and job.get("ms")
                                        and _actual else None),
                "err": (str(job.get("error"))[:160] if job.get("ok") is False
                        else "")}

    out = {"state": "MEASURED", "frames": n, "source_class": "REAL FOOTAGE",
           "rungs": {}}
    for tag, _ in _RUNGS:
        out["rungs"][tag] = batch(tag, "BisectZoom",
                                  {"dir": "bis_seq", "n": n, "rung": tag[0]})
    out["rungs"]["5_overflow"] = batch("5_overflow", "BisectZoom",
                                       {"dir": "bis_seq", "n": n, "rung": "5"})
    # WHICH HALF: the Sequence wrapper, or the component itself?
    out["rungs"]["7_sequence"] = batch("7_sequence", "BisectZoom",
                                       {"dir": "bis_seq", "n": n, "rung": "7"})
    out["rungs"]["8_component"] = batch("8_component", "BisectZoom",
                                        {"dir": "bis_seq", "n": n, "rung": "8"})
    out["rungs"]["9_wrapper"] = batch("9_wrapper", "BisectZoom",
                                      {"dir": "bis_seq", "n": n, "rung": "9"})
    # IS IT THE REGISTRATION? Same content as rung 5, but through a
    # composition with calculateMetadata and an `input`-shaped prop — the two
    # things PromptlyMicroSegments has that BisectZoom does not.
    out["rungs"]["10_registration"] = batch(
        "10_registration", "BisectMicro",
        {"input": {"dir": "bis_seq", "n": n, "rung": "5"}})
    # rung 6: the real component, through the real composition
    plan = {"input": {"sourceUrl": "bis_src.mp4", "fps": 30, "width": 1080,
                      "height": 1920, "totalDurationInFrames": n,
                      "segments": [{"type": "zoom_clip", "outputStartFrame": 0,
                                    "durationInFrames": n,
                                    "clip": {"id": "z0", "src": "bis_src.mp4",
                                             "startFromFrames": 0,
                                             "playbackRate": 1.0,
                                             "durationInFrames": n,
                                             "frames": {"dir": "bis_seq",
                                                        "count": n, "pad": 4,
                                                        "ext": "jpg"},
                                             "zoomEffect": {
                                                 "type": "SnapReframe",
                                                 "events": [{"startMs": 0,
                                                             "durationMs": int(seconds * 1000),
                                                             "scale": 1.25,
                                                             "originX": 0.5,
                                                             "originY": 0.4}]}}}]}}
    out["rungs"]["6_real"] = batch("6_real", "PromptlyMicroSegments", plan)
    import copy as _copy
    _plan_novideo = _copy.deepcopy(plan)
    _plan_novideo["input"]["segments"][0]["clip"].pop("frames", None)
    out["rungs"]["11_real_video"] = batch("11_real_video",
                                          "PromptlyMicroSegments", _plan_novideo)
    bad = [k for k, v in out["rungs"].items() if v["ms_per_frame"] is None]
    if bad:
        out["state"] = "PARTIAL"
        out["detail"] = f"rung(s) that did not render: {bad}"
    return out


@app.local_entrypoint()
def main():
    u = os.environ.get("PROBE_SOURCE_URL", "")
    print("PRICE STATED: one cpu=8 container, seven renders of 66 frames. ~$0.15.")
    r = ladder.remote(source_url=u)
    print(f"  state={r['state']}  {r.get('detail','')}  source_class="
          f"{r.get('source_class')}  frames={r.get('frames')}")
    prev = None
    for k in ("6_real", "9_wrapper"):
        v = r.get("rungs", {}).get(k) or {}
        if v.get("frame_gaps_ms"):
            print(f"    {k} frame gaps ms: {v['frame_gaps_ms']}")
        for ln in (v.get("delay_lines") or [])[:4]:
            print(f"      {k} | {ln}")
    for k in sorted(r.get("rungs", {})):
        v = r["rungs"][k]
        mf = v["ms_per_frame"]
        step = ("" if mf is None or prev is None
                else f"   step x{mf / prev:.2f}" if prev else "")
        _fa = v.get("frames_actual")
        _mfa = v.get("ms_per_actual_frame")
        if _fa is None:
            _den = "   frames_actual=ABSENT (ffprobe gave no count — the " \
                   "denominator is UNVERIFIED, not confirmed)"
        elif _fa != r.get("frames"):
            _den = (f"   *** {_fa} FRAMES RENDERED, not {r.get('frames')} — "
                    f"{_mfa} ms per ACTUAL frame")
        else:
            _den = f"   [{_fa} frames confirmed]"
        print(f"    {k:12s} {str(mf):>8} ms/frame{step}{_den}"
              + (f"   FAILED: {v['err']}" if v.get("err") else ""))
        if mf:
            prev = mf
