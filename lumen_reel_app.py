"""LUMEN REEL — ephemeral Modal app (Wave-3 Task 5). `modal run lumen_reel_app.py`.

Renders FOUR designed scenes through the REAL production components
(GeneratedSceneLayer → LumenScene: TypoStat / HeroObject / PhotoCard — the
exact Pass-2 shell: camera micro-sway, idle drift, breathing glow, motion
blur, legibleOnDark v2) over a CONSTRUCTED source clip, at the canonical
30fps, 1080x1920 VERTICAL, via the LumenReel composition — ONE mp4 uploaded
to hype-samples/lumen-reel/ and the CloudFront URL printed.

Never deployed. The hero asset is generated with the REAL Nano-Banana path
(handler._generate_scene_subject: alpha-forced, hex-scrubbed); if generation
is unavailable the hero scene is dropped and the reel ships with the three
pure-code scenes (reported honestly — no placeholder ever renders).

Scene 4 deliberately carries a 2-COLOR dark palette — the exact v1
legibleOnDark failure vector — so the reel itself proves the label reads.
"""
import os
import sys
sys.path.insert(0, "/")
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("lumen-reel", image=image)

SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-cloudfront"),
]
CDN = "https://d1iax8jos987n3.cloudfront.net/"
FPS = 30


def _scenes(hero_url):
    """Four designed scenes at 30fps across 360f (12s): source breathes between
    takeovers. All text constructed (we are the known input here)."""
    def dur(s):
        return int(round(s * FPS))
    scenes = [
        {   # 1 — TypoStat, value LANDS mid-scene (the Flare value-landing doctrine)
            "fromFrame": dur(0.5), "durationInFrames": dur(2.4), "sceneIndex": 0,
            "sceneType": "typo_stat",
            "stat": {"value": 2400000, "prefix": "$", "suffix": "",
                     "label": "creator payouts", "supporting_line": "in the last 90 days"},
            "landFrame": dur(1.1),
            "background": {"kind": "gradient", "paletteRef": "electric night",
                           "colors": ["#4F9DF7", "#0E1220", "#8FE3FF"]},
            "subject": {"imageUrl": None, "generationPrompt": "", "anchor": "center", "scale": None},
            "textLayers": [],
            "motion": {"entrance": "rise", "easing": "spring", "motionBlur": True},
        },
        {   # 2 — HeroObject: ONE generated asset, orbit words popping on beats
            "fromFrame": dur(3.4), "durationInFrames": dur(2.5), "sceneIndex": 1,
            "sceneType": "hero_object",
            "stat": None, "landFrame": None,
            "background": {"kind": "gradient", "paletteRef": "vault",
                           "colors": ["#F7B84F", "#14100A", "#FFE29A"]},
            "subject": {"imageUrl": hero_url, "generationPrompt": "", "anchor": "center", "scale": None},
            "textLayers": [
                {"content": "LOCKED", "styleRef": None, "anchor": "center", "popFrame": dur(0.5)},
                {"content": "UNTIL NOW", "styleRef": None, "anchor": "center", "popFrame": dur(1.3)},
            ],
            "motion": {"entrance": "scale", "easing": "spring", "motionBlur": True},
        },
        {   # 3 — PhotoCard: three floating cards + a living caption
            "fromFrame": dur(6.4), "durationInFrames": dur(2.5), "sceneIndex": 2,
            "sceneType": "photo_card",
            "stat": None, "landFrame": None,
            "photos": ["reel_photo_0.jpg", "reel_photo_1.jpg", "reel_photo_2.jpg"],
            "background": {"kind": "gradient", "paletteRef": "rose signal",
                           "colors": ["#F75F8F", "#160A12", "#FFC2D6"]},
            "subject": {"imageUrl": None, "generationPrompt": "", "anchor": "center", "scale": None},
            "textLayers": [{"content": "the proof is everywhere", "styleRef": None, "anchor": "center"}],
            "motion": {"entrance": "float", "easing": "spring", "motionBlur": True},
        },
        {   # 4 — TypoStat on a 2-COLOR DARK palette: the v1 legibleOnDark
            # failure vector (label fell back to the dark tint) — reads now.
            "fromFrame": dur(9.4), "durationInFrames": dur(2.3), "sceneIndex": 3,
            "sceneType": "typo_stat",
            "stat": {"value": 97, "prefix": "", "suffix": "%",
                     "label": "retention at day thirty", "supporting_line": ""},
            "landFrame": dur(1.0),
            "background": {"kind": "gradient", "paletteRef": "midnight",
                           "colors": ["#1C1E34", "#101222"]},
            "subject": {"imageUrl": None, "generationPrompt": "", "anchor": "center", "scale": None},
            "textLayers": [],
            "motion": {"entrance": "rise", "easing": "spring", "motionBlur": True},
        },
    ]
    if hero_url is None:
        scenes = [s for s in scenes if s["sceneType"] != "hero_object"]
    return scenes


@app.function(secrets=SECRETS, timeout=2400, cpu=16.0, memory=32768)
def build_reel() -> dict:
    import json
    import subprocess
    import time
    import traceback
    import boto3

    sys.path.insert(0, "/")
    os.environ["APP_URL"] = ""  # belt: no cert traffic to prod
    out = {"ok": False}
    try:
        work = "/tmp/lumen_reel"
        pub = os.path.join(work, "public")
        os.makedirs(pub, exist_ok=True)

        # ── constructed source: a slow living gradient, 12s @30fps vertical ──
        src_mp4 = os.path.join(pub, "reel_source.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error",
             "-f", "lavfi",
             "-i", "gradients=s=1080x1920:rate=30:duration=12:speed=0.015:"
                   "c0=#0B0D18:c1=#1A2340:c2=#101828:c3=#0B0D18:nb_colors=4",
             "-vf", "hue=H=0.05*t,eq=saturation=1.05",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-pix_fmt", "yuv420p", src_mp4],
            check=True, capture_output=True, text=True)

        # ── constructed photo-card imagery (three gradient stills) ──
        for i, spec in enumerate([
            "gradients=s=860x1080:nb_colors=3:c0=#F75F8F:c1=#2A1020:c2=#FFC2D6:seed=7",
            "gradients=s=860x1080:nb_colors=3:c0=#4F9DF7:c1=#0E1830:c2=#8FE3FF:seed=21",
            "gradients=s=860x1080:nb_colors=3:c0=#F7B84F:c1=#241505:c2=#FFE29A:seed=42",
        ]):
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", spec,
                 "-frames:v", "1", os.path.join(pub, f"reel_photo_{i}.jpg")],
                check=True, capture_output=True, text=True)

        # ── the ONE hero asset — REAL Nano-Banana path (alpha-forced) ──
        hero_url = None
        try:
            import handler as H
            scene = {"scene_type": "hero_object",
                     "background": {"kind": "gradient", "palette_ref": "vault"},
                     "subject": {"generation_prompt":
                                 "a heavy brass vault padlock, brushed metal, "
                                 "studio lighting, slight three-quarter angle"}}
            res = H._generate_scene_subject(scene, 0, work, "locked until now")
            if res and res.get("path") and os.path.isfile(res["path"]):
                import shutil
                dst = os.path.join(pub, "reel_hero.png")
                shutil.copyfile(res["path"], dst)
                hero_url = "reel_hero.png"
                out["hero"] = {"generated": True, "cost": res.get("cost"), "ms": res.get("ms")}
            else:
                out["hero"] = {"generated": False, "reason": "no_image_returned"}
        except Exception as he:
            out["hero"] = {"generated": False,
                           "reason": f"{type(he).__name__}: {str(he)[:160]}"}

        # ── render the LumenReel composition (real components, 30fps) ──
        props = {"scenes": _scenes(hero_url), "label": "", "sourceSrc": "reel_source.mp4"}
        props_path = os.path.join(work, "props.json")
        with open(props_path, "w") as f:
            json.dump(props, f)
        out_mp4 = os.path.join(work, "lumen_reel.mp4")
        t0 = time.time()
        r = subprocess.run(
            ["node", "/remotion/lumen-reel-render.mjs", props_path, out_mp4, pub],
            cwd="/remotion", capture_output=True, text=True, timeout=1800)
        out["render_tail"] = (r.stdout or "")[-800:] + (r.stderr or "")[-800:]
        if r.returncode != 0 or not os.path.isfile(out_mp4):
            out["error"] = f"render exit {r.returncode}"
            return out
        out["render_s"] = round(time.time() - t0, 1)

        # ── mechanical probe ──
        pr = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,r_frame_rate,duration", "-of", "json", out_mp4],
            capture_output=True, text=True)
        out["probe"] = json.loads(pr.stdout or "{}")

        # ── upload → CloudFront ──
        s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
        bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
        key = f"hype-samples/lumen-reel/lumen_reel_{int(time.time())}.mp4"
        s3.upload_file(out_mp4, bucket, key, ExtraArgs={"ContentType": "video/mp4"})
        out["url"] = CDN + key
        out["scenes"] = len(props["scenes"])
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc()[-2000:]
        return out


@app.local_entrypoint()
def main():
    import json
    res = build_reel.remote()
    print(json.dumps(res, indent=2))
    if res.get("ok"):
        print(f"\nLUMEN REEL: {res['url']}")
    else:
        raise SystemExit(1)
