#!/usr/bin/env python3
"""
Generate professional sound effects library via ElevenLabs API.

Usage:
    export ELEVENLABS_API_KEY="your_key_here"
    python3 scripts/generate_sfx.py

Requires: pip install elevenlabs (or requests)
Cost: ~6,000 credits (~$1 on Starter plan at $5/mo)

Generated files are saved to src/assets/sounds/ and committed to the repo.
No runtime API calls needed — these ship with the container.
"""

import os
import sys
import time
import requests

API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not API_KEY:
    print("ERROR: Set ELEVENLABS_API_KEY environment variable")
    print("Sign up at https://elevenlabs.io — Starter plan is $5/mo (30K credits)")
    sys.exit(1)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "assets", "sounds")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Each entry: (filename, prompt, duration_seconds)
# 200 credits per generation (auto-duration) or 40 credits/second (manual)
# Using manual durations to control cost: 30 sounds × ~1.5s avg = ~1,800 credits
SFX_LIBRARY = [
    # === TRANSITION SOUNDS ===
    ("whoosh_fast", "fast cinematic whoosh transition swoosh, short and punchy", 0.8),
    ("whoosh_slow", "slow atmospheric cinematic whoosh, smooth and wide", 1.5),
    ("transition_smooth", "smooth soft cinematic transition sound, gentle whoosh with subtle reverb", 1.2),
    ("swipe", "quick digital swipe transition sound, clean and modern", 0.6),

    # === IMPACT SOUNDS ===
    ("bass_drop", "deep heavy sub-bass drop impact, cinematic, powerful", 1.5),
    ("boom", "explosive cinematic boom with sub-bass rumble, dramatic", 2.0),
    ("punch", "physical punch impact hit, meaty and solid with short decay", 0.8),
    ("slam", "heavy door slam impact, powerful and abrupt", 0.7),

    # === RISERS & STINGERS ===
    ("riser", "cinematic tension riser building upward, increasing pitch and intensity", 2.5),
    ("riser_short", "short quick riser swell building tension, 1 second", 1.0),
    ("stinger", "dramatic orchestral stinger hit, short and impactful, movie trailer style", 1.5),
    ("reveal", "magical reveal sound with sparkle and shimmer, discovery moment", 1.5),

    # === UI & NOTIFICATION ===
    ("notification", "modern clean UI notification sound, subtle and pleasant digital chime", 0.8),
    ("text_appear", "soft digital text appearing sound, subtle typing pop, modern UI", 0.5),
    ("click", "clean precise digital click, user interface button press", 0.3),
    ("unlock", "satisfying achievement unlock sound, positive digital chime with sparkle", 1.0),

    # === COMEDY & EXPRESSIVE ===
    ("vinyl_scratch", "vinyl record scratch sound, DJ stopping the music abruptly", 1.0),
    ("sad_trombone", "sad trombone wah wah wah, comedic failure sound, 3 descending notes", 2.0),
    ("boing", "cartoonish spring boing bounce sound, playful and bouncy", 0.6),
    ("fart", "short comedic fart sound effect, whoopee cushion style", 0.5),
    ("record_stop", "vinyl record stopping abruptly with slow down effect", 1.2),

    # === ATMOSPHERIC & TEXTURE ===
    ("static", "TV static white noise burst, short and sharp", 0.8),
    ("tape_rewind", "VHS tape rewind sound, analog retro", 1.0),
    ("glitch", "digital data glitch corruption sound, short electronic distortion", 0.6),
    ("heartbeat", "single dramatic heartbeat thump, deep and resonant", 1.0),

    # === NATURE & ENVIRONMENT ===
    ("wind_gust", "short wind gust whoosh, outdoor atmospheric", 1.5),
    ("thunder", "distant rolling thunder rumble, dramatic and atmospheric", 2.5),

    # === CAMERA & MECHANICAL ===
    ("camera_flash", "professional DSLR camera shutter click with flash capacitor charging", 0.8),
    ("switch", "mechanical toggle switch click, satisfying tactile sound", 0.3),
    ("page_turn", "crisp paper page turning sound, book or magazine", 0.5),
]


def generate_sfx(name, prompt, duration):
    """Generate a single SFX via ElevenLabs API."""
    output_path = os.path.join(OUTPUT_DIR, f"{name}.mp3")

    # Skip if already exists
    if os.path.exists(output_path):
        size = os.path.getsize(output_path)
        if size > 1000:  # >1KB = probably valid
            print(f"  SKIP {name} (already exists, {size // 1024}KB)")
            return True

    print(f"  Generating {name} ({duration}s): \"{prompt}\"")

    try:
        resp = requests.post(
            "https://api.elevenlabs.io/v1/sound-generation",
            headers={
                "xi-api-key": API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "text": prompt,
                "duration_seconds": duration,
                "prompt_influence": 0.5,
            },
            timeout=30,
        )

        if resp.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(resp.content)
            size = os.path.getsize(output_path)
            print(f"  OK {name}: {size // 1024}KB")
            return True
        else:
            print(f"  FAIL {name}: HTTP {resp.status_code} — {resp.text[:200]}")
            return False

    except Exception as e:
        print(f"  FAIL {name}: {e}")
        return False


def main():
    print(f"ElevenLabs SFX Generator")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Sounds: {len(SFX_LIBRARY)}")
    print(f"Est. credits: ~{sum(int(s[2] * 40) for s in SFX_LIBRARY)} (manual duration)")
    print()

    success = 0
    fail = 0
    for name, prompt, duration in SFX_LIBRARY:
        ok = generate_sfx(name, prompt, duration)
        if ok:
            success += 1
        else:
            fail += 1
        # Rate limit: don't hammer the API
        time.sleep(0.5)

    print()
    print(f"Done: {success} generated, {fail} failed")
    print(f"Files in: {OUTPUT_DIR}")
    if fail > 0:
        print("Re-run to retry failed generations (existing files are skipped)")


if __name__ == "__main__":
    main()
