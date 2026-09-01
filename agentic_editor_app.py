"""AGENTIC EDITOR — one agent, prompt + video in, finished vertical video out.

No schema. No separate editorial call. No plan handed to a renderer. The agent
reads the transcript, decides the edit, WRITES THE RENDER CODE, runs it, watches
its own output, and iterates when it is wrong. The self-review loop is the
architecture, not a nicety bolted on the end.

ffmpeg, NOT Remotion. This is the variable that decides whether the idea is
worth anything: Remotion paints ~800-1000 ms/frame in headless Chromium (
measured — SmoothPush 840, StepZoom 785, LetterboxPush 1796), so an agent
driving Remotion inherits today's render time exactly and the whole exercise
buys nothing. ffmpeg composites orders of magnitude faster. Remotion stays
available as a FALLBACK for segments ffmpeg genuinely cannot express (spring
animation, complex motion graphics) — per segment, never as the default.

REUSED, NOT REBUILT: Deepgram for word timings (33ms; no model matches it and
cuts are built on it), failure-corpus/ sources for testing, frame extraction for
the agent's own review pass.

TWO INSTRUMENTS, WIRED FROM THE START BECAUSE RETROFITTING THEM IS HOW THEY
NEVER GET BUILT:

  1. FAILURE LEDGER — every failure mode, with the agent's command and the
     stderr, appended as it happens. A loop that silently retries teaches
     nothing; the point of the first runs is the failure taxonomy.

  2. SPEECH-CONTENT CHECK — the output is TRANSCRIBED and its words compared to
     the words the agent intended to keep. THE URDU INCIDENT DELETED 58 SECONDS
     AND REPORTED SUCCESS. Generated code has no schema stopping that, so the
     check cannot be a schema — it has to be a measurement on the artifact. An
     edit that loses speech FAILS here even if ffmpeg exited 0 and the file
     plays.

  ./run_modal.sh agentic_editor_app.py --source <s3-key> --brief "..."
"""
import json
import os
import re
import time

import modal

app = modal.App("agentic-editor")

# python_version PINNED: debian_slim() defaults to 3.9 and the Deepgram SDK uses
# `match` statements, so the import dies with a SyntaxError before any agent work
# happens. First entry in the failure taxonomy, and an ENVIRONMENT failure rather
# than an agent one — worth separating in the ledger.
IMG = (modal.Image.debian_slim(python_version="3.11")
       .apt_install("ffmpeg")
       .pip_install(["anthropic", "deepgram-sdk==3.*", "boto3"]))

SECRETS = [modal.Secret.from_name("promptly-secrets")]
BUCKET = "thisismybucketagainwooo"
MODEL = "claude-sonnet-5"
MAX_ITERS = 12   # first run hit 5 mid-edit and never self-reviewed

SYSTEM = """You are a video editor. You are given a raw talking-head clip and a
word-level transcript with exact timings. You produce a finished vertical
(1080x1920) short-form video.

You do this by WRITING AND RUNNING SHELL COMMANDS — ffmpeg, ffprobe, python3.
There is no schema and no downstream renderer interpreting a plan. What you
write is what ships.

HOW TO WORK
1. Read the transcript. Decide which words to keep and which to cut. Silence,
   filler and false starts are the usual cuts; keep the meaning intact.
2. Build the edit with ffmpeg. Concatenate the kept spans, crop/scale to
   1080x1920, and burn captions if they improve it.
3. RUN your command with the `shell` tool. Read the stderr.
4. VERIFY with `inspect_output`: it probes the file AND transcribes it, and
   tells you which intended words are MISSING from the result.
5. If words are missing or the output is wrong, FIX IT AND RUN AGAIN. Say
   `DONE` only when inspect_output shows the speech intact.

HARD RULES
- The output must be 1080x1920, H.264, with audio.
- NEVER report success on an output whose speech is missing. An edit that plays
  but has lost the words has failed.
- Cuts land on word boundaries from the transcript, not round numbers.
- Work in /work. The source is /work/source.mp4. Write /work/out.mp4.
"""

TOOLS = [
    {"name": "shell",
     "description": "Run a shell command (ffmpeg/ffprobe/python3). Returns "
                    "exit code, stdout and stderr, truncated.",
     "input_schema": {"type": "object",
                      "properties": {"cmd": {"type": "string"}},
                      "required": ["cmd"]}},
    {"name": "inspect_output",
     "description": "Probe /work/out.mp4 AND transcribe it, reporting duration, "
                    "resolution, and which intended words are missing from the "
                    "rendered audio. Call this before saying DONE.",
     "input_schema": {"type": "object", "properties": {}}},
]


@app.function(image=IMG, secrets=SECRETS, timeout=3600, cpu=8, memory=16384)
def edit(source_key: str, brief: str, max_iters: int = MAX_ITERS) -> dict:
    import subprocess
    import boto3
    from anthropic import Anthropic

    t0 = time.time()
    led = {"failures": [], "iters": 0, "tokens": {"in": 0, "out": 0,
                                                  "cache_read": 0, "cache_write": 0}}

    def fail(kind, detail, cmd=None):
        """THE FAILURE LEDGER. Appended as it happens, never reconstructed."""
        led["failures"].append({"kind": kind, "detail": str(detail)[:400],
                                "cmd": (cmd or "")[:300],
                                "t": round(time.time() - t0, 1)})

    os.makedirs("/work", exist_ok=True)
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    b = os.environ.get("S3_BUCKET_NAME") or BUCKET
    src = "/work/source.mp4"
    s3.download_file(b, source_key, src)
    dl_s = round(time.time() - t0, 1)

    # ── TRANSCRIPT (Deepgram — reused, not reinvented) ─────────────────────
    tw0 = time.time()
    from deepgram import DeepgramClient, PrerecordedOptions
    dg = DeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])
    with open(src, "rb") as fh:
        dgr = dg.listen.prerecorded.v("1").transcribe_file(
            {"buffer": fh.read()},
            PrerecordedOptions(model="nova-3", language="multi",
                               smart_format=True, punctuate=True,
                               utterances=True, filler_words=True))
    d = dgr.to_dict() if hasattr(dgr, "to_dict") else json.loads(dgr.to_json())
    alt = d["results"]["channels"][0]["alternatives"][0]
    words = [{"w": w["word"], "s": round(w["start"], 3), "e": round(w["end"], 3)}
             for w in (alt.get("words") or [])]
    transcript_s = round(time.time() - tw0, 1)
    if not words:
        fail("no_transcript", "Deepgram returned zero words")
        return {"ok": False, "why": "no transcript", "ledger": led}

    def probe(path):
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
             "-show_streams", path], capture_output=True, text=True, timeout=120)
        try:
            return json.loads(p.stdout)
        except Exception:
            return {}

    def transcribe_words(path):
        """Transcribe the OUTPUT. This is the Urdu-incident check: an edit that
        exits 0 and plays can still have deleted the speech."""
        try:
            with open(path, "rb") as fh:
                r = dg.listen.prerecorded.v("1").transcribe_file(
                    {"buffer": fh.read()},
                    PrerecordedOptions(model="nova-3", language="multi",
                                       smart_format=True))
            dd = r.to_dict() if hasattr(r, "to_dict") else json.loads(r.to_json())
            a = dd["results"]["channels"][0]["alternatives"][0]
            return [w["word"].lower().strip(".,!?") for w in (a.get("words") or [])]
        except Exception as e:
            fail("output_transcribe_failed", e)
            return None

    def norm(ws):
        return [w.lower().strip(".,!?") for w in ws]

    def run_shell(cmd):
        try:
            p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               timeout=900, cwd="/work")
            if p.returncode != 0:
                fail("shell_nonzero", (p.stderr or "")[-400:], cmd)
            return {"exit": p.returncode,
                    "stdout": (p.stdout or "")[-1500:],
                    "stderr": (p.stderr or "")[-2500:]}
        except subprocess.TimeoutExpired:
            fail("shell_timeout", "900s", cmd)
            return {"exit": -1, "stdout": "", "stderr": "TIMEOUT after 900s"}

    def inspect():
        out = "/work/out.mp4"
        if not os.path.exists(out):
            fail("no_output", "out.mp4 does not exist")
            return {"exists": False,
                    "error": "/work/out.mp4 does not exist — nothing was rendered"}
        info = probe(out)
        v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
        a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
        dur = float(info.get("format", {}).get("duration") or 0)
        res = {"exists": True, "duration_s": round(dur, 2),
               "width": v.get("width"), "height": v.get("height"),
               "vcodec": v.get("codec_name"), "has_audio": bool(a),
               "size_mb": round(os.path.getsize(out) / 1e6, 1)}
        if not a:
            fail("no_audio_stream", "output has no audio stream")
        if (v.get("width"), v.get("height")) != (1080, 1920):
            fail("wrong_resolution", f"{v.get('width')}x{v.get('height')}")
        # ── THE SPEECH CHECK ───────────────────────────────────────────────
        got = transcribe_words(out)
        if got is None:
            res["speech_check"] = "UNAVAILABLE — transcription failed, treat as UNVERIFIED"
        else:
            src_words = norm([w["w"] for w in words])
            got_set = {}
            for g in got:
                got_set[g] = got_set.get(g, 0) + 1
            missing, remaining = [], dict(got_set)
            for w in src_words:
                if remaining.get(w):
                    remaining[w] -= 1
                else:
                    missing.append(w)
            kept_ratio = 1.0 - (len(missing) / max(1, len(src_words)))
            res["speech_check"] = {
                "source_words": len(src_words), "output_words": len(got),
                "source_words_absent_from_output": len(missing),
                "kept_ratio": round(kept_ratio, 3),
                "sample_missing": missing[:25],
                "note": ("Some absence is EXPECTED — you deliberately cut words. "
                         "What must not happen is losing speech you meant to KEEP. "
                         "If output_words is far below what your edit should "
                         "contain, the render dropped audio."),
            }
            # THE GAP THE FIRST RUN EXPOSED. I ledgered only the total-loss
            # case, so a run that kept 12.7% of the speech recorded ZERO
            # failures — the ledger said clean while the content said
            # destroyed, which is the Urdu shape exactly. A check that
            # MEASURES loss but does not FLAG it is not a check.
            if len(got) == 0:
                fail("output_has_no_speech", "0 words transcribed from output")
            elif kept_ratio < 0.5:
                fail("speech_loss_severe",
                     f"kept_ratio {kept_ratio:.3f}: {len(missing)} of "
                     f"{len(src_words)} source words absent from the output")
            res["speech_check"]["VERDICT"] = (
                "FAIL — most of the speech is gone" if kept_ratio < 0.5
                else "OK" if kept_ratio >= 0.8
                else "SUSPECT — verify this was a deliberate cut")
        return res

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    tl = "\n".join(f"[{w['s']:.2f}-{w['e']:.2f}] {w['w']}" for w in words)
    meta = probe(src)
    vs = next((s for s in meta.get("streams", []) if s.get("codec_type") == "video"), {})
    user = (f"BRIEF: {brief}\n\n"
            f"SOURCE: /work/source.mp4 — {vs.get('width')}x{vs.get('height')}, "
            f"{float(meta.get('format', {}).get('duration') or 0):.1f}s\n\n"
            f"TRANSCRIPT ({len(words)} words):\n{tl}\n\n"
            f"Produce /work/out.mp4. Verify with inspect_output before DONE.")

    msgs = [{"role": "user", "content": user}]
    final_text = ""
    for it in range(max_iters):
        led["iters"] = it + 1
        try:
            r = client.messages.create(
                model=MODEL, max_tokens=8000, system=SYSTEM, tools=TOOLS,
                messages=msgs)
        except Exception as e:
            fail("model_call_failed", e)
            break
        u = getattr(r, "usage", None)
        if u:
            led["tokens"]["in"] += getattr(u, "input_tokens", 0) or 0
            led["tokens"]["out"] += getattr(u, "output_tokens", 0) or 0
            led["tokens"]["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
            led["tokens"]["cache_write"] += getattr(u, "cache_creation_input_tokens", 0) or 0
        msgs.append({"role": "assistant", "content": r.content})
        tool_uses = [c for c in r.content if getattr(c, "type", "") == "tool_use"]
        texts = " ".join(getattr(c, "text", "") for c in r.content
                         if getattr(c, "type", "") == "text")
        final_text = texts or final_text
        if not tool_uses:
            break
        if it == max_iters - 1:
            fail("iteration_budget_exhausted",
                 f"stopped after {max_iters} turns with the agent still working "
                 f"— it never reached its own self-review")
        results = []
        for tu in tool_uses:
            if tu.name == "shell":
                out = run_shell(tu.input.get("cmd", ""))
            elif tu.name == "inspect_output":
                out = inspect()
            else:
                out = {"error": f"unknown tool {tu.name}"}
                fail("unknown_tool", tu.name)
            results.append({"type": "tool_result", "tool_use_id": tu.id,
                            "content": json.dumps(out)[:6000]})
        msgs.append({"role": "user", "content": results})

    final = inspect() if os.path.exists("/work/out.mp4") else {"exists": False}
    key = None
    if final.get("exists"):
        key = f"agentic-editor/{int(time.time())}-{os.path.basename(source_key)}"
        s3.upload_file("/work/out.mp4", b, key,
                       ExtraArgs={"ContentType": "video/mp4"})
    return {"ok": bool(final.get("exists")), "wall_s": round(time.time() - t0, 1),
            "download_s": dl_s, "transcript_s": transcript_s,
            "source_words": len(words), "final": final, "ledger": led,
            "output_key": key, "agent_last_message": final_text[:1200]}


@app.local_entrypoint()
def main(source: str = "failure-corpus/INTEGRITY_TRIP/579dcbe6-5ca5-4e6f-b2f2-3c70da557358.mp4",
         brief: str = "Cut this into a punchy vertical short. Remove silence and "
                      "filler. Keep the meaning intact. Burn readable captions.",
         iters: int = MAX_ITERS):
    r = edit.remote(source, brief, iters)
    print("\n" + "=" * 66)
    print("  AGENTIC EDITOR — first render")
    print("=" * 66)
    print(f"  source          : {source}")
    print(f"  ok              : {r['ok']}")
    print(f"  WALL            : {r['wall_s']}s  "
          f"(download {r['download_s']}s, transcript {r['transcript_s']}s)")
    print(f"  self-review     : {r['ledger']['iters']} iteration(s)")
    t = r["ledger"]["tokens"]
    print(f"  TOKENS          : in {t['in']:,}  out {t['out']:,}  "
          f"cache_read {t['cache_read']:,}  cache_write {t['cache_write']:,}")
    # Sonnet pricing: $3/M in, $15/M out, cache read $0.30/M, write $3.75/M.
    cost = (t["in"] * 3 + t["out"] * 15 + t["cache_read"] * 0.30
            + t["cache_write"] * 3.75) / 1e6
    print(f"  COST (sonnet)   : ${cost:.4f}")
    f = r["final"]
    if f.get("exists"):
        print(f"  output          : {f['duration_s']}s  {f['width']}x{f['height']}  "
              f"{f['vcodec']}  audio={f['has_audio']}  {f['size_mb']}MB")
        sc = f.get("speech_check")
        if isinstance(sc, dict):
            print(f"  SPEECH CHECK    : {sc['output_words']} words in output vs "
                  f"{sc['source_words']} in source (kept_ratio {sc['kept_ratio']})")
            if sc["sample_missing"]:
                print(f"    absent sample : {' '.join(sc['sample_missing'][:14])}")
        else:
            print(f"  SPEECH CHECK    : {sc}")
    print(f"  s3 key          : {r.get('output_key')}")
    fs = r["ledger"]["failures"]
    print(f"\n  FAILURE LEDGER  : {len(fs)} event(s)")
    for x in fs:
        print(f"    [{x['t']:>6}s] {x['kind']}: {x['detail'][:110]}")
    print(f"\n  agent said      : {r['agent_last_message'][:400]}")
