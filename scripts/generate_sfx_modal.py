"""
One-shot Modal function to generate all SFX via ElevenLabs API.
Runs inside Modal where promptly-secrets are available.
Downloads generated files to local src/assets/sounds/.

Usage: modal run scripts/generate_sfx_modal.py
"""
import modal
import os
import base64
import json
import time

app = modal.App("sfx-generator")

image = modal.Image.debian_slim(python_version="3.10").pip_install("requests")

SFX_LIBRARY = [
    # (filename, prompt, duration_seconds)
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


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("promptly-secrets")],
    timeout=300,
)
def generate_all_sfx():
    import requests

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        return {"error": "ELEVENLABS_API_KEY not found in promptly-secrets"}

    results = {}
    success = 0
    fail = 0

    for name, prompt, duration in SFX_LIBRARY:
        print(f"  Generating {name} ({duration}s): \"{prompt}\"")
        try:
            resp = requests.post(
                "https://api.elevenlabs.io/v1/sound-generation",
                headers={
                    "xi-api-key": api_key,
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
                results[name] = base64.b64encode(resp.content).decode()
                print(f"  OK {name}: {len(resp.content) // 1024}KB")
                success += 1
            else:
                print(f"  FAIL {name}: HTTP {resp.status_code} — {resp.text[:200]}")
                fail += 1
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            fail += 1

        # Rate limit
        time.sleep(0.3)

    print(f"\nDone: {success} generated, {fail} failed")
    return {"files": results, "success": success, "fail": fail}


@app.local_entrypoint()
def main():
    print(f"Generating {len(SFX_LIBRARY)} sound effects via ElevenLabs...")
    print()

    result = generate_all_sfx.remote()

    if "error" in result:
        print(f"ERROR: {result['error']}")
        return

    output_dir = os.path.join(os.path.dirname(__file__), "..", "src", "assets", "sounds")
    os.makedirs(output_dir, exist_ok=True)

    files = result.get("files", {})
    saved = 0
    for name, b64_data in files.items():
        path = os.path.join(output_dir, f"{name}.mp3")
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64_data))
        size = os.path.getsize(path)
        print(f"  Saved {name}.mp3 ({size // 1024}KB)")
        saved += 1

    print(f"\n{saved} files saved to {output_dir}")
    print(f"Success: {result['success']}, Failed: {result['fail']}")
