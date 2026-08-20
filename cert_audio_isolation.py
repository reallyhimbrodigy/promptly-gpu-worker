#!/usr/bin/env python3
"""cert_audio_isolation.py — THE SPEAKER'S AUDIO IS THE ONLY AUDIO.

THE LAW: a cutaway is VISUAL ONLY. A full-frame b-roll clip or insert scene
replaces the talking head while the speaker keeps talking underneath. If any
mechanism can interrupt or talk over speech, it is not a cutaway.

WHY THIS CERT EXISTS — the law held BY ACCIDENT. Investigated 2026-08-20:

  * `BrollClip` renders a full-frame `<Video>` with NO `muted` prop. Its stock
    audio WOULD play over the speaker.
  * It does not, because the final mux is `-map 0:v` / `-map 1:a` — video from
    the visual render, audio from final_audio.wav ONLY. Everything the visual
    render carries as audio is discarded.

So the single property the entire cutaway capability rests on was protected by
ONE ffmpeg flag, with nothing asserting it and nothing stating the intent at the
component. Anyone adding an audio path to the visual render, or touching that
mapping, would have silently put stock audio over a user's speech.

TWO CLAUSES, BOTH LOAD-BEARING — belt AND suspenders, deliberately:

  1  INTENT AT THE COMPONENT. Every <Video>/<OffthreadVideo> in the PRODUCTION
     render tree carries `muted`. This is what makes the law true locally
     instead of true-by-side-effect.
  2  ISOLATION AT THE MUX. The final mux takes video from the render and audio
     from final_audio.wav ONLY. This is what makes it true globally even if a
     new component forgets clause 1.

Either alone is a single point of failure. Clause 1 without clause 2 means a
future component that forgets `muted` leaks. Clause 2 without clause 1 means the
law is invisible to anyone reading the renderer.

    python3 cert_audio_isolation.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The PRODUCTION render tree. Probes (GenSceneProbe, ZoomTagProbe) are excluded
# BY NAME and listed here so the exclusion is a claim someone can check, not a
# silent gap in coverage.
TREE = ["src/remotion/src/PromptlyRender.tsx",
        "src/remotion/src/FrameCompositions.tsx"]
EXCLUDED = ["GenSceneProbe.tsx", "ZoomTagProbe.tsx"]   # not mounted in production


def _video_elements(src):
    """Every <Video ...> / <OffthreadVideo ...> element with its attribute text."""
    out = []
    for m in re.finditer(r"<(Video|OffthreadVideo)\b", src):
        depth, i = 0, m.end()
        while i < len(src):
            if src[i] == ">" and depth == 0:
                break
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
            i += 1
        out.append((m.group(1), m.start(), src[m.end():i]))
    return out


def main():
    fails = []

    # ── 1: intent at the component ──────────────────────────────────────────
    total = 0
    for rel in TREE:
        p = os.path.join(HERE, rel)
        if not os.path.exists(p):
            fails.append(f"{rel} is missing — the render tree moved and this "
                         f"cert is no longer covering it")
            continue
        src = open(p, encoding="utf-8").read()
        for tag, off, attrs in _video_elements(src):
            total += 1
            line = src[:off].count("\n") + 1
            if not re.search(r"\bmuted\b", attrs):
                fails.append(f"{os.path.basename(rel)}:{line} <{tag}> has NO "
                             f"`muted` — it can put audio over the speaker")
    print(f"  [1] video elements in the production tree: {total}, all muted: "
          f"{not fails}")
    if total == 0:
        fails.append("found ZERO video elements — the matcher is broken, and a "
                     "cert that inspects nothing passes everything")

    # ── 2: isolation at the mux ─────────────────────────────────────────────
    h = open(os.path.join(HERE, "handler.py"), encoding="utf-8").read()
    got_v = '"-map", "0:v"' in h
    got_a = '"-map", "1:a"' in h
    print(f"  [2] final mux maps video 0:v = {got_v}   audio 1:a = {got_a}")
    if not (got_v and got_a):
        fails.append("the final mux no longer maps video from the render and "
                     "audio from final_audio.wav ONLY — the visual track's "
                     "audio can now reach the output")
    # and the audio the mux trusts must still be the per-cut build
    if "final_audio.wav" not in h:
        fails.append("final_audio.wav is gone — the independent audio bed that "
                     "makes a full-frame takeover safe no longer exists")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT AUDIO-ISOLATION: FAIL")
        return 1
    print(f"  (probes excluded by name, not mounted in production: {EXCLUDED})")
    print("  CERT AUDIO-ISOLATION: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
