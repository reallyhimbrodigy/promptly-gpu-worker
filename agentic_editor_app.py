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

import time

import modal

app = modal.App("agentic-editor")

# python_version PINNED: debian_slim() defaults to 3.9 and the Deepgram SDK uses
# `match` statements, so the import dies with a SyntaxError before any agent work
# happens. First entry in the failure taxonomy, and an ENVIRONMENT failure rather
# than an agent one — worth separating in the ledger.
_HERE = os.path.dirname(os.path.abspath(__file__))
_KNOWLEDGE_DIR = os.path.join(_HERE, "knowledge")

# Remotion needs a real project on disk plus Chrome Headless Shell. Both are
# BAKED INTO THE IMAGE, not fetched at render time — a 150MB chrome download
# inside the agent loop would land as an opaque timeout in the middle of an edit.
_PKG = (
    '{"name":"agentic-mg","version":"1.0.0","private":true,"dependencies":'
    '{"@remotion/cli":"4.0.517","remotion":"4.0.517",'
    '"react":"19.0.0","react-dom":"19.0.0"}}'
)
_ROOT_TSX = (
    'import {Composition} from "remotion";\n'
    'import {Comp} from "./Comp";\n'
    'export const RemotionRoot: React.FC = () => (\n'
    '  <Composition id="Comp" component={Comp as any} durationInFrames={90}\n'
    '    fps={30} width={1080} height={1920} />\n'
    ');\n'
)
_INDEX_TS = (
    'import {registerRoot} from "remotion";\n'
    'import {RemotionRoot} from "./Root";\n'
    'registerRoot(RemotionRoot);\n'
)
# Placeholder the agent OVERWRITES. Transparent background is the contract: the
# MG is composited over the ffmpeg cut, it does not replace it.
_COMP_TSX = (
    'export const Comp: React.FC = () => <div style={{flex:1}} />;\n'
)

IMG = (modal.Image.debian_slim(python_version="3.11")
       .apt_install(
           "ffmpeg", "curl", "ca-certificates",
           # Chrome Headless Shell runtime deps — without these the remotion
           # render dies with a bare "browser failed to launch".
           "libnss3", "libdbus-1-3", "libatk1.0-0", "libasound2", "libxrandr2",
           "libxkbcommon0", "libxfixes3", "libxcomposite1", "libxdamage1",
           "libgbm1", "libpango-1.0-0", "libcairo2", "libatk-bridge2.0-0",
           "libcups2", "libxext6", "libx11-6", "libglib2.0-0")
       .run_commands(
           "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
           "apt-get install -y nodejs",
           "mkdir -p /remotion/src",
           f"cat > /remotion/package.json <<'EOF'\n{_PKG}\nEOF",
           f"cat > /remotion/src/Root.tsx <<'EOF'\n{_ROOT_TSX}EOF",
           f"cat > /remotion/src/index.ts <<'EOF'\n{_INDEX_TS}EOF",
           f"cat > /remotion/src/Comp.tsx <<'EOF'\n{_COMP_TSX}EOF",
           "cd /remotion && npm install --no-audit --no-fund",
           # Bake the browser so the agent loop never pays for it.
           "cd /remotion && npx remotion browser ensure",
       )
       .pip_install(["anthropic", "deepgram-sdk==3.*", "boto3"])
       .add_local_dir(_KNOWLEDGE_DIR, "/knowledge", copy=True))

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

# The editorial knowledge is served as a TOOL, not pasted into the prompt. It is
# 171k characters — inlining it would cost ~43k tokens on every single turn and
# make the $0.10/job law further out of reach, which is the opposite of the point.
# The agent reads the two or three files its edit actually needs.
_KNOWLEDGE_SYSTEM = """
EDITORIAL KNOWLEDGE — READ IT BEFORE YOU CUT

You have `read_knowledge`. It serves the editorial standard this product is
built on: the component catalogue with its FITS/FIGHTS lines, arc structure,
caption rules, grounding rules, the sound-effect library with attack timings,
and where the families actually land in reference edits.

This is not background reading. It is the difference between an edit that cuts
silence and an edit that is DIRECTED. Read `_index` first, then the two or three
files your edit needs. At minimum read the placement findings and the captions
rules before you build.

TWO RULES FROM THAT KNOWLEDGE THAT OVERRIDE YOUR INSTINCTS:
- Overlay text is the WORKHORSE (~7.5 per 25s). Emphasis and SFX are RARE
  (~0.5 per 25s). If your edit has more zooms than text, it is inverted.
- Every component you place must be GROUNDED in something the speaker actually
  said. A card is a quoted line. If you cannot point at the words, do not place
  it.

MOTION GRAPHICS — ffmpeg FIRST, Remotion ONLY when ffmpeg cannot express it

Cuts, crops, zooms, captions, transitions and text overlays are ffmpeg work.
ffmpeg composites orders of magnitude faster than headless Chromium, and that
speed is the whole reason this architecture is worth having.

For a GENUINE motion graphic — spring animation, a counting StatCard, a drawing
divider — you may author a Remotion component:
  1. Write the component to /remotion/src/Comp.tsx. Export `Comp`. Use a
     TRANSPARENT background: it is composited OVER your ffmpeg cut, not instead
     of it. Import from "remotion" (useCurrentFrame, interpolate, spring).
  2. Render with alpha:
     cd /remotion && npx remotion render Comp /work/mg.webm \\
       --codec=vp8 --pixel-format=yuva420p --log=error
  3. Composite with ffmpeg:
     ffmpeg -i /work/base.mp4 -i /work/mg.webm -filter_complex \\
       "[0][1]overlay=enable='between(t,S,E)'" -c:a copy /work/out.mp4

If the Remotion render fails, SHIP THE FFMPEG EDIT. A missing motion graphic is
a weaker video; a missing video is a failure. Never let step 2 cost you step 1.
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

KNOWLEDGE_TOOL = {
    "name": "read_knowledge",
    "description": "Read a file of Promptly's editorial standard. Pass '_index' "
                   "to list what is available. Extracted verbatim from the "
                   "production editorial prompt.",
    "input_schema": {"type": "object",
                     "properties": {"file": {"type": "string"}},
                     "required": ["file"]},
}


@app.function(image=IMG, secrets=SECRETS, timeout=3600, cpu=8, memory=16384)
def edit(source_key: str, brief: str, max_iters: int = MAX_ITERS,
         use_knowledge: bool = True) -> dict:
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

    # ── knowledge served from the image, read on demand ────────────────────
    led["knowledge_reads"] = []

    def read_knowledge(name: str) -> dict:
        d = "/knowledge"
        if not os.path.isdir(d):
            fail("knowledge_dir_missing", d)
            return {"error": "knowledge not mounted"}
        avail = sorted(f for f in os.listdir(d) if f.endswith(".md"))
        if name in ("_index", "index", ""):
            idx = []
            for f in avail:
                p = os.path.join(d, f)
                head = ""
                try:
                    with open(p) as fh:
                        for line in fh:
                            if line.strip():
                                head = line.strip()[:90]
                                break
                except Exception:
                    pass
                idx.append({"file": f, "chars": os.path.getsize(p), "starts": head})
            return {"files": idx}
        cand = name if name in avail else next(
            (f for f in avail if name.lower() in f.lower()), None)
        if not cand:
            fail("knowledge_file_missing", f"{name} not in {avail}")
            return {"error": f"no such file: {name}", "available": avail}
        body = open(os.path.join(d, cand)).read()
        led["knowledge_reads"].append(cand)
        # Truncated per read: the MG catalogue alone is 35k chars and a single
        # unbounded read would blow the turn's budget on one file.
        return {"file": cand, "chars": len(body), "content": body[:24000],
                "truncated": len(body) > 24000}

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    tl = "\n".join(f"[{w['s']:.2f}-{w['e']:.2f}] {w['w']}" for w in words)
    meta = probe(src)
    vs = next((s for s in meta.get("streams", []) if s.get("codec_type") == "video"), {})
    user = (f"BRIEF: {brief}\n\n"
            f"SOURCE: /work/source.mp4 — {vs.get('width')}x{vs.get('height')}, "
            f"{float(meta.get('format', {}).get('duration') or 0):.1f}s\n\n"
            f"TRANSCRIPT ({len(words)} words):\n{tl}\n\n"
            f"Produce /work/out.mp4. Verify with inspect_output before DONE.")

    # cache_control on the system block: run 2 reported cache_read 0 and cost
    # $0.5351 against a $0.10 law. The system text is identical across every turn
    # of every job, so it is the one block that can actually be reused.
    sys_text = SYSTEM + (_KNOWLEDGE_SYSTEM if use_knowledge else "")
    sys_blocks = [{"type": "text", "text": sys_text,
                   "cache_control": {"type": "ephemeral"}}]
    tools = TOOLS + ([KNOWLEDGE_TOOL] if use_knowledge else [])
    led["use_knowledge"] = use_knowledge

    msgs = [{"role": "user", "content": user}]
    final_text = ""
    for it in range(max_iters):
        led["iters"] = it + 1
        try:
            r = client.messages.create(
                model=MODEL, max_tokens=8000, system=sys_blocks, tools=tools,
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
            elif tu.name == "read_knowledge":
                out = read_knowledge(tu.input.get("file", "_index"))
            else:
                out = {"error": f"unknown tool {tu.name}"}
                fail("unknown_tool", tu.name)
            # Knowledge reads get a wider cap than shell output. At 6000 the
            # 24k-char read above would arrive as a quarter of a file and the
            # agent would silently act on a fragment.
            cap = 26000 if tu.name == "read_knowledge" else 6000
            results.append({"type": "tool_result", "tool_use_id": tu.id,
                            "content": json.dumps(out)[:cap]})
        msgs.append({"role": "user", "content": results})

    final = inspect() if os.path.exists("/work/out.mp4") else {"exists": False}
    key = None
    if final.get("exists"):
        key = f"agentic-editor/{int(time.time())}-{os.path.basename(source_key)}"
        s3.upload_file("/work/out.mp4", b, key,
                       ExtraArgs={"ContentType": "video/mp4"})
    if use_knowledge and not led["knowledge_reads"]:
        # The knowledge arm that never opened a file is NOT an arm. Without this
        # the A/B could report "no effect" when the real finding is "the tool was
        # never called" — the two are indistinguishable in the output alone.
        fail("knowledge_never_read",
             "use_knowledge=True but the agent called read_knowledge zero times "
             "— this arm is not a knowledge arm and must not be compared as one")
    return {"ok": bool(final.get("exists")), "wall_s": round(time.time() - t0, 1),
            "download_s": dl_s, "transcript_s": transcript_s,
            "source_words": len(words), "final": final, "ledger": led,
            "output_key": key, "agent_last_message": final_text[:1200]}


@app.local_entrypoint()
def main(source: str = "ab-sources/talking-head-v1/625dfdc5-73s.mp4",
         brief: str = "Cut this into a punchy vertical short. Remove silence and "
                      "filler. Keep the meaning intact. Burn readable captions.",
         iters: int = MAX_ITERS,
         knowledge: bool = True):
    r = edit.remote(source, brief, iters, knowledge)
    print("\n" + "=" * 66)
    print(f"  AGENTIC EDITOR — knowledge={'ON' if knowledge else 'OFF'}")
    print("=" * 66)
    print(f"  source          : {source}")
    kr = r["ledger"].get("knowledge_reads", [])
    print(f"  knowledge reads : {len(kr)}  {kr}")
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
