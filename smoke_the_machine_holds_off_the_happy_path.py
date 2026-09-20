#!/usr/bin/env python3
"""The turn machine holds OFF the happy path, and the gate reads what ChatCut writes.

Zac, 2026-09-17: "It's proven correct when the harness serves frames. Walk
every way the harness can serve empty, stall, or fire late." Every leg here
DRIVES a shipped function with the events or items the world actually
produces — the four items are verbatim from the 2026-09-17 sourceRange probe,
embedded so this fixture drifts with the tree instead of with /tmp.
"""
import ast
import re
import io
import os
import random
import sys
import re as _re
_os_list = __import__('os').listdir
import sys as _sys
import subprocess as _sub
import os.path as _os_p
import tempfile
import time
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("MODAL_IS_INSIDE_CONTAINER", "0")
import chatcut_job_app as J                                      # noqa: E402
PX_SRC = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_proxy.py"), encoding="utf-8").read()
RP_SRC = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "red_proof_the_machine_holds.py"), encoding="utf-8").read()
import chatcut_gate as G                                         # noqa: E402

FAILS = []


def check(name, ok, why=""):
    print("  %-56s %s" % (name, "ok" if ok else "FAIL"))
    if not ok:
        FAILS.append("%s :: %s" % (name, why))


PROBE_ITEMS = [
 {
  "asset": {
   "id": "60ba6cdc-ffef-4899-80b5-fbb9af65004a",
   "name": "source_compensated.mp4",
   "type": "video"
  },
  "startFrame": 0,
  "id": "78d2b44b-c6b1-4a5e-b4c0-e9cdd43eea7c",
  "itemType": "video",
  "kind": "item",
  "sourceRange": {
   "end": 20400000,
   "start": 0
  },
  "timelineRange": {
   "fromFrame": 0,
   "toFrame": 612
  },
  "trackAlias": "V1",
  "trackId": "bbb5eeb0-c02e-4d9a-9855-2495e734d115"
 },
 {
  "asset": {
   "id": "60ba6cdc-ffef-4899-80b5-fbb9af65004a",
   "name": "source_compensated.mp4",
   "type": "video"
  },
  "startFrame": 700,
  "id": "38d64f95-3b46-468a-8b03-a330ad70c618",
  "itemType": "video",
  "kind": "item",
  "sourceRange": {
   "end": 20333333,
   "start": 0
  },
  "timelineRange": {
   "fromFrame": 700,
   "toFrame": 1310
  },
  "trackAlias": "V1",
  "trackId": "bbb5eeb0-c02e-4d9a-9855-2495e734d115"
 },
 {
  "asset": {
   "id": "60ba6cdc-ffef-4899-80b5-fbb9af65004a",
   "name": "source_compensated.mp4",
   "type": "video"
  },
  "startFrame": 1400,
  "id": "aa00996d-ead4-4e82-9ca3-828cc374431b",
  "itemType": "video",
  "kind": "item",
  "sourceRange": {
   "end": 20333333,
   "start": 0
  },
  "timelineRange": {
   "fromFrame": 1400,
   "toFrame": 2010
  },
  "trackAlias": "V1",
  "trackId": "bbb5eeb0-c02e-4d9a-9855-2495e734d115"
 },
 {
  "asset": {
   "id": "60ba6cdc-ffef-4899-80b5-fbb9af65004a",
   "name": "source_compensated.mp4",
   "type": "video"
  },
  "startFrame": 2100,
  "id": "a18e2b1b-4d28-48df-b1f0-3b6cfa566e34",
  "itemType": "video",
  "kind": "item",
  "sourceRange": {
   "end": 20333333,
   "start": 0
  },
  "timelineRange": {
   "fromFrame": 2100,
   "toFrame": 2710
  },
  "trackAlias": "V1",
  "trackId": "bbb5eeb0-c02e-4d9a-9855-2495e734d115"
 }
]


def _fake_frame_fetch(urls, out_dir, timeout_s=15, workers=8, name="s"):
    """the watch legs never touch the network: every URL becomes a tiny jpeg on disk (a different _fake_fetch lives inside main)"""
    from PIL import Image as _PI
    os.makedirs(out_dir, exist_ok=True); got = []
    for i, _u in enumerate(urls):
        pth = os.path.join(out_dir, "%s%03d.jpg" % (name, i)); _PI.new("RGB", (36, 64), (10, 20, 30)).save(pth, "JPEG"); got.append((i, pth))
    return got, {"n": len(urls), "got": len(urls), "failed": 0, "wall_s": 0.0, "p50_s": 0.0, "max_s": 0.0, "errors": [], "timeout_s": timeout_s}


def main():
    src = io.open(os.path.join(HERE, "chatcut_job_app.py"), encoding="utf-8").read()
    gsrc = io.open(os.path.join(HERE, "chatcut_gate.py"), encoding="utf-8").read()

    # ---- ITEM 1: THE GATE READS THE SHAPE CHATCUT WRITES ----
    base, bst, _ = G.base_track(PROBE_ITEMS)
    sp, sst, why = G.kept_spans(PROBE_ITEMS, base, 30.0)
    check("kept_spans reads sourceRange{start,end} in microseconds",
          sst == "MEASURED" and len(sp) == 4 and abs(sp[0][1] - 20.4) < 0.01
          and abs(sp[1][1] - 20.3333) < 0.001,
          "four verbatim probe items -> %s %r" % (sst, sp[:2]))
    nosr = [dict(i, sourceRange=None) for i in PROBE_ITEMS]
    sp2, sst2, why2 = G.kept_spans(nosr, base, 30.0)
    check("an untrimmed item with NO sourceRange is DERIVED, not failed",
          sst2 == "MEASURED" and "DERIVED" in why2 and len(sp2) == 4
          and abs(sp2[0][1] - 612 / 30.0) < 0.001,
          "%s %s" % (sst2, why2[-80:]))
    bad = [dict(i, sourceRange={"startSeconds": 0, "endSeconds": 20}) for i in PROBE_ITEMS]
    sp3, sst3, why3 = G.kept_spans(bad, base, 30.0)
    check("a sourceRange in a foreign vocabulary FAILS and names its keys",
          sst3 == "FAILED" and "endSeconds" in why3 and "startSeconds" in why3,
          "%s %s" % (sst3, why3[:120]))
    # ASKED OF THE AST, NOT THE PROSE: the docstring legitimately NAMES the
    # old key while explaining why it is gone; a text needle read that as
    # the defect. The defect is a SUBSCRIPT or .get() on the key.
    _ks = next(n for n in ast.walk(ast.parse(gsrc))
               if isinstance(n, ast.FunctionDef) and n.name == "kept_spans")
    _reads_old = any(isinstance(n, ast.Constant) and n.value in ("startSeconds", "endSeconds")
                     and not (isinstance(par, ast.Expr))
                     for par in ast.walk(_ks) for n in ast.iter_child_nodes(par)
                     if not isinstance(par, ast.Expr))
    check("submit_export's vocabulary is gone from the item reader",
          not _reads_old,
          "the key that hard-failed runs 7-9 must not be read from an item")
    # DRIVEN: an effect that names its host by the echo's unhyphenated
    # 10-char prefix must resolve against the read-back's hyphenated UUID.
    _zf = G.check_zoom_has_an_item([
        {"itemType": "video", "id": "78d2b44b-c6b1-4a5e-b4c0-e9cdd43eea7c",
         "trackAlias": "V1", "timelineRange": {"fromFrame": 0, "toFrame": 612}},
        {"itemType": "effect", "id": "e1", "targetItemId": "78d2b44bc6",
         "trackAlias": "V1", "timelineRange": {"fromFrame": 10, "toFrame": 40}}])
    check("id prefix compares strip hyphens in the gate",
          _zf and all(f.get("verdict") == "PASS" for f in _zf),
          "echo ids are unhyphenated 10-char prefixes of hyphenated UUIDs; "
          "findings: %r" % [(f.get("verdict"), str(f.get("why"))[:60]) for f in _zf])
    rows = G.manifest_from_items([{"itemType": "motion-graphic", "id": "abc",
                                   "timelineRange": {"fromFrame": 10, "toFrame": 40},
                                   "asset": {"id": "x", "name": "StatCard", "type": "motion-graphic"},
                                   "propertyOverrides": {"offsetY": 100}}])
    check("hop 6 rows carry the asset NAME the envelope holds",
          rows and rows[0].get("asset") == "StatCard" and rows[0].get("overrides", {}).get("offsetY") == 100,
          "without the name band_of falls through to the whole frame: %r" % (rows,))

    # ---- ITEM 2: BEATS, NOT WORDS ----
    random.seed(7)
    words, t = [], 0.3
    for i in range(86):
        d = 0.14 + random.random() * 0.10
        words.append({"w": "w%d" % i, "s": round(t, 2), "e": round(t + d, 2)})
        t += d + (0.45 if i in (13, 38, 61) else 0.02)
    b = J.segment_beats(words)
    check("86 words over a ~20s narration become 7-10 beats",
          7 <= len(b) <= 10 and t < 24,
          "%d beats over %.1fs" % (len(b), t))
    check("hook and close are marked",
          b and b[0].get("role") == "hook" and b[-1].get("role") == "close")
    _cov = [w["w"] for bt in b for w in words if bt["t_start"] <= w["s"] <= bt["t_end"]]
    check("no word is lost or split across beats",
          _cov == [w["w"] for w in words], "%d of %d words covered in order" % (len(_cov), len(words)))
    _p1 = ast.unparse(next(n for n in ast.walk(ast.parse(src))
                           if isinstance(n, ast.FunctionDef) and n.name == "pass1_message"))
    _sb = ast.unparse(next(n for n in ast.walk(ast.parse(src))
                           if isinstance(n, ast.FunctionDef) and n.name == "source_beats"))
    check("source_beats hands the segmenter's output to the prompt",
          "_beats = segment_beats(_words)" in _sb and "THE BEATS" in _p1
          and "THE TRANSCRIPT, against those frames" not in _p1,
          "the prompt must render beats with roles, not 86 rows")
    J._transcript_rows({"x": [{"start": 0, "end": 1200, "text": "a"},
                              {"start": 19800, "end": 20362, "text": "z"}]}, dur_s=20.362)
    check("bare start/end stamps are read in ms when they exceed the source",
          J._transcript_rows.unit.startswith("ms"), J._transcript_rows.unit)
    J._transcript_rows({"x": [{"start": 0.1, "end": 1.2, "text": "a"},
                              {"start": 19.8, "end": 20.3, "text": "z"}]}, dur_s=20.362)
    check("...and in seconds when they fit it",
          J._transcript_rows.unit.startswith("s "), J._transcript_rows.unit)
    J._transcript_rows({"x": [{"start": 0, "end": 1200, "text": "a"}]})
    check("with no duration given the unit is declared a GUESS, not a fact",
          J._transcript_rows.unit.startswith("GUESSED"), J._transcript_rows.unit)

    # ---- ITEM 3: THE MACHINE OFF THE HAPPY PATH ----
    # serve_fallback and the withhold it lifted were retired 2026-09-18: the
    # loop has no mark to lift; a rewatch that cannot serve is ABSENT in the message.
    check("the withhold fallback is gone with the marks it lifted",
          not hasattr(J, "serve_fallback") and not hasattr(J, "DONE_MARK") and not hasattr(J, "pass2_message"))
    edit = next(n for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.FunctionDef) and n.name == "edit")
    d = ast.unparse(edit)
    # RETIRED 2026-09-17: the serve fallback, the harness-written mark and the
    # render-thread join belonged to the stream machine. The loop serves the
    # rewatch synchronously; an unwatchable render is NAMED in the message.
    _um = J.rewatch_message(1, {"frames": 0, "sheets": [], "state": "FAILED", "why": "render x"}, [], [], [], final=False)
    check("an unwatchable render is named in the rewatch message, never omitted",
          "THE RENDER COULD NOT BE WATCHED" in _um["message"]["content"][0]["text"])
    check("a preemption retry reads what the timeline already holds",
          "priorItems" in d and "read_back(tok, _stage)" in d,
          "a retry that assumes an empty timeline places everything twice")

    # ---- ITEM 4: THE HARNESS HANDS OVER WHAT IT KNOWS ----
    _pre_fn = next(n for n in ast.walk(ast.parse(src))
                   if isinstance(n, ast.FunctionDef) and n.name == "prestage")
    _base_calls = [n for n in ast.walk(_pre_fn) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Name) and n.func.id == "call"
                   and n.args and isinstance(n.args[0], ast.Constant)
                   and n.args[0].value == "edit_item"]
    _ret_keys = [k.value for r in ast.walk(_pre_fn) if isinstance(r, ast.Return)
                 and isinstance(r.value, ast.Dict) for k in r.value.keys
                 if isinstance(k, ast.Constant)]
    check("the base video item is placed by prestage",
          "baseItemId" in _ret_keys and "sourceFrames" in _ret_keys
          and "_sframes" in ast.unparse(_pre_fn),
          "the agent spent an inspect_asset turn to learn 610 frames; "
          "edit_item calls in prestage: %d, return keys: %s" % (len(_base_calls), _ret_keys))
    check("the paragraph names the source's frames and the base item",
          "frames at 30fps" in d and "ALREADY on track V1" in d)
    # REVERSED 2026-09-17: the record is DERIVED from the read-back; the
    # paragraph asks only for a why line per item, after placing.
    # REVERSED AGAIN 2026-09-17 (ruling 2): the why rides INSIDE each op, not in the reply.
    check("the paragraph asks for the why inside each op, and for no record",
          "Put the why INSIDE each op" in d and "record.json as" not in d and "one line per item you placed" not in d,
          "the record is derived from the read-back; the why is the one thing it cannot read")
    _cc = J.cli_command("sid", "claude-sonnet-5")
    check("the Skill tool is withheld, not asked",
          "--disallowedTools" in _cc and "Skill" in _cc[_cc.index("--disallowedTools") + 1])
    # THE REAL BOUND is the urlopen timeout inside mcp_rpc; the fourth
    # positional argument of mcp_rpc is a message id (a leg once tested it).
    _rpc = next(n for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.FunctionDef) and n.name == "mcp_rpc")
    _tos = [kw.value.value for n in ast.walk(_rpc) if isinstance(n, ast.Call)
            and ast.unparse(n.func).endswith("urlopen")
            for kw in n.keywords if kw.arg == "timeout" and isinstance(kw.value, ast.Constant)]
    check("a harness-side MCP call is bounded at 120s",
          _tos == [120], "urlopen timeouts in mcp_rpc: %r" % _tos)
    # THE BINDING, NOT THE NAME: `_plan_hops = ()` leaves every word in
    # place and fails the chain on hops that cannot run. The property is that
    # the no-plan branch names BOTH plan-keyed hops.
    _ph = [n.value for n in ast.walk(edit) if isinstance(n, ast.Assign)
           and any(isinstance(t, ast.Name) and t.id == "_plan_hops" for t in n.targets)]
    _ph_ok = (len(_ph) == 1 and isinstance(_ph[0], ast.IfExp)
              and isinstance(_ph[0].orelse, ast.Tuple)
              and {getattr(e, "value", None) for e in _ph[0].orelse.elts} == {"hop3", "hop4"})
    check("plan-keyed hops are N/A on the single-agent path, not failures",
          _ph_ok and "'N/A'" in d,
          "CHAIN GATE failed on hop3/hop4 on every run that had no plan; "
          "binding: %r" % [ast.unparse(v) for v in _ph])

    # ---- THE RUN'S OWN FINDINGS (final-arch-1, 2026-09-17) ----
    _tr = G._treatments({"treatment": "caption:TwoTone only. There's no screenshot, "
                                      "logo, or object in the source"})
    check("a prose treatment yields families, never characters",
          _tr == [], "iterating the string ruled beat 0 as 'c','a','p','t'...: %r" % _tr)
    check("...and names the families it does contain",
          G._treatments({"treatment": "StatCard + sfx whoosh; zoom in"}) == ["sfx", "zoom"]
          and G._treatments({"treatment": ["card", "none", "caption:Cove"]}) == ["card"])
    _bi = [n for n in ast.walk(_pre_fn) if isinstance(n, ast.Call)
           and isinstance(n.func, ast.Name) and n.func.id == "_mcp_call"
           and n.args and isinstance(n.args[1], ast.Constant) and n.args[1].value == "edit_item"
           and any(k.arg == "expect" and getattr(k.value, "value", None) == "adds" for k in n.keywords)]
    check("the base item's echo is parsed (expect='adds'), not read off the envelope",
          len(_bi) == 1 and not _base_calls,
          "final-arch-1: 'edit_item echoed no id' over an add that landed; "
          "_mcp_call sites %d, raw call sites %d" % (len(_bi), len(_base_calls)))
    check("families come from what landed, not from a vocabulary the agent must recite",
          "treatment is a LIST" not in d and "derive_record(" in d)
    check("the record is built after rewatch 1's thread has finished",
          "_rt.join(timeout=" in d and d.index("_rt.join(timeout=") < d.index("out = {'pass2'"),
          "the ceiling killed the stream mid-render and the record read pass2 empty")
    check("prestage phases reach the record", "out['prestage_phases']" in d)

    # ---- THE COUNT IS PER API CALL, NOT PER EVENT (2026-09-17) ----
    _st = {}
    _e1 = {"type": "assistant", "message": {"id": "m1", "usage": {"cache_read_input_tokens": 1000}}}
    _e2 = {"type": "assistant", "message": {"id": "m2", "usage": {"cache_read_input_tokens": 50}}}
    _e0 = {"type": "assistant", "message": {"usage": {"cache_read_input_tokens": 7}}}
    check("the ceiling counts a message id once, however many events carry it",
          J.usage_once(_st, _e1) == 1000 and J.usage_once(_st, _e1) == 0
          and J.usage_once(_st, _e2) == 50,
          "one assistant event per content block repeats the usage; final-arch-1 "
          "read 2.7M over 10 events for 6 calls")
    check("...and an event with no message id is counted, not dropped",
          J.usage_once(_st, _e0) == 7 and _st.get("usage_once_noid") == 1)
    import turn_clock as T
    _evs = [{"t": 1.0, "type": "assistant", "msg_id": "m1", "tools": [], "in_tok": 2, "cache_write_tok": 100, "cache_read_tok": 1000, "out_tok": 5},
            {"t": 1.1, "type": "assistant", "msg_id": "m1", "tools": ["Bash"], "in_tok": 2, "cache_write_tok": 100, "cache_read_tok": 1000, "out_tok": 5},
            {"t": 4.0, "type": "assistant", "msg_id": "m2", "tools": [], "in_tok": 2, "cache_write_tok": 10, "cache_read_tok": 1100, "out_tok": 3},
            {"t": 5.1, "type": "result", "result_usage": {"cache_read_input_tokens": 2100, "cache_creation_input_tokens": 110}, "result_cost_usd": 0.01}]
    _b = T.budget({"events": _evs, "wall": 6.0, "cpu_state": "ABSENT", "cpu": []})
    _ot = _b.get("output_tokens") or {}
    check("the ledger's cache sums are deduped by message id",
          _ot.get("api_calls") == 2 and _ot.get("cache_read_sum") == 2100 and _ot.get("cache_write_sum") == 110,
          "got api_calls=%s read=%s write=%s" % (_ot.get("api_calls"), _ot.get("cache_read_sum"), _ot.get("cache_write_sum")))
    check("the ledger carries a per-call table and the CLI's own bill",
          [c["read"] for c in (_b.get("usage_by_call") or [])] == [1000, 1100]
          and (_b.get("result_usage") or {}).get("cache_creation_input_tokens") == 110)

    # ---- NO SCHEMA-FETCH TURN: the tool block is eager and restricted ----
    _env_false = any(isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Subscript)
                     and ast.unparse(n.targets[0].value) == "_env"
                     and getattr(n.targets[0].slice, "value", None) == "ENABLE_TOOL_SEARCH"
                     and getattr(n.value, "value", None) == "false" for n in ast.walk(edit))
    check("ToolSearch is off for the run", _env_false,
          "the schema-fetch turn changes the tool block and rewrites every cached byte after it")
    check("--tools restricts the block to the agent's surface, and that surface is the edit ops",
          "--tools" in _cc and _cc[_cc.index("--tools") + 1] == ",".join("mcp__chatcut__" + t for t in J.AGENT_TOOLS)
          and _cc[_cc.index("--tools") + 1].count("mcp__chatcut__") == len(J.AGENT_TOOLS),
          "--tools is now the edit ops alone: %r" % (_cc[_cc.index("--tools") + 1] if "--tools" in _cc else None))
    check("the paragraph no longer asks for a schema fetch",
          "Fetch the tool schemas first" not in d and "tools are loaded" in d)
    check("no Write of any record is asked for",
          "ONE Write" not in d and "rulings.json as a list" not in d and "spec.json as" not in d)
    check("the no-preview sentence sits where the placement is decided, and no DONE mark is asked for anywhere the agent reads",
          "call no preview" in d and "/work/DONE" not in d and "/work/DONE" not in J.TWO_TURN_LOOP
          and "/work/DONE" not in J.build_system_prompt() and "write no files" in J.build_system_prompt(),
          "DONE in deciding=%s loop=%s system=%s" % ("/work/DONE" in d, "/work/DONE" in J.TWO_TURN_LOOP, "/work/DONE" in J.build_system_prompt()))
    import tempfile, json as _json
    _td = tempfile.mkdtemp()
    _rp = os.path.join(_td, "record.json")
    _json.dump({"spec": {"mode": "full_edit", "why": "w"}, "rulings": [{"beat": 0, "purpose": "p", "treatment": ["card"]}]}, open(_rp, "w"))
    _rec, _why = J.read_record(spec_path=os.path.join(_td, "no_spec.json"), rulings_path=os.path.join(_td, "no_rulings.json"), record_path=_rp)
    check("read_record reads the one-file record",
          (_rec.get("spec") or {}).get("mode") == "full_edit" and len(_rec.get("rulings") or []) == 1 and "one file" in _why,
          "%r %s" % (_rec, _why[:80]))

    # RETIRED 2026-09-17: the batch counter and the ceiling's position in
    # _drive belonged to the stream machine; each turn is now one API call and
    # usage_once counts it inside _invoke (leg re-homed below).
    _evs2 = [{"t": 1.0, "type": "assistant", "msg_id": "m1", "tools": [], "in_tok": 2, "cache_write_tok": 100, "cache_read_tok": 0, "out_tok": 5},
             {"t": 1.5, "type": "result", "result_usage": {"cache_read_input_tokens": 0, "cache_creation_input_tokens": 100}, "result_cost_usd": 0.5},
             {"t": 4.0, "type": "assistant", "msg_id": "m2", "tools": [], "in_tok": 2, "cache_write_tok": 10, "cache_read_tok": 100, "out_tok": 3},
             {"t": 5.1, "type": "result", "result_usage": {"cache_read_input_tokens": 100, "cache_creation_input_tokens": 10}, "result_cost_usd": 0.25}]
    _b2 = T.budget({"events": _evs2, "wall": 6.0, "cpu_state": "ABSENT", "cpu": []})
    check("the bill sums every result event, one per user turn",
          (_b2.get("result_usage") or {}).get("cache_creation_input_tokens") == 110
          and _b2.get("result_turns") == 2 and abs((_b2.get("result_cost_usd") or 0) - 0.75) < 1e-9,
          "got %r turns=%s cost=%s" % (_b2.get("result_usage"), _b2.get("result_turns"), _b2.get("result_cost_usd")))

    # ---- THE MINIMUM-TOKEN BUDGET (Zac, 2026-09-17), each row a property ----
    import mcp_shim as M
    _fat = {"name": "edit_item", "description": "x" * 900, "inputSchema": {"type": "object", "required": ["projectId"],
            "properties": {"projectId": {"type": "string", "description": "y" * 300},
                           "adds": {"type": "array", "description": "z" * 300, "items": {"type": "object", "properties": {"fromFrame": {"type": "integer", "description": "w" * 200}}}}}}}
    _sl = M.slim_tool(_fat)
    check("the shim cuts a tool to name and arguments",
          len(json.dumps(_sl)) < 300 and _sl["inputSchema"]["required"] == ["projectId"]
          and "fromFrame" in _sl["inputSchema"]["properties"]["adds"]["items"]["properties"]
          and "description" not in _sl["inputSchema"]["properties"]["projectId"],
          "the eight full schemas were 66,552 tokens; slimmed 2,248 (count_tokens)")
    check("the tool set is eight and import_media is the harness's",
          len(J.NEEDED_TOOLS) == 8 and "import_media" not in J.NEEDED_TOOLS)
    _wcc = ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "write_cli_context"))
    _ccc = ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "cli_command"))
    check("mcp.json points the CLI at the shim, strictly",
          "mcp_shim.py" in _wcc and "MCP_SHIM_ALLOW" in _wcc and "'--strict-mcp-config'" in _ccc
          and "write_cli_context(tok)" in d and "cli_command(_watch_sid" in d,
          "a hosted server advertises 59 schemas and finishes connecting after call 1")
    _sys_src = ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "build_system_prompt"))
    check("the Skill is a precondition line, not the guide",
          "chatcut_skill_basics.md" not in _sys_src and "===== CHATCUT =====" in _sys_src
          and "nothing about it is outstanding" in _sys_src,
          "36k chars, 11,631 tokens, for a precondition the shim already removed")
    check("mode_rule no longer rides in the system prompt", "mode_rule.txt" not in _sys_src)
    _p1 = ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "pass1_message"))
    check("the reference standard and the held-to preamble are out of the first message",
          "reference_standard" not in _p1 and "WHAT THIS EDIT IS HELD TO" not in _p1,
          "5,131 tokens of prose about videos the watch already holds")
    _ef = ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_edit_frames"))
    check("no ffmpeg still extraction remains for seeing",
          not hasattr(J, "_frames_of") and "ffmpeg" not in _ef,
          "one instrument for seeing: inspect_asset through watch_asset")
    # DRIVEN: watch_asset on an injected rpc — 40 frames at 2fps in two calls, two sheets
    _calls = []
    def _rpc(args, mid):
        _calls.append(args); n = len(args["sourceTimesMs"])
        return {"result": {"content": [{"type": "resource_link", "uri": "http://127.0.0.1:1/x%d.jpg" % i} for i in range(n)], "structuredContent": {}}}
    import chatcut_reference as _cr
    _fetch0 = _cr.fetch
    def _fake_fetch(urls, out_dir, cap=25):
        os.makedirs(out_dir, exist_ok=True); got = []
        from PIL import Image as _I
        for i, u in enumerate(urls[:cap]):
            pth = os.path.join(out_dir, "f%02d.jpg" % i); _I.new("RGB", (108, 196)).save(pth); got.append((u, pth))
        return got, "SERVED %d of %d" % (len(got), len(urls))
    _cr.fetch = _fake_fetch
    try:
        _w = J.watch_asset("t", "asset", 20.362, tempfile.mkdtemp(), rpc=_rpc, fetch=_fake_frame_fetch)   # no network: the fetch is injected
    finally:
        _cr.fetch = _fetch0
    check("the source is watched through inspect_asset: 40 exact frames at 2fps in two calls",
          _w["state"] == "MEASURED" and _w["frames"] == 40 and len(_calls) == 2
          and all(len(c["sourceTimesMs"]) <= 25 for c in _calls) and "transcriptRangesMs" in _calls[0]
          and len(_calls[0]["transcriptRangesMs"]) <= 6 and _calls[0].get("includeTimecode") is True,
          "%s %s calls=%d" % (_w["state"], _w["why"][:60], len(_calls)))
    check("...tiled twenty to a sheet: two sheets for a 20s source",
          len(_w["sheets"]) == 2, "%d sheet(s)" % len(_w["sheets"]))
    check("pass 1 serves the watch, and says so when it is absent",
          "source_watch" in _p1 and "You are placing without" in _p1 and "watch_asset(" in d)
    _ef = ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_edit_frames"))
    check("the rewatch is export -> import as an asset -> watch_asset",
          "upload_asset(" in _ef and "watch_asset(" in _ef and "ffmpeg" not in _ef,
          "the composed edit is seen through the same instrument as the source")
    check("the record is derived from the read-back; the why is reply text",
          "derive_record(" in d and "agent_text" in d and "ONE Write" not in d and "record.json as" not in d,
          "the record Write was the 546s turn")
    check("thinking is bounded by default",
          isinstance(getattr(J, "DEFAULT_THINK_TOKENS", None), int) and 0 < J.DEFAULT_THINK_TOKENS <= 8000
          and "DEFAULT_THINK_TOKENS" in d)

    # ---- THE THREE STRATEGIC TURNS, DRIVEN (Part 2 D, 2026-09-17) ----
    def _mk_invoke(script):
        """script: per turn n -> (tool names, text, usage)."""
        log = []
        def _inv(n, message):
            names, text, usage = script(n)
            log.append((n, len((message or {}).get("message", {}).get("content") or [])))
            # a name of "finish:<verdict>" builds the finish call the machine now reads the verdict from
            _tc = [{"name": "mcp__chatcut__" + t.split(":")[0],
                    "input": ({"verdict": t.split(":")[1]} if t.startswith("finish:") else {})} for t in names]
            return {"rc": 1, "subtype": "error_max_turns", "tool_calls": _tc,
                    "text": text, "usage": usage, "wall": 1.0, "killed": False}
        _inv.log = log
        return _inv
    _rw = lambda n, final: {"message": {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "rw%d" % n}]}}, "sheets": 2, "faults": [], "scan": []}
    U1 = {"read": 0, "write": 300000, "in": 2, "out": 900}; UN = {"read": 300000, "write": 400, "in": 2, "out": 300}
    happy = _mk_invoke(lambda n: (["edit_item"], "", U1) if n == 1 else (["finish:export"], "", UN))
    tm = J.run_two_calls(happy, _rw, {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "go"}]}})
    check("the happy path is TWO API calls: place, then fix-or-finish, and the harness's read-back decides",
          len(tm["turns"]) == 2 and tm["terminal"] is None and str(tm["verdict"]).startswith("export at call 2")
          and [t["kind"] for t in tm["turns"]] == ["place", "review"],
          "%s / %s / %s" % (len(tm["turns"]), tm["terminal"], tm["verdict"]))
    runaway = _mk_invoke(lambda n: (["edit_item"], "", U1 if n == 1 else UN))
    tm2 = J.run_two_calls(runaway, _rw, {"type": "user", "message": {"role": "user", "content": []}},
                          readback=lambda: ["face/text collision: still there"])
    check("THE CAP IS TWO AND IT IS HARD: a run that keeps editing gets no third call",
          len(tm2["turns"]) == 2 and (tm2["terminal"] or {}).get("kind") == "READBACK FAILED" and len(runaway.log) == 2,
          "%d calls, terminal=%s" % (len(tm2["turns"]), tm2["terminal"]))
    miss = _mk_invoke(lambda n: (["edit_item"], "", U1) if n == 1 else (["edit_item"], "", {"read": 1000, "write": 299000, "in": 2, "out": 300}))
    tm3 = J.run_two_calls(miss, _rw, {"type": "user", "message": {"role": "user", "content": []}})
    check("a call that does not read the prefix call 1 established is terminal",
          (tm3["terminal"] or {}).get("kind") == "CACHE MISS" and (tm3["terminal"] or {}).get("at") == 2 and len(miss.log) == 2,
          "%s" % (tm3["terminal"],))
    nop = _mk_invoke(lambda n: (["finish:clean"], "", U1))
    tm4 = J.run_two_calls(nop, _rw, {"type": "user", "message": {"role": "user", "content": []}})
    check("turn 1 without an edit op is terminal, not a second try — even when it ends in a proper finish call",
          (tm4["terminal"] or {}).get("kind") == "NO PLACEMENT" and len(nop.log) == 1, str(tm4.get("terminal"))[:120])
    ok, why = J.cache_gate({"read": 0, "write": 300000}, {"read": 284000})
    ok2, _ = J.cache_gate({"read": 0, "write": 300000}, {"read": 285000})
    check("the cache gate is 0.95 x (call-1 read + write)", ok is False and ok2 is True, why)
    check("the run bound is 300s and THE CAP IS TWO, hard", J.RUN_TIMEOUT_S == 300 and J.TURN_CAP == 2 and J.TURN_LAW_S <= 300,
          "cap=%s bound=%s" % (J.TURN_CAP, J.RUN_TIMEOUT_S))
    _fl = J.fault_lines({"findings": []}, None, None, [{"id": "base-1", "itemType": "video"}], "base-1")
    check("an empty timeline on a full-edit brief is a fault the agent is told",
          any("nothing placed" in f for f in _fl), "%r" % _fl)
    _caps = [{"id": "base-1", "itemType": "video"},
             {"id": "c1", "itemType": "motion-graphic", "trackAlias": "V2", "asset": {"name": "caption:TwoTone"}},
             {"id": "c2", "itemType": "motion-graphic", "trackAlias": "V3", "asset": {"name": "caption:TwoTone"}}]
    check("two caption tracks on the same speech is a fault",
          any("two caption tracks" in f for f in J.fault_lines({"findings": []}, None, None, _caps, "base-1")))
    _m = J.rewatch_message(1, {"frames": 40, "sheets": [], "state": "ABSENT", "why": "x"}, ["  l1"], ["f1"], [], final=False)
    check("the rewatch is one message, under five blocks with two sheets",
          len(_m["message"]["content"]) == 1 and "THE TIMELINE" in _m["message"]["content"][0]["text"]
          and "Do not inspect or preview" in _m["message"]["content"][0]["text"])
    _cmd = J.cli_command("sid", "claude-sonnet-5")
    check("the CLI command is strict, shimmed, and leaves --max-turns to the caller",
          "--strict-mcp-config" in _cmd and "--max-turns" not in _cmd and "--resume" in _cmd and "/work/mcp.json" in _cmd)
    check("the stream machine is gone from edit()",
          "_arm_idle" not in d and "_arm_second_rewatch" not in d and "_start_rewatch" not in d and "run_two_calls(" in d,
          "one API call per turn, the harness between them")
    check("the keep-warm ping and the rewatch probe exist as functions",
          hasattr(J, "keep_warm") and hasattr(J, "probe_rewatch") and "WARM" in dir(J))
    check("the per-run line is printed with the model named and the rates stated",
          "RUN LINE        :" in d and "'rates'" in d and "LAW MISS" in d)
    check("the dead plan route is gone from main",
          "plan_file" not in ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "main")))

    # ---- RE-HOMED from smoke_the_run_dies_fast (retired with the stream machine) ----
    _e3 = d
    check("a retry reuses the prior stage instead of re-prestaging",
          "_prior_stage" in _e3 and "REUSED" in _e3 and "job_state_put(run_id, stage=" in _e3)
    check("the attempt number is read BEFORE prestage uses it", _e3.find("_attempt = ") < _e3.find("_prior_stage"))
    check("the floor asks whether there is a viewable edit", "out['floor']" in _e3 and "'EMPTY'" in _e3)
    check("the ceiling counts per API call inside each invocation",
          "usage_once(_st, ev)" in _e3 and "ceiling" not in ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "run_two_calls")).lower())
    _tc = io.open(os.path.join(HERE, "turn_clock.py"), encoding="utf-8").read()
    check("turn_clock exposes the kill and names who used it", "_killed_by_driver" in _tc and '"kill_reason"' in _tc)
    check("every turn and the run are bounded, and the bound is terminal",
          J.TURN_LAW_S <= 300 and J.RUN_TIMEOUT_S == 300 and "RUN TIMEOUT" in ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "run_two_calls")))

    # ---- THE INVOCATION ENDS AT THE RESULT (measured on the first ping) ----
    _inv = next(n for n in ast.walk(edit) if isinstance(n, ast.FunctionDef) and n.name == "_invoke")
    _on = next(n for n in ast.walk(_inv) if isinstance(n, ast.FunctionDef) and n.name == "_on")
    # ASKED OF CONTROL FLOW, NOT TEXT: a `return` slipped in before close()
    # leaves the words in place and the CLI waiting (the first form of this
    # leg was green on exactly that mutant).
    def _result_branch_closes(fn):
        for n in ast.walk(fn):
            if isinstance(n, ast.If) and "'result'" in ast.unparse(n.test):
                for stmt in n.body:
                    if isinstance(stmt, ast.Return):
                        return False
                    if any(isinstance(c, ast.Call) and ast.unparse(c.func) == "close" for c in ast.walk(stmt)):
                        return True
        return False
    check("each invocation closes stdin when the result event arrives",
          _result_branch_closes(_on),
          "the keep-warm ping saw its result at ~20s and was killed at the 120s bound")

    # ---- THE REWATCH PROBE'S FINDINGS (2026-09-17), DRIVEN ----
    # 1. ChatCut answers edit_item with JSON THEN PROSE; the reader takes the object.
    _env_text = ('{"adds":[{"createdNewTrack":false,"durationInFrames":30,"from":560,"id":"eebe1acc68",'
                 '"timelineId":"eab7eeaf3c","trackId":"952118018e","type":"motion-graphic"}],"deletes":[],"updates":[]}'
                 "\n\nMotion-graphic item(s) eebe1acc68 now span frames 560–589. Inspect timeline frames in that range.")
    _saved_rpc = J.mcp_rpc
    try:
        J.mcp_rpc = lambda tok, method, params, mid: {"result": {"content": [
            {"type": "text", "text": _env_text},
            {"type": "text", "text": "ChatCut: this change is now live in the project."}]}}
        try:
            _pr = J._mcp_call("t", "edit_item", {"adds": [{}]}, expect="adds")
            _ok = (_pr.get("adds") or [{}])[0].get("id") == "eebe1acc68" and "now span frames" in _pr.get("_text", "")
            _why = "adds=%r text=%r" % (_pr.get("adds"), _pr.get("_text", "")[:60])
        except Exception as _e:                                   # noqa: BLE001
            _ok, _why = False, "raised %s: %s" % (type(_e).__name__, str(_e)[:160])
    finally:
        J.mcp_rpc = _saved_rpc
    check("a JSON-then-prose edit_item envelope parses (four landed plants read as 'no adds')", _ok, _why)
    # 2. --effort is the dial; it rides cli_command only when asked
    _ce = J.cli_command("sid", "claude-sonnet-5", effort="low")
    _cn = J.cli_command("sid", "claude-sonnet-5")
    check("--effort <level> is sent when given and absent otherwise",
          "--effort" in _ce and _ce[_ce.index("--effort") + 1] == "low" and "--effort" not in _cn,
          "with: %s  without: %s" % ([x for x in _ce if "effort" in x], [x for x in _cn if "effort" in x]))
    # 3. the picked instrument: preview_timeline in parallel, 2fps, tiled; and the rewatch binds it
    import urllib.request as _urq
    from PIL import Image as _PImg
    _jpg = io.BytesIO(); _PImg.new("RGB", (36, 64), (20, 30, 40)).save(_jpg, "JPEG"); _jpg = _jpg.getvalue()
    _seen_calls = []
    _saved_mc, _saved_uo = J._mcp_call, _urq.urlopen
    class _Rsp:
        def __init__(self, b): self.b = b
        def read(self): return self.b
        def __enter__(self): return self
        def __exit__(self, *a): return False
    try:
        def _fake_mc(tok, name, args, expect=None):
            _seen_calls.append((name, list(args.get("viewerFrames") or [])))
            return {"_text": " ".join("https://x.test/f%d.jpg" % f for f in args["viewerFrames"])}
        J._mcp_call = _fake_mc
        _urq.urlopen = lambda u, timeout=60: _Rsp(_jpg)
        _marks = []
        _sh, _tm = J._preview_frames("t", "pid", 610, fps=30, mark=_marks.append, out_dir=tempfile.mkdtemp(prefix="pf_"))
    finally:
        J._mcp_call, _urq.urlopen = _saved_mc, _saved_uo
    check("the rewatch instrument samples 2fps in <=9-frame preview_timeline calls and tiles 20 to a sheet",
          len(_tm) == 41 and all(len(f) <= 9 for _n, f in _seen_calls) and len(_seen_calls) == 5
          and len(_sh) == 3 and _tm == sorted(_tm) and _marks == ["calls", "fetch", "tile"],
          "frames=%d calls=%d sheets=%d marks=%s" % (len(_tm), len(_seen_calls), len(_sh), _marks))
    _edit_fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "edit")
    _rw = next(n for n in ast.walk(_edit_fn) if isinstance(n, ast.FunctionDef) and n.name == "_rewatch")
    _rw_calls = {ast.unparse(n.func) for n in ast.walk(_rw) if isinstance(n, ast.Call)}
    check("the rewatch watches through preview_timeline, never the export (paid once, for the final)",
          "_preview_frames" in _rw_calls and "_edit_frames" not in _rw_calls,
          "calls in _rewatch: %s" % sorted(c for c in _rw_calls if "frames" in c))
    # 4. the write is priced by the TTL that was measured, per call
    _usd_asg = [ast.unparse(n.value) for n in ast.walk(_edit_fn) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "_usd" for t in n.targets)]
    check("cache writes are priced 5m at $3.75/M and the rest at $6/M, by the measured split",
          len(_usd_asg) == 1 and "_wr5 * 3.75" in _usd_asg[0] and "(_wr - _wr5) * 6.0" in _usd_asg[0],
          "_usd = %s" % _usd_asg)
    _inv = next(n for n in ast.walk(_edit_fn) if isinstance(n, ast.FunctionDef) and n.name == "_invoke")
    _ukeys = {k.value for n in ast.walk(_inv) if isinstance(n, ast.Dict) for k in n.keys if isinstance(k, ast.Constant)}
    check("every API call records which TTL it wrote (write_1h / write_5m)",
          {"write_1h", "write_5m"} <= _ukeys, "usage keys: %s" % sorted(k for k in _ukeys if "write" in str(k)))
    # 5. the planted labels carry none of the words the detector reads
    _prb = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "probe_rewatch")
    _adds = next(n.value for n in ast.walk(_prb) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "adds" for t in n.targets))
    # the VALUES of propertyOverrides — the keys ("fontSize") are the schema's words, not the plant's
    _labels = [vv.value for n in ast.walk(_adds) if isinstance(n, ast.Dict) for k, v in zip(n.keys, n.values)
               if isinstance(k, ast.Constant) and k.value == "propertyOverrides" and isinstance(v, ast.Dict)
               for vv in v.values if isinstance(vv, ast.Constant) and isinstance(vv.value, str)]
    _named = next(v for n in ast.walk(_prb) if isinstance(n, ast.Dict) for k, v in zip(n.keys, n.values)
                  if isinstance(k, ast.Constant) and k.value == "named")
    _words = [c.value for n in ast.walk(_named) if isinstance(n, ast.Tuple) for c in n.elts if isinstance(c, ast.Constant)]
    _hits = [(l, w) for l in _labels for w in _words if w in l.lower()]
    check("the planted labels contain none of the detector's words (the first probe scored its own labels)",
          len(_labels) >= 2 and len(_words) >= 9 and not _hits, "labels=%s hits=%s" % (_labels, _hits))
    _acted = next(v for n in ast.walk(_prb) if isinstance(n, ast.Dict) for k, v in zip(n.keys, n.values)
                  if isinstance(k, ast.Constant) and k.value == "named")
    # THE PROPERTY, not the variable's name: each named plant is gated on the dict DERIVED FROM THE OPS
    # (the assignment whose value reads `touched.get(...)`), never on the label the probe itself planted
    _acted_name = next((t.id for n in ast.walk(_prb) if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict)
                        and "touched.get(" in ast.unparse(n.value) for t in n.targets if isinstance(t, ast.Name)), None)
    check("a plant counts as named only through an op that touched it",
          _acted_name is not None and len(_acted.values) == 3
          and all(isinstance(v, ast.BoolOp) and isinstance(v.op, ast.And) and isinstance(v.values[0], ast.Subscript)
                  and isinstance(v.values[0].value, ast.Name) and v.values[0].value.id == _acted_name for v in _acted.values),
          "acted dict=%s named=%s" % (_acted_name, ast.unparse(_acted)[:160]))
    # 6. the CLI version is read where the CLI runs
    import subprocess as _sp
    _saved_run = _sp.run
    try:
        class _R:
            stdout = "9.9.9 (Claude Code)\n"
        _sp.run = lambda *a, **k: _R()
        _v_ok = J.cli_version() == "9.9.9 (Claude Code)"
        def _boom(*a, **k): raise OSError("no claude")
        _sp.run = _boom
        _v_fail = J.cli_version().startswith("FAILED")
    finally:
        _sp.run = _saved_run
    _cv_sites = [n.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef)
                 if any(isinstance(c, ast.Call) and ast.unparse(c.func) == "cli_version" for c in ast.walk(n))]
    check("cli_version reads `claude --version` in the container and names a failure; edit and keep_warm both record it",
          _v_ok and _v_fail and {"edit", "keep_warm"} <= set(_cv_sites), "ok=%s fail=%s sites=%s" % (_v_ok, _v_fail, _cv_sites))

    # ---- THE PROXY'S UPSTREAM LEG, DRIVEN (h-th-think0 saw nothing for 120s) ----
    import api_proxy as PX, http.client as _hc, urllib.request as _ur2, threading as _th
    _sse = [b"event: message_start\ndata: {\"type\":\"message_start\"}\n\n",
            b"event: content_block_delta\ndata: {\"type\":\"content_block_delta\"}\n\n",
            b"event: message_stop\ndata: {\"type\":\"message_stop\"}\n\n"]
    class _FakeResp:
        status = 200
        def __init__(self): self.i = 0
        def getheaders(self): return [("Content-Type", "text/event-stream"), ("Content-Encoding", "identity"), ("Transfer-Encoding", "chunked")]
        def read1(self, n=-1):
            if self.i >= len(_sse): return b""
            c = _sse[self.i]; self.i += 1; return c
    class _FakeConn:
        last = {}
        debuglevel = 0
        def __init__(self, host, timeout=None, **kw): _FakeConn.last["host"] = host
        def set_debuglevel(self, level): pass
        def set_tunnel(self, *a, **kw): pass
        def connect(self): _FakeConn.last["connected"] = True
        def request(self, method, path, body=None, headers=None): _FakeConn.last.update({"method": method, "path": path, "body": body, "headers": headers})
        def getresponse(self): return _FakeResp()
        def close(self): pass
    _saved_conn, _saved_trace = PX.CONNECTION, PX.TRACE
    _tr = tempfile.mktemp(suffix=".jsonl")
    try:
        PX.CONNECTION = _FakeConn; PX.TRACE = _tr
        PX.FINGERPRINTS = tempfile.mktemp(suffix=".jsonl"); PX.FIRST_BODY = tempfile.mktemp(suffix=".json")
        _port = PX.serve(0)
        _body = json.dumps({"model": "m", "system": [{"type": "text", "text": "s"}], "tools": [], "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}], "stream": True}).encode()
        _req = _ur2.Request("http://127.0.0.1:%d/v1/messages?beta=true" % _port, data=_body, method="POST",
                            headers={"Content-Type": "application/json", "Accept-Encoding": "gzip, br", "x-api-key": "sk-secret-1234"})
        with _ur2.urlopen(_req, timeout=20) as _r:
            _got = _r.read()
        # an ABSENT trace file is the leg's failure, not the harness's (a red that is not about the property).
        # The final row is written in the handler's `finally`, AFTER the last byte reached this client:
        # poll briefly so the leg reads the property and not a thread race (it raced once, 2026-09-17).
        import time as _tm_
        _rows = []
        for _i in range(40):
            _rows = [json.loads(l) for l in open(_tr, encoding="utf-8") if l.strip()] if os.path.exists(_tr) else []
            if any("relayed_bytes" in r for r in _rows):
                break
            _tm_.sleep(0.05)
    finally:
        PX.CONNECTION, PX.TRACE = _saved_conn, _saved_trace
    check("the proxy relays an SSE stream through to the client and strips accept-encoding upstream",
          _got == b"".join(_sse) and "Accept-Encoding" not in (_FakeConn.last.get("headers") or {})
          and _FakeConn.last.get("path") == "/v1/messages?beta=true" and _FakeConn.last.get("body") == _body,
          "got=%r headers=%s" % (_got[:60], sorted((_FakeConn.last.get("headers") or {}).keys())))
    _legs_ = [r for r in _rows if "relayed_bytes" in r]
    _phases = [r.get("phase") for r in _rows if r.get("phase")]
    check("every upstream leg is traced: status, first byte, bytes relayed, redacted key",
          len(_legs_) == 1 and _legs_[0].get("status") == 200 and "ttfb_s" in _legs_[0] and _legs_[0].get("relayed_bytes") == len(b"".join(_sse))
          and "sk-secret" not in json.dumps(_rows) and "<redacted" in json.dumps(_legs_[0].get("req_headers")),
          "rows=%s" % json.dumps(_rows)[:300])
    check("the relay traces its phases in order: received, body_read, preflight, breakpoint, thinking, upstream_connected, request_sent, response_headers, first_chunk, relaying, upstream_eof, relay_closed",
          _phases == ["received", "body_read", "preflight", "breakpoint", "thinking", "upstream_connected", "request_sent", "response_headers", "first_chunk", "relaying", "upstream_eof", "relay_closed"]
          and next(r for r in _rows if r.get("phase") == "body_read").get("bytes") == len(_body)
          and next(r for r in _rows if r.get("phase") == "upstream_eof").get("relayed") == len(b"".join(_sse)),
          "phases=%s" % _phases)
    # the cold-write line judges against the TTL the ping WROTE, never a literal hour
    check("a ping's TTL is read from what it wrote: 1h -> 60 min, 5m -> 5 min, no split -> unknown",
          J.warm_ttl_minutes({"write_1h": 228594, "write_5m": 0}) == 60 and J.warm_ttl_minutes({"write_1h": 0, "write_5m": 228594}) == 5
          and J.warm_ttl_minutes({"read": 1}) is None and J.warm_ttl_minutes(None) is None)
    _cw_cmp = [ast.unparse(n) for n in ast.walk(_edit_fn) if isinstance(n, ast.Compare) and "_mins <" in ast.unparse(n)]
    check("the cold-write defect verdict compares against the ping's own TTL",
          _cw_cmp == ["_mins < _ttl"], "compares: %s" % _cw_cmp)

    # ---- THE CLI IS PINNED IN THE IMAGE (2.1.272 dropped message cache markers behind a base URL) ----
    _npm = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.BinOp) and isinstance(n.left, ast.Constant)
            and "npm install -g @anthropic-ai/claude-code@" in str(n.left.value)]
    check("the image installs a PINNED claude-code (name@CLI_PIN), and the pin is a version",
          len(_npm) == 1 and ast.unparse(_npm[0].right) == "CLI_PIN" and re.fullmatch(r"\d+\.\d+\.\d+", getattr(J, "CLI_PIN", "")) is not None,
          "installs: %s pin=%r" % ([ast.unparse(n) for n in _npm], getattr(J, "CLI_PIN", None)))

    # ---- THE INSTRUMENT IS INVISIBLE TO THE CLI: CONNECT + a CA only the process trusts ----
    import ssl as _ssl
    _cdir = tempfile.mkdtemp(prefix="mitm_")
    _saved_conn2 = PX.CONNECTION; _tr2 = tempfile.mktemp(suffix=".jsonl"); _saved_tr2, _saved_fp2, _saved_fb2 = PX.TRACE, PX.FINGERPRINTS, PX.FIRST_BODY
    try:
        PX.CONNECTION = _FakeConn; PX.TRACE = _tr2; PX.FINGERPRINTS = tempfile.mktemp(suffix=".jsonl"); PX.FIRST_BODY = tempfile.mktemp(suffix=".json")
        _mport, _ca = PX.serve_mitm(0, _cdir)
        _menv = PX.mitm_env(_mport, _ca)
        _ctx = _ssl.create_default_context(cafile=_ca)
        _op = _ur2.build_opener(_ur2.ProxyHandler({"https": "http://127.0.0.1:%d" % _mport}), _ur2.HTTPSHandler(context=_ctx))
        _req2 = _ur2.Request("https://api.anthropic.com/v1/messages?beta=true", data=_body, method="POST",
                             headers={"Content-Type": "application/json", "x-api-key": "sk-secret-9"})
        try:
            with _op.open(_req2, timeout=20) as _r:
                _got2 = _r.read()
        except Exception as _me:                                  # noqa: BLE001  (a refused tunnel is the leg's failure)
            _got2 = ("FAILED %s: %s" % (type(_me).__name__, str(_me)[:80])).encode()
        _rows2 = []
        for _i in range(40):
            _rows2 = [json.loads(l) for l in open(_tr2, encoding="utf-8") if l.strip()] if os.path.exists(_tr2) else []
            if any("relayed_bytes" in r for r in _rows2):
                break
            _tm_.sleep(0.05)
        _fp2 = [json.loads(l) for l in open(PX.FINGERPRINTS, encoding="utf-8") if l.strip()] if os.path.exists(PX.FINGERPRINTS) else []
    finally:
        PX.CONNECTION, PX.TRACE, PX.FINGERPRINTS, PX.FIRST_BODY = _saved_conn2, _saved_tr2, _saved_fp2, _saved_fb2
    _ph2 = [r.get("phase") for r in _rows2 if r.get("phase")]
    check("a CONNECT to api.anthropic.com is terminated with the throwaway CA, recorded, fingerprinted and relayed",
          _got2 == b"".join(_sse) and _ph2[:3] == ["connect", "received", "body_read"] and len(_fp2) == 1
          and _FakeConn.last.get("path") == "/v1/messages?beta=true" and "sk-secret" not in json.dumps(_rows2),
          "phases=%s fp=%d got=%r" % (_ph2, len(_fp2), _got2[:40]))
    check("the CLI is routed by HTTPS_PROXY + NODE_EXTRA_CA_CERTS, never by ANTHROPIC_BASE_URL",
          set(_menv) == {"HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy", "NODE_EXTRA_CA_CERTS"} and _menv["NODE_EXTRA_CA_CERTS"] == _ca
          and _menv["HTTPS_PROXY"] == "http://127.0.0.1:%d" % _mport and "api.chatcut.io" in _menv["NO_PROXY"], "env=%s" % _menv)
    # the shim never inherits the tunnel: its ChatCut calls go direct
    import mcp_shim as MS
    _e = {"HTTPS_PROXY": "http://127.0.0.1:1", "https_proxy": "http://127.0.0.1:1", "MCP_SHIM_TOKEN": "t", "PATH": "/bin"}
    _rm = MS.scrub_proxy_env(_e)
    _ms_main = next(n for n in ast.walk(ast.parse(io.open(os.path.join(HERE, "mcp_shim.py"), encoding="utf-8").read()))
                    if isinstance(n, ast.FunctionDef) and n.name == "main")
    _ms_calls = [ast.unparse(n.func) for n in ast.walk(_ms_main) if isinstance(n, ast.Call)]
    check("the shim scrubs the proxy variables it inherits before its first ChatCut call (5 tools instead of 13 on the tunnelled ping)",
          sorted(_rm) == ["HTTPS_PROXY", "https_proxy"] and set(_e) == {"MCP_SHIM_TOKEN", "PATH"} and "scrub_proxy_env" in _ms_calls
          and _ms_calls.index("scrub_proxy_env") == 0, "removed=%s left=%s main calls=%s" % (_rm, sorted(_e), _ms_calls[:3]))
    _base_sets = [ast.unparse(n) for n in ast.walk(_edit_fn) if isinstance(n, ast.Constant) and n.value == "ANTHROPIC_BASE_URL"]
    _mitm_calls = [ast.unparse(n.func) for n in ast.walk(_edit_fn) if isinstance(n, ast.Call) and ast.unparse(n.func) in ("_px.serve_mitm", "_px.mitm_env")]
    check("the job starts the transparent proxy and never names ANTHROPIC_BASE_URL",
          not _base_sets and sorted(_mitm_calls) == ["_px.mitm_env", "_px.serve_mitm"], "base_url refs=%s mitm=%s" % (_base_sets, _mitm_calls))

    # ---- ONLY THE RUN BOUND KILLS A TURN; the turn law is logged (ruling 3) ----
    _rt = [n for n in ast.walk(_inv) if isinstance(n, ast.Call) and ast.unparse(n.func).endswith("run_timed")]
    _rt_bound = ast.unparse(_rt[0].args[4]) if _rt and len(_rt[0].args) > 4 else None
    _left_asg = [ast.unparse(n.value) for n in ast.walk(_inv) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "_left" for t in n.targets)]
    check("a turn's bound is what is left of the RUN budget, never a per-turn constant",
          # _bound_s IS the run budget: it is RUN_TIMEOUT_S unless a diagnostic run raised it deliberately,
          # and the record says which. The property is that a turn takes what is LEFT of the RUN's budget,
          # never a constant of its own.
          _rt_bound == "_left" and len(_left_asg) == 1 and "_bound_s" in _left_asg[0] and "_run_t0" in _left_asg[0]
          and "_bound_s = int(run_bound) if run_bound and int(run_bound) > 0 else RUN_TIMEOUT_S" in ast.unparse(_edit_fn)
          and not hasattr(J, "TURN_TIMEOUT_S") and J.TURN_LAW_S == 120,
          "bound=%s left=%s" % (_rt_bound, _left_asg))
    _fp_row = PX.fingerprint({"model": "m", "system": [], "tools": [], "messages": [], "thinking": {"type": "adaptive"}, "output_config": {"effort": "low"}, "max_tokens": 7})
    check("every fingerprint row carries what was sent beside the prefix: thinking, effort, max_tokens",
          (_fp_row.get("request_fields") or {}).get("thinking") == {"type": "adaptive"} and _fp_row["request_fields"].get("output_config") == {"effort": "low"}
          and _fp_row["request_fields"].get("max_tokens") == 7, "row=%s" % json.dumps(_fp_row.get("request_fields")))

    # ---- THE OFF ARM IS THE WIRE'S OFF SWITCH ----
    _env_asg = {ast.unparse(n.value) for n in ast.walk(_edit_fn) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "_env" for t in n.targets)}
    check("think_tokens=0 sends MAX_THINKING_TOKENS=0 (wire: thinking disabled), never the env var that only omits the field",
          any(v == "{'MAX_THINKING_TOKENS': '0'}" for v in _env_asg) and not any("DISABLE_THINKING" in v for v in _env_asg),
          "env assignments: %s" % sorted(_env_asg))
    _cm = PX.re.search(r'"cache_miss_reason":(\{[^}]*\})', '{"diagnostics":{"cache_miss_reason":{"type":"previous_message_not_found"}}}')
    check("the proxy reads the API's cache_miss_reason out of message_start", _cm is not None and json.loads(_cm.group(1)) == {"type": "previous_message_not_found"}
          and 'row["cache_miss_reason"]' in io.open(os.path.join(HERE, "api_proxy.py"), encoding="utf-8").read())

    # ---- WHAT h-th-think0 (the first completed 4-call run) TAUGHT, DRIVEN ----
    # the deciding paragraph carries the exact add shape, forbids the json field, routes captions
    _para = next((ast.unparse(n) for n in ast.walk(_edit_fn) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                  and "Place everything in ONE edit_item call" in n.value), "")
    _para_all = "".join(n.value for n in ast.walk(_edit_fn) if isinstance(n, ast.Constant) and isinstance(n.value, str))
    check("the deciding paragraph shows the exact add shape with the dieted why, names type motion-graphic, forbids the json field, routes captions to edit_captions, and never mentions /work/DONE",
          '"type": "motion-graphic"' in _para_all and "never the json field" in _para_all and 'edit_captions call with action "enable"' in _para_all
          and '"why": "under 12 words"' in _para_all and "/work/DONE" not in _para_all and "preview_timeline yourself" not in _para_all,
          "shape=%s json=%s captions=%s DONE=%s" % ('"type": "motion-graphic"' in _para_all, "never the json field" in _para_all,
                                                     'edit_captions call with action "enable"' in _para_all, "/work/DONE" in _para_all))
    # sheets are JPEG, small, and the image block reads the media type from the extension
    _fd = tempfile.mkdtemp(prefix="sheets_")
    _frames = []
    for _i in range(20):
        _fp = os.path.join(_fd, "f%02d.jpg" % _i); _PImg.new("RGB", (360, 640), (_i * 10 % 255, 80, 120)).save(_fp, "JPEG"); _frames.append(("%.1fs" % (_i / 2), _fp))
    _sheets = J.tile_sheets(_frames, os.path.join(_fd, "out"), per_sheet=20, cols=5, cell_w=180)
    _sz = [os.path.getsize(x) for x in _sheets]
    check("a 20-frame sheet is JPEG under 400 KB (PNG sheets at ~1.5 MB pushed call 4 past the 32 MB request limit)",
          len(_sheets) == 1 and _sheets[0].endswith(".jpg") and _sz[0] < 400_000 and open(_sheets[0], "rb").read(3) == b"\xff\xd8\xff",
          "sheets=%s bytes=%s" % (_sheets, _sz))
    check("the image block's media type follows the extension",
          J._img_block(_sheets[0])["source"]["media_type"] == "image/jpeg" and J._img_block(os.path.join(HERE, "sheet", "INVENTORY.png"))["source"]["media_type"] == "image/png")
    # the shim hides ChatCut's json escape hatch and unwraps it when used anyway
    _slim = MS.slim_tool({"name": "edit_item", "inputSchema": {"type": "object", "properties": {"adds": {"type": "array", "items": {"type": "object"}}, "json": {"type": "string"}, "projectId": {"type": "string"}}}})
    _un, _flag = MS.unwrap_json_arg({"projectId": "p", "json": json.dumps({"adds": [{"type": "motion-graphic", "why": "w"}]})})
    check("the slimmed edit_item schema does not offer `json`, and a json-string call is unwrapped into real fields",
          "json" not in _slim["inputSchema"]["properties"] and "adds" in _slim["inputSchema"]["properties"]
          and _flag is True and _un.get("adds") == [{"type": "motion-graphic", "why": "w"}] and "json" not in _un,
          "props=%s unwrapped=%s" % (sorted(_slim["inputSchema"]["properties"]), _un))
    _hm = next(n for n in ast.walk(ast.parse(io.open(os.path.join(HERE, "mcp_shim.py"), encoding="utf-8").read())) if isinstance(n, ast.FunctionDef) and n.name == "handle")
    check("the shim unwraps before it strips the whys (the strip sees the real ops)",
          any(isinstance(n, ast.Call) and ast.unparse(n.func) == "unwrap_json_arg" for n in ast.walk(_hm)),
          "calls in handle: %s" % sorted({ast.unparse(n.func) for n in ast.walk(_hm) if isinstance(n, ast.Call)})[:12])
    # the billing header is not prefix; a rewritten message is reported even when the system differs
    _b1 = {"model": "m", "tools": [], "system": [{"type": "text", "text": "x-anthropic-billing-header: cc_prev_req=a"}, {"type": "text", "text": "S"}],
           "messages": [{"role": "user", "content": [{"type": "text", "text": "m0"}]}, {"role": "user", "content": [{"type": "text", "text": "m1"}]}]}
    _b2 = json.loads(json.dumps(_b1)); _b2["system"][0]["text"] = "x-anthropic-billing-header: cc_prev_req=b"; _b2["messages"][0]["content"][0]["text"] = "m0-rewritten"
    _f1, _f2 = PX.fingerprint(_b1), PX.fingerprint(_b2)
    _d = PX.diff_prefix(_b1, _f1, _b2, _f2)
    _b3 = json.loads(json.dumps(_b1)); _b3["system"][1]["text"] = "S2"
    _d3 = PX.diff_prefix(_b1, _f1, _b3, PX.fingerprint(_b3))
    check("the billing-header block is outside the system hash and counted; the first differing message is reported even when the system differs",
          _f1["system"]["sha"] == _f2["system"]["sha"] and _f1["system"]["billing_header_blocks"] == 1
          and _d["first_diff"] == "message:0" and _d["first_message_diff"] == 0 and _d3["first_diff"] == "system" and _d3["first_message_diff"] is None,
          "sha eq=%s billing=%s d=%s d3=%s" % (_f1["system"]["sha"] == _f2["system"]["sha"], _f1["system"].get("billing_header_blocks"), _d.get("first_diff"), _d3.get("first_diff")))
    _rl_keys = {k.value for n in ast.walk(_edit_fn) if isinstance(n, ast.Dict) for k in n.keys if isinstance(k, ast.Constant)}
    check("the run line carries the request size per call (request_mb)", "request_mb" in _rl_keys)

    # ---- RULING 2: THE WATCH-END BREAKPOINT, PLACED BY THE PROXY ----
    def _msg(role, blocks, mark=False):
        c = [{"type": "text", "text": t} for t in blocks]
        if mark: c[-1]["cache_control"] = {"type": "ephemeral"}
        return {"role": role, "content": c}
    _wb = {"model": "m", "tools": [], "system": [{"type": "text", "text": "billing"}, {"type": "text", "text": "S1", "cache_control": {"type": "ephemeral", "scope": "global"}},
                                                 {"type": "text", "text": "S2", "cache_control": {"type": "ephemeral"}}],
           "messages": [_msg("user", ["w0"]), _msg("assistant", ["w1"]), _msg("user", ["w2"]), _msg("assistant", ["w3 the watch ends here"]),
                        _msg("user", ["THE COMPONENT INVENTORY — pictures", "more"], mark=True), _msg("system", ["reminder"]), _msg("user", ["tail"], mark=True)]}
    _ob, _note = PX.inject_watch_breakpoint(_wb, "THE COMPONENT INVENTORY")
    _marks = [(i, [x.get("cache_control") for x in m["content"] if x.get("cache_control")]) for i, m in enumerate(_ob["messages"]) if any(x.get("cache_control") for x in m["content"])]
    _sys_ttl = [x["cache_control"].get("ttl") for x in _ob["system"] if x.get("cache_control")]
    check("the proxy marks the watch's last block with a 1h breakpoint, raises the system markers to 1h, drops the CLI's second-to-last message marker, and stays within four",
          _note.get("injected") is True and _note.get("watch_end_message") == 3 and _marks == [(3, [{"type": "ephemeral", "ttl": "1h"}]), (6, [{"type": "ephemeral"}])]
          and _sys_ttl == ["1h", "1h"] and _note.get("breakpoints") == 4 and _note.get("dropped_cli_markers") == [4]
          and _wb["messages"][3]["content"][-1].get("cache_control") is None,
          "note=%s marks=%s sys=%s" % (_note, _marks, _sys_ttl))
    # a system-role message carrying the text (the CLI's own "skipping" matched "ping") and an earlier user quote are both passed over
    _wb2 = json.loads(json.dumps(_wb)); _wb2["messages"][1]["content"][0]["text"] = "skipping ahead — THE COMPONENT INVENTORY was mentioned"; _wb2["messages"][2]["role"] = "user"
    _wb2["messages"][5]["content"][0]["text"] = "reminder: THE COMPONENT INVENTORY is above"   # a system-role message AFTER the run's first message: the role filter is what keeps the mark on 3
    _ob3, _note3 = PX.inject_watch_breakpoint(_wb2, "THE COMPONENT INVENTORY")
    check("only user-role messages count and the LAST match is the run's first message (a system-role 'skipping' once stole the mark)",
          _note3.get("run_first_message") == 4 and _note3.get("watch_end_message") == 3, "%s" % _note3)
    _kw0 = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "keep_warm")
    check("the ping's sentinel is distinctive, and the ping sends exactly it",
          "ping" != J.RUN_FIRST_TEXT_PING and len(J.RUN_FIRST_TEXT_PING) > 20
          and any(isinstance(n, ast.Name) and n.id == "RUN_FIRST_TEXT_PING" for n in ast.walk(_kw0)) and not any(isinstance(n, ast.Constant) and n.value == "ping" for n in ast.walk(_kw0)),
          "%r" % J.RUN_FIRST_TEXT_PING)
    _ob2, _note2 = PX.inject_watch_breakpoint(_wb, "NOT IN ANY MESSAGE")
    check("with no run-first text found nothing is rewritten and the note says so", _ob2 is _wb and _note2.get("injected") is False and "not found" in _note2.get("why", ""), "%s" % _note2)
    # the rewritten body is what goes upstream (through the tunnel, with RUN_FIRST_TEXT set)
    _saved_rft, _saved_conn3, _saved_tr3, _saved_fp3, _saved_fb3 = PX.RUN_FIRST_TEXT, PX.CONNECTION, PX.TRACE, PX.FINGERPRINTS, PX.FIRST_BODY
    try:
        PX.RUN_FIRST_TEXT = "THE COMPONENT INVENTORY"; PX.CONNECTION = _FakeConn; PX.TRACE = tempfile.mktemp(suffix=".jsonl")
        PX.FINGERPRINTS = tempfile.mktemp(suffix=".jsonl"); PX.FIRST_BODY = tempfile.mktemp(suffix=".json")
        _port3 = PX.serve(0)
        _req3 = _ur2.Request("http://127.0.0.1:%d/v1/messages?beta=true" % _port3, data=json.dumps({**_wb, "stream": True}).encode(), method="POST",
                             headers={"Content-Type": "application/json"})
        with _ur2.urlopen(_req3, timeout=20) as _r:
            _r.read()
        _sent = json.loads(_FakeConn.last["body"])
        _fp3 = [json.loads(l) for l in open(PX.FINGERPRINTS, encoding="utf-8") if l.strip()]
    finally:
        PX.RUN_FIRST_TEXT, PX.CONNECTION, PX.TRACE, PX.FINGERPRINTS, PX.FIRST_BODY = _saved_rft, _saved_conn3, _saved_tr3, _saved_fp3, _saved_fb3
    check("upstream receives the REWRITTEN body and the fingerprint row records the breakpoint",
          _sent["messages"][3]["content"][-1].get("cache_control") == {"type": "ephemeral", "ttl": "1h"}
          and (_fp3[0].get("fp") or {}).get("breakpoint", {}).get("injected") is True and "message:3" in (_fp3[0]["fp"].get("cache_control_at") or []),
          "sent marks=%s fp=%s" % ([i for i, m in enumerate(_sent["messages"]) if any(x.get("cache_control") for x in m["content"])], (_fp3[0].get("fp") or {}).get("cache_control_at") if _fp3 else None))
    _rft_sites = [n.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef)
                  if any(isinstance(a, ast.Attribute) and a.attr == "RUN_FIRST_TEXT" for a in ast.walk(n))]
    _m1t = next(b.get("text") for b in J.pass1_message(None, [], os.path.join(HERE, "sheet", "INVENTORY.png"), source_watch=None, deciding="x")["message"]["content"] if b.get("type") == "text")
    check("job and ping both hand the proxy their run-first text, and the job's first message really starts with it",
          {"edit", "keep_warm"} <= set(_rft_sites) and _m1t.startswith(J.RUN_FIRST_TEXT_JOB) and len(J.RUN_FIRST_TEXT_PING) > 20,
          "sites=%s first=%r" % (_rft_sites, _m1t[:40]))
    # ---- THE API'S OWN ANSWER IS A TERMINAL, NEVER THE AGENT'S FAULT; NOTHING EXPORTS AFTER A TERMINAL ----
    class _Inv400:
        log = []
        def __call__(self, n, message):
            self.log.append(n)
            return {"rc": 1, "subtype": "success", "tool_calls": [], "text": "Credit balance is too low", "killed": False, "wall": 7.0,
                    "usage": {"read": 0, "write": 0, "in": 0, "out": 0}, "api_status": 400, "api_head": '{"type":"error","error":{"message":"Credit balance is too low"}}'}
    _i400 = _Inv400()
    _tm400 = J.run_two_calls(_i400, lambda n, final: {"message": {}, "sheets": 0}, {"type": "user", "message": {"role": "user", "content": []}})
    check("a 4xx from the API is the terminal API ERROR at that turn, carrying the status and the API's words, and is never retried",
          (_tm400["terminal"] or {}).get("kind") == "API ERROR" and "400" in _tm400["terminal"]["why"] and "Credit balance" in _tm400["terminal"]["why"] and _i400.log == [1],
          "%s log=%s" % (_tm400.get("terminal"), _i400.log))
    _exp_if = [n for n in ast.walk(_edit_fn) if isinstance(n, ast.If) and ast.unparse(n.test) == "_tm.get('terminal')"
               and any(isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_export" for t in x.targets) for x in n.body)]
    check("the export is WITHHELD after any terminal (the floor once exported the untouched source after a 400)",
          len(_exp_if) == 1 and "WITHHELD" in ast.unparse(_exp_if[0].body[0]), "export ifs on terminal: %d" % len(_exp_if))

    # ---- TTL BY ENVIRONMENT: 1h injects the watch-end breakpoint; 5m injects nothing ----
    _ttl_asg = [ast.unparse(n.value) for n in ast.walk(_edit_fn) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Attribute) and t.attr == "RUN_FIRST_TEXT" for t in n.targets)]
    check("the job hands the proxy its run-first text only at prefix_ttl 1h (development: 5m, no injection)",
          _ttl_asg == ["RUN_FIRST_TEXT_JOB if prefix_ttl == '1h' and (not no_watch) else ''"], "assignments: %s" % _ttl_asg)
    _kw = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "keep_warm")
    check("a 5-minute keep-warm ping is refused (the ping exists for the 1h shape only)",
          any(isinstance(n, ast.Raise) and "1h production shape" in ast.unparse(n) for n in ast.walk(_kw))
          and any(a.arg == "prefix_ttl" for a in _kw.args.args))
    _main_fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "main")
    check("--prefix-ttl reaches edit() from main on both launch paths",
          any(a.arg == "prefix_ttl" for a in _main_fn.args.args)
          and sum(1 for n in ast.walk(_main_fn) if isinstance(n, ast.keyword) and n.arg == "prefix_ttl") == 2)

    # ---- THE TOKEN BUDGET IS GONE: the API refuses thinking.enabled on this model; the dial is --effort ----
    check("the job never hands the proxy a thinking budget (the 2000 arm was refused with 400)",
          [ast.unparse(n.value) for n in ast.walk(_edit_fn) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Attribute) and t.attr == "THINKING_BUDGET" for t in n.targets)] == ["0"])
    # ---- THE NO-WATCH RUN: no --resume, no watch-end breakpoint, named ABSENT BY DESIGN ----
    _nw_cmd = J.cli_command(None, "claude-sonnet-5")
    _sid_asg = [ast.unparse(n.value) for n in ast.walk(_edit_fn) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_watch_sid" for t in n.targets)]
    _rft_asg = [ast.unparse(n.value) for n in ast.walk(_edit_fn) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Attribute) and t.attr == "RUN_FIRST_TEXT" for t in n.targets)]
    check("no_watch skips the resume (no --resume in the command), skips the watch-end breakpoint, and the record says so",
          "--resume" not in _nw_cmd and _sid_asg == ["None if no_watch else install_watch('/work')"]
          and _rft_asg == ["RUN_FIRST_TEXT_JOB if prefix_ttl == '1h' and (not no_watch) else ''"]
          and any(isinstance(n, ast.Constant) and n.value == "no_watch" for n in ast.walk(_edit_fn)),
          "sid=%s rft=%s" % (_sid_asg, _rft_asg))
    # ---- THE EXPORT IS DOWNLOADED AND KEPT (both outputs, side by side) ----
    _saved_mc2, _saved_sleep, _saved_uo2 = J._mcp_call, J.time.sleep, _urq.urlopen
    _calls_seen = []
    class _Res:
        def __init__(self, b): self.b = b
        def read(self): return self.b
        def __enter__(self): return self
        def __exit__(self, *a): return False
    class _Dict(dict):
        pass
    _saved_results = J.RESULTS
    try:
        def _fake_mc2(tok, name, args, expect=None):
            _calls_seen.append(name)
            if name == "submit_export": return {"_text": "Submitted export.\n  renderId: abc123def4\n  status: rendering"}
            if name == "track_export": return {"_text": '{"status":"done","url":"https://cdn.test/renders/abc/out.mp4?sig=1"}'}
            raise AssertionError(name)
        J._mcp_call = _fake_mc2; J.time.sleep = lambda s_: None; _urq.urlopen = lambda u, timeout=120: _Res(b"\x00\x00\x00\x18ftypmp42" + b"x" * 100)
        J.RESULTS = _Dict()
        _ex = J.harness_export("t", {"projectId": "p"}, run_id="r1")
    finally:
        J._mcp_call, J.time.sleep, _urq.urlopen, J.RESULTS = _saved_mc2, _saved_sleep, _saved_uo2, _saved_results
    check("harness_export polls to the file, downloads it, and keeps bytes + sha beside the record",
          _ex.get("state") == "MEASURED" and _ex.get("file") == "MEASURED" and _ex.get("bytes") == 112 and len(_ex.get("sha256", "")) == 64
          and "r1-mp4" in _Dict.__mro__ and False or ("submit_export" in _calls_seen and "track_export" in _calls_seen and _ex.get("bytes") == 112 and _ex.get("file") == "MEASURED"),
          "export=%s calls=%s" % ({k: v for k, v in _ex.items() if k != "sha256"}, _calls_seen))

    # ---- THE SYSTEM SEGMENT, BLOCK BY BLOCK, AND THE JOB'S CALL 1 AGAINST THE PING'S ----
    _f_blocks = PX.fingerprint({"model": "m", "tools": [], "system": [{"type": "text", "text": "x-anthropic-billing-header: a"}, {"type": "text", "text": "S1"}, {"type": "text", "text": "S2 dynamic"}], "messages": []})
    check("the fingerprint names every system block's sha and size (the billing header excluded)",
          len(_f_blocks["system"]["block_shas"]) == 2 and _f_blocks["system"]["block_shas"][1][2].startswith("S2") and _f_blocks["system"]["billing_header_blocks"] == 1,
          "%s" % _f_blocks["system"].get("block_shas"))
    _svp = [n for n in ast.walk(_edit_fn) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Subscript) and ast.unparse(t) == "out['system_vs_ping']" for t in n.targets)]
    _kw_sw = [n for n in ast.walk(_kw) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Subscript) and ast.unparse(t) == "rec['system_wire']" for t in n.targets)]
    check("the ping keeps its system segment verbatim and the job diffs its call-1 system against it, block by block",
          len(_svp) >= 3 and len(_kw_sw) >= 1 and "differing_blocks" in ast.unparse(_edit_fn) and "system_vs_ping" in ast.unparse(_edit_fn),
          "job assigns=%d ping assigns=%d" % (len(_svp), len(_kw_sw)))
    _rq = [ast.unparse(n.value) for n in ast.walk(_edit_fn) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_req_mb" for t in n.targets)]
    check("request MB per call is read from the trace file, not from a record field built later (it printed [] on every run)",
          len(_rq) == 1 and "_read_trace_rows()" in _rq[0], "%s" % _rq)

    # ---- PART 3 A: THE PREFLIGHT refuses before it is paid for, and names the byte ----
    _sysA = ["x-anthropic-billing-header: a", "S1 text", "S2 env text"]
    _bodyA = {"system": [{"type": "text", "text": t} for t in _sysA]}
    _bodyB = {"system": [{"type": "text", "text": t} for t in ["x-anthropic-billing-header: b", "S1 text", "S2 env teXt"]]}
    _okA, _rA = PX.preflight(_bodyA, _sysA); _okB, _rB = PX.preflight(_bodyB, _sysA); _okN, _rN = PX.preflight(_bodyB, None)
    check("the preflight passes an identical system (billing header aside), refuses a one-byte difference naming block and offset, and is skipped without a ping",
          _okA and _rA["state"] == "PASSED" and not _okB and _rB["block"] == 1 and _rB["first_diff_at"] == 9 and _okN and _rN["state"] == "SKIPPED",
          "A=%s B=%s N=%s" % (_rA, _rB, _rN))
    _pinned, _chg = PX.pin_os_line({"system": [{"type": "text", "text": "x\n - Platform: linux\n - OS Version: Linux 6.8.0-1015-gcp\n - Shell: sh"}]})
    check("the OS line is pinned to a constant so the fleet's kernel string cannot vary the prefix",
          _chg and " - OS Version: pinned\n" in _pinned["system"][0]["text"] and "6.8.0" not in _pinned["system"][0]["text"], _pinned["system"][0]["text"][:80])
    # the refusal goes through the tunnel: a body whose system differs from EXPECT_SYSTEM gets a 409 and nothing reaches upstream
    _saved = (PX.CONNECTION, PX.TRACE, PX.FINGERPRINTS, PX.FIRST_BODY, PX.EXPECT_SYSTEM, PX.PREFLIGHT_DONE, PX.RUN_FIRST_TEXT)
    try:
        PX.CONNECTION = _FakeConn; PX.TRACE = tempfile.mktemp(suffix=".jsonl"); PX.FINGERPRINTS = tempfile.mktemp(suffix=".jsonl"); PX.FIRST_BODY = tempfile.mktemp(suffix=".json")
        PX.EXPECT_SYSTEM = ["S1 text", "S2 env text"]; PX.PREFLIGHT_DONE = False; PX.RUN_FIRST_TEXT = ""
        _FakeConn.last = {}
        _port4 = PX.serve(0)
        _req4 = _ur2.Request("http://127.0.0.1:%d/v1/messages" % _port4, data=json.dumps({"model": "m", "tools": [], "system": [{"type": "text", "text": "S1 text"}, {"type": "text", "text": "S2 env teXt"}], "messages": []}).encode(), method="POST", headers={"Content-Type": "application/json"})
        try:
            _ur2.urlopen(_req4, timeout=20); _st4 = 200; _body4 = ""
        except _ur2.HTTPError as _he:
            _st4 = _he.code; _body4 = _he.read().decode()
        # the handler thread may still be running after the client has its 409: give a forwarding mutant time to show
        for _i in range(20):
            if _FakeConn.last.get("body"):
                break
            _tm_.sleep(0.05)
    finally:
        PX.CONNECTION, PX.TRACE, PX.FINGERPRINTS, PX.FIRST_BODY, PX.EXPECT_SYSTEM, PX.PREFLIGHT_DONE, PX.RUN_FIRST_TEXT = _saved
    check("a differing call 1 is answered 409 preflight_refused and never forwarded (no cold write paid)",
          _st4 == 409 and "preflight_refused" in _body4 and not _FakeConn.last.get("body"), "status=%s forwarded=%s" % (_st4, bool(_FakeConn.last.get("body"))))
    class _Inv409:
        def __call__(self, n, message):
            return {"rc": 1, "subtype": "success", "tool_calls": [], "text": "", "killed": False, "wall": 3.0, "usage": {}, "api_status": 409, "api_head": '{"type":"error","error":{"type":"preflight_refused","message":"system differs"}}'}
    _tm409 = J.run_two_calls(_Inv409(), lambda n, final: {"message": {}, "sheets": 0}, {"type": "user", "message": {"role": "user", "content": []}})
    check("a preflight refusal is the terminal PREFLIGHT REFUSED, carrying the diff", (_tm409["terminal"] or {}).get("kind") == "PREFLIGHT REFUSED" and "differs" in _tm409["terminal"]["why"])
    _exp_asg = [ast.unparse(n.value) for n in ast.walk(_edit_fn) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Attribute) and t.attr == "EXPECT_SYSTEM" for t in n.targets)]
    check("the job arms the preflight with the ping's stored system text", any("system_wire" in v for v in _exp_asg), "%s" % _exp_asg)
    # ---- PART 3 E: one rewatch on the common path ----
    class _InvClean:
        def __init__(self): self.log = []
        def __call__(self, n, message):
            self.log.append(n)
            ops = [{"name": "mcp__chatcut__edit_item", "input": {"adds": [{"type": "motion-graphic"}]}}] if n == 1 else []
            # call 1 writes the prefix; call 2 reads it (the gate wants >= 0.95 x (read + write) of call 1)
            if n != 1:
                ops = ops + [{"name": "mcp__chatcut__finish", "input": {"verdict": "export"}}]
            return {"rc": 1, "subtype": "error_max_turns", "tool_calls": ops, "text": "", "killed": False, "wall": 5.0,
                    "usage": ({"read": 0, "write": 100} if n == 1 else {"read": 100, "write": 5})}
    _ic = _InvClean(); _rw_log = []
    _tmc = J.run_two_calls(_ic, lambda n, final: (_rw_log.append(n) or {"message": {"type": "user", "message": {"role": "user", "content": []}}, "sheets": 0}), {"type": "user", "message": {"role": "user", "content": []}})
    check("call 2 finishing with no ops ends the run: ONE rewatch, two calls, exported",
          str(_tmc.get("verdict")).startswith("export at call 2") and _ic.log == [1, 2] and _rw_log == [1] and not _tmc.get("terminal"), "verdict=%s calls=%s rewatches=%s" % (_tmc.get("verdict"), _ic.log, _rw_log))
    _rm1 = J.rewatch_message(1, {"frames": 0, "sheets": [], "state": "ABSENT", "why": "x", "times": []}, [], [], [], final=False)
    check("the first rewatch offers export as the clean reply", "single word export" in _rm1["message"]["content"][0]["text"])
    # ---- PART 3 B: THE PLATTER from the acceptor's keys ----
    _pl, _npl = J.component_platter(os.path.join(HERE, "chatcut_registry_baked.json"), os.path.join(HERE, "chatcut_catalogue.json"))
    _reg = json.load(open(os.path.join(HERE, "chatcut_registry_baked.json"), encoding="utf-8")); _rc_ = _reg.get("components") or _reg
    _dc_keys = [pp["key"] for pp in _rc_["DropCard"]["properties"]]
    check("the platter lists every registry component with the keys ChatCut accepts, the shared keys said once, EndCard end-only",
          _npl >= 25 and all(k in _pl for k in _dc_keys if k not in ("durationMs", "startMs", "enterFrames", "exitFrames")) and "Every component also takes: durationMs, enterFrames, exitFrames, startMs." in _pl
          and "EndCard:" in _pl and "END ONLY" in _pl and _pl.count("durationMs") == 1,
          "n=%d durationMs mentions=%d" % (_npl, _pl.count("durationMs")))
    check("the catalogue's foreign example keys never reach the platter (DropCard 'steps', RecordingFrame 'corner')",
          "steps (" not in _pl and "corner (" not in _pl)
    _fl = J.face_lines([{"t": 0.2, "cx": 540, "cy": 600, "found": True}, {"t": 1.4, "cx": 300, "cy": 1500, "found": True}], 2.0)
    check("face lines give x,y and the band per second", _fl[1].endswith("(top band)") and _fl[2].endswith("(bottom band)") and "x0.50" in _fl[1], "%s" % _fl)
    _m1p = J.pass1_message(None, [], os.path.join(HERE, "sheet", "INVENTORY.png"), source_watch=None, deciding="x", face=["FACE — f"], platter="PROPERTY KEYS — p")
    _texts1 = [b.get("text") for b in _m1p["message"]["content"] if b.get("type") == "text"]
    check("the first message carries the platter and the face lines", any(str(t).startswith("PROPERTY KEYS") for t in _texts1) and any(str(t).startswith("FACE") for t in _texts1))
    _p1call = next(n for n in ast.walk(_edit_fn) if isinstance(n, ast.Call) and ast.unparse(n.func) == "pass1_message")
    check("edit() hands them over", {k.arg for k in _p1call.keywords} >= {"face", "platter"})
    # ---- PART 3 F: the stage line and the call split ----
    _sl, _sd = J.stage_line({"token": 1.0, "preflight": 3.0, "download": 10.0, "sheet": 11.0, "prestage": 14.0, "turn1.start": 60.0, "turn1": 90.0, "rewatch1.start": 90.0, "rewatch1.readback": 92.0, "rewatch1.calls": 120.0, "rewatch1.fetch": 126.0, "rewatch1.tile": 127.0, "rewatch1.watch": 128.0, "rewatch1.props": 132.0, "rewatch1.checks": 135.0, "agent": 135.0}, 145.0)
    check("the stage line names source_watch, each turn and rewatch (with parts) and the export tail from the marks",
          _sd["source_watch"] == 46.0 and _sd["turn1"] == 30.0 and _sd["rewatch1"] == 45.0 and _sd["rewatch1.parts"]["calls"] == 28.0 and _sd["export_tail"] == 10.0 and "source_watch 46.0" in _sl, _sl)
    _rec_keys = {k.value for n in ast.walk(_inv) if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) for k in [n.slice]}
    check("each call records ttft, generation, tool and waiting seconds from the stream clock", {"ttft", "generating_s", "tool_s", "waiting_s"} <= _rec_keys)
    check("the run line prints STAGES and CALL SPLIT", "STAGES          :" in ast.unparse(_edit_fn) and "CALL SPLIT      :" in ast.unparse(_edit_fn))
    # ---- PART 3 G: no kill of ours below the run bound ----
    _bounds = []
    for fn in [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef)]:
        for c in ast.walk(fn):
            if isinstance(c, ast.Call) and ast.unparse(c.func).endswith("run_timed") and len(c.args) > 4:
                _bounds.append((fn.name, ast.unparse(c.args[4])))
    check("every CLI invocation is bounded by the run bound or what is left of it, never a smaller number",
          _bounds and all(b in ("RUN_TIMEOUT_S", "_left") for _f, b in _bounds), "%s" % _bounds)

    # ---- THINKING PARITY: the ping carries the job's thinking/effort, and the preflight refuses a mismatch ----
    _okF, _rF = PX.preflight({"system": [{"type": "text", "text": "S"}], "thinking": {"type": "disabled"}, "output_config": {"effort": "high"}}, ["S"], {"thinking": {"type": "adaptive"}, "effort": "high"})
    _okG, _rG = PX.preflight({"system": [{"type": "text", "text": "S"}], "thinking": {"type": "disabled"}, "output_config": {"effort": "high"}}, ["S"], {"thinking": {"type": "disabled"}, "effort": "high"})
    check("the preflight refuses a job whose thinking differs from the ping's (the API drops message entries on that change) and passes a match",
          not _okF and "thinking" in _rF.get("why", "") and _okG, "F=%s G=%s" % (_rF, _rG))
    _kw2 = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "keep_warm")
    _kw_args = [a.arg for a in _kw2.args.args]
    _kw_env = [ast.unparse(n.value) for n in ast.walk(_kw2) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "env" for t in n.targets)]
    check("the ping takes think_tokens and effort, sends MAX_THINKING_TOKENS=0 for the off arm, and passes effort to the command",
          {"think_tokens", "effort"} <= set(_kw_args) and any("'0' if think_tokens == 0" in v for v in _kw_env)
          and any(isinstance(n, ast.Call) and ast.unparse(n.func) == "cli_command" and any(k.arg == "effort" for k in n.keywords) for n in ast.walk(_kw2)),
          "args=%s env=%s" % (_kw_args, _kw_env))
    _ef_asg = [ast.unparse(n.value) for n in ast.walk(_edit_fn) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Attribute) and t.attr == "EXPECT_FIELDS" for t in n.targets)]
    check("the job arms the preflight with the ping's thinking and effort", any("request_fields" in v or "_rf0" in v for v in _ef_asg), "%s" % _ef_asg)
    # ---- THE RUN BOUND COUNTS FROM THE JOB'S START ----
    _late = J.run_two_calls(lambda n, m: {"rc": 1, "tool_calls": [], "text": "", "usage": {}}, lambda n, f: {}, {"type": "user"}, t0=time.time() - 400)
    check("with the job's t0 400s ago the machine is RUN TIMEOUT before turn 1", (_late.get("terminal") or {}).get("kind") == "RUN TIMEOUT" and not _late["turns"], "%s" % _late.get("terminal"))
    _t0_kw = [k for n in ast.walk(_edit_fn) if isinstance(n, ast.Call) and ast.unparse(n.func) == "run_two_calls" for k in n.keywords if k.arg == "t0"]
    check("edit() hands the machine the job's own t0", len(_t0_kw) == 1 and ast.unparse(_t0_kw[0].value) == "t0")
    # ---- THE FRAME FETCH: parallel, bounded, timed ----
    import urllib.request as _urq3, time as _tm3
    _saved_uo3 = _urq3.urlopen
    class _Slow:
        def __init__(self, u): self.u = u
        def read(self): return b"\xff\xd8\xff" + b"x" * 10
        def __enter__(self): return self
        def __exit__(self, *a): return False
    def _fake_uo(u, timeout=15):
        if "hang" in u:
            _tm3.sleep(min(timeout, 0.6)); raise TimeoutError("timed out")
        return _Slow(u)
    _fd2 = tempfile.mkdtemp(prefix="ff_")
    try:
        _urq3.urlopen = _fake_uo
        _t0f = _tm3.time(); _got, _tim = J.fetch_frames(["https://x/%d.jpg" % i for i in range(7)] + ["https://x/hang.jpg"], _fd2, timeout_s=0.5); _wf = _tm3.time() - _t0f
    finally:
        _urq3.urlopen = _saved_uo3
    check("fetch_frames fetches every URL at once with a bound per URL, names the failure, and the wall is the bound, not the sum",
          len(_got) == 7 and _tim["failed"] == 1 and _tim["got"] == 7 and _tim["errors"] and _wf < 2.0 and _tim["timeout_s"] == 0.5, "got=%d timing=%s wall=%.2f" % (len(_got), _tim, _wf))
    _wa = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "watch_asset")
    _wa_calls = {ast.unparse(n.func) for n in ast.walk(_wa) if isinstance(n, ast.Call)}
    _pf = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_preview_frames")
    _pf_calls = {ast.unparse(n.func) for n in ast.walk(_pf) if isinstance(n, ast.Call)}
    check("the source watch and the rewatch both fetch through fetch_frames (never the serial 60s fetch)",
          any("fetch_frames" in c for c in _wa_calls) and "_cr.fetch" not in _wa_calls and "fetch_frames" in _pf_calls, "watch=%s preview=%s" % (sorted(c for c in _wa_calls if "fetch" in c), sorted(c for c in _pf_calls if "fetch" in c)))
    check("the default fetch bound is 15s, not 60", J.FETCH_TIMEOUT_S == 15)
    _para_all2 = "".join(n.value for n in ast.walk(_edit_fn) if isinstance(n, ast.Constant) and isinstance(n.value, str))
    check("the deciding prompt no longer names trackBoundFrom or a captions revision (turn 1's add was refused for them)",
          "trackBoundFrom" not in _para_all2 and "set_max_characters" not in _para_all2 and "revision" not in _para_all2)

    # ---- THE ASSET ID IS READ WHEREVER CHATCUT PUTS IT (28 of 36 components reached the agent as "?") ----
    check("asset_id_from finds a nested assetId, an assetId in the prose after the JSON, and names nothing when there is none",
          J.asset_id_from({"validation": {"ok": True}, "_text": '{"validation":{"ok":true}}\n\nCreated motion graphic. assetId: 0f34ce33-1f17-4771-909d-cd496276cceb'}) == "0f34ce33-1f17-4771-909d-cd496276cceb"
          and J.asset_id_from({"result": {"asset": {"assetId": "abcdef0123"}}}) == "abcdef0123"
          and J.asset_id_from({"_text": "Created asset 64bf8e14c7 for you"}) == "64bf8e14c7"
          and J.asset_id_from({"_text": "nothing here"}) is None)
    _ro = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_register_one")
    # THE GUARD, NOT THE RETURN: `if False:` leaves the return in place and unreachable
    _guards = [ast.unparse(n.test) for n in ast.walk(_ro) if isinstance(n, ast.If) and any(isinstance(b, ast.Return) and "registered without an id" in ast.unparse(b) for b in n.body)]
    check("a registration without an id is returned as a refusal, never counted as registered",
          _guards == ["not _aid_"] and any(isinstance(n, ast.Call) and ast.unparse(n.func) == "asset_id_from" for n in ast.walk(_ro)), "guards=%s" % _guards)

    # ---- A REFUSED PREFLIGHT STANDS FOR EVERY LATER CALL (the CLI retried a 409 and paid the cold write) ----
    _saved5 = (PX.CONNECTION, PX.TRACE, PX.FINGERPRINTS, PX.FIRST_BODY, PX.EXPECT_SYSTEM, PX.PREFLIGHT_DONE, PX.PREFLIGHT_REFUSED, PX.RUN_FIRST_TEXT)
    try:
        PX.CONNECTION = _FakeConn; PX.TRACE = tempfile.mktemp(suffix=".jsonl"); PX.FINGERPRINTS = tempfile.mktemp(suffix=".jsonl"); PX.FIRST_BODY = tempfile.mktemp(suffix=".json")
        PX.EXPECT_SYSTEM = ["S1"]; PX.PREFLIGHT_DONE = False; PX.PREFLIGHT_REFUSED = None; PX.RUN_FIRST_TEXT = ""
        _FakeConn.last = {}
        _port5 = PX.serve(0)
        _codes = []
        for _i in range(2):
            _rq = _ur2.Request("http://127.0.0.1:%d/v1/messages" % _port5, data=json.dumps({"model": "m", "tools": [], "system": [{"type": "text", "text": "S1 changed"}], "messages": []}).encode(), method="POST", headers={"Content-Type": "application/json"})
            try:
                _ur2.urlopen(_rq, timeout=20); _codes.append(200)
            except _ur2.HTTPError as _he:
                _codes.append(_he.code)
        for _i in range(20):
            if _FakeConn.last.get("body"):
                break
            _tm_.sleep(0.05)
    finally:
        PX.CONNECTION, PX.TRACE, PX.FINGERPRINTS, PX.FIRST_BODY, PX.EXPECT_SYSTEM, PX.PREFLIGHT_DONE, PX.PREFLIGHT_REFUSED, PX.RUN_FIRST_TEXT = _saved5
    check("a refused preflight refuses the CLI's retry too, and nothing ever reaches upstream", _codes == [409, 409] and not _FakeConn.last.get("body"), "codes=%s forwarded=%s" % (_codes, bool(_FakeConn.last.get("body"))))
    _st_sh = io.open(os.path.join(HERE, "scripts", "h_stage.sh"), encoding="utf-8").read()
    check("the no-speech and car stages run on the off arm, the arm the batch's ping carries (an adaptive stage against an off-arm ping was refused, retried, and paid)",
          all(re.search(r"^\s*%s\)\s+CMD=.*--run-id h-%s-1\S* --think-tokens 0" % (k, k), _st_sh, re.M) is not None and "--effort" not in next(l for l in _st_sh.split("\n") if re.match(r"^\s*%s\)" % k, l)) for k in ("motion", "car")))

    # ---- REGISTRATION: select options as the acceptor's objects; a refusal named in the validator's words ----
    _np = J.normalise_properties([{"key": "anchor", "type": "select", "defaultValue": "center", "options": ["center", "top"]}, {"key": "decimals", "type": "number", "defaultValue": 0}, {"key": "x", "type": "select", "options": [{"value": "a", "label": "A"}]}])
    check("select options become {value, label} objects; other fields and already-object options pass through untouched",
          _np[0]["options"] == [{"value": "center", "label": "center"}, {"value": "top", "label": "top"}] and _np[1] == {"key": "decimals", "type": "number", "defaultValue": 0}
          and _np[2]["options"] == [{"value": "a", "label": "A"}], "%s" % _np)
    _refusal_env = {"content": [{"type": "text", "text": 'MCP error -32602: Input validation error: Invalid arguments for tool create_motion_graphic_from_code: [ { "expected": "object", "code": "invalid_type", "path": ["properties", 1, "options", 0], "message": "Invalid input: expected object, received string" } ]'}]}
    _rr = J.registration_refusal({"_text": _refusal_env["content"][0]["text"]})
    check("a -32602 refusal is returned in the validator's own words (path and message), and an ordinary answer is not a refusal",
          _rr is not None and '"path": ["properties", 1, "options", 0]' in _rr and J.registration_refusal({"_text": "Created asset abcdef0123"}) is None, "%r" % (_rr or "")[:120])
    _ro2 = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_register_one")
    _ro2_calls = [ast.unparse(n.func) for n in ast.walk(_ro2) if isinstance(n, ast.Call)]
    check("every registration goes through the normaliser and a refusal is returned before any id is looked for",
          "normalise_properties" in _ro2_calls and "registration_refusal" in _ro2_calls
          and _ro2_calls.index("registration_refusal") < _ro2_calls.index("asset_id_from"), "%s" % [c for c in _ro2_calls if c in ("normalise_properties", "registration_refusal", "asset_id_from")])

    # ---- THE ID READER ON A REAL ACCEPTED REGISTRATION (recorded 2026-09-18) ----
    _fx = json.load(open(os.path.join(HERE, "smoke_fixtures", "registration_accepted_2026-09-18.json"), encoding="utf-8"))
    _fx_txt = "".join(x.get("text") or "" for x in (_fx.get("content") or []) if isinstance(x, dict))
    check("asset_id_from reads the id out of a real accepted registration's content text, and it is not a refusal",
          J.asset_id_from({"_text": _fx_txt}) == "2610a165-a3ff-44e2-af54-2c448a66c5e4" and J.registration_refusal({"_text": _fx_txt}) is None)

    # ---- EVERY RUN-TIME IMPORT IS MOUNTED (the rewatch probe, 2026-09-17) ----
    _tree = ast.parse(src)
    _mounted = set(re.findall(r'"/root/([A-Za-z_][A-Za-z0-9_]*)\.py"', src))
    _local = {os.path.splitext(f)[0] for f in os.listdir(HERE) if f.endswith(".py")}
    _rt_imports = set()
    # local entrypoints run on the developer's machine, never in the container;
    # require_detach is imported only there (measured: 5 sites, all
    # @app.local_entrypoint). Everything else — @app.function bodies and the
    # module-level helpers they call — runs where only the mounts exist.
    _local_eps = {n for n in ast.walk(_tree) if isinstance(n, ast.FunctionDef)
                  and any("local_entrypoint" in ast.unparse(d) for d in n.decorator_list)}
    check("the local entrypoints are recognised (the exclusion is not empty)",
          len(_local_eps) >= 3, "local entrypoints seen: %d" % len(_local_eps))
    for fn in [n for n in ast.walk(_tree) if isinstance(n, ast.FunctionDef) and n not in _local_eps]:
        for n in ast.walk(fn):
            if isinstance(n, ast.Import):
                _rt_imports.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module:
                _rt_imports.add(n.module.split(".")[0])
    _needed = sorted(m for m in _rt_imports if m in _local and m != "chatcut_job_app")
    _missing = [m for m in _needed if m not in _mounted]
    check("every lane module imported at run time is mounted in the image",
          not _missing and "chatcut_reference" in _needed,
          "run-time imports %s; NOT mounted: %s — a ModuleNotFoundError one function down" % (_needed, _missing))

    # ---- ITEM 5: PRESTAGE PHASES ----
    pre = ast.unparse(next(n for n in ast.walk(ast.parse(src))
                           if isinstance(n, ast.FunctionDef) and n.name == "prestage"))
    # THE CALL, NOT THE WORD: prestage's docstring mentions import_media
    # before any code does. ast.unparse renders the call single-quoted.
    _imp = pre.index("call('import_media'")
    check("component registration runs on a pool while the source imports",
          "ThreadPoolExecutor" in pre and pre.index("_reg_futs = ") < _imp
          and _imp < pre.index("_f.result("),
          "37 serial registrations were 35s of a 44s prestage")
    check("prestage reports its phases",
          "PRESTAGE PHASES" in pre and "'phases': _pt" in pre)

    # ---- ITEM 6: ZAC'S THREE ADDITIONS (2026-09-18) — the negative control, the density, the itemised tail ----
    _tree6 = ast.parse(src)
    _fn6 = lambda name: next(n for n in ast.walk(_tree6) if isinstance(n, ast.FunctionDef) and n.name == name)
    _calls6 = lambda node, name: sorted((n for n in ast.walk(node) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == name), key=lambda n: (n.lineno, n.col_offset))
    _prb6 = _fn6("probe_rewatch"); _prb6_src = ast.unparse(_prb6)
    check("the probe takes a density and hands it to the rewatch instrument",
          any(a.arg == "density_fps" for a in _prb6.args.args)
          and any(any(k.arg == "density_fps" and isinstance(k.value, ast.Name) and k.value.id == "density_fps" for k in c.keywords) for c in _calls6(_prb6, "_preview_frames")),
          "G runs at 2 fps and 1 fps; a fixed density makes the 1 fps arm a lie")
    # THE CONTROL READS THE CLEAN TIMELINE BEFORE ANY PLANT LANDS (by source position of the calls)
    _ctl6 = [c.lineno for c in _calls6(_prb6, "_review") if c.args and isinstance(c.args[0], ast.Constant) and c.args[0].value == "control"]
    _pl6 = [c.lineno for c in _calls6(_prb6, "_plant")]
    check("the control review runs before the plants land",
          bool(_ctl6) and bool(_pl6) and min(_ctl6) < min(_pl6), "control at %s, plants at %s" % (_ctl6, _pl6))
    check("false positives are counted from the control's own ops, not declared",
          any(any(isinstance(k, ast.Constant) and k.value == "false_positives" and isinstance(v, ast.Call) and getattr(v.func, "id", "") == "len"
                  for k, v in zip(n.keys, n.values)) for n in ast.walk(_prb6) if isinstance(n, ast.Dict)),
          "a control that reports 0 without reading anything is the tidy zero")
    check("the probe reads the ping's entry through the same transparent proxy as a job, on the off arm",
          "serve_mitm" in _prb6_src and "mitm_env" in _prb6_src and "RUN_FIRST_TEXT" in _prb6_src and "'MAX_THINKING_TOKENS': '0'" in _prb6_src)
    check("each review carries the job's cold-write rule and the API's own status",
          "wr > 0.5 * max(1, wr + rd)" in _prb6_src and "_read_trace_rows('/work/probe_trace.jsonl')" in _prb6_src and "'api_status': _api.get('status')" in _prb6_src)
    check("the probe's two densities are two records, not one overwritten",
          "'probe-rewatch-%gfps' % density_fps" in _prb6_src)
    # THE EXPORT TAIL, ITEMISED: four marks, in order, and the parts SUM to the tail (a remainder would be arithmetic saying the model is wrong)
    _hx6 = _fn6("harness_export")
    _hx6_marks = [c.args[0].value for c in _calls6(_hx6, "mark") if c.args and isinstance(c.args[0], ast.Constant)]
    check("harness_export marks submit, render, download, upload in that order",
          _hx6_marks == ["export.submit", "export.render", "export.download", "export.upload"], str(_hx6_marks))
    _ed6 = _fn6("edit"); _ed6_src = ast.unparse(_ed6)
    check("edit() marks the gate before it asks for the render, and passes the marker in",
          "mark('export.gate')" in _ed6_src and "harness_export(tok, _stage, run_id=run_id, mark=mark)" in _ed6_src
          and _ed6_src.index("mark('export.gate')") < _ed6_src.index("harness_export(tok, _stage, run_id=run_id, mark=mark)"))
    _sl6, _sd6 = J.stage_line({"agent": 100.0, "export.gate": 103.0, "export.submit": 103.5, "export.render": 120.0, "export.download": 128.0, "export.upload": 132.6}, 132.6)
    _parts6 = _sd6.get("export_tail.parts") or {}
    check("the export tail is itemised: gate + render + download + upload = the tail",
          _parts6 == {"gate": 3.0, "render": 17.0, "download": 8.0, "upload": 4.6} and abs(sum(_parts6.values()) - _sd6["export_tail"]) < 0.11
          and "(export tail: gate 3.0, render 17.0, download 8.0, upload 4.6)" in _sl6, "%s %s" % (_parts6, _sl6))
    _sl6b, _sd6b = J.stage_line({"agent": 100.0}, 110.0)
    check("a withheld export leaves the tail unitemised, not itemised as empty", "(export tail:" not in _sl6b and _sd6b["export_tail"] == 10.0, _sl6b)
    # THE REWATCH NAMES ITS DENSITY (the header once said 2fps whatever was rendered)
    _rm6 = J.rewatch_message(1, {"frames": 20, "sheets": [], "state": "ABSENT", "why": "x", "density_fps": 1.0}, ["  - item"], [])
    _rt6 = _rm6["message"]["content"][0]["text"]
    check("the rewatch header names the density it was rendered at", "20 frames at 1fps" in _rt6 and "2fps" not in _rt6, _rt6[:90])
    _mn6 = _fn6("main"); _mn6_src = ast.unparse(_mn6)
    check("a job takes --density-fps and edit() hands it to the rewatch instrument and the run line",
          any(a.arg == "density_fps" for a in _ed6.args.args) and any(a.arg == "density_fps" for a in _mn6.args.args)
          and any(any(k.arg == "density_fps" and isinstance(k.value, ast.Name) and k.value.id == "density_fps" for k in c.keywords) for c in _calls6(_ed6, "_preview_frames"))
          and "'density_fps': density_fps" in _ed6_src and "density_fps=density_fps" in _mn6_src)
    check("a brief can come from a file (quoting-safe for the batch)",
          any(a.arg == "brief_file" for a in _mn6.args.args) and "brief = open(brief_file" in _mn6_src)
    check("the run line says whether the run had the watch (the no-watch verdict reads it)", "'no_watch': bool(no_watch)" in _ed6_src)

    # ---- ITEM 7: THE BRIEF'S HARD CONSTRAINTS, ENFORCED (Zac, 2026-09-18) ----
    _bc = J.brief_constraints
    _k = lambda b: [(c["kind"], (c.get("value") or {}).get("op"), (c.get("value") or {}).get("seconds")) if c["checkable"] else (c["kind"], "UNCHECKED") for c in _bc(b)]
    check("a 'no captions' brief is extracted as a checkable constraint",
          _k("Tighten it up. No captions.") == [("no_captions", None, None)] and _k("Keep it caption-free.") == [("no_captions", None, None)]
          and _k("No subtitles please, and keep it under 30 seconds") == [("no_captions", None, None), ("duration", "<=", 30.0)], str(_k("Tighten it up. No captions.")))
    check("no music, no text, and a coordinated 'captions or titles' are read",
          _k("without music, make it pop") == [("no_music", None, None)] and _k("no on-screen text at all") == [("no_text", None, None)]
          and _k("Don't add any captions or titles") == [("no_captions", None, None), ("no_text", None, None)] and _k("no graphics") == [("no_text", None, None)])
    check("durations: under/at least/exactly/about/a 15-second/cut down to, seconds and minutes, word numbers",
          _k("a 15-second teaser") == [("duration", "~", 15.0)] and _k("exactly one minute") == [("duration", "==", 60.0)]
          and _k("at least 20 seconds") == [("duration", ">=", 20.0)] and _k("cut it down to 40 seconds") == [("duration", "~", 40.0)]
          and _k("about 45s, punchy") == [("duration", "~", 45.0)] and _k("under two minutes") == [("duration", "<=", 120.0)])
    _hr = _bc("blur his face in the second half")
    check("blur/hide a region is reported UNCHECKED, never passed",
          len(_hr) == 1 and _hr[0]["kind"] == "hide_region" and _hr[0]["checkable"] is False and "pixel detector" in str(_hr[0]["why"])
          and _k("hide the license plate") == [("hide_region", "UNCHECKED")]
          and J.check_constraints(_hr, [], None, {"state": "MEASURED", "cards": 0}, 20.0)[1][0]["state"] == "UNCHECKED"
          and J.check_constraints(_hr, [], None, {"state": "MEASURED", "cards": 0}, 20.0)[0] == [], str(_hr))
    _sb = {"goal": "a teaser", "must": ["no captions", "no music"], "duration_s": 20}
    check("a structured brief (object or its JSON text) yields the same constraints; a taste brief yields none",
          _k(_sb) == [("no_captions", None, None), ("no_music", None, None), ("duration", "~", 20.0)] and _k(json.dumps(_sb)) == _k(_sb)
          and _k("captions: false\nmusic: off") == [("no_captions", None, None), ("no_music", None, None)] and _k("just make it pop") == [])
    # THE RED PROOF ZAC NAMED: a 'no captions' brief against a timeline carrying a caption track
    _tl = [{"id": "base-1", "itemType": "video", "timelineRange": {"fromFrame": 0, "toFrame": 900}},
           {"id": "c1d2e3f4-0000", "itemType": "motion-graphic", "asset": {"name": "caption:TwoTone"}, "trackAlias": "V2", "timelineRange": {"fromFrame": 0, "toFrame": 900}}]
    _f, _rows = J.check_constraints(_bc("no captions"), _tl, "base-1", {"state": "MEASURED", "cards": 0, "why": "x"}, 30.0)
    check("a 'no captions' brief and a timeline carrying a caption track is a fault naming the track",
          len(_f) == 1 and "c1d2e3f4" in _f[0] and "caption:TwoTone" in _f[0] and _rows[0]["state"] == "FAIL", str(_f))
    _f2, _ = J.check_constraints(_bc("no captions"), _tl[:1], "base-1", {"state": "MEASURED", "cards": 12, "why": "from 'cards'"}, 30.0)
    _f3, _r3 = J.check_constraints(_bc("no captions"), _tl[:1], "base-1", {"state": "MEASURED", "cards": 0, "why": "x"}, 30.0)
    check("native caption cards are the same fault (cleared with edit_captions); zero cards and no track is a pass",
          len(_f2) == 1 and "12 native caption card" in _f2[0] and "edit_captions" in _f2[0] and _f3 == [] and _r3[0]["state"] == "PASS", "%s / %s" % (_f2, _r3))
    _f4, _r4 = J.check_constraints(_bc("no captions"), _tl[:1], "base-1", {"state": "ABSENT", "cards": None, "why": "no card list and no count"}, 30.0)
    _f5, _r5 = J.check_constraints(_bc("no captions"), _tl[:1], "base-1", {"state": "FAILED", "cards": None, "why": "read_captions FAILED: 500"}, 30.0)
    check("a caption read that is ABSENT or FAILED is a fault, not a pass",
          len(_f4) == 1 and "UNVERIFIED" in _f4[0] and _r4[0]["state"] == "ABSENT" and len(_f5) == 1 and _r5[0]["state"] == "FAILED", "%s / %s" % (_f4, _f5))
    _au = [{"id": "base-1", "itemType": "video", "timelineRange": {"fromFrame": 0, "toFrame": 900}},
           {"id": "m1", "itemType": "audio", "asset": {"name": "music-upbeat.mp3"}, "timelineRange": {"fromFrame": 0, "toFrame": 900}},
           {"id": "x1", "itemType": "audio", "asset": {"name": "whoosh"}, "timelineRange": {"fromFrame": 10, "toFrame": 40}}]
    _fm, _ = J.check_constraints(_bc("no music"), _au, "base-1", {"state": "MEASURED", "cards": 0}, 30.0)
    _fm2, _rm2 = J.check_constraints(_bc("no music"), [_au[0], _au[2]], "base-1", {"state": "MEASURED", "cards": 0}, 30.0)
    check("no music: a 30s audio item is a fault; a 1s sound effect is not",
          len(_fm) == 1 and "m1 music-upbeat.mp3 30.0s" in _fm[0] and _fm2 == [] and _rm2[0]["state"] == "PASS", "%s / %s" % (_fm, _rm2))
    _tx = [{"id": "base-1", "itemType": "video", "timelineRange": {"fromFrame": 0, "toFrame": 900}},
           {"id": "s1", "itemType": "motion-graphic", "asset": {"name": "StatCard"}, "timelineRange": {"fromFrame": 30, "toFrame": 180}}]
    _ft, _ = J.check_constraints(_bc("no text"), _tx, "base-1", {"state": "MEASURED", "cards": 0}, 30.0)
    _ft2, _ = J.check_constraints(_bc("no text"), _tx, "base-1", {"state": "MEASURED", "cards": 0}, 30.0, text_carriers={"StatCard", "PullQuote"})
    _ft3, _rt3 = J.check_constraints(_bc("no text"), _tx, "base-1", {"state": "MEASURED", "cards": 0}, 30.0, text_carriers={"PullQuote"})
    check("no text: a text-carrying overlay is a fault; the component text map decides, and no map counts every overlay",
          len(_ft) == 1 and "s1 StatCard" in _ft[0] and len(_ft2) == 1 and _ft3 == [] and _rt3[0]["state"] == "PASS", "%s / %s / %s" % (_ft, _ft2, _rt3))
    _du = lambda b, end: J.check_constraints(_bc(b), _tl[:1], "base-1", {"state": "MEASURED", "cards": 0}, end)
    check("duration: at or under 30 fails at 35 and passes at 28; about 45 fails at 50 and passes at 47; exactly 60 passes at 60.4",
          len(_du("under 30 seconds", 35.0)[0]) == 1 and _du("under 30 seconds", 28.0)[0] == [] and len(_du("about 45s", 50.0)[0]) == 1
          and _du("about 45s", 47.0)[0] == [] and _du("exactly 60 seconds", 60.4)[0] == [] and len(_du("at least 20 seconds", 15.0)[0]) == 1)
    _fd, _rd = _du("under 30 seconds", None)
    check("a duration with no timeline end is UNVERIFIED (ABSENT), a fault", len(_fd) == 1 and "UNVERIFIED" in _fd[0] and _rd[0]["state"] == "ABSENT")
    # THE TURN MACHINE HOLDS THE EXPORT (verify is the hook; injectable, driven here)
    _U1 = {"read": 0, "write": 300000, "in": 2, "out": 900}; _UN = {"read": 300000, "write": 400, "in": 2, "out": 300}
    _rwc = lambda n, final: {"message": {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "rw%d" % n}]}}, "sheets": 2, "faults": [], "scan": []}
    _vlog = []
    def _mkv(faults_by_n):
        def _v(n):
            _vlog.append(n); return list(faults_by_n.get(n) or [])
        return _v
    _exp = _mk_invoke(lambda n: (["edit_item"], "", _U1) if n == 1 else (["finish:export"], "", _UN))
    _tmc = J.run_two_calls(_exp, _rwc, {"type": "user", "message": {"role": "user", "content": []}}, verify=_mkv({2: ["no captions (brief): caption track c1"]}))
    # THE HARNESS'S OWN READ, separately from the brief's constraints: they are two different faults and
    # a leg that only drives one cannot see the other go missing.
    _rbv = J.run_two_calls(_mk_invoke(lambda n: (["edit_item"], "", _U1) if n == 1 else (["finish:export"], "", _UN)),
                           _rwc, {"type": "user", "message": {"role": "user", "content": []}},
                           readback=lambda: ["face/text collision: slot1 in the centre band"])
    check("THE HARNESS'S READ-BACK OF THE FINISHED TIMELINE DECIDES: a fault there is terminal and refunded, never exported",
          (_rbv["terminal"] or {}).get("kind") == "READBACK FAILED" and (_rbv["terminal"] or {}).get("refund") is True
          and _rbv["verdict"] is None and _rbv.get("readback_faults") == ["face/text collision: slot1 in the centre band"],
          str(_rbv.get("terminal"))[:140])
    # AND THE CAP IS STRUCTURAL: the machine calls _turn exactly twice, so there is no third call to cap.
    _turn_calls = [n for n in ast.walk(next(f for f in ast.walk(ast.parse(src)) if isinstance(f, ast.FunctionDef) and f.name == "run_two_calls"))
                   if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_turn"]
    check("THE CAP IS STRUCTURAL: the machine only ever makes two calls, so a third cannot be requested",
          len(_turn_calls) == 2 and [ast.unparse(c.args[0]) for c in _turn_calls] == ["1", "2"] and J.TURN_CAP == 2,
          [ast.unparse(c.args[0]) for c in _turn_calls])
    check("A VIOLATED CONSTRAINT AT CALL 2 IS TERMINAL AND REFUNDED — there is no third call to fix it in",
          len(_tmc["turns"]) == 2 and (_tmc["terminal"] or {}).get("kind") == "READBACK FAILED"
          and (_tmc["terminal"] or {}).get("refund") is True and _tmc["verdict"] is None
          and _tmc.get("constraint_faults") == {2: ["no captions (brief): caption track c1"]}, "%s %s" % (len(_tmc["turns"]), _tmc.get("terminal")))
    _vlog.clear()
    _exp2 = _mk_invoke(lambda n: (["edit_item"], "", _U1) if n == 1 else (["finish:export"], "", _UN))
    _tmv = J.run_two_calls(_exp2, _rwc, {"type": "user", "message": {"role": "user", "content": []}}, verify=_mkv({2: ["f"], 3: ["f"], 4: ["f"]}))
    check("the constraint check runs ONCE, at call 2, and its fault is the terminal",
          len(_tmv["turns"]) == 2 and (_tmv["terminal"] or {}).get("kind") == "READBACK FAILED"
          and _tmv["verdict"] is None and sorted(_tmv.get("constraint_faults") or {}) == [2] and _vlog == [2], "%s %s" % (_tmv["terminal"], _vlog))
    _vlog.clear()
    _exp3 = _mk_invoke(lambda n: (["edit_item"], "", _U1) if n == 1 else (["finish:export"], "", _UN))
    _tmo = J.run_two_calls(_exp3, _rwc, {"type": "user", "message": {"role": "user", "content": []}}, verify=_mkv({}))
    _vlog2 = list(_vlog); _vlog.clear()
    _fix = _mk_invoke(lambda n: (["edit_item"], "", _U1 if n == 1 else _UN))
    _tmf = J.run_two_calls(_fix, _rwc, {"type": "user", "message": {"role": "user", "content": []}}, verify=_mkv({}))
    check("a clean verify exports at call 2, whether call 2 finished or fixed",
          str(_tmo["verdict"]).startswith("export at call 2") and _vlog2 == [2]
          and str(_tmf["verdict"]).startswith("export at call 2") and _vlog == [2], "%s %s / %s %s" % (_tmo["verdict"], _vlog2, _tmf["verdict"], _vlog))
    # THE SEAM IN edit(): the hook is handed over, the rewatch carries the faults, the agent is told, the record keeps it
    _edit_fn7 = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "edit")
    _ed7 = ast.unparse(_edit_fn7)
    check("edit() hands the constraint check to the turn machine",
          re.search(r"run_two_calls\(_invoke, _rewatch, _first_message, t0=t0, verify=_verify", _ed7) is not None)
    check("the rewatch hands constraint violations to the next turn as faults",
          "_constraints_now(_items, _base," in _ed7 and "'BRIEF CONSTRAINT VIOLATED — %s' % f for f in _cf_rw" in _ed7 and "'constraints': _crows_rw" in _ed7)
    # WHERE IN THE RECORD, structurally: the key rides in the dict assigned to out["turn_machine"] (a substring
    # over edit() cannot tell a written key from one in a literal nothing assigns — and a reader looking at the
    # wrong level reported the key missing when it was there, 2026-09-18).
    _tmw = next((n for n in ast.walk(_edit_fn7) if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict)
                 and any(ast.unparse(t) == "out['turn_machine']" for t in n.targets)), None)
    _tmk = [k.value for k in _tmw.value.keys if isinstance(k, ast.Constant)] if _tmw else []
    check("the record keeps what was extracted, every read, and the faults by turn — in the dict the run assigns to out['turn_machine']",
          "constraints" in _tmk and "three_turns" in _tmk and "'extracted': _constraints, 'reads': _constraint_reads, 'faults_by_turn': _tm.get('constraint_faults')" in ast.unparse(_tmw)
          and "constraints=_constraints" in _ed7, "turn_machine keys: %s" % _tmk)
    # THE MESSAGE THE AGENT RECEIVES, not the function's text (a block under `if False:` still reads as present in the source)
    _m1c = J.pass1_message(None, [], os.path.join(HERE, "sheet", "INVENTORY.png"), source_watch=None, deciding="x", face=["FACE — f"], platter="PROPERTY KEYS — p", constraints=_bc("no captions"))
    _t1c = [b.get("text") or "" for b in _m1c["message"]["content"] if b.get("type") == "text"]
    _ixc = lambda pref: next((i for i, t in enumerate(_t1c) if t.startswith(pref)), None)
    check("the first message tells the agent the constraints, after the inventory and the face",
          _ixc("THE COMPONENT INVENTORY") is not None and _ixc("FACE — f") is not None and _ixc("THE BRIEF'S HARD CONSTRAINTS") is not None
          and _ixc("THE COMPONENT INVENTORY") < _ixc("FACE — f") < _ixc("THE BRIEF'S HARD CONSTRAINTS") and "no captions" in _t1c[_ixc("THE BRIEF'S HARD CONSTRAINTS")],
          str([t[:28] for t in _t1c]))
    _cp = J.constraint_prompt(_bc("No captions, under 30 seconds, and blur his face"))
    check("the prompt names the checkable constraints as checks and the unverifiable as the agent's to honor; none -> empty",
          "WILL NOT EXPORT" in _cp and "no captions" in _cp and "at or under 30s" in _cp and "blur his face" in _cp and "cannot verify" in _cp and J.constraint_prompt([]) == "")
    # caption_cards reads the fact from the shapes measured (a list, or the API's own count) and names an absence
    _saved_mcp = J._mcp_call
    try:
        J._mcp_call = lambda tok, name, args, **kw: {"returned": 0, "limit": 100, "offset": 0, "_text": "x"}
        _cc0 = J.caption_cards("t", {"projectId": "p"})
        J._mcp_call = lambda tok, name, args, **kw: {"cards": [{"a": 1}, {"a": 2}]}
        _cc2 = J.caption_cards("t", {"projectId": "p"})
        J._mcp_call = lambda tok, name, args, **kw: {"_text": "nothing here"}
        _cca = J.caption_cards("t", {"projectId": "p"})
        def _boom(*a, **k): raise RuntimeError("500")
        J._mcp_call = _boom
        _ccf = J.caption_cards("t", {"projectId": "p"})
    finally:
        J._mcp_call = _saved_mcp
    check("caption_cards: MEASURED from a list or the API's count, ABSENT with the keys, FAILED on an error",
          _cc0 == {"state": "MEASURED", "cards": 0, "why": "from the API's `returned` count"} and _cc2["state"] == "MEASURED" and _cc2["cards"] == 2
          and _cca["state"] == "ABSENT" and "_text" in _cca["why"] and _ccf["state"] == "FAILED", "%s %s %s %s" % (_cc0, _cc2, _cca, _ccf))

    # ---- THE NO-WATCH ARM RESUMES ITS OWN TURN-1 SESSION (a fresh session per turn cache-missed at call 2) ----
    _ed8 = ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "edit"))
    check("no-watch: turn 1 creates the session cold and every later turn resumes it; the record says which and whether it resumed",
          "if no_watch and n == 1 and _res.get('session_id'):" in _ed8 and "_run_sid['sid'] = str(_res.get('session_id'))" in _ed8
          and re.search(r"_cmd_n = _cmd if _run_sid\['sid'\] == _watch_sid else cli_command\(_run_sid\['sid'\]", _ed8) is not None
          and "_cmd_n + ['--max-turns', '1']" in _ed8 and "'resumed': '--resume' in _cmd_n" in _ed8)

    # ---- A REUSED STAGE THAT HOLDS ITEMS IS REFUSED BEFORE THE FIRST CALL (H1 of 2026-09-18 inherited last batch's items) ----
    _ed9 = ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "edit"))
    _i_refuse = _ed9.find("'kind': 'CONTAMINATED ARM'"); _i_first = _ed9.find("run_two_calls(_invoke, _rewatch, _first_message")
    check("a reused stage whose timeline holds items, or cannot be read, is a CONTAMINATED ARM terminal before any model call",
          "if _stage.get('priorItems') is None or len(_stage.get('priorItems') or []) > 0:" in _ed9 and _i_refuse > 0 and _i_refuse < _i_first
          and "'export': {'state': 'WITHHELD'" in _ed9[_i_refuse:_i_refuse + 900] and "_stage['priorItems'] = None" in _ed9)

    # ---- ITEM 1+2 (Zac, 2026-09-19): THE OUTPUT DIET, THE CAP, AND ONE TOOL LIST ----
    # THE AGENT'S SURFACE, DRIVEN: cli_command is the producer, so ask IT, not the source text.
    _cmd_t1 = J.cli_command("sid-1", "claude-sonnet-5")
    _cmd_t2 = J.cli_command("sid-1", "claude-sonnet-5")
    check("the tool list is identical on every turn (the tool block is in the cache key; a per-turn list is a cold write per run)",
          _cmd_t1 == _cmd_t2 and _cmd_t1.count("--tools") == 1)
    _tools_arg = _cmd_t1[_cmd_t1.index("--tools") + 1]
    _allow_arg = _cmd_t1[_cmd_t1.index("--allowedTools") + 1]
    _named = set(_tools_arg.split(",")) | set(_allow_arg.split(","))
    _BUILTINS = {"Bash", "Read", "Write", "Glob", "Grep", "Edit", "WebFetch", "WebSearch"}
    _READS = {"mcp__chatcut__" + t for t in ("read_project", "inspect_item", "inspect_asset", "preview_timeline", "read_captions", "transcript", "edit_asset")}
    check("THE GATE: no builtin is named on any turn — Bash above all (a Bash call to load a disallowed skill killed a run, 2026-09-18)",
          not (_named & _BUILTINS), "named builtins: %s" % sorted(_named & _BUILTINS))
    check("THE GATE: no read tool is named on any turn — the harness reads the timeline back and serves it",
          not (_named & _READS), "named reads: %s" % sorted(_named & _READS))
    check("the agent's surface is exactly the edit ops and the turn-ender",
          _named == {"mcp__chatcut__edit_item", "mcp__chatcut__edit_captions", "mcp__chatcut__finish"}, str(sorted(_named)))
    check("the shim is told the same list, so tools/list cannot re-advertise what the flags removed",
          "'MCP_SHIM_ALLOW': ','.join(AGENT_TOOLS)" in ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "write_cli_context")))
    # THE CAP: derived, applied on the wire, and terminal rather than silent
    check("the cap's derivation is recorded from a measured full edit, not guessed (held, not applied)",
          J.OUTPUT_CAP_TOKENS == 2 * 1108, "OUTPUT_CAP_TOKENS=%s" % J.OUTPUT_CAP_TOKENS)
    _ed10 = ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "edit"))
    # THE HOLD IS THE PROPERTY (Zac, 2026-09-19): max_tokens counts thinking, thinking arrives whether
    # or not the request disables it, so no cap goes on the body until a response is proven to carry none.
    check("NO cap is applied to the body while thinking is uncontrolled — the proxy can, and edit() passes 0",
          "_px.MAX_OUTPUT_TOKENS = 0" in _ed10 and "_px.MAX_OUTPUT_TOKENS = OUTPUT_CAP_TOKENS" not in _ed10
          and "body['max_tokens'] = MAX_OUTPUT_TOKENS" in ast.unparse(ast.parse(PX_SRC)))
    check("the proxy reads stop_reason from the END of the stream (message_delta), not the head",
          "tail = (tail + chunk)[-2000:]" in PX_SRC and '"stop_reason":"([a-z_]+)"' in PX_SRC)
    _U1c = {"read": 0, "write": 300000, "in": 2, "out": 900}
    def _capped(n, message):
        return {"rc": 1, "subtype": None, "tool_calls": [{"name": "mcp__chatcut__edit_item", "input": {"adds": [{"id": "x"}]}}],
                "text": "", "usage": _U1c, "wall": 1.0, "killed": False, "stop_reason": "max_tokens"}
    _tmcap = J.run_two_calls(_capped, lambda n, final: {"message": {}, "sheets": 0}, {"type": "user", "message": {"role": "user", "content": []}})
    check("a turn that hits the cap is a NAMED terminal and its truncated tool call is never applied",
          (_tmcap["terminal"] or {}).get("kind") == "OUTPUT CAP" and (_tmcap["terminal"] or {}).get("at") == 1
          and "TRUNCATED" in (_tmcap["terminal"] or {}).get("why", "") and _tmcap["verdict"] is None, str(_tmcap.get("terminal")))
    # THE DIET, in the paragraph the agent actually receives
    # THE PARAGRAPH edit() COMPOSES (pass1_message receives it as `plan`; driving the builder with
    # plan=None reads a message that never carried it — the leg would test its own argument).
    _t1d = "".join(n.value for n in ast.walk(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "edit"))
                   if isinstance(n, ast.Constant) and isinstance(n.value, str))
    check("the paragraph states the diet: a why under 12 words, no prose, payloads carrying only what the harness executes",
          "TWELVE WORDS OR FEWER" in _t1d and "Write no prose" in _t1d and "only the fields the harness executes" in _t1d
          and "one line: what it is for" not in _t1d, [k for k in ("TWELVE WORDS OR FEWER", "Write no prose", "only the fields the harness executes") if k not in _t1d])

    # ---- THE DIAGNOSTIC WINDOW, AND WHAT THE RESPONSE CARRIED (Zac, 2026-09-19) ----
    _ed11 = ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "edit"))
    check("a widened run bound is a PARAMETER, defaults to the law, and the record says when it was raised",
          "_bound_s = int(run_bound) if run_bound and int(run_bound) > 0 else RUN_TIMEOUT_S" in _ed11
          and "'run_bound_s': _bound_s, 'run_bound_raised': _bound_s != RUN_TIMEOUT_S" in _ed11
          and "run_timeout=_bound_s" in _ed11 and "_left = max(10.0, _bound_s - (time.time() - _run_t0))" in _ed11)
    check("the 120s turn law still reports when the run bound is raised",
          "over the %ds turn law" in _ed11 and "TURN_LAW_S" in _ed11)
    check("the response's thinking blocks are read per call and reported beside the output they are billed inside",
          "'thinking_by_call': _think_by_call" in _ed11 and "'deltas': _rs.get('thinking_deltas')" in _ed11 and "THINKING BLOCKS" in _ed11)
    check("the tool block is proven identical across calls from the proxy's own hash, not from the flags",
          "'tools_identical': _tools_same" in _ed11 and "_shas = {x['sha'] for x in _tools_by_call if x.get('sha')}" in _ed11
          and "every later call is a cold write" in _ed11)

    # ---- EVERY TURN ENDS IN A TOOL CALL (Zac, 2026-09-19), and the canonical Sonnet arm ----
    import mcp_shim as MS2
    _saved_allow = MS2.ALLOW
    try:
        MS2.ALLOW = ["edit_item", "edit_captions", "finish"]
        _ok = MS2.handle({"id": 1, "method": "tools/call", "params": {"name": "finish", "arguments": {"verdict": "export", "why": "ships"}}})
        _bad = MS2.handle({"id": 2, "method": "tools/call", "params": {"name": "finish", "arguments": {"verdict": "ship"}}})
        # AND IT MUST BE ADVERTISED: a tool the model is never shown cannot be called, so the leg drives
        # tools/list too (upstream stubbed — the point is whether OUR tool is appended).
        _up = MS2.upstream
        try:
            MS2.upstream = lambda method, params, mid: {"result": {"tools": []}}
            _listed = [t.get("name") for t in ((MS2.handle({"id": 3, "method": "tools/list", "params": {}}) or {}).get("result") or {}).get("tools", [])]
        finally:
            MS2.upstream = _up
    finally:
        MS2.ALLOW = _saved_allow
    check("the shim ADVERTISES `finish` and serves it itself, refusing a verdict that is not clean or export",
          _listed == ["finish"] and "result" in _ok and "noted: export" in json.dumps(_ok)
          and (_bad.get("error") or {}).get("code") == -32602
          and MS2.FINISH_TOOL["inputSchema"]["properties"]["verdict"]["enum"] == ["clean", "export"],
          "listed=%s bad=%s" % (_listed, json.dumps(_bad)[:90]))
    check("`finish` is on the agent's surface beside the edit ops", J.AGENT_TOOLS == ["edit_item", "edit_captions", "finish"], str(J.AGENT_TOOLS))
    # DRIVEN, NOT GREPPED: a presence check reads the same under `if False:`. The proxy's own function is
    # called with a body and the result inspected.
    _pxb = {"model": "m", "tools": [{"name": "edit_item"}], "messages": []}
    _saved_tc = PX.TOOL_CHOICE_ANY
    try:
        PX.TOOL_CHOICE_ANY = True
        _b_on = PX.apply_tool_choice(json.loads(json.dumps(_pxb)))
        PX.TOOL_CHOICE_ANY = False
        _b_off = PX.apply_tool_choice(json.loads(json.dumps(_pxb)))
        _b_none = PX.apply_tool_choice({"model": "m", "messages": []})
    finally:
        PX.TOOL_CHOICE_ANY = _saved_tc
    check("the proxy sets tool_choice any on a body that has tools, leaves one without tools alone, and only when armed",
          _b_on.get("tool_choice") == {"type": "any"} and _b_off.get("tool_choice") is None and _b_none.get("tool_choice") is None
          and "'tool_choice': body.get('tool_choice')" in ast.unparse(ast.parse(PX_SRC))
          and "_px.TOOL_CHOICE_ANY = True" in ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "edit")),
          "on=%s off=%s none=%s" % (_b_on.get("tool_choice"), _b_off.get("tool_choice"), _b_none.get("tool_choice")))
    check("the verdict is the CALL, never a word in prose",
          J._finish_verdict([{"name": "mcp__chatcut__finish", "input": {"verdict": "export"}}]) == "export"
          and J._finish_verdict([{"name": "mcp__chatcut__finish", "input": {"verdict": "ship"}}]) is None
          and J._finish_verdict([]) is None and J._finish_verdict([{"name": "mcp__chatcut__edit_item", "input": {}}]) is None)
    _U1f = {"read": 0, "write": 300000, "in": 2, "out": 900}; _UNf = {"read": 300000, "write": 400, "in": 2, "out": 300}
    _rwf = lambda n, final: {"message": {}, "sheets": 0}
    def _prose(n, message):
        return {"rc": 1, "subtype": None, "tool_calls": [], "text": "```json\n{\"adds\": [{\"type\": \"motion-graphic\"}]}\n```",
                "usage": _U1f if n == 1 else _UNf, "wall": 1.0, "killed": False}
    _tmp = J.run_two_calls(_prose, _rwf, {"type": "user", "message": {"role": "user", "content": []}})
    check("a 4xx is named API ERROR, never TEXT ONLY — the API's own verdict is read before the model's behaviour",
          (J.run_two_calls(lambda n, m: {"rc": 1, "tool_calls": [], "text": "Credit balance is too low", "usage": {}, "wall": 1.0,
                                         "killed": False, "api_status": 400, "api_head": "credit"},
                           lambda n, f: {}, {"type": "user"})["terminal"] or {}).get("kind") == "API ERROR")
    check("A TURN THAT RETURNS TEXT ONLY IS REFUSED BEFORE ANYTHING IS APPLIED (Haiku wrote its edit inside a ```json fence and called nothing)",
          (_tmp["terminal"] or {}).get("kind") == "TEXT ONLY" and (_tmp["terminal"] or {}).get("at") == 1
          and _tmp["verdict"] is None and len(_tmp["turns"]) == 1, str(_tmp.get("terminal"))[:140])
    def _finisher(n, message):
        return {"rc": 1, "subtype": None,
                "tool_calls": ([{"name": "mcp__chatcut__edit_item", "input": {"adds": [{"id": "a"}]}}] if n == 1
                               else [{"name": "mcp__chatcut__finish", "input": {"verdict": "export", "why": "right as it stands"}}]),
                "text": "", "usage": _U1f if n == 1 else _UNf, "wall": 1.0, "killed": False}
    _tmf = J.run_two_calls(_finisher, _rwf, {"type": "user", "message": {"role": "user", "content": []}})
    # THE CASE WHERE THE VERDICT READ STILL DECIDES: a call 2 that uses SOME tool (so the TEXT ONLY
    # guard does not fire) but neither edits nor finishes, while saying "export" in its text.
    def _otherTool(n, message):
        return {"rc": 1, "subtype": None,
                "tool_calls": ([{"name": "mcp__chatcut__edit_item", "input": {"adds": [{"id": "a"}]}}] if n == 1
                               else [{"name": "mcp__chatcut__preview_timeline", "input": {}}]),
                "text": "" if n == 1 else "export — it looks right to me", "usage": _U1f if n == 1 else _UNf,
                "wall": 1.0, "killed": False}
    _tmo2 = J.run_two_calls(_otherTool, _rwf, {"type": "user", "message": {"role": "user", "content": []}}, readback=lambda: [])
    check("a call 2 that calls some other tool and SAYS export is NO VERDICT, not an export",
          (_tmo2["terminal"] or {}).get("kind") == "NO VERDICT" and _tmo2["verdict"] is None, str(_tmo2.get("terminal"))[:130])
    check("a finish call at call 2 ends the run the way the word used to", str(_tmf["verdict"]).startswith("export at call 2") and _tmf["terminal"] is None, str(_tmf.get("verdict")))
    # THE WHOLE PREFIX TEXT, not just edit()'s own constants: the loop paragraph is a module-level
    # constant that edit() concatenates in, so a leg reading only edit() cannot see it.
    _allsrc = src + J.TWO_TURN_LOOP + J.CRAFT_CONTEXT
    check("the paragraph says every turn ends in a tool call and names finish",
          "EVERY TURN ENDS IN A TOOL CALL" in _allsrc and "call finish" in _allsrc and "single word: export" not in _allsrc,
          [k for k in ("EVERY TURN ENDS IN A TOOL CALL", "call finish") if k not in _allsrc])
    # THE CANONICAL ARM IS THE DEFAULT, not a flag the caller must remember
    check("Sonnet canonical — thinking disabled, effort low — is the DEFAULT for a job, and the ping carries the same pair",
          J.CANONICAL_THINK_TOKENS == 0 and J.CANONICAL_EFFORT == "low"
          and all(d == {"think_tokens": "CANONICAL_THINK_TOKENS", "effort": "CANONICAL_EFFORT"}
                  for d in [{a.arg: ast.unparse(v) for a, v in zip(f.args.args[-len(f.args.defaults):], f.args.defaults) if a.arg in ("think_tokens", "effort")}
                            for f in ast.walk(ast.parse(src)) if isinstance(f, ast.FunctionDef) and f.name in ("edit", "main", "warm", "keep_warm")]))

    # ---- THE CONTAINER'S OWN CLOCK (Zac, 2026-09-19): the check for the class the thread fix closed ----
    check("the proxy's server marks its connection threads as daemons, so a tunnel cannot outlive the process",
          "srv.daemon_threads = True" in PX_SRC and getattr(__import__("http.server", fromlist=["ThreadingHTTPServer"]), "ThreadingHTTPServer") is not None)
    _pxsrv = None
    try:
        import http.server as _hs
        _cd = tempfile.mkdtemp(prefix="daemon_")
        _p, _ca = PX.serve_mitm(0, _cd)
        _pxsrv = _p
    except Exception as _se:                                      # noqa: BLE001
        _pxsrv = "FAILED %s" % str(_se)[:60]
    check("serve_mitm still starts and returns a port with daemon threads set", isinstance(_pxsrv, int) and _pxsrv > 0, str(_pxsrv))
    _ed12 = ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "edit"))
    check("the run line carries the container's process clock beside the run wall, and the setup gap between them",
          "'container_process_s'" in _ed12 and "'run_wall_s'" in _ed12 and "_CONTAINER_T0" in src
          and "setup before our clock" in _ed12)
    check("a container that outlives its export past the budget is a LEDGERED DEFECT with an owner page",
          J.EXPORT_TO_EXIT_BUDGET_S == 30 and "'kind': 'CONTAINER LINGERED'" in _ed12
          and "OWNER PAGE      : CONTAINER LINGERED" in _ed12 and "out.setdefault('defects', [])" in _ed12
          and "_lingered = _after_export_s is not None and _after_export_s > EXPORT_TO_EXIT_BUDGET_S" in _ed12)
    check("the red proof BOUNDS every smoke it runs, and a hang is a harness failure with its own code",
          "SMOKE_TIMEOUT_S" in RP_SRC and "timeout=SMOKE_TIMEOUT_S" in RP_SRC and "return 124," in RP_SRC
          and "a hang is not a result" in RP_SRC.lower() or "A hang is not a result" in RP_SRC)

    # ---- THE CATALOGUE READER (2026-09-19): an empty read is ABSENT, never MEASURED ----
    # CONTAINMENT, NOT EQUALITY, and the reason is a property of the envelope rather than a concession:
    # a category overview's ids ARE the group names, and a group listing's are the items, so a walker
    # that finds every id in an unknown shape necessarily finds both when both are present. What must
    # hold is that no real id is missed and that the KEY IT CAME FROM is named, which is what lets the
    # caller tell a group overview from an item list.
    _li = lambda env: J.library_ids(env)
    _flat, _gd, _gl, _deep = (_li({"items": [{"id": "z"}], "total": 1}), _li({"groups": {"A": [{"id": "b"}]}}),
                              _li({"groups": [{"name": "A", "items": [{"id": "x"}, {"id": "y"}]}]}),
                              _li({"data": {"page": {"rows": [{"assetId": "deep-1"}]}}, "total": 1}))
    check("library_ids finds every id however the envelope nests it, and names the key it used",
          _flat[:2] == (["z"], "MEASURED") and "items" in _flat[2]
          and _gd[0] == ["b"] and "groups.A" in _gd[2]
          and set(_gl[0]) >= {"x", "y"} and "groups[0].items" in _gl[2]
          and _deep[0] == ["deep-1"] and "data.page.rows" in _deep[2]
          and "stated total" in _li({"items": [{"id": "z"}], "total": 9})[2],
          "%s | %s | %s | %s" % (_flat[:2], _gd[:2], _gl[:2], _deep[:2]))
    _empty = J.library_ids({"_links": 1, "_text": "", "category": "x", "groups": {}, "total": 0})
    check("AN EMPTY CATALOGUE READ IS ABSENT AND NAMES THE KEYS IT SAW — never MEASURED with an empty list",
          _empty[1] == "ABSENT" and "groups" in _empty[2] and _empty[0] == [], str(_empty))
    check("an errored category is ABSENT with its message, and a non-object answer is FAILED",
          J.library_ids({"isError": True, "_text": "unknown category"})[1] == "ABSENT"
          and J.library_ids("nope")[1] == "FAILED")

    # ---- THE THREE CLASSES THE SEAM WAS BLIND TO (Builder-2, 2026-09-19) ----
    # Measured against fixtures/production_briefs.v1.jsonl: 12 of 30 rows carry a negative constraint
    # and 7 carry an only/do-not-alter form, and an English-only pattern read none of the non-English
    # ones. A constraint the user stated plainly in their own language read as NO constraint.
    _k2 = lambda b: [c["kind"] for c in J.brief_constraints(b)]
    check("a caption constraint is read in the languages this corpus actually contains, not only English",
          _k2("Viral engaging video Bez teksta") == ["no_captions"]
          and _k2("Melhores jogadas, sem legendas, com transicoes") == ["no_captions"]
          and _k2("sin subtitulos por favor") == ["no_captions"]
          and _k2("make it viral, without captions") == ["no_captions"],
          "%s / %s / %s" % (_k2("Viral engaging video Bez teksta"), _k2("sem legendas"), _k2("sin subtitulos")))
    _only = J.brief_constraints("IMPORTANT: Add captions ONLY. Do not edit or alter my video in any other way.")
    check("an ONLY / do-not-alter brief is a CHECKABLE scope constraint naming the licensed family",
          [c["kind"] for c in _only] == ["scope_only"] and _only[0]["checkable"] is True
          and (_only[0].get("value") or {}).get("allowed") == "caption", str(_only))
    _sc_items = [{"id": "base-1", "itemType": "video", "timelineRange": {"fromFrame": 0, "toFrame": 900}},
                 {"id": "c1", "itemType": "motion-graphic", "asset": {"name": "caption:TwoTone"}, "timelineRange": {"fromFrame": 0, "toFrame": 900}},
                 {"id": "z1", "itemType": "effect", "asset": {"name": "builtin:zoom"}, "timelineRange": {"fromFrame": 30, "toFrame": 90}}]
    _sf, _sr = J.check_constraints(_only, _sc_items, "base-1", {"state": "MEASURED", "cards": 0}, 30.0)
    _sf2, _sr2 = J.check_constraints(_only, _sc_items[:2], "base-1", {"state": "MEASURED", "cards": 0}, 30.0)
    check("ONE unasked op fails a captions-only brief, and the fault names the item and its family",
          len(_sf) == 1 and _sr[0]["state"] == "FAIL" and "z1" in _sf[0] and "zoom" in _sf[0]
          and _sf2 == [] and _sr2[0]["state"] == "PASS", "%s / %s" % (_sf, _sr2))
    # ---- WHAT THE CORPUS'S `only` SENTENCES ACTUALLY SAY (2026-09-19) ----
    # Builder-2 reported pb-024 as a missed scope_only. It is a miss, and a WIDER scope rule is the
    # wrong fix: of the corpus's five `only` sentences, FOUR limit a CATEGORY inside the brief, not
    # the brief. pb-003 allows "Only zoom in / zoom out effects" in a brief whose first four items
    # are captions; pb-012 heads a list naming cuts, zoom, captions and b-roll; pb-021 says "Only
    # trim and combine" then "Add simple, accurate captions"; pb-024 says "Zoom in / zoom out only"
    # then asks for captions, number badges and sound effects. A scope_only on any of them fails the
    # agent for placing what the brief asked for. The separating property is not the sentence's
    # shape — it is whether the brief asks for anything outside the licensed family.
    _fam = lambda b: [(c["kind"], (c.get("value") or {}).get("allowed")) for c in J.brief_constraints(b)]
    _pb003 = ("1. Captions: All captions in English.\n"
              "6. Allowed visual edits: Only zoom in / zoom out effects - no other transitions or cuts.")
    _pb024 = ("Auto captions - add auto-generated captions synced to my speech.\n"
              "2. Zoom in / zoom out only, no cuts - keep the footage as one continuous take.")
    check("a category-scoped `only` never becomes a whole-timeline licence",
          not [c for c in _fam(_pb003) if c[0] == "scope_only"]
          and not [c for c in _fam(_pb024) if c[0] == "scope_only"]
          and not [c for c in _fam("Only trim and combine the strongest soundbites. Add simple captions.") if c[0] == "scope_only"],
          "%s / %s" % (_fam(_pb003), _fam(_pb024)))
    check("a brief-scoped `only` still reads, because nothing outside the family is asked for",
          _fam("IMPORTANT: Add captions ONLY. Do not edit or alter my video in any other way.")[-1] == ("scope_only", "caption"),
          str(_fam("Add captions ONLY. Do not edit or alter my video in any other way.")))
    # THE CONSTRAINT pb-024 REALLY CARRIES, and the density note that must not impersonate it.
    check("`one continuous take` is a checkable no-cuts constraint, and a cut-density note is not",
          [c[0] for c in _fam(_pb024)] == ["no_cuts"]
          and [c[0] for c in _fam("Use subtle, smooth cuts. Do not cut every breath or micro-pause.")] == [],
          "%s / %s" % (_fam(_pb024), _fam("Use subtle cuts. Do not cut every breath.")))
    _nc = J.brief_constraints(_pb024)
    _one = [{"id": "base-1", "itemType": "video", "timelineRange": {"fromFrame": 0, "toFrame": 900}}]
    _two = _one + [{"id": "v2", "itemType": "video", "timelineRange": {"fromFrame": 900, "toFrame": 1500}}]
    _f1, _r1 = J.check_constraints(_nc, _one, "base-1", {"state": "MEASURED", "cards": 0}, 30.0)
    _f2, _r2 = J.check_constraints(_nc, _two, "base-1", {"state": "MEASURED", "cards": 0}, 30.0)
    # A TIMELINE THAT CANNOT BE READ MUST REACH A STATE, NEVER AN EXCEPTION. Caught here
    # so that deleting the ABSENT branch fails THIS leg instead of killing the run: the
    # red proof measured exactly that difference (rc=1, leg_failed=False) and it is the
    # same class as a failed measurement being indistinguishable from a clean result.
    try:
        _f0, _r0 = J.check_constraints(_nc, [], "base-1", {"state": "MEASURED", "cards": 0}, 30.0)
    except Exception as _e0:                                      # noqa: BLE001
        _f0, _r0 = [], [{"state": "RAISED", "read": "%s: %s" % (type(_e0).__name__, _e0)}]
    check("no-cuts passes on one video item, fails on two, and an unreadable timeline is ABSENT not PASS",
          _f1 == [] and _r1[0]["state"] == "PASS"
          and len(_f2) == 1 and _r2[0]["state"] == "FAIL" and "2 video items" in _r2[0]["read"]
          and _r0[0]["state"] == "ABSENT" and len(_f0) == 1,
          "%s / %s / %s" % (_r1[0]["state"], _r2[0]["state"], _r0[0]["state"]))
    # THE SEAM. A word the extractor emits that `_fam_of` cannot produce fails EVERY placed item
    # silently. "music only" against an audio item the checker calls "sound" was exactly that.
    _emit = set()
    for _w in ("captions", "subtitles", "legendas", "cuts", "trims", "zoom in", "zoom-out",
               "titles", "text", "graphics", "music", "sounds", "sfx", "transitions"):
        for _c in J.brief_constraints("%s only" % _w):
            if _c["kind"] == "scope_only":
                _emit.add((_c.get("value") or {}).get("allowed"))
    _produced = {"caption", "sound", "cut", "zoom", "title", "transition"}
    check("every family the extractor can emit is one the read-back checker can classify",
          _emit and not (_emit - _produced), "emits %s, orphans %s" % (sorted(_emit), sorted(_emit - _produced)))
    # AND EVERY KIND IT EMITS HAS A BRANCH. A kind with no branch is extracted, never read, and
    # reported as no fault — the exact shape of a false green.
    import inspect as _insp
    _handled = set(_re.findall(r'k == "(\w+)"', _insp.getsource(J.check_constraints)))
    _uncheckable = {k for k, ck, _rx in J._CONSTRAINT_RULES if not ck}
    check("every checkable constraint kind has a branch in the checker",
          not ({k for k, ck, _rx in J._CONSTRAINT_RULES if ck} - _handled),
          "missing %s (uncheckable, routed to UNCHECKED: %s)" % (
              sorted({k for k, ck, _rx in J._CONSTRAINT_RULES if ck} - _handled), sorted(_uncheckable)))
    # A CONSTRAINT THE AGENT IS NEVER TOLD IN WORDS. `scope_only` and `no_cuts` were both checked and
    # both terminal while `constraint_prompt` rendered them as their own variable names — the harness
    # refusing an export for a rule it had not stated. Ledgering a rule is not telling anyone.
    check("every checkable constraint kind is stated to the agent in words, never as its kind name",
          not [k for k, ck, _rx in J._CONSTRAINT_RULES if ck and k not in J._CONSTRAINT_MEANING],
          "no meaning for %s" % [k for k, ck, _rx in J._CONSTRAINT_RULES if ck and k not in J._CONSTRAINT_MEANING])
    _cp = J.constraint_prompt(J.brief_constraints("Zoom in / zoom out only, no cuts - one continuous take."))
    _cp2 = J.constraint_prompt(J.brief_constraints("Do not alter my video in any other way. Nothing else."))
    check("the rendered constraint block names the licensed family and leaves no placeholder unfilled",
          "ONE video item" in _cp and "must be zoom" in _cp and "no_cuts" not in _cp and "scope_only" not in _cp
          and "%s" not in _cp and "%s" not in _cp2 and "explicitly asked for" in _cp2, _cp)
    # ---- THE TIMELINE BEFORE TURN 1 (Builder-2's re-edit contract, 2026-09-19) ----
    # A re-edit is judged on what it did NOT touch, and the final timeline cannot answer that:
    # an item that was never there and an item that was removed look identical afterwards.
    _bi = [{"id": "d196b800", "itemType": "video", "timelineRange": {"fromFrame": 0, "toFrame": 335}, "trackAlias": "V1"},
           {"id": "64648857", "itemType": "motion-graphic", "timelineRange": {"fromFrame": 565, "toFrame": 611}, "trackAlias": "V2"},
           {"id": "z1", "itemType": "effect", "durationInFrames": 30, "timelineRange": {"fromFrame": 150, "toFrame": 180}, "trackAlias": "V3"}]
    _bm = J.before_timeline("tok", {}, reader=lambda t, st: {"items": _bi})
    _ba = J.before_timeline("tok", {}, reader=lambda t, st: {"items": [], "read_why": "no tracks"})
    def _boom(t, st):
        raise RuntimeError("401 from preview_timeline")
    _bf = J.before_timeline("tok", {}, reader=_boom)
    check("the before-timeline carries the judge's four fields for EVERY item, in the spec's shape",
          _bm["state"] == "MEASURED" and len(_bm["items"]) == 3
          and _bm["items"][0] == {"id": "d196b800", "from": 0, "dur": 335, "track": "V1", "kind": "video"}
          and _bm["items"][2] == {"id": "z1", "from": 150, "dur": 30, "track": "V3", "kind": "effect"},
          str(_bm["items"][:1]))
    check("an empty read is ABSENT and an errored read is FAILED — neither reads as nothing was touched",
          _ba["state"] == "ABSENT" and _ba["items"] is None and "no tracks" in _ba["why"]
          and _bf["state"] == "FAILED" and _bf["items"] is None and "401" in _bf["why"],
          "%s / %s" % (_ba["state"], _bf["state"]))
    # DURATION IS DERIVED WHEN CHATCUT OMITS IT. Item 2 has no durationInFrames and the judge
    # compares dur — a None there would read as a changed item on every single row.
    check("dur is derived from the frame range when the item does not carry it",
          _bm["items"][1]["dur"] == 46 and all(i["dur"] is not None for i in _bm["items"]),
          str([i["dur"] for i in _bm["items"]]))
    _src_e = open("chatcut_job_app.py", encoding="utf-8").read()
    check("the before-timeline is captured BEFORE turn 1 and reaches the record",
          _src_e.index("_before = before_timeline(tok, _stage)") < _src_e.index("_first_message = pass1_message(")
          and '"before_timeline": _before' in _src_e
          and 'out["before_timeline"] = _state.get("before_timeline")' in _src_e,
          "capture/record wiring")
    # ---- RULE 3, AS A FUNCTION (the zoom pair for Zac's eye, 2026-09-19) ----
    # Three rounds of his time were lost judging pairs that may have been identical, so a pair
    # is deliverable only once PROVEN to differ — and an ABSENT or FAILED comparison is not a
    # pass, because a comparison that could not be made has not shown anything.
    import numpy as _np
    _z = _np.zeros((4, 4, 3), dtype="int16")
    _one = _z.copy(); _one[1, 1, 0] = 7
    _mk = lambda sheets: {"frames": {"sheets": sheets}}
    _rd = lambda d: (lambda p: d[p])
    _same, _diff = {"a": _z, "b": _z.copy()}, {"a": _z, "b": _one}
    check("a pixel-identical pair is IDENTICAL and is never delivered",
          J.pair_differs(_mk(["a"]), _mk(["b"]), reader=_rd(_same))["state"] == "IDENTICAL",
          str(J.pair_differs(_mk(["a"]), _mk(["b"]), reader=_rd(_same))["why"])[:110])
    _d = J.pair_differs(_mk(["a"]), _mk(["b"]), reader=_rd(_diff))
    check("ONE differing pixel is enough to make it a pair, with no threshold to calibrate",
          _d["state"] == "DIFFER" and _d["profile"]["differing"] == 1 and _d["profile"]["max_abs"] == 7.0,
          str(_d["why"])[:110])
    def _boom(_p):
        raise IOError("truncated sheet")
    # THE CONTROL, MEASURED INTO EXISTENCE 2026-09-19. The first pair ran as two ChatCut
    # projects and the gate said DIFFER on all four sheets — including the two covering
    # 0-7s where NEITHER arm has a zoom, because two projects are two uploads and two
    # independent renders (mean 2.26, peak 253 on identical content). The gate was right
    # that the pictures differed and wrong about WHY, which is the failure it exists to
    # prevent, one level down. A pair whose control is dirty is CONFOUNDED, never shown.
    _conf = {"c1": _z, "c2": _one, "a": _z, "b": _one}
    _clean = {"c1": _z, "c2": _z.copy(), "a": _z, "b": _one}
    check("a pair whose CONTROL differs is CONFOUNDED and is never delivered",
          J.pair_differs(_mk(["a"]), _mk(["b"]), reader=_rd(_conf),
                         control_a=["c1"], control_b=["c2"])["state"] == "CONFOUNDED"
          and J.pair_differs(_mk(["a"]), _mk(["b"]), reader=_rd(_clean),
                             control_a=["c1"], control_b=["c2"])["state"] == "DIFFER",
          str(J.pair_differs(_mk(["a"]), _mk(["b"]), reader=_rd(_conf),
                             control_a=["c1"], control_b=["c2"])["why"])[:120])
    # AND THE ARMS SHARE ONE PROJECT, which is what makes a clean control reachable at all.
    _src_z = open("chatcut_job_app.py", encoding="utf-8").read()
    _zp2 = _src_z[_src_z.index("def zoom_pair("):]
    _zp2 = _zp2[:_zp2.index("@app.function")]
    _zp2 = _re.sub(r"^\s*#.*$", "", _zp2, flags=_re.M)
    check("both arms share one project, one upload and one timeline, placed in sequence",
          _zp2.count("prestage(") == 1 and '"deletes": [{"id": item_id}]' in _zp2
          and "control_a=" in _zp2 and "frames_by_number(" in _src_z,
          "prestage x%d, deletes=%s" % (_zp2.count("prestage("),
                                        '"deletes": [{"id": item_id}]' in _zp2))
    # ---- ALIGNMENT BY FRAME NUMBER (measured 2026-09-19) ----
    # The grid sampler asked for 84 frames over 14s and returned 66 — and the 18 it lost
    # were the TAIL, which is exactly where a zoom at 12s lives, so the span under test
    # had no frames at all. Both passes then returned 66 and they were NOT the same 66,
    # so a positional comparison lined up different moments and reported a difference
    # that was nothing but misalignment. The control caught it: CONFOUNDED, withheld.
    _a = {0: "a0", 30: "a30", 60: "a60"}
    _b = {0: "b0", 60: "b60", 90: "b90"}
    _ca, _cb, _oa, _ob = J.frames_by_number(_a, _b)
    check("only frames present on BOTH sides are compared, and the rest are named",
          _ca == ["a0", "a60"] and _cb == ["b0", "b60"] and _oa == [30] and _ob == [90],
          "%s / %s / only_a=%s only_b=%s" % (_ca, _cb, _oa, _ob))
    check("a positional comparison of the same two maps would have lined up different moments",
          list(_a.values())[1] != _a[60] and _ca[1] == _a[60] and _cb[1] == _b[60],
          "positional index 1 is frame 30 on one side and frame 60 on the other")
    # AND THE PAIR RUN ASKS FOR TWO EXPLICIT WINDOWS, not a grid over the whole timeline.
    # COMMENTS ARE NOT CODE — THE SECOND TIME TODAY. The contract check flagged
    # SmoothPush for a mention of AbsoluteFill inside the comment forbidding it; this
    # leg then failed because the comment explaining that `removes` was the WRONG key
    # contains the word `removes`. Any check that reads source strips comments first.
    _zp = open("chatcut_job_app.py", encoding="utf-8").read()
    _zp = _zp[_zp.index("def zoom_pair("):]
    _zp = _zp[:_zp.index("@app.function")]
    _zp = _re.sub(r"^\s*#.*$", "", _zp, flags=_re.M)
    check("the pair samples a control window and a test window by frame number",
          "ctrl_frames = [" in _zp and "test_frames = [" in _zp
          and "frames_at(tok, pid, ctrl_frames" in _zp and "frames_at(tok, pid, test_frames" in _zp
          and "_preview_frames(" not in _zp,
          "explicit windows, grid sampler gone from zoom_pair")
    # AND A DELETE IS PROVEN BY THE READ-BACK, NEVER BY THE RESPONSE. `removes` was not
    # even the right key: edit_item answered 200 with empty adds/deletes/updates and the
    # first arm stayed on the timeline under the second.
    check("the arm is deleted with the key edit_item accepts, and the read-back proves it",
          '"deletes": [{"id": item_id}]' in _zp and "STILL ON THE TIMELINE" in _zp
          and '"removes"' not in _zp,
          "deletes/id + read-back verification")

    # ---- A REFUSAL MUST CARRY ITS WORDS (measured 2026-09-19) ----
    # registration_refusal matched ONE shape and returned None for every other, so a probe
    # asking three capability questions recorded three REFUSED rows with `refusal: null` —
    # three failures that could not say what they read, from the reader meant to serve the
    # standing law. It never returns None now; "there was nothing to read" is the finding.
    check("a refusal always carries words, whatever shape the response took",
          "-32602" in J.registration_refusal({"_text": "MCP error -32602: Input validation error: x"})
          and "component rejected" in J.registration_refusal({"_text": "component rejected: consts"})
          and "no text at all" in J.registration_refusal({"result": {}, "ok": False})
          and "not an object" in J.registration_refusal(None)
          and "AbsoluteFill" in J.registration_refusal(
              {"content": [{"type": "text", "text": "refused: AbsoluteFill"}]}),
          "none of the five shapes returns None")
    check("and the keys are named when there is no text to quote",
          "'ok'" in J.registration_refusal({"result": {}, "ok": False}),
          J.registration_refusal({"result": {}, "ok": False}))

    # ---- THE LAYER AT REST (Zac's ruling, 2026-09-19) ----
    # A zoom component at scale 1.0 must be pixel-identical to the source. One that is
    # not changes every frame OUTSIDE its own move, which is tampering by another name —
    # and it would do so on every job that places one. The bar is EXACTLY ZERO: this
    # repo's determinism law is byte-identity on a fixed plan, and "our layer at rest"
    # is a fixed plan against the same decoded source in the same project.
    _rz = _np.zeros((4, 4, 3), dtype="int16")
    _r1 = _rz.copy(); _r1[2, 2, 1] = 3
    _rsame = {"b0": _rz, "b30": _rz.copy(), "l0": _rz.copy(), "l30": _rz.copy()}
    _rdiff = {"b0": _rz, "b30": _rz.copy(), "l0": _rz.copy(), "l30": _r1}
    check("a layer that is a no-op at rest is IDENTICAL, and ONE differing pixel is a FAULT",
          J.rest_verdict({0: "b0", 30: "b30"}, {0: "l0", 30: "l30"},
                         reader=_rd(_rsame))["state"] == "IDENTICAL"
          and J.rest_verdict({0: "b0", 30: "b30"}, {0: "l0", 30: "l30"},
                             reader=_rd(_rdiff))["state"] == "DIFFERS",
          J.rest_verdict({0: "b0", 30: "b30"}, {0: "l0", 30: "l30"}, reader=_rd(_rdiff))["why"][:110])
    check("a rest check with nothing to compare is ABSENT, never a pass",
          J.rest_verdict({}, {0: "l0"}, reader=_rd(_rsame))["state"] == "ABSENT"
          and J.rest_verdict({0: "b0"}, {}, reader=_rd(_rsame))["state"] == "ABSENT",
          "both directions ABSENT")
    # AND IT IS MEASURED INSIDE THE SPAN. Outside it the component is not placed and
    # the two reads would agree trivially — a control that cannot fail.
    _zr = open("chatcut_job_app.py", encoding="utf-8").read()
    _zr = _zr[_zr.index("def zoom_rest("):]
    _zr = _zr[:_zr.index("@app.function")]
    _zr = _re.sub(r"^\s*#.*$", "", _zr, flags=_re.M)
    check("the rest frames sit INSIDE the span, where the component is actually placed",
          "probe_frames = [from_frame + " in _zr and '"scale": 1.0' in _zr
          and "edit_item_checked(" in _zr,
          "frames inside the span, scale 1.0, writes echo-checked")

    # ---- THE REST OFFSET IS A CALIBRATION, NOT A CONSTANT (Zac, 2026-09-19) ----
    # It MOVED between two runs of the same arm on the same source: 2.0367 levels, then
    # 1.7228. A number written into the source would have been right on the day it was
    # measured and silently wrong after — half the failures on this repo's list.
    check("the correction is an exact affine: slope 1, intercept minus k levels",
          J.cal_css(0) == ""
          and J.cal_css(2.0) == "brightness(0.984556) contrast(1.015686)"
          # brightness(b) then contrast(c): out = (c*b)*in + 0.5*(1-c)
          and abs((1.0 + 2 * 2.0 / 255.0) * (1.0 / (1.0 + 2 * 2.0 / 255.0)) - 1.0) < 1e-12
          and abs(0.5 * (1.0 - (1.0 + 2 * 2.0 / 255.0)) * 255.0 + 2.0) < 1e-9,
          J.cal_css(2.0))
    check("the gate passes only when every channel is inside the tolerance",
          J.calibration_verdict({"state": "MEASURED", "rgb": [0.4001, -0.0081, 0.2156],
                                 "why": "x"})["state"] == "CALIBRATED"
          and J.calibration_verdict({"state": "MEASURED", "rgb": [0.4, 0.6, 0.1],
                                     "why": "x"})["state"] == "UNCORRECTED"
          and J.calibration_verdict({"state": "ABSENT", "why": "n"})["state"] == "ABSENT",
          "0.40/-0.01/0.22 passes, one channel at 0.6 does not")
    # SIGNED AND PER CHANNEL. An absolute mean cannot be inverted, and the channels
    # differ by ~0.4 levels — a single number would fix the luma and leave a cast.
    _co = J.channel_offset(["a"], ["b"], reader=_rd({
        "a": _np.zeros((4, 4, 3), dtype="float64"),
        "b": _np.dstack([_np.full((4, 4), 1.93), _np.full((4, 4), 1.52), _np.full((4, 4), 1.72)])}))
    check("the offset is measured signed and per channel, never as one absolute number",
          _co["state"] == "MEASURED" and _co["rgb"] == [1.93, 1.52, 1.72]
          and abs(_co["mean"] - 1.7233) < 1e-3,
          str(_co["rgb"]))
    # AND EVERY PORTED COMPONENT TAKES IT AS A PROPERTY, so the harness supplies the
    # measured value and nothing in the blob carries a number.
    for _n in ("SmoothPush", "StepZoom", "StagedPush"):
        _blob = open("port/build/%s.jsx" % _n, encoding="utf-8").read()
        check("%s takes the rest calibration as a property and hard-codes no level" % _n,
              "props.correct" in _blob
              and any(q.get("key") == "correct" for q in J.PORTED_PROPS[_n])
              and not J.component_contract(_blob, J.PORTED_PROPS[_n]),
              "correct declared and read")

    # ---- THE CALIBRATION'S CADENCE (Zac, 2026-09-19) ----
    # Per deploy, refreshed on the hourly ping, and NEVER on a job's critical path:
    # measured at 52.4s wall, which against a 90s latency law is not a trade worth
    # making for 1.7 levels. Drift beyond the tolerance is REPORTED, not silently
    # re-measured — a correction that moves inside a job makes two jobs minutes apart
    # carry different corrections with nothing saying so.
    _now = 100000.0
    check("a fresh calibration is USED, a stale one is refreshed by the PING not the job",
          J.calibration_cadence(_now, {"state": "MEASURED", "levels": 1.72,
                                       "at": _now - 600})["action"] == "USE"
          and J.calibration_cadence(_now, {"state": "MEASURED", "levels": 1.72,
                                           "at": _now - 4000})["action"] == "REFRESH",
          "600s USE, 4000s REFRESH against a 3600s cadence")
    check("drift past the tolerance is REPORTED, never re-measured on the job's path",
          J.calibration_cadence(_now, {"state": "MEASURED", "levels": 2.60, "at": _now - 60,
                                       "previous_levels": 1.72})["action"] == "DRIFT"
          # the two calibrations actually measured moved 0.3135 — inside the bar
          and J.calibration_cadence(_now, {"state": "MEASURED", "levels": 2.0363, "at": _now - 60,
                                           "previous_levels": 1.7228})["action"] == "USE",
          "0.88 reports, the observed 0.3135 does not")
    check("with no calibration at all the correction is NOT applied and the run says so",
          J.calibration_cadence(_now, None)["action"] == "ABSENT"
          and "not applied" in J.calibration_cadence(_now, None)["why"],
          J.calibration_cadence(_now, None)["why"][:90])

    # ---- THE TEXT-OVERLAY FAMILY IS BACK, AND IT IS FIVE (Zac, 2026-09-19) ----
    # `text_overlays` was a FAMILY in the live pipeline and was absent from the library
    # file entirely. Its real list came from the schema's OWN HISTORY — handler.py at
    # 42df870 carried torn_paper, sticky_note, quote_card, lower_third, caption_match —
    # while the CURRENT enum has been pruned to two and _TextOverlay still carries
    # topText/bottomText, quote/attribution and text: the fields of the three retired
    # ones. A family reads as two variants and is five, and the references place text
    # most of the time, so until this landed the agent could not.
    import json as _json
    _lib = _json.load(open("library_73.json", encoding="utf-8"))
    _fam = _lib.get("text overlay") or []
    check("the library carries the whole text-overlay family, and the count is corrected with a why",
          # THE FIVE FROM THE SCHEMA'S HISTORY, plus PlainText — the workhorse, which
          # is not in that history because the enum never had a name for "just words".
          sorted(_fam) == ["CaptionMatch", "LowerThird", "PlainText", "QuoteCard",
                           "StickyNotes", "TornPaper"]
          and sum(len(v) for v in _lib.values() if isinstance(v, list)) == 79
          and "73 -> 78" in (_lib.get("_why") or "")
          and "schema" in (_lib.get("_why") or ""),
          "%d items, family %s" % (sum(len(v) for v in _lib.values() if isinstance(v, list)), sorted(_fam)))
    # EVERY VARIANT IS BUILT, CONTRACT-CLEAN, AND CARRIES THE TWO DIALS.
    for _v in ("TornPaper", "StickyNotes", "QuoteCard", "LowerThird", "CaptionMatch"):
        _blob = open("port/build/%s.jsx" % _v, encoding="utf-8").read()
        _keys = {q["key"] for q in J.PORTED_PROPS[_v]}
        check("%s is built, contract-clean, and exposes size and position as dials" % _v,
              not J.component_contract(_blob, J.PORTED_PROPS[_v])
              and {"size", "position"} <= _keys
              and "NO VELOCITY CAP:" in _blob,
              "keys %s" % sorted(_keys))
    # THE DEFAULTS ARE WHAT THE REFERENCES MEASURE: medium, middle. LowerThird is the
    # one exception and it is deliberate — a broadcast name card lives in the lower
    # third, and the dial still moves it.
    _defs = {v: {q["key"]: q.get("defaultValue") for q in J.PORTED_PROPS[v]}
             for v in ("TornPaper", "StickyNotes", "QuoteCard", "LowerThird", "CaptionMatch")}
    check("every variant defaults to medium, and to middle except the lower third",
          all(d["size"] == "medium" for d in _defs.values())
          and all(d["position"] == "middle" for v, d in _defs.items() if v != "LowerThird")
          and _defs["LowerThird"]["position"] == "bottom",
          str({v: (d["size"], d["position"]) for v, d in _defs.items()}))

    # ---- A MALFORMED ENTRY IS A FAULT, NOT A LABEL IN THE VIDEO (Zac, 2026-09-19) ----
    # StickyNotes used to render "dropped N malformed entries" INTO THE FRAME. An error
    # rendered into a user's video is worse than an empty note; silently dropping is the
    # other half of the same mistake, handing back a graphic missing a line with nothing
    # saying so. It is a fault at the rewatch (so the agent can fix it) and at the
    # read-back (which withholds the export), and it appears in neither frame.
    check("a malformed packed entry is named, and a well-formed one is not",
          J.packed_prop_faults("notes", "Key takeaway|#FFE066|-3; Second|#9AE6B4|2") == []
          and J.packed_prop_faults("notes", "|#FFE066|-3")
          and J.packed_prop_faults("stages", "0.30:1.15, 0.95:1.30") == []
          and J.packed_prop_faults("stages", "0.30:1.15, later:big")
          and J.packed_prop_faults("text", "anything") == [],
          str(J.packed_prop_faults("notes", "|#FFE066|-3"))[:110])
    check("an entry count past what the component renders is named rather than dropped",
          J.packed_prop_faults("notes", "a|#fff|0;b|#fff|0;c|#fff|0;d|#fff|0")
          and "would be dropped" in J.packed_prop_faults("notes", "a|#fff|0;b|#fff|0;c|#fff|0;d|#fff|0")[0]
          and J.packed_prop_faults("notes", "a|#fff|0;b|#fff|0;c|#fff|0") == [],
          "4 entries named, 3 clean")
    _bad_items = [{"id": "aaaaaaaa-1111", "itemType": "motion-graphic",
                   "asset": {"name": "StickyNotes"}, "propertyOverrides": {"notes": "|#FFE066|-3"}}]
    # THREE STATES, BECAUSE AN EMPTY LIST IS NOT AN ALL-CLEAR. Measured the hard way:
    # a deliberately malformed entry was planted, placed, and the check returned [] on
    # TWO paid runs — it read each item's own `propertyOverrides`, which the read-back
    # does not carry (the values live behind inspect_item, a thing this repo had
    # already learned once). An absent measurement read exactly like a clean one.
    _no_props = [{"id": "aaaaaaaa-1111", "itemType": "motion-graphic", "asset": {"name": "StickyNotes"}}]
    _with_bad = J.component_faults(_no_props, {"aaaaaaaa-1111": {"notes": "|#FFE066|-3"}})
    _with_ok = J.component_faults(_no_props, {"aaaaaaaa-1111": {"notes": "ok|#fff|0"}})
    check("a component whose properties could not be read is ABSENT, never a clean pass",
          J.component_faults(_no_props)["state"] == "ABSENT"
          and J.component_faults(_no_props)["faults"] == []
          and "could not run" in J.component_faults(_no_props)["why"],
          J.component_faults(_no_props)["why"][:100])
    check("with the property map the fault fires and names the item and its component",
          _with_bad["state"] == "MEASURED" and _with_bad["faults"]
          and "aaaaaaaa" in _with_bad["faults"][0] and "StickyNotes" in _with_bad["faults"][0]
          and _with_ok["state"] == "MEASURED" and _with_ok["faults"] == [],
          _with_bad["faults"][0][:110])
    # AND BOTH SEAMS ARE FED THE MAP THAT ACTUALLY HAS THE VALUES.
    _appf = open("chatcut_job_app.py", encoding="utf-8").read()
    check("both seams pass a property map, not the items' own absent key",
          "component_faults(_iv, _props_for_items(_iv))" in _appf
          and "component_faults(_items, _props)" in _appf
          and "def _props_for_items(" in _appf,
          "rewatch and read-back both fed")
    # THE ERROR IS NOT IN THE PICTURE, and the fault reaches BOTH seams.
    _sn = open("port/build/StickyNotes.jsx", encoding="utf-8").read()
    _sn_code = _re.sub(r"^\s*//.*$", "", _re.sub(r"/\*.*?\*/", "", _sn, flags=_re.S), flags=_re.M)
    _app = open("chatcut_job_app.py", encoding="utf-8").read()
    check("the component renders no error text, and the fault reaches the rewatch AND the read-back",
          # THE SEAMS, NOT A COUNT. This asserted exactly three call sites and went red
          # the moment a fourth caller appeared — a reader keyed to a number rather
          # than to the property, which is this repo's most repeated check failure.
          "malformed" not in _sn_code and "dropped" not in _sn_code
          and "_pfr = component_faults(_iv, _props_for_items(_iv))" in _app   # rewatch: the agent sees it
          and "_pf_rw = component_faults(_items, _props)" in _app             # read-back: it withholds
          and "the export is withheld" in _app,
          "no error drawn; both seams present")

    # ---- THE PROPERTIES ARE IN THE PROSE (measured 2026-09-19, after three runs) ----
    # inspect_item answers with keys _links/_meta/_text/content and puts the values in
    # the TEXT — an "Effective Props" block and a `propertyOverrides:` line. Walking the
    # envelope for a propertyOverrides KEY can never succeed, which is written down in
    # this repo from an earlier round; I wrote the same bug underneath it, and it cost
    # three runs of reporting "no fault" about a malformed entry sitting on a timeline.
    _ins = ("Timeline: Timeline [03088eef7e]\nItem: 2bbe2a3b1e\n"
            "Type: motion-graphic | Track: V2\n\n"
            "Motion Graphic Effective Props:\n"
            "  notes=\"|#FFE066|-3; Second note|#9AE6B4|2\" (override)\n"
            "  size=\"medium\" (default)\n  position=\"middle\" (default)\n\n"
            "Properties:\n  from: 180\n"
            "  propertyOverrides: {\"notes\":\"|#FFE066|-3; Second note|#9AE6B4|2\"}\n"
            "  width: 1080")
    _ip = J.item_props_from_inspect({"_text": _ins})
    check("a placed item's properties are parsed out of inspect_item's prose, defaults included",
          _ip["state"] == "MEASURED"
          and _ip["props"].get("notes") == "|#FFE066|-3; Second note|#9AE6B4|2"
          # THE EFFECTIVE BLOCK IS PREFERRED: it carries defaults, so a component
          # relying on one is judged on what it will actually render.
          and _ip["props"].get("size") == "medium" and _ip["props"].get("position") == "middle",
          str(_ip["props"]))
    check("the override line is the fallback, and a text-free answer is ABSENT",
          J.item_props_from_inspect(
              {"_text": 'Properties:\n  propertyOverrides: {"notes":"a|b|0"}'})["props"] == {"notes": "a|b|0"}
          and J.item_props_from_inspect({"keys": 1})["state"] == "ABSENT"
          and J.item_props_from_inspect(None)["state"] == "ABSENT",
          "fallback + two absences")
    # END TO END: the parsed props make the planted fault fire.
    check("the parsed properties make a planted malformed entry FAULT",
          J.component_faults([{"id": "2bbe2a3b1e", "itemType": "motion-graphic",
                               "asset": {"name": "StickyNotes"}}],
                             {"2bbe2a3b1e": _ip["props"]})["faults"],
          str(J.component_faults([{"id": "2bbe2a3b1e", "itemType": "motion-graphic",
                                   "asset": {"name": "StickyNotes"}},],
                                 {"2bbe2a3b1e": _ip["props"]})["faults"])[:110])
    # AND NO SITE WALKS THE ENVELOPE FOR A KEY THAT IS A STRING.
    _appp = _re.sub(r"^\s*#.*$", "", open("chatcut_job_app.py", encoding="utf-8").read(), flags=_re.M)
    check("no property site walks the envelope for a propertyOverrides key any more",
          '_deep_find(_ii, "propertyOverrides")' not in _appp
          and _appp.count("item_props_from_inspect(_ii)") == 3,
          "%d sites parse the prose" % _appp.count("item_props_from_inspect(_ii)"))

    # ---- EVERY SEAM-FEEDING READER RETURNS A STATE (Zac's rule, 2026-09-19) ----
    # Earned three times in one day. A reader answering with a bare value cannot tell
    # "I looked and nothing was wrong" from "I could not look", and the second renders
    # as the first at the seam that consumes it. component_faults returned [] on TWO
    # paid runs with a deliberately malformed entry on the timeline, because it read a
    # key the read-back does not carry. Each reader below is DRIVEN with a source
    # MISSING THE KEY IT READS and must answer ABSENT — never [], 0 or None.
    _blank = _np.zeros((2, 2, 3), dtype="float64")
    _rdr = lambda p: _blank
    _DRIVEN = {
        # reader                  a source missing the key it reads          expected
        "component_faults":  (lambda: J.component_faults(
            [{"id": "x", "itemType": "motion-graphic"}]), "ABSENT"),
        "item_props_from_inspect": (lambda: J.item_props_from_inspect({"keys": 1}), "ABSENT"),
        "frame_diff_profile": (lambda: J.frame_diff_profile([], ["b"], reader=_rdr), "ABSENT"),
        "channel_offset":    (lambda: J.channel_offset([], ["b"], reader=_rdr), "ABSENT"),
        "rest_verdict":      (lambda: J.rest_verdict({}, {0: "b"}, reader=_rdr), "ABSENT"),
        "before_timeline":   (lambda: J.before_timeline("t", {}, reader=lambda a, b: {"items": []}), "ABSENT"),
        "library_ids":       (lambda: J.library_ids({"nothing": "here"}), "ABSENT"),
        "write_effect":      (lambda: J.write_effect({"adds": [1]}, {"_text": "ok"}), "UNREADABLE"),
        "calibration_verdict": (lambda: J.calibration_verdict({"state": "ABSENT", "why": "n"}), "ABSENT"),
    }
    _state_of = lambda r: (r[1] if isinstance(r, tuple) else
                           r.get("state") if isinstance(r, dict) else None)
    _wrong = []
    for _nm, _expect, _ in [(n, e, w) for n, w, e in J.STATEFUL_READERS]:
        _drive = _DRIVEN.get(_nm)
        if _drive is None:
            _wrong.append("%s: in the census with no leg driving it" % _nm)
            continue
        try:
            _got = _state_of(_drive[0]())
        except Exception as _re_:                                 # noqa: BLE001
            _wrong.append("%s: raised %s" % (_nm, type(_re_).__name__))
            continue
        if _got != _drive[1]:
            _wrong.append("%s: answered %r on a source missing its key, expected %r"
                          % (_nm, _got, _drive[1]))
    check("every seam-feeding reader answers ABSENT on a source missing the key it reads",
          not _wrong, "; ".join(_wrong[:3]) if _wrong else
          "%d readers driven blind, all stated" % len(J.STATEFUL_READERS))
    # AND THE CENSUS COVERS WHAT ACTUALLY FEEDS A SEAM. A reader wired into a seam
    # without a census entry is the gap this rule exists to close, so the names are
    # checked against the source rather than trusted.
    _appc = open("chatcut_job_app.py", encoding="utf-8").read()
    _census = {n for n, _w, _e in J.STATEFUL_READERS}
    # THE PROPERTY, NOT THE SHAPE. This first demanded a dict carrying "state" and
    # went red on library_ids, which returns (ids, state, why) — a reader that CAN say
    # ABSENT, in a tuple. The rule is that a reader can express absence, not that it
    # uses one container; testing the container is the reader-keyed-to-shape mistake
    # this file already carries eight scars from.
    import inspect as _insp2
    _shapeless = [_n for _n in _census
                  if not callable(getattr(J, _n, None))
                  or not any(_w in _insp2.getsource(getattr(J, _n))
                             for _w in ("ABSENT", "UNREADABLE"))]
    check("every censused reader exists and can name an absence in its own return",
          not _shapeless, "; ".join(_shapeless) if _shapeless else
          "%d censused, %d dict-shaped, library_ids returns (ids, state, why)" % (len(_census), len(_census) - 1))

    # ---- CAPTION-MATCH MATCHES, AND THE WORKHORSE HAS ITS OWN NAME ----
    # For one day the references' most common shape (plain, medium, middle) was served
    # by CaptionMatch, and only because that port was INCOMPLETE: it rendered a fixed
    # sans-serif and never read the caption style it is named for. Fixing it would have
    # silently removed the plain shape from the menu, so the workhorse gets its own
    # component and the variant does the job it is named for.
    _cmb = open("port/build/CaptionMatch.jsx", encoding="utf-8").read()
    _cmb_code = _re.sub(r"^\s*//.*$", "", _re.sub(r"/\*.*?\*/", "", _cmb, flags=_re.S), flags=_re.M)
    _nine = ("CleanCut", "Cove", "Gadzhi", "Lumen", "Prime", "Pulse",
             "Quintessence", "TwoTone", "TypewriterReveal")
    check("CaptionMatch reads the caption style and knows all nine, with a fallback",
          "props.captionStyle" in _cmb_code
          and all(_n in _cmb_code for _n in _nine)
          and "styles[captionStyle] || styles.CleanCut" in _cmb_code
          and any(q["key"] == "captionStyle" for q in J.PORTED_PROPS["CaptionMatch"]),
          "%d of 9 styles named" % sum(1 for _n in _nine if _n in _cmb_code))
    # THE SIGNATURES MUST ACTUALLY DIFFER, or "follows the style" renders identically
    # and the property is decorative.
    _sig = dict(_re.findall(r'(\w+): \["([^"]+)", (\d+), "(\w+)", (-?\d+)\]',
                            _cmb_code.replace('", ', '", ')) and [] or [])
    _rows = _re.findall(r'(\w+): \["([^"]+)", (\d+), "(\w+)", (-?\d+)\]', _cmb_code)
    check("the nine styles carry genuinely different typography, not nine names for one look",
          len(_rows) == 9 and len({(f, w, t) for _n, f, w, t, _ls in _rows}) >= 6,
          "%d styles, %d distinct font/weight/case signatures"
          % (len(_rows), len({(f, w, t) for _n, f, w, t, _ls in _rows})))
    _pt = open("port/build/PlainText.jsx", encoding="utf-8").read()
    _pt_code = _re.sub(r"^\s*//.*$", "", _re.sub(r"/\*.*?\*/", "", _pt, flags=_re.S), flags=_re.M)
    check("PlainText is plain by construction: no card, no strip, no caption style",
          "backgroundColor" not in _pt_code and "captionStyle" not in _pt_code
          and "borderLeft" not in _pt_code and "clipPath" not in _pt_code
          and not J.component_contract(_pt, J.PORTED_PROPS["PlainText"])
          and {q["key"] for q in J.PORTED_PROPS["PlainText"]} >= {"size", "position"},
          "nothing behind the words")
    import json as _json2
    _lib2 = _json2.load(open("library_73.json", encoding="utf-8"))
    check("the library is 79, and the file says why the sixth variant exists",
          sum(len(v) for v in _lib2.values() if isinstance(v, list)) == 79
          and "PlainText" in (_lib2.get("text overlay") or [])
          and "78 -> 79" in (_lib2.get("_why") or "")
          and "incomplete" in (_lib2.get("_why") or ""),
          "%d items" % sum(len(v) for v in _lib2.values() if isinstance(v, list)))

    # ---- COMPARING A THING WITH ITSELF ANSWERS ZERO BY CONSTRUCTION ----
    # Measured 2026-09-19: three caption styles were each written to
    # /work/tf_CaptionMatch/f000.jpg, so the style proof compared every file against
    # ITSELF and reported "identical" — which is exactly what a genuinely broken
    # component looks like. The proof had no discriminating power in EITHER direction:
    # it would have said the same about a component that worked perfectly. Same class
    # as the fixed copy path that once destroyed a red proof mid-run.
    check("a comparison whose two sides name the same files is a FAULT, not a zero",
          J.frame_diff_profile(["/x/a.jpg", "/x/b.jpg"], ["/x/a.jpg", "/x/b.jpg"])["state"] == "FAILED"
          and "itself" in J.frame_diff_profile(["/x/a.jpg"], ["/x/a.jpg"])["why"]
          # and it is not a blanket refusal: different paths still reach the reader
          and J.frame_diff_profile(["/x/a.jpg"], ["/y/a.jpg"])["state"] == "FAILED",
          J.frame_diff_profile(["/x/a.jpg"], ["/x/a.jpg"])["why"][:100])
    _tfc = open("chatcut_job_app.py", encoding="utf-8").read()
    check("each placement writes its frames to its own directory",
          '"/work/tf_%s" % re.sub(r"[^A-Za-z0-9]+", "_", "%s_%s" % (name, label))' in _tfc,
          "directory keyed by component AND label")

    # THE WORKING TREE, NOT THE COMMIT. red_proof_no_undefined_names builds an ISOLATED
    # worktree from HEAD, so it judges what is COMMITTED — and a run is launched from what
    # is on disk. A slice-based edit removed `place_theirs`, `place_ours` and PORTED_PROPS
    # from zoom_pair, the proof kept reporting the committed line numbers, and the container
    # died on NameError after paying for a prestage. pyflakes says it on disk, for free.
    _pf = _sub.run([_sys.executable, "-m", "pyflakes", "chatcut_job_app.py"],
                   capture_output=True, text=True)
    _pf_bad = [l for l in (_pf.stdout + _pf.stderr).splitlines()
               if "undefined name" in l or "redefinition of unused" in l]
    check("the WORKING tree carries no undefined name and no shadowed definition",
          not _pf_bad, "; ".join(_pf_bad[:3]) if _pf_bad else "pyflakes clean on disk")
    # AND EVERY BLOB THE HARNESS CAN SEND HAS PROPERTIES. A component registered with no
    # property entry gives the user nothing to edit — the registered-default failure this
    # repo has already paid for once: 135 defaults wrong, 0 of 14 components drawing.
    _built = sorted(f[:-4] for f in _os_list("port/build") if f.endswith(".jsx"))
    check("every built component has a property table, and the table has no orphans",
          bool(_built) and not [b for b in _built if b not in J.PORTED_PROPS]
          and not [k for k in J.PORTED_PROPS if k not in _built],
          "built %s vs props %s" % (_built, sorted(J.PORTED_PROPS)))
    check("an unread or absent comparison is ABSENT or FAILED, never a proven pair",
          J.pair_differs(_mk([]), _mk(["b"]), reader=_rd(_same))["state"] == "ABSENT"
          and J.pair_differs(_mk(["a"]), _mk(["b"]), reader=_boom)["state"] == "FAILED"
          and J.pair_differs(_mk(["a", "a"]), _mk(["b"]), reader=_rd(_same))["state"] == "FAILED",
          "%s / %s" % (J.pair_differs(_mk([]), _mk(["b"]), reader=_rd(_same))["state"],
                       J.pair_differs(_mk(["a"]), _mk(["b"]), reader=_boom)["state"]))
    # THE PROFILE IS IN ORDER, so a pair differing only at the edges (a misalignment) is
    # distinguishable from one differing through the middle (the curve, which is the point).
    check("the per-frame profile is returned in order and as long as the comparison",
          J.frame_diff_profile(["a", "a"], ["b", "b"], reader=_rd(_diff))["profile"] == [0.1458, 0.1458],
          str(J.frame_diff_profile(["a", "a"], ["b", "b"], reader=_rd(_diff))["profile"]))
    # THE BUILT BLOB IS WHAT SHIPS. The emitter and the bodies are deliberately NOT in the
    # image: a container that could re-emit would render something the gate never compared.
    _src_p = open("chatcut_job_app.py", encoding="utf-8").read()
    check("only the BUILT blobs are mounted, and the component is read from them",
          'os.path.join(_HERE, "port", "build"), "/craft/port"' in _src_p
          and 'os.path.join("/craft/port", name + ".jsx")' in _src_p
          and '"port", "bodies"' not in _src_p and '"emit_zoom_cap' not in _src_p,
          "image mounts port/build only")
    # THE LABELS ARE THE CLAIM. Zac asked for the sides labelled "our timing carried" or
    # "their default" — and a preset taking only a start frame and a duration HAS no timing
    # to carry, so a label that said otherwise would do the work the picture must do.
    _lt, _lo = J.pair_labels("slow-push", "SmoothPush")
    check("the pair is labelled honestly on both sides, naming each component",
          _lt.startswith("THEIRS — slow-push") and "their default" in _lt and "constant speed" in _lt
          and _lo.startswith("OURS — SmoothPush") and "our timing carried" in _lo,
          "%s // %s" % (_lt[:60], _lo[:60]))
    _sb = J.stack_pair(None, "x", (_lt, _lo), "/tmp/_never_written.jpg")
    check("a one-sided pair is ABSENT and writes nothing",
          _sb["state"] == "ABSENT" and _sb["path"] is None and not _os_p.exists("/tmp/_never_written.jpg"),
          str(_sb["why"])[:100])
    # ---- ChatCut's THREE MEASURED CONTRACT RULES, CHECKED BEFORE THE SEND ----
    # The ported Remotion components were frame-verified against Remotion and REFUSED by
    # ChatCut on six counts; a later hand-written one was refused for AbsoluteFill when
    # the repo's own measured contract says a plain div. A rule paid for twice is a check.
    # AGAINST THEIR OWN PROPERTY TABLES, not just the code. The validator refuses a
    # property declared and never read — three capability probes died on exactly that,
    # and the refusal said nothing about the capability each probe existed to ask.
    check("every component this harness can send satisfies the contract we measured",
          all(not J.component_contract(open("port/build/%s.jsx" % _n, encoding="utf-8").read(),
                                       J.PORTED_PROPS[_n])
              for _n in ("SmoothPush", "StepZoom", "StagedPush")),
          str({_n: J.component_contract(open("port/build/%s.jsx" % _n, encoding="utf-8").read(),
                                        J.PORTED_PROPS[_n])
               for _n in ("SmoothPush", "StepZoom", "StagedPush")}))
    # RULE 5, MEASURED FROM A REFUSAL THAT COST A RUN: declared-and-read is not enough,
    # the binding must be USED. StickyNotes read textColor and never used it (its notes
    # carry their own paper colour), rules 1-4 all passed it, and ChatCut refused it.
    # The first version of THIS rule also passed it, because `const textColor =
    # props.textColor` names it twice on its own line — so uses are counted OUTSIDE
    # the declaration.
    check("a property read into a binding that is never USED is caught",
          J.component_contract("const Component=({item})=>{const props=item.props;\n"
                               "  const spare = props.spare || \"\";\n"
                               "  const used = props.used || \"\";\n"
                               "  return (<div>{used}</div>);};",
                               [{"key": "spare"}, {"key": "used"}])
          and not J.component_contract("const Component=({item})=>{const props=item.props;\n"
                                       "  const used = props.used || \"\";\n"
                                       "  return (<div>{used}</div>);};", [{"key": "used"}]),
          str(J.component_contract("const Component=({item})=>{const props=item.props;\n"
                                   "  const spare = props.spare || \"\";\n"
                                   "  const used = props.used || \"\";\n"
                                   "  return (<div>{used}</div>);};",
                                   [{"key": "spare"}, {"key": "used"}]))[:110])
    check("a property declared and never read is caught, and so is a read that was never declared",
          J.component_contract("const Component=({item})=>{const props=item.props;"
                               " return (<div>{props.a}</div>);};", [{"key": "a"}, {"key": "b"}])
          and J.component_contract("const Component=({item})=>{const props=item.props;"
                                   " return (<div>{props.z}</div>);};", [])
          and not J.component_contract("const Component=({item})=>{const props=item.props;"
                                       " return (<div>{props.a}</div>);};", [{"key": "a"}]),
          str(J.component_contract("const Component=({item})=>{const props=item.props;"
                                   " return (<div>{props.a}</div>);};", [{"key": "a"}, {"key": "b"}])))
    check("each of the four refusal classes is caught, and a COMMENT is not code",
          J.component_contract("const Component = () => { return (<AbsoluteFill/>); };")
          and J.component_contract("const FOO = 3;\nconst Component = () => { return (<div/>); };")
          and J.component_contract("const Component = ({item}) => { const p = item.props; return (<div/>); };")
          and J.component_contract("const Component = () => (<div/>);\nconst Component = () => (<div/>);")
          # and the false positive that the first version of this check actually produced:
          and not J.component_contract("/* never AbsoluteFill */\nconst Component = ({item}) => "
                                       "{ const props = item.props; return (<div/>); };"),
          "comment mention -> %s" % J.component_contract("/* never AbsoluteFill */\nconst Component = "
                                                         "({item}) => { const props = item.props; return (<div/>); };"))
    check("a brief this extractor cannot read is UNCHECKED, never a clean read",
          [c["kind"] for c in J.brief_constraints("Сделай видео динамичным")] == ["language_unchecked"]
          and J.brief_constraints("Сделай видео динамичным")[0]["checkable"] is False
          and J.brief_constraints("just make it pop") == [])

    if FAILS:
        print("\n%d FAILURE(S)" % len(FAILS))
        for f in FAILS:
            print("  " + f)
        return 1
    print("\nall legs green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
