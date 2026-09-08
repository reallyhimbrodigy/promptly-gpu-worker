"""What does a REAL zoom cost in THIS lane? The number that gates the port.

THE QUESTION. The parity budget priced all seven zoom types off production's
p50 of 1047.8 ms/frame for micro segments (video decoded and composited through
Remotion) against 114.5 for overlays — 9.2x, measured over 83/94 organic jobs
with legs (sweep_micro_concurrency_app.py:337). At that rate one zoom at
reference density is +21.8s of wall, and the fidelity question has to go to Zac.

WHY THAT NUMBER IS SUSPECT HERE, and why this probe is worth $0.05:
  - This lane's ALPHA rate is 49.0 ms/frame (round 33 captions, 443 frames),
    already 2.3x better than production's overlay p50 of 114.5 on the same
    composition class.
  - 1047.8 was measured under production's DEFAULT render concurrency.
    sweep_micro_concurrency_app.py exists precisely to sweep that variable on
    micro segments and there is NO RECORDED RESULT anywhere in the repo — its
    own confirmation step is the last thing written about it.
  - The identical lever on this lane's overlay path was worth 2.63x (a26925d),
    and it was worth it because the setting had leaked from a measurement
    harness into production at concurrency 1.
If micro responds like overlay, zoom is ~+8s and the taste call never needs
making.

THE SAME IMAGE, NOT A COPY OF IT. This imports agentic_editor_app and uses its
IMG and its render_remotion_batch, because the thing being measured is what that
container does — a probe with its own image would answer a question about the
probe. (Standing rule: nothing ships on a path you have not verified in the
running image.)

TWO POINTS PER TYPE, so the reported rate is MARGINAL. A single length folds
selectComposition and encoder startup into the per-frame number, which is how a
per-frame rate ends up describing a fixed cost. rate = (t_long - t_short) /
(frames_long - frames_short).

A REAL SOURCE, DOWNLOADED AND SERVED LOCALLY. Paint cost here is dominated by
decoding 1080x1920 video, so a synthetic pattern would measure the wrong thing;
and fetching per-frame over a presigned URL would fold network variance into a
paint measurement. The fixture is pulled once and copied into public/.

  python3 presign.py ab-sources/reliability-fixtures-v1/talking_head-eeb40bc7.mp4
  modal run probe_micro_paint_app.py --src-url "<the GET url>"

COST: 8 cpu / 16 GB. At the pessimistic 1047.8 ms/frame the whole sweep is
7 types x 44 frames = 308 frames = ~5.4 min; at this lane's alpha rate it is
~25s. Stated in advance: ~$0.05, actual reported at the end.
"""
import json
import os
import shutil
import subprocess
import time

import modal

import agentic_editor_app as AE

app = modal.App("probe-micro-paint")

# MOUNT THE MODULE YOU IMPORT. Modal mounts the ENTRYPOINT module; a sibling
# imported at module level is not in the container, and the run dies with
# ModuleNotFoundError before any measurement — which is what happened on the
# first launch of this probe. smoke_modal_app_preflight.py exists to catch
# exactly this and I did not run it on a new file; it is in the loop now.
# add_local_python_source, NOT add_local_file. The first attempt copied the file
# to /root/agentic_editor_app.py and the container STILL raised
# ModuleNotFoundError with the mount plainly listed in `modal run`'s output — a
# mount existing is not the same as the module being importable, which is this
# lane's oldest shape wearing a new hat. This is the mechanism Modal provides
# for exactly this and it puts the module on sys.path rather than a path that
# merely looks like it is on sys.path.
IMG = AE.IMG.add_local_python_source("agentic_editor_app", "type_registries")

# Every zoom type production can place. ZOOM_ARC_HOMES tiles the registry, so
# this list IS the registry — read from it rather than restated, because a type
# added later must appear here without anyone remembering.
ZOOM_TYPES = ("SmoothPush", "SnapReframe", "FocusWindow", "StepZoom",
              "LetterboxPush", "DepthPull", "StagedPush")

# Production's own natural durations and default scales, so the probe measures
# the move that actually ships rather than a generic push.
NATURAL_MS = {"SmoothPush": 1200, "SnapReframe": 700, "FocusWindow": 1500,
              "StepZoom": 800, "LetterboxPush": 1400, "DepthPull": 2200,
              "StagedPush": 1800}
NATURAL_SCALE = {"SmoothPush": 1.22, "SnapReframe": 1.30, "FocusWindow": 1.80,
                 "StepZoom": 1.25, "LetterboxPush": 1.25, "DepthPull": 1.25,
                 "StagedPush": 1.25}


def _plan(zoom_type, frames, fps=30):
    return {"input": {
        "sourceUrl": "probe.mp4", "fps": fps, "width": 1080, "height": 1920,
        "totalDurationInFrames": frames,
        "segments": [{
            "type": "zoom_clip", "outputStartFrame": 0,
            "durationInFrames": frames,
            "clip": {"id": f"z-{zoom_type}", "startFromFrames": 0,
                     "playbackRate": 1.0, "durationInFrames": frames,
                     "zoomEffect": {
                         "type": zoom_type,
                         "events": [{"startMs": 0,
                                     "durationMs": NATURAL_MS.get(zoom_type, 1200),
                                     "scale": NATURAL_SCALE.get(zoom_type, 1.22),
                                     "originX": 0.5, "originY": 0.4}],
                     }},
        }],
    }}


@app.function(image=IMG, secrets=AE.SECRETS, timeout=2400, cpu=8, memory=16384)
def measure(src_url: str, short_frames: int = 10, long_frames: int = 34,
            fps: int = 30) -> dict:
    import urllib.request as _url
    os.makedirs("/work", exist_ok=True)
    pub = "/promptly-remotion/public"
    os.makedirs(pub, exist_ok=True)
    t_dl = time.time()
    with _url.urlopen(_url.Request(src_url, method="GET"), timeout=600) as r, \
            open("/work/probe.mp4", "wb") as fh:
        shutil.copyfileobj(r, fh)
    # staticFile() serves out of public/, and the bundle is built by the batch
    # below — so this must land BEFORE the render call, not after.
    shutil.copy("/work/probe.mp4", os.path.join(pub, "probe.mp4"))
    dl_s = round(time.time() - t_dl, 1)
    src_bytes = os.path.getsize("/work/probe.mp4")

    jobs = []
    for zt in ZOOM_TYPES:
        for tag, n in (("short", short_frames), ("long", long_frames)):
            p = f"/work/micro-{zt}-{tag}.json"
            with open(p, "w") as fh:
                json.dump(_plan(zt, n, fps), fh)
            jobs.append({"id": f"{zt}:{tag}", "composition": "PromptlyMicroSegments",
                         "propsFile": p, "out": f"/work/micro-{zt}-{tag}.mp4"})

    t0 = time.time()
    res = AE.render_remotion_batch(jobs, env=AE._SUBPROCESS_ENV, timeout=2200)
    wall = round(time.time() - t0, 1)

    # ONE ALPHA JOB IN THE SAME PROCESS, as the in-run control. The whole claim
    # is a RATIO between micro and overlay paint, and a ratio across two runs on
    # two machines is not a ratio — it is two numbers. Same process, same
    # container, same bundle.
    cap_plan = "/work/cap-probe.json"
    _pages = [{"startMs": i * 400, "durationMs": 380, "text": "probe caption",
               "tokens": [{"text": "probe", "fromMs": i * 400, "toMs": i * 400 + 190},
                          {"text": "caption", "fromMs": i * 400 + 190,
                           "toMs": i * 400 + 380}]} for i in range(4)]
    with open(cap_plan, "w") as fh:
        json.dump(AE.caption_overlay_plan(_pages, "CleanCut", long_frames, fps=fps), fh)
    cap_short = "/work/cap-probe-short.json"
    with open(cap_short, "w") as fh:
        json.dump(AE.caption_overlay_plan(_pages, "CleanCut", short_frames, fps=fps), fh)
    cap_res = AE.render_remotion_batch(
        [{"id": "cap:short", "composition": "PromptlyOverlay",
          "propsFile": cap_short, "out": "/work/cap-short.mov", "alpha": True},
         {"id": "cap:long", "composition": "PromptlyOverlay",
          "propsFile": cap_plan, "out": "/work/cap-long.mov", "alpha": True}],
        env=AE._SUBPROCESS_ENV, timeout=900)

    # ── DID THE ZOOM ACTUALLY RENDER THE FOOTAGE? ───────────────────────────
    # A CLEAN ZERO IS GUILTY UNTIL PROVEN INNOCENT. The first run of this probe
    # returned a MEDIAN OF -0.5 ms/frame across all seven types — 34 frames
    # rendering faster than 10 — with every job reporting ok=true. That is not a
    # fast renderer, it is a renderer painting nothing, and reported as a rate it
    # would have been a failed measurement wearing a confident number.
    #
    # So the timing is not believed until the OUTPUT is inspected: real bytes,
    # real luma, and a frame that is not identical to the frame a zoom of a
    # different scale would produce. An empty or black composition is cheap to
    # paint and indistinguishable from a fast one in the clock alone.
    verify = {}
    for zt in ZOOM_TYPES:
        f = f"/work/micro-{zt}-long.mp4"
        v = {"exists": os.path.exists(f),
             "bytes": os.path.getsize(f) if os.path.exists(f) else 0}
        if v["exists"] and v["bytes"]:
            try:
                r2 = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-nostats", "-i", f,
                     "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG",
                     "-f", "null", "-"],
                    capture_output=True, text=True, timeout=120,
                    env=AE._SUBPROCESS_ENV)
                ys = [float(x) for x in __import__("re").findall(
                    r"lavfi\.signalstats\.YAVG=([0-9.]+)",
                    (r2.stdout or "") + (r2.stderr or ""))]
                v["y_mean"] = round(sum(ys) / len(ys), 1) if ys else None
                v["y_frames"] = len(ys)
                v["y_moves"] = (round(max(ys) - min(ys), 2) if ys else None)
            except Exception as e:
                v["y_error"] = str(e)[:120]
        verify[zt] = v

    return {"micro": res, "overlay": cap_res, "wall_s": wall, "dl_s": dl_s,
            "verify": verify,
            "src_bytes": src_bytes, "short": short_frames, "long": long_frames,
            "fps": fps,
            "concurrency": os.environ.get("PROMPTLY_REMOTION_CONCURRENCY", "8 (default)")}


def _marginal(res, key, short_n, long_n):
    a = (res or {}).get(f"{key}:short") or {}
    b = (res or {}).get(f"{key}:long") or {}
    if not (a.get("ok") and b.get("ok")):
        return None, (a.get("error") or b.get("error") or "job did not run")
    d = long_n - short_n
    if d <= 0:
        return None, "frame counts do not differ"
    return round((b["ms"] - a["ms"]) / d, 1), None


@app.local_entrypoint()
def main(src_url: str, short_frames: int = 10, long_frames: int = 34):
    r = measure.remote(src_url, short_frames, long_frames)
    short_n, long_n = r["short"], r["long"]
    print(f"\n=== MICRO-SEGMENT PAINT, THIS LANE'S CONTAINER ===")
    print(f"  source {r['src_bytes']:,} bytes (dl {r['dl_s']}s)   "
          f"concurrency {r['concurrency']}   batch wall {r['wall_s']}s")
    print(f"  marginal over {long_n - short_n} frames ({short_n} -> {long_n}), "
          f"so selectComposition and encoder startup are DIFFERENCED OUT\n")
    mb = (r["micro"] or {}).get("_batch") or {}
    ob = (r["overlay"] or {}).get("_batch") or {}
    print(f"  micro batch  : bundle {(mb.get('bundle_ms') or 0)/1000:.1f}s  "
          f"{mb.get('jobs')} jobs  rc={mb.get('returncode')}")
    print(f"  overlay batch: bundle {(ob.get('bundle_ms') or 0)/1000:.1f}s  "
          f"{ob.get('jobs')} jobs  rc={ob.get('returncode')}")
    if mb.get("stderr_tail"):
        print(f"  micro stderr : {mb['stderr_tail']}")

    print(f"\n  {'zoom type':<16}{'ms/frame':>10}   note")
    rates = {}
    for zt in ZOOM_TYPES:
        rate, err = _marginal(r["micro"], zt, short_n, long_n)
        rates[zt] = rate
        print(f"  {zt:<16}{(f'{rate:.1f}' if rate is not None else 'FAILED'):>10}"
              f"   {err or ''}")
    ov_rate, ov_err = _marginal(r["overlay"], "cap", short_n, long_n)
    print(f"  {'(overlay ctrl)':<16}{(f'{ov_rate:.1f}' if ov_rate is not None else 'FAILED'):>10}"
          f"   {ov_err or 'PromptlyOverlay, same process — the in-run control'}")

    # ── THE OUTPUT, BEFORE ANY RATE IS BELIEVED ─────────────────────────────
    print(f"\n  {'zoom type':<16}{'bytes':>10}{'Y mean':>9}{'Y range':>9}{'frames':>8}   verdict")
    _blank = []
    for zt in ZOOM_TYPES:
        v = (r.get("verify") or {}).get(zt) or {}
        _y = v.get("y_mean")
        _bad = (not v.get("exists")) or v.get("bytes", 0) < 2000 or _y is None or _y < 3.0
        if _bad:
            _blank.append(zt)
        # PRE-FORMATTED, not nested inside the f-string. A nested same-quote
        # f-string is PEP 701 and parses on 3.12+; the modal CLI ships 3.9 and
        # dies with SyntaxError before the app is even sent.
        _ystr = "%.1f" % _y if _y is not None else "—"
        _mv = v.get("y_moves")
        _mstr = "%.2f" % _mv if _mv is not None else "—"
        _verd = "BLANK — nothing painted" if _bad else "carries footage"
        print("  %-16s%10s%9s%9s%8s   %s" % (
            zt, "{:,}".format(v.get("bytes", 0)), _ystr, _mstr,
            v.get("y_frames", 0), _verd))
    if _blank:
        print(f"\n  ❌ INSTRUMENT FAILURE — {len(_blank)}/{len(ZOOM_TYPES)} outputs "
              f"carry no picture: {_blank}")
        print("     The composition rendered without error and painted nothing, so "
              "every ms/frame below\n     is the cost of painting NOTHING. Do not "
              "read a zoom rate out of this run.")
        print("     Root-cause the source resolution before re-running; a rate is "
              "not a result.")

    ok = [v for v in rates.values() if v is not None]
    if not ok:
        print("\n  EVERY TYPE FAILED — this is an instrument failure, not a "
              "result. Do not read a rate out of it.")
        return
    med = sorted(ok)[len(ok) // 2]
    print(f"\n  measured on {len(ok)}/{len(ZOOM_TYPES)} types   "
          f"median {med:.1f} ms/frame   range {min(ok):.1f}-{max(ok):.1f}")
    if ov_rate:
        print(f"  micro/overlay ratio IN THIS RUN: {med / ov_rate:.1f}x   "
              f"(production's organic ratio was 9.2x: 1047.8 vs 114.5)")

    # ── WHAT IT MEANS FOR THE BUDGET, computed here rather than by hand ──────
    # talking_head, round 33: source 38.5s = 1.54 units of 25s; the reference
    # zoom rate is 0.35/25s, so 0.54 zooms; mean natural duration across the
    # seven types is 1.37s. Today's ffmpeg zoom cost 2.28s of wall.
    exp_zooms = 1.54 * 0.35
    mean_frames = exp_zooms * 1.37 * 30
    for label, rate in (("MEASURED HERE", med), ("production p50", 1047.8)):
        add = mean_frames * rate / 1000.0
        print(f"  at {label:<15}: {mean_frames:.0f} frames -> {add:.1f}s, "
              f"net {add - 2.28:+.1f}s against today's ffmpeg zoom")
    print("\n  (a rate is a rate: three zooms on one job cost 3x this, and the "
          "corpus places 3 on music)")
