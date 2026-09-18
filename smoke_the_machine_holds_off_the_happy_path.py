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
import tempfile
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("MODAL_IS_INSIDE_CONTAINER", "0")
import chatcut_job_app as J                                      # noqa: E402
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
    check("--tools names the builtins and the eight ChatCut tools",
          "--tools" in _cc and _cc[_cc.index("--tools") + 1].startswith("Bash,Read,Write,Glob,Grep,mcp__chatcut__")
          and _cc[_cc.index("--tools") + 1].count("mcp__chatcut__") == 8,
          "--tools restricts builtins; the MCP block is the shim's eight")
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
        _w = J.watch_asset("t", "asset", 20.362, tempfile.mkdtemp(), rpc=_rpc)
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
            return {"rc": 1, "subtype": "error_max_turns", "tool_calls": [{"name": "mcp__chatcut__" + t, "input": {}} for t in names],
                    "text": text, "usage": usage, "wall": 1.0, "killed": False}
        _inv.log = log
        return _inv
    _rw = lambda n, final: {"message": {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "rw%d" % n}]}}, "sheets": 2, "faults": [], "scan": []}
    U1 = {"read": 0, "write": 300000, "in": 2, "out": 900}; UN = {"read": 300000, "write": 400, "in": 2, "out": 300}
    happy = _mk_invoke(lambda n: (["edit_item"], "", U1) if n == 1 else ((["edit_item"], "", UN) if n == 2 else ([], "export", UN)))
    tm = J.run_three_turns(happy, _rw, {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "go"}]}})
    check("the happy path is three API calls: place, review-fix, export",
          len(tm["turns"]) == 3 and tm["terminal"] is None and str(tm["verdict"]).startswith("export at turn 3")
          and [t["kind"] for t in tm["turns"]] == ["place", "review", "confirm"],
          "%s / %s / %s" % (len(tm["turns"]), tm["terminal"], tm["verdict"]))
    runaway = _mk_invoke(lambda n: (["edit_item"], "", U1 if n == 1 else UN))
    tm2 = J.run_three_turns(runaway, _rw, {"type": "user", "message": {"role": "user", "content": []}})
    check("a forced runaway hits the cap: four calls, the fifth is terminal",
          len(tm2["turns"]) == 4 and (tm2["terminal"] or {}).get("kind") == "TURN CAP" and len(runaway.log) == 4,
          "%d calls, terminal=%s" % (len(tm2["turns"]), tm2["terminal"]))
    miss = _mk_invoke(lambda n: (["edit_item"], "", U1) if n == 1 else (["edit_item"], "", {"read": 1000, "write": 299000, "in": 2, "out": 300}))
    tm3 = J.run_three_turns(miss, _rw, {"type": "user", "message": {"role": "user", "content": []}})
    check("a call that does not read the prefix call 1 established is terminal",
          (tm3["terminal"] or {}).get("kind") == "CACHE MISS" and (tm3["terminal"] or {}).get("at") == 2 and len(miss.log) == 2,
          "%s" % (tm3["terminal"],))
    nop = _mk_invoke(lambda n: ([], "I would rather ask a question", U1))
    tm4 = J.run_three_turns(nop, _rw, {"type": "user", "message": {"role": "user", "content": []}})
    check("turn 1 without an edit op is terminal, not a second try",
          (tm4["terminal"] or {}).get("kind") == "NO PLACEMENT" and len(nop.log) == 1)
    ok, why = J.cache_gate({"read": 0, "write": 300000}, {"read": 284000})
    ok2, _ = J.cache_gate({"read": 0, "write": 300000}, {"read": 285000})
    check("the cache gate is 0.95 x (call-1 read + write)", ok is False and ok2 is True, why)
    check("the run bound is 300s and the cap is four", J.RUN_TIMEOUT_S == 300 and J.TURN_CAP == 4 and J.TURN_LAW_S <= 300)
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
          "_arm_idle" not in d and "_arm_second_rewatch" not in d and "_start_rewatch" not in d and "run_three_turns(" in d,
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
          "usage_once(_st, ev)" in _e3 and "ceiling" not in ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "run_three_turns")).lower())
    _tc = io.open(os.path.join(HERE, "turn_clock.py"), encoding="utf-8").read()
    check("turn_clock exposes the kill and names who used it", "_killed_by_driver" in _tc and '"kill_reason"' in _tc)
    check("every turn and the run are bounded, and the bound is terminal",
          J.TURN_LAW_S <= 300 and J.RUN_TIMEOUT_S == 300 and "RUN TIMEOUT" in ast.unparse(next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "run_three_turns")))

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
    check("a plant counts as named only through an op that touched it",
          len(_acted.values) == 3 and all("_acted[" in ast.unparse(v) for v in _acted.values), ast.unparse(_acted)[:200])
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
    check("the relay traces its phases in order: received, body_read, breakpoint, thinking, upstream_connected, request_sent, response_headers, first_chunk, relaying, upstream_eof, relay_closed",
          _phases == ["received", "body_read", "breakpoint", "thinking", "upstream_connected", "request_sent", "response_headers", "first_chunk", "relaying", "upstream_eof", "relay_closed"]
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
          _rt_bound == "_left" and len(_left_asg) == 1 and "RUN_TIMEOUT_S" in _left_asg[0] and "_run_t0" in _left_asg[0]
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
    check("the deciding paragraph shows the exact add shape, names type motion-graphic, forbids the json field, routes captions to edit_captions, and never mentions /work/DONE",
          '"type": "motion-graphic"' in _para_all and "never the json field" in _para_all and 'edit_captions call with action "enable"' in _para_all
          and '"why": "one line' in _para_all and "/work/DONE" not in _para_all and "preview_timeline yourself" not in _para_all,
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
          {"edit", "keep_warm"} <= set(_rft_sites) and _m1t.startswith(J.RUN_FIRST_TEXT_JOB) and J.RUN_FIRST_TEXT_PING == "ping",
          "sites=%s first=%r" % (_rft_sites, _m1t[:40]))
    # ---- THE API'S OWN ANSWER IS A TERMINAL, NEVER THE AGENT'S FAULT; NOTHING EXPORTS AFTER A TERMINAL ----
    class _Inv400:
        log = []
        def __call__(self, n, message):
            self.log.append(n)
            return {"rc": 1, "subtype": "success", "tool_calls": [], "text": "Credit balance is too low", "killed": False, "wall": 7.0,
                    "usage": {"read": 0, "write": 0, "in": 0, "out": 0}, "api_status": 400, "api_head": '{"type":"error","error":{"message":"Credit balance is too low"}}'}
    _i400 = _Inv400()
    _tm400 = J.run_three_turns(_i400, lambda n, final: {"message": {}, "sheets": 0}, {"type": "user", "message": {"role": "user", "content": []}})
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

    # ---- THE BOUNDED THINKING ARM IS WRITTEN BY THE PROXY (the CLI sends adaptive for any N>0) ----
    _tb, _tn = PX.apply_thinking_budget({"model": "m", "max_tokens": 64000, "thinking": {"type": "adaptive"}}, 2000)
    _td, _tdn = PX.apply_thinking_budget({"model": "m", "thinking": {"type": "disabled"}}, 2000)
    _t0, _t0n = PX.apply_thinking_budget({"model": "m", "thinking": {"type": "adaptive"}}, 0)
    _ts, _tsn = PX.apply_thinking_budget({"model": "m", "max_tokens": 1500, "thinking": {"type": "adaptive"}}, 2000)
    check("a budget rewrites adaptive thinking to {enabled, budget_tokens}; disabled stays disabled; no budget leaves the body alone; max_tokens is lifted above the budget",
          _tb["thinking"] == {"type": "enabled", "budget_tokens": 2000} and _tn.get("rewritten") is True and _tb["max_tokens"] == 64000
          and _td["thinking"] == {"type": "disabled"} and _tdn.get("rewritten") is False
          and _t0["thinking"] == {"type": "adaptive"} and _t0n.get("rewritten") is False
          and _ts["thinking"]["budget_tokens"] == 2000 and _ts["max_tokens"] > 2000,
          "budget=%s disabled=%s none=%s small=%s" % (_tb.get("thinking"), _td.get("thinking"), _t0.get("thinking"), _ts.get("max_tokens")))
    _tbs = [ast.unparse(n.value) for n in ast.walk(_edit_fn) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Attribute) and t.attr == "THINKING_BUDGET" for t in n.targets)]
    check("the job hands the proxy think_tokens as the budget (0 stays the off switch)", _tbs == ["int(think_tokens) if think_tokens > 0 else 0"], "%s" % _tbs)
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

    if FAILS:
        print("\n%d FAILURE(S)" % len(FAILS))
        for f in FAILS:
            print("  " + f)
        return 1
    print("\nall legs green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
