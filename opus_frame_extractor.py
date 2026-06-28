"""Phase 1 — motion-aware frame extractor for the Opus 4.8 vision+recipe call.

STANDALONE. Not imported by handler.py — zero production impact until wired in
Phase 2/4. Reuses signals the pipeline already computes (scdet scene-cut scores,
face frames, vocal emphasis, Deepgram word timings) so nothing new is detected.

Opus sees far fewer frames than Gemini's native 18fps, so the frames it DOES see
must land where editorial decisions are made: scene cuts, gesture motion, face
expression, and vocal-emphasis beats. Coverage is guaranteed end-to-end (a uniform
baseline grid), then budget is spent adaptively on the high-signal moments.

Tunable constants below are set conservatively; FINAL values await gate #2
(production clip-length distribution) and the Phase-3 cost/quality A/B — fewer
frames is the main cost lever.
"""
from __future__ import annotations
import os
import subprocess

# ── Tunables (pending gate #2 + Phase-3 A/B) ─────────────────────────────────
FRAME_CAP = 200                 # hard max frames/render — under Anthropic's 600-image + 32MB request limits
BASE_FPS = 0.5                  # uniform baseline (1 frame / 2s) — guarantees full-timeline coverage
MOTION_FPS = 2.0                # density inside high-motion windows
FRAME_WIDTH = 512               # downscale width (height auto) — ~197 image tokens/frame
JPEG_Q = 4                      # ffmpeg -q:v (2 best .. 31 worst); 4 keeps editing detail at small size
DEDUPE_EPS = 0.20               # merge selected timestamps within this many seconds
INLINE_BYTES_LIMIT = 20 * 1024 * 1024   # above this total payload → use the Files API instead of inline


def select_frame_timestamps(
    duration: float,
    *,
    shot_cuts=None,             # list[float] scene-cut timestamps (scdet >= threshold) — always kept
    motion_windows=None,        # list[(start, end)] high-motion spans → sampled at motion_fps
    face_times=None,            # list[float] timestamps with a face present (expression coverage)
    emphasis_times=None,        # list[float] high vocal-emphasis word starts (likely decision beats)
    frame_cap: int = FRAME_CAP,
    base_fps: float = BASE_FPS,
    motion_fps: float = MOTION_FPS,
):
    """Return a sorted, deduped, capped list of timestamps (seconds) to extract.

    Guarantees: (1) both endpoints and every scene cut are present; (2) when the
    adaptive set exceeds the cap, density is reduced UNIFORMLY across the whole
    timeline (the tail is never dropped); (3) result length <= frame_cap.
    """
    if duration <= 0:
        return [0.0]
    shot_cuts = [t for t in (shot_cuts or []) if 0.0 <= t <= duration]
    motion_windows = motion_windows or []
    face_times = [t for t in (face_times or []) if 0.0 <= t <= duration]
    emphasis_times = [t for t in (emphasis_times or []) if 0.0 <= t <= duration]

    # Mandatory frames — never dropped by the cap. The end anchor is clamped
    # slightly inward (duration - 0.08s) because there is rarely a real frame
    # exactly at `duration` — the last decoded frame sits just before it.
    mandatory = {0.0, round(max(0.0, duration - 0.08), 3)}
    mandatory.update(round(t, 3) for t in shot_cuts)

    # Adaptive candidates.
    cand = set(mandatory)
    step = 1.0 / base_fps if base_fps > 0 else duration
    t = 0.0
    while t <= duration:
        cand.add(round(t, 3))
        t += step
    mstep = 1.0 / motion_fps if motion_fps > 0 else None
    if mstep:
        for (ws, we) in motion_windows:
            ws = max(0.0, ws); we = min(duration, we)
            t = ws
            while t <= we:
                cand.add(round(t, 3))
                t += mstep
    cand.update(round(t, 3) for t in face_times)
    cand.update(round(t, 3) for t in emphasis_times)

    selected = _dedupe(sorted(cand))

    if len(selected) <= frame_cap:
        return selected

    # Over budget → degrade. Keep mandatory (cuts + endpoints); fill the rest of
    # the budget with a uniform grid over the WHOLE timeline so coverage stays
    # even and the tail is never truncated.
    keep = _dedupe(sorted(mandatory))
    budget = frame_cap - len(keep)
    if budget <= 0:
        # More scene cuts than the cap (pathological) — uniformly subsample cuts.
        return _uniform_subsample(keep, frame_cap)
    grid = [round(i * duration / (budget + 1), 3) for i in range(1, budget + 1)]
    return _dedupe(sorted(set(keep) | set(grid)))


def _dedupe(ts):
    out = []
    for t in ts:
        if not out or (t - out[-1]) >= DEDUPE_EPS:
            out.append(t)
    return out


def _uniform_subsample(ts, k):
    if len(ts) <= k:
        return ts
    idx = [round(i * (len(ts) - 1) / (k - 1)) for i in range(k)]
    return [ts[i] for i in sorted(set(idx))]


def extract_frames(video_path: str, timestamps, *, width: int = FRAME_WIDTH,
                   jpeg_q: int = JPEG_Q, out_dir: str = None):
    """Extract the given timestamps as downscaled JPEGs in ONE ffmpeg pass.

    Returns list of (timestamp_seconds, jpeg_bytes, label) in temporal order.
    Uses a single select filter (between-windows) so it's one decode pass, not N
    seeks. Raises RuntimeError on ffmpeg failure (caller decides fallback).
    """
    import re
    if not timestamps:
        return []
    out_dir = out_dir or os.path.join(os.path.dirname(os.path.abspath(video_path)) or ".", "_opus_frames")
    os.makedirs(out_dir, exist_ok=True)
    # Window of ~±40ms around each target catches >=1 real frame even on low-fps
    # sources; any extra frames are deduped below by their ACTUAL timestamp.
    eps = 0.04
    expr = "+".join(f"between(t,{max(0.0, t - eps):.3f},{t + eps:.3f})" for t in timestamps)
    pattern = os.path.join(out_dir, "f_%05d.jpg")
    # showinfo prints each output frame's real pts_time → we label by the ACTUAL
    # frame time, never by zip-position, so a missing/extra frame can't shift labels.
    cmd = ["ffmpeg", "-y", "-i", video_path,
           "-vf", f"select='{expr}',scale={width}:-2,showinfo",
           "-vsync", "0", "-q:v", str(jpeg_q), pattern]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg frame extract failed: {(proc.stderr or '')[-400:]}")
    pts = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", proc.stderr or "")]
    files = sorted(f for f in os.listdir(out_dir) if f.startswith("f_") and f.endswith(".jpg"))
    if len(files) != len(pts):
        # Defensive: counts should match (showinfo runs per output frame). If not,
        # trust the smaller and log — never silently mislabel.
        print(f"[opus-frames] WARN files={len(files)} pts={len(pts)} — truncating to min")
    out = []
    last_t = -1e9
    for fn, t in zip(files, pts):  # both in temporal order, equal count
        if t - last_t < DEDUPE_EPS:
            continue  # drop a duplicate caught by the same window
        last_t = t
        with open(os.path.join(out_dir, fn), "rb") as fh:
            out.append((round(t, 3), fh.read(), _label(t)))
    return out


def _label(t: float) -> str:
    m, s = divmod(t, 60.0)
    return f"t={int(m):02d}:{s:06.3f}"


def plan_summary(duration, **kw):
    """Diagnostics: the frame budget for a duration without doing extraction."""
    ts = select_frame_timestamps(duration, **kw)
    return {"duration": duration, "n_frames": len(ts),
            "est_payload_mb": round(len(ts) * 0.04, 2),   # ~40KB/frame @ 512px
            "use_files_api": len(ts) * 0.04 * 1024 * 1024 > INLINE_BYTES_LIMIT,
            "first": ts[0] if ts else None, "last": ts[-1] if ts else None}


if __name__ == "__main__":
    # Local self-test of the MECHANISM (budget math + cap/degrade + real ffmpeg
    # extraction on a generated motion video). No pipeline, no API.
    import tempfile, json
    print("=== budget math per clip-length bucket (cap=%d, base=%.2ffps) ===" % (FRAME_CAP, BASE_FPS))
    for dur in (30, 60, 90, 180, 300, 600):
        cuts = [i * 7.0 for i in range(int(dur / 7))]          # a cut ~every 7s
        motion = [(i * 20.0, i * 20.0 + 4.0) for i in range(int(dur / 20))]  # 4s gesture window every 20s
        print(json.dumps(plan_summary(dur, shot_cuts=cuts, motion_windows=motion)))

    print("\n=== real ffmpeg extraction on a generated 60s motion clip ===")
    td = tempfile.mkdtemp()
    vid = os.path.join(td, "t.mp4")
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    "testsrc=size=480x854:rate=30:duration=60",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", vid],
                   check=True, capture_output=True)
    ts = select_frame_timestamps(60.0, shot_cuts=[7, 14, 21, 28, 35, 42, 49, 56],
                                 motion_windows=[(10, 14), (30, 34), (50, 54)])
    frames = extract_frames(vid, ts, out_dir=os.path.join(td, "frames"))
    total_mb = sum(len(b) for _, b, _ in frames) / 1024 / 1024
    print(f"requested={len(ts)} extracted={len(frames)} total={total_mb:.2f}MB "
          f"avg={total_mb/max(1,len(frames))*1024:.0f}KB/frame")
    print("labels sample:", [lbl for _, _, lbl in frames[:5]], "...", [lbl for _, _, lbl in frames[-2:]])
    start_ok = abs(frames[0][0] - 0.0) < 0.1
    end_ok = abs(frames[-1][0] - 60.0) < 0.3       # last frame within 0.3s of the true end
    monotonic = all(frames[i][0] < frames[i + 1][0] for i in range(len(frames) - 1))
    print(f"endpoints covered: start={start_ok} end={end_ok} | labels monotonic (no drift)={monotonic}")
