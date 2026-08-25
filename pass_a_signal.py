#!/usr/bin/env python3
"""pass_a_signal.py — PASS A, EXTENDED: what is HEARD, and how motion MOVES.

Both are ffmpeg-derived. No model, no cost, and they measure two things the
model structurally cannot.

WHY AUDIO. The corpus as specced records what is ON SCREEN and nothing about
what is HEARD. A cut landing on a drum hit and the same cut landing 200ms off it
are different edits, and every frame-based instrument we have scores them
identically. Editing is substantially an audio craft and the corpus was deaf.

WHY NATIVE-FPS MOTION. Pass B samples at 2fps to match the live proxy. At 2fps a
500ms ease-in and a 500ms hard snap are THE SAME TWO FRAMES — smoothness is
below the sampling floor. The model cannot see it, we cannot ask it about it, and
no amount of prompting fixes a measurement that was never taken. A per-frame
difference curve at NATIVE fps is the only instrument that can distinguish
eased / linear / held, which is the property the smoothness work has been
arguing about without a number.
"""
import json
import re
import subprocess


def _run(args, timeout=300):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.stdout + p.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def native_fps(path):
    out = _run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=r_frame_rate", "-of", "default=nw=1:nk=1", path])
    if not out:
        return None
    try:
        n, d = out.strip().split("/")
        return float(n) / float(d) if float(d) else None
    except Exception:
        return None


def motion_curve(path):
    """Per-frame difference score at NATIVE fps, via scdet=threshold=0.

    scdet emits lavfi.scd.score for EVERY frame when the threshold is 0, which is
    exactly a frame-difference curve — not a cut list. The cut list already comes
    from the scene filter in Pass A; this is the SHAPE BETWEEN cuts.

    Returns None on probe failure — NOT an empty curve. A still video and a
    failed probe are different facts and the spec's whole discipline is that they
    must never collapse together.
    """
    out = _run(["ffmpeg", "-i", path, "-vf", "scdet=threshold=0,metadata=print:file=-",
                "-an", "-f", "null", "-"])
    if out is None:
        return None
    scores = [float(m) for m in re.findall(r"lavfi\.scd\.score=([0-9.]+)", out)]
    return scores or None


def classify_motion(scores, fps, cuts, window_s=0.6):
    """eased | linear | held | snap, per cut, from the curve AFTER each cut.

    The shape of the difference curve in the ~600ms following a cut is the
    motion character: a push that ramps produces a RISING then FALLING curve; a
    linear move is flat; a held frame is near-zero; a snap is one spike.

    Thresholds are deliberately coarse. This is a first instrument and a
    confident fine-grained label would be false precision — the useful output
    today is a DISTRIBUTION across the corpus, not a verdict per cut.
    """
    if not scores or not fps or not cuts:
        return []
    n = max(2, int(window_s * fps))
    out = []
    for t in cuts:
        i = int(t * fps)
        w = scores[i:i + n]
        if len(w) < 3:
            continue
        mx, mean = max(w), sum(w) / len(w)
        if mx < 0.02:
            kind = "held"
        elif mx > 0.25 and mean < mx * 0.35:
            kind = "snap"          # one spike, quiet either side
        elif mean > mx * 0.6:
            kind = "linear"        # sustained, flat
        else:
            kind = "eased"         # ramps up and settles
        out.append({"t": round(t, 3), "kind": kind,
                    "peak": round(mx, 4), "mean": round(mean, 4)})
    return out


def audio_envelope(path):
    """RMS per ~100ms frame, plus onsets derived from RMS RISES.

    Onsets are computed from the envelope rather than asked of a model, for the
    same reason ffmpeg owns the cuts: a model asked to locate a hit will locate
    one. Returns None on probe failure.
    """
    out = _run(["ffmpeg", "-i", path, "-af",
                "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
                "-vn", "-f", "null", "-"])
    if out is None:
        return None
    frames = []
    for m in re.finditer(r"pts_time:([0-9.]+)[\s\S]{0,200}?RMS_level=(-?[0-9.inf]+)", out):
        try:
            frames.append((float(m.group(1)), float(m.group(2))))
        except ValueError:
            continue
    if not frames:
        return None
    # ONSET = a rise of >= 6 dB over the previous frame. 6 dB is a doubling of
    # amplitude; below that we would be labelling noise as hits.
    onsets = [round(t, 3) for i, (t, r) in enumerate(frames)
              if i and (r - frames[i - 1][1]) >= 6.0]
    lv = [r for _, r in frames]
    return {"n_frames": len(frames),
            "rms_mean_db": round(sum(lv) / len(lv), 2),
            "rms_min_db": round(min(lv), 2), "rms_max_db": round(max(lv), 2),
            "onsets_s": onsets[:400], "n_onsets": len(onsets)}


def cut_onset_join(cuts, onsets, tol_s=0.12):
    """THE JOIN THAT MATTERS: how close does each cut land to an audio onset?

    A cut on the hit and a cut 200ms off it are different edits that every
    frame-based score treats identically. `aligned_frac` is the number this
    exists to produce — and if it turns out high across the corpus, cutting to
    audio is a rule we are not following and can start following.
    """
    if not cuts or not onsets:
        return None
    deltas = [min(abs(c - o) for o in onsets) for c in cuts]
    aligned = sum(1 for d in deltas if d <= tol_s)
    return {"n_cuts": len(cuts), "tol_s": tol_s,
            "aligned": aligned, "aligned_frac": round(aligned / len(cuts), 3),
            "median_delta_s": round(sorted(deltas)[len(deltas) // 2], 3)}


def analyse(path, cuts):
    fps = native_fps(path)
    scores = motion_curve(path)
    audio = audio_envelope(path)
    return {
        "native_fps": fps,
        # UNMEASURED is distinct from "no motion"/"silent" everywhere below.
        "motion_curve_frames": len(scores) if scores is not None else None,
        "motion_per_cut": classify_motion(scores, fps, cuts) if scores else [],
        "audio": audio,
        "cut_onset_join": cut_onset_join(cuts, (audio or {}).get("onsets_s") or []),
    }


if __name__ == "__main__":
    import sys
    print(json.dumps(analyse(sys.argv[1], []), indent=1)[:2000])
