"""MILESTONE 1 — one job, end to end, returning a rendered file.

THE SHAPE, and what it replaces. Claude Code runs headless in a cold Modal
container and edits through ChatCut's MCP server. ChatCut owns the timeline,
the cut, the components and the render. We own the judgment: which moments
matter, what goes on screen, and whether it looks like Zac's references.

MEASURED BEFORE COMMITTING (probe_claude_boot_app.py): the per-job floor is
5.21s wall, cold — node 0.195s, CLI 0.249s, MCP reachable in 0.340s. That is
~4% of the 120s law, so containers run COLD PER JOB and no warm pool is needed.
Turns are the constraint, exactly as on the ffmpeg pipeline (7-10 on a talking
head, round 70).

WHAT THE CRAFT IS HERE. The knowledge documents, the reference corpus and the
derived control distributions are MOUNTED AS THE SESSION'S CONTEXT, not wired
into a harness. That is the whole point of the rewrite: they are what makes the
agent edit like the references instead of generically, and a harness that
re-encodes them as rules loses exactly the thing that took the week.
"""
import json
import os
import subprocess
import time
import urllib.error
import urllib.request

import modal

app = modal.App("chatcut-editor")

_HERE = os.path.dirname(os.path.abspath(__file__))
MCP_URL = "https://api.chatcut.io/api/external-mcp/mcp"
TOKEN_URL = "https://api.chatcut.io/auth/mcp/token"

# THE CRAFT, BAKED IN. Copied into the image rather than fetched at run time —
# a mid-edit download lands as an opaque stall, which is the lesson the Chrome
# download and the knowledge-mount path both taught this lane.
IMG = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("curl", "ca-certificates", "git", "ffmpeg")
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
        "apt-get install -y nodejs",
        "npm install -g @anthropic-ai/claude-code",
    )
    .add_local_dir(os.path.join(_HERE, "knowledge"), "/craft/knowledge",
                   copy=True)
    .add_local_file(os.path.join(_HERE, "control_distributions.json"),
                    "/craft/control_distributions.json", copy=True)
    .add_local_file(os.path.join(_HERE, "reference_index.json"),
                    "/craft/reference_index.json", copy=True)
)


def _access_token():
    """Exchange the stored refresh token for an access token. STATE, not a guess.

    ROTATION IS HANDLED AND SAID OUT LOUD. If ChatCut returns a NEW refresh
    token, the old one may already be dead — two concurrent containers sharing
    one stored token would then race and one would silently invalidate the
    other, surfacing only as intermittent auth failure under load. We report the
    rotation so the Secret can be updated; we never pretend it did not happen.
    """
    rt = os.environ.get("CHATCUT_REFRESH_TOKEN")
    cid = os.environ.get("CHATCUT_CLIENT_ID")
    if not rt or not cid:
        raise RuntimeError(
            "CHATCUT_REFRESH_TOKEN / CHATCUT_CLIENT_ID are ABSENT from the "
            "environment. The Modal Secret is not attached — this is a missing "
            "credential, not an expired one, and the job must not proceed.")
    import urllib.parse
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token", "refresh_token": rt, "client_id": cid,
        "resource": MCP_URL,
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            tok = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"refresh failed HTTP {e.code}: {e.read()[:200].decode()} — the "
            f"stored refresh token is rejected. Re-run chatcut_oauth.py and "
            f"update the Secret.")
    if tok.get("refresh_token") and tok["refresh_token"] != rt:
        print("  TOKEN ROTATED: ChatCut issued a new refresh token. Update the "
              "Modal Secret or the NEXT job may fail. Concurrent containers "
              "sharing the old value will now race.", flush=True)
    if not tok.get("access_token"):
        raise RuntimeError("refresh returned no access_token — ABSENT")
    return tok["access_token"]


def preflight(access_token):
    """PROVE THE TOOLS ARE THERE BEFORE SPENDING A TURN. Returns the tool count.

    THE CLASS THIS EXISTS FOR, anticipated before it could happen. An
    unauthenticated MCP server leaves a Claude Code session with NO TOOLS rather
    than an error. A toolless container is then indistinguishable from an agent
    that looked at the clip and chose to do nothing: it burns a turn, produces
    no edit, exits 0, and every downstream instrument reports a true and
    useless zero. That is this project's oldest failure family and it has been
    paid for repeatedly.

    So this runs BEFORE the agent, over plain HTTP, and RAISES. It does not warn
    and continue.
    """
    def rpc(method, params, mid):
        req = urllib.request.Request(
            MCP_URL,
            data=json.dumps({"jsonrpc": "2.0", "id": mid, "method": method,
                             "params": params}).encode(),
            headers={"Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     "Authorization": f"Bearer {access_token}"},
            method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
        # The endpoint may answer as SSE; take the last data: line either way.
        if raw.lstrip().startswith("{"):
            return json.loads(raw)
        for line in reversed(raw.splitlines()):
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        raise RuntimeError(f"unparseable MCP response: {raw[:200]}")

    try:
        rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "promptly-preflight",
                                          "version": "1"}}, 1)
        tools = rpc("tools/list", {}, 2)
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"PREFLIGHT FAILED: MCP returned HTTP {e.code}. The container has "
            f"NO TOOLS. Refusing to run the agent — a toolless run is "
            f"indistinguishable from an agent that chose to do nothing.")
    names = [t["name"] for t in (tools.get("result") or {}).get("tools", [])]
    if "create_project" not in names or "submit_export" not in names:
        raise RuntimeError(
            f"PREFLIGHT FAILED: MCP answered but the editing tools are absent "
            f"({len(names)} tools: {names[:8]}). Refusing to run.")
    print(f"  PREFLIGHT       : MEASURED  {len(names)} tools, create_project "
          f"and submit_export present", flush=True)
    return len(names)


CRAFT_CONTEXT = """\
You are editing a short vertical video for Promptly, through the ChatCut MCP
tools. You own the judgment; ChatCut owns the timeline and the render.

THE CRAFT IS MOUNTED, NOT SUMMARISED. Read what you need from /craft before you
decide anything:

  /craft/knowledge/          the craft documents — the cut pass, captions, text
                             overlays, motion graphics, emphasis zoom, sound
                             effects, seam treatments, and the standard.
  /craft/control_distributions.json
                             what the reference corpus ACTUALLY does, per family,
                             every share with its denominator and video count.
                             It DESCRIBES the references; it is never a target.
                             A run that repeats a choice on purpose is correct.
  /craft/reference_index.json
                             the annotated reference beats themselves.

HOW TO WORK
  1. Import the clip, wait for transcription, place it.
  2. Read the transcript with read_script before deciding the cut. The cut is
     what you REMOVE: a false start, a restated point, a run-up that says
     nothing. Saying "nothing to cut" is a real answer; padding is not.
  3. Look at the actual frames with preview_timeline views:["viewer"] BEFORE
     choosing where anything goes. The frame decides placement, not the
     timing. Footage with burned-in graphics has different free bands than a
     clean talking head.
  4. Place what the moment needs. Vary size, case and position deliberately —
     check control_distributions.json for what the references do rather than
     defaulting to full-size ALL CAPS in one spot.
  5. Verify composed frames before you call it done. A successful tool call is
     not verification.
  6. Export video, h264, 1080p.

Report what you cut and why, what you placed and where, and the render id.
"""


@app.function(image=IMG, timeout=1800,
              secrets=[modal.Secret.from_name("chatcut-oauth"),
                       modal.Secret.from_name("anthropic-api-key")])
def edit(clip_url: str, brief: str, model: str = "claude-sonnet-5"):
    t0 = time.time()
    marks = {}

    def mark(k):
        marks[k] = round(time.time() - t0, 2)

    tok = _access_token()
    mark("token")
    n_tools = preflight(tok)
    mark("preflight")

    os.makedirs("/work", exist_ok=True)
    subprocess.run(["curl", "-sS", "-o", "/work/source.mp4", clip_url],
                   check=True, timeout=300)
    mark("download")

    # THE MCP SERVER, CONFIGURED WITH A BEARER WE ALREADY PROVED WORKS. The
    # preflight above ran the same credential over the same endpoint, so a
    # failure after this point is the agent or the tools, never the auth.
    cfg = {"mcpServers": {"chatcut": {
        "type": "http", "url": MCP_URL,
        "headers": {"Authorization": f"Bearer {tok}",
                    "x-chatcut-mcp-client": "claude_code",
                    "x-chatcut-mcp-surface": "embedded-preview"}}}}
    with open("/work/mcp.json", "w") as fh:
        json.dump(cfg, fh)
    with open("/work/CLAUDE.md", "w") as fh:
        fh.write(CRAFT_CONTEXT)

    prompt = (f"{CRAFT_CONTEXT}\n\nTHE CLIP: /work/source.mp4\n"
              f"THE BRIEF: {brief}\n")
    r = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "json",
         "--mcp-config", "/work/mcp.json",
         "--permission-mode", "bypassPermissions",
         "--model", model],
        cwd="/work", capture_output=True, text=True, timeout=1500)
    mark("agent")

    out = {"marks": marks, "tools": n_tools, "rc": r.returncode,
           "stdout_tail": (r.stdout or "")[-4000:],
           "stderr_tail": (r.stderr or "")[-2000:]}
    out["wall_s"] = round(time.time() - t0, 2)
    return out


@app.local_entrypoint()
def main(clip_url: str = "", brief: str = "Cut this tighter and add one title."):
    if not clip_url:
        raise SystemExit("pass --clip-url")
    res = edit.remote(clip_url, brief)
    print(json.dumps(res, indent=1)[:6000])
