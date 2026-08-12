#!/usr/bin/env python3
"""Background music v1 cert — REAL ffmpeg, local, $0.

72 recorded asks. The machinery is dark; what has to be certified is not "does
ffmpeg run" but the two things that decide whether this is safe to own:

  1. A PLACEHOLDER CAN NEVER REACH A USER. Every bed in assets/music/ is
     synthesized and marked deliverable:false. Bed selection refuses anything
     not explicitly deliverable, so flipping the flag today delivers NO music
     and says so honestly. The audio a user receives is gated on the owner's
     licensing pick, not on a flag.
  2. THE DUCK IS REAL AND MEASURED. The bed must actually drop under speech,
     verified by measuring both sections of a rendered mix — not by trusting a
     filter string that ffmpeg happily accepts and silently mis-wires.

  python3 cert_music_v1.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  [PASS] {label}")
    else:
        FAILURES.append(f"{label}{(' — ' + detail) if detail else ''}")
        print(f"  [FAIL] {label}{(' — ' + detail) if detail else ''}")


def mean_db(path, start, dur):
    """mean_volume of one window, via volumedetect."""
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-ss", str(start), "-t", str(dur),
         "-i", path, "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, timeout=120)
    m = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", (r.stderr or b"").decode())
    return float(m.group(1)) if m else None


def main():
    os.environ.pop("PROMPTLY_MUSIC_V1", None)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import handler as H

    print("=== ARM 1: DARK by default ===")
    check("flag off", H._music_v1_enabled({}) is False)
    check("per-job test override works", H._music_v1_enabled({"music_v1_test": True}) is True)

    print("\n=== ARM 2: the ask detector (negation-guarded) ===")
    P = H._parse_music_request
    for t in ["add background music", "can you put some music under it",
              "add a soundtrack", "music bed please", "I want music"]:
        check(f"detects {t!r}", P(t) is True)
    for t in ["no music", "without background music", "don't add music",
              "remove the music", "make it punchy"]:
        check(f"NOT a request: {t!r}", P(t) is False)

    print("\n=== ARM 3: A PLACEHOLDER CAN NEVER BE DELIVERED ===")
    tracks = H._music_load_manifest()
    check("the library loads", len(tracks) >= 2, f"{len(tracks)} tracks")
    check("EVERY shipped track is marked deliverable:false",
          all(t.get("deliverable") is not True for t in tracks),
          repr([t.get("id") for t in tracks if t.get("deliverable") is True]))
    check("every track carries a licence record",
          all(str(t.get("licence") or "") for t in tracks))
    check("bed selection REFUSES the placeholder library",
          H._music_pick_bed("bright viral energetic") is None,
          "a placeholder was selected — it could reach a user")
    check("no fit -> the honest note, never silence",
          H._music_note(False) == H._MUSIC_NO_FIT_NOTE)
    check("the honest note explains WHY (rights, not a shrug)",
          "rights" in H._MUSIC_NO_FIT_NOTE and "licence" in H._MUSIC_NO_FIT_NOTE)

    # ...and it DOES select once a track is genuinely deliverable.
    tmpdir = tempfile.mkdtemp(prefix="music-cert-")
    try:
        src_dir = H._MUSIC_DIR
        for f in os.listdir(src_dir):
            shutil.copy(os.path.join(src_dir, f), os.path.join(tmpdir, f))
        man = json.load(open(os.path.join(tmpdir, "manifest.json")))
        for t in man["tracks"]:
            t["deliverable"] = True
            t["licence"] = "TEST-ONLY"
        json.dump(man, open(os.path.join(tmpdir, "manifest.json"), "w"))
        picked = H._music_pick_bed("bright viral energetic", music_dir=tmpdir)
        check("a DELIVERABLE library is selected from", picked is not None)
        check("mood matching works (viral -> bright_lift)",
              picked and picked.get("id") == "bright_lift", repr(picked and picked.get("id")))
        check("an unmatched vibe still gets a bed (never silent when one exists)",
              H._music_pick_bed("zzz nothing matches", music_dir=tmpdir) is not None)
        check("delivered note names the track",
              "bright_lift" in H._music_note(True, picked))

        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            print("\nSKIP(no-ffmpeg) — the duck arms cannot run on this box.")
            return 1 if FAILURES else 0

        print("\n=== ARM 4: THE DUCK IS REAL — measured, not asserted ===")
        # speech proxy: silence for 4s, then a loud tone for 4s. The bed must be
        # audible in the silent half and pushed DOWN in the loud half.
        speech = os.path.join(tmpdir, "speech.wav")
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo:d=4",
                        "-f", "lavfi", "-i", "sine=frequency=300:duration=4:sample_rate=44100",
                        "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1,volume=2.0[o]",
                        "-map", "[o]", speech], capture_output=True, timeout=180)
        check("speech fixture built", os.path.exists(speech))

        music = os.path.join(tmpdir, str(picked["file"]))
        out = os.path.join(tmpdir, "mixed.wav")
        chain = H._music_filter_chain(music_label="1:a", speech_label="0:a", out_label="amixed")
        r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                            "-i", speech, "-i", music,
                            "-filter_complex", chain, "-map", "[amixed]",
                            "-t", "8", out], capture_output=True, timeout=300)
        check("the filter graph COMPILES and renders", r.returncode == 0 and os.path.exists(out),
              (r.stderr or b"")[-260:].decode(errors="replace"))

        if os.path.exists(out):
            quiet = mean_db(out, 0.5, 3.0)     # bed alone
            loud = mean_db(out, 4.5, 3.0)      # bed + speech, bed ducked
            check("both windows measurable", quiet is not None and loud is not None,
                  f"quiet={quiet} loud={loud}")
            # Bed-only must be quiet: present, never competing.
            # TWO-SIDED ON PURPOSE. The first version only asserted "not too
            # loud", which a SILENT bed also passes — and the first build
            # produced exactly that: -57.8 dBFS, inaudible, a no-op that the
            # cert called green. A bed must be present AND must not compete.
            check(f"bed is AUDIBLE (>= -40 dBFS): {quiet} dB",
                  quiet is not None and quiet >= -40.0,
                  f"{quiet} dB — an inaudible bed is the feature shipping as a no-op")
            check(f"bed does not compete (<= -18 dBFS): {quiet} dB",
                  quiet is not None and quiet <= -18.0, f"{quiet} dB")
            # The speech section is louder overall (voice on top) — that alone
            # does NOT prove ducking, so measure the BED's own contribution by
            # rendering the same speech with NO bed and comparing.
            nobed = os.path.join(tmpdir, "nobed.wav")
            subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                            "-i", speech, "-t", "8", nobed], capture_output=True, timeout=180)
            loud_nobed = mean_db(nobed, 4.5, 3.0)
            delta = (loud - loud_nobed) if (loud is not None and loud_nobed is not None) else None
            check("under speech the bed adds < 1.5 dB (it is DUCKED, not merely mixed)",
                  delta is not None and delta < 1.5,
                  f"bed added {delta:.2f} dB over speech-only" if delta is not None else "unmeasurable")
            print(f"       measured: bed-only {quiet:.1f} dB · speech+bed {loud:.1f} dB · "
                  f"speech-only {loud_nobed:.1f} dB · bed contribution {delta:+.2f} dB")

        print("\n=== ARM 5: the volume law is stated in numbers, not vibes ===")
        check("bed target is absolute (-28 LUFS), not a relative gain",
              H._MUSIC_BED_LUFS == -28.0 and "loudnorm" in chain)
        check("duck depth constant is -14 dB", H._MUSIC_DUCK_DB == -14.0)
        check("attack 20ms / release 400ms",
              H._MUSIC_ATTACK_MS == 20 and H._MUSIC_RELEASE_MS == 400)
        check("the duck is SIDECHAINED off the speech, not scheduled",
              "sidechaincompress" in chain and "asplit" in chain)
        check("speech is split (reusing one label yields an empty stream)",
              chain.count("asplit=2") == 1)
        check("amix does not auto-gain (normalize=0)", "normalize=0" in chain)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print()
    if FAILURES:
        print(f"MUSIC-V1 CERT: {len(FAILURES)} FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("MUSIC-V1 CERT: ALL PASS (dark, negation-guarded ask, placeholders UNDELIVERABLE, "
          "honest no-fit note, real sidechain duck measured, volume law pinned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
