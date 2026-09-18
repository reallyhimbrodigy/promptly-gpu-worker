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
import shutil
import subprocess
import threading
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
CLI_PIN = "2.1.226"   # the claude-code version baked into IMG; see the npm line below
IMG = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("curl", "ca-certificates", "git", "ffmpeg", "openssl")   # openssl: the transparent proxy's throwaway CA
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
        # PINNED (2026-09-17). Unpinned, the image took 2.1.272, measured in the
        # container: cache entries written with a 5-MINUTE TTL (local 2.1.226
        # writes 1h — the keep-warm ruling's premise), and with ANTHROPIC_BASE_URL
        # set (the fingerprint proxy, ruling 1's instrument) cache markers only on
        # the system prompt — the 181k-token watch uncached on every call
        # (message_start: input 181,191 / read 41,631 / written 0). 2.1.226
        # through the same proxy marks the last message and writes 1h entries.
        "npm install -g @anthropic-ai/claude-code@" + CLI_PIN,
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
    # THE RECORDING PROXY (2026-09-17): every /v1/messages request the CLI
    # sends is fingerprinted segment by segment before it is forwarded, so a
    # cache miss comes with the bytes that moved. Proven locally: it streamed
    # a real run and showed the tool block growing 169 -> 289 between call 1
    # and call 2 as MCP servers finished connecting — the whole-prefix rewrite.
    .add_local_file(os.path.join(_HERE, "api_proxy.py"),
                    "/root/api_proxy.py", copy=True)
    # THE MCP SHIM (2026-09-17): advertises the nine tools this job may call,
    # forwards their calls, and answers `initialize` WITHOUT the hosted
    # server's instructions (the Skill-turn mandate). Proven locally through
    # the proxy: upstream 59 -> kept 9, present on call 1, identical on call 2.
    .add_local_file(os.path.join(_HERE, "mcp_shim.py"),
                    "/root/mcp_shim.py", copy=True)
    # THE REFERENCE INSTRUMENT (frame_urls / fetch / structured /
    # transcript_lines): watch_asset imports it at run time. Measured on the
    # rewatch probe of 2026-09-17: ModuleNotFoundError — every rewatch and the
    # source watch would have died. The leg below reads every run-time import
    # against these mounts so the next one cannot be missed.
    .add_local_file(os.path.join(_HERE, "chatcut_reference.py"),
                    "/root/chatcut_reference.py", copy=True)
    .add_local_file(os.path.join(_HERE, "verify_chain.py"),
                    "/root/verify_chain.py", copy=True)
    # GATE B. `gate_b` does `import chatcut_gate` at /root, so an unmounted
    # module is an ImportError in the container and a gate that never runs.
    # It is also how the undefined-name smoke finds a file at all: that
    # population is DERIVED from these mounts, so a module the image does not
    # carry is a module no check covers. One omission, two failures.
    .add_local_file(os.path.join(_HERE, "chatcut_gate.py"),
                    "/root/chatcut_gate.py", copy=True)
    # THE MODE RULE AND THE VERIFIED PRIMITIVES — the two things the single
    # agent needs that only the planner and the translator used to carry.
    # ONE COPY EACH: the rule is a file both images mount, and FAMILY_MAP is
    # imported from the translator rather than restated here. The translator
    # is being retired as a STEP; its map is the record of what was observed
    # on a live timeline, and that outlives it.
    .add_local_file(os.path.join(_HERE, "mode_rule.txt"),
                    "/craft/mode_rule.txt", copy=True)
    .add_local_file(os.path.join(_HERE, "plan_for_chatcut.py"),
                    "/root/plan_for_chatcut.py", copy=True)
    .add_local_file(os.path.join(_HERE, "chatcut_sound_library.json"),
                    "/craft/chatcut_sound_library.json", copy=True)
    # THE REFERENCE STANDARD — what Claude wrote from watching all ten through
    # inspect_asset. The Gemini sheets and their reader are NOT here any more:
    # 45,871 image tokens for 38 sampled moments, replaced by a document
    # written from 852.
    .add_local_file(os.path.join(_HERE, "reference_standard.md"),
                    "/craft/reference_standard.md", copy=True)
    # THE WATCH ITSELF, NOT A DOCUMENT ABOUT IT. 21 MB of real Claude Code
    # session: 41 contact sheets over 852 frames of the ten references, and the
    # model's own reading of each clip turn by turn. Resumed, the run holds the
    # frames it looked at and can be asked about a moment no summary mentions.
    # A FIXTURE BELONGS IN THE TREE — a session file at a /tmp path is the
    # recorded failure set (MISSING, DRIFTED, STALE FROM A BRANCH), and the
    # third of those restores silently under a green tally.
    .add_local_file(os.path.join(_HERE, "watch_session.jsonl"),
                    "/craft/watch_session.jsonl", copy=True)
    .add_local_file(os.path.join(_HERE, "watch_session_id.txt"),
                    "/craft/watch_session_id.txt", copy=True)
    # THE CHATCUT SKILL, INLINED RATHER THAN INVOKED. The MCP server's own
    # instructions tell the model to call the Skill tool before its first
    # ChatCut call — a whole model turn (~$0.054 and ~2.6s) spent loading text
    # we can simply put in the prefix. 9,030 tokens cached costs $0.0027 a
    # turn warm; the turn it replaces costs $0.054. It is a PROMPT-LEVEL fold:
    # the server asks, and the prefix answers before it is asked.
    .add_local_file(os.path.join(_HERE, "chatcut_skill_basics.md"),
                    "/craft/chatcut_skill_basics.md", copy=True)
    # THE PRE-TOOL GATE. Withholding preview_timeline until the edit exists is
    # the one fold that could not be done with --allowedTools, because that
    # list is fixed at launch and this withholding is CONDITIONAL. A
    # PreToolUse hook refuses per call: verified locally, two Bash calls
    # denied in one run with the reason surfaced to the model verbatim.
    .add_local_file(os.path.join(_HERE, "withhold_preview.sh"),
                    "/root/withhold_preview.sh", copy=True)
    .add_local_file(os.path.join(_HERE, "chatcut_hooks.json"),
                    "/root/chatcut_hooks.json", copy=True)
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
# SPEND AND SETUP SURVIVE A PREEMPTION, KEYED BY RUN ID.
#
# Modal restarts a preempted Function WITH THE SAME INPUT, in a fresh
# container. Measured on run 9: attempt 1 reached the ceiling at 2,663,652
# tokens, was preempted, and the retry reached it again at 2,574,041 — one
# launch, two full attempts, both billed. The ceiling bounded an ATTEMPT and
# not a JOB, so the instrument built to cap spend was silently doubled by the
# thing it could not see.
#
# And run 3 left an ORPHAN PROJECT the same way: the retry re-prestaged,
# creating a second ChatCut project and paying twice for the same setup.
#
# Both are the same gap — per-container state where the job is the unit — so
# both live here, keyed by run id.
JOBSTATE = modal.Dict.from_name("chatcut-jobstate", create_if_missing=True)
WARM = modal.Dict.from_name("chatcut-warm", create_if_missing=True)


def job_state(run_id):
    """Durable per-JOB state that survives a preemption restart."""
    try:
        return dict(JOBSTATE.get(run_id) or {})
    except Exception:                                             # noqa: BLE001
        return {}


def job_state_put(run_id, **kw):
    """Merge into the durable job state. Never raises into the run."""
    try:
        _s = job_state(run_id)
        _s.update(kw)
        JOBSTATE[run_id] = _s
    except Exception:                                             # noqa: BLE001
        pass


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
    _init_tools = {"state": "ABSENT", "why": "no system/init event in the stream"}
    _msg_ids = set()
    calls, errors, turns = [], 0, 0
    # THE REASONING, KEPT. Until 2026-09-15 this function counted thinking
    # deltas and `turn_clock` timed them to the tenth of a second, and NOT ONE
    # WORD was kept anywhere — 112 measured seconds of deliberation per run,
    # unreadable, because stream.jsonl dies with the container. Asked what the
    # agent was thinking about, the only honest answer was "the harness never
    # looked". That is this repo's own rule — a derived signal that is not
    # printed cannot be verified — applied to the most expensive block in the
    # run.
    #
    # It is attached to the assistant EVENT, beside the tool call that event
    # emitted, so "what was it working out before it called this" is a read
    # rather than a join between two numbering schemes that do not line up
    # (classify_stream counts assistant events, turn_clock counts
    # message_start..message_stop; 17 against 8 on the same run).
    reasoning = []
    # THINKING ARRIVES AS DELTAS, NOT AS A BLOCK ON THE ASSISTANT MESSAGE.
    #
    # This collector only read `type == "thinking"` blocks off the `assistant`
    # event and captured ZERO on run 6 — while turn_clock, reading the same
    # file, counted 321 thinking deltas. The run could say turn 7 spent 206
    # SECONDS thinking (53% of all model time) and not one word of what about:
    # the largest single cost in the run, unreadable by construction.
    #
    # With --include-partial-messages the text is in
    # stream_event -> content_block_delta -> delta.thinking, keyed by the
    # block index whose type came from content_block_start. Accumulated here
    # and flushed onto the assistant event that closes the turn.
    _blk_types, _think_buf = {}, []
    # THE RAW WIRE, VERBATIM, BECAUSE TWICE NOW I HAVE GUESSED THE SHAPE.
    #
    # The collector below was written against an assumed delta shape and
    # captured nothing on runs 6 and 7 — 209 and 321 thinking deltas, zero
    # kept — while a synthetic fixture written to the SAME assumption passed.
    # A fixture that agrees with your assumption tests the assumption, not the
    # wire. These are the first few block-start and block-delta lines exactly
    # as they arrived, carried in the durable record so the shape is READ once
    # instead of inferred a third time. Bounded so the record stays small.
    _raw_starts, _raw_deltas = [], []
    _think_tok, _think_deltas = [0], [0]
    _think_tok_total = [0]
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
            if t == "stream_event":
                _inner = ev.get("event") or {}
                _it = _inner.get("type")
                if _it == "content_block_start" and len(_raw_starts) < 8:
                    _raw_starts.append(line[:600])
                elif _it == "content_block_delta" and len(_raw_deltas) < 8:
                    _raw_deltas.append(line[:600])
                if _it == "content_block_start":
                    _blk_types[_inner.get("index")] = (
                        (_inner.get("content_block") or {}).get("type"))
                elif _it == "content_block_delta":
                    if _blk_types.get(_inner.get("index")) == "thinking":
                        _d = _inner.get("delta") or {}
                        _think_buf.append(str(_d.get("thinking")
                                              or _d.get("text") or ""))
                        # THE CONTENT IS NOT ON THE WIRE — READ, NOT GUESSED.
                        # Two collectors captured nothing and both parse paths
                        # were CORRECT: the CLI emits
                        #   {"type":"thinking_delta","thinking":"",
                        #    "estimated_tokens":50}
                        # — an empty string and a token estimate. Verbatim
                        # from run 8's wire sample. So no third collector can
                        # recover the text, and the honest instrument reports
                        # REDACTED with the size rather than ABSENT with a
                        # shrug. The estimate is a real measure and was being
                        # thrown away.
                        _think_tok[0] = max(_think_tok[0],
                                            int(_d.get("estimated_tokens") or 0))
                        _think_deltas[0] += 1
                elif _it == "content_block_stop":
                    _blk_types.pop(_inner.get("index"), None)
            if t == "system" and ev.get("subtype") == "init":
                _tl = ev.get("tools") or []
                _init_tools = {"count": len(_tl),
                               "toolsearch": "ToolSearch" in _tl,
                               "mcp": sum(1 for x in _tl if str(x).startswith("mcp__")),
                               "state": "MEASURED"}
            if t == "assistant":
                turns += 1
                _mid0 = (ev.get("message") or {}).get("id")
                if _mid0:
                    _msg_ids.add(_mid0)
                # THE MESSAGE'S OWN BLOCKS FIRST, THEN THE DELTAS. Either
                # source is legitimate — which one carries the text depends on
                # whether partial messages are on — and taking whichever is
                # non-empty means this cannot go silently blank again if that
                # flag changes.
                _think = " ".join(
                    str(b.get("thinking") or b.get("text") or "")
                    for b in ((ev.get("message") or {}).get("content") or [])
                    if b.get("type") == "thinking").strip()
                if not _think and _think_buf:
                    _think = "".join(_think_buf).strip()
                _think_buf = []
                _think_tok_total[0] += _think_tok[0]
                _turn_think = (_think_tok[0], _think_deltas[0])
                _think_tok, _think_deltas = [0], [0]
                if not _think and _turn_think[1]:
                    # DELTAS ARRIVED AND CARRIED NO TEXT: redacted, not absent.
                    reasoning.append({
                        "turn": turns, "chars": 0, "truncated": False,
                        "text": "", "redacted": True,
                        "est_thinking_tokens": _turn_think[0],
                        "thinking_deltas": _turn_think[1],
                        "tools": [b.get("name") for b in
                                  ((ev.get("message") or {}).get("content") or [])
                                  if b.get("type") == "tool_use"]})
                if _think:
                    # TRUNCATED WITH ITS DENOMINATOR, never silently. A thought
                    # cut at 6000 characters reads as a complete one that
                    # happens to stop.
                    reasoning.append({
                        "turn": turns, "chars": len(_think),
                        "truncated": len(_think) > 6000,
                        "text": _think[:6000],
                        "tools": [b.get("name") for b in
                                  ((ev.get("message") or {}).get("content") or [])
                                  if b.get("type") == "tool_use"]})
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
    return {"assistant_turns": turns,
            "api_calls": len(_msg_ids),
            "init_tools": _init_tools, "tool_calls": len(calls),
            "tool_errors": errors, "identical_repeats": repeats,
            # WHAT IT WAS WORKING OUT, per assistant event, beside the call
            # that event made. A STATE, not a possibly-empty list: a run whose
            # reasoning was never captured and a run that did not think read
            # identically once you are only looking at a list length.
            "reasoning": reasoning,
            # THE EVIDENCE FOR THE NEXT FIX, not a summary of it.
            "stream_shape_sample": {
                "content_block_start": _raw_starts,
                "content_block_delta": _raw_deltas,
                "why": ("verbatim wire lines — the reasoning collector has "
                        "been written against a guessed shape twice; read "
                        "these before writing a third")},
            "reasoning_state": ("MEASURED: %d event(s) carried thinking, "
                                "%d chars" % (len(reasoning),
                                              sum(r["chars"] for r in reasoning))
                                if any(not r.get("redacted") for r in reasoning)
                                else
                                "REDACTED — %d turn(s) carried thinking "
                                "deltas totalling ~%d estimated token(s), and "
                                "the CLI transmits them with an EMPTY text "
                                "field. The content is not on the wire; no "
                                "collector can recover it. Verified against "
                                "run 8's raw delta lines."
                                % (len(reasoning), _think_tok_total[0])
                                if reasoning else
                                "ABSENT — no thinking block reached the "
                                "transcript. Either the model emitted none, or "
                                "this stream has no thinking blocks in it; "
                                "those are different and this line cannot tell "
                                "them apart"),
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
tools. You own the judgment; ChatCut owns the timeline and the render, and the
harness owns every look: it watches the source and your edit for you and sends
the frames. You never import, preview, inspect, export or read files.

THE CRAFT IS MOUNTED, NOT SUMMARISED. What you need is in your context already;
the rest is on disk for a job that needs it:

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

`edit_item` takes `adds`, `updates` and `deletes` together and commits them
atomically — one call places every overlay, card and trim you have decided on.
Vary size, case and position deliberately. Judge the COMPOSED PICTURE the
harness sends back: a successful tool call is not verification.
"""
# REWRITTEN 2026-09-18: the previous block described previews, ffmpeg contact
# sheets, importing the clip, read_script, export and a fifteen-call budget —
# every one dead under rulings 2-4. The vocabulary gate reads every surface now.


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
    # THE SINGLE AGENT'S SURFACE, 2026-09-16. It now DECIDES as well as places,
    # so it authors its own graphics — the harness can no longer prestage a
    # title it does not know. What it still does not get is anything it would
    # spend a turn DISCOVERING: the project, the media, the sound ids and the
    # component contract all arrive in the prefix.
    "edit_item",          # place, and fix by `updates` on the one revision
    "edit_captions",      # captions are a separate surface that owns its text
    "preview_timeline",   # scrub: any frame, any moment, as often as needed —
                          # and views:["transcript"] for the words against the
                          # TIMELINE, mapped through trim, offset and rate
    "read_captions",      # the viewer-facing caption Cards at any frame, with
                          # their timing, layout, line count and overflow
    "inspect_item",       # a named defect may need one item's full state
    "inspect_asset",      # ...and the SOURCE, at source time, with its words —
                          # this is how the one agent watches the footage
    "edit_asset",         # ...or a property on the asset behind it
    # ADDED 2026-09-16 after a live run spent four of its seven tool errors on
    # permission refusals, this one among them. prestage() imports the SOURCE
    # itself, so this is not for the clip — it is for anything the agent
    # decides it needs to bring in. A job the design assigns to the agent must
    # be a job the tool list permits; we advertised the work and forbade the
    # tool, which is `when we advertise a shape, the acceptor must take it`
    # one layer out.
    # import_media LEFT the list 2026-09-17: the harness imports the source
    # and places the base item; the paragraph says so. Eight tools, as ruled.
    "read_project",
    # ── NOT HERE, AND THE ABSENCES ARE THE DESIGN ───────────────────────────
    # create_motion_graphic_from_code: I ADDED THIS AND IT WAS WRONG. The
    #   reasoning was "the harness can no longer prestage a title it does not
    #   know" — but `prestage` registers the WHOLE component registry, 35
    #   components with assetIds, independent of any title. The agent places a
    #   registered component and sets its text through `propertyOverrides`.
    #   Offering the authoring tool contradicted the prefix outright ("you
    #   never author component code"), and resolving a contradiction is
    #   deciding, which is the cost this path exists to remove. It also opened
    #   a route whose validator has a strict contract this lane has measured —
    #   0 of 29 ported blobs loadable — so an agent-authored graphic is more
    #   likely refused than placed.
    # submit_export / track_export: THE HARNESS EXPORTS, after the gate. An
    #   agent told not to export until the gate passes is obeying a preference;
    #   an agent without the tool is a property. This lane's own law, earned
    #   when the prompt said "do not orchestrate" and the agent orchestrated.
    # browse_library: the sound catalogue is in the prefix. Five browse_library
    #   calls went on ONE placement when it was reachable. The GATE reads the
    #   live library — cached for the agent, live for the check.
    # create_project / import_media: the harness prestages both.
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
    create_project and create_motion_graphic_from_code. `import_media` WAS left
    to the agent, and no longer is — this function calls it (create_session +
    the node upload helper) and returns `sourceAssetId`. The sentence that
    said otherwise survived the change and was read as fact on 2026-09-16,
    including by me, while diagnosing a run. Kept as the correction. What
    guessing a schema costs is what
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

    _pt0 = time.time()

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
    _pt = {"project": round(time.time() - _pt0, 2)}
    # ── THE 37 REGISTRATIONS START NOW, ON A POOL, WHILE THE SOURCE UPLOADS ──
    # Arm A (sub-watch-3, 2026-09-17): prestage took 44.3s of a 90s budget,
    # 37 serial create_motion_graphic_from_code calls at that container's
    # ~1.1s round trip. Registration needs only the project id; the import
    # needs only the project id. Neither waits on the other.
    from concurrent.futures import ThreadPoolExecutor
    registered, reg_failed = {}, {}
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

    def _register_one(_i, _n, _c):
        try:
            _r = call("create_motion_graphic_from_code",
                      {"projectId": pid, "name": _n, "code": _c["code"],
                       "width": w, "height": h, "durationInSeconds": 5,
                       "properties": _c["properties"]}, 100 + _i)
            _ov = _c.get("overrides") or {}
            _v = _find(_r, "validation") or {}
            if _v.get("errors"):
                return _n, None, _v["errors"][:2]
            return _n, ({"assetId": _find(_r, "assetId"), "overrides": _ov}
                        if _ov else _find(_r, "assetId")), None
        except Exception as e:                                    # noqa: BLE001
            return _n, None, [f"{type(e).__name__}: {e}"][:1]
    _reg_items = [(_i, _n, _c) for _i, (_n, _c) in enumerate(sorted(_reg.items()))
                  if not (want_components and _n not in want_components)]
    _pool = ThreadPoolExecutor(max_workers=8)
    _reg_futs = [_pool.submit(_register_one, *_it) for _it in _reg_items]
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

    src_asset, _base_id, _sframes = None, None, None
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
        # THE BASE ITEM IS THE HARNESS'S TO PLACE. The whole source on V1
        # from frame 0 is deterministic — the agent was spending an
        # inspect_asset turn to learn the frame count (arm A, 2026-09-17) and
        # once sent 612 frames for a 610.86-frame source, which ChatCut
        # accepted unclamped. The harness knows the duration; it places it.
        _pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                              "format=duration", "-of", "csv=p=0",
                              source_path], capture_output=True, text=True,
                             timeout=60)
        _sdur = float((_pr.stdout or "0").strip() or 0)
        _sframes = int(_sdur * fps)
        if _sframes > 0 and _find(proj, "trackId"):
            _add = {"type": "video", "assetId": src_asset,
                    "trackId": _find(proj, "trackId"), "fromFrame": 0,
                    "durationInFrames": _sframes}
            # THROUGH _mcp_call, WHICH PARSES. The `call` closure returns the
            # raw MCP envelope ({_meta, content, structuredContent}) and
            # final-arch-1 printed "edit_item echoed no id: {'_meta': ..." over
            # an add that had in fact landed. _mcp_call reads the payload the
            # three ways ChatCut returns it and raises if `adds` is absent.
            try:
                _ar = _mcp_call(access_token, "edit_item",
                                {"projectId": pid, "adds": [_add]}, expect="adds")
                for _e in (_ar.get("adds") or []):
                    if isinstance(_e, dict) and _e.get("id"):
                        _base_id = str(_e["id"])
                        break
            except Exception as _bae:                             # noqa: BLE001
                _ar = {"error": "%s: %s" % (type(_bae).__name__, str(_bae)[:160])}
            print("  BASE ITEM       : %s  %d frame(s) of %.2fs on %s"
                  % ("MEASURED id=%s" % _base_id if _base_id else
                     "FAILED — edit_item echoed no id: %s" % str(_ar)[:160],
                     _sframes, _sdur, _find(proj, "trackId")), flush=True)
        else:
            print("  BASE ITEM       : ABSENT — source frames %d, trackId %r"
                  % (_sframes, _find(proj, "trackId")), flush=True)

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
    _pt["import_done_at"] = round(time.time() - _pt0, 2)
    for _f in _reg_futs:
        _n, _val, _err = _f.result(timeout=300)
        if _err:
            reg_failed[_n] = _err
        else:
            registered[_n] = _val
    _pool.shutdown(wait=False)
    _pt["registrations_done_at"] = round(time.time() - _pt0, 2)
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
    _pt["total"] = round(time.time() - _pt0, 2)
    print("  PRESTAGE PHASES : %s" % json.dumps(_pt), flush=True)
    return {"projectId": pid, "timelineId": _find(proj, "timelineId"),
            "trackId": _find(proj, "trackId"), "titleAssetId": aid,
            "sourceAssetId": src_asset, "titles": made,
            "baseItemId": _base_id, "sourceFrames": _sframes,
            "components": registered, "components_refused": reg_failed,
            "editorUrl": _find(proj, "editorUrl"), "phases": _pt}


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
# THE FETCH RULE IS NOW A SERVE RULE, and the old text is the reason.
#
# It used to say: `preview_timeline` returns signed URLs, so download them all,
# tile them with ffmpeg, Read the sheet once. Every word of that was correct
# when written — reading a URL errors, and one Read per frame had cost twelve
# turns on an earlier run. It was also, measured on run 24, the single most
# expensive instruction in the prompt:
#
#     49,501 chars of tool-call payload typed by the agent
#       1,380 (2.8%) was the EDIT — two edit_item calls
#      44,098 (89%) was signed S3 URLs, retyped into curl commands
#     at 6.23s of generation per 1k chars => ~275s TYPING, ~156s RUNNING
#
# The harness now watches for a `preview_timeline` result and fetches what it
# points at, sending the pixels back. So the instruction inverts: the agent
# asks to look, and looking is free. It is NOT told to look less — bounding the
# looking is precisely what Zac reversed.
FETCH_RULE = (
    "YOU DO NOT DOWNLOAD FRAMES. When you call `preview_timeline`, the frames "
    "it names are FETCHED FOR YOU and arrive in your next message as pictures, "
    "in the order the tool returned them. Look at them there.\n"
    "  - do NOT curl, wget or otherwise download a frame URL\n"
    "  - do NOT tile frames with ffmpeg\n"
    "  - do NOT `Read` a frame: `Read` opens local paths, and you already have "
    "the pixels in the conversation\n"
    "None of that is a limit on LOOKING. Ask `preview_timeline` for whatever "
    "frames you want, as often as you want, at whatever moments you think "
    "matter — entrances, exits, the frame after a cut, a band you are unsure "
    "about. Every call is served back to you as pictures. The only thing that "
    "has been taken away is the typing.\n"
    "If a frame you asked for does not arrive as a picture, say so in your "
    "final message — a frame you did not see is not a frame that was fine.\n\n")

TWO_TURN_LOOP = (
    # THE THREE-TURN CONTRACT (Zac, 2026-09-17, rulings 2-4). Rewritten 2026-09-18:
    # the previous text still asked for /work/DONE and /work/DONE2 marks and
    # invited scrubbing with preview_timeline — the marks were retired with the
    # turn machine, the rewatch forbids discovery calls, and h-th-think0's
    # agent spent its turns "never following up" on a contract that no longer
    # existed.
    "THE LOOP IS THREE TURNS, EACH ONE CALL. The harness watches the render "
    "between them and sends you the composed frames; you never fetch, "
    "inspect or preview anything yourself.\n\n"
    "  TURN 1 — PLACE. Everything you need is in this message: the inventory "
    "as pictures, the source as frames with the words against them, and the "
    "brief. Decide every placement and send ONE edit_item call carrying all "
    "of them, each op with its own why inside it.\n\n"
    "  TURN 2 — REVIEW. The next message carries frames of your timeline "
    "with everything on it, the timeline read back, and any fault the "
    "harness found. Judge the COMPOSED PICTURE and fix what is wrong in ONE "
    "edit_item call: a graphic colliding with another or with the captions, "
    "something illegible or off-frame, something on the speaker's face, a "
    "title on the wrong moment, wrong size, drift.\n\n"
    "  TURN 3 — CONFIRM. Frames again. If it is right, your whole reply is the "
    "single word: export. If one thing is still wrong, one more edit_item "
    "call; a fourth call exists only for something that fix broke, and there "
    "is no fifth.\n\n"
    "YOU DO NOT EXPORT and you write no files. The harness reads the timeline "
    "back, checks it, and exports.\n\n")
# TWO_TURN_LOOP_DECIDE WAS HERE AND IS GONE. 3,578 characters of procedure
# that the one-paragraph preamble now says in three sentences. It was already
# unreferenced when this was written — `ast` found zero Load sites — and TWO
# SMOKES WERE STILL CHECKING IT, which is how a dead constant keeps looking
# alive. The plan path keeps TWO_TURN_LOOP; that one is still loaded.


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
    # THE FOURTH ARGUMENT IS THE JSON-RPC MESSAGE ID, NOT A TIMEOUT. Kept as
    # the correction (2026-09-17): a pass "bounding" this call changed 900 to
    # 120 here and wrote a note claiming a 120s bound — the bound was already
    # `urlopen(req, timeout=120)` inside mcp_rpc, and this number never
    # touched it. The sweep's own leg then tested the id. Read mcp_rpc for the
    # bound; this is an id.
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
            # THE JSON, THEN PROSE. Measured 2026-09-17 on a track-creating
            # add: `{"adds":[...]}`, two newlines, then "Motion-graphic item(s)
            # eebe1acc68 now span frames 560–589. Inspect timeline frames..."
            # json.loads raised "Extra data" at char 188, this reader fell
            # through, and FOUR LANDED placements were recorded as
            # "no 'adds'". raw_decode takes the leading object; the sentence
            # stays in `_text` beside it.
            try:
                parsed, _endpos = json.JSONDecoder().raw_decode(t.strip())
                if not isinstance(parsed, (dict, list)):
                    parsed = None
                    continue
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
            # 900, NOT 240. The validation error naming the bad argument was
            # CUT OFF at 240 characters — "Invalid arguments for to" — so the
            # failure reported itself and withheld the one word that mattered.
            # A failure must carry its evidence; truncating the evidence to a
            # tidy length is the same defect as not printing it.
            "First 900 chars: %r"
            % (name, (" (no %r)" % expect) if expect else "",
               sorted(parsed or out)[:12] if isinstance(parsed or out, dict)
               else type(parsed or out).__name__,
               json.dumps(parsed if parsed is not None else out)[:900]))
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
        # NAME WHERE THE QUESTION WENT. On the single-agent path there is no
        # plan, so these two cannot run — and "no plan or no prestage" reads
        # as a broken harness rather than as a check that moved. It moved:
        #   hop 3 (every add became an item)  -> chatcut_gate
        #                                        .check_every_ruling_landed,
        #                                        asked of the RULINGS against
        #                                        the timeline instead of of
        #                                        the plan against the timeline
        #   hop 4 (the item carries what was
        #          named)                     -> chatcut_gate
        #                                        .check_card_props_resolve,
        #                                        for cards. THE OTHER FAMILIES
        #                                        ARE NOT COVERED, and that is
        #                                        a gap, not a delegation.
        res["hop3"]["why"] = (
            "no plan — superseded by GATE B check_every_ruling_landed, which "
            "asks the same question of the rulings against the timeline")
        res["hop4"]["why"] = (
            "no plan — GATE B check_card_props_resolve covers CARDS only; "
            "whether a text/sfx/zoom item carries what its ruling named is "
            "UNCHECKED on this path")
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
                           "marker. UNCHECKED. First 900 chars of what it did "
                           "return: %r"
                           % (r["from"], str((det or {}).get("_text") or "")[:900])}
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


# ── GATE B: THE HARNESS READS CHATCUT BACK, AND THE AGENT DOES NOT EXPORT ────
# Ruled by Zac 2026-09-16 with the single agent: the cross-checks are harness
# checks between the placement call and the export, not things the agent asks
# itself.

RECORD_SPEC = "/work/spec.json"
RECORD_RULINGS = "/work/rulings.json"
RECORD_PATH = "/work/record.json"     # honoured if written; no longer asked for
DEFAULT_THINK_TOKENS = 3000          # per call; the record Write thought for 546s
TURN_CAP = 4                         # three strategic turns + one contingency; the fifth is terminal
TURN_LAW_S = 120                     # a TURN over this is LOGGED (law miss); only the RUN bound kills (ruling 3).
                                     # Was TURN_TIMEOUT_S=120 and terminal: h-th-think0's placement turn was
                                     # killed mid-stream at 120s while the model was still generating — a
                                     # bound of my own, not a ruling, turned a slow turn into a dead run.
RUN_TIMEOUT_S = 300                  # was 1,500 (Zac, 2026-09-17); terminal, never a retry
CACHE_FRACTION = 0.95                # every call after the first reads >= this x the prefix
LAW_WALL_S = 120                     # a run over this is logged as a law miss with its stage line
# The agent's "I have finished placing" signal. A Write, because
# the agent already has Write and a new tool would be a new
# schema entry — and a capability in the schema will be used.
ABSENT_S = "ABSENT"
# DONE_MARK / DONE2_MARK retired 2026-09-18 with the withhold they signalled.
# HOW LONG THE HARNESS WAITS FOR /work/DONE2 BEFORE REWATCHING ANYWAY. Chosen
# against the measured shape of turn 2: the fix batch is one round of
# edit_item calls, and the slowest observed review turn was 125.8s. 420s is
# well past a fix batch and well short of the 1500s run timeout, so a stalled
# turn 2 costs a bounded wait instead of the whole run.
REWATCH2_WAIT_S = 420
# THE STREAM GOING QUIET IS ITSELF A FAILURE, AND IT HAD NO BOUND.
#
# Measured on the blue-shirt run: the agent produced events for 293s and then
# NOTHING for 1,207s — 80.6% of the wall at 0.03 cores — until the 1,500s
# watchdog. It had ended a turn without writing /work/DONE (it had nothing to
# place); the harness waits for /work/DONE before sending anything; the CLI
# waits on stdin. Both sides waiting, neither bounded.
#
# I had built a bound for the SECOND mark and never asked whether the first had
# the same hole. It did. The rule is the one that keeps recurring here: fixing
# an instance is not fixing the class. Every wait in this harness now carries a
# bound — the MCP transport at 120s, the export poll at ~236s, the detector
# join at 25s, the run at 1,500s, and this.
#
# 240s is generous against the longest turn ever measured here (97.6s) and far
# short of the run timeout, so a deadlock costs a bounded wait instead of the
# whole budget.
STREAM_IDLE_S = 240

# THE TOOLS THAT CHANGE THE TIMELINE. A "batch" is an assistant turn carrying
# at least one of these; everything else (looking, reading, ToolSearch) is
# free and does not advance the turn machine.
MUTATING_TOOLS = ("edit_item", "edit_captions", "edit_asset", "split_item",
                  "detach_audio", "smooth_audio", "apply_script")

# THE SPEND CEILING, IN CUMULATIVE CACHE-READ TOKENS.
#
# Run 4 read 33,848,937 tokens across 96 assistant turns — $10.15 of read
# inside a $25.97 run that was supposed to take three turns. The ceiling is
# what makes "three turns" survivable when the shape fails anyway.
#
# THE ARITHMETIC, STATED BECAUSE IT DISAGREES WITH THE ESTIMATE. Run 4's mean
# read was 352,593 tokens per assistant turn (33,848,937 / 96), and an
# assistant turn is not a "turn" in the loop's sense: each tool call costs TWO
# — one to emit it, one to read its result. So three LOOP turns with their
# tool results is ~7 assistant turns, ~2.5M read, not the ~670k that three API
# calls would cost. A 670k ceiling would kill every legitimate run inside
# turn 2. This is set to permit the intended shape with headroom and to kill
# anything on run 4's trajectory an order of magnitude early.
READ_TOKEN_CEILING = 2_500_000
# HOW THE HARNESS WAITS ON A CLOUD RENDER. Sums to ~240s, the same budget the
# fixed `sleep(6) x 40` loop had, but front-loaded: a render that finishes
# quickly is picked up in ~1s instead of ~6s. Measured locally, everything
# AFTER the download costs 1.6s per rewatch (0.2s motion decode, 0.6s for 18
# frame seeks, 0.8s scan) — so poll granularity, not our own processing, was
# the harness-side latency worth removing.
EXPORT_POLL_SCHEDULE = ([1] * 6 + [2] * 6 + [3] * 6 + [4] * 5 + [6] * 30)


def derive_record(items, beats, base_item_id=None, why_text=""):
    """The record, READ OFF THE TIMELINE. -> {spec, rulings}

    THE RECORD WRITE IS GONE (Zac, 2026-09-17). The agent's one Write of
    rulings-and-spec was the 546s turn — a plan before the placement, in the
    record's clothes. What a read-back cannot carry is only the WHY, and that
    is one line per item after placing, taken from the reply text.
    A ruling per beat: the families that landed inside the beat's window
    (item start in source seconds via an untrimmed base), `nothing` where
    none did. Families come from what the item IS: a non-base video item is a
    cut; a motion-graphic whose asset name starts `caption:` is a caption, any
    other is a card; an effect is a zoom; audio is sfx; a transition is a
    transition.
    """
    _fam = []
    for i in (items or []):
        kind = str(i.get("itemType") or "")
        if str(i.get("id") or "").replace("-", "")[:10] == str(base_item_id or "").replace("-", "")[:10]:
            continue
        _as = i.get("asset") if isinstance(i.get("asset"), dict) else {}
        name = str(_as.get("name") or "")
        fam = ("cut" if kind == "video" else
               ("caption" if name.startswith("caption:") else "card") if kind == "motion-graphic" else
               "zoom" if kind == "effect" else "sfx" if kind == "audio" else
               "transition" if kind == "transition" else None)
        if not fam:
            continue
        tr = i.get("timelineRange") or {}
        try:
            t0 = int(tr.get("fromFrame")) / 30.0
        except (TypeError, ValueError):
            continue
        _fam.append((t0, fam, str(i.get("id") or "")[:8], name))
    rulings = []
    for b in (beats or []):
        a, z = float(b.get("t_start", 0)), float(b.get("t_end", 0))
        landed = [(f, iid, nm) for t0, f, iid, nm in _fam if a <= t0 < z]
        rulings.append({"beat": int(b.get("i", len(rulings))),
                        "treatment": sorted({f for f, _, _ in landed}) or ["nothing"],
                        "items": [iid for _, iid, _ in landed],
                        "derived": True})
    spec = {"mode": "derived", "why": (why_text or "").strip()[:4000] or None,
            "derived_from": "%d item(s), %d beat(s)" % (len(items or []), len(beats or []))}
    return {"spec": spec, "rulings": rulings}


def read_record(spec_path=RECORD_SPEC, rulings_path=RECORD_RULINGS,
                record_path=RECORD_PATH):
    """({spec, rulings}, why) — THE DURABLE ARTEFACT, read off disk.

    Zac, 2026-09-16: "And the durable artefact stays. Write the rulings and the
    ledger the same way — that's how the 43% was found, and losing it means
    losing the ability to diagnose anything."

    The single agent writes both with the Write tool; the harness reads them
    here and the gate refuses a run that recorded neither. It is deliberately
    NOT inferred from the timeline: what is on the timeline is what the agent
    DID, and the spec is what it MEANT — the 43% was diagnosed by comparing the
    two, and a record reconstructed from the placements can only ever agree
    with them.

    EVERY FAILURE IS NAMED RATHER THAN EMPTY. A missing file, a malformed file
    and an agent that ruled nothing are three different facts, and `{}` for all
    three is how "the agent recorded nothing" becomes indistinguishable from
    "the harness could not read it".
    """
    out, why = {"spec": None, "rulings": None}, []
    # ONE FILE FIRST. Two Writes were two API calls (final-arch-1); the
    # paragraph now asks for one record carrying both keys. The two-file
    # shape stays readable so an older run's record still parses.
    _one = None
    if record_path and os.path.exists(record_path):
        try:
            with open(record_path, encoding="utf-8") as fh:
                _one = json.load(fh)
            if not isinstance(_one, dict):
                why.append("record.json FAILED: expected an object, got %s"
                           % type(_one).__name__)
                _one = None
            else:
                why.append("record.json MEASURED (one file)")
        except Exception as e:                                    # noqa: BLE001
            why.append("record.json FAILED to parse: %s" % str(e)[:120])
            _one = None
    for key, path in (("spec", spec_path), ("rulings", rulings_path)):
        if isinstance(_one, dict) and key in _one:
            val = _one[key]
        elif not os.path.exists(path):
            why.append("%s ABSENT (%s was never written)" % (key, path))
            continue
        else:
            try:
                with open(path, encoding="utf-8") as fh:
                    val = json.load(fh)
            except Exception as e:                                # noqa: BLE001
                why.append("%s FAILED to parse: %s" % (key, str(e)[:120]))
                continue
        # THE SHAPE IS CHECKED HERE, where the file is still in hand. A dict
        # iterated as a list yields its KEYS — strings — and this lane has
        # already lost a run to `'str' object has no attribute 'get'` after
        # printing a plausible count on the way to the crash.
        if key == "rulings" and not isinstance(val, list):
            if isinstance(val, dict) and isinstance(val.get("rulings"), list):
                val = val["rulings"]
            else:
                why.append("rulings FAILED: expected a list, got %s"
                           % type(val).__name__)
                continue
        if key == "spec" and not isinstance(val, dict):
            why.append("spec FAILED: expected an object, got %s"
                       % type(val).__name__)
            continue
        out[key] = val
        why.append("%s MEASURED (%s)"
                   % (key, "%d ruling(s)" % len(val) if key == "rulings"
                      else "mode=%r" % val.get("mode")))
    return out, "; ".join(why)


def read_back(tok, stage):
    """Every item on the timeline, plus the catalogues. THE HARNESS'S OWN READ.

    TWO PROPERTIES, AND THEY ARE THE WHOLE POINT OF THE FUNCTION.

    NO WINDOW. `preview_timeline` takes `tracks`, `fromFrame` and `toFrame`.
    An agent that chooses the window chooses what the gate sees, so this passes
    none of them — every track, every frame. Reading the agent's own preview
    call would have been cheaper and would have handed the agent the gate.

    AND IT PAGES. The existing `_chain_items` asks for `limit: 100` and takes
    what comes. A timeline with more entries than that reads SHORT, and a short
    read makes the reconciliation report placements that landed as never having
    landed — a truncated list presented as a total, which is a standing rule
    here and would have fired as a false WITHHOLD on exactly the busy edits
    this lane is trying to produce. `nextOffset` is followed to exhaustion and
    a page cap that is hit is FAILED, never a quiet stop.
    """
    out = {"items": None, "fps": None, "library_ids": None,
           "component_props": None, "read_why": ""}
    ents, off, pages = [], 0, 0
    try:
        while True:
            pages += 1
            if pages > 40:
                out["read_why"] = ("timeline paging did not terminate after "
                                   "40 pages (%d entries so far) — FAILED "
                                   "rather than truncated" % len(ents))
                return out
            tl = _mcp_call(tok, "preview_timeline",
                           {"projectId": stage["projectId"],
                            # 100, NOT 200. The only other preview_timeline
                            # call in this file sends 100 and works; this one
                            # sent 200 and came back `MCP error -32602: Input
                            # validation error: Invalid arguments`, so the
                            # harness could not read its own timeline back and
                            # the review had no window to render — on a run
                            # where the agent had successfully placed 8 items.
                            # Two call sites, two limits, one schema.
                            "views": ["timeline"], "limit": 100,
                            **({"offset": off} if off else {})},
                           expect="timeline")
            blk = (tl.get("timeline") or {})
            ents += [e for e in (blk.get("entries") or [])
                     if e.get("kind") == "item"]
            nxt = blk.get("nextOffset")
            if not nxt or nxt == off:
                break
            off = nxt
        out["items"] = ents
        # FROM THE CANVAS, THEN THE STAGE, THEN NAMED. My first line here read
        # `FPS_DEFAULT`, which lives in plan_for_chatcut.py and does not exist
        # in this module — a NameError on every gate run, caught by pyflakes
        # before it shipped rather than by a dead run.
        out["fps"] = ((tl.get("canvas") or {}).get("fps")
                      or (blk.get("canvas") or {}).get("fps")
                      or stage.get("fps") or 30)
        out["read_why"] = "%d item(s) over %d page(s)" % (len(ents), pages)
    except Exception as e:                                        # noqa: BLE001
        out["read_why"] = "preview_timeline FAILED: %s" % (str(e)[:200],)
        return out
    # THE SOUND LIBRARY, LIVE. The agent is given the cached catalogue in its
    # prefix so it never spends a turn searching; the GATE reads the live one,
    # because a cached catalogue and a live one are indistinguishable right up
    # until they are not.
    try:
        lib = _mcp_call(tok, "browse_library",
                        # 30 IS THE SCHEMA MAX, read from the live tool
                        # definition on 2026-09-17, not from memory. This sent
                        # 200 — the same defect as preview_timeline's limit,
                        # in a call nobody had exercised, and it would have
                        # failed -32602 the first time the sound library was
                        # read.
                        {"category": "sound-effects", "limit": 30},
                        expect="items")
        out["library_ids"] = [str(x.get("id") or "").split(":")[-1]
                              for x in (lib.get("items") or [])]
    except Exception as e:                                        # noqa: BLE001
        out["read_why"] += "; browse_library FAILED: %s" % (str(e)[:120],)
    return out


def caption_band(tok, stage):
    """(band, why) — where ChatCut's caption layer sits, as y fractions.

    THE THIRD OCCUPANT, AND NOTHING READ IT. hop 6 checks a graphic against the
    face and the source's own burned-in text; hop 5 checks it against other
    TRACK ITEMS. ChatCut's captions are neither — `edit_captions` is a separate
    surface with no item — so a card landing on the captions passed both.

    THE SHAPE IS NOT VERIFIED and this says so rather than guessing. Our own
    component's measured caption band is a fact about a DIFFERENT renderer, so
    using it here would be a guess about ChatCut wearing a measurement's
    clothes. Several plausible keys are tried; when none parse, the result is
    ABSENT WITH THE KEYS THAT DID COME BACK, which is what makes the first real
    run able to settle it instead of another reading of the docs.
    """
    try:
        r = _mcp_call(tok, "read_captions", {"projectId": stage["projectId"]})
    except Exception as e:                                        # noqa: BLE001
        return None, "read_captions FAILED: %s" % (str(e)[:160],)
    if not isinstance(r, dict):
        return None, "read_captions returned %s" % type(r).__name__
    cards = (r.get("cards") or r.get("captions") or r.get("items") or [])
    if not cards:
        return None, ("read_captions returned no cards (keys: %s) — either "
                      "captions are off or the reader is looking in the wrong "
                      "place" % sorted(r)[:8])
    for c in cards:
        if not isinstance(c, dict):
            continue
        lay = c.get("layout") or c.get("position") or c
        for k0, k1 in (("y0", "y1"), ("top", "bottom"),
                       ("yStart", "yEnd"), ("y", "height")):
            a, b = lay.get(k0), lay.get(k1)
            if a is None or b is None:
                continue
            try:
                a, b = float(a), float(b)
            except (TypeError, ValueError):
                continue
            if k1 == "height":
                b = a + b
            # normalise pixels to fractions if they look like pixels
            if b > 1.5:
                b, a = b / 1920.0, a / 1920.0
            if 0.0 <= a < b <= 1.0:
                return (a, b), ("MEASURED from read_captions %r/%r on %d card(s)"
                                % (k0, k1, len(cards)))
    return None, ("%d caption card(s) and none carried a readable band — keys "
                  "seen: %s" % (len(cards),
                                sorted(cards[0])[:10]
                                if isinstance(cards[0], dict) else "?"))


def gate_b(tok, stage, rulings, spec, source_duration_s=None,
           prefetched=None, bands=None, beats=None):
    """Read ChatCut back and check the placements against it. -> report.

    `source_duration_s` is None when the probe did not read one — NOT 0.0. A
    duration nobody measured and a zero-length clip are different facts, and
    the cutaway address check treats the first as ABSENT rather than failing
    every cutaway for being past the end of a zero-second source.
    """
    import sys as _sys
    _sys.path.insert(0, "/root")
    import chatcut_gate as _g
    # ONE READ FOR THE WHOLE POST-STREAM PHASE. The pixel hops run first and
    # need the same item list; two readers disagreeing about what is on the
    # timeline is how a placement reads as missing to one check and present to
    # another. `prefetched` is that read, never the agent's.
    st = prefetched if prefetched is not None else read_back(tok, stage)
    st["spec"] = spec
    st["bands"] = bands
    st["beats"] = beats          # a ruling's anchor by beat index (gate, 2026-09-17)
    st["source_duration_s"] = source_duration_s
    rep = _g.gate(rulings, st)
    rep["read_why"] = st.get("read_why")
    # THE ITEMS THE GATE ACTUALLY REASONED ABOUT, for hops 5 and 6 to share.
    # Private (leading underscore) and stripped before the record is written —
    # a full item list in the persisted JSON is bulk nobody reads.
    rep["_items"] = st.get("items")
    # PRINTED IN FULL, WITH THE EVIDENCE. `report_lines` was written to be shown
    # to the AGENT and had no caller at all — the gate runs after the stream
    # ends, so there is nobody left in the conversation to show it to. A
    # producer with no consumer, in the module built this afternoon.
    #
    # It goes to the run log instead, which is where it is actually read, and
    # it carries each finding's `read:` line — a check that cannot say what it
    # READ makes the next run the debugger. The previous version truncated the
    # why at 150 chars and dropped the evidence entirely.
    print("  GATE B          : %s  (%s)" % (rep["verdict"], st.get("read_why")),
          flush=True)
    for _l in _g.report_lines(rep):
        print("     " + _l, flush=True)
    return rep


def harness_export(tok, stage):
    """THE EXPORT THE AGENT NO LONGER HAS.

    `submit_export` is out of the allowlist, so this is the only path to a
    deliverable and it runs AFTER the gate. Instructing the agent not to export
    until the gate passes would have been a preference; removing the tool makes
    it a property. Same law that made "do not go looking" true by withholding
    browse_library rather than by asking.
    """
    try:
        # THE ID COMES BACK IN THE TEXT, NOT IN A KEY. Measured 2026-09-16: the
        # export SUBMITTED — "Submitted export.\n  renderId: c93543eec1\n
        # status: rendering" — and this reader reported FAILED because it
        # demanded a JSON `renderId` and the server answers in `_text`. A
        # SUCCESSFUL call read as a failure, which is the family this repo is
        # built against running in the other direction: the run reported no
        # export while ChatCut was rendering one.
        # `_edit_frames` already regexes the blob; this does the same, and
        # NAMES the absence rather than returning a None that reads as an id.
        ex = _mcp_call(tok, "submit_export",
                       {"projectId": stage["projectId"]}, expect=None)
        _blob = json.dumps(ex) + str(ex.get("_text") or "")
        _m = re.search(r"renderId[\"':\s]+([0-9a-f-]{8,})", _blob)
        if not _m:
            return {"state": "FAILED",
                    "why": "submit_export named no renderId anywhere in its "
                           "response: %s" % _blob[:400]}
        return {"state": "MEASURED", "renderId": _m.group(1)}
    except Exception as e:                                        # noqa: BLE001
        return {"state": "FAILED", "why": str(e)[:200]}


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
    # THE PLAN WAS NEVER USED HERE. `man = vc.plan_manifest(plan)` was assigned
    # and never read — pyflakes said so all day and I read the warning four
    # times as pre-existing noise. The mechanism is per-track renders off
    # `items`, which is timeline state, so guarding on a plan turned the ONE
    # check that can see two placements over each other OFF for the entire
    # single-agent path. Four of seven hops went ABSENT when the plan was
    # removed; this is the one that did not have to.
    if not (stage and items):
        out["why"] = "no prestage or no items"
        return out
    pid = stage["projectId"]

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


def verify_hop6_clear(plan, source="/work/source.mp4", items=None,
                      caption_band=None):
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
    out = {"state": "ABSENT", "why": "not attempted", "detail": [],
           # THE MEASURED BAND PER PLACEMENT, EXPORTED. It was computed here
           # and thrown away, so "does the placement sit where the ruling said"
           # had no source of truth — a derived signal that is not published
           # cannot be verified by anything downstream.
           "bands": {}}
    # FROM THE PLAN WHEN THERE IS ONE, FROM THE TIMELINE WHEN THERE IS NOT.
    # This guarded on `plan`, so "nothing sits on the speaker's face or on the
    # source's own burned-in text" was OFF for every single-agent run —
    # silently, as one ABSENT hop among six others.
    if not ((plan or items) and os.path.exists(source)):
        out["why"] = "no plan, no items, or no source on disk"
        return out
    if plan:
        man = vc.plan_manifest(plan)
    else:
        import chatcut_gate as _cg6
        man = _cg6.manifest_from_items(items)
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

    # THE CAPTION BAND, MEASURED OR NAMED ABSENT — never assumed. It is passed
    # in from `read_captions`, because ChatCut's caption layer is ChatCut's and
    # our own component's measured band is a fact about a DIFFERENT renderer.
    _cap_bands = set()
    if caption_band:
        try:
            _cap_bands = set(vc.bands_touched(
                (float(caption_band[0]), float(caption_band[1])),
                fb.band_to_fraction))
        except Exception:                                         # noqa: BLE001
            _cap_bands = set()
    out["caption_band"] = (
        {"band": list(caption_band), "names": sorted(_cap_bands)}
        if _cap_bands else
        {"state": "ABSENT",
         "why": "no caption band was read, so whether a graphic sits on the "
                "captions is UNCHECKED — not clear"})
    bad = []
    for r in vis:
        t0 = r["from"] / 30.0
        t1 = (r["from"] + (r["dur"] or 0)) / 30.0
        occ = fb.face_occupied_bands(traj, t0, t1)
        b = vc.band_of(r, meas)
        out["bands"][str(r["slot"])] = {
            "band": [round(b[0], 4), round(b[1], 4)],
            "names": sorted(vc.bands_touched(b, fb.band_to_fraction))}
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
        # THE CAPTION LAYER IS THE THIRD OCCUPANT, and it was counted by
        # nothing. The comment above defers card-vs-caption to hop 5, which is
        # true only while the captions are a TRACK ITEM hop 5 can hide and
        # re-render. On the single-agent path they are `edit_captions` — a
        # separate surface with no item — so hop 5 cannot see them and this
        # skipped them. A card landing on the captions passed both checks.
        _capnames = set(_cap_bands or ())
        for name in sorted(mine & (occ | bbands | _capnames)):
            bad.append((r["slot"], name,
                        "face" if name in occ else
                        ("source text" if name in bbands else "the captions"),
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


def _audio_lag_ms(a_path, b_path, at=11.0, dur=3.0, b_at=None):
    """How late a_path's audio is against b_path's, in ms. None if unmeasurable.

    Envelope cross-correlation at 2ms resolution. A source-against-itself
    control reads exactly 0 at r=1.000, so the instrument has no bias of its
    own — which is the only reason a 42ms reading can be believed.
    """
    def env(f, _at=None):
        p = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss",
             "%.3f" % (at if _at is None else _at), "-t", "%.3f" % dur,
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
    # SEPARATE OFFSETS, BECAUSE AN EDIT IS NOT ITS SOURCE. Correlating both
    # files at the same second is right for the DELIVERED file against the
    # source it was cut from only when nothing was removed. On an edit with
    # cuts, timeline 11.0s is some OTHER source second, and correlating them
    # measures the cut, not the sync — it would report a large "lag" on a
    # perfectly synced edit. The caller maps a timeline moment back through
    # the kept spans and passes the source second as b_at.
    A, B = env(a_path), env(b_path, b_at if b_at is not None else at)
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
# NO LONGER NINE. That was `preview_timeline`'s cap — and the cap itself is no
# longer nine either: read from tools/list on 2026-09-16 it is 25, for both
# viewerFrames and viewerFrameCount. Pass 2 samples a real rendered file
# instead, so the number is chosen for what the agent needs to see rather than
# for what the tool would give — but the note is corrected because a stale
# claim about someone else's limit is the thing that kept the PLAN asking for
# nine review frames long after twenty-five were available. Half evenly spaced so nothing is unwatched, half on the biggest
# frame-to-frame changes, which is where entrances, exits and collisions are.
EDIT_FRAMES_N = 25                   # preview_timeline's cap, re-read 2026-09-16


SHEET_PER = 8            # review default; watch_asset tiles 20 (source and edit)
SHEET_COLS = 4
SHEET_CELL_W = 280       # 1120 x ~995 px -> ~1.5k tokens a sheet; three under 5k (Zac, 2026-09-17)


def _deep_find(o, key):
    """First value under `key` anywhere in a nested envelope, or None."""
    if isinstance(o, dict):
        if key in o and o[key] not in (None, ""):
            return o[key]
        for v in o.values():
            r = _deep_find(v, key)
            if r is not None:
                return r
    elif isinstance(o, list):
        for v in o:
            r = _deep_find(v, key)
            if r is not None:
                return r
    return None


def tile_sheets(entries, out_dir, per_sheet=SHEET_PER, cols=SHEET_COLS,
                cell_w=SHEET_CELL_W):
    """Frames -> a few contact sheets with the label burned in. -> [png paths]

    UNDER 20 BLOCKS PER MESSAGE. The API's cache lookup walks back ~20 content
    blocks from a breakpoint; a user message of 14 or 24 image blocks pushes
    the previous breakpoint out of reach and the NEXT call rewrites the whole
    prefix (final-arch-2: calls 2, 4 and 5 read 0 / 120k / 120k and wrote ~300k
    each, ~$5.8 of the run's write). Eight frames per sheet turns 24 frames
    into three blocks. Cells keep the frame's aspect; the label (a timestamp or
    a frame number) is burned top-left so the agent can still name a moment.
    `entries` are [(label, path)]; an unreadable frame leaves an empty cell
    with its label, never a silently shorter sheet.
    """
    from PIL import Image, ImageDraw
    os.makedirs(out_dir, exist_ok=True)
    out = []
    entries = list(entries or [])
    for si in range(0, len(entries), max(1, per_sheet)):
        chunk = entries[si:si + per_sheet]
        ims = []
        for lbl, pth in chunk:
            try:
                im = Image.open(pth).convert("RGB")
            except Exception:                                     # noqa: BLE001
                im = None
            ims.append((lbl, im))
        cell_h = max((int(cell_w * im.height / max(1, im.width)) for _, im in ims if im is not None),
                     default=int(cell_w * 16 / 9))
        rows = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (16, 16, 16))
        draw = ImageDraw.Draw(sheet)
        for k, (lbl, im) in enumerate(ims):
            x, y = (k % cols) * cell_w, (k // cols) * cell_h
            if im is not None:
                sheet.paste(im.resize((cell_w, cell_h)), (x, y))
            draw.rectangle([x, y, x + 8 + 9 * len(str(lbl)), y + 22], fill=(0, 0, 0))
            draw.text((x + 4, y + 4), str(lbl), fill=(255, 255, 0))
        fp = os.path.join(out_dir, "sheet_%02d.jpg" % (len(out) + 1))
        sheet.convert("RGB").save(fp, "JPEG", quality=85, optimize=True)
        out.append(fp)
    return out


def watch_asset(tok, asset_id, dur_s, out_dir, fps=2.0, per_sheet=20, cols=5,
                cell_w=180, rpc=None):
    """Watch an asset THROUGH ChatCut: inspect_asset, dense, native, aligned.

    ONE INSTRUMENT FOR SEEING (Zac, 2026-09-17): the references were watched
    this way, the source is watched this way before placing, and the composed
    edit is watched this way at each rewatch. No ffmpeg stills, no second
    pipeline. Exact `sourceTimesMs` at `fps` (25 per call, the schema's cap),
    the editor's own timecode strip under every frame, and transcript rows for
    up to six ranges covering the clip, so the words sit beside the frames
    they were said over. Tiled 20 to a sheet for cost: 40 frames of a 20s
    source are two sheets.
    -> {"sheets": [png], "frames": n, "times": [s], "transcript": str,
        "state": MEASURED|ABSENT|FAILED, "why": str}
    `rpc` is injectable so a check can drive this without ChatCut.
    """
    import chatcut_reference as _cr
    rpc = rpc or (lambda args, mid: mcp_rpc(tok, "tools/call",
                                            {"name": "inspect_asset", "arguments": args}, mid))
    out = {"sheets": [], "frames": 0, "times": [], "transcript": "",
           "state": "ABSENT", "why": "not attempted"}
    if not asset_id or not dur_s or dur_s <= 0:
        out["why"] = "no asset id or duration (%r, %r)" % (asset_id, dur_s)
        return out
    step = 1.0 / float(fps)
    times = [round(t, 3) for t in
             [i * step for i in range(int(dur_s / step) + 1)] if t <= dur_s - 0.5]
    ranges, nr = [], min(6, max(1, int(round(dur_s / 4.0))))
    for k in range(nr):
        ranges.append({"startMs": int(k * dur_s * 1000 / nr),
                       "endMs": int((k + 1) * dur_s * 1000 / nr)})
    urls, tx = [], []
    for ci in range(0, len(times), 25):
        chunk = times[ci:ci + 25]
        args = {"assetId": asset_id, "sourceTimesMs": [int(round(t * 1000)) for t in chunk],
                "includeTimecode": True}
        if ci == 0:
            args["transcriptRangesMs"] = ranges
        try:
            r = rpc(args, 700 + ci)
        except Exception as e:                                    # noqa: BLE001
            out["state"], out["why"] = "FAILED", "inspect_asset: %s: %s" % (type(e).__name__, str(e)[:160])
            return out
        if r.get("error"):
            out["state"], out["why"] = "FAILED", "inspect_asset error: %s" % str(r["error"])[:200]
            return out
        urls += _cr.frame_urls(r)
        if ci == 0:
            tx.append(_cr.transcript_lines(_cr.structured(r)))
    got, fst = _cr.fetch(urls, out_dir, cap=len(times) + 5)
    if not got:
        out["state"], out["why"] = "ABSENT", "inspect_asset returned %d frame url(s); %s" % (len(urls), fst)
        return out
    entries = [("%.1fs" % times[i] if i < len(times) else "?", pth) for i, (_u, pth) in enumerate(got)]
    out["sheets"] = tile_sheets(entries, os.path.join(out_dir, "sheets"), per_sheet=per_sheet,
                                cols=cols, cell_w=cell_w)
    out["frames"] = len(got)
    out["times"] = times[:len(got)]
    # THE RANGE LINES ONLY: the per-word timings repeat what the beats block
    # already carries, at ~1k tokens (measured 2026-09-17).
    out["transcript"] = "\n".join(ln for ln in "\n".join(tx).splitlines()
                                  if not ln.strip().startswith("word timings"))
    out["state"] = "MEASURED"
    out["why"] = "%d frame(s) at %.1ffps over %.1fs -> %d sheet(s); %s" % (len(got), fps, dur_s, len(out["sheets"]), fst)
    return out


def upload_asset(tok, pid, path):
    """The rendered edit into the project's media pool. -> assetId or None.

    The same import path prestage uses for the source (import_media session +
    the plugin's upload helper), so a rewatch can be served through
    inspect_asset like everything else the agent sees.
    """
    sess = mcp_rpc(tok, "tools/call", {"name": "import_media",
                                       "arguments": {"action": "create_session", "projectId": pid}}, 40)
    _tok = _deep_find(sess, "token")
    _ep = _deep_find(sess, "endpoint")
    if not (_tok and _ep):
        raise RuntimeError("import session returned no token/endpoint: %s" % str(sess)[:200])
    helper = ("/root/.claude/plugins/cache/chatcut-inc/chatcut/1.10.12"
              "/skills/asset-import/scripts/upload-media.mjs")
    _out = path + ".import.json"
    r = subprocess.run(["node", helper, "--token", _tok, "--endpoint", _ep,
                        "--input", path, "--json-out", _out],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError("upload helper exited %d: %s" % (r.returncode, (r.stderr or "")[-300:]))
    return _deep_find(json.load(open(_out, encoding="utf-8")), "assetId")


def _img_block(path, media=None):
    """An image block; the media type follows the file's extension unless
    given. Sheets became JPEG on 2026-09-17: PNG sheets at ~1.5 MB each put
    call 4 of h-th-think0 over the API's 32 MB request limit and the CLI
    pruned the watch's first-message images — 66,764 tokens rewritten."""
    if media is None:
        media = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    with open(path, "rb") as fh:
        return {"type": "image",
                "source": {"type": "base64", "media_type": media,
                           "data": base64.b64encode(fh.read()).decode()}}


def _message(blocks_and_text):
    """A stream-json user message from an ordered list of blocks."""
    return {"type": "user", "message": {"role": "user",
                                        "content": blocks_and_text}}


def source_beats(tok, stage, dur_s, wait_s=90):
    """The SPOKEN WORDS against source time. -> ([beat], state, why).

    THE CONSUMER WAS ALREADY WRITTEN AND NOTHING EVER FED IT. `pass1_message`
    has carried a "THE TRANSCRIPT, against those frames" block the whole time,
    keyed on `t_start`/`t_end`/`text`, and on this path `beats` came only from
    a `transcript` argument nobody passes. So the agent was handed 14 stills of
    a 20.4s NARRATION clip and asked to derive every moment from pictures —
    with no words, no dead air and no cut points, because nothing in this file
    computes any of them.

    Measured on runs 6 and 7: one turn of 206s and one of 277s, no tool call,
    the largest single cost in each run. Handing over the words it is deriving
    is SUBTRACTION, not a new capability.

    THE WORDS ARE ALREADY IN CHATCUT. `prestage` imports the source, so the
    asset exists; `trigger_transcript` is idempotent and returns unchanged for
    complete/transcribing states; `inspect_asset` with `transcriptRangesMs` is
    the ONLY input that returns transcript rows, at most 6 ranges covering at
    most 120 seconds, each row carrying its own timestamps. All three read from
    the live tool definitions, not from memory.

    ABSENT IS NAMED, NEVER EMPTY. A clip with no speech and a transcript that
    did not finish are different facts and the agent is told which — a silent
    `[]` would put it straight back to deriving, with nothing saying why.
    """
    _aid = (stage or {}).get("sourceAssetId")
    if not _aid:
        return [], ABSENT_S, "no source asset to transcribe"
    try:
        _mcp_call(tok, "trigger_transcript",
                  {"asset": _aid, "projectId": stage["projectId"]})
    except Exception as e:                                        # noqa: BLE001
        return [], "FAILED", "trigger_transcript: %s" % str(e)[:160]
    # RANGES ARE CAPPED BY THE SCHEMA: 6 ranges, 120s total. A 20s clip is one
    # range; anything longer is chunked rather than silently truncated.
    _ms = int(max(1.0, float(dur_s or 0)) * 1000)
    _ranges, _a = [], 0
    while _a < _ms and len(_ranges) < 6:
        _b = min(_a + 120000 // 6, _ms)
        _ranges.append({"startMs": _a, "endMs": _b})
        _a = _b
    _deadline = time.time() + wait_s
    _last = "never polled"
    while time.time() < _deadline:
        try:
            r = _mcp_call(tok, "inspect_asset",
                          {"assetId": _aid, "projectId": stage["projectId"],
                           "transcriptRangesMs": _ranges})
        except Exception as e:                                    # noqa: BLE001
            _last = "inspect_asset: %s" % str(e)[:140]
            time.sleep(3)
            continue
        _rows = _transcript_rows(r, dur_s)
        if _rows:
            # WORDS BECOME BEATS HERE. 86 rows with timestamps are not
            # editorial units; the planner path segmented them and ruled
            # seven beats in 11-19s. Same segmenter, ported.
            _words = [{"w": x["text"], "s": x["t_start"], "e": x["t_end"]}
                      for x in _rows]
            _beats = segment_beats(_words)
            for _b in _beats:
                _b["words"] = sum(1 for x in _rows
                                  if _b["t_start"] <= x["t_start"] <= _b["t_end"])
            return _beats, "MEASURED", ("%d word(s) -> %d beat(s) over %.1fs, "
                                        "stamps read as %s"
                                        % (len(_rows), len(_beats), dur_s or 0,
                                           getattr(_transcript_rows, "unit",
                                                   "?")))
        _blob = (json.dumps(r) + str(r.get("_text") or "")).lower()
        if "no_audio" in _blob or "no audio" in _blob:
            return [], ABSENT_S, "the source has no audio to transcribe"
        _last = "transcript not ready (keys: %s)" % sorted(r)[:8]
        time.sleep(3)
    return [], ABSENT_S, "%s after %ds" % (_last, wait_s)


def _transcript_rows(r, dur_s=None):
    """Transcript rows out of an inspect_asset envelope, shape-tolerantly.

    THE UNIT IS DECIDED BY THE SOURCE'S KNOWN DURATION, NOT BY A MAGIC 300.
    The first version divided any stamp above 300 by 1000 — a word at 301s of
    a five-minute source would have been read as 0.3s. Now: `startMs/endMs`
    are milliseconds by name; bare `start/end` are compared against dur_s
    (seconds if the largest stamp fits it, else ms, else µs) and the choice is
    reported in `_transcript_rows.unit` for the BEATS line to print.

    THE SHAPE IS NOT ASSUMED. Twice this week a reader demanded one spelling
    and called a good response empty, so this tries the plausible containers
    AND falls back to parsing the text envelope, and the caller reports ABSENT
    with the keys it saw rather than an empty list.
    """
    out, raw = [], []
    def _walk(o):
        if isinstance(o, dict):
            _ms = "startMs" in o
            _s = o.get("startMs", o.get("start", o.get("t_start")))
            _e = o.get("endMs", o.get("end", o.get("t_end")))
            _t = o.get("text", o.get("content"))
            if _t and _s is not None and _e is not None:
                raw.append((float(_s), float(_e), str(_t), _ms))
                return
            for v in o.values():
                _walk(v)
        elif isinstance(o, list):
            for v in o:
                _walk(v)
    _walk(r)
    _transcript_rows.unit = "none"
    if raw:
        _mx = max(e for _, e, _, _ in raw)
        if all(ms for *_, ms in raw):
            _div, _transcript_rows.unit = 1000.0, "ms (startMs/endMs)"
        elif dur_s and _mx <= float(dur_s) * 1.5:
            _div, _transcript_rows.unit = 1.0, "s (fits the %.1fs source)" % dur_s
        elif dur_s and _mx <= float(dur_s) * 1500.0:
            _div, _transcript_rows.unit = 1000.0, "ms (%.0f vs %.1fs source)" % (_mx, dur_s)
        elif dur_s:
            _div, _transcript_rows.unit = 1e6, "us (%.0f vs %.1fs source)" % (_mx, dur_s)
        else:
            _div, _transcript_rows.unit = (1000.0 if _mx > 300 else 1.0), "GUESSED (no duration given)"
        out = [{"t_start": a / _div, "t_end": b / _div, "text": t}
               for a, b, t, _ in raw]
    # AND THE TEXT ENVELOPE, when the rows only exist as prose.
    if not out:
        for m in re.finditer(r"(\d+):(\d{2})[.,](\d{1,3})\s*[-\u2192>]+\s*"
                             r"(\d+):(\d{2})[.,](\d{1,3})\s*(.+)",
                             str(r.get("_text") or "")):
            a = int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3)) / 1000.0
            b = int(m.group(4)) * 60 + int(m.group(5)) + int(m.group(6)) / 1000.0
            out.append({"t_start": a, "t_end": b, "text": m.group(7).strip()})
    return sorted(out, key=lambda b: b["t_start"])

def pass1_message(plan, beats, inventory_png, source_watch=None,
                  deciding=False):
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
    # ── THE REFERENCES: WHAT I LEARNED FROM WATCHING THEM ──────────────────
    # Zac's ruling, 2026-09-16: "Claude watches all ten itself, through
    # ChatCut... It analyses them itself and writes what it learned. Not a
    # summary handed to it — its own reading of what it watched."
    #
    # WHAT CAME OUT, and why the replacement is TEXT. The previous artefact was
    # Gemini's 38 gated moments plus sixteen contact sheets — 45,871 image
    # tokens and 6,487 of prose, 52,358 in total, for 38 samples across 426
    # seconds. Those sheets are gone. What replaces them is one document
    # written from watching all ten at 2fps through inspect_asset — 852 samples
    # of the same 426 seconds, twenty-two times the coverage — and the reading
    # is worth more in the prefix than the pictures were, because the agent can
    # open any reference itself with inspect_asset when it wants to look.
    # TWO PATHS, like every other artefact this lane mounts: the container's
    # copy first, then the one beside the module. Without the second, this
    # branch is UNTESTABLE on a developer machine — it always takes the ABSENT
    # path — and an artefact nobody can exercise locally is one whose failure
    # is only ever discovered in a run.
    # THE REFERENCE STANDARD IS THE WATCH. Its 13,810-character summary no
    # longer rides in the first message (Zac's table, 2026-09-17: "it's in
    # the watch"); the resumed session holds the ten readings themselves.
    # THE SOURCE, WATCHED THROUGH CHATCUT (watch_asset): dense frames with the
    # editor's timecode strip, tiled, and the transcript rows aligned to them.
    _sw = source_watch or {}
    if _sw.get("sheets"):
        blocks.append({"type": "text", "text":
                       "THE SOURCE — %d frames at 2fps across the whole clip, "
                       "on %d sheet(s), each cell stamped with its source time. "
                       "Look at the footage before you decide anything: the "
                       "beats are derived from the transcript and cannot see "
                       "what is already in the frame, where the speaker is, or "
                       "what the shot already shows.%s"
                       % (_sw.get("frames", 0), len(_sw["sheets"]),
                          ("\n\nTHE WORDS, against those frames:\n" + _sw["transcript"])
                          if _sw.get("transcript") else "")})
        for fp in _sw["sheets"]:
            blocks.append(_img_block(fp))
    else:
        blocks.append({"type": "text", "text":
                       "THE SOURCE FRAMES: %s — %s. You are placing without "
                       "having seen the footage; say so in your reply."
                       % (_sw.get("state", "ABSENT"), _sw.get("why", "not watched"))})
    if beats:
        # THE BEATS, NOT THE WORDS. Each line is one editorial unit the agent
        # rules on; hook and close are marked because that is where the
        # corpus puts 64% of its sound.
        blocks.append({"type": "text", "text":
                       "THE BEATS — %d editorial unit(s), against those "
                       "frames. Rule each one:\n" % len(beats)
                       + "\n".join(
                           "  beat %-2s %6.2f-%6.2fs %-6s %s"
                           % (b.get("i", "?"), b.get("t_start", 0),
                              b.get("t_end", 0),
                              ("[%s]" % b["role"]) if b.get("role") else "",
                              str(b.get("text") or "").split(" \u00b7 ")[0])
                           for b in beats)})
    # ── WHAT GOOD LOOKS LIKE, IN THE EXECUTING HALF TOO ────────────────
    # The PLANNER knows the ten references are the bar; this half never did.
    # It got a plan and an inventory and nothing telling it what it is aiming
    # at, which is how "place the adds and export" becomes the whole job. The
    # plan's ACCEPTANCE block says what each placement must be true of; this
    # says what the edit as a whole is being held to. No rates — the density
    # rates GRADE and never instruct, and that law does not bend for being in
    # a different file.
    # THE SECOND HALF OF THIS DEPENDS ON WHOSE DECISION IT IS, and getting it
    # wrong is not cosmetic. Written for an executor, it says "every editorial
    # decision is already made, and inventing more is the failure" — handed to
    # the SINGLE AGENT, which is the thing making those decisions, that is an
    # instruction to place nothing. When a thing is promoted to a new role,
    # every rule that constrains it was written for the old one and none of
    # them announce that.
    # THE "HELD TO" PREAMBLE IS GONE (2026-09-17): it pointed at reference
    # sheets that no longer ride in this message — the watch holds them — and
    # its second half restated the paragraph. The paragraph's own sentence,
    # "you have watched the ten reference edits; they are the standard", is
    # the whole of it.
    blocks.append({"type": "text", "text": plan})
    return _message(blocks)




# ── THE FRAME SERVER: THE AGENT ASKS TO LOOK, THE HARNESS FETCHES ───────────
#
# MEASURED on run 24, and it is the whole execution half:
#
#     tool-call payload the agent TYPED        49,501 chars
#       of which mcp__chatcut__edit_item        1,380   2.8%   <- the EDIT
#       of which Bash                          47,379  95.7%
#       of which signed S3 frame URLs          44,098  89.1%
#     at 6.23 s of tool_use generation per 1k chars
#       => ~275s TYPING URLS, plus 156s of Bash RUNNING the curls
#       => ~430 of 908 seconds fetching frames by hand
#
# `preview_timeline` returns signed URLs, not pixels. So an agent that scrubs —
# which is exactly what it is supposed to do — pays for every look by
# retyping a 300-character signed URL into a curl command, then tiling with
# ffmpeg, then Read-ing the tile back. Zac's ruling was that the agent scrubs
# and nobody pre-picks its frames; it was never that looking should cost four
# minutes of typing.
#
# So the harness watches for a `preview_timeline` RESULT and serves what it
# points at: fetch the URLs here, send the pixels back. The agent keeps asking
# for whatever frames it wants, and never writes a URL again.
#
# BOUNDED, BUT NOT CHEAPENED. The cap is on total frames served in a run, not
# on how often the agent may look — bounding the looking is the thing that was
# reversed. `preview_timeline` caps itself at 9 per call.
_FRAME_URL_RE = re.compile(r'https://[^\s"\\\']+?\.(?:jpg|jpeg|png)(?:\?[^\s"\\\']*)?')
_SERVE_CAP = 60                      # frames, whole run


def _frame_urls(result_text):
    """Signed frame URLs in a tool result, in order, deduped."""
    seen, out = set(), []
    for u in _FRAME_URL_RE.findall(result_text or ""):
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _fetch_frames(urls, out_dir, already):
    """(blocks, state). Fetch signed frame URLs and return them as image blocks.

    A STATE, never a silent empty list: served-nothing and asked-for-nothing
    are different facts, and only one of them means the agent is about to go
    and curl them itself.
    """
    import urllib.request
    os.makedirs(out_dir, exist_ok=True)
    blocks, got, failed = [], [], []
    for u in urls:
        if u in already:
            continue
        if len(already) + len(got) >= _SERVE_CAP:
            failed.append("cap %d reached" % _SERVE_CAP)
            break
        fp = os.path.join(out_dir, "f%03d.jpg" % (len(already) + len(got)))
        try:
            with urllib.request.urlopen(u, timeout=45) as r:
                b = r.read()
            if not b:
                failed.append("empty body")
                continue
            with open(fp, "wb") as fh:
                fh.write(b)
        except Exception as e:                                    # noqa: BLE001
            failed.append("%s: %s" % (type(e).__name__, str(e)[:60]))
            continue
        already.add(u)
        got.append(u)
        blocks.append(_img_block(fp))
    if not blocks:
        return [], ("SERVED 0 — %d url(s) seen, %d already served, failures %s"
                    % (len(urls), len(urls) - len(failed), failed[:3]))
    return blocks, "SERVED %d of %d url(s)%s" % (
        len(blocks), len(urls),
        ("; %d failed: %s" % (len(failed), failed[:2])) if failed else "")


def _preview_frames(tok, pid, total_frames, fps=30, density_fps=2.0, mark=None, per_call=9, workers=5, out_dir=None):
    """THE REWATCH INSTRUMENT, PICKED (ruling 5, measured 2026-09-17 on one
    scratch timeline carrying three planted defects, 40 frames each):

        preview_timeline viewer, 5 calls serial      59.9s   composite shown
        preview_timeline viewer, 5 calls parallel    47.1s   (calls 33.1s + fetch 14s)
        export -> download -> upload -> inspect      75.0s   composite shown

    Both show the composite (sheets read by eye: captions, the card over the
    face, the 3x quote). Picked by wall: the viewer, parallel. The export is
    paid ONCE, for the final. Density stays 2 fps (ruling 6): n = 2 * seconds.
    -> (sheets, times_s), the shape `_edit_frames` returned.
    """
    from concurrent.futures import ThreadPoolExecutor
    import urllib.request as _ur
    dur = float(total_frames) / float(fps)
    n = max(per_call, int(round(density_fps * dur)))
    frames = [int(total_frames * (i + 0.5) / n) for i in range(n)]
    chunks = [frames[k:k + per_call] for k in range(0, n, per_call)]

    def _one(fr):
        r = _mcp_call(tok, "preview_timeline", {"projectId": pid, "views": ["viewer"], "viewerFrames": fr}, expect=None)
        return _frame_urls(json.dumps(r) + str(r.get("_text") or ""))
    try:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            urls = sum(list(ex.map(_one, chunks)), [])
    except Exception as e:                                        # noqa: BLE001
        print("  REWATCH FRAMES  : FAILED preview_timeline %s: %s" % (type(e).__name__, str(e)[:120]), flush=True)
        return [], []
    if mark:
        mark("calls")
    out_dir = out_dir or ("/work/preview_%d" % int(time.time()))
    os.makedirs(out_dir, exist_ok=True)

    def _get(iu):
        i, u = iu
        pth = os.path.join(out_dir, "f%03d.jpg" % i)
        try:
            with _ur.urlopen(u, timeout=60) as rsp:
                open(pth, "wb").write(rsp.read())
            return (i, pth)
        except Exception:                                         # noqa: BLE001
            return (i, None)
    with ThreadPoolExecutor(max_workers=8) as ex:
        got = [g for g in ex.map(_get, list(enumerate(urls))) if g[1]]
    if mark:
        mark("fetch")
    if not got:
        print("  REWATCH FRAMES  : ABSENT  %d url(s), 0 fetched" % len(urls), flush=True)
        return [], []
    times = [round(frames[i] / float(fps), 2) if i < len(frames) else -1 for i, _p in got]
    entries = [("%.1fs" % t, pth) for t, (_i, pth) in zip(times, got)]
    sheets = tile_sheets(entries, os.path.join(out_dir, "sheets"), per_sheet=20, cols=5, cell_w=180)
    if mark:
        mark("tile")
    print("  REWATCH FRAMES  : MEASURED  preview_timeline x%d parallel, %d of %d frame(s) at %.1ffps over %.1fs -> %d sheet(s)"
          % (len(chunks), len(got), n, density_fps, dur, len(sheets)), flush=True)
    return sheets, times


def _edit_frames(tok, pid, total_frames, n=EDIT_FRAMES_N, fps=30, mark=None):
    """Frames of the EDIT for pass 2 — from a real render, not the 9-frame cap.

    READ OFF THEIR SCHEMAS RATHER THAN INFERRED. `preview_timeline`'s viewer is
    "actual composed timeline pixels for exact frames or a uniform sample (up
    to 9 frames)" — stills, hard-capped at nine per call, and ChatCut's own
    `verification` skill verifies exactly that way: download the signed frame
    URLs and inspect the files. There is no playback on the tool surface; the
    viewer with play/pause in their docs is the human editor's.

    BUT `submit_export` IS RICHER: "Video/audio support frame- or seconds-based
    partial ranges" and "always start a durable cloud render". So the harness
    renders the edit ONCE and samples it at whatever density is useful, instead
    of paying nine cloud renders for nine moments it had to nominate up front.

    AND THE FRAMES GO WHERE THE MOTION IS. An even grid spends its budget on
    held shots; a defect does not. Half the frames are evenly spaced so nothing
    is unwatched, and half land on the biggest frame-to-frame changes, which is
    where an entrance, an exit or a collision actually happens.
    """
    try:
        ex = _mcp_call(tok, "submit_export",
                       {"projectId": pid, "format": "video", "codec": "h264",
                        "resolution": "720p"})
        blob = json.dumps(ex) + str(ex.get("_text") or "")
        rid = re.search(r"renderId[\"':\s]+([0-9a-f-]{8,})", blob)
        if not rid:
            print("  EDIT RENDER     : ABSENT  submit_export named no renderId",
                  flush=True)
            return [], []
        url = None
        # ADAPTIVE POLL, NOT A FIXED 6s. The old loop slept SIX SECONDS BEFORE
        # ITS FIRST CHECK, so a render that finished in two cost six — and the
        # loop now runs TWICE per job, once per rewatch, so that floor was up
        # to 12s of the 90-second budget spent waiting for a file that was
        # already there. Discovery lag is not render time.
        #
        # Short early, backing off: the same ~240s total budget, but a fast
        # render is noticed in about a second. Nothing here makes the render
        # faster; it stops the harness adding latency on top of it.
        for _iv in EXPORT_POLL_SCHEDULE:
            time.sleep(_iv)
            st = _mcp_call(tok, "track_export",
                           {"projectId": pid, "action": "status",
                            "renderIds": rid.group(1)})
            b2 = json.dumps(st) + str(st.get("_text") or "")
            m = re.search(r'(https://[^\s"\\]+out\.mp4[^\s"\\]*)', b2)
            if m:
                url = m.group(1)
                break
            if re.search(r'"status"\s*:\s*"(failed|error)"', b2):
                print("  EDIT RENDER     : FAILED  the render reported failure",
                      flush=True)
                return [], []
        if not url:
            print("  EDIT RENDER     : ABSENT  the render did not finish in "
                  "time", flush=True)
            return [], []
        (mark or (lambda k: None))("export")
        import urllib.request as _u
        with _u.urlopen(url, timeout=900) as r, open("/work/edit.mp4", "wb") as fh:
            fh.write(r.read())
        (mark or (lambda k: None))("download")
        # THE COMPOSED EDIT, WATCHED THE SAME WAY AS THE SOURCE: into the media
        # pool, then inspect_asset at 2fps, tiled. The ffmpeg still-sampler
        # that used to live here was a second pipeline for seeing.
        try:
            _aid = upload_asset(tok, pid, "/work/edit.mp4")
        except Exception as _ue:                                  # noqa: BLE001
            print("  EDIT RENDER     : FAILED  the render could not be imported "
                  "for watching (%s)" % str(_ue)[:160], flush=True)
            return [], []
        (mark or (lambda k: None))("upload")
        _dur = total_frames / float(fps or 30)
        _w = watch_asset(tok, _aid, _dur, "/work/edit_watch_%d" % int(time.time()))
        (mark or (lambda k: None))("inspect+tile")
        print("  EDIT RENDER     : %s  rendered once, imported as %s, %s"
              % (_w["state"], str(_aid)[:8], _w["why"]), flush=True)
        return _w.get("sheets") or [], _w.get("times") or []
    except Exception as e:                                        # noqa: BLE001
        print("  EDIT RENDER     : FAILED  %s: %s" % (type(e).__name__, e),
              flush=True)
        return [], []



def rendered_defects(edit_path, spans=None, source_path=None, fps=30.0,
                     expect_end_frames=None):
    """WHAT STILLS CANNOT SHOW, off the rendered file. -> (lines, summary).

    THE SECOND REWATCH IS A SCAN, NOT A SECOND OPINION. Composed frames answer
    "does this look right"; they cannot answer whether the audio drifted, a
    gap went black between two placements, a stretch froze, or the fixes
    truncated the edit. Those are the failures a fix batch INTRODUCES — you
    move an item to clear a collision and open a hole behind it — and they are
    exactly the ones an eye on nine stills will not catch.

    EVERY CHECK CARRIES ITS OWN STATE. A scan that could not run must never
    render as a clean scan: ffmpeg exiting non-zero, a missing audio stream, a
    source that is not there — each says FAILED or ABSENT and says why. This
    is the whole family this repo is built against: a failed measurement and a
    clean result are indistinguishable once you are only reading verdicts.
    SO THE SUMMARY REPORTS `scanned` AND `clean` SEPARATELY, and a rewatch
    where nothing could be scanned says so instead of saying nothing is wrong.
    """
    lines, states, findings = [], {}, 0

    def _run(args, timeout=600):
        try:
            r = subprocess.run(args, capture_output=True, text=True,
                               timeout=timeout)
            return r.returncode, (r.stderr or "") + (r.stdout or "")
        except Exception as e:                                    # noqa: BLE001
            return None, "%s: %s" % (type(e).__name__, str(e)[:120])

    if not (edit_path and os.path.exists(edit_path)
            and os.path.getsize(edit_path) > 10000):
        return (["  THE RENDERED FILE IS NOT THERE — none of the checks that "
                 "need it (sync, black, freeze, silence, length) ran. Nothing "
                 "below is a clean result; judge the frames by eye and say "
                 "the scan did not run."],
                {"scanned": 0, "clean": 0, "findings": 0,
                 "state": "ABSENT — no rendered file at %s" % edit_path})

    def _f(sec):
        return int(round(float(sec) * float(fps or 30)))

    # --- BLACK: a hole between two placements, or a gap the fixes opened ---
    rc, out = _run(["ffmpeg", "-v", "info", "-i", edit_path, "-vf",
                    "blackdetect=d=0.15:pix_th=0.10", "-an", "-f", "null", "-"])
    if rc is None:
        states["black"] = "FAILED"
        lines.append("  black frames : FAILED — the detector did not run (%s)"
                     % out[:80])
    else:
        states["black"] = "MEASURED"
        hits = re.findall(r"black_start:([\d.]+)\s+black_end:([\d.]+)", out)
        if hits:
            findings += len(hits)
            for a, b in hits[:6]:
                lines.append("  black frames : FRAME %d-%d — the picture is "
                             "BLACK for %.2fs (timeline %.2f-%.2fs). Nothing "
                             "is on screen there."
                             % (_f(a), _f(b), float(b) - float(a),
                                float(a), float(b)))
        else:
            lines.append("  black frames : none — scanned end to end")

    # --- FREEZE: a held frame the eye reads as a still ---
    rc, out = _run(["ffmpeg", "-v", "info", "-i", edit_path, "-vf",
                    "freezedetect=n=-60dB:d=0.7", "-an", "-f", "null", "-"])
    if rc is None:
        states["freeze"] = "FAILED"
        lines.append("  frozen video : FAILED — the detector did not run (%s)"
                     % out[:80])
    else:
        states["freeze"] = "MEASURED"
        hits = re.findall(r"freeze_start:\s*([\d.]+)", out)
        if hits:
            findings += len(hits)
            for a in hits[:6]:
                lines.append("  frozen video : FRAME %d — the picture stops "
                             "moving at timeline %.2fs" % (_f(a), float(a)))
        else:
            lines.append("  frozen video : none — scanned end to end")

    # --- SILENCE: audio that vanished under an edit ---
    rc, out = _run(["ffmpeg", "-v", "info", "-i", edit_path, "-af",
                    "silencedetect=n=-50dB:d=0.7", "-vn", "-f", "null", "-"])
    if rc is None:
        states["silence"] = "FAILED"
        lines.append("  silence      : FAILED — the detector did not run (%s)"
                     % out[:80])
    elif "Output file does not contain any stream" in out or rc != 0:
        states["silence"] = "ABSENT"
        lines.append("  silence      : ABSENT — the render has no audio "
                     "stream to scan, which is itself worth knowing")
    else:
        states["silence"] = "MEASURED"
        hits = re.findall(r"silence_start:\s*(-?[\d.]+)", out)
        if hits:
            findings += len(hits)
            for a in hits[:6]:
                lines.append("  silence      : FRAME %d — the audio goes "
                             "silent at timeline %.2fs" % (_f(a), float(a)))
        else:
            lines.append("  silence      : none — scanned end to end")

    # --- LENGTH: did the fixes truncate or overrun the timeline ---
    rc, out = _run(["ffprobe", "-v", "error", "-show_entries",
                    "format=duration", "-of", "csv=p=0", edit_path])
    _dur = None
    try:
        _dur = float((out or "").strip().splitlines()[0])
    except Exception:                                             # noqa: BLE001
        _dur = None
    if _dur is None:
        states["length"] = "FAILED"
        lines.append("  length       : FAILED — the duration could not be read")
    elif expect_end_frames:
        states["length"] = "MEASURED"
        _want = float(expect_end_frames) / float(fps or 30)
        _d = abs(_dur - _want)
        if _d > 0.5:
            findings += 1
            lines.append("  length       : FRAME %d — the render is %.2fs but "
                         "the timeline ends at %.2fs (%.2fs out). Something "
                         "was truncated or overran."
                         % (_f(_dur), _dur, _want, _d))
        else:
            lines.append("  length       : %.2fs, and the timeline ends at "
                         "%.2fs — they agree" % (_dur, _want))
    else:
        states["length"] = "ABSENT"
        lines.append("  length       : %.2fs rendered; the timeline end was "
                     "not supplied, so nothing compared it" % _dur)

    # --- SYNC: the edit's audio against the SOURCE SECOND it came from ---
    # MAPPED THROUGH THE KEPT SPANS, not compared at the same second. An edit
    # with cuts plays some other source second at timeline 11.0s, so a naive
    # correlation measures the CUT and reports a large lag on a perfectly
    # synced edit.
    _best = None
    for _a, _b, _f0, _f1 in (spans or []):
        if (_b - _a) >= 4.0 and (_best is None or (_b - _a) > _best[1] - _best[0]):
            _best = (_a, _b, _f0, _f1)
    if not source_path or not os.path.exists(source_path):
        states["sync"] = "ABSENT"
        lines.append("  a/v sync     : ABSENT — the source is not here to "
                     "compare against, so sync was NOT checked")
    elif _best is None:
        states["sync"] = "ABSENT"
        lines.append("  a/v sync     : ABSENT — no kept span is long enough "
                     "(>=4s) to correlate, so sync was NOT checked")
    else:
        _a, _b, _f0, _f1 = _best
        _tl = (_f0 / float(fps or 30)) + 1.0          # 1s into the span
        _src = _a + 1.0
        _lag = _audio_lag_ms(edit_path, source_path, at=_tl, dur=3.0,
                             b_at=_src)
        if _lag is None:
            states["sync"] = "FAILED"
            lines.append("  a/v sync     : FAILED — the envelopes could not "
                         "be read, so sync is UNKNOWN, not fine")
        else:
            states["sync"] = "MEASURED"
            if abs(_lag) > 60:
                findings += 1
                lines.append("  a/v sync     : FRAME %d — the edit's audio is "
                             "%dms %s the source it was cut from (timeline "
                             "%.2fs against source %.2fs). Lips will not match."
                             % (_f(_tl), abs(_lag),
                                "BEHIND" if _lag > 0 else "AHEAD", _tl, _src))
            else:
                lines.append("  a/v sync     : %dms against the source second "
                             "it was cut from — within tolerance" % _lag)

    _scanned = sum(1 for v in states.values() if v == "MEASURED")
    summary = {"scanned": _scanned, "checks": len(states),
               "findings": findings, "states": dict(states),
               "state": "MEASURED" if _scanned else
                        "ABSENT — no check completed"}
    return lines, summary

# _sheet_message WAS HERE AND IS GONE — defined, called by nothing.
# It was not harmless: it is the only writer of /work/review.jpg, and the
# visual-pass gate asked `os.path.exists("/work/review.jpg")` to decide whether
# the harness had delivered frames. A dead producer with a live consumer, so
# that branch was permanently false and the gate fell back to the agent having
# called preview_timeline — scoring FAILED for the intended behaviour.


# _review_sheet WAS HERE AND IS GONE — defined, called by nothing.
# It was not harmless: it is the only writer of /work/review.jpg, and the
# visual-pass gate asked `os.path.exists("/work/review.jpg")` to decide whether
# the harness had delivered frames. A dead producer with a live consumer, so
# that branch was permanently false and the gate fell back to the agent having
# called preview_timeline — scoring FAILED for the intended behaviour.


def segment_beats(words, gap_s=0.35, max_beat_s=3.0):
    """Cut the transcript into BEATS — the unit the agent rules on.

    PORTED from the planner path (agentic_editor_app.py `segment_beats`, one
    decision per beat, 2026-09-04) on Zac's ruling of 2026-09-17: the old
    planner got seven segmented beats and ruled them in 11-19 seconds; this
    agent got 86 words with timestamps and thought for twelve minutes.

    Split on dead air first — a pause is a real boundary. But gaps alone are
    not enough: a scripted explainer with no gap >= 0.35s collapses to one
    beat, which is no segmentation at all, so any run longer than max_beat_s
    is also split, on word boundaries, never mid-word. max_beat_s is 3.0 here
    (the planner used 6.0) because the 20s talking-head sources this path sees
    should come out at 7-10 beats, and 6.0 gives four.

    `words` are [{"w", "s", "e"}] in seconds. -> [{i, t_start, t_end, text,
    role?}] with the first and last marked hook/close, as the corpus places
    64% of its sound on exactly those two.
    """
    if not words:
        return []
    beats, cur = [], [words[0]]
    for prev, w in zip(words, words[1:]):
        gap = w["s"] - prev["e"]
        span = w["e"] - cur[0]["s"]
        if gap >= gap_s or span > max_beat_s:
            beats.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        beats.append(cur)
    out = [{"i": i,
            "t_start": round(b[0]["s"], 2),
            "t_end": round(b[-1]["e"], 2),
            "text": " ".join(str(x["w"]) for x in b)[:180]}
           for i, b in enumerate(beats)]
    if out:
        out[0]["role"] = "hook"
        out[-1]["role"] = "close"
    return out




def usage_once(state, ev):
    """Cache-read tokens this assistant event adds to the ceiling. -> int

    ONE ASSISTANT EVENT PER CONTENT BLOCK, EACH REPEATING THE MESSAGE'S USAGE
    — measured locally 2026-09-17: a thinking + tool_use call arrived as two
    events, both carrying the same cache_read/cache_creation. Summing every
    event over-counted every multi-block call by its block count; final-arch-1
    hit the 2.5M ceiling at "2,725,573" over 10 events for 6 calls. A message
    id is counted once. An event with no id is counted (never silently
    dropped); `state["usage_once_noid"]` says how many there were.
    """
    if not isinstance(ev, dict) or ev.get("type") != "assistant":
        return 0
    _m = ev.get("message") or {}
    _u = _m.get("usage") or {}
    _mid = _m.get("id")
    _seen = state.setdefault("seen_msg_ids", set())
    if _mid:
        if _mid in _seen:
            return 0
        _seen.add(_mid)
    else:
        state["usage_once_noid"] = state.get("usage_once_noid", 0) + 1
    return int(_u.get("cache_read_input_tokens") or 0)


def install_watch(cwd="/work", sid_p="/craft/watch_session_id.txt",
                  jsonl_p="/craft/watch_session.jsonl", home=None):
    """Put the watch session where `claude --resume` will find it. -> sid.

    THE SLUG IS DERIVED FROM CWD, NOT GUESSED. Claude Code resolves a resumed
    session strictly within the project directory for the cwd it is launched
    in, and a session file in the wrong slug answers "No conversation found"
    — measured, not assumed.

    AND THE CWD IS PART OF THE CACHED PREFIX. Measured 2026-09-16: the same
    session, same uuid, resumed from a cwd it had never run in read 32,318
    and wrote 37,894 — a full rewrite. So every container must launch from the
    SAME cwd or each one pays a cold write. /work is that cwd.

    A MISSING WATCH RAISES. It is the entire reference layer; a run that
    proceeds without it produces an edit graded against nothing, and an
    unmounted reference layer looks exactly like a mounted one from the log.
    """
    # THE PATHS ARE PARAMETERS WITH THE PRODUCTION DEFAULTS, so a smoke can
    # drive THIS function instead of restating it. A rule a check has to
    # reimplement is a rule the check does not cover: two mutations to a real
    # dispatch once passed green in this file because the smoke drove its own
    # copy.
    if not (os.path.exists(sid_p) and os.path.exists(jsonl_p)):
        raise FileNotFoundError(
            "the watch session is not mounted (%s=%s, %s=%s) — the reference "
            "layer would be silently absent"
            % (sid_p, os.path.exists(sid_p), jsonl_p, os.path.exists(jsonl_p)))
    sid = open(sid_p).read().strip()
    slug = cwd.replace("/", "-")
    dest_d = os.path.join(home or os.path.expanduser("~"),
                          ".claude", "projects", slug)
    os.makedirs(dest_d, exist_ok=True)
    dest = os.path.join(dest_d, "%s.jsonl" % sid)
    shutil.copyfile(jsonl_p, dest)
    _n = sum(1 for _ in open(dest, encoding="utf-8", errors="replace"))
    print("  WATCH           : MEASURED  sid=%s  %d lines  %.1f MB  -> %s"
          % (sid[:8], _n, os.path.getsize(dest) / 1048576.0, dest), flush=True)
    return sid

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
    # ── THE MODE RULE. THE SINGLE AGENT DECIDES ITS OWN SCOPE ──────────────
    # It used to be the planner's, and the planner is gone. Without it the
    # agent answers "does this brief ask for a vibe" by judgement, and that is
    # the defect that made 3 of 7 runs rule `none` on every beat and deliver a
    # user their own footage with captions on it, passing every gate.
    # mode_rule.txt no longer rides in the prefix (Zac's table, 2026-09-17:
    # "mode_rule 2k -> 0"); the paragraph's brief is the scope.
    # ── THE PRIMITIVES, AS OBSERVED ON A LIVE TIMELINE ─────────────────────
    # Ten turns of the 999s run went on parameter spelling — eight failing
    # `adds` of one video item, then two guesses at a geometry field. This is
    # the translator's FAMILY_MAP, which is the record of what was actually
    # read back off a timeline, and it is the single highest-value thing that
    # path produced. Imported, never restated.
    try:
        sys.path.insert(0, "/root")
        import plan_for_chatcut as _pfc
        _pl = ["\n\n===== HOW EACH FAMILY IS BUILT IN CHATCUT =====\n",
               "Every shape below was READ OFF A LIVE TIMELINE in this repo, "
               "not inferred from a schema. Build them exactly this way; "
               "guessing a parameter name is what cost ten turns.\n"]
        for _f, _r in sorted(_pfc.FAMILY_MAP.items()):
            if not _r.get("verified"):
                continue
            _pl.append("\n  %s -> %s\n      %s\n"
                       % (_f.upper(), _r.get("primitive", "?"),
                          " ".join(str(_r.get("how", "")).split())))
        parts.append("".join(_pl))
    except Exception as _e:                                       # noqa: BLE001
        parts.append("\n\n===== HOW EACH FAMILY IS BUILT : ABSENT (%s) "
                     "=====\nThe agent will be guessing parameter names.\n"
                     % _e)
    # ── THE SOUND LIBRARY, CACHED. browse_library is NOT in the tool list ──
    # Five browse_library calls went on one placement when it was reachable.
    # Cached for the agent, live for the gate.
    try:
        _sl = json.load(open("/craft/chatcut_sound_library.json",
                             encoding="utf-8"))["sounds"]
        parts.append("\n\n===== THE SOUND LIBRARY (%d) =====\n"
                     "You cannot search for these and you do not need to — "
                     "every id is here. Use the id verbatim.\n%s\n"
                     % (len(_sl), "\n".join("  %-34s %s" % (x.get("id"),
                                                            x.get("name"))
                                             for x in _sl)))
    except Exception as _e:                                       # noqa: BLE001
        parts.append("\n\n===== THE SOUND LIBRARY : ABSENT (%s) =====\n"
                     "Rule no sound you cannot name an id for.\n" % _e)
    # ── WHAT THE HARNESS DOES AFTER YOU ────────────────────────────────────
    parts.append(
        # REWRITTEN 2026-09-18: this block asked for /work/spec.json,
        # /work/rulings.json and a /work/DONE mark — the record is DERIVED from
        # the read-back now, the why rides inside each op, and the harness
        # renders between turns without any mark. h-th-think0's agent was
        # still reading this.
        "\n\n===== THE RECORD, AND WHO EXPORTS =====\n"
        "You write no files. The record is read back from the timeline; the "
        "one thing it cannot read is WHY, so every op you send carries a "
        "\"why\" field — one line, what that item is for. An op without it "
        "cannot be diagnosed when the edit delivers nothing.\n\n"
        "YOU DO NOT EXPORT. You have no submit_export tool. After each call "
        "the harness renders your timeline and sends you the frames; when "
        "you say export it reads the timeline back, checks every placement, "
        "and exports. A placement it cannot verify is REMOVED and named in "
        "the ledger; the rest still ships.\n")
    # ── THE CHATCUT PRECONDITION, MET IN ONE LINE ─────────────────────────
    # The hosted server's instructions mandated a Skill turn before the first
    # ChatCut call; the shim drops those instructions and the Skill tool is
    # withheld, so nothing is outstanding. The 36k-character guide used to
    # sit here whole (Zac's table, 2026-09-17: "the precondition line, ≤200").
    parts.append(
        "\n\n===== CHATCUT =====\n"
        "The ChatCut guide is loaded; nothing about it is outstanding. What "
        "matters here: every id comes from a tool result; video tracks stack "
        "and a higher track covers a lower one; items on one track never "
        "overlap, so layered graphics go on the tracks above; edits leave "
        "gaps unless you ripple; placement is frame-native.\n")
    parts.append(
        "\n\n===== THE REST IS ON DISK =====\n"
        "/craft/knowledge/ holds the other documents and "
        "/craft/reference_index.json the annotated beats. Read them only if "
        "this job needs something the above does not cover.\n")
    return "".join(parts)


# SIZED TO WHAT IT USES, NOT TO WHAT IT MIGHT. Measured on the blue-shirt run:
# cpu_mean 0.03 cores, p90 0.08, against 16.125 RESERVED, with zero throttling
# — the container spends its life idling on the model and on ChatCut's cloud
# render, and Modal bills the reservation, not the demand. That was $0.92 of
# cpu on a run that placed nothing.
#
# NOT sized to 0.08. The mean is low because the WAIT dominates; the work is
# bursty and real — ffmpeg builds a 20-frame contact sheet, res10 runs over 82
# sampled frames, and `_edit_frames` does a full decode plus 18 seeks per
# rewatch. 4 cores keeps headroom over every burst measured here while cutting
# the reservation 4x. A judgement with margin, not a fit to 0.03.
def cache_gate(call1, calln, fraction=CACHE_FRACTION):
    """Did call n read the prefix call 1 established? -> (ok, why). PURE.

    The prefix is what call 1 read plus what it wrote. A later call that reads
    less than `fraction` of it has a different prefix — the bytes moved — and
    that is terminal (Zac, ruling 1, 2026-09-17), not weather.
    """
    prefix = int(call1.get("read") or 0) + int(call1.get("write") or 0)
    if prefix <= 0:
        return True, "no prefix measured on call 1"
    r = int(calln.get("read") or 0)
    return r >= fraction * prefix, "read %d against %.2f x %d" % (r, fraction, prefix)


def _edit_ops(tool_calls):
    return [c for c in (tool_calls or [])
            if str(c.get("name") or "").endswith(("edit_item", "edit_captions"))]


def _says(text, *words):
    t = (text or "").strip().lower()
    return any(w in t for w in words)


def run_three_turns(invoke, rewatch, first_message, cap=TURN_CAP,
                    clock=time.time, run_timeout=RUN_TIMEOUT_S):
    """THE THREE STRATEGIC TURNS, THE HARNESS FETCHING BETWEEN THEM. -> tm

    Zac's rulings of 2026-09-17: each turn is ONE API call that ends at the
    tool call (the CLI's --max-turns 1, measured locally: the tool executes,
    no trailing call, the next --resume reads the whole prefix); the harness
    applies, reads the timeline back, runs the checks and serves the rewatch;
    the cap is four API calls and the fifth is terminal — kill, ledger, owner
    page, never a retry. Every call after the first must read the prefix.

    `invoke(n, message)` -> {rc, subtype, tool_calls, text, usage{read,write,
    in,out}, wall, ttft, killed}; `rewatch(n, final)` -> {message, ...}. Both
    are injectable so the machine is driven by a check, not a $ run.
    """
    t0 = clock()
    tm = {"turns": [], "terminal": None, "verdict": None, "cap": cap,
          "cold_write": None, "rewatches": []}
    call1 = {}

    def _turn(n, message, kind):
        nonlocal call1
        if n > cap:
            tm["terminal"] = {"kind": "TURN CAP", "at": n,
                              "why": "turn %d requested; the cap is %d — kill, ledger, page" % (n, cap)}
            return None
        if clock() - t0 > run_timeout:
            tm["terminal"] = {"kind": "RUN TIMEOUT", "at": n,
                              "why": "%.0fs elapsed before turn %d; the run bound is %ds" % (clock() - t0, n, run_timeout)}
            return None
        r = dict(invoke(n, message) or {})
        r["n"], r["kind"] = n, kind
        u = r.get("usage") or {}
        if n == 1:
            call1 = u
            w, rd = int(u.get("write") or 0), int(u.get("read") or 0)
            tm["cold_write"] = {"write": w, "read": rd,
                                "cold": w > 0.5 * max(1, w + rd)}
        else:
            ok, why = cache_gate(call1, u)
            r["cache_gate"] = why
            if not ok:
                tm["turns"].append(r)
                tm["terminal"] = {"kind": "CACHE MISS", "at": n,
                                  "why": "call %d did not read the prefix call 1 established (%s) — the bytes moved" % (n, why)}
                return None
        if isinstance(r.get("api_status"), int) and r["api_status"] >= 400:
            tm["turns"].append(r)
            tm["terminal"] = {"kind": "API ERROR", "at": n,
                              "why": "turn %d: the API answered %d: %s" % (n, r["api_status"], (r.get("api_head") or "")[:120])}
            return None
        if r.get("killed") or r.get("subtype") in ("error_during_execution",):
            tm["turns"].append(r)
            tm["terminal"] = {"kind": "TURN FAILED", "at": n,
                              "why": "turn %d: killed=%s subtype=%s" % (n, r.get("killed"), r.get("subtype"))}
            return None
        tm["turns"].append(r)
        return r

    r1 = _turn(1, first_message, "place")
    if r1 is None:
        return tm
    if not _edit_ops(r1.get("tool_calls")):
        tm["terminal"] = {"kind": "NO PLACEMENT", "at": 1,
                          "why": "turn 1 ended without an edit op: %s" % (str(r1.get("text") or r1.get("subtype") or "")[:160])}
        return tm
    rw1 = rewatch(1, False)
    tm["rewatches"].append({k: v for k, v in (rw1 or {}).items() if k != "message"})
    r2 = _turn(2, (rw1 or {}).get("message"), "review")
    if r2 is None:
        return tm
    ops2 = _edit_ops(r2.get("tool_calls"))
    rw2 = rewatch(2, True)
    tm["rewatches"].append({k: v for k, v in (rw2 or {}).items() if k != "message"})
    r3 = _turn(3, (rw2 or {}).get("message"), "confirm")
    if r3 is None:
        return tm
    ops3 = _edit_ops(r3.get("tool_calls"))
    if not ops3:
        tm["verdict"] = ("export at turn 3 (%s)" % ("clean at turn 2" if not ops2 else "one fix pass")
                         if _says(r3.get("text"), "export", "clean", "ship") or not r3.get("tool_calls")
                         else "turn 3 ended without ops or export: %s" % str(r3.get("text"))[:120])
        return tm
    rw3 = rewatch(3, True)
    tm["rewatches"].append({k: v for k, v in (rw3 or {}).items() if k != "message"})
    r4 = _turn(4, (rw3 or {}).get("message"), "contingency")
    if r4 is None:
        return tm
    if _edit_ops(r4.get("tool_calls")):
        tm["terminal"] = {"kind": "TURN CAP", "at": 4,
                          "why": "fix ops at the contingency turn; a fifth turn would be needed — kill, ledger, page"}
    else:
        tm["verdict"] = "export at turn 4 (contingency used)"
    return tm


def timeline_lines(items, props_by_id=None, base_item_id=None):
    """Every item, every property the harness holds, one line each."""
    out = []
    for i in (items or []):
        iid = str(i.get("id") or "")
        _as = i.get("asset") if isinstance(i.get("asset"), dict) else {}
        tr = i.get("timelineRange") or {}
        sr = i.get("sourceRange") or {}
        base = iid.replace("-", "")[:10] == str(base_item_id or "").replace("-", "")[:10]
        pv = (props_by_id or {}).get(iid) or (props_by_id or {}).get(iid[:8])
        out.append("  %s %-14s %-4s frames %s-%s%s  %s%s%s"
                   % (iid[:8], i.get("itemType"), i.get("trackAlias"),
                      tr.get("fromFrame"), tr.get("toFrame"),
                      (" src %.2f-%.2fs" % (float(sr.get("start") or 0) / 1e6, float(sr.get("end") or 0) / 1e6)) if sr else "",
                      _as.get("name") or "", " [base]" if base else "",
                      ("  props=%s" % json.dumps(pv, ensure_ascii=False)[:300]) if pv else ""))
    return out


def rewatch_message(n, watch, tl_lines, faults, scan_lines=None, final=False, calls_note=""):
    """The rewatch as ONE message: sheets + the whole timeline + the faults."""
    _w = watch or {}
    head = ("REWATCH %d — the composed edit as it renders now: %d frames at 2fps on %d "
            "sheet(s), each cell stamped with its timeline time. %s\n\n"
            "THE TIMELINE, every item the harness read back (id, type, track, frames, "
            "source range, asset, properties):\n%s\n\n"
            "WHAT THE HARNESS FOUND against ChatCut's own state (facts, not opinions):\n%s\n%s"
            % (n, _w.get("frames", 0), len(_w.get("sheets") or []),
               ("" if _w.get("sheets") else "THE RENDER COULD NOT BE WATCHED: %s — %s. Judge from the timeline lines." % (_w.get("state"), str(_w.get("why"))[:160])),
               "\n".join(tl_lines or ["  (no items read back)"]),
               "\n".join("  - " + f for f in (faults or [])) or "  - none",
               ("\nTHE RENDER SCAN:\n" + "\n".join(scan_lines)) if scan_lines else ""))
    tail = (("\n\nReply with the single word export if it ships as is; otherwise ONE edit_item "
             "call with the fixes, each op carrying its why. This is the last look."
             if final else
             "\n\nFix what is wrong in ONE edit_item call, each op carrying its why — or reply "
             "with the single word clean. Do not inspect or preview: everything the timeline "
             "holds is above.") + calls_note)
    blocks = [{"type": "text", "text": head + tail}]
    for fp in (_w.get("sheets") or []):
        blocks.append(_img_block(fp))
    return _message(blocks)


def fault_lines(gate_report, hop6, hop5, items, base_item_id, brief_mode="full_edit"):
    """The timeline-state checks as facts for the agent, one line each."""
    out = []
    for f in ((gate_report or {}).get("findings") or []):
        if f.get("verdict") != "PASS":
            out.append("%s: %s" % (f.get("check"), str(f.get("why"))[:200]))
    if hop6 and hop6.get("state") == "FAILED":
        out.append("face/text collision: %s" % str(hop6.get("why"))[:260])
    if hop5 and hop5.get("state") == "FAILED":
        out.append("overlay overlap: %s" % str(hop5.get("why"))[:200])
    placed = [i for i in (items or []) if str(i.get("id") or "").replace("-", "")[:10] != str(base_item_id or "").replace("-", "")[:10]]
    if not placed and brief_mode == "full_edit":
        out.append("nothing placed on a full-edit brief: the timeline holds only the source")
    caps = [i for i in placed if str(((i.get("asset") or {}) if isinstance(i.get("asset"), dict) else {}).get("name") or "").startswith("caption:")]
    tracks = {}
    for c in caps:
        tracks.setdefault(str(c.get("trackAlias")), []).append(c)
    if len(tracks) >= 2:
        out.append("two caption tracks (%s) show the same speech" % ", ".join(sorted(tracks)))
    return out


def write_cli_context(tok):
    """mcp.json (the shim), CLAUDE.md and system.md — the same bytes for a job
    and for the keep-warm ping, because the cache key is those bytes.

    KEPT AS THE CORRECTION: the first version of this function was RECURSIVE
    — a str.replace aimed at edit()'s copy of this block hit this one first
    (the earlier occurrence), leaving edit() with its own copy and this with
    a call to itself. The leg that reads both functions caught it.
    """
    cfg = {"mcpServers": {"chatcut": {
        "command": "python3", "args": ["/root/mcp_shim.py"],
        "env": {"MCP_SHIM_UPSTREAM": MCP_URL, "MCP_SHIM_TOKEN": tok,
                "MCP_SHIM_ALLOW": ",".join(NEEDED_TOOLS),
                "MCP_SHIM_LOG": "/work/mcp_shim.log"}}}}
    with open("/work/mcp.json", "w") as fh:
        json.dump(cfg, fh)
    with open("/work/CLAUDE.md", "w") as fh:
        fh.write(CRAFT_CONTEXT)
    sys_prompt = build_system_prompt()
    with open("/work/system.md", "w") as fh:
        fh.write(sys_prompt)
    return sys_prompt


def warm_ttl_minutes(warm_rec):
    """How long the last ping's cache entry lives, from the TTL it WROTE.
    -> 60 (1h entries), 5 (5m entries), or None when the ping recorded no
    split. The cold-write line once compared against a literal 60 while the
    container's CLI (2.1.272) writes 5-minute entries — every cold write
    after 5 minutes would have been called a defect of a ping that had
    already expired."""
    if not isinstance(warm_rec, dict):
        return None
    if int(warm_rec.get("write_1h") or 0) > 0:
        return 60
    if int(warm_rec.get("write_5m") or 0) > 0:
        return 5
    return None


def _read_trace_rows(path="/work/proxy_trace.jsonl"):
    """The proxy's trace rows so far. -> list (empty when absent)."""
    try:
        return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    except Exception:                                             # noqa: BLE001
        return []


def _read_prefix_rows(path="/work/prefix_calls.jsonl"):
    """The proxy's fingerprint rows so far. -> list (empty when absent)."""
    try:
        return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    except Exception:                                             # noqa: BLE001
        return []


def cli_version():
    """`claude --version` where the CLI runs — the image installs it UNPINNED.
    Read here because the container wrote 5-minute cache entries while the
    local 2.1.226 writes 1-hour ones, and a version is the first suspect."""
    try:
        return subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=30).stdout.strip() or "ABSENT (empty)"
    except Exception as e:                                        # noqa: BLE001
        return "FAILED %s: %s" % (type(e).__name__, str(e)[:60])


def cli_command(sid, model, use_hands=False, agents=None, partial=True, effort=None):
    """The claude invocation, ONE turn (the caller appends --max-turns 1).

    `effort` -> `--effort <level>` (low|medium|high|xhigh). Measured through
    the proxy 2026-09-17, CLI 2.1.226: the body carries
    output_config.effort (default xhigh) and, unless thinking is disabled,
    thinking {type: adaptive} — MAX_THINKING_TOKENS=3000 does NOT put a
    budget in the request. The effort flag is the dial that exists.
    """
    _sel = ",".join("mcp__chatcut__" + t for t in NEEDED_TOOLS)
    return (["claude", "-p",
             *(["--resume", sid] if sid else []),
             "--input-format", "stream-json",
             "--append-system-prompt-file", "/work/system.md",
             *(["--agents", json.dumps(agents)] if use_hands and agents else []),
             "--output-format", "stream-json", "--verbose",
             "--mcp-config", "/work/mcp.json", "--strict-mcp-config",
             "--settings", "/root/chatcut_hooks.json",
             "--allowedTools",
             ",".join(["mcp__chatcut__" + t for t in NEEDED_TOOLS]
                      + ["Bash", "Read", "Write", "Glob", "Grep"]),
             "--tools", "Bash,Read,Write,Glob,Grep," + _sel,
             "--disallowedTools", "Skill,Task,Agent",
             "--model", model]
            + (["--effort", str(effort)] if effort else [])
            + (["--include-partial-messages"] if partial else []))


RUN_FIRST_TEXT_JOB = "THE COMPONENT INVENTORY"   # the first text of pass1_message: what the proxy finds the watch's end by
RUN_FIRST_TEXT_PING = "ping"

@app.function(image=IMG, timeout=900, cpu=4, memory=8192,
              # SECTION B: the container's imports and CLI are snapshotted
              # after module load; per-job ChatCut work (project, import,
              # base item) cannot be, and is measured in PRESTAGE PHASES.
              enable_memory_snapshot=True,
              secrets=[modal.Secret.from_name("chatcut-oauth"),
                       modal.Secret.from_name("anthropic-api-key")])
def edit(clip_url: str, brief: str, model: str = "claude-sonnet-5",
         run_id: str = "latest", use_hands: bool = False, plan: str = "",
         think_tokens: int = -1, effort: str = "", prefix_ttl: str = "1h", prestage_title: str = "",
         prestage_controls: str = "", prestage_titles: str = "",
         transcript: str = "",
         # THE SUBTRACTION EXPERIMENT (2026-09-17). Same paragraph, same
         # beats, same components; one arm resumes the watch and one does
         # not; both stop the moment the first batch lands. If thinking drops
         # from ~270s to ~30s without the watch, the watch is what the model
         # deliberates over. If it does not, the watch is innocent and the
         # cause is the input shape. Off for every real job.
         read_ceiling: int = 0):
    t0 = time.time()
    marks = {}

    def mark(k):
        marks[k] = round(time.time() - t0, 2)

    tok = _access_token()
    mark("token")
    pf = preflight(tok)
    n_tools = pf["n_tools"]
    mark("preflight")
    _cli_ver = cli_version()
    print("  CLI VERSION     : %s" % _cli_ver, flush=True)

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
    # MARKED WHERE THE STAGE ENDS, NOT WHERE THE NEXT PRINT HAPPENS. This mark
    # used to sit after the contact sheet was built, so every "download" figure
    # this lane has ever reported silently included the sheet. Two stages under
    # one name is the same defect as two numbers under one name, and it was
    # invisible because the total was right.
    mark("download")
    # THE DETECTORS RUN OFF THE WALL CLOCK. `region_states` is ~160 res10
    # inferences plus an EAST pass, and its answer is not needed until the
    # REVIEW — which is the last stage of the run. Serially it would be pure
    # added latency against a 90-second budget that the review already
    # overruns; on a thread started here it costs nothing but CPU the
    # container measured itself barely using (0.146 cores of 16.125).
    #
    # THE HOLDER STARTS AS A NAMED ABSENCE, NOT AS AN EMPTY DICT. If the
    # thread dies, is still running, or never ran, the criteria must say which
    # — "no faces found" and "we did not look" are different answers, and the
    # second one printed as the first is the most dangerous bug this lane
    # shipped.
    _regions = {"face_state": "ABSENT — the detector thread did not finish "
                              "before the review", "face_traj": None}

    _dur_for_detect = 0.0
    for _ln0 in _p.stdout.splitlines():
        if _ln0.startswith("duration="):
            _dur_for_detect = float(_ln0.split("=", 1)[1] or 0)

    # THE DURATION IS PASSED, NOT CLOSED OVER. It resolved correctly either way
    # — the thread starts after the binding — but a closure whose body READS a
    # name bound five lines BELOW it is the exact shape that has cost this repo
    # real time ("an edit above a rebinding is not an edit"), and the next
    # person to move either line would have to re-derive that it is safe.
    def _detect_into(_holder, _dur):
        import sys as _s
        if "/root" not in _s.path:
            _s.path.insert(0, "/root")
        try:
            _holder.update(region_states("/work/source.mp4", _dur))
        except Exception as _de:                                  # noqa: BLE001
            _holder["face_state"] = "FAILED — %s: %s" % (
                type(_de).__name__, str(_de)[:120])

    _detect_th = threading.Thread(target=_detect_into,
                                  args=(_regions, _dur_for_detect),
                                  daemon=True)
    _detect_th.start()
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
    # MARKED, BECAUSE THE BUDGET CANNOT BE ITEMISED FROM STAGES THAT DO NOT
    # REPORT. The 90s itemisation had eight UNMEASURED rows and two of them
    # were harness work nobody had timed — a derived signal that is not
    # printed cannot be verified, applied to the clock.
    mark("sheet")
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

    # THE MCP SERVER, CONFIGURED WITH A BEARER WE ALREADY PROVED WORKS. The
    # preflight above ran the same credential over the same endpoint, so a
    # failure after this point is the agent or the tools, never the auth.
    # THROUGH THE SHIM, NOT THE HOSTED SERVER DIRECTLY. The tool block is the
    # largest thing in the prefix after the watch — 59 schemas, 182,903 bytes,
    # for nine callable tools — and `--tools` leaves MCP definitions in. The
    # shim's tools/list is the upstream list filtered to NEEDED_TOOLS.
    sys_prompt = write_cli_context(tok)
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
    # PRESTAGE IS NOT PLAN WORK — IT IS WHAT MAKES A RUN POSSIBLE AT ALL.
    #
    # This block sat under `if plan:`. It was correct when a planner and an
    # executor were two agents; the split is gone, the single-agent path has no
    # plan, and so NO PROJECT WAS EVER CREATED. Measured 2026-09-16 on the
    # blue-shirt clip: prestaged=false, 0 edit_item calls, 1,521s, $6.68 for no
    # edit, and every downstream stage reporting ABSENT with an honest reason.
    #
    # The law is *a check can be correct when written and wrong once the design
    # moves*, and the lesson is the one after it: I had already found `plan`
    # gating hop 5 on this path, fixed that instance, and never asked what else
    # the predicate gated. What stays under `if plan:` must defend a property
    # genuinely about HAVING a plan, not merely correlate with one.
    _ctl = json.loads(prestage_controls) if prestage_controls else {}
    _titles = json.loads(prestage_titles) if prestage_titles else []
    # WHAT THIS JOB HAS ALREADY DONE AND SPENT, from before any preemption. Read once
    # here so the ceiling reasons about the job rather than this container.
    _js = job_state(run_id)
    _prior_read = int(_js.get("read_tok") or 0)
    _attempt = int(_js.get("attempts") or 0) + 1
    # ONE CEILING, BOUND ONCE. The comparison honoured `read_ceiling`; the
    # kill message, the record and the summary line all printed
    # READ_TOKEN_CEILING — an arm launched at 6M would have reported
    # "against a ceiling of 2500000" while stopping at 6M.
    _ceil = int(read_ceiling or READ_TOKEN_CEILING)
    job_state_put(run_id, attempts=_attempt)
    if _prior_read:
        print("  RESUMED         : attempt %d — this job has already read %d "
              "token(s) against a %d ceiling"
              % (_attempt, _prior_read, _ceil), flush=True)
    # IDEMPOTENT ON RESTART. Modal retries a preempted Function with the same
    # input in a fresh container, and a retry that re-prestages creates a
    # SECOND ChatCut project, re-uploads the source and re-registers 37
    # components — paying twice for one setup and leaving an orphan. Run 3
    # did exactly this. The stage is durable per run id; a retry that finds
    # one reuses it, and says so.
    _prior_stage = job_state(run_id).get("stage")
    # AN EXPERIMENT ARM IS A FRESH JOB OR IT IS NOT AN ARM. A reused stage
    # means a reused run id: prior read tokens already on the ceiling, a
    # project that may hold items, and a "first" batch that is not the
    # first. Refuse it rather than measure a contaminated arm.
    if _prior_stage and _prior_stage.get("projectId"):
        _stage = _prior_stage
        print("  PRESTAGE        : REUSED  project=%s from attempt %d — this "
              "is a preemption retry, not a new job"
              % (str(_stage["projectId"])[:8], max(1, _attempt - 1)),
              flush=True)
        # WHAT THE EARLIER ATTEMPT LEFT ON THE TIMELINE, read rather than
        # assumed empty: the paragraph names it so the agent revises instead
        # of placing a second copy of everything.
        try:
            _prb = read_back(tok, _stage)
            _stage["priorItems"] = [str(i.get("id")) for i in (_prb.get("items") or [])
                                    if i.get("id") and str(i.get("id")).replace("-", "")[:10]
                                    != str(_stage.get("baseItemId") or "").replace("-", "")[:10]]
            print("  PRIOR ITEMS     : %d on the reused timeline (%s)"
                  % (len(_stage["priorItems"]), _prb.get("read_why")), flush=True)
        except Exception as _pe:                                  # noqa: BLE001
            _stage["priorItems"] = []
            print("  PRIOR ITEMS     : FAILED to read (%s)" % _pe, flush=True)
    else:
        _stage = prestage(tok, prestage_title, controls=_ctl,
                          source_path="/work/source.mp4", titles=_titles)
        job_state_put(run_id, stage=_stage)
    # AND ITS ABSENCE IS FATAL IN SECONDS, NOT IN TWENTY MINUTES. A run with no
    # project cannot place anything; letting it proceed buys a 1,500s timeout
    # and a ledger full of honest, useless ABSENTs. Fail where the precondition
    # is missing, not where its consequences surface.
    if not (_stage and _stage.get("projectId")):
        raise RuntimeError(
            "PRESTAGE produced no projectId — there is no timeline to edit, so "
            "the agent would spend the whole budget discovering that. "
            "Envelope: %s" % str(_stage)[:300])
    if not _stage.get("sourceAssetId"):
        raise RuntimeError(
            "PRESTAGE created project %s but registered NO SOURCE ASSET — the "
            "agent would face an empty timeline with no clip to cut. "
            "prestage() imports the source itself, so a missing sourceAssetId "
            "means that upload failed silently."
            % str(_stage.get("projectId"))[:12])
    # THE WORDS, FETCHED WHILE THE REST OF SETUP HAPPENS. Transcription is a
    # wait on somebody else's machine, and pass 1 cannot start without it, so
    # it runs on a thread from the moment the asset exists and is joined where
    # the message is built — overlapping the watch install, the system prompt
    # and the frame extraction instead of adding to them.
    _beats_box = {"beats": [], "state": "ABSENT", "why": "not started"}

    def _fetch_beats():
        try:
            _b, _st, _w = source_beats(tok, _stage, _dur_for_detect)
            _beats_box.update({"beats": _b, "state": _st, "why": _w})
        except Exception as _be:                                  # noqa: BLE001
            _beats_box.update({"state": "FAILED",
                               "why": "%s: %s" % (type(_be).__name__,
                                                  str(_be)[:140])})

    _beats_th = threading.Thread(target=_fetch_beats, daemon=True)
    _beats_th.start()
    # THE SOURCE IS WATCHED THROUGH CHATCUT while the message is prepared.
    _watch_box = {"state": "ABSENT", "why": "not started"}

    def _watch_source():
        try:
            _watch_box.update(watch_asset(tok, _stage.get("sourceAssetId"),
                                          _dur_for_detect, "/work/source_watch"))
        except Exception as _we:                                  # noqa: BLE001
            _watch_box.update({"state": "FAILED",
                               "why": "%s: %s" % (type(_we).__name__, str(_we)[:140])})
    _watch_th = threading.Thread(target=_watch_source, daemon=True)
    _watch_th.start()
    mark("prestage")
    _libn = len(_stage.get("components") or {})

    # THE STAGE REACHES THE AGENT ON EVERY PATH, NOT ONLY THE PLAN ONE.
    #
    # Measured 2026-09-16, run `blueshirt-fixed-3`: prestage created the
    # project, imported the source and registered 37 components — and the
    # DECIDING prompt named none of them. `timelineId` and `trackId` appeared
    # ZERO times in edit(). So the agent was told to place things onto a
    # project it could not name, reached for `read_project` to find out, was
    # refused by the allowlist, retried once, and stopped. 9 turns, 0
    # placements, 1,401s of silence.
    #
    # A PRODUCER WITH NO CONSUMER. The harness knew every id and told the agent
    # nothing; this block is the consumer. It sits beside the plan path's
    # identical block, which is why the plan path worked and this one never
    # could — the same information, offered on one branch only.
    # THE IDS GO IN THE SENTENCE, THE COMPONENTS GO IN A LIST.
    #
    # Zac, 2026-09-16: "Everything in it is an id or a sentence. No procedure,
    # no warnings, no restatement of rules the tool schemas already carry."
    # The ids are what the agent could not name and spent a whole run
    # discovering; the component table is a lookup, which is a list.
    _ids_line = "project %s" % _stage["projectId"]
    for _k2, _lbl in (("timelineId", "timeline"), ("trackId", "track"),
                      ("sourceAssetId", "source")):
        if _stage.get(_k2):
            _ids_line += ", %s %s" % (_lbl, _stage[_k2])
    _components_block = (
        ("\n\nTHE %d REGISTERED COMPONENTS — place one and set its text through "
         "`propertyOverrides`. Use the whole id.\n%s\n"
         % (_libn, "\n".join(
             "    %-22s %s" % (
                 _k, ((_v.get("assetId") if isinstance(_v, dict) else _v)
                      or "?"))
             for _k, _v in sorted(
                 (_stage.get("components") or {}).items())[:60])))
        if _libn else "")
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
    # AN EMPTY MANIFEST IS ABSENT, NOT A PASS.
    #
    # HOP 2 asks whether every assetId THE PLAN NAMES is registered before
    # the agent starts. The single agent authors its own graphics at run
    # time, so there is no plan and `_manifest` is empty — and
    # `hop2_prestage([])` finds no misses and this line printed
    # "MEASURED 0 add(s), every assetId registered". A check comparing
    # against an empty set passes, and passes quietly; this repo has the
    # rule and it still took writing a new smoke to see it here.
    #
    # The question it asked has not been lost, it has MOVED: whether a
    # placement carries what it claims is now asked of the placed item by
    # chatcut_gate.check_card_props_resolve, against the component library.
    if not _manifest:
        print("  HOP 2           : ABSENT — no plan names any asset "
              "(single-agent path: the agent authors its own graphics). "
              "The question moved to GATE B, which asks it of the PLACED "
              "item.", flush=True)
    else:
        print("  HOP 2           : MEASURED  %d add(s), every assetId "
              "registered" % len(_manifest), flush=True)
    print("  TITLE CONTROLS  : %s" % (json.dumps(_ctl) if _ctl
                                      else "ABSENT — defaults"), flush=True)
    print("  PRESTAGE        : MEASURED  project=%s title=%s source=%s  "
          "(the agent writes no JSX and uploads nothing)"
          % (_stage["projectId"][:8], (_stage["titleAssetId"] or "?")[:8],
             (_stage["sourceAssetId"] or "ABSENT")[:8]), flush=True)
    # THE PLAN PATH IS GONE (ruling C, 2026-09-17): one branch, the deciding paragraph.
    _src_frames = int(round(_dur_for_detect * 30)) if _dur_for_detect else 0
    _base_line = (
        ("The source (%.2fs = %d frames at 30fps) is ALREADY on track V1 "
         "as item %s, frames 0-%d, untrimmed. Cut it with edit_item "
         "updates (fromFrame, durationInFrames, sourceStartFromInSeconds) "
         "and adds of further video items from the same assetId; place "
         "graphics on the tracks above it. "
         % (_dur_for_detect, _src_frames, _stage.get("baseItemId"),
            _src_frames))
        if _stage.get("baseItemId") else
        ("The source is %.2fs = %d frames at 30fps. "
         % (_dur_for_detect, _src_frames)))
    _prior_line = (
        ("The timeline ALREADY HOLDS %d item(s) from an earlier attempt of "
         "this same job (ids %s) — revise them; do not place them again. "
         % (len(_stage.get("priorItems") or []),
            ", ".join(str(x)[:8] for x in (_stage.get("priorItems") or [])[:8])))
        if _stage.get("priorItems") else "")
    prompt = (
        ("You are editing this video. The project is open — %s. The %d "
         "components are listed below, with a picture of each. You have "
         "watched the ten reference edits; they are the standard.\n\n"
         % (_ids_line, _libn))
        + _base_line + _prior_line +
        "An edit_item add takes assetId, trackId, fromFrame and "
        "durationInFrames. A track-bound effect also takes trackBoundFrom "
        "and trackBoundDurationInFrames. A component's text goes in "
        "propertyOverrides. Caption edits take the revision "
        "read_captions returns — Card edits AND track-wide ones "
        "like set_max_characters.\n\n"
        "Your %d ChatCut tools are loaded and the ChatCut guide is already "
        "in your context.\n\n"
        "THE BRIEF: %s\n\n"
        # THE THREE-TURN CONTRACT, with the shapes ChatCut's slimmed schema
        # cannot show (adds.items is {} upstream too). Measured 2026-09-17
        # (h-th-think0): without them the agent guessed type "caption-track",
        # wrapped its ops in the `json` string field, and put `why` where
        # the shim could not take it off — three of four calls refused.
        "Place everything in ONE edit_item call, using the adds/updates/"
        "deletes fields directly (never the json field). Every add is "
        "exactly this shape: {\"type\": \"motion-graphic\", \"assetId\": "
        "\"<inventory id>\", \"fromFrame\": N, \"durationInFrames\": N, "
        "\"propertyOverrides\": {...}, \"why\": \"one line: what it is for\"}. "
        "type is motion-graphic for every inventory component. Captions are "
        "NOT an item: one edit_captions call with action \"enable\" turns "
        "them on. Put the why INSIDE each op — the harness reads it there; "
        "write no files and call no preview: after your call the harness "
        "watches the render and sends you the frames. Then you fix in one "
        "call, and once more if needed, and say \"export\"."
        % (_nsel, brief)
        # THE CONTRACT, IN FULL. Until 2026-09-18 TWO_TURN_LOOP rode only the
        # plan path (deleted); the deciding agent had never seen it.
        + "\n\n" + TWO_TURN_LOOP
        + _components_block
        + (HANDS_PARA_DECIDE if use_hands else ""))

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
    # A PASSED TRANSCRIPT WINS; OTHERWISE THE ONE WE FETCHED. Both are the
    # same shape and the ledger says which arrived, because "no speech" and
    # "we never asked" are different facts about the edit that follows.
    try:
        _beats = json.loads(transcript) if transcript else []
        _beats_why = "passed in" if _beats else ""
    except Exception:                                             # noqa: BLE001
        _beats, _beats_why = [], "the passed transcript did not parse"
    if not _beats:
        _beats_th.join(timeout=60)
        _watch_th.join(timeout=120)
        if _watch_th.is_alive():
            _watch_box.update({"state": "ABSENT", "why": "watch_asset still running after 120s"})
        print("  SOURCE WATCH    : %s — %s" % (_watch_box.get("state"), str(_watch_box.get("why"))[:140]),
              flush=True)
        if _beats_th.is_alive():
            _beats_why = "the transcript fetch was still running after 60s"
        else:
            _beats = _beats_box["beats"]
            _beats_why = "%s — %s" % (_beats_box["state"], _beats_box["why"])
    print("  BEATS           : %s  %d beat(s)"
          % (_beats_why or "ABSENT", len(_beats)), flush=True)
    print("  PASS 1 SERVES   : inventory=%s  source frames=%d  transcript=%d "
          "beat(s)"
          % (os.path.exists("/craft/component_sheet.png"), int(_watch_box.get("frames") or 0),
             len(_beats)), flush=True)
    # THE WATCH IS INSTALLED BEFORE THE COMMAND IS BUILT, because the command
    # names its session id and a --resume onto a file that is not there is the
    # one failure that looks exactly like success: the CLI starts a FRESH
    # session, the edit runs, every gate passes, and the reference layer was
    # never in context.
    _watch_sid = install_watch("/work")
    _cmd = cli_command(_watch_sid, model, use_hands, agents if use_hands else None, _pm, effort=(effort or None))
    # THE THINKING CAP. 267 of 608 seconds — 44% of the wall — was `thinking`
    # blocks on an agent handed a COMPLETE plan. It is executing, not deciding,
    # and it was reasoning as if it were. `MAX_THINKING_TOKENS` is read from the
    # binary's own strings, not from documentation: the CLI also carries
    # CLAUDE_CODE_DISABLE_THINKING and DISABLE_INTERLEAVED_THINKING, and this
    # is the one that BOUNDS rather than removes — the review pass still needs
    # judgment about whether the composed frames are right.
    # BOUNDED BY DEFAULT (Zac's table, 2026-09-17: output per run ≤8k, "no
    # record, no plan"). Thinking is output; 546s of it wrote the record.
    # -1 = the default bound; 0 = thinking REMOVED (the CLI's own switch,
    # since what MAX_THINKING_TOKENS=0 means is not documented and an arm
    # that silently ran the default would be no arm); N = a bound of N.
    # MEASURED ON THE WIRE (2026-09-17, transparent proxy, CLI 2.1.226):
    #   MAX_THINKING_TOKENS=0            -> thinking {type: disabled}   (the off switch)
    #   CLAUDE_CODE_DISABLE_THINKING=1   -> no thinking field at all; Sonnet 5 then
    #                                       thinks ADAPTIVELY — h-th-think0 streamed
    #                                       25k thinking tokens in 300s under it
    #   MAX_THINKING_TOKENS=N (N>0)      -> thinking {type: adaptive}, no budget
    if think_tokens == 0:
        _env = {"MAX_THINKING_TOKENS": "0"}
    else:
        _env = {"MAX_THINKING_TOKENS": str(think_tokens if think_tokens > 0 else DEFAULT_THINK_TOKENS)}
    # NO ToolSearch. Tool definitions sit FIRST in the cache hierarchy; the
    # ToolSearch turn loads nine schemas into that block on call 2 and every
    # cached byte after it — system, watch, first message — is rewritten.
    # Measured locally 2026-09-17: ENABLE_TOOL_SEARCH=false removes ToolSearch
    # from the init tool list, and `--tools` restricts the block itself
    # (5 tools -> 19,909 tokens written; eager-all -> 68,460). With both, the
    # block is fixed from call 1 and there is no schema-fetch turn.
    _env["ENABLE_TOOL_SEARCH"] = "false"
    # EVERY REQUEST THROUGH THE RECORDING PROXY. Started here, on a thread,
    # and torn down with the container. The fingerprints land in
    # /work/prefix_calls.jsonl and reach the record below.
    # TRANSPARENT (2026-09-17): handed to the CLI as HTTPS_PROXY + a CA only
    # this process trusts, never as ANTHROPIC_BASE_URL — behind a base URL of
    # http://127.0.0.1 the CLI's request changed (a "ping" thought 100s+ three
    # times out of three; direct, 'pong' in 19s), and an instrument the
    # subject can see is not an instrument.
    try:
        import api_proxy as _px
        _px.FINGERPRINTS = "/work/prefix_calls.jsonl"
        _px.FIRST_BODY = "/work/req_first.json"
        _px.TRACE = "/work/proxy_trace.jsonl"
        # TTL BY ENVIRONMENT (Zac, 2026-09-18): "1h" is the production shape —
        # the proxy places the watch-end breakpoint at 1h and the hourly ping
        # keeps it; "5m" is development — no ping, no injection, call 1 writes
        # and calls 2+ read (the within-run assertion alone).
        _px.RUN_FIRST_TEXT = RUN_FIRST_TEXT_JOB if prefix_ttl == "1h" else ""
        print("  PREFIX TTL      : %s — %s" % (prefix_ttl, "watch-end breakpoint at 1h (production shape)" if prefix_ttl == "1h"
                                                 else "no breakpoint injected; call 1 writes 5m, calls 2+ read (development)"), flush=True)
        _px_port, _px_ca = _px.serve_mitm(0, "/work/mitm")
        _env.update(_px.mitm_env(_px_port, _px_ca))
        print("  API PROXY       : MEASURED  transparent, HTTPS_PROXY=http://127.0.0.1:%d, CA %s"
              % (_px_port, _px_ca), flush=True)
    except Exception as _pxe:                                     # noqa: BLE001
        print("  API PROXY       : FAILED to start (%s) — the CLI goes direct and "
              "this run carries NO prefix fingerprints" % _pxe, flush=True)
    print("  THINKING CAP    : %s" % (" ".join("%s=%s" % kv for kv in _env.items() if "THINK" in kv[0])
                                      + ("" if think_tokens > 0 else (" (removed)" if think_tokens == 0 else " (default)"))), flush=True)
    # ── THE HARNESS DRIVES THE CONVERSATION ─────────────────────────────────
    # Two user messages, both carrying PIXELS the harness already has:
    #   1. the plan, with the SOURCE contact sheet as an image
    #   2. after the placements land, the REVIEW sheet as an image
    # Between them that removes five agent turns — a Read of the source sheet,
    # and the preview/curl/tile/Read the review used to cost — because none of
    # it is a decision. The model is needed for the LOOKING, not the fetching.
    sys.path.insert(0, "/root")
    # THE EDIT'S LENGTH COMES FROM THE TIMELINE NOW, NOT FROM A PLAN.
    #
    # It was `max(from + dur)` over the plan manifest. With no plan the
    # manifest is EMPTY, `max([] or [0])` is 0, and `_edit_frames` would have
    # been asked to render a ZERO-FRAME edit — the review pass returning
    # nothing, reported as "the harness could not render the edit", on a
    # perfectly good timeline. Absence rendered as a value, in the number that
    # decides whether the agent ever sees its own work.
    #
    # It is read at PASS 2 time rather than here, because at this point the
    # agent has not placed anything and the answer would be 0 for a second,
    # truer reason.
    # ── THE THREE STRATEGIC TURNS (Zac, 2026-09-17) ──────────────────────
    # One API call per turn (--max-turns 1); the harness fetches, applies,
    # checks and serves between them; cap four; every later call must read
    # the prefix the first established. The stream machine that used to live
    # here — marks, rewatch threads, idle bounds — is gone with it.
    _first_message = pass1_message(prompt, _beats, "/craft/component_sheet.png",
                                   _watch_box, deciding=not bool(plan))
    out_first = _first_message          # into the record below, in full (section C)
    _turn_recs = []

    def _invoke(n, message):
        _stream = "/work/stream_turn%d.jsonl" % n
        _tfile = "/work/timing_turn%d.json" % n
        _st = {}
        _calls, _texts, _res = [], [], {}

        def _on(ev, send, close, kill=None):
            if ev.get("type") == "assistant":
                _st["read"] = _st.get("read", 0) + usage_once(_st, ev)
                for b in ((ev.get("message") or {}).get("content") or []):
                    if b.get("type") == "tool_use":
                        _calls.append({"name": b.get("name"), "input": b.get("input"), "id": b.get("id")})
                    elif b.get("type") == "text" and (b.get("text") or "").strip():
                        _texts.append(b["text"].strip())
            elif ev.get("type") == "result":
                _res.update(ev)
                # THE TURN IS OVER WHEN THE RESULT ARRIVES. In stream-json
                # input mode the CLI keeps waiting for the next message; the
                # keep-warm ping measured it: result at ~20s, killed at the
                # 120s bound (rc -9). Closing stdin is the EOF that ends it.
                try:
                    close()
                except Exception:                                 # noqa: BLE001
                    pass
        mark("turn%d.start" % n)
        # THE ONLY KILL IS THE RUN BOUND: this turn may use whatever is left of it.
        _left = max(10.0, RUN_TIMEOUT_S - (time.time() - _run_t0))
        rc, err, wall, killed = turn_clock.run_timed(
            _cmd + ["--max-turns", "1"], "/work", _stream, _tfile, _left,
            env=_env, stdin_first=json.dumps(message), on_event=_on)
        mark("turn%d" % n)
        if wall > TURN_LAW_S:
            print("  LAW MISS (turn) : turn %d took %.1fs, over the %ds turn law%s" % (n, wall, TURN_LAW_S, " — KILLED at the run bound" if killed else ""), flush=True)
        u = _res.get("usage") or {}
        # THE API'S OWN ANSWER, from the trace: a 400 "Credit balance is too
        # low" once reached the machine as the agent's NO PLACEMENT.
        _legs = [x for x in _read_trace_rows() if isinstance(x, dict) and str(x.get("path", "")).split("?")[0] == "/v1/messages" and "status" in x and "req_bytes" in x]
        _api = _legs[-1] if _legs else {}
        rec = {"rc": rc, "subtype": _res.get("subtype"), "tool_calls": _calls,
               "text": "\n".join(_texts)[:2000], "killed": bool(killed), "wall": round(wall, 2),
               "bound_s": round(_left, 1), "over_turn_law": wall > TURN_LAW_S,
               "api_status": _api.get("status"), "api_head": str(_api.get("head") or "")[:200], "api_calls_seen": len(_legs),
               "usage": {"read": u.get("cache_read_input_tokens"), "write": u.get("cache_creation_input_tokens"),
                         "in": u.get("input_tokens"), "out": u.get("output_tokens"),
                         # WHICH TTL WAS WRITTEN. The rewatch probe's review wrote 231,986 as
                         # ephemeral_5m while the local CLI (2.1.226) writes 1h — the keep-warm
                         # cadence and the write rate both hang on this, so it is read per call.
                         "write_1h": (u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens"),
                         "write_5m": (u.get("cache_creation") or {}).get("ephemeral_5m_input_tokens")},
               "cost_usd": _res.get("total_cost_usd"), "err": (err or "")[-300:]}
        try:
            _tj = json.load(open(_tfile, encoding="utf-8"))
            _b = turn_clock.budget(_tj)
            rec["ttft"] = (_b.get("buckets_s") or {}).get("TTFT")
            rec["generating_s"] = (_b.get("buckets_s") or {}).get("GENERATING")
            _turn_recs.append((_tj, _stream))
        except Exception as _te:                                  # noqa: BLE001
            rec["timing"] = "FAILED: %s" % str(_te)[:100]
        print("  TURN %d          : %s  calls=%s  read=%s write=%s out=%s  wall=%.1fs%s"
              % (n, rec["subtype"], [c["name"].split("__")[-1] for c in _calls],
                 rec["usage"]["read"], rec["usage"]["write"], rec["usage"]["out"], wall,
                 ("  text=%r" % rec["text"][:80]) if rec["text"] else ""), flush=True)
        return rec

    def _rewatch(n, final):
        import chatcut_gate as _cgf
        mark("rewatch%d.start" % n)
        _rb = read_back(tok, _stage)
        _items = _rb.get("items") or []
        _bs, _bst, _ = _cgf.base_track(_items)
        _sp, _sst, _swhy = (_cgf.kept_spans(_items, _bs, float(_rb.get("fps") or 30))
                            if _bs else ([], "ABSENT", ""))
        _end, _est, _ewhy = _cgf.timeline_end(_sp)
        mark("rewatch%d.readback" % n)
        _w = {"state": "ABSENT", "why": "no timeline end (%s)" % (_ewhy or _swhy)[:100], "sheets": [], "frames": 0, "times": []}
        if _est == "MEASURED" and _end:
            _sheets, _times = _preview_frames(tok, _stage["projectId"], _end, fps=float(_rb.get("fps") or 30),
                                              mark=lambda k: mark("rewatch%d.%s" % (n, k)))
            _w = {"state": "MEASURED" if _sheets else "ABSENT", "why": "%d sheet(s)" % len(_sheets),
                  "sheets": _sheets, "frames": len(_times), "times": _times,
                  "instrument": "preview_timeline x5 parallel (picked 2026-09-17: 47s vs 75s export->upload->inspect; both composite)"}
            # THE SHEETS TRAVEL WITH THE RECORD, so a report can show what the
            # review saw instead of counting it (RESULTS[run_id-sheets]).
            try:
                import base64 as _b64
                _sb = RESULTS.get(run_id + "-sheets") or {}
                _sb["rewatch%d" % n] = [_b64.b64encode(open(x, "rb").read()).decode() for x in _sheets]
                RESULTS[run_id + "-sheets"] = _sb
            except Exception as _sbe:                             # noqa: BLE001
                print("  SHEETS PERSIST  : FAILED %s" % str(_sbe)[:80], flush=True)
        mark("rewatch%d.watch" % n)
        _props = {}
        _base = _stage.get("baseItemId")
        for it in [x for x in _items if str(x.get("id") or "").replace("-", "")[:10] != str(_base or "").replace("-", "")[:10]][:20]:
            try:
                _ii = _mcp_call(tok, "inspect_item", {"projectId": _stage["projectId"], "itemId": it.get("id")}, expect=None)
                _pv = _deep_find(_ii, "propertyOverrides") or _deep_find(_ii, "effectiveProps") or _deep_find(_ii, "properties")
                if _pv:
                    _props[str(it.get("id"))] = _pv
            except Exception as _ie:                              # noqa: BLE001
                _props[str(it.get("id"))] = {"inspect_item": "FAILED %s" % str(_ie)[:80]}
        mark("rewatch%d.props" % n)
        _rec = derive_record(_items, _beats, _base, "\n".join(_shim_whys()))
        _g = gate_b(tok, _stage, _rec.get("rulings"), _rec.get("spec"),
                    source_duration_s=(_dur_for_detect or None), prefetched=_rb, beats=_beats)
        # THE CAPTION BAND FEEDS THE FACE/TEXT CHECK: a graphic on the
        # captions is a collision the review must be told about.
        try:
            _cb, _cbw = caption_band(tok, _stage)
        except Exception as _cbe:                                 # noqa: BLE001
            _cb, _cbw = None, "caption_band FAILED: %s" % str(_cbe)[:80]
        print("  CAPTION BAND    : %s" % (("MEASURED %s" % (list(_cb),)) if _cb else ("ABSENT — %s" % _cbw)), flush=True)
        _h6 = {"state": "ABSENT", "why": "not run"}
        try:
            _h6 = verify_hop6_clear(None, "/work/source.mp4", items=_items, caption_band=_cb)
        except Exception as _h6e:                                 # noqa: BLE001
            _h6 = {"state": "ABSENT", "why": "hop6 %s" % str(_h6e)[:80]}
        _faults = fault_lines(_g, _h6, None, _items, _base)
        _scan = []
        try:
            if os.path.exists("/work/edit.mp4"):
                _dl, _dsum = rendered_defects("/work/edit.mp4", spans=_sp, source_path="/work/source.mp4",
                                              fps=float(_rb.get("fps") or 30), expect_end_frames=_end)
                _scan = _dl
        except Exception as _se:                                  # noqa: BLE001
            _scan = ["  THE SCAN FAILED (%s)" % str(_se)[:80]]
        mark("rewatch%d.checks" % n)
        _msg = rewatch_message(n, _w, timeline_lines(_items, _props, _base), _faults, _scan, final=final)
        print("  REWATCH %d       : %s — %d item(s), %d fault(s), props for %d"
              % (n, _w["why"], len(_items), len(_faults), len(_props)), flush=True)
        return {"message": _msg, "watch": {k: v for k, v in _w.items() if k != "sheets"}, "sheets": len(_w.get("sheets") or []),
                "items": len(_items), "faults": _faults, "scan": _scan[:12], "gate_verdict": _g.get("verdict"),
                "scan_state": "MEASURED" if os.path.exists("/work/edit.mp4") else "ABSENT (no render before the final export; the scan runs on it)",
                "inspect_item_calls": len(_props)}

    def _shim_whys():
        out = []
        try:
            for ln in open("/work/mcp_shim.log", encoding="utf-8"):
                try:
                    j = json.loads(ln)
                except ValueError:
                    continue
                for w in (j.get("whys") or []):
                    out.append("%s: %s" % (w.get("op"), w.get("why")))
        except Exception:                                         # noqa: BLE001
            pass
        return out

    _run_t0 = time.time()
    _tm = run_three_turns(_invoke, _rewatch, _first_message)
    mark("agent")
    _tm["whys"] = _shim_whys()
    # THE THINKING ARM, AS SENT (not as named): measured through the proxy
    # 2026-09-17 on CLI 2.1.226 — CLAUDE_CODE_DISABLE_THINKING=1 sends no
    # thinking block; MAX_THINKING_TOKENS=N sends thinking {type: adaptive}
    # with NO budget (the review call under "3000" thought 7,976 tokens);
    # --effort sets output_config.effort, default xhigh.
    _wire = [((c.get("fp") or {}).get("request_fields") or {}) for c in _read_prefix_rows()]
    _tm["prefix_ttl"] = prefix_ttl
    _tm["thinking_arm"] = {"env": {k: v for k, v in _env.items() if k in ("MAX_THINKING_TOKENS",)},
                           "effort_flag": effort or None,
                           "asked": ("thinking {type: disabled}" if _env.get("MAX_THINKING_TOKENS") == "0"
                                     else "thinking {type: adaptive}, no budget"),
                           "on_the_wire": [{"thinking": w.get("thinking"), "effort": (w.get("output_config") or {}).get("effort")} for w in _wire]}
    print("  THINKING ARM    : %s" % json.dumps(_tm["thinking_arm"]), flush=True)
    if _tm.get("terminal"):
        print("  TERMINAL        : %s — %s" % (_tm["terminal"]["kind"], _tm["terminal"]["why"]), flush=True)
        print("  OWNER PAGE      : run %s ended terminal at turn %s (%s); ledger entry written; "
              "refund applies on the production route" % (run_id, _tm["terminal"].get("at"), _tm["terminal"]["kind"]), flush=True)
    else:
        print("  VERDICT         : %s" % _tm.get("verdict"), flush=True)
    # ── what the record tail reads, from the loop ──
    _turns = _tm["turns"]
    _reads = sum(int((t.get("usage") or {}).get("read") or 0) for t in _turns)
    _state = {"experiment_stop": None, "served": [], "served_urls": set(),
              "rewatch1_fired_by": "turn 1 placed" if len(_tm["rewatches"]) >= 1 else "NEVER FIRED",
              "rewatch2_fired_by": "turn 2 reviewed" if len(_tm["rewatches"]) >= 2 else "NEVER FIRED",
              "rewatch2_scan": ({"state": "MEASURED", "lines": _tm["rewatches"][1].get("scan")} if len(_tm["rewatches"]) >= 2 else None),
              "read_tok": _reads, "pass2": ("SERVED %d sheet(s)" % _tm["rewatches"][0]["sheets"]) if _tm["rewatches"] else "NEVER FIRED — turn 1 placed nothing",
              "pass3": ("SERVED %d sheet(s)" % _tm["rewatches"][1]["sheets"]) if len(_tm["rewatches"]) >= 2 else None,
              "idle_death": None, "frames_delivered": sum(r["sheets"] for r in _tm["rewatches"]),
              "ev": len(_turns), "done_seen": False, "done2_seen": False, "ceiling_hit": None,
              "batches": sum(1 for t in _turns if _edit_ops(t.get("tool_calls"))),
              "batch_results": [], "batch_events": [t["n"] for t in _turns if _edit_ops(t.get("tool_calls"))],
              "agent_text": _tm["whys"], "withhold_lifted_by_harness": None, "render_thread": None}
    # merged timing for the ledger: every turn's events, offset, one budget
    _timing = {"events": [], "wall": 0.0, "cpu_state": "ABSENT", "cpu": []}
    _off = 0.0
    for _tj, _stream_p in _turn_recs:
        for e in (_tj.get("events") or []):
            e2 = dict(e); e2["t"] = float(e.get("t") or 0) + _off; _timing["events"].append(e2)
        _off += float(_tj.get("wall") or 0); _timing["wall"] = _off
    with open("/work/stream.jsonl", "w", encoding="utf-8") as _fh:
        for _tj, _stream_p in _turn_recs:
            try:
                _fh.write(open(_stream_p, encoding="utf-8").read())
            except Exception:                                     # noqa: BLE001
                pass
    _rc = (_turns[-1].get("rc") if _turns else 1)
    _errtxt = (_turns[-1].get("err") if _turns else "no turn ran")
    _wall = _timing["wall"]
    _killed = any(t.get("killed") for t in _turns)

    class _R:
        pass
    r = _R()
    r.returncode, r.stdout, r.stderr = _rc, "", _errtxt
    _timing = {}
    try:
        _timing = json.load(open("/work/timing.json", encoding="utf-8"))
        _budget = turn_clock.budget(_timing)
    except Exception as e:                                        # noqa: BLE001
        _budget = {"state": "FAILED", "why": f"{type(e).__name__}: {e}"}
    try:
        shape = classify_stream("/work/stream.jsonl")
    except Exception as e:                                        # noqa: BLE001
        shape = {"error": f"classifier failed: {type(e).__name__}: {e}"}

    # PER-TURN, PRINTED — the same question the planner now answers. The
    # run-level split says thinking/tool_use/text; only this says whether the
    # deliberation sits on the turns that DECIDE or is spread across turns
    # placing what the plan already settled.
    _pt = (_budget or {}).get("per_turn") or []
    if _pt:
        _tot = sum(t["s"] for t in _pt) or 1.0
        # CORRECTED 2026-09-17: this line said "the CLI takes no effort flag".
        # It does (`--effort`, measured through the proxy: output_config.effort,
        # default xhigh), and MAX_THINKING_TOKENS is not a cap — see THINKING ARM.
        print("  MODEL TIME BY TURN: %.1fs over %d turn(s)   effort: %s "
              "(MAX_THINKING_TOKENS=%s sends adaptive thinking, not a budget)"
              % (sum(t["s"] for t in _pt), len(_pt), (effort or "xhigh (CLI default)"), think_tokens or "unset"),
              flush=True)
        for t in _pt:
            _b = ", ".join("%s %.1fs" % (k, v) for k, v in
                           sorted(t["blocks"].items(), key=lambda kv: -kv[1]))
            print("     turn %-2d %7.2fs  %5.1f%%  %s"
                  % (t["n"], t["s"], 100 * t["s"] / _tot, _b or "-"), flush=True)
        _pk = max(_pt, key=lambda t: t["s"])
        print("     PEAK: turn %d at %.0f%% of model time"
              % (_pk["n"], 100 * _pk["s"] / _tot), flush=True)
    print("  TURN BUDGET     : %s" % json.dumps(
        {k: v for k, v in (_budget or {}).items() if k != "gap_detail"}),
        flush=True)
    # THE RECORD IS BUILT AFTER REWATCH 1 HAS FINISHED SENDING. On
    # final-arch-1 the ceiling killed the stream while the review render was
    # still polling; the thread printed "PASS 2: SERVED 24 frame(s)" AFTER the
    # record had read pass2 as empty and written NEVER FIRED.
    _rt = _state.get("render_thread")
    if _rt is not None and _rt.is_alive():
        _rt.join(timeout=90)
    out = {"pass2": _state.get("pass2") or ("NEVER FIRED — %s"
                                            % (_state.get("rewatch1_fired_by")
                                               or "no batch landed (no edit_item op reached the timeline)")),
           # THE FRAME SERVER'S OWN NUMBER, in the record, because the whole
           # point of it is that a number moves: 89% of everything the agent
           # typed on run 24 was signed S3 URLs it was about to curl.
           "frames_served": {"urls": len(_state.get("served_urls") or ()),
                             "events": _state.get("served") or [],
                             "state": ("MEASURED" if _state.get("served")
                                       else "NONE — the agent never asked "
                                            "preview_timeline for a frame")},
           "think_tokens": think_tokens,
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
        _state.get("frames_delivered", 0) > 0
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
    # ONE READ, SHARED. `_chain_items` asks for `limit: 100` and takes what
    # comes; the gate's own `read_back` pages to exhaustion, so hops 5 and 6
    # now get the SAME complete list the gate reasoned about rather than a
    # possibly-truncated second opinion. Two readers disagreeing about what is
    # on the timeline is how a placement reads as missing to one check and
    # present to another.
    _readback = read_back(tok, _stage) if _stage else {"items": None,
                                                      "read_why": "no prestage"}
    _hop_items = _readback.get("items")
    if _hop_items is None:
        # NAMED, NOT SILENTLY EMPTY. A read that failed and a timeline with
        # nothing on it are different facts, and `_chain_items` returning None
        # rather than [] is the only reason the hops can tell them apart.
        print("  READ-BACK       : FAILED (%s) — falling back to the windowed "
              "reader; hops 5/6 may see a SHORT list"
              % _readback.get("read_why"), flush=True)
        _hop_items = _chain_items(tok, _stage)
    out["chain"]["hop5"] = _hop("hop5", verify_hop5_composition, tok, _stage,
                                plan, _hop_items)
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
    _cap_band, _cap_why = (caption_band(tok, _stage) if _stage
                           else (None, "no prestage"))
    print("  CAPTION BAND    : %s  (%s)"
          % (_cap_band if _cap_band else "ABSENT", _cap_why), flush=True)
    out["caption_band"] = {"band": list(_cap_band) if _cap_band else None,
                           "why": _cap_why}
    out["chain"]["hop6"] = _hop("hop6", verify_hop6_clear, plan,
                                "/work/source.mp4", _hop_items, _cap_band)
    print("  HOP6           : %s  %s" % (out["chain"]["hop6"]["state"],
                                         out["chain"]["hop6"]["why"]), flush=True)
    for _l in out["chain"]["hop6"].get("detail") or []:
        print("      %s" % _l, flush=True)
    out["chain"]["hop7"] = _hop("hop7", verify_hop7_sync, tok, _stage, shape)
    print("  HOP7           : %s  %s" % (out["chain"]["hop7"]["state"],
                                         out["chain"]["hop7"]["why"]), flush=True)
    for _l in out["chain"]["hop7"].get("detail") or []:
        print("      %s" % _l, flush=True)
    # HOPS 3 AND 4 READ A PLAN. On the single-agent path there is none, and a
    # gate that fails the chain on their ABSENT is keyed to a state that no
    # longer exists — every run 6-9 printed "CHAIN GATE: FAILED on hop3, hop4"
    # about hops that could not have run. They are N/A here, not failures.
    _plan_hops = () if plan else ("hop3", "hop4")
    for _h in _plan_hops:
        out["chain"][_h]["state"] = "N/A"
        out["chain"][_h]["why"] = "reads a plan; this path has none — not checked, not failed"
    _failed = [h for h in ("hop3", "hop4", "hop5", "hop6", "hop7")
               if h not in _plan_hops and out["chain"][h]["state"] != "MEASURED"]
    out["chain"]["gate"] = "FAILED" if _failed else "PASSED"
    if _failed:
        print("  CHAIN GATE      : FAILED on %s — the edit is NOT confirmed"
              % ", ".join(_failed), flush=True)

    # ── GATE B RUNS AFTER THE PIXEL HOPS, AND THE EXPORT AFTER IT ───────────
    # THE ORDERING WAS WRONG AND IT UNDID THE RULING. Gate B and the export sat
    # 150 lines ABOVE this, so hops 5, 6 and 7 — the only checks that can see a
    # placement that is present but illegible, covered, or on a face — ran
    # AFTER the export had already been submitted. They were post-hoc
    # diagnostics wearing a gate's name, which is precisely the shape Zac's
    # ruling was written against: "harness checks between the placement call
    # and the export".
    #
    # Now: the hops look at pixels, Gate B reads the timeline back and takes
    # hop 6's measured bands, and only then does anything ship.
    # ── GATE B, AND IT RUNS WHETHER OR NOT THE AGENT COOPERATED ─────────────
    # POST-STREAM ON PURPOSE. An in-loop gate lets the agent fix what it finds,
    # which is worth having — but a gate that only runs when the agent reaches
    # it is a gate with a way past it. This one runs after the stream ends, on
    # every path including a timeout, a crash and an agent that stopped early.
    # The export is downstream of it, so there is no route to a deliverable
    # that does not pass through here.
    # DERIVED, with a file record honoured only if the agent wrote one anyway.
    _file_rec, _file_why = read_record()
    if _file_rec.get("rulings"):
        _record, _rec_why = _file_rec, _file_why
    else:
        _record = derive_record((_readback or {}).get("items") or [], _beats,
                                _stage.get("baseItemId") if _stage else None,
                                "\n".join(_state.get("agent_text") or []))
        _rec_why = ("DERIVED from the read-back (%s); why %s"
                    % (_record["spec"]["derived_from"],
                       "MEASURED (%d chars of reply text)" % len(_record["spec"]["why"] or "")
                       if _record["spec"]["why"] else "ABSENT — the agent gave no line per item"))
    print("  RECORD          : %s" % _rec_why, flush=True)
    _gate = gate_b(tok, _stage, _record.get("rulings"), _record.get("spec"),
                   source_duration_s=(_dur or None), prefetched=_readback,
                   bands=(out["chain"].get("hop6") or {}).get("bands"),
                   beats=_beats) \
        if _stage else {"verdict": "WITHHOLD", "state": "ABSENT", "bad": [],
                        "findings": [], "checked": 0,
                        "read_why": "no prestage — nothing to read back"}
    import sys as _sysg
    _sysg.path.insert(0, "/root")
    import chatcut_gate as _cg
    _remove, _unbuilt = _cg.withhold(_gate)
    # ZAC'S RULING: withhold the placement, export the rest, name it in the
    # ledger. It is the graceful drop production already does for a graphic
    # that cannot clear a face — a component was considered and not placed.
    # THE REMOVAL IS VERIFIED BY READ-BACK, NOT BY THE RESPONSE.
    #
    # `edit_item` takes `deletes`, but the ELEMENT SHAPE and the response key
    # are things I have not observed on a live timeline, and this lane asserts
    # only what it has observed. An earlier version sent `{"itemId": ...}` and
    # demanded `ok` back: a wrong `expect` would have turned every successful
    # delete into a reported failure, and a wrong element shape would have
    # returned success while the item stayed. Both render identically in a log.
    #
    # So the response is not trusted at all. The deletes are sent, the timeline
    # is read again, and an item still present is NOT REMOVED — which is the
    # same principle the gate itself rests on, applied to the gate's own
    # remedy. ChatCut resolves an id PREFIX, so the comparison does too.
    _removed_ok, _remove_why = [], []
    if _remove and _stage:
        for _r in _remove:
            try:
                _mcp_call(tok, "edit_item",
                          {"projectId": _stage["projectId"],
                           "deletes": [{"itemId": _r["item"]}]})
            except Exception as _e:                               # noqa: BLE001
                _remove_why.append("%s: the call failed (%s)"
                                   % (_r["item"], str(_e)[:100]))
        _after = read_back(tok, _stage)
        _still = _after.get("items")
        if _still is None:
            # A PLACEMENT THAT COULD NOT BE CONFIRMED GONE IS NOT GONE.
            _remove_why.append("the timeline could not be re-read (%s), so no "
                               "removal is confirmed" % _after.get("read_why"))
        else:
            _ids = [str(i.get("id") or "") for i in _still]
            for _r in _remove:
                _it = str(_r["item"])
                # HYPHENS OUT: the echo is `78d2b44bc6`, the read-back is
                # `78d2b44b-c6b1-...` — measured 2026-09-17.
                _nh = lambda x: str(x or "").replace("-", "")        # noqa: E731
                _present = any(_nh(_i) == _nh(_it) or _nh(_i).startswith(_nh(_it))
                               or _nh(_it).startswith(_nh(_i)) for _i in _ids if _i)
                if _present:
                    _remove_why.append(
                        "%s IS STILL ON THE TIMELINE after the delete — the "
                        "export carries a placement the gate refused" % _it)
                else:
                    _removed_ok.append(_r)
    print("  WITHHELD        : %d placement(s) removed, %d ruling(s) never "
          "landed%s" % (len(_removed_ok), len(_unbuilt),
                        (", %d COULD NOT BE REMOVED" % len(_remove_why))
                        if _remove_why else ""), flush=True)
    # ── THE FLOOR ──────────────────────────────────────────────────────────
    # A RUN MUST NEVER PRODUCE NOTHING AND COST MONEY.
    #
    # The ceiling stops a run that spends too much. This stops one that spends
    # anything at all for no output: if the timeline is empty when the stream
    # closes there is nothing to ship, and exporting it bills a cloud render to
    # deliver the source back unedited — which reads downstream as a finished
    # job. Three runs today reached this point having placed nothing.
    #
    # EMPTY AND UNREADABLE ARE DIFFERENT DEATHS and it says which. `read_back`
    # separates them already: items == [] with a "0 item(s)" why is genuinely
    # empty; items is None with a FAILED why means nobody could tell. Both
    # refuse to export, and a reader must be able to see which happened —
    # collapsing them is the defect this whole lane is built against.
    _final = read_back(tok, _stage) if _stage else {
        "items": None, "read_why": "no prestage"}
    _fitems = _final.get("items")
    if _fitems is None:
        out["floor"] = {
            "state": "FAILED",
            "why": ("the timeline could not be read back (%s), so whether "
                    "anything was placed is UNKNOWN — refusing to export on a "
                    "timeline nobody could see"
                    % str(_final.get("read_why"))[:200])}
    elif _cg.base_track(_fitems)[1] != _cg.MEASURED:
        # ITEMS ARE NOT AN EDIT. Run 6 put SIX items on the timeline — all of
        # them full-frame motion graphics — and never placed the source video.
        # The floor counted 6 and passed, so a render was billed for graphics
        # over black.
        #
        # AND THE FIX'S FIRST VERSION WAS ITS OWN SECOND READER. It tested
        # `i["type"]`/`i["kind"]` against ("video","clip") — a guessed field
        # name. ChatCut's read-back calls it `itemType`, so on run 7 the floor
        # reported "NOT ONE of them is video" about 36 items while GATE B, from
        # the SAME read-back, named the base-track video item by id. Two
        # readers of one timeline disagreeing, and mine was the invented one.
        # `base_track` already answers this and is RED-proven; it is the only
        # reader now.
        out["floor"] = {
            "state": "NO_BASE",
            "items": len(_fitems),
            "why": ("%d item(s) on the timeline and NOT ONE of them is video "
                    "— there is no footage under the graphics, so an export "
                    "renders overlays on black" % len(_fitems))}
    elif len(_fitems) == 0:
        out["floor"] = {
            "state": "EMPTY",
            "why": ("the timeline holds ZERO items after the stream closed "
                    "(%s) — there is no edit to export, and exporting would "
                    "bill a render to hand back the source unedited"
                    % str(_final.get("read_why"))[:120])}
    else:
        out["floor"] = {"state": "MEASURED",
                        "items": len(_fitems),
                        "why": "%d item(s) on the timeline" % len(_fitems)}
    print("  FLOOR           : %s — %s"
          % (out["floor"]["state"], out["floor"]["why"]), flush=True)

    # THE EXPORT IS THE HARNESS'S, and it is the only path to a deliverable.
    # NOTHING IS EXPORTED AFTER A TERMINAL (ruling 3: kill, ledger, owner page,
    # refund) — the floor once exported the untouched source after a 400.
    if _tm.get("terminal"):
        _export = {"state": "WITHHELD", "why": "terminal %s at turn %s — nothing is exported after a terminal" % (_tm["terminal"]["kind"], _tm["terminal"].get("at"))}
        print("  EXPORT          : WITHHELD — %s" % _export["why"], flush=True)
    elif out["floor"]["state"] != "MEASURED":
        _export = {"state": "REFUSED", "why": out["floor"]["why"]}
        print("  EXPORT          : REFUSED — %s" % out["floor"]["why"],
              flush=True)
    else:
        _export = harness_export(tok, _stage) if _stage else {
            "state": "ABSENT", "why": "no prestage"}
        print("  EXPORT          : %s" % json.dumps(_export), flush=True)

    out["gate"] = {k: v for k, v in _gate.items()
                   if k not in ("findings", "_items")}
    out["gate_findings"] = _gate.get("findings") or []
    # THE DURABLE ARTEFACT. `spec.why` is the field the 43% was found in —
    # seven ledgers compared. A run that does not carry it is a run whose
    # failure is not diagnosable afterwards, which is the capability the
    # planner/executor split was keeping.
    out["spec"] = _record.get("spec")
    out["rulings"] = _record.get("rulings")
    out["record_why"] = _rec_why
    out["withheld"] = {"removed": _removed_ok, "unbuilt": _unbuilt,
                       "could_not_remove": _remove_why}
    out["export"] = _export

    out["visual_pass"] = {
        "read_source_sheet": _saw_sheet,
        "previewed_before_render": _looked_before_render,
        "state": ("MEASURED" if (_saw_sheet and _looked_before_render)
                  else "FAILED"),
    }
    print("  VISUAL PASS     : %s  sheet=%s  preview_before_render=%s"
          % (out["visual_pass"]["state"], _saw_sheet, _looked_before_render),
          flush=True)
    # THE TURN MACHINE'S OWN RECORD. Printed AND ledgered in the commit that
    # adds it: run 4 could not be diagnosed from its ledger because nothing
    # said why a rewatch fired or how many batches landed, and the answer had
    # to be reconstructed from 41 tool calls by hand.
    # THE SCAN'S OWN RESULT, IN THE RECORD. It was written into `_state`,
    # printed once, and read by nothing — so the durable record could not say
    # whether the desync/black/freeze/silence scan had run at all. That is the
    # precise distinction the scan's three states exist for ("0 findings" vs
    # "0 checks completed"), lost one layer below where it was built.
    # THE TIMELINE AS CHATCUT RETURNS IT, VERBATIM AND BOUNDED.
    #
    # `kept_spans` hard-fails when a base-track video item has no
    # `sourceRange.startSeconds/endSeconds`, and that single failure is
    # upstream of every ABSENT in runs 7, 8 and 9: no spans -> no timeline end
    # -> no render window -> the review is served nothing -> no acceptance
    # criteria and no gate. Whether the agent omits a field or ChatCut simply
    # does not return one for an untrimmed item is NOT DECIDABLE from any
    # record so far, because `read_back` computed the items and the record
    # never carried them.
    #
    # Three items with their keys settles it in one run. I have guessed an
    # envelope shape twice this week and been wrong twice; this is the same
    # correction as the raw-wire sample, applied to ChatCut's side.
    _fi = (_final.get("items") or [])
    out["timeline_sample"] = {
        "count": len(_fi),
        "video_count": sum(1 for i in _fi
                           if str(i.get("itemType")) == "video"),
        "items": [{k: i.get(k) for k in sorted(i.keys())[:18]}
                  for i in _fi[:3]],
        "why": ("verbatim read-back items — kept_spans needs "
                "sourceRange.startSeconds/endSeconds and "
                "timelineRange.fromFrame/toFrame; read these before adding a "
                "field to the add shape"),
    }
    out["rewatch2_scan"] = _state.get("rewatch2_scan") or {
        "state": "NEVER RAN", "why": "the second rewatch did not reach the scan"}
    out["turn_machine"] = {
        "batches": _state.get("batches", 0),
        "batch_events": _state.get("batch_events") or [],
        "assistant_events_seen": _state.get("ev", 0),
        "rewatch1_fired_by": _state.get("rewatch1_fired_by") or "NEVER FIRED",
        "rewatch2_fired_by": _state.get("rewatch2_fired_by") or "NEVER FIRED",
        "done_seen": bool(_state.get("done_seen")),
        "done2_seen": bool(_state.get("done2_seen")),
        "idle_death": _state.get("idle_death"),
        "read_tok": _state.get("read_tok", 0),
        "read_ceiling": _ceil,
        # MEASURED / ABSENT, never a bare number: a run that stopped on the
        # ceiling and one that merely spent a lot look identical once you are
        # reading the token count alone.
        "ceiling": _state.get("ceiling_hit") or "NOT REACHED",
        "three_turns": {"api_calls": len(_tm["turns"]), "verdict": _tm.get("verdict"),
                        "terminal": _tm.get("terminal"), "cold_write": _tm.get("cold_write"),
                        "killed": bool(_killed), "kill_reason": _timing.get("kill_reason")},
    }
    print("  TURN MACHINE    : %d batch(es)  rewatch1=%s  rewatch2=%s  "
          "read=%d/%d"
          % (out["turn_machine"]["batches"],
             out["turn_machine"]["rewatch1_fired_by"],
             out["turn_machine"]["rewatch2_fired_by"],
             out["turn_machine"]["read_tok"], _ceil), flush=True)
    out["wall_s"] = round(time.time() - t0, 2)
    out["prestage_phases"] = (_stage or {}).get("phases")
    # SECTION C: the system prompt and the first message AS RUN, in full —
    # images as their pixel sizes, every text block verbatim.
    out["system_prompt"] = sys_prompt
    _fm = []
    for _b in (out_first.get("message") or {}).get("content") or []:
        if _b.get("type") == "text":
            _fm.append({"text": _b.get("text")})
        elif _b.get("type") == "image":
            try:
                from PIL import Image as _PI
                import base64 as _b64, io as _io
                _im = _PI.open(_io.BytesIO(_b64.b64decode(_b["source"]["data"])))
                _fm.append({"image": "%dx%d %s" % (_im.size[0], _im.size[1], _b["source"]["media_type"])})
            except Exception as _ie:                              # noqa: BLE001
                _fm.append({"image": "unreadable: %s" % str(_ie)[:60]})
    out["first_message"] = _fm
    out["three_turns"] = _tm
    # SECTION E: THE PER-RUN LINE, printed in the commit that adds it.
    _kinds = {}
    for _t in _tm["turns"]:
        for _c in (_t.get("tool_calls") or []):
            _k = str(_c.get("name") or "").split("__")[-1]
            _kinds[_k] = _kinds.get(_k, 0) + 1
    _rd = sum(int((_t.get("usage") or {}).get("read") or 0) for _t in _tm["turns"])
    _wr = sum(int((_t.get("usage") or {}).get("write") or 0) for _t in _tm["turns"])
    _in = sum(int((_t.get("usage") or {}).get("in") or 0) for _t in _tm["turns"])
    _ou = sum(int((_t.get("usage") or {}).get("out") or 0) for _t in _tm["turns"])
    _wr1 = sum(int((_t.get("usage") or {}).get("write_1h") or 0) for _t in _tm["turns"])
    _wr5 = sum(int((_t.get("usage") or {}).get("write_5m") or 0) for _t in _tm["turns"])
    _ttl_state = "MEASURED" if (_wr1 + _wr5) == _wr else "ABSENT (no TTL split in usage; priced at 1h)"
    _usd = (_rd * 0.30 + _wr5 * 3.75 + (_wr - _wr5) * 6.00 + _in * 3.00 + _ou * 15.00) / 1e6
    _cli_usd = sum(float(_t.get("cost_usd") or 0) for _t in _tm["turns"])
    _req_mb = [round(float(x.get("req_bytes") or 0) / 1e6, 2) for x in (out.get("proxy_trace") or []) if isinstance(x, dict)
               and str(x.get("path", "")).split("?")[0] == "/v1/messages" and "req_bytes" in x]
    if any(m > 30.0 for m in _req_mb):
        print("  REQUEST SIZE    : %s MB per call — over 30 MB the CLI prunes old images to stay under the API's 32 MB limit and the prefix is rewritten" % _req_mb, flush=True)
    out["run_line"] = {"model": model, "api_calls": len(_tm["turns"]), "tool_calls_by_kind": _kinds, "request_mb": _req_mb,
                       "model_wall_s": round(_wall, 1),
                       "tokens": {"cached_read": _rd, "cache_write": _wr, "cache_write_1h": _wr1, "cache_write_5m": _wr5,
                                  "uncached_in": _in, "out": _ou, "ttl_split": _ttl_state},
                       "usd_at_rate": round(_usd, 4), "usd_cli": round(_cli_usd, 4),
                       "rates": "read $0.30/M, write 1h $6/M or 5m $3.75/M by the measured split, in $3/M, out $15/M",
                       "cli_version": _cli_ver,
                       "marks_s": marks, "wall_s": out["wall_s"], "verdict": _tm.get("verdict"),
                       "terminal": _tm.get("terminal"), "cold_write": _tm.get("cold_write")}
    print("  RUN LINE        : %s | api_calls=%d | tools=%s | tokens read=%d write=%d (1h %d / 5m %d) in=%d out=%d | request MB per call=%s | $%.4f at rate ($%.4f CLI) | wall=%.1fs | cli=%s | marks=%s"
          % (model, len(_tm["turns"]), _kinds, _rd, _wr, _wr1, _wr5, _in, _ou, _req_mb, _usd, _cli_usd, out["wall_s"],
             _cli_ver, json.dumps(marks)), flush=True)
    if out["wall_s"] > LAW_WALL_S:
        print("  LAW MISS        : %.1fs over the %ds law — stages: %s" % (out["wall_s"], LAW_WALL_S, json.dumps(marks)), flush=True)
    if _tm.get("cold_write", {}).get("cold"):
        try:
            _warm = WARM.get("last") if "last" in WARM else None
        except Exception:                                         # noqa: BLE001
            _warm = None
        _mins = ((time.time() - float(_warm["t"])) / 60.0) if _warm and _warm.get("t") else None
        _ttl = warm_ttl_minutes(_warm)
        print("  COLD WRITE      : call 1 wrote %d read %d — %s since the last warm (its TTL: %s)%s"
              % (_tm["cold_write"]["write"], _tm["cold_write"]["read"],
                 ("%.0f min" % _mins) if _mins is not None else "no warm on record",
                 ("%d min" % _ttl) if _ttl else "unknown",
                 " — a DEFECT, the ping was alive" if (_mins is not None and _ttl and _mins < _ttl) else ""), flush=True)
        out["run_line"]["warm_ttl_minutes"] = _ttl
        out["run_line"]["cold_write_minutes_since_warm"] = _mins
    # THE UPSTREAM LEG OF EVERY CALL (status, first byte, bytes relayed, error).
    out["proxy_trace"] = []
    try:
        for _ln in open("/work/proxy_trace.jsonl", encoding="utf-8"):
            out["proxy_trace"].append(json.loads(_ln))
    except Exception as _pte:                                     # noqa: BLE001
        out["proxy_trace"] = "ABSENT %s" % str(_pte)[:80]
    print("  PROXY TRACE     : %s" % json.dumps([{k: v for k, v in r.items() if k in ("status", "ttfb_s", "done_s", "relayed_bytes", "error", "failed_s", "req_bytes")}
                                                  for r in out["proxy_trace"]] if isinstance(out["proxy_trace"], list) else out["proxy_trace"])[:1200], flush=True)
    # THE PREFIX, CALL BY CALL, and against the previous run's first call.
    out["prefix_calls"] = []
    try:
        for _ln in open("/work/prefix_calls.jsonl", encoding="utf-8"):
            out["prefix_calls"].append(json.loads(_ln))
    except Exception as _pe:                                      # noqa: BLE001
        out["prefix_calls"] = {"state": "ABSENT", "why": str(_pe)[:120]}
    if isinstance(out["prefix_calls"], list) and out["prefix_calls"]:
        for _r in out["prefix_calls"]:
            _d = _r.get("vs_prev") or {}
            print("  PREFIX call %-2s : tools=%s system=%s msgs=%d | vs prev: %s%s"
                  % (_r.get("n"), (_r.get("fp") or {}).get("tools", {}).get("n"),
                     (_r.get("fp") or {}).get("system", {}).get("sha"),
                     len((_r.get("fp") or {}).get("messages") or []),
                     _d.get("state"), (" at %s" % _d["first_diff"]) if _d.get("first_diff") else ""),
                  flush=True)
        try:
            import api_proxy as _px2
            _first = out["prefix_calls"][0]
            _body1 = json.load(open("/work/req_first.json", encoding="utf-8"))
            _ref = RESULTS.get("prefix-ref") if "prefix-ref" in RESULTS else None
            if _ref and _ref.get("body_lite"):
                out["prefix_vs_previous_run"] = dict(
                    _px2.diff_prefix(_ref["body_lite"], _ref["fp"], _body1, _first["fp"]),
                    previous_run=_ref.get("run_id"))
            else:
                out["prefix_vs_previous_run"] = {"state": "NO REFERENCE — first run with the proxy"}
            print("  PREFIX vs prev run: %s%s" % (
                out["prefix_vs_previous_run"].get("state"),
                (" at %s" % out["prefix_vs_previous_run"]["first_diff"])
                if out["prefix_vs_previous_run"].get("first_diff") else ""), flush=True)
            # what the NEXT run diffs against: the first call, images dropped to
            # their sha so the reference stays small
            def _lite(body):
                msgs = []
                for _m in body.get("messages") or []:
                    _c = _m.get("content")
                    if isinstance(_c, list):
                        _c = [({"type": "image", "sha": _px2._sha(b)[0]} if (b or {}).get("type") == "image" else b) for b in _c]
                    msgs.append({"role": _m.get("role"), "content": _c})
                return {"tools": body.get("tools"), "system": body.get("system"), "messages": msgs}
            _lite1 = _lite(_body1)
            RESULTS["prefix-ref"] = {"run_id": run_id, "fp": _px2.fingerprint(_lite1), "body_lite": _lite1,
                                     "note": "images replaced by their sha; message shas here differ from the live fingerprint"}
        except Exception as _pe2:                                 # noqa: BLE001
            out["prefix_vs_previous_run"] = {"state": "FAILED", "why": "%s: %s" % (type(_pe2).__name__, str(_pe2)[:160])}
    RESULTS[run_id] = out
    print(f"  RESULT PERSISTED: chatcut-results[{run_id}]", flush=True)
    return out



# NO SECRETS. This fetches a public CDN URL and runs two local models; it
# touches neither ChatCut nor Anthropic, and a function that asks for
# credentials it does not use is a function that fails for the wrong reason.

@app.function(image=IMG, timeout=300, cpu=2, memory=4096,
              secrets=[modal.Secret.from_name("chatcut-oauth"),
                       modal.Secret.from_name("anthropic-api-key")])
def keep_warm(model: str = "claude-sonnet-5", proxy: bool = True, base_url: str = "", prefix_ttl: str = "1h"):
    """ONE PING AGAINST THE BYTE-IDENTICAL PREFIX, so the watch stays warm.

    Zac, ruling 1 (2026-09-17): one ping per 55 minutes on the 1h TTL. The
    CLI marks the last two messages (measured through the proxy), so a
    --resume of the watch with a one-word message writes the cache entry a
    job's first call looks up. Same image, same shim, same system.md, same
    watch — the cache key is those bytes. Records read/write in the
    chatcut-warm Dict; a job's call 1 reads it to age a cold write.
    A schedule is not attached here: this lane does not deploy (Rule 0). Run
    it by hand before a job — `modal run chatcut_job_app.py::warm`.
    """
    os.makedirs("/work", exist_ok=True)
    tok = _access_token()
    sid = install_watch("/work")
    write_cli_context(tok)
    env = {"ENABLE_TOOL_SEARCH": "false", "MAX_THINKING_TOKENS": str(DEFAULT_THINK_TOKENS)}
    sys.path.insert(0, "/root")
    import turn_clock
    # `proxy`: the same ping THROUGH the recording proxy — the first job run
    # through it (h-th-think0) got no byte back in 120s, and a 228k ping is
    # the $0.10 way to ask whether proxy+CLI is the pair that fails in the
    # container before a $2.50 run asks again.
    if proxy:
        import api_proxy as _px
        _px.FINGERPRINTS, _px.FIRST_BODY, _px.TRACE = "/work/warm_fp.jsonl", "/work/warm_first.json", "/work/warm_trace.jsonl"
        if prefix_ttl != "1h":
            raise RuntimeError("a keep-warm ping only exists for the 1h production shape; development runs carry no ping (prefix_ttl=%r)" % prefix_ttl)
        _px.RUN_FIRST_TEXT = RUN_FIRST_TEXT_PING       # the same watch-end breakpoint the job gets
        _pp, _pca = _px.serve_mitm(0, "/work/mitm")
        env.update(_px.mitm_env(_pp, _pca))
    elif base_url:
        # the experiment: the REAL endpoint, but named through the env var —
        # does the variable's presence alone change what the CLI sends?
        env["ANTHROPIC_BASE_URL"] = base_url
    msg = _message([{"type": "text", "text": "ping"}])
    res = {}

    def _on(ev, send, close, kill=None):
        if ev.get("type") == "result":
            res.update(ev)
            try:
                close()                    # EOF on stdin ends the invocation
            except Exception:                                     # noqa: BLE001
                pass
    rc, err, wall, killed = turn_clock.run_timed(
        cli_command(sid, model) + ["--max-turns", "1"], "/work", "/work/warm_stream.jsonl",
        "/work/warm_timing.json", 120, env=env, stdin_first=json.dumps(msg), on_event=_on)
    u = res.get("usage") or {}
    _cc = u.get("cache_creation") or {}
    # WHAT CAME BACK, in both modes: output volume and the reply's head — the
    # proxied ping streamed thousands of tokens for "ping" while the direct
    # one answered in ~20s; the two must be compared on the same fields.
    _out_tok = u.get("output_tokens"); _think = (u.get("output_tokens_details") or {}).get("thinking_tokens")
    _reply = (res.get("result") or "")[:300]
    rec = {"t": time.time(), "read": u.get("cache_read_input_tokens"),
           "out": _out_tok, "thinking": _think, "reply_head": _reply, "result_wall_s": res.get("duration_api_ms"),
           "write": u.get("cache_creation_input_tokens"), "rc": rc, "wall": round(wall, 1),
           "write_1h": _cc.get("ephemeral_1h_input_tokens"), "write_5m": _cc.get("ephemeral_5m_input_tokens"),
           "cli_version": cli_version(), "proxy": bool(proxy), "subtype": res.get("subtype"), "killed": bool(killed)}
    if proxy:
        try:
            rec["proxy_trace"] = [json.loads(l) for l in open("/work/warm_trace.jsonl", encoding="utf-8") if l.strip()]
        except Exception as _te:                                  # noqa: BLE001
            rec["proxy_trace"] = "ABSENT %s" % str(_te)[:80]
        print("  PROXY TRACE     : %s" % json.dumps(rec["proxy_trace"])[:2500], flush=True)
        try:
            rec["fingerprints"] = [json.loads(l) for l in open("/work/warm_fp.jsonl", encoding="utf-8") if l.strip()]
        except Exception as _fe:                                  # noqa: BLE001
            rec["fingerprints"] = "ABSENT %s" % str(_fe)[:80]
        print("  PROXY FP        : %s" % json.dumps(rec["fingerprints"])[:600], flush=True)
        rec["stderr_tail"] = (err or "")[-800:]
        print("  CLI STDERR      : %r" % rec["stderr_tail"][-400:], flush=True)
        # THE REQUEST'S NON-PREFIX FIELDS, which the fingerprint does not cover
        try:
            _fb = json.load(open("/work/warm_first.json", encoding="utf-8"))
            rec["request_fields"] = {k: _fb.get(k) for k in ("thinking", "output_config", "max_tokens", "stream", "context_management", "temperature", "top_p")}
            rec["request_fields"]["metadata_keys"] = sorted((_fb.get("metadata") or {}).keys())
            rec["request_fields"]["cache_control"] = [(i, b.get("cache_control")) for i, b in enumerate(_fb.get("system") or []) if isinstance(b, dict) and b.get("cache_control")]
            _recv = next((r for r in (rec.get("proxy_trace") or []) if isinstance(r, dict) and r.get("req_headers")), {})
            rec["request_fields"]["anthropic_beta"] = (_recv.get("req_headers") or {}).get("anthropic-beta") or (_recv.get("req_headers") or {}).get("Anthropic-Beta")
            rec["request_fields"]["user_agent"] = (_recv.get("req_headers") or {}).get("user-agent") or (_recv.get("req_headers") or {}).get("User-Agent")
        except Exception as _fbe:                                 # noqa: BLE001
            rec["request_fields"] = "ABSENT %s" % str(_fbe)[:80]
        print("  REQUEST FIELDS  : %s" % json.dumps(rec["request_fields"])[:1200], flush=True)
        # THE CLI'S SIDE OF THE SAME SECONDS: what it emitted, and when.
        try:
            _lines = [json.loads(l) for l in open("/work/warm_stream.jsonl", encoding="utf-8") if l.strip()]
            rec["cli_events"] = [{"type": e.get("type"), "subtype": e.get("subtype"),
                                  "event": ((e.get("event") or {}).get("type") if isinstance(e.get("event"), dict) else None)}
                                 for e in _lines][:12]
            rec["cli_event_count"] = len(_lines)
        except Exception as _ce:                                  # noqa: BLE001
            rec["cli_events"] = "ABSENT %s" % str(_ce)[:80]
        try:
            _tj = json.load(open("/work/warm_timing.json", encoding="utf-8"))
            rec["cli_timeline"] = [(round(float(e.get("t") or 0), 1), e.get("kind") or e.get("type")) for e in (_tj.get("events") or [])][:12]
        except Exception as _ce:                                  # noqa: BLE001
            rec["cli_timeline"] = "ABSENT %s" % str(_ce)[:80]
        print("  CLI EVENTS      : n=%s %s | timeline %s" % (rec.get("cli_event_count"), json.dumps(rec["cli_events"])[:700], json.dumps(rec["cli_timeline"])[:400]), flush=True)
    WARM["last"] = rec
    print("  WARM            : read=%s write=%s (1h %s / 5m %s) out=%s thinking=%s wall=%.1fs rc=%s cli=%s reply=%r"
          % (rec["read"], rec["write"], rec["write_1h"], rec["write_5m"], rec["out"], rec["thinking"], wall, rc, rec["cli_version"], rec["reply_head"][:120]), flush=True)
    return rec


@app.local_entrypoint()
def warm(proxy: bool = True, base_url: str = ""):
    from require_detach import require_detach
    require_detach("the keep-warm ping")
    print(json.dumps(keep_warm.remote(proxy=proxy, base_url=base_url))[:3000])


@app.function(image=IMG, timeout=900, cpu=4, memory=8192,
              secrets=[modal.Secret.from_name("chatcut-oauth"),
                       modal.Secret.from_name("anthropic-api-key")])
def probe_rewatch(clip_url: str, model: str = "claude-sonnet-5"):
    """RULING 5 + THE PLANTED-DEFECT PROOF, on one scratch timeline.

    Plants three defects the review must name — a card centred on the
    speaker's face, a second caption track showing the same speech, an
    overlay at 3x its intended size — then times both rewatch instruments on
    that same timeline: preview_timeline's viewer (composed pixels, 9 per
    call) and export -> upload -> inspect_asset (watch_asset). Each is judged
    on wall AND on whether its frames show the composite. Then ONE review call
    (--max-turns 1, the real model, the rewatch message exactly as a job
    sends it) and the record says which of the three it named.
    """
    _t0 = time.time()
    RESULTS["probe-rewatch"] = {"state": "STARTED", "t0": _t0}
    os.makedirs("/work", exist_ok=True)
    subprocess.run(["curl", "-fsSL", "-o", "/work/source.mp4", clip_url], check=True, timeout=300)
    tok = _access_token()
    stage = prestage(tok, "", controls={}, source_path="/work/source.mp4",
                     want_components={"StatCard", "caption:TwoTone", "PullQuote"}, titles=[])
    pid = stage["projectId"]
    comps = stage.get("components") or {}
    _aid = lambda n: (comps.get(n) or {}).get("assetId") if isinstance(comps.get(n), dict) else comps.get(n)
    out = {"state": "RUNNING", "projectId": pid, "components": {k: (_aid(k) or None) for k in ("StatCard", "caption:TwoTone", "PullQuote")}, "planted": []}
    # the defects: centre band card over the face, two caption tracks, a 3x overlay
    adds = [{"type": "motion-graphic", "assetId": _aid("StatCard"), "fromFrame": 30, "durationInFrames": 150,
             # THE LABELS CARRY NO DETECTION WORD. The first probe planted
             # "ON THE FACE" and "THREE TIMES TOO BIG", the review quoted both
             # back, and the keyword reader scored 3 of 3 named when it had
             # named ONE (the duplicate captions) — the other two matched the
             # plant's own text. Read by eye 2026-09-17.
             "propertyOverrides": {"label": "REVENUE", "value": "10x", "offsetY": 0}},
            {"type": "motion-graphic", "assetId": _aid("caption:TwoTone"), "fromFrame": 0, "durationInFrames": 600},
            {"type": "motion-graphic", "assetId": _aid("caption:TwoTone"), "fromFrame": 0, "durationInFrames": 600},
            {"type": "motion-graphic", "assetId": _aid("PullQuote"), "fromFrame": 300, "durationInFrames": 150,
             "propertyOverrides": {"text": "THE PAYOFF", "fontSize": 3 * 64}}]
    for a in adds:
        try:
            r = _mcp_call(tok, "edit_item", {"projectId": pid, "adds": [a]}, expect="adds")
            _eid = ((r.get("adds") or [{}])[0] or {}).get("id")
            out["planted"].append({"add": a, "echo": str(r.get("adds"))[:160], "echo_id": _eid})
        except Exception as e:                                    # noqa: BLE001
            out["planted"].append({"add": a, "FAILED": str(e)[:200]})
    rb = read_back(tok, stage); items = rb.get("items") or []
    out["items_on_timeline"] = len(items)
    sys.path.insert(0, "/root")
    import chatcut_gate as _cg
    _bt, _, _ = _cg.base_track(items); _sp, _, _ = _cg.kept_spans(items, _bt, 30.0); _end, _, _ = _cg.timeline_end(_sp)
    # instrument A: preview_timeline viewer, 9 frames per call, ~40 frames
    tA = time.time(); a_frames = []; a_calls = 0
    try:
        for k in range(0, 40, 9):
            fr = [int(_end * (k + i + 0.5) / 40) for i in range(9) if k + i < 40]
            r = _mcp_call(tok, "preview_timeline", {"projectId": pid, "views": ["viewer"], "viewerFrames": fr}, expect=None)
            a_calls += 1
            a_frames += _frame_urls(json.dumps(r) + str(r.get("_text") or ""))
        import chatcut_reference as _cr
        got, fst = _cr.fetch(a_frames, "/work/probe_preview", cap=45)
        sheetsA = tile_sheets([("f%d" % i, pth) for i, (_u, pth) in enumerate(got)], "/work/probe_preview/sheets", per_sheet=20, cols=5, cell_w=180)
        out["preview_timeline"] = {"wall_s": round(time.time() - tA, 1), "calls": a_calls, "frames": len(got), "sheets": len(sheetsA), "fetch": fst}
    except Exception as e:                                        # noqa: BLE001
        out["preview_timeline"] = {"wall_s": round(time.time() - tA, 1), "FAILED": str(e)[:200]}; sheetsA = []
    # instrument B: export -> upload -> inspect_asset
    tB = time.time(); marksB = {}
    sheetsB, timesB = _edit_frames(tok, pid, _end, mark=lambda k: marksB.__setitem__(k, round(time.time() - tB, 1)))
    out["export_upload_inspect"] = {"wall_s": round(time.time() - tB, 1), "marks": marksB, "frames": len(timesB), "sheets": len(sheetsB)}
    # one review call, the rewatch message exactly as a job sends it, on instrument B's sheets (or A's if B failed)
    sid = install_watch("/work"); write_cli_context(tok)
    tl = timeline_lines(items, None, stage.get("baseItemId"))
    msg = rewatch_message(1, {"frames": len(timesB or []), "sheets": sheetsB or sheetsA, "state": "MEASURED"}, tl, [], [], final=False)
    import turn_clock
    res = {}; texts = []; calls = []

    def _on(ev, send, close, kill=None):
        if ev.get("type") == "result":
            res.update(ev)
            try:
                close()
            except Exception:                                     # noqa: BLE001
                pass
        if ev.get("type") == "assistant":
            for b in ((ev.get("message") or {}).get("content") or []):
                if b.get("type") == "text": texts.append(b.get("text") or "")
                if b.get("type") == "tool_use": calls.append({"name": b.get("name"), "input": b.get("input")})
    env = {"ENABLE_TOOL_SEARCH": "false", "MAX_THINKING_TOKENS": str(DEFAULT_THINK_TOKENS)}
    tC = time.time()
    rc, err, wall, killed = turn_clock.run_timed(cli_command(sid, model) + ["--max-turns", "1"], "/work", "/work/probe_review.jsonl",
                                                 "/work/probe_review_timing.json", 180, env=env, stdin_first=json.dumps(msg), on_event=_on)
    # NAMED = an op touched THAT plant and its `why` says the planted fault.
    # A keyword over the whole reply matched the plants' own labels quoted
    # back (first probe: "3 of 3" for one real). The reply text is kept and
    # reported beside it, never counted.
    _pid8 = lambda x: str(x or "").replace("-", "")[:8]
    _plants = {"card": _pid8((out["planted"][0] or {}).get("echo_id")),
               "captions": [_pid8((out["planted"][i] or {}).get("echo_id")) for i in (1, 2)],
               "quote": _pid8((out["planted"][3] or {}).get("echo_id"))}
    _ops = [(k, o) for c in calls if str(c.get("name") or "").endswith("edit_item")
            for k in ("deletes", "updates") for o in ((c.get("input") or {}).get(k) or [])]
    _touched = {}
    for k, o in _ops:
        _touched.setdefault(_pid8(o.get("id")), []).append("%s: %s" % (k, str(o.get("why") or "")))
    _why = lambda ids: " ".join(w for i in ids for w in _touched.get(i, [])).lower()
    _acted = {"card": bool(_touched.get(_plants["card"])), "captions": any(_touched.get(i) for i in _plants["captions"]),
              "quote": bool(_touched.get(_plants["quote"]))}
    out["review"] = {"wall_s": round(time.time() - tC, 1), "rc": rc, "subtype": res.get("subtype"),
                     "usage": res.get("usage"), "text": "\n".join(texts)[:2000], "tool_calls": calls[:6],
                     "plants": _plants, "acted_on": _acted, "ops_whys": _touched,
                     "named": {"card_on_face": _acted["card"] and any(w in _why([_plants["card"]]) for w in ("face", "speaker", "cover", "eyes", "head")),
                               "duplicate_captions": _acted["captions"] and any(w in _why(_plants["captions"]) for w in ("duplicate", "two caption", "second caption", "same", "twice", "both")),
                               "oversized_overlay": _acted["quote"] and any(w in _why([_plants["quote"]]) for w in ("big", "large", "size", "scale", "font", "huge", "oversized"))}}
    try:
        import base64 as _b64
        out["sheets_b64"] = {"A": [_b64.b64encode(open(x, "rb").read()).decode() for x in (sheetsA or [])],
                             "B": [_b64.b64encode(open(x, "rb").read()).decode() for x in (sheetsB or [])]}
    except Exception as _sbe:                                     # noqa: BLE001
        out["sheets_b64"] = "FAILED %s" % str(_sbe)[:80]
    out["wall_s"] = round(time.time() - _t0, 1); out["state"] = "MEASURED"
    RESULTS["probe-rewatch"] = out
    print("  PREVIEW_TIMELINE: %s" % json.dumps(out["preview_timeline"]), flush=True)
    print("  EXPORT+INSPECT  : %s" % json.dumps(out["export_upload_inspect"]), flush=True)
    print("  REVIEW NAMED    : %s  acted_on=%s (wall %.1fs)" % (out["review"]["named"], out["review"]["acted_on"], out["review"]["wall_s"]), flush=True)
    return out


@app.local_entrypoint()
def probe_rw(clip_url: str = "", out: str = "/tmp/bs/probe_rewatch.json"):
    from require_detach import require_detach
    require_detach("the rewatch-instrument probe")
    r = probe_rewatch.remote(clip_url)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(r, open(out, "w", encoding="utf-8"), indent=1)
    print("WROTE %s" % out); print("  preview:", r.get("preview_timeline")); print("  export+inspect:", r.get("export_upload_inspect")); print("  named:", (r.get("review") or {}).get("named"))

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


@app.function(image=IMG, timeout=600, cpu=2, memory=4096, secrets=[modal.Secret.from_name("chatcut-oauth")])
def probe_sheets(pid: str, asset_prefix: str, end_frames: int = 610, dur_s: float = 20.35, serial_a: bool = True):
    """THE SHEETS THEMSELVES, for a timeline that already exists.

    The rewatch probe timed both instruments and kept only counts — 40 frames,
    2 sheets each — and a count cannot say whether a frame shows the composite
    (Zac's ruling 5 asks exactly that). This re-reads the same scratch
    timeline with both instruments and carries the PNGs out as base64, plus
    one raw edit_item envelope so the plant reader's failure can be read from
    what ChatCut actually sent rather than from a 200-character excerpt.
    No model call. Cost: the container only.
    """
    import base64
    tok = _access_token()
    out = {"state": "RUNNING", "projectId": pid}
    sys.path.insert(0, "/root")
    import chatcut_reference as _cr
    os.makedirs("/work", exist_ok=True)
    # instrument A: preview_timeline viewer, 9 per call
    tA = time.time(); a_urls = []; a_calls = 0
    try:
        if not serial_a:
            raise RuntimeError("SKIPPED by request (serial A measured on the previous pass)")
        for k in range(0, 40, 9):
            fr = [int(end_frames * (k + i + 0.5) / 40) for i in range(9) if k + i < 40]
            r = _mcp_call(tok, "preview_timeline", {"projectId": pid, "views": ["viewer"], "viewerFrames": fr}, expect=None)
            a_calls += 1
            a_urls += _frame_urls(json.dumps(r) + str(r.get("_text") or ""))
        got, fst = _cr.fetch(a_urls, "/work/ps_a", cap=45)
        sheetsA = tile_sheets([("f%d" % i, pth) for i, (_u, pth) in enumerate(got)], "/work/ps_a/sheets", per_sheet=20, cols=5, cell_w=180)
        out["A"] = {"wall_s": round(time.time() - tA, 1), "calls": a_calls, "frames": len(got), "fetch": fst,
                    "sheets_b64": [base64.b64encode(open(x, "rb").read()).decode() for x in sheetsA]}
    except Exception as e:                                        # noqa: BLE001
        out["A"] = {"wall_s": round(time.time() - tA, 1), "FAILED": "%s: %s" % (type(e).__name__, str(e)[:300])}
    # instrument A again, the five calls IN PARALLEL (harness-side; ruling 4 bounds the agent's calls, not these)
    tP = time.time()
    try:
        from concurrent.futures import ThreadPoolExecutor
        def _one(k):
            fr = [int(end_frames * (k + i + 0.5) / 40) for i in range(9) if k + i < 40]
            r = _mcp_call(tok, "preview_timeline", {"projectId": pid, "views": ["viewer"], "viewerFrames": fr}, expect=None)
            return _frame_urls(json.dumps(r) + str(r.get("_text") or ""))
        with ThreadPoolExecutor(max_workers=5) as ex:
            p_urls = sum(list(ex.map(_one, range(0, 40, 9))), [])
        t_calls = round(time.time() - tP, 1)
        gotp, fstp = _cr.fetch(p_urls, "/work/ps_p", cap=45)
        out["A_parallel"] = {"wall_s": round(time.time() - tP, 1), "calls_wall_s": t_calls, "frames": len(gotp), "fetch": fstp}
    except Exception as e:                                        # noqa: BLE001
        out["A_parallel"] = {"wall_s": round(time.time() - tP, 1), "FAILED": "%s: %s" % (type(e).__name__, str(e)[:300])}
    # instrument B: inspect_asset on the imported edit asset (watch_asset)
    tB = time.time()
    try:
        ba = _mcp_call(tok, "browse_assets", {"projectId": pid}, expect=None)
        blob = json.dumps(ba) + str(ba.get("_text") or "")
        # browse_assets ids are the 10-hex echo shape ("e2c6e741da"), not the
        # hyphenated read-back UUID — the first pass demanded 20+ chars and
        # found nothing in a library that held it. Match the id FIELD, either shape.
        m = re.search(r'"id"\s*:\s*"(' + re.escape(asset_prefix) + r'[0-9a-f-]*)"', blob)
        if not m:
            out["B"] = {"wall_s": round(time.time() - tB, 1), "FAILED": "no asset starting %s in browse_assets; first 600: %s" % (asset_prefix, blob[:600])}
        else:
            w = watch_asset(tok, m.group(1), dur_s, "/work/ps_b")
            out["B"] = {"wall_s": round(time.time() - tB, 1), "asset": m.group(1), "state": w["state"], "why": w["why"],
                        "frames": w["frames"], "sheets_b64": [base64.b64encode(open(x, "rb").read()).decode() for x in w["sheets"]]}
    except Exception as e:                                        # noqa: BLE001
        out["B"] = {"wall_s": round(time.time() - tB, 1), "FAILED": "%s: %s" % (type(e).__name__, str(e)[:300])}
    # the raw envelope of a track-creating add, then the item is removed again
    try:
        ba2 = _mcp_call(tok, "browse_assets", {"projectId": pid}, expect=None)
        blob2 = json.dumps(ba2) + str(ba2.get("_text") or "")
        pq = re.search(r'"id"\s*:\s*"([0-9a-f-]{8,36})",\s*"name"\s*:\s*"PullQuote"', blob2)
        if pq:
            raw = mcp_rpc(tok, "tools/call", {"name": "edit_item", "arguments": {"projectId": pid, "adds": [
                {"type": "motion-graphic", "assetId": pq.group(1), "fromFrame": 560, "durationInFrames": 30}]}}, 901)
            out["raw_add_envelope"] = json.dumps(raw)[:6000]
            ids = re.findall(r'"id"\s*:\s*"([0-9a-f]{8,}[0-9a-f-]*)"', json.dumps(raw))
            out["raw_add_ids"] = ids[:5]
            if ids:
                d = mcp_rpc(tok, "tools/call", {"name": "edit_item", "arguments": {"projectId": pid, "deletes": [{"id": ids[0]}]}}, 902)
                out["raw_delete_ok"] = not d.get("error")
        else:
            out["raw_add_envelope"] = "ABSENT: no PullQuote asset id found in browse_assets; first 600: %s" % blob2[:600]
    except Exception as e:                                        # noqa: BLE001
        out["raw_add_envelope"] = "FAILED %s: %s" % (type(e).__name__, str(e)[:300])
    out["state"] = "MEASURED"
    RESULTS["probe-sheets"] = out
    print("  A: %s" % json.dumps({k: v for k, v in out["A"].items() if k != "sheets_b64"}), flush=True)
    print("  A_parallel: %s" % json.dumps(out.get("A_parallel")), flush=True)
    print("  B: %s" % json.dumps({k: v for k, v in out["B"].items() if k != "sheets_b64"}), flush=True)
    print("  RAW ADD: %s" % str(out.get("raw_add_envelope"))[:400], flush=True)
    return {k: v for k, v in out.items() if k not in ("A", "B")} | {"A_sheets": len(out["A"].get("sheets_b64", [])), "B_sheets": len(out["B"].get("sheets_b64", []))}


@app.local_entrypoint()
def probe_sh(pid: str, asset_prefix: str, out: str = "/tmp/bs/probe_sheets.json", serial_a: bool = True):
    """Fetch the sheets of both rewatch instruments for an existing scratch timeline."""
    import base64
    from require_detach import require_detach
    require_detach("the sheet probe")
    r = probe_sheets.remote(pid, asset_prefix, serial_a=serial_a)
    full = RESULTS["probe-sheets"]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    for inst in ("A", "B"):
        for i, b in enumerate((full.get(inst) or {}).get("sheets_b64") or []):
            pth = out.replace(".json", "_%s%d.png" % (inst, i))
            open(pth, "wb").write(base64.b64decode(b)); print("  SHEET %s" % pth)
    slim = {k: ({kk: vv for kk, vv in v.items() if kk != "sheets_b64"} if isinstance(v, dict) else v) for k, v in full.items()}
    json.dump(slim, open(out, "w"), indent=1); print("WROTE %s" % out); print(json.dumps(r)[:600])

@app.function(image=IMG, timeout=300, cpu=2, memory=2048, secrets=[modal.Secret.from_name("anthropic-api-key")])
def egress_probe():
    """WHY THE PROXY'S UPSTREAM LEG NEVER RETURNS IN THE CONTAINER. No model.

    The proxied ping (2026-09-17) got no byte in 120s and wrote no trace row,
    so the handler thread was stuck inside connect/request. This reads the
    container's own facts: the address families api.anthropic.com resolves
    to, whether each connects within 8s, and whether a one-token call relays
    through the proxy with the default connection class and with the
    IPv4-only one, each bounded at 40s.
    """
    import socket, threading, urllib.request as _ur
    sys.path.insert(0, "/root")
    import api_proxy as _px
    out = {"state": "RUNNING"}
    try:
        infos = socket.getaddrinfo("api.anthropic.com", 443, 0, socket.SOCK_STREAM)
        out["families"] = [("v6" if af == socket.AF_INET6 else "v4", sa[0]) for af, _st, _pr, _cn, sa in infos]
    except Exception as e:                                        # noqa: BLE001
        out["families"] = "FAILED %s" % str(e)[:120]; infos = []
    conn = []
    for af, st, pr, _cn, sa in infos[:6]:
        t0 = time.time()
        try:
            sk = socket.socket(af, st, pr); sk.settimeout(8); sk.connect(sa); sk.close()
            conn.append({"addr": sa[0], "ok": True, "s": round(time.time() - t0, 2)})
        except Exception as e:                                    # noqa: BLE001
            conn.append({"addr": sa[0], "ok": False, "s": round(time.time() - t0, 2), "err": "%s: %s" % (type(e).__name__, str(e)[:60])})
    out["connects"] = conn
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    body = json.dumps({"model": "claude-haiku-4-5-20251001", "max_tokens": 5, "messages": [{"role": "user", "content": "Say ok."}]}).encode()

    def _via(cls, tag):
        _px.CONNECTION = cls
        _px.TRACE = "/work/egress_%s.jsonl" % tag
        os.makedirs("/work", exist_ok=True)
        port = _px.serve(0)
        res = {"tag": tag}
        def _go():
            t0 = time.time()
            try:
                req = _ur.Request("http://127.0.0.1:%d/v1/messages" % port, data=body, method="POST",
                                  headers={"content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
                with _ur.urlopen(req, timeout=40) as r:
                    res["status"] = r.status; res["bytes"] = len(r.read()); res["s"] = round(time.time() - t0, 2)
            except Exception as e:                                # noqa: BLE001
                res["error"] = "%s: %s" % (type(e).__name__, str(e)[:120]); res["s"] = round(time.time() - t0, 2)
        th = threading.Thread(target=_go, daemon=True); th.start(); th.join(45)
        if th.is_alive():
            res["error"] = "HUNG past 45s"
        try:
            res["trace"] = [json.loads(l) for l in open(_px.TRACE, encoding="utf-8") if l.strip()]
        except Exception as e:                                    # noqa: BLE001
            res["trace"] = "ABSENT %s" % type(e).__name__
        return res
    out["default_class"] = _via(__import__("http.client").client.HTTPSConnection, "default")
    out["v4_class"] = _via(_px.V4HTTPSConnection, "v4")
    out["state"] = "MEASURED"
    RESULTS["egress-probe"] = out
    print("  EGRESS          : %s" % json.dumps(out)[:2500], flush=True)
    return out


@app.local_entrypoint()
def egress(out: str = "/tmp/bs/egress.json"):
    from require_detach import require_detach
    require_detach("the egress probe")
    r = egress_probe.remote()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(r, open(out, "w"), indent=1); print("WROTE %s" % out)

@app.local_entrypoint()
def roundtrip(clip_url: str = "", out: str = "/tmp/bs/roundtrip.json"):
    from require_detach import require_detach
    require_detach("an audio round-trip probe")
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


def region_states(path, duration_s=0.0):
    """Face trajectory and burned-in text for ONE LOCAL FILE, three-state.

    HOISTED OUT OF `detect_regions` DELIBERATELY. The merged single-agent path
    needs exactly this answer and already has the clip at /work/source.mp4 in
    the SAME image that carries the models — so calling the @app.function would
    spawn a second container to re-download a file we are sitting on. A rule
    that lives inside a dispatch cannot be driven by a check, and a second copy
    of it is how the two drift; there is one implementation and both callers
    use it.

    FAILED IS NOT ABSENT IS NOT MEASURED. A detector that could not load says
    so rather than returning an empty trajectory, because "no faces found" and
    "we did not look" must never be the same value.
    """
    # BOUNDED. Every other subprocess in this file carries a timeout; this one
    # did not, and an ffprobe that never returns would hang the rewatch thread
    # with no watchdog under it.
    _d = duration_s or float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=120).stdout.strip() or 0.0)
    out = {"duration_s": _d, "face_state": "ABSENT", "text_state": "ABSENT",
           "face_traj": None, "source_text_regions": None}
    try:
        import face_bands as fb
        ts = [round(i * 0.25, 2) for i in range(int(max(1.0, _d) / 0.25) + 1)]
        traj = fb.detect_face_positions(path, ts)
        if traj is None:
            out["face_state"] = "FAILED"
            out["face_why"] = "cv2 or the res10 model is missing"
        else:
            out["face_traj"] = traj
            out["face_state"] = "MEASURED"
            out["faces_found"] = sum(1 for p in traj if p.get("found"))
            out["face_sampled"] = len(traj)
    except Exception as e:                                        # noqa: BLE001
        out["face_state"] = "FAILED"
        out["face_why"] = "%s: %s" % (type(e).__name__, str(e)[:160])
    try:
        import burned_text as bt
        b = bt.detect_burned_in_text(path)
        if b is None:
            out["text_state"] = "FAILED"
            out["text_why"] = "the EAST model is missing or unreadable"
        else:
            out["source_text_regions"] = list(b.get("source_text_regions") or ())
            out["text_state"] = "MEASURED"
            out["has_burned_captions"] = bool(b.get("has_burned_captions"))
    except Exception as e:                                        # noqa: BLE001
        out["text_state"] = "FAILED"
        out["text_why"] = "%s: %s" % (type(e).__name__, str(e)[:160])
    print("  DETECT          : face=%s (%s/%s found)  text=%s %s"
          % (out["face_state"], out.get("faces_found"), out.get("face_sampled"),
             out["text_state"], out.get("source_text_regions")), flush=True)
    return out


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
    return region_states("/work/src.mp4", duration_s)



# ONE READ-BACK, FOUR WRITE SHAPES. Settles whether an untrimmed video item
# carries sourceRange — and WHICH write field makes it so — the same way
# cutaway and transition were verified: by doing it.
@app.function(image=IMG, timeout=1200,
              secrets=[modal.Secret.from_name("chatcut-oauth")])
def probe_sourcerange(clip_url: str):
    """Which video-add shape comes back with sourceRange? -> per-variant, verbatim.

    THE QUESTION, and why one shape could not answer it. `kept_spans` hard-fails
    when a base-track video item lacks sourceRange.startSeconds/endSeconds; that
    one failure is upstream of every ABSENT in runs 7, 8 and 9. Two opposite
    fixes look identical from the records — the agent omits a field, or the gate
    demands one ChatCut never sets — and the read-back items never reached any
    record.

    THE FIRST VERSION OF THIS PROBE WOULD HAVE ANSWERED ON THE WRONG SIDE. It
    sent one shape and its verdict could only say "gate right" or "gate wrong".
    The refutation pass found, on disk, that the OLD planner-path agent always
    wrote `sourceStartFromInSeconds: 0` and `from` (not `fromFrame`), and that
    ChatCut's own echo uses `from` — so the live hypothesis is a WRITE-FIELD
    dependency: sourceRange exists only when sourceStartFromInSeconds is written.
    A one-shape probe cannot see that, and `fromFrame: 0` masks an ignored key
    because an ignored key and an honoured one both land at frame 0.

    SO: four adds, SEPARATE calls (the batch is atomic — one rejection would
    hide the other three), spaced in time so they cannot overlap on one track,
    NONZERO offsets on B/C/D so the position key is proven honoured, and the
    verdict comes from REPLAYING THE GATE (base_track + kept_spans) rather than
    re-implementing it with a weaker predicate. Each read-back item is tied to
    its add through the id in ChatCut's echo, never by "any video item".

      A  {type, assetId, trackId, fromFrame:0,    durationInFrames:612}
         — the new paragraph's shape, VERBATIM. 612 > 20.362s x 30 = 610.86,
           so it is OVER-LENGTH and labelled so; a clamp is a trim.
      B  A at fromFrame:700, durationInFrames:610, + sourceStartFromInSeconds:0
      C  {type, assetId, trackId, from:1400, durationInFrames:610}
         — the OLD agent's position key
      D  A at fromFrame:2100, durationInFrames:610 — honest length, honest key

    ABSENT IS NAMED PER VARIANT. A refusal, a missing echo id, or an item that
    did not come back each says so on its own line; no `all()` over a mixed list.
    """
    _t0 = time.time()
    RESULTS["probe-sourcerange"] = {"state": "STARTED", "t0": _t0}
    os.makedirs("/work", exist_ok=True)
    subprocess.run(["curl", "-fsSL", "-o", "/work/source.mp4", clip_url],
                   check=True, timeout=300)
    _pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration", "-of", "csv=p=0",
                          "/work/source.mp4"], capture_output=True, text=True,
                         timeout=60)
    _dur = float((_pr.stdout or "0").strip() or 0)
    _src_frames = int(_dur * 30)                  # prestage creates fps=30
    tok = _access_token()
    stage = prestage(tok, "", controls={}, source_path="/work/source.mp4",
                     want_components={"__no_components__"}, titles=[])
    if not (stage.get("trackId") and stage.get("sourceAssetId")):
        raise RuntimeError("prestage returned no trackId/sourceAssetId — the "
                           "add would be sent against None: %s"
                           % json.dumps({k: stage.get(k) for k in
                                         ("projectId", "trackId",
                                          "sourceAssetId")}))
    out = {"state": "RUNNING", "projectId": stage["projectId"],
           "trackId": stage["trackId"], "sourceAssetId": stage["sourceAssetId"],
           "source_duration_s": _dur, "source_frames_at_30": _src_frames,
           "prestage_wall_s": round(time.time() - _t0, 1), "variants": {}}
    base = {"type": "video", "assetId": stage["sourceAssetId"],
            "trackId": stage["trackId"]}
    V = {
        "A_paragraph_verbatim_612": dict(base, fromFrame=0,
                                         durationInFrames=612),
        "B_sourceStartFromInSeconds": dict(base, fromFrame=700,
                                           durationInFrames=610,
                                           sourceStartFromInSeconds=0),
        "C_old_agent_from_key": dict(base, **{"from": 1400,
                                              "durationInFrames": 610}),
        "D_honest_length_offset": dict(base, fromFrame=2100,
                                       durationInFrames=610),
    }
    _sent_pos = {"A_paragraph_verbatim_612": 0, "B_sourceStartFromInSeconds": 700,
                 "C_old_agent_from_key": 1400, "D_honest_length_offset": 2100}
    for name, add in V.items():
        rec = {"add_sent": add, "over_length": add["durationInFrames"] > _src_frames}
        try:
            r = _mcp_call(tok, "edit_item",
                          {"projectId": stage["projectId"], "adds": [add]},
                          expect="adds")
            _echo = r.get("adds") or []
            _eid = None
            for e in _echo:
                if isinstance(e, dict) and e.get("id"):
                    _eid = str(e["id"])
                    break
            rec["echo"] = (json.dumps(r) + str(r.get("_text") or ""))[:700]
            rec["echo_id"] = _eid
            rec["edit_item_state"] = "MEASURED" if _eid else (
                "MEASURED-NO-ID — the echo carried no item id, so this add "
                "cannot be tied to a read-back item")
        except Exception as e:                                    # noqa: BLE001
            rec["edit_item_state"] = "FAILED"
            rec["echo"] = "%s: %s" % (type(e).__name__, str(e)[:500])
            rec["echo_id"] = None
        out["variants"][name] = rec
        print("  ADD %-28s %s" % (name, rec["edit_item_state"][:60]), flush=True)
    # ONE READ-BACK, THEN THE GATE REPLAYED VERBATIM
    rb = read_back(tok, stage)
    items = rb.get("items")
    out["read_why"] = rb.get("read_why")
    out["read_state"] = ("FAILED" if items is None else
                         "EMPTY" if not items else "MEASURED")
    items = items or []
    out["items_verbatim"] = items[:6]
    # THE KEYS THE READ-BACK ACTUALLY CARRIES, recorded before any matching —
    # the gate ties items by `id` (chatcut_gate.py:356) and so does this
    # probe; if the read-back spells it differently every variant reads
    # UNDECIDED and this line is what says why.
    out["readback_item_keys"] = sorted(items[0].keys()) if items else None
    sys.path.insert(0, "/root")
    import chatcut_gate as _cg
    _bt, _bst, _bwhy = _cg.base_track(items)
    _sp, _sst, _swhy = _cg.kept_spans(items, _bt, float(rb.get("fps") or 30))
    out["gate_replay"] = {"base_track": _bt, "base_state": _bst, "base_why": _bwhy,
                          "spans": _sp, "spans_state": _sst, "spans_why": _swhy}
    by_id = {str(i.get("id")).replace("-", ""): i for i in items if i.get("id")}
    for name, rec in out["variants"].items():
        it = by_id.get(str(rec.get("echo_id") or "").replace("-", ""))
        if rec["edit_item_state"] != "MEASURED":
            rec["verdict"] = "ABSENT — the add did not succeed (%s)" % rec["edit_item_state"][:40]
            continue
        if it is None:
            # maybe the id is a prefix of the read-back id
            _cands = [i for k, i in by_id.items() if k.startswith(rec["echo_id"])
                      or rec["echo_id"].startswith(k)]
            it = _cands[0] if len(_cands) == 1 else None
        if it is None:
            rec["verdict"] = ("UNDECIDED — echo id %s matched no read-back item "
                              "(read: %s)" % (rec["echo_id"], out["read_why"]))
            continue
        rec["readback_keys"] = sorted(it.keys())
        rec["sourceRange"] = it.get("sourceRange")
        rec["timelineRange"] = it.get("timelineRange")
        _tr = it.get("timelineRange") or {}
        _obs = _tr.get("fromFrame")
        rec["position_honoured"] = (
            "MEASURED yes" if _obs == _sent_pos[name] else
            "MEASURED NO — sent %s, landed at %r (the key was ignored or "
            "remapped)" % (_sent_pos[name], _obs))
        _sr = it.get("sourceRange")
        rec["verdict"] = (
            "sourceRange PRESENT (%r)" % _sr if isinstance(_sr, dict)
            and "start" in _sr and "end" in _sr else
            "sourceRange ABSENT (keys: %s)" % rec["readback_keys"])
    out["gate_verdict"] = (
        "GATE IS RIGHT — kept_spans MEASURED over the probe's items: %s" % _swhy
        if _sst == "MEASURED" else
        "GATE FAILS ON THESE ITEMS — %s; see per-variant lines for which "
        "shape(s) carry sourceRange" % _swhy)
    out["wall_s"] = round(time.time() - _t0, 1)
    out["state"] = "MEASURED"
    print("  GATE REPLAY     : %s" % out["gate_verdict"], flush=True)
    for name, rec in out["variants"].items():
        print("  %-28s %s | pos %s" % (name, rec.get("verdict", "?")[:70],
                                        rec.get("position_honoured", "-")[:40]),
              flush=True)
    RESULTS["probe-sourcerange"] = out
    return out


@app.local_entrypoint()
def probe_sr(clip_url: str = "", out: str = "/tmp/bs/probe_sourcerange.json"):
    from require_detach import require_detach
    require_detach("the sourceRange probe")
    r = probe_sourcerange.remote(clip_url)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(r, fh, indent=1)
    print("WROTE %s" % out)
    print("  gate:", r.get("gate_verdict"))
    for n, v in (r.get("variants") or {}).items():
        print("  %-28s %s" % (n, v.get("verdict")))

@app.local_entrypoint()
def detect(clip_url: str = "", out: str = "/tmp/bs/regions.json"):
    from require_detach import require_detach
    require_detach("a region-detection probe")
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


# THE `sweep` ENTRYPOINT IS GONE (2026-09-15). It called `wiring_sweep.remote`,
# and `wiring_sweep` was deleted in 48c5c33 — so `modal run
# chatcut_job_app.py::sweep` has raised NameError ever since, and the only
# reason it was not noticed is that nothing has needed it. Second dangling
# reference in this file found by the same scoped check in the same minute as
# SHEET_RULE; the entrypoint is removed rather than repaired because the
# function it drove no longer exists and the question it answered — do the
# components draw — is now `bake_probe` and `component_render_check`.


@app.local_entrypoint()
def main(clip_url: str = "", brief: str = "Cut this tighter and add one title.",
         run_id: str = "", wait: bool = False,
         read_ceiling: int = 0,
         model: str = "claude-sonnet-5", use_hands: bool = False,
         think_tokens: int = -1, effort: str = "", prefix_ttl: str = "1h",
         prestage_title: str = "", prestage_controls: str = "",
         prestage_titles: str = "", transcript_file: str = ""):
    if not clip_url:
        raise SystemExit("pass --clip-url")
    # THE PLAN IS READ HERE, ON THE MACHINE THAT OWNS IT, and passed as a
    # value. Mounting it would make the container's copy a second artifact that
    # can drift from the ledger it came from; a string argument cannot.
    plan_text = ""
    plan_text = None            # the plan route is gone (one session; Zac, 2026-09-17)
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
                                     think_tokens=think_tokens, effort=effort, prefix_ttl=prefix_ttl,
                                     prestage_title=prestage_title,
                      prestage_controls=prestage_controls,
                      prestage_titles=prestage_titles,
                      transcript=_tx, read_ceiling=read_ceiling),
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
                      think_tokens=think_tokens, effort=effort, prefix_ttl=prefix_ttl,
                      prestage_title=prestage_title,
                      prestage_controls=prestage_controls,
                      prestage_titles=prestage_titles,
                      transcript=_tx, read_ceiling=read_ceiling)
    print(f"SPAWNED run_id={rid} call={call.object_id}")
    print(f"read it with:  modal run chatcut_read_result.py --run-id {rid}")
