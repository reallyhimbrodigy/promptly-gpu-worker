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
import base64
import json
import math
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
    # opencv PINNED BELOW 5. The unpinned install resolved to 5.0.0.93, which
    # REMOVED the legacy Caffe importer: `cv2.dnn has no attribute
    # readNetFromCaffe`, and HOP 6 died on the line that loads production's
    # res10 model. Production's image pins 4.x, so an unpinned copy of its
    # detector was always going to drift away from the weights it was written
    # for. Same class as copying wget with its surroundings left behind.
    .pip_install("pillow", "numpy", "opencv-python-headless<5")
    # THE REAL DETECTORS, NOT INVENTED ZONES. The sweep's face and burned-text
    # legs were judging against constants I made up — a face zone of 0.04-0.34
    # that reported "30% overlap" for every title, and an edge-density scan
    # whose min-to-max union covered 0.284-0.667 so everything overlapped. Two
    # guessed bands, after a guessed caption band had already let the card ship
    # on top of the captions. This repo has both detectors already: the res10
    # SSD face detector handler.py has used since forever, and burned_text.py's
    # EAST text-region detector, calibrated with its own thresholds and
    # fail-safe to None. Mirrors modal_app.py's wget block exactly.
    .run_commands(
        "mkdir -p /models/face_detector /models/east",
        # curl, NOT wget. modal_app.py's block uses wget because THAT image
        # apt-installs it; this base has curl only, and the build died at
        # "wget: not found" — a command copied with its surroundings left
        # behind. -fsSL so a redirect body or a 404 page cannot land as a
        # "model" that then fails at runtime as a missing detector.
        "curl -fsSL -o /models/face_detector/deploy.prototxt "
        "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/"
        "face_detector/deploy.prototxt",
        "curl -fsSL -o /models/face_detector/res10_300x300_ssd_iter_140000.caffemodel "
        "https://raw.githubusercontent.com/opencv/opencv_3rdparty/"
        "dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel",
        "curl -fsSL -o /models/east/frozen_east_text_detection.pb "
        "https://d1iax8jos987n3.cloudfront.net/models/east/"
        "frozen_east_text_detection.pb",
        # VERIFY THEY LANDED. A truncated or HTML fetch must fail at BUILD, not
        # silently at runtime where the detector would return None and the leg
        # would read ABSENT for a reason nobody could see.
        "test $(stat -c%s /models/east/frozen_east_text_detection.pb) -gt 90000000",
        "test $(stat -c%s /models/face_detector/"
        "res10_300x300_ssd_iter_140000.caffemodel) -gt 5000000",
    )
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
    .add_local_file(os.path.join(_HERE, "chatcut_registry_baked.json"),
                    "/craft/chatcut_registry_baked.json", copy=True)
    # THE CATALOGUE — the library the agent SEES before it chooses. A bare enum
    # is a list of words: two rounds read 1-of-29 selected and StatCard x4
    # because the prefix named StatCard and nothing else. One sheet, 26
    # components, labelled with their size band; the JSON carries the WHEN
    # condition each answers, the 37 selection arrows, and props known to render
    # because they are the props that produced the still.
    # THE SHEET THE AGENT SEES MUST BE THE SHEET THAT WAS PROVEN. This mounted
    # `component_sheet.png` — a file from the day before, built before the bake
    # and before the caption styles. The inventory built from actual renders is
    # sheet/INVENTORY.png, and it was never wired: the agent was choosing from
    # a stale picture while the proven one sat on disk beside it.
    .add_local_file(os.path.join(_HERE, "sheet", "INVENTORY.png"),
                    "/craft/component_sheet.png", copy=True)
    .add_local_file(os.path.join(_HERE, "sheet", "sheet.json"),
                    "/craft/component_sheet.json", copy=True)
    .add_local_file(os.path.join(_HERE, "chatcut_catalogue.json"),
                    "/craft/chatcut_catalogue.json", copy=True)
    .add_local_file(os.path.join(_HERE, "turn_clock.py"),
                    "/root/turn_clock.py", copy=True)
    .add_local_file(os.path.join(_HERE, "verify_chain.py"),
                    "/root/verify_chain.py", copy=True)
    .add_local_file(os.path.join(_HERE, "burned_text.py"),
                    "/root/burned_text.py", copy=True)
    .add_local_file(os.path.join(_HERE, "face_bands.py"),
                    "/root/face_bands.py", copy=True)
    # THE MEASURED BANDS THEMSELVES. verify_chain reads sheet/rows.json
    # relative to its own directory, and that file was never mounted — so in
    # the container `measured_bands()` returned {} and EVERY band fell through
    # to the whole frame. HOP 6 then reported the card at 0.150-1.150 (off the
    # bottom of a 0-1 frame) and every placement as occupying all three bands,
    # which is why it failed five of them. A clean zero from a reader that
    # found no input, for the fourth time today.
    .add_local_file(os.path.join(_HERE, "sheet", "rows.json"),
                    "/root/sheet/rows.json", copy=True)
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
# ChatCut's export delays the audio by this much, measured on a NO-EDIT round
# trip (upload a file, export it untouched) across four exports. Set to 0 to
# ship uncompensated — hop 7 then reports the raw offset instead of ~0.
CHATCUT_AUDIO_LEAD_MS = 42


NEEDED_TOOLS = [
    # SIX, NOT TWENTY-FIVE. The plan now carries the project, the assets, the
    # sound ids, the item references and the review frames, so the agent
    # creates nothing, imports nothing, searches nothing and discovers nothing.
    # Every tool it was offered for those jobs was a tool it could spend a turn
    # on. What is left is: place, look, fix, deliver.
    "edit_item",          # place, and fix by `updates` on the one revision
    "preview_timeline",   # look at the composed frames
    "inspect_item",       # a named defect may need one item's full state
    "edit_asset",         # ...or a property on the asset behind it
    "submit_export",      # deliver
    "track_export",       # and report where it got to
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
    # ── PRE-COMPENSATE ChatCut's AUDIO DELAY ────────────────────────────────
    # MEASURED, NOT INFERRED. A file uploaded and exported with NO EDITS comes
    # back with its audio +42ms late — identical to a fully-edited run, so the
    # offset lives entirely in their import/export and nothing we do to a plan
    # can touch it. The edit lists name the mechanism: every file in the chain
    # declares an AAC priming skip except theirs.
    #     source            video 0                  audio 2112 @44.1k = 47.9ms
    #     what we upload    video 1024 @15360 = 66.7 audio 1024 @44.1k = 23.2ms
    #     their export      video 1024 @15360 = 66.7 audio 0  — none declared
    # Our own transcode measures 0ms against the source, so this is not ours to
    # fix; it is ours to CORRECT FOR, because the user gets the delivered file
    # either way and a correct one is the requirement.
    #
    # THE COMPENSATION IS MEASURED ON EVERY RUN (hop 7) rather than trusted. A
    # hard-coded shift with nothing watching it is precisely what breaks in
    # silence the day ChatCut fixes their end — at which point the check fails
    # LOUDLY on the over-correction and names this constant.
    if source_path and os.path.exists(source_path) and CHATCUT_AUDIO_LEAD_MS:
        _comp = "/work/source_compensated.mp4"
        _r = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", source_path,
             "-itsoffset", "-%.3f" % (CHATCUT_AUDIO_LEAD_MS / 1000.0),
             "-i", source_path, "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
             "-movflags", "+faststart", _comp],
            capture_output=True, text=True, timeout=900)
        if _r.returncode == 0 and os.path.getsize(_comp) > 10000:
            print("  AUDIO LEAD      : MEASURED  shifted %dms earlier before "
                  "upload to cancel ChatCut's export delay"
                  % CHATCUT_AUDIO_LEAD_MS, flush=True)
            source_path = _comp
        else:
            # NAMED, NOT SILENT. An uncompensated upload is a deliverable with
            # 42ms of lip-sync error; saying so beats shipping it quietly.
            print("  AUDIO LEAD      : FAILED  could not pre-compensate (%s) — "
                  "the delivered audio will be ~%dms late"
                  % ((_r.stderr or "")[-120:], CHATCUT_AUDIO_LEAD_MS), flush=True)

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
    # THE BAKED REGISTRY, AND THE RIGHT LEVEL OF IT. This read the file and
    # iterated it directly — but the file is {"components": ..., "refused": ...},
    # so every iteration handed a two-key envelope where a component was
    # expected. It also read the UNBAKED registry, whose list components carry
    # their content as an empty string. Both fixed here, with the same accessor
    # the render check uses, so the thing that is PROVEN to draw is the thing
    # that gets staged.
    try:
        _bp = "/craft/chatcut_registry_baked.json"
        _rp = _bp if os.path.exists(_bp) else "/craft/chatcut_registry.json"
        _raw = json.load(open(_rp, encoding="utf-8"))
        _reg = _raw.get("components") or _raw
        print(f"  REGISTRY SOURCE : {_rp}  ({len(_reg)} components)", flush=True)
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
            _ov = _c.get("overrides") or {}
            _v = _find(_r, "validation") or {}
            if _v.get("errors"):
                reg_failed[_n] = _v["errors"][:2]
            else:
                # THE SCALAR HALF TRAVELS WITH THE COMPONENT. Structured
                # content is already inside the code; the overrides are what
                # propertyOverrides is for, and carrying them here means the
                # agent never has to re-derive them from a fixture file.
                registered[_n] = {"assetId": _find(_r, "assetId"),
                                  "overrides": _ov} if _ov else _find(_r, "assetId")
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
    "errors and you will have looked at nothing. Download first, then read.\n\n"
    # ONE SHEET, NOT ONE READ PER FRAME. Measured on run-1789443426: 13 of 24
    # tool calls were `Read` of a single frame — twelve turns spent on the same
    # review an earlier run did in one, because nothing said to tile. A
    # contact sheet is also the BETTER instrument: the defects this turn is
    # for — a collision, a band drifting, a title landing on the wrong moment —
    # are comparisons ACROSS frames, and frames read one at a time are compared
    # from memory.
    "DOWNLOAD THEM ALL, TILE THEM INTO ONE SHEET, READ THE SHEET ONCE. Not one "
    "Read per frame: twelve frames read one at a time is twelve turns spent on "
    "the review, and a collision or a drifting band is a comparison ACROSS "
    "frames that a sheet shows you and a sequence of single frames does not.\n"
    "    mkdir -p /work/frames && cd /work/frames\n"
    "    curl -fsSL -o f0.jpg \"<uri 1>\"   # one curl per uri, all in ONE Bash\n"
    "    curl -fsSL -o f1.jpg \"<uri 2>\"\n"
    "    ffmpeg -v error -i f0.jpg -i f1.jpg ... -filter_complex \\\n"
    "      \"[0][1]...hstack=inputs=N,scale=1600:-1\" -frames:v 1 sheet.png\n"
    "    Read /work/frames/sheet.png            # ONE Read\n"
    "Use -fsSL: without it curl writes a redirect body and exits 0, which is a "
    "file that is not a frame. If a curl fails, say so — a sheet with a missing "
    "tile is a frame you did not look at, not a frame that was fine.\n\n")

TWO_TURN_LOOP = (
    "THE LOOP IS TWO PASSES. A third is a failure state, not a budget.\n\n"
    "  PASS 1 — YOU WATCH THE SOURCE, THEN PLACE EVERYTHING IN ONE BATCH.\n"
    "  Everything you need is in this message: the component inventory as "
    "pictures, the source as a sequence of frames, the transcript against "
    "them, and the plan. You look nothing up. Decide every placement — which "
    "component, where it sits, when it runs — and send them in the calls the "
    "plan names (usually one for the items, a second for any EFFECT, because "
    "an effect names an item that must already exist).\n\n"
    "  THEN YOUR TURN ENDS. Do not preview, do not fetch a frame, do not read "
    "a file, do not check your work. The edit will be RENDERED AND SENT TO "
    "YOU as the next message. Anything you do between your last placement and "
    "that message is a turn spent on something you are about to be given.\n\n"
    "  PASS 2 — YOU WATCH THE EDIT, THEN FIX IT IN ONE BATCH. The next "
    "message carries frames of your timeline with everything on it. Judge the "
    "COMPOSED PICTURE — tool results cannot show you a collision. Fix what is "
    "wrong in ONE edit_item call: a graphic colliding with another or with "
    "the captions, something illegible or off-frame, something on the "
    "speaker's face, a title on the wrong moment, wrong size, drift. If it is "
    "right, submit the export and stop.\n\n"
    "  PASS 3 — ONLY ON A DEFECT YOU CAN NAME. If you take one, your final "
    "message must name the defect, the frame you saw it in, and what you "
    "changed. Unnamed, it is the same as not taking it: the run reports the "
    "third pass as UNJUSTIFIED and the edit is judged without it.\n\n"
    "WHY THE BATCHES. Each pass is a model turn with the whole context behind "
    "it. Placing one item at a time to watch it land spends a turn per item "
    "and tells you nothing a batch would not — `edit_item` commits a batch "
    "atomically and rolls the whole batch back on one failure, so a batch that "
    "fails tells you something a half-built timeline never can.\n\n")


def _mcp_call(tok, name, args, expect=None):
    """One ChatCut tool call at module level, for the harness's own checks.

    IT RAISES RATHER THAN RETURNING THE ENVELOPE. The first version fell back
    to the raw result when it could not parse the text block — so
    `preview_timeline` came back as an envelope, `.get("timeline")` was None,
    `entries` was EMPTY, and hop 3 reported all twelve adds as never placed on
    a timeline that demonstrably held sixteen. A FALSE RED, which is the same
    failure as a false green wearing the other sign: the instrument failed and
    blamed the thing it was measuring.

    So `expect` names the key the caller needs, and its absence is an error
    that says what DID come back instead of a zero that reads like a finding.
    Content blocks may also arrive as `resource`/`json` rather than `text`.
    """
    r = mcp_rpc(tok, "tools/call", {"name": name, "arguments": args}, 900)
    if r.get("error"):
        raise RuntimeError("%s failed: %s" % (name, r["error"]))
    out = r.get("result") or {}
    parsed = None
    # `structuredContent` FIRST. MCP returns the payload three ways and this
    # reader only knew one: the last run came back with keys
    # ['_meta', 'content', 'structuredContent'] and no parseable text block, so
    # hop 3 could not read a timeline that held sixteen entries. The previous
    # version of this bug reported "12 adds never became an item"; this one
    # said "returned nothing this reader could use (no 'timeline'). Keys seen:
    # [...]" — which is the whole reason the message carries what it got.
    if isinstance(out.get("structuredContent"), dict):
        sc = out["structuredContent"]
        parsed = sc.get("result") if isinstance(sc.get("result"), dict) else sc
    for c in ([] if parsed is not None else (out.get("content") or [])):
        t = c.get("text")
        if not t and isinstance(c.get("resource"), dict):
            t = c["resource"].get("text")
        if not t and isinstance(c.get("json"), (dict, list)):
            parsed = c["json"]
            break
        if t and t.strip().startswith("{"):
            try:
                parsed = json.loads(t)
                break
            except Exception:                                     # noqa: BLE001
                continue
    # EVERY BLOCK, NOT JUST THE JSON ONE. Looked at rather than guessed:
    #   preview_timeline returns a JSON block AND a separate resource_link
    #     block carrying the frame URL — the URL is not in the JSON at all,
    #     which is why four different walkers found nothing and HOP 5 kept
    #     reporting the composition unrenderable.
    #   inspect_item returns PLAIN TEXT, not JSON — a formatted report whose
    #     `propertyOverrides: {...}` line is a string. Walking it for a
    #     `propertyOverrides` KEY could never succeed, which is why HOP 4 said
    #     the card carried none of its four overrides while inspect_item was
    #     printing all four marked `(override)`.
    # So the envelope always travels with the raw text and any links beside it.
    _blocks = out.get("content") or []
    _text = "".join(c.get("text") or "" for c in _blocks if isinstance(c, dict))
    _links = [c.get("uri") for c in _blocks
              if isinstance(c, dict) and isinstance(c.get("uri"), str)]
    _links += [c["resource"]["uri"] for c in _blocks
               if isinstance(c, dict) and isinstance(c.get("resource"), dict)
               and isinstance(c["resource"].get("uri"), str)]
    if parsed is None and isinstance(out, dict) and (
            expect is None or expect in out):
        parsed = out
    if parsed is None and (_text or _links):
        parsed = {}
    if isinstance(parsed, dict):
        parsed.setdefault("_text", _text)
        parsed.setdefault("_links", _links)
    if parsed is None or (expect is not None and expect not in parsed):
        raise RuntimeError(
            "%s returned nothing this reader could use%s. Keys seen: %s. "
            "First 240 chars: %r"
            % (name, (" (no %r)" % expect) if expect else "",
               sorted(parsed or out)[:12] if isinstance(parsed or out, dict)
               else type(parsed or out).__name__,
               json.dumps(parsed if parsed is not None else out)[:240]))
    return parsed


def verify_hops_3_and_4(tok, stage, plan):
    """Read the placements back: did every add become an item, carrying what
    the plan named?

    HOP 3  every add BECAME AN ITEM. `items_added` counted adds SENT, and
           ChatCut resolves an id PREFIX and returns ok, so a send was never a
           landing.
    HOP 4  every item ARRIVED CARRYING the ruling — the asset the plan named
           and the propertyOverrides it specified. That is where the card died:
           registered into an asset with no card properties, placed, counted,
           and green.

    THREE STATES. A check that could not run is FAILED or ABSENT and says
    which; neither is a pass.
    """
    import sys as _sys
    _sys.path.insert(0, "/root")
    import verify_chain as vc
    res = {"hop3": {"state": "ABSENT", "why": "not attempted"},
           "hop4": {"state": "ABSENT", "why": "not attempted"}, "detail": []}
    if not (plan and stage):
        res["hop3"]["why"] = res["hop4"]["why"] = "no plan or no prestage"
        return res
    man = vc.plan_manifest(plan)
    pid = stage["projectId"]
    try:
        tl = _mcp_call(tok, "preview_timeline",
                       {"projectId": pid, "views": ["timeline"], "limit": 100},
                       expect="timeline")
        entries = ((tl.get("timeline") or {}).get("entries") or [])
        _total = ((tl.get("timeline") or {}).get("totalEntries"))
    except Exception as e:                                        # noqa: BLE001
        res["hop3"] = {"state": "FAILED",
                       "why": "could not read the timeline: %s" % e}
        return res

    items = [e for e in entries if e.get("kind") == "item"]
    miss3 = vc.hop3_placed(man, entries)
    if miss3 and not items:
        # NOT A PLACEMENT FAILURE — A READ FAILURE. Every add missing and zero
        # items read is the instrument, not the edit, and calling it FAILED
        # here would blame the run for the reader's silence.
        res["hop3"] = {"state": "FAILED",
                       "why": "the timeline read returned ZERO items (%s total "
                              "entries) — this is the reader failing, not the "
                              "placements" % _total}
        res["hop4"] = {"state": "ABSENT",
                       "why": "hop 3 could not read the timeline"}
        return res
    res["hop3"] = {
        "state": "FAILED" if miss3 else "MEASURED",
        # THE DENOMINATOR IS IN THE MESSAGE. Without it, "12 adds never
        # became an item" cannot be told apart from "the reader saw nothing",
        # which is exactly how the false red read as a placement failure.
        "why": ("%d of %d add(s) never became an item — the timeline read "
                "returned %d item(s) of %s total: %s"
                % (len(miss3),
                   len([r for r in man if r["type"] != "effect"]),
                   len(items), _total,
                   "; ".join("CALL %s adds[%s] %s"
                             % (r["call"], r["slot"], w)
                             for r, w in miss3))
                if miss3 else
                "%d planned add(s), %d item(s) on the timeline"
                % (len([r for r in man if r["type"] != "effect"]), len(items)))}

    # TWO PLACEMENTS CAN START ON THE SAME FRAME. The card and the title that
    # carries it both begin at 526, and keying by frame alone kept the FIRST —
    # so hop 4 inspected Title 07, found no overrides on it, and reported the
    # CARD's four overrides as missing. The evidence line is what caught it:
    # "Asset: [62be58ebc6] Title 0...". Match the asset the plan named, not
    # merely the frame it named.
    by_frame = {}
    for it in items:
        f = (it.get("timelineRange") or {}).get("fromFrame")
        if f is not None:
            by_frame.setdefault(f, []).append(it)

    def _pick(row):
        """The item at this row's frame whose ASSET is the one the plan named.

        AUDIO BY CONTAINMENT, NOT BY START. `fromFrame` is an ANCHOR: edit_item
        shifts the item so the sound's anchor lands there, so a vine-boom
        anchored at 526 is an item starting at 518 and no item starts at the
        row's frame at all. Hop 3 learned this; this picker had not, so hop 4
        reported 'no item at frame 526 to carry it' for a sound that was on the
        timeline. The same semantics, biting a third reader.
        """
        if row["type"] == "audio":
            return next((it for it in items
                         if it.get("itemType") == "audio"
                         and (it.get("timelineRange") or {}).get("fromFrame", 0)
                         <= row["from"] <
                         (it.get("timelineRange") or {}).get("toFrame", 0)), None)
        cands = by_frame.get(row["from"]) or []
        if len(cands) == 1:
            return cands[0]
        want = (row.get("asset") or "").lower()
        for it in cands:
            nm = str(((it.get("asset") or {}).get("name") or "")).lower()
            if nm and nm in want:
                return it
        # a card is the row with numeric overrides; prefer an item whose asset
        # name is not a plain "Title NN" when we are looking for one
        if (row.get("overrides") or {}).get("value") is not None:
            for it in cands:
                nm = str(((it.get("asset") or {}).get("name") or ""))
                if not nm.lower().startswith("title"):
                    return it
        return cands[0] if cands else None

    # KEYED BY THE ROW, NOT THE FRAME. Keying by frame collapsed again: the
    # title, the card AND the sound effect all name frame 526, so the LAST row
    # written won and hop 4 inspected whichever that was. A frame does not
    # identify a placement — that was the whole lesson of the previous fix, and
    # the dict I built to apply it repeated the mistake one line later.
    by_row = {}
    for r in man:
        it = _pick(r)
        if it is not None:
            by_row[(r["call"], r["slot"])] = it
    by_from = by_row

    def _find_po(o, item_id):
        """The overrides on THE ITEM, not the first ones in the tree.

        The first version returned the first `propertyOverrides` key a
        depth-first walk met, and reported that slot 8 carried none of its four
        overrides on a run where the agent had demonstrably sent
        {"value": 5, "label": ..., "suffix": " MINUTES", "offsetY": 288}. A
        reader taking the first match — the same shape as every other reader
        that broke today. Match the node that IS the item, and only fall back
        to a non-empty match elsewhere.
        """
        hit = [None]

        def walk(o, depth=0):
            if isinstance(o, dict):
                if str(o.get("id") or "").startswith(str(item_id)[:8]) \
                        and "propertyOverrides" in o:
                    hit[0] = o["propertyOverrides"]
                    return True
                for v in o.values():
                    if walk(v, depth + 1):
                        return True
            elif isinstance(o, list):
                for v in o:
                    if walk(v, depth + 1):
                        return True
            return False

        if walk(o):
            return hit[0]

        # no id-matched node: take the first NON-EMPTY overrides rather than
        # the first key, so an empty asset-level dict cannot mask the item's.
        best = [None]

        def walk2(o):
            if isinstance(o, dict):
                po = o.get("propertyOverrides")
                if isinstance(po, dict) and po and best[0] is None:
                    best[0] = po
                for v in o.values():
                    walk2(v)
            elif isinstance(o, list):
                for v in o:
                    walk2(v)
        walk2(o)
        return best[0]

    # overrides live on the ITEM and the timeline view does not carry them, so
    # the rows that name any are inspected individually. There is normally one.
    for r in man:
        _key = (r["call"], r["slot"])
        if not (r.get("overrides") and _key in by_from):
            continue
        try:
            det = _mcp_call(tok, "inspect_item",
                            {"projectId": pid,
                             "itemId": by_from[_key]["id"]})
            _po = _find_po(det, by_from[_key]["id"])
            if not _po:
                # inspect_item is a TEXT report. Its own line is authoritative:
                #   propertyOverrides: {"label":"…","value":5,…}
                _txt = str((det or {}).get("_text") or "")
                _m = re.search(r"propertyOverrides:\s*(\{.*?\})\s*$",
                               _txt, re.M)
                if _m:
                    try:
                        _po = json.loads(_m.group(1))
                    except Exception:                             # noqa: BLE001
                        _po = None
                if not _po:
                    # THE OTHER SHAPE THE SAME REPORT PRINTS. Above the
                    # Properties block, inspect_item lists every effective
                    # prop and marks the ones that are not defaults:
                    #     value=5 (override)
                    #     suffix=" MINUTES" (override)
                    # That is the same fact in a form this reader can take, and
                    # taking both means one of them changing does not blind the
                    # hop.
                    _po = {}
                    for _k2, _v2 in re.findall(
                            r"^\s*(\w+)=(.*?)\s*\(override\)\s*$",
                            _txt, re.M):
                        try:
                            _po[_k2] = json.loads(_v2)
                        except Exception:                         # noqa: BLE001
                            _po[_k2] = _v2.strip('"')
                    _po = _po or None
            if _po is None:
                res["hop4"] = {
                    "state": "FAILED",
                    # CARRY THE EVIDENCE. Three times today a failure
                    # message without its input cost a whole run to diagnose:
                    # "12 adds never became an item" (the reader saw nothing),
                    # "could not render the frame" (the URL was in another
                    # block), and this. A message that cannot say what it read
                    # makes the next run the debugger.
                    "why": "could not read the overrides off the item at frame "
                           "%s — inspect_item gave neither a JSON node, a "
                           "`propertyOverrides:` line, nor any `(override)` "
                           "marker. UNCHECKED. First 240 chars of what it did "
                           "return: %r"
                           % (r["from"], str((det or {}).get("_text") or "")[:240])}
                return res
            by_from[_key] = dict(by_from[_key], propertyOverrides=_po)
        except Exception as e:                                    # noqa: BLE001
            res["hop4"] = {"state": "FAILED",
                           "why": "could not inspect the item at frame %s: %s"
                                  % (r["from"], e)}
            return res

    # hop4_carries indexes by frame. Only rows that NAME overrides are checked
    # for them, and at most one row per frame does, so a frame-keyed map built
    # from those rows alone is unambiguous — where the general map was not.
    _for_hop4 = {}
    for r in man:
        k = (r["call"], r["slot"])
        if k in by_row:
            _for_hop4.setdefault(r["from"], by_row[k])
        if r.get("overrides") and k in by_row:
            _for_hop4[r["from"]] = by_row[k]
    bad4 = vc.hop4_carries(man, _for_hop4)
    res["detail"] = ["%-8s slot%-3s frame %-5s %s"
                     % ("MISSING" if any(b[0] is r for b in bad4) else "ok",
                        r["slot"], r["from"], (r.get("asset") or "")[:44])
                     for r in man if r["type"] != "effect"]
    res["hop4"] = {
        "state": "FAILED" if bad4 else "MEASURED",
        "why": ("%d placement(s) did not carry the ruling: %s"
                % (len(bad4), "; ".join("slot%s %s" % (r["slot"], w)
                                        for r, w in bad4))
                if bad4 else
                "every item carries the asset and the overrides the plan named")}
    return res


def _gray(path, w=270, h=480):
    """One frame as raw 8-bit gray at a fixed size. None if it cannot be read."""
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf",
         "scale=%d:%d,format=gray" % (w, h), "-frames:v", "1",
         "-f", "rawvideo", "-"], capture_output=True, timeout=120)
    if r.returncode != 0 or len(r.stdout or b"") != w * h:
        return None
    return r.stdout


def _fetch(uri, path):
    import urllib.request as _u
    try:
        with _u.urlopen(uri, timeout=180) as resp, open(path, "wb") as fh:
            fh.write(resp.read())
        return os.path.getsize(path) > 2000
    except Exception:                                             # noqa: BLE001
        return False


def _chain_items(tok, stage):
    """The timeline's items, for hop 5. ABSENT rather than [] on failure, so a
    read that did not happen cannot read as a composition with nothing in it."""
    try:
        tl = _mcp_call(tok, "preview_timeline",
                       {"projectId": stage["projectId"], "views": ["timeline"],
                        "limit": 100}, expect="timeline")
        return [e for e in ((tl.get("timeline") or {}).get("entries") or [])
                if e.get("kind") == "item"]
    except Exception:                                             # noqa: BLE001
        return None


def verify_hop5_composition(tok, stage, plan, items):
    """HOP 5 — no frame ships with two placements' pixels on top of each other.

    THIS IS COMPOSED-AGAINST-COMPOSED, which is why it works where the earlier
    attempt did not. That one compared a placement's band against the SOURCE
    frame and was defeated by the zoom: `shape: "payoff"` ramps the
    magnification, so a fixed-scale comparison never registers and an 11.75%
    residual swamped every overlay. Here the two frames are renders of the SAME
    composition with ONE TRACK HIDDEN — identical geometry, identical zoom — so
    the difference between them is exactly that track's pixels. No registration,
    no bands, no guessing.

    ONE PREVIEW PER TRACK, not per pair: with N overlay tracks it is N+1
    renders and every pairwise intersection comes out of those.

    AND IT IS A GATE. A frame carrying two placements over each other fails the
    run. A measurement that could not be taken is ABSENT and also fails — the
    whole point is that nothing ships unchecked.
    """
    import sys as _sys
    _sys.path.insert(0, "/root")
    import verify_chain as vc
    out = {"state": "ABSENT", "why": "not attempted", "detail": []}
    if not (plan and stage and items):
        out["why"] = "no plan, prestage or items"
        return out
    pid = stage["projectId"]
    man = vc.plan_manifest(plan)

    # the frames worth checking: where two or more overlay items coincide
    ov = [it for it in items
          if (it.get("trackAlias") or "") not in ("V1", "A1")]
    if len(ov) < 2:
        return {"state": "MEASURED", "why": "fewer than two overlay items — "
                                            "nothing can collide", "detail": []}
    tracks = sorted({it.get("trackId") for it in ov if it.get("trackId")})
    best, bestn = None, 0
    for f in range(0, max((it.get("timelineRange") or {}).get("toFrame", 0)
                          for it in ov), 8):
        n = sum(1 for it in ov
                if (it.get("timelineRange") or {}).get("fromFrame", 0) <= f
                < (it.get("timelineRange") or {}).get("toFrame", 0))
        if n > bestn:
            best, bestn = f, n
    if best is None or bestn < 2:
        return {"state": "MEASURED", "why": "no frame carries two overlays",
                "detail": []}

    os.makedirs("/work/hop5", exist_ok=True)

    def shot(tag):
        # NO `expect` HERE. The viewer payload's key is not "viewer" and
        # demanding it made _mcp_call raise, which HOP 5 reported as "could
        # not render the all-visible frame" — the reader's own strictness
        # showing up as a composition that could not be checked. What this
        # call actually needs is A URL, so that is what it asserts, and a
        # response with none names the keys it did get.
        pv = _mcp_call(tok, "preview_timeline",
                       {"projectId": pid, "views": ["viewer"],
                        "viewerFrames": [best]})
        uris = list(pv.get("_links") or []) if isinstance(pv, dict) else []

        def walk(o):
            # ANY http STRING, not only the two keys I guessed. The response
            # carries a `viewer` node — the keys it reported were
            # ['editorUrl','projectId','state','viewer','views'] — and the frame
            # URL inside it is not under `uri` or `url`, so the walker found
            # nothing and HOP 5 reported the composition as unrenderable. The
            # editorUrl/projectId strings are excluded by name, since those are
            # links to the project rather than to a frame.
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("editorUrl", "projectId", "browserHandoff"):
                        continue
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
            elif isinstance(o, str) and o.startswith("http") \
                    and ("render" in o or ".jpg" in o or ".png" in o):
                uris.append(o)
        walk(pv)
        if not uris:
            out["detail"].append(
                "preview_timeline returned no frame URL; keys: %s"
                % (sorted(pv)[:10] if isinstance(pv, dict) else type(pv).__name__))
            return None
        p2 = "/work/hop5/%s.jpg" % tag
        return p2 if _fetch(uris[0], p2) else None

    try:
        base = shot("all")
        g_all = _gray(base) if base else None
        if g_all is None:
            out["why"] = ("could not render the all-visible frame at %d — the "
                          "composition is UNCHECKED" % best)
            return out
        masks = {}
        for t in tracks:
            _mcp_call(tok, "edit_track", {"projectId": pid, "action": "update",
                                          "trackId": t,
                                          "json": json.dumps({"hidden": True})})
            try:
                p3 = shot("no_%s" % t[:8])
                g = _gray(p3) if p3 else None
            finally:
                _mcp_call(tok, "edit_track",
                          {"projectId": pid, "action": "update", "trackId": t,
                           "json": json.dumps({"hidden": False})})
            if g is None:
                out["why"] = ("could not render with track %s hidden — the "
                              "composition is UNCHECKED" % t[:8])
                return out
            masks[t] = bytes(1 if abs(g_all[i] - g[i]) > 24 else 0
                             for i in range(len(g_all)))
        # THE JUDGMENT LIVES IN verify_chain SO IT CAN BE PROVEN WITHOUT A
        # RENDER. A gate whose decision only runs inside a Modal container,
        # against live pixels, can only ever be tested by spending a run — and
        # a gate that has only ever passed is untested.
        hits = vc.masks_overlap(masks)
        for _a, _b, _n, _f in [(t1, t2, None, None) for i, t1 in
                               enumerate(tracks) for t2 in tracks[i + 1:]]:
            m1, m2 = masks[_a], masks[_b]
            _both = sum(1 for k in range(len(m1)) if m1[k] and m2[k])
            _area = min(sum(m1), sum(m2)) or 1
            out["detail"].append(
                "frame %d  %s vs %s  %d px shared (%.1f%% of the smaller)"
                % (best, _a[:8], _b[:8], _both, _both / float(_area) * 100))
        out["state"] = "FAILED" if hits else "MEASURED"
        out["why"] = (
            "%d pair(s) overlap at frame %d: %s"
            % (len(hits), best,
               "; ".join("%s/%s share %d px (%.0f%% of the smaller)"
                         % (a[:8], b[:8], n, f * 100) for a, b, n, f in hits))
            if hits else
            "%d overlay track(s) checked at frame %d, none share pixels"
            % (len(tracks), best))
    except Exception as e:                                        # noqa: BLE001
        out["state"] = "FAILED"
        out["why"] = "%s: %s — the composition is UNCHECKED" % (type(e).__name__, e)
    return out


def verify_hop6_clear(plan, source="/work/source.mp4"):
    """HOP 6 — nothing sits on the speaker's face or on the source's own text.

    REAL DETECTORS, NOT INVENTED ZONES. The sweep's first attempt at these two
    legs judged against constants I made up: a face zone of 0.04-0.34 that
    reported "30% overlap" for every title, and an edge-density text scan whose
    min-to-max union covered 0.284-0.667 so everything overlapped. Both were
    guesses, and a guessed band had already let the card ship on top of the
    captions.

    This repo had both answers the whole time — the res10 SSD face detector
    handler.py has used for months, and burned_text.py's EAST text-region
    detector with its own calibrated thresholds. Their constants are copied
    verbatim and pinned by smoke_bands_match_production.py.

    THREE STATES, and ABSENT FAILS. A detector that could not load returns None
    and this reports ABSENT — because "we could not look" must not read the
    same as "nothing is in the way", which is the whole lesson of the alpha
    guard.
    """
    import sys as _sys
    _sys.path.insert(0, "/root")
    import verify_chain as vc
    out = {"state": "ABSENT", "why": "not attempted", "detail": []}
    if not (plan and os.path.exists(source)):
        out["why"] = "no plan or no source on disk"
        return out
    man = vc.plan_manifest(plan)
    meas = vc.measured_bands()
    vis = [r for r in man if r["type"] == "motion-graphic" and r["from"] is not None]
    if not vis:
        return {"state": "MEASURED", "why": "no visual placements", "detail": []}

    try:
        import face_bands as fb
        import burned_text as bt
    except Exception as e:                                        # noqa: BLE001
        out["why"] = "detectors could not be imported (%s) — UNCHECKED" % e
        return out

    # sample at each placement's own settled moment, not on a fixed grid
    ts = sorted({round((r["from"] + min(12, (r["dur"] or 0) // 2)) / 30.0, 2)
                 for r in vis})
    traj = fb.detect_face_positions(source, ts)
    if traj is None:
        out["why"] = ("the face detector could not load (cv2 or the model is "
                      "missing) — the face leg is UNCHECKED, not clear")
        return out
    nfound = sum(1 for p in traj if p.get("found"))
    burned = None
    try:
        burned = bt.detect_burned_in_text(source)
    except Exception:                                             # noqa: BLE001
        burned = None
    if burned is None:
        out["why"] = ("the EAST text detector returned nothing (model missing "
                      "or unreadable) — the burned-text leg is UNCHECKED")
        return out
    # the field is `source_text_regions` — the bands a camera or overlay must
    # AVOID. `bands` does not exist on this dict, and reading a key that is not
    # there would have returned an empty set: a clean zero from a reader that
    # found no input, which is the most expensive result to trust.
    bbands = set(burned.get("source_text_regions") or ())

    bad = []
    for r in vis:
        t0 = r["from"] / 30.0
        t1 = (r["from"] + (r["dur"] or 0)) / 30.0
        occ = fb.face_occupied_bands(traj, t0, t1)
        b = vc.band_of(r, meas)
        # THE CAPTION TRACK IS AN OCCUPANT, NOT A PLACEE. production's
        # `_caption_occupied_bands` exists so OTHER graphics avoid where our
        # captions land — the caption track itself goes where its style puts
        # it, and is never repositioned around the speaker. Judging it by the
        # face rule would condemn every captioned edit on this surface, which
        # is the shape of a check that rejects a correct implementation. It is
        # still checked for PIXEL overlap against everything else by hop 5.
        if "caption" in (r.get("asset") or ""):
            out["detail"].append(
                "slot%-3s band %.3f-%.3f  the caption track — an occupant "
                "others avoid, not a placement judged against the face"
                % (r["slot"], b[0], b[1]))
            continue
        # IN BAND NAMES. A placement intrudes when a band it MEANINGFULLY
        # occupies is one the face or the source's text also owns — not when
        # its edge touches the seam between two bands.
        mine = vc.bands_touched(b, fb.band_to_fraction)
        for name in sorted(mine & (occ | bbands)):
            bad.append((r["slot"], name,
                        "face" if name in occ else "source text",
                        1.0))
        out["detail"].append(
            "slot%-3s band %.3f-%.3f occupies %s | face %s | source text %s"
            % (r["slot"], b[0], b[1],
               sorted(vc.bands_touched(b, fb.band_to_fraction)) or "none",
               sorted(occ) or "none", sorted(bbands) or "none"))
    out["state"] = "FAILED" if bad else "MEASURED"
    out["why"] = (
        "%d placement(s) sit on something: %s"
        % (len(bad), "; ".join("slot%s in the %s band, which the %s occupies"
                               % (s, n, k) for s, n, k, _o in bad))
        if bad else
        "faces found in %d of %d sampled frames; source text in %s; no "
        "placement overlaps either"
        % (nfound, len(traj), sorted(bbands) or "no band"))
    return out


def _audio_lag_ms(a_path, b_path, at=11.0, dur=3.0):
    """How late a_path's audio is against b_path's, in ms. None if unmeasurable.

    Envelope cross-correlation at 2ms resolution. A source-against-itself
    control reads exactly 0 at r=1.000, so the instrument has no bias of its
    own — which is the only reason a 42ms reading can be believed.
    """
    def env(f):
        p = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", "%.3f" % at, "-t", "%.3f" % dur,
             "-i", f, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
            capture_output=True, timeout=300)
        if p.returncode != 0 or not p.stdout:
            return None
        import struct as _st
        n = len(p.stdout) // 2
        v = _st.unpack("<%dh" % n, p.stdout[:n * 2])
        w = 32                                   # 2ms at 16kHz
        return [math.sqrt(sum(x * x for x in v[i:i + w]) / w)
                for i in range(0, n - w, w)]
    A, B = env(a_path), env(b_path)
    if not A or not B:
        return None
    n, best = min(len(A), len(B)), (-2.0, 0)
    for L in range(-60, 61):
        xs = [(A[i], B[i - L]) for i in range(max(0, L), min(n, n + L))]
        if len(xs) < 60:
            continue
        ma = sum(x for x, _ in xs) / len(xs)
        mb = sum(y for _, y in xs) / len(xs)
        num = sum((x - ma) * (y - mb) for x, y in xs)
        den = math.sqrt(sum((x - ma) ** 2 for x, _ in xs)
                        * sum((y - mb) ** 2 for _, y in xs))
        if den and num / den > best[0]:
            best = (num / den, L)
    return best[1] * 2


def verify_hop7_sync(tok, stage, shape):
    """HOP 7 — the DELIVERED audio lines up with the source it came from.

    THE COMPENSATION IS MEASURED, NOT TRUSTED. CHATCUT_AUDIO_LEAD_MS shifts our
    audio 42ms earlier before upload because their export delays it by exactly
    that, measured on a NO-EDIT round trip. A hard-coded shift with nothing
    watching it is what breaks in silence the day they fix their end — so this
    reads the delivered file and fails on a residual either way, naming the
    constant so whoever sees it knows what to change.

    Tolerance is 20ms: half a frame at 30fps, and well inside the threshold at
    which lip-sync error becomes visible.
    """
    out = {"state": "ABSENT", "why": "not attempted", "detail": []}
    if not (stage and shape):
        out["why"] = "no prestage or no agent shape"
        return out
    if not os.path.exists("/work/source.mp4"):
        out["why"] = "the original source is gone — nothing to measure against"
        return out
    try:
        ex = _mcp_call(tok, "track_export",
                       {"projectId": stage["projectId"], "action": "status"})
        blob = json.dumps(ex) + str(ex.get("_text") or "")
        url = re.search(r'(https://[^\s"\\]+out\.mp4[^\s"\\]*)', blob)
        if not url:
            out["why"] = ("no finished export to measure yet — the render was "
                          "still going when the chain ran")
            return out
        import urllib.request as _u
        with _u.urlopen(url.group(1), timeout=600) as r, \
                open("/work/delivered.mp4", "wb") as fh:
            fh.write(r.read())
        lag = _audio_lag_ms("/work/delivered.mp4", "/work/source.mp4")
        if lag is None:
            out["why"] = "the envelope could not be read from one of the files"
            return out
        out["detail"].append(
            "delivered audio is %+dms against the source; compensation applied "
            "was %dms" % (lag, CHATCUT_AUDIO_LEAD_MS))
        out["state"] = "MEASURED" if abs(lag) <= 20 else "FAILED"
        out["why"] = (
            "delivered audio is %+dms against the source — within 20ms"
            % lag if abs(lag) <= 20 else
            "delivered audio is %+dms against the source. The compensation is "
            "%dms; if this reads about %+d the export delay is gone and "
            "CHATCUT_AUDIO_LEAD_MS should go to 0, and if it reads about +42 "
            "the compensation did not apply."
            % (lag, CHATCUT_AUDIO_LEAD_MS, -CHATCUT_AUDIO_LEAD_MS))
    except Exception as e:                                        # noqa: BLE001
        out["state"] = "FAILED"
        out["why"] = "%s: %s — the sync is UNCHECKED" % (type(e).__name__, e)
    return out


# THE MODEL CANNOT WATCH VIDEO. Tested directly rather than assumed: a `video`
# content block is refused — "Input tag 'video' ... does not match any of the
# expected tags", and the accepted list carries image and document and no
# moving picture. So "it watches the footage" has a ceiling, and the honest
# ceiling is a DENSE SEQUENCE OF FULL FRAMES plus the transcript. Individual
# frames at readable size, not one 240px tile of twenty — a tile is a thing the
# harness chose and compressed; a sequence is the nearest thing to watching
# that this surface allows.
SOURCE_FRAMES_N = 14
EDIT_FRAMES_N = 9                    # preview_timeline returns at most 9


def _frames_of(video, n, out_dir, width=480):
    """N evenly-spaced frames of a video, as individual readable images."""
    os.makedirs(out_dir, exist_ok=True)
    dur = 0.0
    try:
        dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", video],
            capture_output=True, text=True, timeout=120).stdout.strip() or 0.0)
    except Exception:                                             # noqa: BLE001
        return []
    if dur <= 0:
        return []
    out = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        fp = os.path.join(out_dir, "f%02d.jpg" % i)
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % t, "-i", video,
             "-vf", "scale=%d:-2" % width, "-frames:v", "1", "-q:v", "4", fp],
            capture_output=True, timeout=300)
        if r.returncode == 0 and os.path.exists(fp) and \
                os.path.getsize(fp) > 2000:
            out.append((round(t, 2), fp))
    return out


def _img_block(path, media="image/jpeg"):
    with open(path, "rb") as fh:
        return {"type": "image",
                "source": {"type": "base64", "media_type": media,
                           "data": base64.b64encode(fh.read()).decode()}}


def _message(blocks_and_text):
    """A stream-json user message from an ordered list of blocks."""
    return {"type": "user", "message": {"role": "user",
                                        "content": blocks_and_text}}


def pass1_message(plan, beats, inventory_png, source_video):
    """WHAT THE AGENT IS SERVED BEFORE IT DECIDES ANYTHING.

    In order, in one message:
      1. THE INVENTORY, as a picture — every component that renders, each a
         real frame of itself, with what it is for beside it. Served, not
         fetched: if it has to look something up it is not on a platter, and
         the previous shape mounted a file and told it to Read one.
      2. THE SOURCE, as a dense sequence of full frames with their timestamps.
         Not a tile the harness compressed — individual readable frames. The
         model cannot take video (tested: a `video` block is refused), so this
         is the ceiling and it is stated rather than dressed up.
      3. THE TRANSCRIPT, time-aligned against those frames.
      4. THE PLAN.
    """
    blocks = []
    if inventory_png and os.path.exists(inventory_png):
        blocks.append({"type": "text", "text":
                       "THE COMPONENT INVENTORY — every one of these renders, "
                       "each picture is a real frame of that component, and "
                       "the list underneath says what each is for. This is "
                       "everything you can place. You never author component "
                       "code and you never look anything up."})
        blocks.append(_img_block(inventory_png, "image/png"))
    frames = _frames_of(source_video, SOURCE_FRAMES_N, "/work/src_frames")
    if frames:
        blocks.append({"type": "text", "text":
                       "THE SOURCE — %d frames across the whole clip, in order, "
                       "at %s. Look at the footage before you decide anything: "
                       "the plan is derived from the transcript and CANNOT SEE "
                       "the picture, so it does not know what is already burned "
                       "into the frame, where the speaker is, or what the shot "
                       "already shows."
                       % (len(frames),
                          ", ".join("%.1fs" % t for t, _ in frames))})
        for _t, fp in frames:
            blocks.append(_img_block(fp))
    if beats:
        blocks.append({"type": "text", "text":
                       "THE TRANSCRIPT, against those frames:\n"
                       + "\n".join(
                           "  %6.2f-%6.2fs  %s"
                           % (b.get("t_start", 0), b.get("t_end", 0),
                              str(b.get("text") or "").split(" \u00b7 ")[0])
                           for b in beats)})
    blocks.append({"type": "text", "text": plan})
    return _message(blocks)


def pass2_message(frames, plan_frames):
    """WHAT THE AGENT IS SERVED BEFORE IT FIXES ANYTHING — the edit itself.

    The composed timeline with everything on it, as a sequence of frames
    across the whole edit. Fetched, downloaded and handed over by the harness:
    the agent spends no turn getting them.
    """
    blocks = [{"type": "text", "text":
               "THE EDIT — your timeline with everything on it, %d frames "
               "across the whole thing (timeline frames %s). This is what the "
               "viewer sees.\n\n"
               "Look at it and fix what is wrong: a graphic colliding with "
               "another or with the captions, something illegible, something "
               "off-frame, something sitting on the speaker's face, a title on "
               "the wrong moment, wrong size, drift. Make EVERY correction in "
               "ONE edit_item call.\n\n"
               "If it is right, submit the export. A further pass is only for "
               "a defect you can NAME — and if you take one, say which frame "
               "you saw it in and what you changed."
               % (len(frames), ", ".join(str(f) for f in plan_frames[:9]))}]
    for fp in frames:
        blocks.append(_img_block(fp))
    return _message(blocks)


def _edit_frames(tok, pid, total_frames, n=EDIT_FRAMES_N):
    """N frames evenly across the EDIT, downloaded. [] with the reason printed.

    Evenly across the whole timeline, not only the settled moments — the
    question in pass 2 is "is the edit right", and a defect does not wait for
    a frame the planner nominated.
    """
    want = [int(total_frames * (i + 0.5) / n) for i in range(n)] if \
        total_frames else []
    if not want:
        print("  EDIT FRAMES     : ABSENT  the timeline length is unknown",
              flush=True)
        return [], []
    try:
        pv = _mcp_call(tok, "preview_timeline",
                       {"projectId": pid, "views": ["viewer"],
                        "viewerFrames": want})
        uris = list(pv.get("_links") or [])
        if not uris:
            print("  EDIT FRAMES     : ABSENT  the viewer returned no links "
                  "(keys %s)" % sorted(pv)[:8], flush=True)
            return [], want
        import urllib.request as _u
        os.makedirs("/work/edit_frames", exist_ok=True)
        got = []
        for i, u in enumerate(uris[:n]):
            fp = "/work/edit_frames/e%02d.jpg" % i
            try:
                with _u.urlopen(u, timeout=180) as r, open(fp, "wb") as fh:
                    fh.write(r.read())
                if os.path.getsize(fp) > 2000:
                    got.append(fp)
            except Exception:                                     # noqa: BLE001
                continue
        print("  EDIT FRAMES     : %s  %d of %d frame(s) at %s"
              % ("MEASURED" if got else "FAILED", len(got), len(want),
                 ", ".join(str(f) for f in want)), flush=True)
        return got, want
    except Exception as e:                                        # noqa: BLE001
        print("  EDIT FRAMES     : FAILED  %s: %s" % (type(e).__name__, e),
              flush=True)
        return [], want


def _sheet_message(text, image_path=None, media="image/jpeg"):
    """A stream-json user message carrying TEXT and, when given, PIXELS.

    PROVEN BEFORE IT WAS BUILT ON: an image passed this way is read by the
    model with ZERO tool calls and the whole exchange is one turn. The old
    shape — write the sheet to /work and tell the agent to Read it — spent a
    turn getting pixels the harness already had in memory.
    """
    content = []
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as fh:
            content.append({"type": "image",
                            "source": {"type": "base64", "media_type": media,
                                       "data": base64.b64encode(
                                           fh.read()).decode()}})
    content.append({"type": "text", "text": text})
    return {"type": "user", "message": {"role": "user", "content": content}}


def _review_sheet(tok, pid, frames, out="/work/review.jpg"):
    """Fetch the composed frames the plan named and tile them into ONE image.

    THE HARNESS DOES WHAT COST FOUR AGENT TURNS. preview_timeline, a curl per
    frame, an ffmpeg tile and a Read was four turns to look once; none of it is
    a decision, and the model was only ever needed for the LOOKING. Returns the
    path, or None with the reason printed — a review that could not be built
    must not read as a review that found nothing.
    """
    try:
        pv = _mcp_call(tok, "preview_timeline",
                       {"projectId": pid, "views": ["viewer"],
                        "viewerFrames": list(frames)[:9]})
        uris = list(pv.get("_links") or [])
        if not uris:
            print("  REVIEW SHEET    : ABSENT  the viewer returned no frame "
                  "links (keys %s)" % sorted(pv)[:8], flush=True)
            return None
        import urllib.request as _u
        os.makedirs("/work/rev", exist_ok=True)
        got = []
        for i, u in enumerate(uris):
            fp = "/work/rev/f%02d.jpg" % i
            try:
                with _u.urlopen(u, timeout=180) as r, open(fp, "wb") as fh:
                    fh.write(r.read())
                if os.path.getsize(fp) > 2000:
                    got.append(fp)
            except Exception:                                     # noqa: BLE001
                continue
        if not got:
            print("  REVIEW SHEET    : ABSENT  no frame downloaded", flush=True)
            return None
        args = ["ffmpeg", "-v", "error", "-y"]
        for fp in got:
            args += ["-i", fp]
        n = len(got)
        # BUILT EXPLICITLY. `A + B + C if n > 1 else D` binds the ternary to
        # the WHOLE concatenation, so the one-frame case silently dropped the
        # scale — a precedence trap that would have produced a full-size single
        # tile and looked fine until a plan named one review frame.
        _scale = "".join("[%d]scale=360:-1[s%d];" % (i, i) for i in range(n))
        if n > 1:
            _fc = _scale + "".join("[s%d]" % i for i in range(n)) \
                + "hstack=inputs=%d" % n
        else:
            _fc = _scale + "[s0]null"
        args += ["-filter_complex", _fc, "-frames:v", "1", out]
        if subprocess.run(args, capture_output=True,
                          timeout=300).returncode != 0 or \
                not os.path.exists(out):
            print("  REVIEW SHEET    : FAILED  the tile did not build",
                  flush=True)
            return None
        print("  REVIEW SHEET    : MEASURED  %d frame(s) tiled into %s (%d KB)"
              % (n, out, os.path.getsize(out) // 1024), flush=True)
        return out
    except Exception as e:                                        # noqa: BLE001
        print("  REVIEW SHEET    : FAILED  %s: %s" % (type(e).__name__, e),
              flush=True)
        return None


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
    # BUILT FROM WHAT DREW, not from the old catalogue. `chatcut_catalogue.json`
    # named 29 components — including SpeechBubble, which is REFUSED and cannot
    # be placed — and named NONE of the nine caption styles, which is exactly
    # the set that was built to be offered. So the agent was shown one thing it
    # could not use and none of the nine it should have picked from.
    # sheet.json is written by the render check: every entry in it has a real
    # frame and a WHEN condition, and nothing that failed to draw is in it.
    try:
        _sh = json.load(open("/craft/component_sheet.json", encoding="utf-8"))
        _entries = _sh.get("entries") or []
        if not _entries:
            raise ValueError("sheet.json carries no entries")
        _lines = ["\n\n===== THE COMPONENT LIBRARY =====\n",
                  _sh.get("header", "") + "\n",
                  "Every one is ALREADY REGISTERED in your project. You place it "
                  "by assetId and you never author component code.\n",
                  "THE PICTURE OF ALL %d IS THE FIRST IMAGE IN THIS MESSAGE "
                  "— you already have it, there is nothing to open. The "
                  "picture is how you pick; the lines below are its index, in "
                  "the same order.\n" % len(_entries)]
        _by = {}
        for _e2 in _entries:
            _by.setdefault(_e2.get("when", "?"), []).append(_e2)
        for _h in sorted(_by):
            _lines.append("  %s\n" % _h)
            for _e2 in sorted(_by[_h], key=lambda x: x["name"]):
                _lines.append("      %-22s %-7s %s\n"
                              % (_e2["name"], _e2.get("size", "?"),
                                 _e2.get("claim", "")))
        parts.append("".join(_lines))
    except Exception as _e:                                       # noqa: BLE001
        # ABSENT IS NAMED, NOT SILENT. A library that failed to load and a
        # library with nothing in it read the same from downstream.
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
         run_id: str = "latest", use_hands: bool = False, plan: str = "",
         think_tokens: int = 0, prestage_title: str = "",
         prestage_controls: str = "", prestage_titles: str = "",
         transcript: str = ""):
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
        # ── HOP 2: plan -> prestage ─────────────────────────────────────────
        # Every assetId the plan names must be registered BEFORE the agent
        # starts. The card was lost exactly here: the plan named it, the
        # launcher never carried card_hero/card_label into the payload, the
        # asset registered without them, and the run went green on a graphic
        # that rendered its title and no card. A check that runs after the
        # agent is a report; this one refuses to start.
        sys.path.insert(0, "/root")
        import verify_chain as _vc
        _manifest = _vc.plan_manifest(plan or "")
        _reg = dict(_stage.get("components") or {})
        for _i2, _t2 in enumerate(_stage.get("titles") or []):
            _reg["GRAPHIC %d" % (_i2 + 1)] = _t2["assetId"]
        _miss2 = _vc.hop2_prestage(_manifest, _reg)
        if _miss2:
            raise RuntimeError(
                "HOP 2 (plan -> prestage): the plan names %d add(s) with no "
                "registered asset behind them. Refusing to run — the agent "
                "would place them and the run would go green on placements "
                "that cannot render:\n  %s"
                % (len(_miss2), "\n  ".join(
                    "CALL %s adds[%s] (%s): %s"
                    % (r["call"], r["slot"], r["type"], why)
                    for r, why in _miss2)))
        print("  HOP 2           : MEASURED  %d add(s), every assetId "
              "registered" % len(_manifest), flush=True)
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
                + ("PASS `projectId` ON EVERY CALL — the id is above. Do "
                   "NOT call target_project: binding the session is a turn, "
                   "and every tool here takes projectId directly. Then place "
                   "EVERY add the plan names, in the CALLS THE PLAN NAMES — "
                   "it labels "
                   "each add `CALL 1, adds[3]:` and says at the end how many "
                   "calls there are and why. Each graphic's assetId is listed "
                   "above and already carries its own text, band, size, hold "
                   "and colours, so there is nothing to pass and nothing to "
                   "decide. `import_media` and "
                   "`create_motion_graphic_from_code` are both NOT part of "
                   "this job. Your work is the placements, the look, and the "
                   "one revision.\n")
                + (("\nThe project also carries %d PRE-REGISTERED components, "
                    "each already validated, each with its editable properties "
                    "declared. If the plan calls for one, place it by the "
                    "assetId BESIDE ITS NAME — the plan writes the NAME "
                    "(`caption:TwoTone`), this list holds the ID. Never send a "
                    "name as an assetId, and never author component code:\n"
                    "%s\n"
                    # THE WHOLE UUID. This printed `[:8]`, so every id the
                    # agent could see was already truncated — and it then sent
                    # `caption:TwoTone` (rejected, the run's only error) and
                    # recovered with `c85df628`, the 8 characters this line
                    # gave it. Every abbreviated id in two runs came from here.
                    # edit_item happens to resolve a prefix and inspect_item
                    # refuses one, so the truncation cost three failed calls in
                    # the run before this and one rejected call in this one,
                    # while looking like the agent mistyping.
                    % (_libn, "\n".join(
                        "    %-22s %s%s" % (
                            k,
                            ((v.get("assetId") if isinstance(v, dict) else v)
                             or "?"),
                            ("   (+overrides)" if isinstance(v, dict) else ""))
                        for k, v in sorted(
                            (_stage.get("components") or {}).items())[:60])))
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
    # PASS 1 IS SERVED, NOT SENT SHOPPING. The inventory as pictures, the
    # source as a dense frame sequence, the transcript against it, the plan.
    _sheet_src = "/work/source_sheet.png" \
        if os.path.exists("/work/source_sheet.png") else None
    # THE TRANSCRIPT TRAVELS WITH THE JOB, time-aligned, because pass 1 needs
    # to read the words against the frames it is looking at.
    try:
        _beats = json.loads(transcript) if transcript else []
    except Exception:                                             # noqa: BLE001
        _beats = []
    print("  PASS 1 SERVES   : inventory=%s  source frames=%d  transcript=%d "
          "beat(s)"
          % (os.path.exists("/craft/component_sheet.png"), SOURCE_FRAMES_N,
             len(_beats)), flush=True)
    _cmd = (
        ["claude", "-p",
         "--input-format", "stream-json",
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
         # NAMED, NOT WILDCARDED. `mcp__chatcut__*` admits all 60 tools the
         # server advertises, and 60 tools is why their schemas arrive
         # DEFERRED — which is the whole reason a ToolSearch turn exists at
         # all. Whether Claude Code's deferral counts the server's tools or
         # the ALLOWED ones is not documented, so this run answers it: if the
         # ToolSearch turn disappears, the deferral respects the allowlist and
         # the turn was ours to remove. If it survives, the deferral is the
         # server's tool count and the turn is the harness's, not the edit's.
         # Either way the six are exactly what a pre-resolved plan needs.
         "--allowedTools",
         ",".join(["mcp__chatcut__" + t for t in NEEDED_TOOLS]
                  + ["Bash", "Read", "Write", "Glob", "Grep"]),
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
    # ── THE HARNESS DRIVES THE CONVERSATION ─────────────────────────────────
    # Two user messages, both carrying PIXELS the harness already has:
    #   1. the plan, with the SOURCE contact sheet as an image
    #   2. after the placements land, the REVIEW sheet as an image
    # Between them that removes five agent turns — a Read of the source sheet,
    # and the preview/curl/tile/Read the review used to cost — because none of
    # it is a decision. The model is needed for the LOOKING, not the fetching.
    sys.path.insert(0, "/root")
    import verify_chain as _vc_f
    _man = _vc_f.plan_manifest(plan or "")
    _total_frames = max([(r["from"] or 0) + (r["dur"] or 0) for r in _man]
                        or [0])
    _n_calls = len({r["call"] for r in _man}) or 1
    _state = {"edits": 0, "sent": False}

    def _drive(ev, send, close):
        """PASS 2: the edit is shown to the agent, once its placements land.

        FIRED ON THE PLAN'S LAST CALL, not on a fixed count — a plan with no
        effect names one call, and waiting for a second would have hung.
        """
        if _state["sent"] or ev.get("type") != "assistant":
            return
        for b2 in ((ev.get("message") or {}).get("content") or []):
            if b2.get("type") == "tool_use" and \
                    str(b2.get("name") or "").endswith("edit_item"):
                _state["edits"] += 1
        if _state["edits"] < _n_calls or not _stage:
            return
        _state["sent"] = True
        _got, _want = _edit_frames(tok, _stage["projectId"], _total_frames)
        if _got:
            send(pass2_message(_got, _want))
        else:
            # NAMED, NOT SILENT. An agent told nothing would export blind.
            send(_message([{"type": "text", "text":
                            "The edit could not be rendered for you to look "
                            "at, so you have NOT seen it. Fetch the frames "
                            "yourself with preview_timeline at %s before you "
                            "export, and say in your final message that the "
                            "harness could not show you the edit."
                            % ", ".join(str(f) for f in _want[:9])}]))
        close()

    _rc, _errtxt, _wall, _killed = turn_clock.run_timed(
        _cmd, "/work", "/work/stream.jsonl", "/work/timing.json", 1500,
        env=_env,
        stdin_first=json.dumps(pass1_message(
            prompt, _beats, "/craft/component_sheet.png", "/work/source.mp4")),
        on_event=_drive)
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
    # THE SHEET IS DELIVERED, NOT FETCHED. It now arrives as pixels in the
    # first message, so a Read of source_sheet.png is exactly what should NOT
    # happen — keying the check on that call would report FAILED on the run
    # that fixed it. What must hold is that the harness HANDED IT OVER.
    _saw_sheet = bool(_sheet_src) or any(
        "source_sheet" in (c.get("in") or "") for c in _calls)
    _prev_i = [i for i, c in enumerate(_calls)
               if c["tool"].endswith("preview_timeline")]
    _exp_i = [i for i, c in enumerate(_calls)
              if c["tool"].endswith("submit_export")]
    # AND THE REVIEW IS DELIVERED TOO. The harness tiles the composed frames
    # and sends them; a preview_timeline call by the AGENT is now the fallback
    # path, not the expected one. What must hold is that the composed frames
    # reached it before it exported — by either route.
    _looked_before_render = (
        bool(_state.get("sent")) and os.path.exists("/work/review.jpg")
    ) or (bool(_prev_i) and (not _exp_i or min(_prev_i) < max(_exp_i)))
    # THE UNDER-DELIVERY GATE. Every adherence leg asked whether the agent
    # ADDED something ruled out; none asked whether it placed what was ruled IN.
    # A run that skips a placement is FASTER and passes everything: 153.8s,
    # visual pass MEASURED, export submitted, exit 0, and no title. Over-reach
    # was instrumented and under-delivery was not — the cheaper failure to have
    # and the easier one to ship. It is a GATE now, not a line in a report.
    # A COUNTER KEYED TO PROSE BREAKS WHEN THE PROSE CHANGES. This counted
    # `plan.count("edit_item adds[")`. The plan now labels every add with its
    # CALL ("CALL 1, adds[3]:") because an effect cannot ride the batch that
    # creates its target — and the counter would have read ZERO, putting the
    # gate into ABSENT and reporting a complete edit as an empty plan. Fifth
    # reader this session to be wrong about correct text. So: anchored to the
    # whole line, and matching BOTH spellings, so a format change cannot
    # silently zero it again.
    _planned = len(re.findall(
        r"^[ \t]*(?:CALL \d+, |edit_item )adds\[\d+\]:[ \t]*$",
        plan or "", re.M))
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
        # WHAT THIS COUNTS, stated in the record. `items_added` is the number
        # of adds the agent SENT, read out of its own tool calls — not the
        # number of items ChatCut created. edit_item accepts an id PREFIX and
        # returns ok, so an add whose assetId or targetItemId resolved to
        # nothing is indistinguishable from a correct one at this seam.
        # Measured 2026-09-14: `targetItemId:"57ef4b265b"` — ten characters —
        # was accepted, and the zoom did land; `inspect_item` refuses the same
        # abbreviation. A green number here is a claim about the CALL. The
        # placement itself is proven in the frames.
        "counts": "adds SENT by the agent; not items ChatCut created",
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
    # ── HOPS 3 AND 4 ───────────────────────────────────────────────────────
    # The last run's agent said in its closing message that it could not
    # confirm the StatCard. It was right, and nothing acted on it. A placement
    # the agent intended and cannot confirm is a DEFECT, not a note.
    # A VERIFIER MUST NEVER KILL THE RUN. HOP 6 raised
    # `cv2.dnn has no attribute readNetFromCaffe` and the whole job died in the
    # container — no record persisted, the turn budget, the placements and the
    # agent's entire transcript lost, for an edit that had already exported
    # successfully. A gate exists to fail the VERDICT, not to destroy the
    # evidence: every hop now returns FAILED on its own exception and the
    # record is written either way.
    def _hop(name, fn, *a):
        try:
            return fn(*a)
        except Exception as e:                                    # noqa: BLE001
            return {"state": "FAILED", "detail": [],
                    "why": "%s raised %s: %s — this is the CHECK failing, not "
                           "the edit" % (name, type(e).__name__, str(e)[:160])}

    out["chain"] = _hop("hops 3+4", verify_hops_3_and_4, tok, _stage, plan)
    for _k in ("hop3", "hop4"):
        out["chain"].setdefault(_k, {"state": "FAILED",
                                     "why": "the hop 3/4 pass did not report"})
    out["chain"].setdefault("detail", [])
    out["chain"]["hop5"] = _hop("hop5", verify_hop5_composition, tok, _stage,
                                plan, _chain_items(tok, _stage))
    for _h in ("hop3", "hop4", "hop5"):
        print("  %s           : %s  %s"
              % (_h.upper(), out["chain"][_h]["state"], out["chain"][_h]["why"]),
              flush=True)
    for _l in (out["chain"].get("detail") or []) + \
              (out["chain"]["hop5"].get("detail") or []):
        print("      %s" % _l, flush=True)
    # A GATE, NOT A REPORT. A run whose placements cannot be confirmed, or
    # whose frames carry two things on top of each other, does not pass —
    # whatever the agent exported. The deliverable is the edit that was ruled,
    # and an unverified one is not it.
    out["chain"]["hop6"] = _hop("hop6", verify_hop6_clear, plan)
    print("  HOP6           : %s  %s" % (out["chain"]["hop6"]["state"],
                                         out["chain"]["hop6"]["why"]), flush=True)
    for _l in out["chain"]["hop6"].get("detail") or []:
        print("      %s" % _l, flush=True)
    out["chain"]["hop7"] = _hop("hop7", verify_hop7_sync, tok, _stage, shape)
    print("  HOP7           : %s  %s" % (out["chain"]["hop7"]["state"],
                                         out["chain"]["hop7"]["why"]), flush=True)
    for _l in out["chain"]["hop7"].get("detail") or []:
        print("      %s" % _l, flush=True)
    _failed = [h for h in ("hop3", "hop4", "hop5", "hop6", "hop7")
               if out["chain"][h]["state"] != "MEASURED"]
    out["chain"]["gate"] = "FAILED" if _failed else "PASSED"
    if _failed:
        print("  CHAIN GATE      : FAILED on %s — the edit is NOT confirmed"
              % ", ".join(_failed), flush=True)

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



# NO SECRETS. This fetches a public CDN URL and runs two local models; it
# touches neither ChatCut nor Anthropic, and a function that asks for
# credentials it does not use is a function that fails for the wrong reason.
@app.function(image=IMG, timeout=1800,
              secrets=[modal.Secret.from_name("chatcut-oauth")])
def audio_roundtrip(clip_url: str):
    """THE TWO PROBES THAT SETTLE THE +42ms WITH NO INFERENCE.

    PROBE 1 — upload a file and export it with NO EDITS. If the export comes
    back +42ms against the file we uploaded, the offset lives in their
    import/export and nothing we do to a plan can touch it. If it comes back
    clean, something our EDIT introduces it.

    PROBE 2 — ffprobe THE EXACT BYTES THE HELPER SENDS. Not my reproduction of
    its command — the file on disk at the moment it uploads. Edit list, priming
    samples, first timestamp, at that precise hop.

    Everything so far has been elimination: our transcode command measured 0ms
    and theirs measured +42ms, so it was theirs BY SUBTRACTION. This measures
    the hop directly instead.
    """
    os.makedirs("/work", exist_ok=True)
    subprocess.run(["curl", "-fsSL", "-o", "/work/source.mp4", clip_url],
                   check=True, timeout=600)
    tok = _access_token()
    out = {"probe1": {"state": "ABSENT"}, "probe2": {"state": "ABSENT"}}

    def probe(path, label):
        r = subprocess.run(
            ["ffprobe", "-v", "trace", "-i", path],
            capture_output=True, text=True, timeout=180)
        el = re.findall(r"Processing st: (\d+), edit list \d+ - media time: "
                        r"(-?\d+)", r.stderr or "")
        j = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=index,codec_type,codec_name,sample_rate,start_pts,"
             "start_time,time_base,initial_padding", "-of", "json", path],
            capture_output=True, text=True, timeout=180)
        try:
            streams = json.loads(j.stdout or "{}").get("streams") or []
        except Exception:                                         # noqa: BLE001
            streams = []
        return {"label": label, "edit_lists": el, "streams": streams,
                "bytes": os.path.getsize(path)}

    _stage = prestage(tok, "", controls={}, source_path="/work/source.mp4",
                      titles=[])
    pid = _stage["projectId"]

    # PROBE 2 — the helper leaves its transcode in the work dir; find it.
    cands = sorted(
        [os.path.join("/work", f) for f in os.listdir("/work")
         if f.startswith("chatcut-") and f.endswith(".mp4")]
        + [os.path.join("/tmp", f) for f in os.listdir("/tmp")
           if f.startswith("chatcut-") and f.endswith(".mp4")],
        key=lambda x: os.path.getmtime(x), reverse=True)
    out["probe2"] = {
        "state": "MEASURED" if cands else "ABSENT",
        "why": ("the helper's transcode at %s" % cands[0]) if cands else
               "no chatcut-*.mp4 left behind — the helper cleans up, so the "
               "uploaded bytes could not be probed at that hop",
        "source": probe("/work/source.mp4", "source (what we fetched)"),
        "uploaded": probe(cands[0], "uploaded (helper output)") if cands else None,
    }

    # PROBE 1 — place the whole clip and export with no other edit.
    _mcp_call(tok, "edit_item", {
        "projectId": pid,
        "adds": [{"type": "video", "assetId": _stage["sourceAssetId"],
                  "from": 0, "sourceStartFromInSeconds": 0}]})
    ex = _mcp_call(tok, "submit_export", {
        "projectId": pid, "format": "video", "codec": "h264",
        "resolution": "1080p"})
    rid = re.search(r"renderId[\"':\s]+([0-9a-f-]{8,})", json.dumps(ex) +
                    str(ex.get("_text") or ""))
    out["probe1"] = {"state": "SUBMITTED", "projectId": pid,
                     "renderId": rid.group(1) if rid else None,
                     "why": "poll track_export for the URL, then measure it "
                            "against /work/source.mp4"}
    print("  PROBE2          : %s" % out["probe2"]["why"], flush=True)
    print("  PROBE1          : project=%s render=%s"
          % (pid, out["probe1"]["renderId"]), flush=True)
    return out


@app.local_entrypoint()
def roundtrip(clip_url: str = "", out: str = "/tmp/bs/roundtrip.json"):
    r = audio_roundtrip.remote(clip_url)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(r, fh, indent=1)
    print("WROTE %s" % out)
    print("  probe2:", r["probe2"]["why"])
    for k in ("source", "uploaded"):
        v = r["probe2"].get(k)
        if v:
            print("    %-28s edit_lists=%s" % (v["label"], v["edit_lists"]))
    print("  probe1: project=%s render=%s"
          % (r["probe1"].get("projectId"), r["probe1"].get("renderId")))


@app.function(image=IMG, timeout=900)
def detect_regions(clip_url: str, duration_s: float = 0.0):
    """The face trajectory and the source's own text bands, for PLAN TIME.

    THE PLAN IS BUILT OFFLINE AND THE MODELS LIVE IN THIS IMAGE. Production
    routes a placement around the speaker's face and the source's burned-in
    text before anything is built; this lane could not, because
    `agentic_editor_app.py` produces no `face_traj` and no
    `source_text_regions` and the translator has neither cv2 nor the weights.
    So the detectors run here, once, and the answer travels with the ruling.

    Returns a JSON-safe dict, and NAMES its absences: a detector that could not
    load reports so rather than returning an empty trajectory, because "no
    faces found" and "we did not look" must not be the same value.
    """
    import sys as _sys
    _sys.path.insert(0, "/root")
    # /work IS NOT THERE YET IN THIS FUNCTION. `edit` creates it; this one runs
    # on its own and curl exited 23 (write error) on a directory that does not
    # exist — a failure that reads like a bad URL and is not.
    os.makedirs("/work", exist_ok=True)
    subprocess.run(["curl", "-fsSL", "-o", "/work/src.mp4", clip_url],
                   check=True, timeout=600)
    _d = duration_s or float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", "/work/src.mp4"],
        capture_output=True, text=True).stdout.strip() or 0.0)
    out = {"duration_s": _d, "face_state": "ABSENT", "text_state": "ABSENT",
           "face_traj": None, "source_text_regions": None}
    try:
        import face_bands as fb
        ts = [round(i * 0.25, 2) for i in range(int(max(1.0, _d) / 0.25) + 1)]
        traj = fb.detect_face_positions("/work/src.mp4", ts)
        if traj is None:
            out["face_why"] = "cv2 or the res10 model is missing"
        else:
            out["face_traj"] = traj
            out["face_state"] = "MEASURED"
            out["faces_found"] = sum(1 for p in traj if p.get("found"))
            out["face_sampled"] = len(traj)
    except Exception as e:                                        # noqa: BLE001
        out["face_why"] = "%s: %s" % (type(e).__name__, str(e)[:160])
    try:
        import burned_text as bt
        b = bt.detect_burned_in_text("/work/src.mp4")
        if b is None:
            out["text_why"] = "the EAST model is missing or unreadable"
        else:
            out["source_text_regions"] = list(b.get("source_text_regions") or ())
            out["text_state"] = "MEASURED"
            out["has_burned_captions"] = bool(b.get("has_burned_captions"))
    except Exception as e:                                        # noqa: BLE001
        out["text_why"] = "%s: %s" % (type(e).__name__, str(e)[:160])
    print("  DETECT          : face=%s (%s/%s found)  text=%s %s"
          % (out["face_state"], out.get("faces_found"), out.get("face_sampled"),
             out["text_state"], out.get("source_text_regions")), flush=True)
    return out


@app.local_entrypoint()
def detect(clip_url: str = "", out: str = "/tmp/bs/regions.json"):
    r = detect_regions.remote(clip_url)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(r, fh, indent=1)
    print("WROTE %s  face=%s text=%s regions=%s"
          % (out, r["face_state"], r["text_state"],
             r.get("source_text_regions")))


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
    _baked = "/craft/chatcut_registry_baked.json"
    _path = _baked if os.path.exists(_baked) else "/craft/chatcut_registry.json"
    reg = json.load(open(_path, encoding="utf-8"))
    print("  REGISTRY        : %s" % _path, flush=True)
    comps = reg.get("components") or reg
    refused = reg.get("refused") or {}
    samples = json.loads(sample_props_json) if sample_props_json else {}
    # THE BAKED REGISTRY CARRIES ITS OWN OVERRIDES — the scalar half of the
    # split. Structured content is already inside the code; what is left is
    # exactly what propertyOverrides is for, so it travels with the component
    # rather than being supplied again from a fixture file that could drift.
    for _n, _sp in comps.items():
        if _sp.get("overrides"):
            samples.setdefault(_n, {}).update(_sp["overrides"])
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
            # A COHERENT REGION IS A RENDER, WHATEVER ITS AREA. A flat
            # 0.2%-of-frame floor called three correct components ABSENT:
            # TikTokComment at 0.188% (a complete comment row — avatar "KE",
            # "kellan", "wait how", heart, 98 likes, READ FROM THE FRAME),
            # RecordingFrame at 0.134% (its screen-chrome border, bbox 88% of
            # the picture), and caption:Prime at 0.170% (one caption word, the
            # same shape as eight sibling styles that passed at 0.29-1.17%).
            # A threshold tight enough to reject a correct implementation is
            # not a check — third time this lane has paid for that, and the
            # first two were someone else's code.
            #
            # Noise has no bbox worth the name; a render does. So either the
            # area is unambiguous, or the changed pixels form a region.
            _px = None if frac is None else frac * 1080 * 1920
            _bba = 0 if not box else (box[2] - box[0]) * (box[3] - box[1])
            _drew = frac is not None and (
                frac > 0.002 or (_px >= 1200 and _bba >= 4000))
            rows[n] = {
                "content_unavailable": spec.get("content_unavailable") or [],
                "state": ("FAILED" if frac is None
                          else "MEASURED" if _drew else "ABSENT"),
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


@app.function(image=IMG, timeout=1800,
              secrets=[modal.Secret.from_name("chatcut-oauth"),
                       modal.Secret.from_name("anthropic-api-key")])
def bake_probe(payload_json: str):
    """Register ONE component whose ARRAY CONTENT IS BAKED INTO THE CODE, place
    it over a stage, and diff the pixels against that project's own empty frame.

    THE IDEA BEING TESTED. ChatCut has no array property type, so eight
    components were registered with their content typed `text` and defaulting
    to "" — they rendered blank and passed every validator. But the CODE is
    registered per asset, and the plan knows the items at registration time. So
    the array does not have to be a property at all: bake it in as a literal
    and the component gets its content.

    Both halves move together: the read `items: props.items` becomes a literal
    AND the `items` declaration is dropped, because ChatCut refuses a declared
    property the code does not read just as firmly as the reverse.
    """
    import urllib.request
    tok = _access_token()
    spec = json.loads(payload_json)
    name = spec.get("name") or "baked"

    def call(fn, args, mid):
        r = mcp_rpc(tok, "tools/call", {"name": fn, "arguments": args}, mid)
        if r.get("error"):
            raise RuntimeError(f"{fn}: {r['error']}")
        out = r.get("result") or {}
        txt = "".join(c.get("text") or "" for c in (out.get("content") or []))
        if txt.strip().startswith("{"):
            try:
                return json.loads(txt)
            except Exception:                                  # noqa: BLE001
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

    STAGE = ('const Component = ({ item }) => {\n'
             '  const props = (item && item.props) || {};\n'
             '  const rootStyle = { position: "absolute", inset: 0,\n'
             '    backgroundColor: "#202024" };\n'
             '  return <div style={rootStyle} />;\n'
             '};\n')
    pr = call("create_project", {"name": f"bake {name}",
                                 "compositionWidth": 1080,
                                 "compositionHeight": 1920, "fps": 30}, 1)
    pid = find(pr, "projectId") or re.search(
        r"/editor/([0-9a-f-]{36})", find(pr, "editorUrl") or "").group(1)
    st = call("create_motion_graphic_from_code",
              {"projectId": pid, "name": "stage", "code": STAGE,
               "width": 1080, "height": 1920, "durationInSeconds": 20,
               "properties": []}, 2)
    call("edit_item", {"projectId": pid, "adds": [
        {"type": "motion-graphic", "assetId": st.get("assetId"),
         "from": 0, "durationInFrames": 300}]}, 3)

    def shot(at, mid):
        r = call("preview_timeline", {"projectId": pid, "views": ["viewer"],
                                      "viewerFrames": [at]}, mid)
        u = find(r, "uri")
        return (urllib.request.urlopen(u, timeout=120).read() if u else None)

    eff = {p["key"]: p["defaultValue"] for p in spec["properties"]}
    eff.update(spec.get("overrides") or {})
    at = max(1, min(int(eff.get("enterFrames") or 12) + 8,
                    round((eff.get("durationMs") or 4000) / 1000.0 * 30)
                    - int(eff.get("exitFrames") or 8) - 4))
    base = shot(at, 4)
    a = call("create_motion_graphic_from_code",
             {"projectId": pid, "name": name, "code": spec["code"],
              "width": 1080, "height": 1920, "durationInSeconds": 8,
              "properties": spec["properties"]}, 5)
    v = find(a, "validation") or {}
    if v.get("errors") or not a.get("assetId"):
        return {"name": name, "state": "REFUSED",
                "detail": str(v.get("errors") or a)[:600]}
    add = {"type": "motion-graphic", "assetId": a["assetId"],
           "from": 0, "durationInFrames": 150}
    if spec.get("overrides"):
        add["propertyOverrides"] = spec["overrides"]
    call("edit_item", {"projectId": pid, "adds": [add]}, 6)
    png = shot(at, 7)

    from PIL import Image, ImageChops
    import io, base64
    ia = Image.open(io.BytesIO(base)).convert("RGB")
    ib = Image.open(io.BytesIO(png)).convert("RGB")
    d = ImageChops.difference(ia, ib).convert("L").point(
        lambda q: 255 if q > 12 else 0)
    frac = sum(d.histogram()[255:]) / float(ia.size[0] * ia.size[1])
    return {"name": name, "state": "MEASURED" if frac > 0.002 else "ABSENT",
            "frac_pct": round(frac * 100, 3), "bbox": d.getbbox(),
            "frame": at, "project": pid,
            "jpg_b64": base64.b64encode(png).decode()}


@app.local_entrypoint()
def bake(payload_file: str):
    """Register one baked component and report whether it draws."""
    from require_detach import require_detach
    require_detach(why_not="one component, one render — ~90s")
    import base64
    r = bake_probe.remote(open(payload_file, encoding="utf-8").read())
    print("  %-18s %-9s %s%%  bbox %s  @f%s"
          % (r["name"], r["state"], r.get("frac_pct"), r.get("bbox"),
             r.get("frame")))
    if r.get("detail"):
        print("  detail: %s" % r["detail"])
    if r.get("jpg_b64"):
        out = "/tmp/bs/bake_%s.jpg" % r["name"]
        open(out, "wb").write(base64.b64decode(r["jpg_b64"]))
        print("  frame -> %s" % out)


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
         model: str = "claude-sonnet-5", use_hands: bool = False,
         plan_file: str = "", think_tokens: int = 0,
         prestage_title: str = "", prestage_controls: str = "",
         prestage_titles: str = "", transcript_file: str = ""):
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
        # A URL WITH NO EXPIRY IS THE ANSWER, NOT A GAP. This bucket's policy
        # allows ONLY the CloudFront service principal, so a presigned S3 URL
        # is refused by design and every one this harness minted had a clock on
        # it — three runs were launched against a URL with under twenty minutes
        # left and one expired mid-session. The distribution (E1LT8PUEHV3OVA,
        # d1iax8jos987n3.cloudfront.net) serves the same objects unsigned, so
        # the CDN URL has no expiry to check and no re-minting to forget.
        import urllib.request as _ur
        try:
            _rq = _ur.Request(clip_url, method="HEAD")
            with _ur.urlopen(_rq, timeout=30) as _rs:
                _code = _rs.status
        except Exception as _e:                                   # noqa: BLE001
            raise SystemExit(
                "REFUSING TO LAUNCH: the clip URL carries no expiry and a HEAD "
                "on it failed (%s). An unreachable source dies in the container "
                "with nothing in the results Dict." % _e)
        if _code != 200:
            raise SystemExit(
                "REFUSING TO LAUNCH: the clip URL carries no expiry and HEAD "
                "returned %s." % _code)
        print("  CLIP URL        : MEASURED  no expiry, HEAD 200 (CDN)")
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
    # THE TRANSCRIPT, read here so a missing file fails at LAUNCH rather than
    # leaving pass 1 with frames and no words.
    _tx = ""
    if transcript_file:
        with open(transcript_file, encoding="utf-8") as fh:
            _tx = fh.read()
        print("  TRANSCRIPT      : MEASURED  %d beat(s)" % len(json.loads(_tx)))
    else:
        print("  TRANSCRIPT      : ABSENT — pass 1 gets frames and no words")
    rid = run_id or f"run-{int(time.time())}"
    if wait:
        print(json.dumps(edit.remote(clip_url, brief, model=model, run_id=rid,
                                     use_hands=use_hands, plan=plan_text,
                                     think_tokens=think_tokens,
                                     prestage_title=prestage_title,
                      prestage_controls=prestage_controls,
                      prestage_titles=prestage_titles,
                      transcript=_tx),
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
                      prestage_titles=prestage_titles,
                      transcript=_tx)
    print(f"SPAWNED run_id={rid} call={call.object_id}")
    print(f"read it with:  modal run chatcut_read_result.py --run-id {rid}")
