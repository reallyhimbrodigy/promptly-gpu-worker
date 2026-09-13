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
    # THE CHATCUT PLUGIN, BAKED IN. Its MCP server carries a MANDATORY
    # precondition: invoke chatcut:chatcut-plugin-basics-claude before the
    # first ChatCut tool call, and if it is unavailable, STOP. The first
    # end-to-end run proved the agent obeys that literally — it refused to
    # touch a single tool and said so, which is the correct behaviour and a
    # harness gap, not a finding. The skills ship with the image.
    .add_local_dir(os.path.expanduser(
        "~/.claude/plugins/cache/chatcut-inc/chatcut/1.10.12"),
        "/root/.claude/plugins/cache/chatcut-inc/chatcut/1.10.12", copy=True)
    # THE REGISTRATION IS REWRITTEN FOR THE CONTAINER. The local
    # installed_plugins.json points installPath at /Users/zaclibman/... which
    # does not exist here; copying it verbatim would register a plugin at a
    # missing path and the skills would be silently absent again.
    # THE MARKETPLACE, AND THIS IS THE PIECE THAT WAS MISSING. A plugin
    # resolves THROUGH its marketplace: the cache, installed_plugins.json and
    # enabledPlugins are all necessary and none of them is sufficient. Three
    # runs had every one of those in place and still got "Unknown skill",
    # because .claude-plugin/marketplace.json was not in the container. A
    # diagnostic container settled it — only built-in skills were listed —
    # rather than a fourth guess. .git is excluded: 228M -> 115M.
    .add_local_dir("/tmp/cc_marketplace",
                   "/root/.claude/plugins/marketplaces/chatcut-inc", copy=True)
    .run_commands(
        "mkdir -p /root/.claude/plugins",
        """cat > /root/.claude/plugins/known_marketplaces.json <<'JSON'
{"chatcut-inc":{"source":{"source":"git",
  "url":"https://github.com/ChatCut-Inc/agent-plugin.git","ref":"main"},
  "installLocation":"/root/.claude/plugins/marketplaces/chatcut-inc"}}
JSON""",
        # ENABLED, NOT MERELY PRESENT. The cache plus installed_plugins.json
        # registers the plugin; `enabledPlugins` is what makes its SKILLS
        # resolvable. Without it the agent gets "Unknown skill" and — correctly
        # — refuses to touch a ChatCut tool. Two runs proved that: the plugin
        # was on disk both times and the skill was still absent.
        """cat > /root/.claude/settings.json <<'JSON'
{"enabledPlugins":{"chatcut@chatcut-inc":true},
 "extraKnownMarketplaces":{"chatcut-inc":{"source":{"source":"git",
   "url":"https://github.com/ChatCut-Inc/agent-plugin.git","ref":"main"}}}}
JSON""",
        """cat > /root/.claude/plugins/installed_plugins.json <<'JSON'
{"version":2,"plugins":{"chatcut@chatcut-inc":[{"scope":"user",
"installPath":"/root/.claude/plugins/cache/chatcut-inc/chatcut/1.10.12",
"version":"1.10.12"}]}}
JSON""",
    )
    .add_local_dir(os.path.join(_HERE, "knowledge"), "/craft/knowledge",
                   copy=True)
    .add_local_file(os.path.join(_HERE, "control_distributions.json"),
                    "/craft/control_distributions.json", copy=True)
    .add_local_file(os.path.join(_HERE, "reference_index.json"),
                    "/craft/reference_index.json", copy=True)
)


# THE LIVE TOKEN STORE. A Modal Secret is immutable from inside a function, so
# a rotating refresh token written only to a log is lost the moment the
# container exits — and the NEXT job fails with a credential that looks expired
# rather than superseded. The Dict is seeded from the Secret once and is the
# source of truth afterwards.
TOKENS = modal.Dict.from_name("chatcut-tokens", create_if_missing=True)
# RESULTS OUTLIVE THE LAUNCHER. Two runs were lost to "Received a cancellation
# signal" — CLIENT side, the round-58 class, and setsid + --detach did not stop
# it. The lesson this repo already wrote down is that `.spawn()`ed work outlives
# the local process, so the RESULT must land somewhere durable rather than being
# returned to a client that may not be there. A job whose answer dies with the
# launcher is a job that did the work and reported nothing.
RESULTS = modal.Dict.from_name("chatcut-results", create_if_missing=True)


def _access_token():
    """Exchange the stored refresh token for an access token. STATE, not a guess.

    ROTATION IS HANDLED AND SAID OUT LOUD. If ChatCut returns a NEW refresh
    token, the old one may already be dead — two concurrent containers sharing
    one stored token would then race and one would silently invalidate the
    other, surfacing only as intermittent auth failure under load. We report the
    rotation so the Secret can be updated; we never pretend it did not happen.
    """
    # THE DICT WINS over the Secret: it holds the most recent rotation. The
    # Secret is the seed, used only until the first rotation happens.
    cid = os.environ.get("CHATCUT_CLIENT_ID")
    rt = TOKENS.get("refresh_token") or os.environ.get("CHATCUT_REFRESH_TOKEN")
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
        # PERSISTED, NOT ANNOUNCED. Round 1 of this job proved ChatCut DOES
        # rotate on use: the warning fired, the new value was dropped, and the
        # stored credential was dead from that moment. A warning about a
        # credential you then discard is the absence-as-success shape wearing a
        # log line.
        TOKENS["refresh_token"] = tok["refresh_token"]
        print("  TOKEN ROTATED   : persisted the new refresh token to the "
              "chatcut-tokens Dict. Concurrent containers sharing one token "
              "still race — serialise jobs or give each its own grant.",
              flush=True)
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
    # PER-CALL ROUND TRIP, the number nobody had. If ChatCut answers in 400ms
    # then 15 calls is six seconds and the ceiling is the model; if it answers
    # in 3s then no amount of call-collapsing saves us and the ceiling is the
    # network. Measured with the cheapest real read, three times, so one warm
    # cache or one slow hop does not become the answer.
    _rt = []
    for _i in range(3):
        _s = time.time()
        try:
            rpc("tools/call", {"name": "list_projects", "arguments": {"limit": 1}},
                10 + _i)
            _rt.append(round((time.time() - _s) * 1000))
        except Exception:                                         # noqa: BLE001
            pass
    if _rt:
        print("  MCP ROUND TRIP  : MEASURED  %s ms (min %d, median %d)"
              % (_rt, min(_rt), sorted(_rt)[len(_rt) // 2]), flush=True)
    else:
        print("  MCP ROUND TRIP  : ABSENT — could not time a call", flush=True)
    names = [t["name"] for t in (tools.get("result") or {}).get("tools", [])]
    if "create_project" not in names or "submit_export" not in names:
        raise RuntimeError(
            f"PREFLIGHT FAILED: MCP answered but the editing tools are absent "
            f"({len(names)} tools: {names[:8]}). Refusing to run.")
    print(f"  PREFLIGHT       : MEASURED  {len(names)} tools, create_project "
          f"and submit_export present", flush=True)
    return {"n_tools": len(names), "round_trip_ms": _rt}


def classify_stream(path):
    """Where the turns actually go. Reads the stream-json transcript. PURE-ish.

    93 TURNS HAS A SHAPE AND NOBODY KNEW IT. Re-reading state, retrying
    malformed calls, verifying frame by frame, or genuinely deciding 93 times
    are FOUR DIFFERENT FIXES, and a total that does not distinguish them buys
    nothing. So every tool call is classified, not counted.

    THE FAMILY THIS SERVES, named because all four harness fixes on the first
    run were one class: SOMETHING THAT SUCCEEDS WHILE DOING NOTHING. curl wrote
    a 483-byte redirect body and exited 0. A token rotation was warned about and
    discarded. Three plugin pieces looked sufficient and the fourth was missing.
    A turn count is the same shape one level up: 93 is a number that reports
    activity and says nothing about whether any of it moved the edit forward.
    """
    import collections
    calls, errors, turns = [], 0, 0
    by_tool = collections.Counter()
    per_turn = collections.Counter()
    pending = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except Exception:                                     # noqa: BLE001
                continue
            t = ev.get("type")
            if t == "assistant":
                turns += 1
                for blk in (ev.get("message") or {}).get("content") or []:
                    if blk.get("type") == "tool_use":
                        nm = blk.get("name", "?")
                        by_tool[nm] += 1
                        per_turn[turns] += 1
                        pending[blk.get("id")] = nm
                        _in = json.dumps(blk.get("input") or {})[:110]
                        calls.append({"turn": turns, "tool": nm, "in": _in,
                                      "err": None})
            elif t == "user":
                for blk in (ev.get("message") or {}).get("content") or []:
                    if blk.get("type") == "tool_result":
                        nm = pending.get(blk.get("tool_use_id"))
                        bad = bool(blk.get("is_error"))
                        if bad:
                            errors += 1
                        for c in reversed(calls):
                            if c["tool"] == nm and c["err"] is None:
                                c["err"] = bad
                                break
    # READ vs WRITE vs VERIFY, because that is what tells the four fixes apart.
    READ = {"read_project", "browse_assets", "inspect_asset", "inspect_item",
            "read_script", "read_captions", "find_transcript", "list_projects",
            "browse_library", "manage_timelines", "edit_track", "search_fonts",
            "track_progress", "track_export"}
    VERIFY = {"preview_timeline"}
    buckets = collections.Counter()
    for c in calls:
        base = c["tool"].split("__")[-1]
        if base in VERIFY:
            buckets["verify"] += 1
        elif base in READ:
            buckets["read"] += 1
        elif c["tool"].startswith("mcp__"):
            buckets["write"] += 1
        else:
            buckets["local"] += 1
    # REPEATS: the same tool called with a byte-identical argument set is a
    # re-read of state the agent already had, not a new decision.
    seen, repeats = set(), 0
    for c in calls:
        k = (c["tool"], c["in"])
        if k in seen:
            repeats += 1
        seen.add(k)
    return {"assistant_turns": turns, "tool_calls": len(calls),
            "tool_errors": errors, "identical_repeats": repeats,
            "buckets": dict(buckets),
            "by_tool": by_tool.most_common(20),
            "turns_with_no_tool": sum(1 for i in range(1, turns + 1)
                                      if per_turn[i] == 0),
            "calls": calls}


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

HOW TO WORK — THE LOOP, AND IT IS A LOOP ON PURPOSE

  PLACE EVERYTHING IN ONE BATCH. PREVIEW THE WHOLE TIMELINE ONCE. REVISE IN ONE
  BATCH. PREVIEW AGAIN. RENDER.

  `edit_item` takes `adds`, `updates` and `deletes` together and commits them
  atomically — one call places every overlay, card and trim you have decided on.
  Eleven separate calls to place eleven things is eleven round trips and eleven
  turns for one decision you already made.

  THE REVIEW PASSES ARE NOT OPTIONAL. The batch is only safe BECAUSE they
  exist: placing eleven things blind and rendering would be faster and worse.
  Never skip a preview to save time. If you are short of budget, cut the number
  of placements, never the number of looks.

  LOOK AT FRAMES IN CONTACT SHEETS, NOT ONE AT A TIME. Reading 25 stills is 25
  turns. Tile them into ONE image and read that:

    ffmpeg -v error -i /work/source.mp4 -vf \
      "select='not(mod(n\,NN))',scale=240:-1,tile=5x3" -frames:v 1 /tmp/sheet.png

  One sheet across the whole clip tells you the shots, the burned-in graphics
  and the free bands. Go to individual frames only for a moment the sheet
  cannot resolve. The same applies to verification: `preview_timeline` with
  `viewerFrameCount` returns several composed frames in ONE call.

  1. Import the clip, wait for transcription, place it.
  2. Read the transcript with read_script before deciding the cut. The cut is
     what you REMOVE: a false start, a restated point, a run-up that says
     nothing. Saying "nothing to cut" is a real answer; padding is not.
  3. Look at the actual frames with preview_timeline views:["viewer"] BEFORE
     choosing where anything goes. The frame decides placement, not the
     timing. Footage with burned-in graphics has different free bands than a
     clean talking head.
  4. Place what the moment needs, ALL IN ONE edit_item BATCH. Vary size, case
     and position deliberately — the reference shares are in your context.
  5. Verify composed frames before you call it done. A successful tool call is
     not verification. Use one preview_timeline call with viewerFrameCount
     rather than one call per frame.
  6. Export video, h264, 1080p.

A BUDGET, SO THE LOOP STAYS A LOOP: about fifteen ChatCut calls is the shape of
a good edit here — setup, transcript, one batch, two previews, export. If you
are heading past thirty, you are working one item at a time; stop and batch.
This is a budget on ROUND TRIPS, never on placements or on looks.

Report what you cut and why, what you placed and where, and the render id.
"""


# THE DOCUMENTS THE AGENT ACTUALLY READ, chosen from the transcript rather than
# guessed. Run shape-144148 spent four Read calls on exactly these four, plus
# three python one-liners pulling shares out of control_distributions.json.
# 55KB of prose is ~14k tokens, cached across every turn of the session — the
# agent paid a TURN per document to obtain what a cached system prompt hands it
# for free. The rest of /craft stays mounted for the rare lookup.
LOADBEARING = ["00_job_and_arc.md", "02_intent_standard.md", "01_cut_pass.md",
               "04_text_overlays.md"]

# THE TOOLS, NAMED. Nine ToolSearch calls went on discovering a toolset we
# already know is needed: ChatCut exposes 60 tools so Claude Code defers their
# schemas. There is no eager-load flag, so the next best thing is to tell the
# agent exactly which ones to fetch, in ONE call instead of nine.
NEEDED_TOOLS = [
    "create_project", "target_project", "list_projects", "import_media",
    "browse_assets", "inspect_asset", "trigger_transcript", "track_progress",
    "read_script", "apply_script", "find_transcript", "preview_timeline",
    "inspect_item", "edit_item", "edit_track", "manage_timelines",
    "split_item", "smooth_audio", "browse_library", "search_fonts",
    "create_motion_graphic_from_code", "edit_asset", "edit_captions",
    "read_captions", "submit_export", "track_export",
]


def control_digest(path="/craft/control_distributions.json"):
    """The corpus shares as prose, with denominators. DERIVED at job time.

    The agent computed this itself with three python one-liners. Handing it over
    costs nothing and saves three turns — and it stays DERIVED from the file, so
    a corpus re-read moves the prompt and no share is ever hand-typed.
    """
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception as e:                                        # noqa: BLE001
        return f"[control distributions ABSENT ({e}) — no corpus behind these]"
    out = []
    for fam in ("text", "card", "cutaway"):
        f = (d.get("by_family") or {}).get(fam) or {}
        bits = []
        for field in ("case", "size", "where"):
            dd = f.get(field) or {}
            vals = list((dd.get("values") or {}).items())[:4]
            if not vals:
                continue
            bits.append("%s (%d of %d answered): %s" % (
                field, dd.get("answered", 0), dd.get("of_placements", 0),
                ", ".join("%s %d%%" % (k, round(100 * (v.get("share") or 0)))
                          for k, v in vals)))
        if bits:
            out.append("  %s — %d placements over %d videos\n    %s"
                       % (fam.upper(), f.get("placements", 0),
                          f.get("videos", 0), "\n    ".join(bits)))
    return "\n".join(out)


def build_system_prompt():
    """The craft, in the session's context instead of on its to-do list."""
    parts = [CRAFT_CONTEXT, "\n\n===== THE CRAFT DOCUMENTS =====\n"]
    for name in LOADBEARING:
        p = os.path.join("/craft/knowledge", name)
        try:
            parts.append(f"\n----- {name} -----\n" + open(p, encoding="utf-8").read())
        except Exception as e:                                    # noqa: BLE001
            # ABSENT IS SAID, never silently skipped — a craft document that
            # failed to load would otherwise show up as the agent editing
            # generically, with nothing anywhere saying why.
            parts.append(f"\n----- {name} : ABSENT ({e}) -----\n")
    parts.append("\n\n===== WHAT THE REFERENCE CORPUS DOES =====\n"
                 "Shares with denominators. They DESCRIBE the references and "
                 "are never a target.\n" + control_digest())
    parts.append(
        "\n\n===== THE REST IS ON DISK =====\n"
        "/craft/knowledge/ holds the other documents and "
        "/craft/reference_index.json the annotated beats. Read them only if "
        "this job needs something the above does not cover.\n")
    return "".join(parts)


@app.function(image=IMG, timeout=1800,
              secrets=[modal.Secret.from_name("chatcut-oauth"),
                       modal.Secret.from_name("anthropic-api-key")])
def edit(clip_url: str, brief: str, model: str = "claude-sonnet-5",
         run_id: str = "latest"):
    t0 = time.time()
    marks = {}

    def mark(k):
        marks[k] = round(time.time() - t0, 2)

    tok = _access_token()
    mark("token")
    pf = preflight(tok)
    n_tools = pf["n_tools"]
    mark("preflight")

    os.makedirs("/work", exist_ok=True)
    # -L, AND THEN PROVE IT IS A VIDEO. Without -L an S3 presign against the
    # wrong region answers 301 and curl writes the 483-byte REDIRECT BODY to
    # source.mp4 — exit 0, a file exists, and the agent is handed XML. Caught
    # on the first staging attempt. ffprobe is the difference between "a file
    # arrived" and "the clip arrived", which is the same distinction as
    # MEASURED vs ABSENT everywhere else in this lane.
    subprocess.run(["curl", "-fsSL", "-o", "/work/source.mp4", clip_url],
                   check=True, timeout=300)
    _p = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=codec_type", "-show_entries", "format=duration",
         "-of", "default=nw=1", "/work/source.mp4"],
        capture_output=True, text=True, timeout=60)
    if _p.returncode != 0 or "video" not in _p.stdout:
        _sz = os.path.getsize("/work/source.mp4") if os.path.exists("/work/source.mp4") else 0
        raise RuntimeError(
            f"the downloaded clip is not a decodable video ({_sz} bytes): "
            f"{(_p.stderr or _p.stdout)[:200]} — refusing to hand the agent a "
            f"redirect body or an error page")
    print(f"  SOURCE          : MEASURED  {_p.stdout.strip().splitlines()[-1]}",
          flush=True)
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

    sys_prompt = build_system_prompt()
    with open("/work/system.md", "w") as fh:
        fh.write(sys_prompt)
    _sel = ",".join("mcp__chatcut__" + t for t in NEEDED_TOOLS)
    prompt = (
        f"THE CLIP: /work/source.mp4\n"
        f"THE BRIEF: {brief}\n\n"
        f"The ChatCut tool schemas are DEFERRED. Fetch them in ONE call before "
        f"you start:\n  ToolSearch query=\"select:{_sel}\"\n"
        f"The craft is already in your context — do not read /craft unless you "
        f"need something it does not cover.\n")
    led_prompt_chars = len(sys_prompt)
    r = subprocess.run(
        ["claude", "-p", prompt,
         "--append-system-prompt-file", "/work/system.md",
         # STREAM-JSON, because `json` returns only the final result and the
         # ordered tool calls are then unrecoverable. That gap is what made the
         # first run's 93 turns a number instead of a diagnosis.
         "--output-format", "stream-json", "--verbose",
         "--mcp-config", "/work/mcp.json",
         # NOT bypassPermissions. It maps to --dangerously-skip-permissions,
         # which REFUSES to run as root, and every Modal container is root:
         # "cannot be used with root/sudo privileges for security reasons".
         # An explicit allowlist is the right mechanism anyway — the agent
         # should have exactly the ChatCut tools and the local file tools, and
         # nothing it was never meant to reach.
         "--allowedTools", "mcp__chatcut__*,Bash,Read,Write,Glob,Grep",
         "--model", model],
        cwd="/work", capture_output=True, text=True, timeout=1500)
    mark("agent")
    with open("/work/stream.jsonl", "w") as fh:
        fh.write(r.stdout or "")
    try:
        shape = classify_stream("/work/stream.jsonl")
    except Exception as e:                                        # noqa: BLE001
        shape = {"error": f"classifier failed: {type(e).__name__}: {e}"}

    out = {"marks": marks, "tools": n_tools, "rc": r.returncode,
           "mcp_round_trip_ms": pf["round_trip_ms"],
           "system_prompt_chars": led_prompt_chars,
           "shape": shape,
           "stderr_tail": (r.stderr or "")[-2000:]}
    out["wall_s"] = round(time.time() - t0, 2)
    RESULTS[run_id] = out
    print(f"  RESULT PERSISTED: chatcut-results[{run_id}]", flush=True)
    return out


@app.local_entrypoint()
def main(clip_url: str = "", brief: str = "Cut this tighter and add one title.",
         run_id: str = "", wait: bool = False):
    if not clip_url:
        raise SystemExit("pass --clip-url")
    rid = run_id or f"run-{int(time.time())}"
    if wait:
        print(json.dumps(edit.remote(clip_url, brief, run_id=rid), indent=1)[:6000])
        return
    # SPAWN, DO NOT WAIT. The result lands in the chatcut-results Dict, so the
    # answer survives a client that is signalled, disconnected, or simply gone.
    call = edit.spawn(clip_url, brief, run_id=rid)
    print(f"SPAWNED run_id={rid} call={call.object_id}")
    print(f"read it with:  modal run chatcut_read_result.py --run-id {rid}")
