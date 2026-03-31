"""
Fix: regenerate click and switch SFX with 0.5s minimum duration.
Usage: modal run scripts/generate_sfx_fix.py
"""
import modal
import os
import base64

app = modal.App("sfx-fix")
image = modal.Image.debian_slim(python_version="3.10").pip_install("requests")

SFX_FIX = [
    ("click", "clean precise digital click, user interface button press", 0.5),
    ("switch", "mechanical toggle switch click, satisfying tactile sound", 0.5),
]

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("promptly-secrets")],
    timeout=60,
)
def generate_fix_sfx():
    import requests
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        return {"error": "ELEVENLABS_API_KEY not found"}
    results = {}
    for name, prompt, duration in SFX_FIX:
        print(f"  Generating {name} ({duration}s)")
        resp = requests.post(
            "https://api.elevenlabs.io/v1/sound-generation",
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json={"text": prompt, "duration_seconds": duration, "prompt_influence": 0.5},
            timeout=30,
        )
        if resp.status_code == 200:
            results[name] = base64.b64encode(resp.content).decode()
            print(f"  OK {name}: {len(resp.content) // 1024}KB")
        else:
            print(f"  FAIL {name}: HTTP {resp.status_code} — {resp.text[:200]}")
    return results

@app.local_entrypoint()
def main():
    result = generate_fix_sfx.remote()
    if "error" in result:
        print(f"ERROR: {result['error']}")
        return
    output_dir = os.path.join(os.path.dirname(__file__), "..", "src", "assets", "sounds")
    for name, b64_data in result.items():
        path = os.path.join(output_dir, f"{name}.mp3")
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64_data))
        print(f"  Saved {name}.mp3 ({os.path.getsize(path) // 1024}KB)")
