# Phase 0 throwaway probe — confirms Opus 4.8 API access via the Modal-secret key,
# lists reachable Opus model IDs, reads real rate-limit headers, and measures
# vision latency with a realistic frame batch. Touches NOTHING in the live pipeline.
#   modal run /tmp/phase0_opus_probe.py::confirm
#   modal run /tmp/phase0_opus_probe.py::latency --n-images 120 --reps 3
import modal

app = modal.App("phase0-opus-probe")
image = modal.Image.debian_slim().pip_install("anthropic>=0.40", "pillow")
SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-cloudfront"),
]


def _find_key():
    import os
    for k, v in os.environ.items():
        if isinstance(v, str) and v.startswith("sk-ant-"):
            return k, v
    return None, os.environ.get("ANTHROPIC_API_KEY")


@app.function(image=image, secrets=SECRETS, timeout=300)
def confirm():
    import anthropic
    keyvar, api_key = _find_key()
    print(f"[key] found in env var: {keyvar!r}  present={bool(api_key)}")
    if not api_key:
        print("[FATAL] no sk-ant-* key found in any attached secret")
        return
    client = anthropic.Anthropic(api_key=api_key)

    print("\n[models] Opus IDs reachable by this key:")
    try:
        for m in client.models.list(limit=100).data:
            if "opus" in m.id.lower():
                print(f"   - {m.id}")
    except Exception as e:
        print(f"   models.list failed: {type(e).__name__}: {e}")

    for candidate in ("claude-opus-4-8", "claude-opus-4-8-20250930", "claude-opus-4-1-20250805"):
        try:
            raw = client.messages.with_raw_response.create(
                model=candidate, max_tokens=16,
                messages=[{"role": "user", "content": "Reply with the single word OK."}],
            )
            msg = raw.parse()
            rl = {k: v for k, v in raw.headers.items()
                  if "ratelimit" in k.lower() or k.lower() == "retry-after"}
            print(f"\n[access] model={candidate!r} OK -> responded model={msg.model!r}")
            print(f"[ratelimits] {rl}")
            return
        except Exception as e:
            print(f"[access] model={candidate!r} FAILED: {type(e).__name__}: {str(e)[:200]}")


@app.function(image=image, secrets=SECRETS, timeout=1800)
def latency(n_images: int = 120, reps: int = 3, effort: str = "high", model: str = "claude-opus-4-8"):
    import time, io, base64, anthropic
    from PIL import Image
    keyvar, api_key = _find_key()
    client = anthropic.Anthropic(api_key=api_key)

    # Synthetic downscaled frames (~512x288 ~= 197 image tokens each). Content is
    # irrelevant for LATENCY (token count drives it); quality needs real frames (Phase 3).
    def frame(i):
        im = Image.new("RGB", (512, 288), ((i * 7) % 255, (i * 13) % 255, (i * 29) % 255))
        b = io.BytesIO(); im.save(b, format="JPEG", quality=70)
        return base64.standard_b64encode(b.getvalue()).decode()

    content = []
    for i in range(n_images):
        content.append({"type": "text", "text": f"t={i*0.5:05.1f}s"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": frame(i)}})
    # Realistic transcript (~150 indexed words) + a task that FORCES a full
    # PostCutPlan-sized output (~3-4K tokens) so latency reflects real generation,
    # not a trivial reply. System filler approximates the ~67KB editorial prompt.
    transcript = "TRANSCRIPT (kept-only word indices, [i]=word@start-end):\n" + " ".join(
        f"[{i}]word{i}@{i*0.4:.2f}" for i in range(150))
    task = (
        "\n\nYou are the video editor. Using the timestamped frames + transcript, emit a COMPLETE "
        "JSON edit recipe (PostCutPlan) fully populated: video_plan {what_happens, hook_word_index, "
        "payoff_word_index, close_word_index, 4 key_moments each {word_index, what_lands, why_emphasis, "
        "what_i_saw, viewer_feeling}, story_shape, arc_segments tiling ALL words, editorial_vision}, "
        "caption_style, caption_keywords, 8 emphasis_moments, 6 transitions, 8 sound_effects, "
        "6 motion_graphics, 4 text_overlays, 5 broll_clips, caption_position_changes, thumbnail_word_index, "
        "audio_denoise, outro, aspect_ratio, notes. Reason about timing + visual grounding first, then "
        "output ONLY the full JSON (~3000-4000 tokens), every array populated with real word indices.")
    content.append({"type": "text", "text": transcript + task})
    system = "EDITORIAL SYSTEM PROMPT.\n" + ("rule detail line for the editor. " * 2600)  # ~17K tok approx

    import statistics as st
    MAX_TOKENS = 64000  # raised from 40000 — thinking shares this ceiling with output
    PRICE_IN, PRICE_OUT = 15.0 / 1e6, 75.0 / 1e6  # ASSUMED Opus 4.x $/token (label as estimate)
    print(f"[probe] model={model} n_images={n_images} effort={effort} max_tokens={MAX_TOKENS} reps={reps}")
    lats = []; ins = []; outs = []; thinks = []; jsons = []
    for r in range(reps):
        t0 = time.time(); ttft_any = None; ttft_text = None
        try:
            with client.messages.stream(
                model=model, max_tokens=MAX_TOKENS, system=system,
                messages=[{"role": "user", "content": content}],
                extra_body={"thinking": {"type": "adaptive"},
                            "output_config": {"effort": effort}},
            ) as s:
                for ev in s:
                    if ttft_any is None:
                        ttft_any = time.time() - t0
                    if getattr(ev, "type", "") == "content_block_delta":
                        d = getattr(ev, "delta", None)
                        if getattr(d, "type", "") == "text_delta" and ttft_text is None:
                            ttft_text = time.time() - t0
                fm = s.get_final_message()
            dt = time.time() - t0
            in_tok = fm.usage.input_tokens; out_tok = fm.usage.output_tokens
            think_tok = round(sum(len(getattr(b, "thinking", "") or "") for b in fm.content
                                  if getattr(b, "type", "") == "thinking") / 4)
            json_tok = round(sum(len(getattr(b, "text", "") or "") for b in fm.content
                                 if getattr(b, "type", "") == "text") / 4)
            stop = fm.stop_reason
            cost = in_tok * PRICE_IN + out_tok * PRICE_OUT
            lats.append(dt); ins.append(in_tok); outs.append(out_tok); thinks.append(think_tok); jsons.append(json_tok)
            tt = f"{ttft_text:.1f}" if ttft_text else "NA"
            print(f"  rep{r}: total={dt:.1f}s ttft_any={ttft_any:.1f}s first_text={tt}s in={in_tok} "
                  f"out_total={out_tok} ~think={think_tok} ~json={json_tok} stop={stop!r} "
                  f"headroom={MAX_TOKENS - out_tok} cost=${cost:.3f}")
        except Exception as e:
            print(f"  rep{r}: FAILED {type(e).__name__}: {str(e)[:240]}")
    if lats:
        sl = sorted(lats)
        p50 = sl[len(sl) // 2]; p95 = sl[min(len(sl) - 1, int(len(sl) * 0.95))]
        print(f"[result] n_images={n_images} effort={effort}: lat p50={p50:.1f}s p95={p95:.1f}s "
              f"min={sl[0]:.1f}s max={sl[-1]:.1f}s | avg_in={round(st.mean(ins))} "
              f"avg_out_total={round(st.mean(outs))} avg_think={round(st.mean(thinks))} "
              f"avg_json={round(st.mean(jsons))} | avg_cost=${st.mean([i*PRICE_IN+o*PRICE_OUT for i,o in zip(ins,outs)]):.3f} "
              f"| min_headroom={MAX_TOKENS - max(outs)}")


gimage = modal.Image.debian_slim().apt_install("ffmpeg").pip_install("google-genai>=1.0")


@app.function(image=gimage, secrets=SECRETS, timeout=900)
def gemini_cost(duration: int = 60, reps: int = 2):
    """Measure the CURRENT Gemini path's real token usage + cost for apples-to-apples
    vs the Opus probe. Synthetic video has the same token count as a real one of the
    same specs (count is frames x resolution, not content)."""
    import os, time, json, subprocess
    from google import genai as gm
    from google.genai import types as gt
    from google.oauth2 import service_account
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    f"testsrc=size=480x854:rate=18:duration={duration}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "/tmp/t.mp4"],
                   check=True, capture_output=True)
    vb = open("/tmp/t.mp4", "rb").read()
    print(f"[gemini] synthetic {duration}s 480x854@18fps video = {len(vb)/1024/1024:.2f}MB")
    creds = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"]),
        scopes=["https://www.googleapis.com/auth/cloud-platform"])
    client = gm.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"],
                       location=os.environ["GOOGLE_CLOUD_LOCATION"], credentials=creds)
    part = gt.Part(inline_data=gt.Blob(data=vb, mime_type="video/mp4"),
                   video_metadata=gt.VideoMetadata(fps=18))
    system = "EDITORIAL SYSTEM PROMPT.\n" + ("rule detail line for the editor. " * 2600)
    transcript = "TRANSCRIPT (kept-only word indices):\n" + " ".join(f"[{i}]word{i}@{i*0.4:.2f}" for i in range(150))
    task = ("\n\nEmit a COMPLETE JSON edit recipe (PostCutPlan): video_plan, caption_style, "
            "8 emphasis_moments, 6 transitions, 8 sound_effects, 6 motion_graphics, 4 text_overlays, "
            "5 broll_clips, etc., every array populated with real word indices. Output ONLY the JSON.")
    PIN, POUT = 2.0 / 1e6, 12.0 / 1e6  # ASSUMED gemini-3.1-pro $/token (label as estimate)
    print(f"[gemini] PRICING ASSUMED: ${PIN*1e6:.2f}/M in, ${POUT*1e6:.2f}/M out")
    for r in range(reps):
        t0 = time.time()
        try:
            resp = client.models.generate_content(
                model="gemini-3.1-pro-preview", contents=[part, transcript + task],
                config=gt.GenerateContentConfig(
                    system_instruction=system, temperature=1.0, max_output_tokens=40000,
                    thinking_config=gt.ThinkingConfig(thinking_budget=24576),
                    media_resolution="MEDIA_RESOLUTION_LOW"))
            dt = time.time() - t0
            u = resp.usage_metadata
            pt = u.prompt_token_count or 0
            ct = u.candidates_token_count or 0
            th = getattr(u, "thoughts_token_count", 0) or 0
            cost = pt * PIN + (ct + th) * POUT
            print(f"  rep{r}: total={dt:.1f}s prompt_in(incl video)={pt} thoughts={th} output={ct} cost=${cost:.4f}")
        except Exception as e:
            print(f"  rep{r}: FAILED {type(e).__name__}: {str(e)[:240]}")
