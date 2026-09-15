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
import re
import subprocess
import sys
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
    # PILLOW, because run 1 errored on `from PIL import Image`: the agent was
    # building its own contact sheet, a module this image did not have. The
    # sheet is already at /work/source_sheet.png, so this is insurance rather
    # than a fix — but an agent improvising around a tool it cannot import is
    # a turn spent and an error logged, and both are free to remove.
    # pillow AND numpy. Adding only pillow was a half-fix: the agent's command
    # is `from PIL import Image; import numpy as np`, so the identical error
    # came back on the next run. A fix aimed at the first line of a traceback.
    .pip_install("pillow", "numpy")
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
    # THE COMPONENT REGISTRY. 29 ported Remotion components, each through the
    # seven contract rules, so the agent references an assetId instead of
    # streaming ~20KB of JSX as tool arguments. That JSON was 37% of the wall.
    .add_local_file(os.path.join(_HERE, "chatcut_registry.json"),
                    "/craft/chatcut_registry.json", copy=True)
    # THE CATALOGUE — the library the agent SEES before it chooses. A bare enum
    # is a list of words: two rounds read 1-of-29 selected and StatCard x4
    # because the prefix named StatCard and nothing else. One sheet, 26
    # components, labelled with their size band; the JSON carries the WHEN
    # condition each answers, the 37 selection arrows, and props known to render
    # because they are the props that produced the still.
    .add_local_file(os.path.join(_HERE, "component_sheet.png"),
                    "/craft/component_sheet.png", copy=True)
    .add_local_file(os.path.join(_HERE, "chatcut_catalogue.json"),
                    "/craft/chatcut_catalogue.json", copy=True)
    .add_local_file(os.path.join(_HERE, "turn_clock.py"),
                    "/root/turn_clock.py", copy=True)
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


def mcp_rpc(access_token, method, params, mid=1):
    """One MCP call over plain HTTP. HOISTED so more than one caller can use it.

    It lived inside `preflight` as a closure, which made it unreachable from
    the pre-stage below and undrivable from a smoke — the same reason this repo
    hoists any rule a check must exercise: a local copy is what let two
    mutations pass green on the re-edit merge.
    """
    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps({"jsonrpc": "2.0", "id": mid, "method": method,
                         "params": params}).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "Authorization": f"Bearer {access_token}"},
        method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read().decode()
    if raw.lstrip().startswith("{"):
        return json.loads(raw)
    for line in reversed(raw.splitlines()):
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    raise RuntimeError(f"unparseable MCP response: {raw[:200]}")


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
        return mcp_rpc(access_token, method, params, mid)

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
    last_text = ""
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
                    if blk.get("type") == "text" and (blk.get("text") or "").strip():
                        last_text = blk["text"]
                for blk in (ev.get("message") or {}).get("content") or []:
                    if blk.get("type") == "tool_use":
                        nm = blk.get("name", "?")
                        by_tool[nm] += 1
                        per_turn[turns] += 1
                        pending[blk.get("id")] = nm
                        _raw = json.dumps(blk.get("input") or {})
                        # A 110-CHARACTER PREFIX CANNOT ANSWER A QUESTION ABOUT
                        # WHAT WAS SENT. The under-delivery gate counted
                        # `"type"` occurrences in this string and a two-element
                        # `adds` array shows only its first element — so a run
                        # that DID place both would have read as under-delivery.
                        # It happened to be right three times and would have
                        # lied on the first run that worked. The placement
                        # tools keep their input WHOLE; everything else keeps a
                        # prefix, and says so.
                        _whole = nm.endswith(("edit_item", "edit_asset",
                                              "manage_timelines", "edit_track"))
                        calls.append({"turn": turns, "tool": nm,
                                      "in": _raw if _whole else _raw[:110],
                                      "in_truncated": not _whole,
                                      "in_chars": len(_raw),
                                      "err": None})
            elif t == "user":
                for blk in (ev.get("message") or {}).get("content") or []:
                    if blk.get("type") == "tool_result":
                        nm = pending.get(blk.get("tool_use_id"))
                        bad = bool(blk.get("is_error"))
                        if bad:
                            errors += 1
                        # WHAT CAME BACK, for the placement tools. "Attempted
                        # and refused" and "never formed" are different fixes
                        # and only the RESULT tells them apart — a refusal
                        # carries the reason, an absence carries nothing.
                        _c = blk.get("content")
                        if isinstance(_c, list):
                            _c = " ".join(str(x.get("text") or "") for x in _c
                                          if isinstance(x, dict))
                        _c = str(_c or "")
                        for c in reversed(calls):
                            if c["tool"] == nm and c["err"] is None:
                                c["err"] = bad
                                if not c.get("in_truncated") or bad:
                                    c["result"] = _c[:1200]
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
            "calls": calls,
            # THE AGENT'S OWN LAST WORD. Three runs skipped a placement and the
            # only account of why was a 110-char prefix of a call it never
            # made. If it decided against the title, it probably said so.
            "final_text": last_text[:4000]}


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
      "select='not(mod(n\\,NN))',scale=240:-1,tile=5x3" -frames:v 1 /tmp/sheet.png

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


# ── THE PROMISE IS PART OF THE CAPABILITY ──────────────────────────────────
# These paragraphs used to be UNCONDITIONAL while the subagent itself was
# behind `use_hands`. So a `--no-use-hands` run told the agent it had a `hands`
# subagent, the agent called `Agent(subagent_type="hands")`, that failed, and it
# retried with the generic `claude` subagent — 152 of 160 seconds of the bucket
# I had just reported as "CLI overhead". Two runs described as no-hands both
# had a subagent, and the comparison built on them was contaminated.
#
# This repo's rule is "a capability in the schema will be used"; this is the
# same rule from the other side — a capability in the PROMPT that is not in the
# schema gets ATTEMPTED, and the attempt costs turns whether or not it works.
# `Agent` is not in --allowedTools either, which does not stop it: the
# allowlist does not gate the built-in.
HANDS_PARA_PLAN = (
    "YOU HAVE A `hands` SUBAGENT ON A FASTER MODEL. In this mode almost "
    "everything is already decided, so almost everything is its work: the "
    "import, the transcription wait, every trim to a range the plan names, "
    "every placement whose geometry the plan gives, the export and its "
    "polling. Keep for yourself only the LOOK — whether the composed frames "
    "are right — and the one revision. Hand it decided parameters, one task "
    "out, one result back, and never in the background.\n\n")

HANDS_PARA_DECIDE = (
    "YOU HAVE A `hands` SUBAGENT ON A FASTER MODEL. Delegate the mechanical "
    "legs to it — import, waiting for transcription, a trim to a range you "
    "have decided, a placement whose geometry you have decided, the export "
    "and its polling. Keep every JUDGMENT yourself: what to cut, where things "
    "go, how large, what they say, and whether the composed frames are right. "
    "Hand it decided parameters, never a choice.\n"
    "DELEGATE SYNCHRONOUSLY AND WAIT FOR THE RESULT. One task out, one result "
    "back, then the next.\n")


# ── THE HOUSE TITLE, AUTHORED ONCE ─────────────────────────────────────────
# 227 of 608 seconds — 37% of the wall — was the model streaming tool-call JSON,
# and the largest single payload is a motion graphic's SOURCE CODE:
# `create_motion_graphic_from_code` takes the whole component inline, so the
# biggest thing an execution agent produces is JSX it is retyping from scratch
# on every run. Authored here once and registered BEFORE the agent starts, the
# agent receives an assetId and writes none of it.
#
# WHY NOT THE PORTED REMOTION COMPONENTS. They are frame-verified against
# Remotion and still REFUSED by ChatCut's validator on six counts: ~60
# top-level constants, four top-level components where exactly one is allowed,
# React.createContext, Freeze, loadFont, and static prop-name matching. Faithful
# to Remotion is not the same as correct here, which was the whole finding.
#
# THREE CONTRACT RULES LEARNED FROM THE VALIDATOR, not from documentation:
#   * exactly ONE top-level component, and no top-level constants at all;
#   * the root must be a plain div, never an AbsoluteFill;
#   * every editable value must be read through an identifier literally named
#     `props` — binding item.props to `p` makes the checker report the property
#     as declared-but-unused. It is a static name match, which is also why a
#     helper whose PARAMETER was named `props` once had its locals reported as
#     undeclared item properties.
TITLE_COMPONENT = r"""
const Component = ({ item }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const props = (item && item.props) || {};
  const text = props.text || "";
  const band = props.band || "upper_third";
  const size = props.size || "large";
  const holdSeconds = props.holdSeconds || 3;
  const textColor = props.textColor || "#FFFFFF";
  const accentColor = props.accentColor || "#C8551F";
  const justify = band === "upper_third"
    ? "flex-start" : band === "lower_third" ? "flex-end" : "center";
  const fontSize = size === "dominant" ? 168
    : size === "large" ? 128 : size === "medium" ? 96 : 72;
  const enterFrames = Math.max(1, Math.round(0.35 * fps));
  const t = Math.min(Math.max(frame / enterFrames, 0), 1);
  const ease = t < 0.25
    ? 1.333 * 0.25 * (Math.pow(t / 0.25, 3) - 0.5 * Math.pow(t / 0.25, 4))
    : 1.333 * (0.125 + (t - 0.25));
  const enter = Math.min(1, ease);
  const holdFrames = Math.max(enterFrames + 6, Math.round(holdSeconds * fps));
  const exit = interpolate(frame, [holdFrames - 8, holdFrames], [1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const rule = interpolate(frame, [enterFrames, enterFrames + 6], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    flexDirection: "column", alignItems: "center", justifyContent: justify,
    boxSizing: "border-box", paddingTop: 270, paddingBottom: 420,
    paddingLeft: 80, paddingRight: 200, backgroundColor: "transparent" };
  return (
    <div style={rootStyle}>
      <div style={{ display: "flex", flexDirection: "column",
        alignItems: "center", opacity: enter * exit }}>
        <div style={{ fontFamily: "Anton", fontSize: fontSize, fontWeight: 400,
          letterSpacing: "-0.02em", lineHeight: 1.05, color: textColor,
          textTransform: "uppercase", textAlign: "center", maxWidth: 760,
          whiteSpace: "normal", overflowWrap: "break-word",
          transform: `scale(${0.94 + 0.06 * enter})`, transformOrigin: "center",
          textShadow: "0 2px 10px rgba(0,0,0,0.9), 0 14px 44px rgba(0,0,0,0.6)" }}>
          {text}
        </div>
        <div style={{ marginTop: 18, width: Math.round(fontSize * 3.2),
          height: Math.max(8, Math.round(fontSize * 0.075)), borderRadius: 6,
          backgroundColor: accentColor, transform: `scaleX(${rule})`,
          transformOrigin: "center", boxShadow: "0 3px 10px rgba(0,0,0,0.5)" }} />
      </div>
    </div>
  );
};
"""

TITLE_DEFAULTS = {"band": "upper_third", "size": "medium",
                  "holdSeconds": 3, "textColor": "#FFFFFF",
                  "accentColor": "#C8551F"}

TITLE_PROPS = [
    {"key": "text", "label": "Title", "type": "text", "defaultValue": "TITLE"},
    {"key": "band", "label": "Band", "type": "select",
     "defaultValue": "upper_third",
     "options": ["upper_third", "middle", "lower_third"]},
    {"key": "size", "label": "Size", "type": "select", "defaultValue": "large",
     "options": ["small", "medium", "large", "dominant"]},
    {"key": "holdSeconds", "label": "Hold (s)", "type": "number",
     "defaultValue": 3},
    {"key": "textColor", "label": "Text colour", "type": "color",
     "defaultValue": "#FFFFFF"},
    {"key": "accentColor", "label": "Accent colour", "type": "color",
     "defaultValue": "#C8551F"},
]



def prestage(access_token, title_text, controls=None, source_path=None,
             want_components=None, titles=None, w=1080, h=1920, fps=30):
    """Create the project and register the title BEFORE the agent starts.

    Scoped deliberately to the two calls whose shapes have been OBSERVED here —
    create_project and create_motion_graphic_from_code. `import_media` is left
    to the agent because nobody has read its schema, and guessing one is what
    cost ten turns of parameter spelling in the 999s run.
    """
    def _find(obj, key):
        """First value for `key` anywhere in the response. RECURSIVE ON PURPOSE.

        The raw MCP envelope does not put a tool's fields where the tool's own
        documentation shows them: `create_project` returns its project under
        `_meta.chatcutLiveProject`, and reading a top-level `projectId` got
        None. Rather than hard-code one nesting — which is the shape-guessing
        that cost ten turns in the 999s run — find the key wherever it is, and
        fail loudly naming what came back if it is nowhere.
        """
        if isinstance(obj, dict):
            if key in obj and obj[key]:
                return obj[key]
            for v in obj.values():
                got = _find(v, key)
                if got:
                    return got
        elif isinstance(obj, list):
            for v in obj:
                got = _find(v, key)
                if got:
                    return got
        return None

    def call(name, args, mid):
        r = mcp_rpc(access_token, "tools/call",
                    {"name": name, "arguments": args}, mid)
        if r.get("error"):
            raise RuntimeError(f"prestage {name} failed: {r['error']}")
        out = (r.get("result") or {})
        txt = ""
        for c in out.get("content") or []:
            txt += c.get("text") or ""
        if txt.strip().startswith("{"):
            try:
                merged = json.loads(txt)
                if isinstance(merged, dict):
                    merged.setdefault("_envelope", out)
                    return merged
            except Exception:                                     # noqa: BLE001
                pass
        return out

    proj = call("create_project",
                {"name": "Promptly plan-first", "compositionWidth": w,
                 "compositionHeight": h, "fps": fps}, 20)
    pid = _find(proj, "projectId")
    if not pid:
        # last resort: the id is in the editor URL, which is always present
        _u = _find(proj, "editorUrl") or ""
        _m = re.search(r"/editor/([0-9a-f-]{36})", _u)
        pid = _m.group(1) if _m else None
    if not pid:
        raise RuntimeError(f"prestage: no projectId anywhere in {str(proj)[:300]}")
    # A PLAN WITH NO GRAPHICS STILL WANTS THE PROJECT AND THE SOURCE STAGED.
    # The house title was a required argument, so pre-staging was coupled to
    # having something to title — and a cut-only plan would either skip the
    # pre-stage entirely (handing the agent an import it should never do) or
    # register a title asset the plan never names, which the PLACEMENTS gate
    # would then have to explain away. Neither is the staging being asked for.
    mg = None if not title_text else call(
              "create_motion_graphic_from_code",
              {"projectId": pid, "name": "Title",
               "code": TITLE_COMPONENT, "width": w, "height": h,
               "durationInSeconds": 6,
               # FULL-FRAME BOX ON PURPOSE. The band is the component's job, so
               # the agent never has to decide item geometry — the one decision
               # that cost two failed guesses (`geometry`, then `rect`) in the
               # 999s run.
               "properties": [
                   dict(p, defaultValue=(
                       title_text if p["key"] == "text"
                       else (controls or {}).get(p["key"], p["defaultValue"])))
                   for p in TITLE_PROPS]}, 21)
    val = (_find(mg, "validation") or {}) if mg else {}
    if val.get("errors"):
        raise RuntimeError(f"prestage: the house title no longer validates: "
                           f"{val['errors']}")
    # ── THE IMPORT, DONE BY THE HARNESS ────────────────────────────────────
    # 43 of 56 tool calls in one run were Read and Bash, because `import_media`
    # only opens a SESSION — the bytes go up through a plugin helper script the
    # agent has to drive by hand, file by file. The helper is baked into this
    # image, the harness has the same token, and none of it is a decision. So
    # the harness runs it and the agent never touches the upload.
    #
    # THE FIELD NAMES WERE READ OFF A LIVE create_session RESPONSE, not guessed:
    # `token` (cmi_exec_...), `endpoint`, ttlSeconds 1800.
    src_asset = None
    if source_path and os.path.exists(source_path):
        sess = call("import_media",
                    {"action": "create_session", "projectId": pid}, 22)
        _tok = _find(sess, "token")
        _ep = _find(sess, "endpoint")
        if not (_tok and _ep):
            raise RuntimeError(
                f"prestage: import session returned no token/endpoint — the "
                f"harness cannot upload and the agent would have to. Envelope: "
                f"{str(sess)[:300]}")
        helper = ("/root/.claude/plugins/cache/chatcut-inc/chatcut/1.10.12"
                  "/skills/asset-import/scripts/upload-media.mjs")
        if not os.path.exists(helper):
            raise RuntimeError(f"prestage: upload helper missing at {helper}")
        _out = "/work/import.json"
        _r = subprocess.run(
            ["node", helper, "--token", _tok, "--endpoint", _ep,
             "--input", source_path, "--json-out", _out],
            capture_output=True, text=True, timeout=900)
        if _r.returncode != 0:
            raise RuntimeError(
                f"prestage: the upload helper exited {_r.returncode}. "
                f"stderr tail: {(_r.stderr or '')[-500:]}")
        try:
            _imp = json.load(open(_out, encoding="utf-8"))
        except Exception as e:                                    # noqa: BLE001
            raise RuntimeError(f"prestage: helper wrote no readable "
                               f"{_out}: {type(e).__name__}: {e}")
        src_asset = _find(_imp, "assetId")
        if not src_asset:
            raise RuntimeError(
                f"prestage: the upload reported success and returned no "
                f"assetId — the agent would have nothing to place. "
                f"{str(_imp)[:300]}")

    # ── ONE ASSET PER PLANNED TITLE ────────────────────────────────────────
    # A plan with fifteen graphics needs fifteen different strings, and one
    # asset carries one default. ChatCut supports per-ITEM property overrides —
    # `inspect_item` prints "Motion Graphic Effective Props … (default)" — but
    # the WRITE field is not in any surface I have read, and two guesses at it
    # (`props`, `propertyValues`) were both refused. Guessing a third is the
    # exact habit that cost ten turns of parameter spelling.
    #
    # So the need is removed instead: register one asset per planned title, its
    # text and controls baked in, and the agent places assetIds. Registration is
    # the one path proven 29 of 29.
    made = []
    for _i, _t in enumerate(titles or []):
        _c = dict(TITLE_DEFAULTS)
        _c.update(_t.get("controls") or {})
        _c["text"] = _t.get("text") or ""
        try:
            _r = call("create_motion_graphic_from_code",
                      {"projectId": pid, "name": "Title %02d" % (_i + 1),
                       "code": TITLE_COMPONENT, "width": w, "height": h,
                       "durationInSeconds": 8,
                       "properties": [dict(p, defaultValue=_c.get(
                           p["key"], p["defaultValue"])) for p in TITLE_PROPS]},
                      300 + _i)
            _v = _find(_r, "validation") or {}
            made.append({"text": _c["text"],
                         "assetId": None if _v.get("errors") else _find(_r, "assetId"),
                         "errors": _v.get("errors") or []})
        except Exception as e:                                    # noqa: BLE001
            made.append({"text": _c["text"], "assetId": None,
                         "errors": [f"{type(e).__name__}: {e}"]})
    if titles:
        _ok = sum(1 for m in made if m["assetId"])
        print("  TITLES          : MEASURED  %d of %d registered"
              % (_ok, len(titles)), flush=True)
        if _ok < len(titles):
            raise RuntimeError(
                "prestage: %d planned title(s) did not register — the agent "
                "would have nothing to place for them, and a partial library "
                "reads exactly like a complete one: %s"
                % (len(titles) - _ok,
                   [m["errors"][:1] for m in made if not m["assetId"]][:3]))

    # ── REGISTER THE LIBRARY ────────────────────────────────────────────────
    # Registered once per project, referenced by id thereafter. Failures are
    # COUNTED AND NAMED rather than swallowed: a component that does not
    # register is one the agent would have to author, which is the cost this
    # exists to remove, and a silent partial registry looks exactly like a
    # complete one.
    registered, reg_failed = {}, {}
    try:
        _reg = json.load(open("/craft/chatcut_registry.json", encoding="utf-8"))
    except Exception as e:                                        # noqa: BLE001
        _reg = {}
        print(f"  REGISTRY        : ABSENT ({e}) — the agent will have to "
              f"author any component it needs", flush=True)
    for _i, (_n, _c) in enumerate(sorted(_reg.items())):
        if want_components and _n not in want_components:
            continue
        try:
            _r = call("create_motion_graphic_from_code",
                      {"projectId": pid, "name": _n, "code": _c["code"],
                       "width": w, "height": h, "durationInSeconds": 5,
                       "properties": _c["properties"]}, 100 + _i)
            _v = _find(_r, "validation") or {}
            if _v.get("errors"):
                reg_failed[_n] = _v["errors"][:2]
            else:
                registered[_n] = _find(_r, "assetId")
        except Exception as e:                                    # noqa: BLE001
            reg_failed[_n] = [f"{type(e).__name__}: {e}"][:1]
    if _reg:
        print("  REGISTRY        : MEASURED  %d registered / %d attempted"
              % (len(registered), len(registered) + len(reg_failed)), flush=True)
        for _n, _e in list(reg_failed.items())[:6]:
            print(f"      REFUSED {_n}: {str(_e)[:150]}", flush=True)

    aid = _find(mg, "assetId") if mg else None
    if mg and not aid:
        raise RuntimeError(f"prestage: the title registered but returned no "
                           f"assetId — the agent would have nothing to place: "
                           f"{str(mg)[:300]}")
    return {"projectId": pid, "timelineId": _find(proj, "timelineId"),
            "trackId": _find(proj, "trackId"), "titleAssetId": aid,
            "sourceAssetId": src_asset, "titles": made,
            "components": registered, "components_refused": reg_failed,
            "editorUrl": _find(proj, "editorUrl")}


# ── THE SHEET IS REQUIRED, AND THE GATE AND THE PROMPT SHARE THIS SENTENCE ──
# Three runs reported VISUAL PASS: FAILED for not reading the contact sheet,
# and all three were obeying their instructions: the deciding prompt says
# "BEFORE ANY CUT DECISION, read it", the plan prompt said "you also have it,
# IF YOU NEED TO", and the gate demanded it in both. The agent did as it was
# told and the gate disagreed with the telling — a producer/consumer mismatch
# where I wrote both halves.
#
# AND THE COST WAS NOT BOOKKEEPING. The sheet is the only thing that shows what
# is BURNED INTO the footage. The plan is derived from the transcript and cannot
# see a graphic already on screen, so demoting the sheet removed the one check
# that would have caught this run's real defect: a title placed over the
# source's own "100 TIKTOKS PER HOUR", the same words twice.
#
# Both surfaces now read this constant, so they cannot drift apart again.
# ── PREVIEW FRAMES ARE URLs, AND Read TAKES PATHS ──────────────────────────
# The review ran HALF-BLIND. `preview_timeline` returns signed image URIs;
# `Read` takes local paths, so three consecutive Reads errored on the URL and
# the agent exported without ever seeing a composed frame. ChatCut's own skill
# says to download each URI and inspect the pixels there — and nothing in this
# prompt said so, which is the producer half of the same gap.
FETCH_RULE = (
    "LOOKING AT A COMPOSED FRAME TAKES TWO STEPS. `preview_timeline` returns "
    "signed image URLs, and `Read` only opens LOCAL paths — reading a URL "
    "errors and you will have looked at nothing. Download first, then read:\n"
    "    mkdir -p /work/frames && curl -fsSL -o /work/frames/f1.jpg \"<uri>\"\n"
    "    Read /work/frames/f1.jpg\n"
    "Use -fsSL: without it curl writes a redirect body and exits 0, which is a "
    "file that is not a frame.\n\n")

TWO_TURN_LOOP = (
    "THE LOOP IS TWO TURNS. A third is a failure state, not a budget.\n\n"
    "  TURN 1 — PLACE EVERYTHING, IN ONE BATCH. Every add the plan names goes "
    "in a SINGLE edit_item call: the video segments and the graphics together. "
    "`edit_item` commits the whole batch atomically and rolls the whole batch "
    "back on one failure, so a batch that fails tells you something a "
    "half-built timeline never can. Do not place them one at a time to watch "
    "them land.\n\n"
    "  TURN 2 — LOOK, THEN FIX IN ONE BATCH. Call preview_timeline with "
    "viewerFrameCount, DOWNLOAD the frames and READ them as images (see the "
    "two-step rule below), and judge the COMPOSED PICTURE — not the tool "
    "results, which cannot show you a collision. Then make every correction in "
    "one more edit_item call. Spend this turn only on what the frames show: "
    "something illegible, something colliding, something off-frame, something "
    "landing on the wrong moment. Not on taste. If the frames are right, skip "
    "the turn and export — a revision you cannot justify from a frame is a "
    "revision that costs a turn and changes nothing.\n\n"
    "  TURN 3 — ONLY ON A DEFECT YOU CAN NAME. If you take one, your final "
    "message must name the defect, the frame you saw it in, and what you "
    "changed. Unnamed, it is the same as not taking it: the run reports the "
    "third turn as UNJUSTIFIED and the edit is judged without it.\n\n"
    "WHY THE BATCHES. Each turn is a model turn with the whole context behind "
    "it, and the measured wall is 71-84% the model producing tokens — so turns "
    "are the unit that costs, not calls. Three placements in three turns costs "
    "three times what three placements in one batch costs and builds the same "
    "timeline.\n\n")

SHEET_RULE = (
    "BEFORE YOU PLACE ANYTHING, read the image /work/source_sheet.png — a "
    "20-frame contact sheet of the whole source. THE PLAN CANNOT SEE THE "
    "FOOTAGE: it is derived from the transcript, so it does not know what is "
    "already BURNED INTO the frame. If the source already shows the words a "
    "title would add, say so and skip that placement rather than printing the "
    "same words twice. This is checked after the run.\n\n")


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
    # ── THE LIBRARY, IN THE PROMPT ─────────────────────────────────────────
    # The eight WHEN headings are the discriminator the selection question
    # actually needs, and they have sat in a document `read_knowledge` was
    # called ZERO times on. In the context, not on the to-do list — the same
    # move as the craft documents above.
    try:
        _cat = json.load(open("/craft/chatcut_catalogue.json", encoding="utf-8"))
        _cond = _cat.get("_conditions") or {}
        _comp = _cat.get("components") or {}
        _lines = ["\n\n===== THE COMPONENT LIBRARY =====\n",
                  "Every one of these is ALREADY REGISTERED in your project. You "
                  "place it by assetId and you never author component code.\n",
                  "/craft/component_sheet.png is one image of all of them — READ "
                  "IT before you choose, the way you read the source sheet.\n"]
        for _h, _cs in _cond.items():
            _lines.append("  %s\n      %s\n" % (
                _h, ", ".join("%s (%s)" % (c, (_comp.get(c) or {}).get(
                    "size_band", "?")) for c in _cs)))
        _arrows = [(c, v["reach_for_it_instead_of"]) for c, v in _comp.items()
                   if v.get("reach_for_it_instead_of")]
        if _arrows:
            _lines.append("\n  REACH FOR IT INSTEAD OF — the catalogue's own "
                          "discriminators:\n")
            for _c, _a in sorted(_arrows):
                _lines.append("      %-18s not: %s\n" % (_c, "; ".join(_a[:4])))
        parts.append("".join(_lines))
    except Exception as _e:                                       # noqa: BLE001
        parts.append("\n\n===== THE COMPONENT LIBRARY : ABSENT (%s) =====\n"
                     "The agent will be choosing from names alone.\n" % _e)
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
         run_id: str = "latest", use_hands: bool = True, plan: str = "",
         think_tokens: int = 0, prestage_title: str = "",
         prestage_controls: str = "", prestage_titles: str = ""):
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
    # THE CONTACT SHEET IS BUILT BY THE HARNESS, NOT ASKED FOR IN THE PROMPT.
    # The Haiku arm inspected ZERO source frames and kept 4.4s of TikTok app
    # chrome that both Sonnet arms found and trimmed. Telling a model to look
    # is a preference; putting the picture in front of it is a property. This
    # also removes the ffmpeg turns the Sonnet arms spent building sheets by
    # hand — the work happens once, in a subprocess, for free.
    _dur = 0.0
    for _ln in _p.stdout.splitlines():
        if _ln.startswith("duration="):
            _dur = float(_ln.split("=", 1)[1] or 0)
    _n = 20
    _step = max(1, int(_dur * 30 / _n)) if _dur else 30
    _sheet = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", "/work/source.mp4", "-vf",
         f"select='not(mod(n\\,{_step}))',scale=240:-1,tile=5x4",
         "-frames:v", "1", "/work/source_sheet.png", "-y"],
        capture_output=True, text=True, timeout=180)
    _has_sheet = os.path.exists("/work/source_sheet.png") and \
        os.path.getsize("/work/source_sheet.png") > 5000
    if not _has_sheet:
        # ABSENT IS FATAL HERE. The whole point of this arm is that the agent
        # cannot skip looking; a missing sheet would silently return it to the
        # arm that missed the tail, and the run would look like a fair test.
        raise RuntimeError(
            f"could not build the source contact sheet "
            f"({(_sheet.stderr or '')[:160]}) — refusing to run, because the "
            f"visual pass is the property under test")
    print(f"  CONTACT SHEET   : MEASURED  /work/source_sheet.png "
          f"({os.path.getsize('/work/source_sheet.png')//1024} KB, "
          f"20 frames over {_dur:.1f}s)", flush=True)
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
    # max_results DEFAULTS TO 5 AND THE SELECT LIST IS 26 NAMES LONG, so the
    # "fetch them in ONE call" instruction was unsatisfiable as written: the
    # bulk call returned five schemas and every other tool stayed uncallable.
    # Measured on run-1789432983 — 23 ToolSearch calls out of 44 tool calls
    # total, being `edit_item` re-fetched six times before it would run and
    # `submit_export` sixteen, the agent visibly probing the cap
    # (max_results 1, 2, 10, omitted). Those 22 extra round trips are also
    # where 69% of that run's idle gap time sits. One argument, not a prompt
    # rewrite: the count comes FROM the list so it cannot drift from it.
    _nsel = len(NEEDED_TOOLS)
    # THE MODEL LEVER. ~700 of the 728s is the model thinking, and 39 of 88
    # turns called no tool at all, so the only remaining saving is thinking
    # LESS — not plumbing less. The split puts the mechanical legs (import,
    # wait for transcription, trim to a decided range, place a decided item,
    # export, poll) on Haiku and keeps every JUDGMENT on the stronger model.
    #
    # THE LINE IS DELIBERATE AND IT IS NOT "SIMPLE vs HARD". It is: has the
    # decision already been made? Choosing WHERE a card goes is editorial and
    # stays. Executing a placement whose frame, band and duration are already
    # chosen is mechanical and moves. A subagent that is asked to decide
    # anything is the wrong split and will show up as a worse edit.
    agents = {
        "hands": {
            "description": (
                "Executes ChatCut operations that are already decided: import, "
                "transcription waits, a trim to a given range, a placement with "
                "given geometry, export, and status polling. Never chooses what "
                "to cut, where something goes, how large it is, or what it says."),
            "model": "haiku",
            "prompt": (
                "You execute ChatCut operations that have ALREADY BEEN DECIDED. "
                "You are given exact parameters — frames, ranges, ids, "
                "geometry — and you make the calls and report what came back.\n\n"
                "YOU DO NOT MAKE EDITORIAL DECISIONS. If an instruction leaves "
                "a choice open — which moment, which band, how big, what "
                "wording, how long — do NOT pick one. Stop and say exactly "
                "which parameter is missing. A guess from you is indis"
                "tinguishable from a decision, and it will ship as one.\n\n"
                "Batch related operations into one call where the tool takes a "
                "batch. Report tool errors verbatim; never retry a call that "
                "failed for a reason you cannot name."),
        }
    }
    # ── THE THIRD LEVER: EXECUTE A DECIDED PLAN ────────────────────────────
    # Two levers have been measured and both are nearly spent. Simplifying the
    # SURFACE took 95 tool calls to 49 and moved the wall 840 -> 728, because
    # 39 of 88 turns call no tool at all: the time is the model deciding, and
    # deciding is also where the quality comes from. So the only untested lever
    # is to REMOVE THE DECISIONS rather than the plumbing — the pipeline has
    # already ruled this clip in ~45s of model time, and that ruling arrives
    # here as the starting point.
    #
    # THE RISK THIS PROMPT IS WRITTEN AGAINST: an agent handed a plan can
    # quietly re-decide and the wall does not move. That failure is invisible
    # in the output — a good edit either way — so the harness MEASURES
    # adherence from the call stream rather than trusting the instruction.
    _stage = None
    if plan:
        # THE RULED CONTROLS REACH THE ASSET. The planner now answers band,
        # size, hold and colour (0 refused, first pass); an acceptor that
        # ignores them is the v1 defect, and a harness that never forwards them
        # is the same defect one layer out.
        _ctl = json.loads(prestage_controls) if prestage_controls else {}
        _titles = json.loads(prestage_titles) if prestage_titles else []
        _stage = prestage(tok, prestage_title, controls=_ctl,
                          source_path="/work/source.mp4", titles=_titles)
        _libn = len(_stage.get("components") or {})
        print("  TITLE CONTROLS  : %s" % (json.dumps(_ctl) if _ctl
                                          else "ABSENT — defaults"), flush=True)
        print("  PRESTAGE        : MEASURED  project=%s title=%s source=%s  "
              "(the agent writes no JSX and uploads nothing)"
              % (_stage["projectId"][:8], (_stage["titleAssetId"] or "?")[:8],
                 (_stage["sourceAssetId"] or "ABSENT")[:8]), flush=True)
    if plan:
        with open("/work/PLAN.md", "w") as fh:
            fh.write(plan)
        prompt = (
            f"THE CLIP: /work/source.mp4\n"
            f"THE BRIEF: {brief}\n\n"
            f"THE EDIT IS ALREADY DECIDED. The plan is at /work/PLAN.md and "
            f"reproduced at the end of this message. It came from the pipeline "
            f"that has already read this clip's transcript and its frames. "
            f"YOUR JOB IS TO EXECUTE IT, LOOK AT WHAT YOU BUILT, AND FIX WHAT "
            f"THE FRAMES SHOW IS WRONG. It is not to decide the edit again.\n\n"
            f"DO NOT re-derive the cuts. Do not choose different moments, "
            f"different wording, or a different number of placements. Where "
            f"the plan is silent on a MECHANICAL detail — a font, an asset "
            f"boundary, an id — choose it and move on. Where it is silent on "
            f"an EDITORIAL one, build it as written and NAME THE OPEN QUESTION "
            f"in your final message. Do not fill it in quietly: a guess from "
            f"you is indistinguishable from a decision the pipeline made.\n\n"
            f"THE ChatCut tool schemas are DEFERRED. Fetch them in ONE call "
            f"before you start:\n  ToolSearch query=\"select:{_sel}\" "
            f"max_results={_nsel}\n"
            f"  (max_results defaults to 5 — without it you get five of the "
            f"{_nsel} and the rest stay uncallable.)\n\n"
            + TWO_TURN_LOOP
            + SHEET_RULE
            + FETCH_RULE
            + (HANDS_PARA_PLAN if use_hands else "")
            + (("EVERYTHING IS ALREADY STAGED. Create nothing and upload "
                "nothing.\n"
                f"  projectId      : {_stage['projectId']}\n"
                f"  source assetId : {_stage['sourceAssetId']}\n"
                + ("".join(
                    "  GRAPHIC %d assetId : %s   %r\n"
                    % (_i + 1, _t["assetId"], _t["text"])
                    for _i, _t in enumerate(_stage.get("titles") or []))
                   or (f"  title assetId  : {_stage['titleAssetId']}\n"
                       if _stage.get("titleAssetId") else
                       "  NO GRAPHIC IS STAGED — this plan names none. Place "
                       "the video segments only.\n"))
                + ("Call target_project with that id, then place EVERY add the "
                   "plan names in ONE edit_item call — the video segments and "
                   "the graphics together. Each graphic's assetId is listed "
                   "above and already carries its own text, band, size, hold "
                   "and colours, so there is nothing to pass and nothing to "
                   "decide. `import_media` and "
                   "`create_motion_graphic_from_code` are both NOT part of "
                   "this job. Your work is the placements, the look, and the "
                   "one revision.\n")
                + (("\nThe project also carries %d PRE-REGISTERED components, "
                    "each already validated, each with its editable properties "
                    "declared. If the plan calls for one, place it by assetId — "
                    "you never author component code:\n  %s\n"
                    % (_libn, ", ".join(
                        "%s=%s" % (k, (v or "?")[:8])
                        for k, v in sorted(
                            (_stage.get("components") or {}).items())[:40])))
                   if _libn else "")
                + "\n") if _stage else "")
            + f"===== THE PLAN =====\n{plan}\n===== END OF PLAN =====\n")
    else:
        prompt = (
            f"THE CLIP: /work/source.mp4\n"
            f"THE BRIEF: {brief}\n\n"
            + SHEET_RULE
            + FETCH_RULE
            + f"BEFORE RENDER, call preview_timeline with viewerFrameCount to see the "
            f"composed result. Both of these are checked after the run.\n\n"
            f"The ChatCut tool schemas are DEFERRED. Fetch them in ONE call before "
            f"you start:\n  ToolSearch query=\"select:{_sel}\" "
            f"max_results={_nsel}\n"
            f"  (max_results defaults to 5 — without it you get five of the "
            f"{_nsel} and the rest stay uncallable.)\n"
            f"The craft is already in your context — do not read /craft unless you "
            f"need something it does not cover.\n\n"
            + (HANDS_PARA_DECIDE if use_hands else ""))

    # THE PROMISE, CHECKED AGAINST THE CAPABILITY, IN THE LOG. Printed in the
    # same commit that gates it — a counter added to answer a question and never
    # shown answers nothing, and this one was invisible for two whole runs.
    _promises_hands = "`hands` subagent" in prompt
    print("  SUBAGENT        : offered=%s  promised_in_prompt=%s  %s"
          % (use_hands, _promises_hands,
             "OK" if _promises_hands == use_hands else
             "MISMATCH — the prompt and the capability disagree; the agent "
             "will call a subagent that does not exist"), flush=True)
    led_prompt_chars = len(sys_prompt)
    # ── THE TURN LOOP, TIMESTAMPED ─────────────────────────────────────────
    # `subprocess.run` hands back ONE BUFFER when the agent is already finished,
    # so every arrival time is lost and the loop is unmeasurable by
    # construction. 728 seconds and 88 turns is equally consistent with 700s of
    # generation, 700s of queueing, and 700s of a container parked on a run
    # queue — three different problems with three different fixes, and the
    # total cannot tell them apart.
    sys.path.insert(0, "/root")
    import turn_clock
    _pm_state, _pm = turn_clock.partial_messages_supported()
    print("  PARTIAL MESSAGES: %s  supported=%s" % (_pm_state, _pm), flush=True)
    _q_state, _q = turn_clock.cpu_quota()
    print("  CPU QUOTA       : %s  cores=%s  os.cpu_count=%s"
          % (_q_state, _q, os.cpu_count()), flush=True)
    _cmd = (
        ["claude", "-p", prompt,
         "--append-system-prompt-file", "/work/system.md",
         *(["--agents", json.dumps(agents)] if use_hands else []),
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
         "--model", model]
        # THE FLAG THAT MAKES THE SPLIT POSSIBLE. Without the deltas, queue,
        # prefill and generation collapse into one bucket — and a coarser
        # answer that looks identical to a finer one is the oldest failure in
        # this repo. Added only when the installed CLI actually takes it, and
        # its absence is printed rather than silently changing the meaning of
        # the number.
        + (["--include-partial-messages"] if _pm else []))
    # THE THINKING CAP. 267 of 608 seconds — 44% of the wall — was `thinking`
    # blocks on an agent handed a COMPLETE plan. It is executing, not deciding,
    # and it was reasoning as if it were. `MAX_THINKING_TOKENS` is read from the
    # binary's own strings, not from documentation: the CLI also carries
    # CLAUDE_CODE_DISABLE_THINKING and DISABLE_INTERLEAVED_THINKING, and this
    # is the one that BOUNDS rather than removes — the review pass still needs
    # judgment about whether the composed frames are right.
    _env = {"MAX_THINKING_TOKENS": str(think_tokens)} if think_tokens else {}
    print("  THINKING CAP    : %s"
          % (f"MAX_THINKING_TOKENS={think_tokens}" if think_tokens
             else "UNCAPPED (default)"), flush=True)
    _rc, _errtxt, _wall, _killed = turn_clock.run_timed(
        _cmd, "/work", "/work/stream.jsonl", "/work/timing.json", 1500,
        env=_env)
    mark("agent")

    class _R:
        pass
    r = _R()
    r.returncode, r.stdout, r.stderr = _rc, "", _errtxt
    try:
        _timing = json.load(open("/work/timing.json", encoding="utf-8"))
        _budget = turn_clock.budget(_timing)
    except Exception as e:                                        # noqa: BLE001
        _budget = {"state": "FAILED", "why": f"{type(e).__name__}: {e}"}
    try:
        shape = classify_stream("/work/stream.jsonl")
    except Exception as e:                                        # noqa: BLE001
        shape = {"error": f"classifier failed: {type(e).__name__}: {e}"}

    print("  TURN BUDGET     : %s" % json.dumps(
        {k: v for k, v in (_budget or {}).items() if k != "gap_detail"}),
        flush=True)
    out = {"think_tokens": think_tokens,
           "prestaged": bool(_stage),
           "turn_budget": _budget,
           "partial_messages": {"state": _pm_state, "supported": _pm},
           "marks": marks, "tools": n_tools, "rc": r.returncode,
           "mcp_round_trip_ms": pf["round_trip_ms"],
           "system_prompt_chars": led_prompt_chars,
           "shape": shape,
           "stderr_tail": (r.stderr or "")[-2000:]}
    # THE GATE. Suggested-in-the-prompt is a preference; checked-in-the-harness
    # is a property. A run that reached submit_export without ever looking at
    # the source sheet or the composed timeline is reported as a FAILED visual
    # pass, whatever it rendered — because that is exactly the run that kept
    # the dead tail and exited 0.
    _calls = (shape or {}).get("calls") or []
    _saw_sheet = any("source_sheet" in (c.get("in") or "") for c in _calls)
    _prev_i = [i for i, c in enumerate(_calls)
               if c["tool"].endswith("preview_timeline")]
    _exp_i = [i for i, c in enumerate(_calls)
              if c["tool"].endswith("submit_export")]
    _looked_before_render = bool(_prev_i) and (
        not _exp_i or min(_prev_i) < max(_exp_i))
    # THE UNDER-DELIVERY GATE. Every adherence leg asked whether the agent
    # ADDED something ruled out; none asked whether it placed what was ruled IN.
    # A run that skips a placement is FASTER and passes everything: 153.8s,
    # visual pass MEASURED, export submitted, exit 0, and no title. Over-reach
    # was instrumented and under-delivery was not — the cheaper failure to have
    # and the easier one to ship. It is a GATE now, not a line in a report.
    _planned = (plan.count("edit_item adds[") if plan else 0)
    # Counted on the WHOLE input now, and only where the input is whole — a
    # count over a prefix is a claim about a string, not about the call.
    _added = 0
    for c in _calls:
        if c["tool"].endswith("edit_item") and not c.get("in_truncated"):
            try:
                _a = (json.loads(c["in"]) or {}).get("adds") or []
                _added += len(_a)
            except Exception:                                     # noqa: BLE001
                _added += str(c.get("in") or "").count('"type"')
    # ── THE THIRD STATE ────────────────────────────────────────────────────
    # A planned placement can be absent for two opposite reasons and only one
    # is a failure. On 2026-09-14 the agent read the contact sheet, saw the
    # source already carried its own burned-in "100 TIKTOKS PER HOUR" in the
    # exact hook window, applied the rule against printing the same words twice,
    # skipped the title AND NAMED IT as the open question in its final message.
    # That is SHEET_RULE working — the very defect it was written to prevent —
    # and the gate called it UNDER_DELIVERED.
    #
    # A gate that cannot tell a reasoned refusal from a silent omission trains
    # the next agent to place the duplicate. DECLINED is the difference, and it
    # requires BOTH halves: the placement absent, and the agent having said so.
    # A decline verb alone is too loose — an agent that mentions "skip" in
    # passing would launder a real omission.
    _ft = ((shape or {}).get("final_text") or "").lower()
    _said_skip = any(w in _ft for w in
                     ("skipped", "left it out", "did not place", "omitted",
                      "declined", "not placed"))
    _named = any(w in _ft for w in ("title", "graphic", "v2", "overlay"))
    _declined = _added < _planned and _said_skip and _named
    out["placements"] = {
        "planned_adds": _planned, "items_added": _added,
        "declared_skip": bool(_said_skip and _named),
        "state": ("MEASURED" if _planned and _added >= _planned
                  else "ABSENT" if not _planned
                  else "DECLINED" if _declined
                  else "UNDER_DELIVERED")}
    print("  PLACEMENTS      : %s  plan asks %d add(s), agent added %d%s"
          % (out["placements"]["state"], _planned, _added,
             "  (the agent named the omission)"
             if out["placements"]["declared_skip"] else ""), flush=True)
    out["visual_pass"] = {
        "read_source_sheet": _saw_sheet,
        "previewed_before_render": _looked_before_render,
        "state": ("MEASURED" if (_saw_sheet and _looked_before_render)
                  else "FAILED"),
    }
    print("  VISUAL PASS     : %s  sheet=%s  preview_before_render=%s"
          % (out["visual_pass"]["state"], _saw_sheet, _looked_before_render),
          flush=True)
    out["wall_s"] = round(time.time() - t0, 2)
    RESULTS[run_id] = out
    print(f"  RESULT PERSISTED: chatcut-results[{run_id}]", flush=True)
    return out



@app.function(image=IMG, timeout=3600,
              secrets=[modal.Secret.from_name("chatcut-oauth"),
                       modal.Secret.from_name("anthropic-api-key")])
def component_render_check(sample_props_json: str = ""):
    """One ChatCut project per component. Frame diffed against its OWN empty
    frame. Nothing is ever removed.

    WHY THIS SHAPE. Five sweeps shared one timeline and tore down between
    measurements, and the teardown silently failed — so every row reported the
    control's pixels. The delete shape stops mattering if nothing needs
    deleting: each component gets a fresh project, its baseline is that
    project's own stage-only frame, and the two frames differ by exactly one
    thing. It also makes the result an INVENTORY rather than a tally — the
    frames compose the sheet the worker chooses from, and a component that
    does not appear in the sheet is not offered.
    """
    import urllib.request
    tok = _access_token()
    reg = json.load(open("/craft/chatcut_registry.json", encoding="utf-8"))
    comps = reg.get("components") or reg
    refused = reg.get("refused") or {}
    samples = json.loads(sample_props_json) if sample_props_json else {}
    STAGE = ('const Component = ({ item }) => {\n'
             '  const props = (item && item.props) || {};\n'
             '  const rootStyle = { position: "absolute", inset: 0,\n'
             '    backgroundColor: "#202024" };\n'
             '  return <div style={rootStyle} />;\n'
             '};\n')

    def call(name, args, mid):
        r = mcp_rpc(tok, "tools/call", {"name": name, "arguments": args}, mid)
        if r.get("error"):
            raise RuntimeError(f"{name}: {r['error']}")
        out = r.get("result") or {}
        txt = "".join(c.get("text") or "" for c in (out.get("content") or []))
        if txt.strip().startswith("{"):
            try:
                return json.loads(txt)
            except Exception:                                     # noqa: BLE001
                pass
        return out

    def find(o, k):
        if isinstance(o, dict):
            if o.get(k):
                return o[k]
            for v in o.values():
                g = find(v, k)
                if g:
                    return g
        elif isinstance(o, list):
            for v in o:
                g = find(v, k)
                if g:
                    return g
        return None

    def px(a, b):
        from PIL import Image, ImageChops
        import io
        ia = Image.open(io.BytesIO(a)).convert("RGB")
        ib = Image.open(io.BytesIO(b)).convert("RGB")
        if ia.size != ib.size:
            return 1.0, None
        d = ImageChops.difference(ia, ib).convert("L")
        m = d.point(lambda p: 255 if p > 12 else 0)
        return sum(m.histogram()[255:]) / float(ia.size[0] * ia.size[1]), m.getbbox()

    rows, frames = {}, {}
    for i, (n, spec) in enumerate(sorted(comps.items())):
        try:
            pr = call("create_project", {"name": f"render check {n}",
                                         "compositionWidth": 1080,
                                         "compositionHeight": 1920,
                                         "fps": 30}, 10 + i * 9)
            pid = find(pr, "projectId") or re.search(
                r"/editor/([0-9a-f-]{36})", find(pr, "editorUrl") or "").group(1)

            # THE SETTLED FRAME, NOT FRAME 30. A fixed frame measures whatever
            # phase the component happens to be in: SectionDivider enters over
            # 50 frames and PullQuote over 40, so frame 30 caught both
            # mid-entrance, at partial opacity, and a faint reading would have
            # been filed as the component's appearance. Each component is shot
            # after ITS OWN entrance completes and before its exit begins —
            # derived from the effective props, so the frame means the same
            # thing for every row and the sheet shows the settled design.
            eff = dict((p["key"], p["defaultValue"]) for p in spec["properties"])
            eff.update(samples.get(n) or {})
            _enter = eff.get("enterFrames") or 0
            _exit = eff.get("exitFrames") or 0
            _durf = round((eff.get("durationMs") or 4000) / 1000.0 * 30)
            at = max(1, min(int(_enter) + 8, _durf - int(_exit) - 4))

            def shot(mid):
                r = call("preview_timeline",
                         {"projectId": pid, "views": ["viewer"],
                          "viewerFrames": [at]}, mid)
                u = find(r, "uri")
                return (urllib.request.urlopen(u, timeout=120).read()
                        if u else None), u

            st = call("create_motion_graphic_from_code",
                      {"projectId": pid, "name": "stage", "code": STAGE,
                       "width": 1080, "height": 1920, "durationInSeconds": 20,
                       "properties": []}, 11 + i * 9)
            sid = st.get("assetId") if isinstance(st, dict) else None
            call("edit_item", {"projectId": pid, "adds": [
                {"type": "motion-graphic", "assetId": sid, "from": 0,
                 "durationInFrames": 300}]}, 12 + i * 9)
            base, _ = shot(13 + i * 9)
            if base is None:
                rows[n] = {"state": "FAILED", "how": "no baseline frame"}
                continue

            a = call("create_motion_graphic_from_code",
                     {"projectId": pid, "name": n, "code": spec["code"],
                      "width": 1080, "height": 1920, "durationInSeconds": 8,
                      "properties": spec["properties"]}, 14 + i * 9)
            v = find(a, "validation") or {}
            aid = a.get("assetId") if isinstance(a, dict) else None
            if v.get("errors") or not aid:
                rows[n] = {"state": "ABSENT", "how": "validator refused",
                           "detail": str(v.get("errors", a))[:400]}
                print("  %-18s ABSENT  refused" % n, flush=True)
                continue
            add = {"type": "motion-graphic", "assetId": aid, "from": 0,
                   "durationInFrames": 150}
            if samples.get(n):
                add["propertyOverrides"] = samples[n]
            call("edit_item", {"projectId": pid, "adds": [add]}, 15 + i * 9)
            shot_png, uri = shot(16 + i * 9)
            frac, box = (None, None) if shot_png is None else px(base, shot_png)
            rows[n] = {
                "content_unavailable": spec.get("content_unavailable") or [],
                "state": ("FAILED" if frac is None
                          else "MEASURED" if frac > 0.002 else "ABSENT"),
                "how": "own project, own empty frame, pixels diffed",
                "detail": (f"{frac*100:.3f}% px @f{at}, bbox {box}"
                           if frac is not None else "no frame"),
                "project": pid, "uri": uri or "",
            }
            if shot_png:
                # THE URI EXPIRES IN 900s AND THE RUN TAKES LONGER THAN THAT.
                # Carrying the frame home as bytes is the difference between
                # an inventory and a list of dead links — and the sheet is
                # built from these frames, so a link that 404s by the time it
                # is read would quietly shrink the set the worker is offered.
                import base64 as _b64
                frames[n] = {"uri": uri,
                             "jpg_b64": _b64.b64encode(shot_png).decode(),
                             "frame": at}
            print("  %-18s %-9s %s" % (n, rows[n]["state"],
                                       rows[n]["detail"][:54]), flush=True)
        except Exception as e:                                    # noqa: BLE001
            rows[n] = {"state": "FAILED", "how": "raised",
                       "detail": f"{type(e).__name__}: {str(e)[:130]}"}
            print("  %-18s FAILED  %s" % (n, str(e)[:60]), flush=True)
    for n, why in refused.items():
        rows[n] = {"state": "REFUSED", "how": "not registrable",
                   "detail": str(why)[:150]}
    # DISTINCT COMPONENTS CANNOT AGREE TO THE PIXEL.
    import collections as _c
    meas = [v for v in rows.values() if v["state"] == "MEASURED"]
    dup = [d for d, c in _c.Counter(v["detail"] for v in meas).items() if c > 1]
    if dup:
        for v in meas:
            v["state"] = "FAILED"
            v["how"] = "instrument: rows agreed to the pixel"
        print("  REFUSING: %d rows share a reading %s" % (len(meas), dup[:1]),
              flush=True)
    ok = sum(1 for v in rows.values() if v["state"] == "MEASURED")
    print("  RENDER CHECK: %d of %d components DRAW PIXELS" % (ok, len(comps)),
          flush=True)
    out = {"components": rows, "frames": frames, "rendered": ok,
           "attempted": len(comps)}
    RESULTS["render-check"] = out
    return out


@app.function(image=IMG, timeout=900,
              secrets=[modal.Secret.from_name("chatcut-oauth"),
                       modal.Secret.from_name("anthropic-api-key")])
def explain_refusal(name: str, use_old_props: str = ""):
    """Register ONE component and print the validator's WHOLE complaint.

    THE TRUNCATION WAS THE PROBLEM. Six components came back ABSENT with
    `validator refused` and a detail string cut off before the actual error
    — a failed measurement wearing a result's clothes, which is the family
    this lane has paid for repeatedly. This returns the full text, and takes
    an ALTERNATIVE property list so "did my change cause this?" is answered
    by running both, not by reasoning about which values look harmless.
    """
    tok = _access_token()
    reg = json.load(open("/craft/chatcut_registry.json", encoding="utf-8"))
    spec = reg["components"][name]
    props = json.loads(use_old_props) if use_old_props else spec["properties"]
    r = mcp_rpc(tok, "tools/call", {"name": "create_project", "arguments": {
        "name": f"refusal {name}", "compositionWidth": 1080,
        "compositionHeight": 1920, "fps": 30}}, 1)
    txt = "".join(c.get("text") or "" for c in
                  ((r.get("result") or {}).get("content") or []))
    pid = re.search(r"[0-9a-f]{8}-[0-9a-f-]{27}", txt).group(0)
    r = mcp_rpc(tok, "tools/call", {
        "name": "create_motion_graphic_from_code",
        "arguments": {"projectId": pid, "name": name, "code": spec["code"],
                      "width": 1080, "height": 1920, "durationInSeconds": 8,
                      "properties": props}}, 2)
    out = json.dumps(r, indent=1)
    print("  props supplied: %s" % ("OLD (from argument)" if use_old_props
                                    else "current registry"))
    print(out[:4000], flush=True)
    return out


@app.local_entrypoint()
def refusal(name: str, old_props_file: str = ""):
    """Print the full validator error for one component."""
    from require_detach import require_detach
    require_detach(why_not="one registration call, ~60s — a client drop costs "
                           "a minute, not a run")
    old = ""
    if old_props_file:
        import json as _j
        old = _j.dumps(_j.load(open(old_props_file))["components"][name]["properties"])
    explain_refusal.remote(name, old)


@app.local_entrypoint()
def rendercheck(props_file: str = ""):
    """One project per component, pixels diffed, no teardown."""
    from require_detach import require_detach
    require_detach("a per-component render check (18 components, ~18 min)")
    txt = open(props_file, encoding="utf-8").read() if props_file else ""
    r = component_render_check.remote(txt)
    rows = r["components"]
    import base64
    sheet_dir = os.path.join(_HERE, "sheet")
    os.makedirs(sheet_dir, exist_ok=True)
    for n, f in (r.get("frames") or {}).items():
        if isinstance(f, dict) and f.get("jpg_b64"):
            open(os.path.join(sheet_dir, n + ".jpg"), "wb").write(
                base64.b64decode(f["jpg_b64"]))
    json.dump(r["components"], open(os.path.join(sheet_dir, "rows.json"), "w"),
              indent=1)
    print("  frames written to %s" % sheet_dir)
    print("\n%-20s %-9s %s" % ("COMPONENT", "STATE", "EVIDENCE"))
    for n, v in sorted(rows.items()):
        print("%-20s %-9s %s" % (n, v["state"], (v.get("detail") or "")[:86]))
    print("\nDRAW PIXELS: %d of %d" % (r["rendered"], r["attempted"]))


@app.local_entrypoint()
def sweep(props_file: str = ""):
    """Run the wiring sweep and print the table. No render, no agent."""
    from require_detach import require_detach
    require_detach("a wiring sweep")
    txt = open(props_file, encoding="utf-8").read() if props_file else ""
    r = wiring_sweep.remote(txt)
    rows = r["components"]
    print("\n%-22s %-9s %s" % ("COMPONENT", "STATE", "EVIDENCE"))
    for n, v in sorted(rows.items()):
        print("%-22s %-9s %s" % (n, v["state"], v["detail"][:96]))
    print("\nRENDERED %d of %d attempted (baseline %sB)"
          % (r["rendered"], r["attempted"], r["baseline_bytes"]))


@app.local_entrypoint()
def main(clip_url: str = "", brief: str = "Cut this tighter and add one title.",
         run_id: str = "", wait: bool = False,
         model: str = "claude-sonnet-5", use_hands: bool = True,
         plan_file: str = "", think_tokens: int = 0,
         prestage_title: str = "", prestage_controls: str = "",
         prestage_titles: str = ""):
    if not clip_url:
        raise SystemExit("pass --clip-url")
    # THE PLAN IS READ HERE, ON THE MACHINE THAT OWNS IT, and passed as a
    # value. Mounting it would make the container's copy a second artifact that
    # can drift from the ledger it came from; a string argument cannot.
    plan_text = ""
    if plan_file:
        plan_text = open(plan_file, encoding="utf-8").read()
        if not plan_text.strip():
            raise SystemExit(f"plan file {plan_file} is EMPTY — refusing to "
                             f"run a plan-mode job with no plan, which would "
                             f"silently be an ordinary deciding run.")
        print(f"  PLAN            : {len(plan_text)} chars from {plan_file}")
    # A PRESIGNED URL IS A CLAIM WITH AN EXPIRY DATE ON IT. Run 2 of arm A was
    # launched eight minutes after its URL expired: the container booted, paid
    # for the image, authenticated, ran the preflight, and died on a 403 with
    # no result in the Dict. Nothing about the command said the URL was stale,
    # and an expired arm is indistinguishable from a crashed one until someone
    # reads the container log.
    #
    # The expiry is knowable BEFORE spending anything, so it is checked here.
    _exp = re.search(r"[?&]Expires=(\d+)", clip_url)
    _x_amz = re.search(r"X-Amz-Date=(\d{8}T\d{6}Z).*?X-Amz-Expires=(\d+)",
                       clip_url)
    _left = None
    if _exp:
        _left = int(_exp.group(1)) - int(time.time())
    elif _x_amz:
        _t = time.mktime(time.strptime(_x_amz.group(1), "%Y%m%dT%H%M%SZ"))
        _left = int(_t - time.timezone + int(_x_amz.group(2)) - time.time())
    if _left is None:
        print("  CLIP URL        : ABSENT expiry — cannot check staleness")
    elif _left <= 0:
        raise SystemExit(
            f"REFUSING TO LAUNCH: the clip URL expired {-_left}s ago. The "
            f"container would boot, authenticate, run the preflight and die on "
            f"a 403 with nothing in the results Dict. Re-mint it.")
    elif _left < 900:
        raise SystemExit(
            f"REFUSING TO LAUNCH: the clip URL expires in {_left}s and a run "
            f"takes 500-900s. It would die mid-job. Re-mint it.")
    else:
        print(f"  CLIP URL        : MEASURED  {_left}s of validity left")
    rid = run_id or f"run-{int(time.time())}"
    if wait:
        print(json.dumps(edit.remote(clip_url, brief, model=model, run_id=rid,
                                     use_hands=use_hands, plan=plan_text,
                                     think_tokens=think_tokens,
                                     prestage_title=prestage_title,
                      prestage_controls=prestage_controls,
                      prestage_titles=prestage_titles),
                         indent=1)[:6000])
        return
    # SPAWN, DO NOT WAIT. The result lands in the chatcut-results Dict, so the
    # answer survives a client that is signalled, disconnected, or simply gone.
    #
    # AND THAT IS ONLY HALF THE PROBLEM. `.spawn()` protects against the CLIENT
    # dying; it does NOT keep the APP alive. An ephemeral `modal run` stops its
    # app the moment this entrypoint returns — "Stopping app - local entrypoint
    # completed" — and the spawned call dies with it. The plan-first run was
    # lost exactly that way: spawned cleanly, app stopped one second later, and
    # the Dict read ABSENT fifteen minutes on.
    #
    # Round 58 recorded "--detach keeps the APP alive; it does not stop the
    # CLIENT cancelling" and the fix taken from it was `.spawn()`. Both halves
    # of that sentence are true and NEITHER MECHANISM COVERS THE OTHER'S
    # FAILURE. So this refuses rather than relying on anyone remembering which
    # half they are looking at.
    # ONE GUARD, SHARED. This lived here as an inline refusal and the OTHER
    # launcher — agentic_editor_app.py::main — did not have it, so on
    # 2026-09-14 that one ran 468s, lost its client and stopped mid-ruling.
    # A copy in one file is not a rule; it is a rule one file happens to know.
    from require_detach import require_detach
    require_detach("a spawned ChatCut edit")
    call = edit.spawn(clip_url, brief, model=model, run_id=rid,
                      use_hands=use_hands, plan=plan_text,
                      think_tokens=think_tokens,
                      prestage_title=prestage_title,
                      prestage_controls=prestage_controls,
                      prestage_titles=prestage_titles)
    print(f"SPAWNED run_id={rid} call={call.object_id}")
    print(f"read it with:  modal run chatcut_read_result.py --run-id {rid}")
