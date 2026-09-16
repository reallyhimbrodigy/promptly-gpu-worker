#!/usr/bin/env python3
"""The agent asks to look; the harness fetches. It never types a signed URL.

WHAT THIS PREVENTS, measured on run 24 rather than imagined:

    tool-call payload the agent TYPED        49,501 chars
      mcp__chatcut__edit_item                 1,380   2.8%   <- the EDIT
      Bash                                   47,379  95.7%
        of which signed S3 frame URLs        44,098  89.1%
    at 6.23s of tool_use generation per 1k chars
      => ~275s typing URLs + 156s running curl = ~430 of 908 seconds

The cause was an instruction: FETCH_RULE told the agent to download every frame
URL, tile them with ffmpeg and Read the sheet. Correct when written — `Read`
does not open URLs, and one Read per frame had cost twelve turns — and the most
expensive sentence in the prompt by the time anyone measured it.

THE LEGS ARE WRITTEN AGAINST THE PROPERTY, not against either decision:

  1. a `preview_timeline` RESULT is turned into pixels and sent back
  2. the prompt does not instruct the agent to fetch, tile or Read a frame
  3. the prompt does not bound how OFTEN it may look — that was reversed once
     already and the cheap fix for a slow review is to re-impose it
  4. the render never runs on the event loop: blocking the callback stops
     stdout being read, the pipe fills at 64K and the AGENT blocks
  5. stdin is closed on every path out of that thread, or the run hangs to its
     timeout looking like a slow model
  6. a fetch that fails returns a STATE, never a silent empty list

RED-proven at the bottom on mutated source.
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "chatcut_job_app.py")
SRC = open(APP, encoding="utf-8").read()
TREE = ast.parse(SRC)
fail = []


def bad(msg):
    fail.append(msg)


def fn(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and n.name == name:
            return n
    return None


def legs(src=None, tree=None):
    src = src if src is not None else SRC
    tree = tree if tree is not None else ast.parse(src)
    out = []

    # ── 1. THE RESULT BECOMES PIXELS ────────────────────────────────────────
    _srv = fn(tree, "_serve_what_it_asked_to_see")
    if _srv is None:
        out.append(("serves", "there is no frame server"))
    else:
        body = ast.unparse(_srv)
        if "tool_result" not in body:
            out.append(("serves", "the server never looks at a tool_result"))
        if "preview_timeline" not in body:
            out.append(("serves", "the server is not keyed to preview_timeline"))
        if "_fetch_frames" not in body:
            out.append(("serves", "the server never fetches anything"))
        # REACHABLE, AND CARRYING THE FRAMES. `send(` appearing in the source
        # is satisfied by `if False: send(...)` — the presence-check hole this
        # repo has been caught by more than any other. So: the name bound from
        # _fetch_frames must reach a send() call, and no branch in the server
        # may be gated on a constant.
        _bound = set()
        for _n in ast.walk(_srv):
            if isinstance(_n, ast.Assign) and "_fetch_frames" in \
                    ast.unparse(_n.value):
                for _t in _n.targets:
                    if isinstance(_t, ast.Tuple):
                        _bound |= {e.id for e in _t.elts
                                   if isinstance(e, ast.Name)}
                    elif isinstance(_t, ast.Name):
                        _bound.add(_t.id)
        _sent = False
        for _n in ast.walk(_srv):
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) \
                    and _n.func.id == "send":
                _names = {x.id for x in ast.walk(_n) if isinstance(x, ast.Name)}
                if _names & _bound:
                    _sent = True
        if not _bound:
            out.append(("serves", "nothing in the server is bound from "
                                  "_fetch_frames"))
        elif not _sent:
            out.append(("serves", "the fetched frames never reach a send()"))
        for _n in ast.walk(_srv):
            if isinstance(_n, ast.If) and isinstance(_n.test, ast.Constant):
                out.append(("serves", "a branch of the server is gated on the "
                                      "constant %r — dead code that still "
                                      "contains the call it replaced"
                                      % _n.test.value))
    # and the DRIVER calls it — a server nobody invokes is the read_knowledge
    # failure one layer down.
    _drv = fn(tree, "_drive")
    if _drv is None:
        out.append(("serves", "there is no _drive"))
    elif "_serve_what_it_asked_to_see" not in ast.unparse(_drv):
        out.append(("serves", "_drive never calls the frame server"))

    # ── 2 & 3. WHAT THE PROMPT SAYS ─────────────────────────────────────────
    _fr = ""
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(
                getattr(t, "id", "") == "FETCH_RULE" for t in n.targets):
            try:
                _fr = ast.literal_eval(n.value)
            except Exception:                                     # noqa: BLE001
                _fr = ast.unparse(n.value)
    if not _fr:
        out.append(("prompt", "FETCH_RULE is gone — the agent is told nothing "
                              "about how frames reach it, and an agent told "
                              "nothing will curl"))
    else:
        low = _fr.lower()
        for _verb in ("curl ", "wget ", "ffmpeg -", "download them"):
            # an INSTRUCTION to fetch, not a prohibition. The prohibition
            # contains the word too, so the test is the imperative shape.
            if re.search(r"(?m)^\s*" + re.escape(_verb), low) or \
                    (_verb + "all") in low:
                out.append(("prompt", "FETCH_RULE still instructs %r" % _verb))
        if "sent to you" not in low and "arrive in your next message" not in low:
            out.append(("prompt", "FETCH_RULE never says the frames are SENT"))
        # the looking must stay unbounded
        for _bound in ("only once", "do not preview", "at most one",
                       "your turn ends"):
            if _bound in low:
                out.append(("unbounded", "FETCH_RULE bounds the looking (%r) — "
                                         "reversed 2026-09-14, and the cheap "
                                         "fix for a slow review is to put it "
                                         "back" % _bound))

    # ── 4. THE RENDER IS OFF THE EVENT LOOP ─────────────────────────────────
    if _drv is not None:
        _dsrc = ast.unparse(_drv)
        # _edit_frames must be called from a thread target, not from _drive's
        # own body. Checked structurally: the call sits inside a nested def.
        _direct = False
        for n in _drv.body:
            for sub in ast.walk(n):
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    break
            else:
                if "_edit_frames" in ast.unparse(n):
                    _direct = True
        if _direct:
            out.append(("offloop", "_edit_frames is called straight from "
                                   "_drive — a 240s render poll inside the "
                                   "callback stops stdout being read and the "
                                   "agent blocks on a full pipe"))
        if "Thread(" not in _dsrc:
            out.append(("offloop", "_drive starts no thread for the render"))

    # ── 5. STDIN IS CLOSED ON EVERY PATH ────────────────────────────────────
    _rs = fn(tree, "_render_and_send")
    if _rs is None:
        out.append(("close", "there is no _render_and_send"))
    else:
        _tries = [n for n in ast.walk(_rs) if isinstance(n, ast.Try)]
        if not _tries or not any(t.finalbody for t in _tries):
            out.append(("close", "_render_and_send has no finally — a thread "
                                 "that raises leaves stdin open and the run "
                                 "burns to its timeout"))
        elif not any("close" in ast.unparse(ast.Module(t.finalbody, []))
                     for t in _tries if t.finalbody):
            out.append(("close", "the finally does not close stdin"))

    # ── 6. A FAILED FETCH RETURNS A STATE ───────────────────────────────────
    _ff = fn(tree, "_fetch_frames")
    if _ff is None:
        out.append(("state", "there is no _fetch_frames"))
    else:
        for r in [n for n in ast.walk(_ff) if isinstance(n, ast.Return)]:
            v = ast.unparse(r.value or ast.Constant(None))
            if "[]" in v and ("SERVED 0" not in v and "state" not in v.lower()):
                out.append(("state", "an empty return with no state: %s" % v))
    return out


bad_now = legs()
for k, m in bad_now:
    bad("[%s] %s" % (k, m))

# ── BEHAVIOUR, on the real function ─────────────────────────────────────────
sys.path.insert(0, HERE)
import modal_stub                                                # noqa: E402
modal_stub.install()
_ns = {"re": re, "os": os}
for n in TREE.body:
    if isinstance(n, ast.Assign) and any(
            getattr(t, "id", "").startswith("_FRAME_URL") or
            getattr(t, "id", "") == "_SERVE_CAP" for t in n.targets):
        exec(compile(ast.Module([n], []), "<c>", "exec"), _ns)
    if isinstance(n, ast.FunctionDef) and n.name in ("_frame_urls",):
        exec(compile(ast.Module([n], []), "<c>", "exec"), _ns)
if "_frame_urls" not in _ns:
    bad("[behaviour] _frame_urls is not module-level and drivable")
else:
    _f = _ns["_frame_urls"]
    _signed = ('https://rendererbucket-48236b1.s3.us-west-2.amazonaws.com/'
               'p/frame_55.jpg?X-Amz-Algorithm=AWS4-HMAC&X-Amz-Signature=abc')
    got = _f('viewer: "%s" and "%s" and %s'
             % (_signed, _signed, _signed.replace("55.jpg", "90.png")))
    if len(got) != 2:
        bad("[behaviour] deduped to %d, expected 2: %s" % (len(got), got))
    elif got[0] != _signed:
        bad("[behaviour] the query string was truncated: %r" % got[0])
    if _f("no urls here at all"):
        bad("[behaviour] found a URL in text with none")
    if _f('see https://example.com/page.html for details'):
        bad("[behaviour] matched a non-image URL")

# ── RED PROOF ───────────────────────────────────────────────────────────────
red = 0
MUT = (
    ("the driver stops calling the server", "serves",
     lambda s: s.replace("        _serve_what_it_asked_to_see(ev, send)\n",
                         "        pass\n")),
    ("the server fetches and never sends", "serves",
     lambda s: s.replace('        if _blocks:\n            send(_message(',
                         '        if False:\n            send(_message(')),
    ("the prompt tells it to curl again", "prompt",
     lambda s: s.replace('    "YOU DO NOT DOWNLOAD FRAMES.',
                         '    "curl -fsSL every frame url.\\n"\n'
                         '    "YOU DO NOT DOWNLOAD FRAMES.')),
    ("the looking is bounded again", "unbounded",
     lambda s: s.replace('"frames you want, as often as you want,',
                         '"frames you want, only once, ')),
    ("the render goes back on the event loop", "offloop",
     lambda s: s.replace("        def _render_and_send():",
                         "        _edit_frames(tok, _stage['projectId'],\n"
                         "                     _total_frames)\n\n"
                         "        def _render_and_send():")),
    ("the finally that closes stdin is removed", "close",
     lambda s: s.replace("            finally:\n                close()\n",
                         "            finally:\n                pass\n")),
)
for label, kind, mut in MUT:
    m = mut(SRC)
    if m == SRC:
        print("  *** MUTATION DID NOT APPLY: %s (anchor 0x)" % label)
        red += 1
        continue
    try:
        r = legs(m, ast.parse(m))
    except SyntaxError as e:
        print("  *** MUTANT DOES NOT PARSE: %s (%s)" % (label, e))
        red += 1
        continue
    hit = any(k == kind for k, _ in r)
    print("    %-44s -> %d leg(s) red, names %s: %s"
          % (label, len(r), kind, hit))
    if not hit:
        red += 1

if fail:
    print()
    for m in fail:
        print("  *** " + m)
print("\nsmoke_the_harness_serves_the_frames: %d wrong, %d mutation(s) not red "
      "(of %d)" % (len(fail), red, len(MUT)))
sys.exit(1 if (fail or red) else 0)
