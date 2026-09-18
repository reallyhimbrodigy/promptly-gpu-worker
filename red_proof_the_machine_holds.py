#!/usr/bin/env python3
"""RED proof for smoke_the_machine_holds_off_the_happy_path.

Six mutations, one per property the consolidated pass of 2026-09-17 added:
the microsecond read, the derived span, the segmenter's length split, the
lifted withhold, the plan-keyed hops, and the withheld Skill tool. The first
four hit DRIVEN legs — the mutant changes a return value, not a sentence.
"""
import ast
import io
import re
import subprocess
import sys

sys.path.insert(0, ".")
import red_proof_anchor as RA                                   # noqa: E402

TARGET = "chatcut_job_app.py"
SMOKE = "smoke_the_machine_holds_off_the_happy_path.py"

MUTATIONS = [
    ("sourceRange is read as milliseconds",
     '            a, b = float(sr["start"]) / 1e6, float(sr["end"]) / 1e6',
     '            a, b = float(sr["start"]) / 1e3, float(sr["end"]) / 1e3',
     "kept_spans reads sourceRange{start,end} in microseconds",
     'float(sr["start"]) / 1e6'),
    ("a missing sourceRange fails instead of deriving",
     '            if not sr:\n                a, b = 0.0, (f1 - f0) / float(fps or 30.0)',
     '            if False:\n                a, b = 0.0, (f1 - f0) / float(fps or 30.0)',
     "an untrimmed item with NO sourceRange is DERIVED, not failed",
     "if not sr:"),
    ("the segmenter stops splitting long runs",
     '        if gap >= gap_s or span > max_beat_s:',
     '        if gap >= gap_s:',
     "86 words over a ~20s narration become 7-10 beats",
     "span > max_beat_s"),
    ("plan-keyed hops fail the chain again",
     '    _plan_hops = () if plan else ("hop3", "hop4")',
     '    _plan_hops = ()',
     "plan-keyed hops are N/A on the single-agent path, not failures",
     '_plan_hops = () if plan else ("hop3", "hop4")'),
    # TWO MUTATIONS, TWO LEGS. Skipping the string branch makes a prose
    # treatment yield [] — which the "never characters" leg accepts — so that
    # mutant is aimed at the leg it actually breaks (the families it names),
    # and the character iteration is reintroduced by letting a str fall into
    # the list branch, which is exactly the shape that produced 2,648 withholds.
    # VACUOUS the first time: letting a str fall into the list branch changed
    # nothing, because the str branch above it catches strings first. The
    # honest mutation removes the FAMILY FILTER — then the run's own prose
    # ("caption:TwoTone only. There's no screenshot...") yields 'only',
    # 'there', 's', 'no'... and the leg that expects [] goes red.
    ("the family filter on a prose treatment is removed",
     '        fams = [x for x in toks if x in KNOWN_FAMILIES]',
     '        fams = toks',
     "a prose treatment yields families, never characters",
     "fams = [x for x in toks if x in KNOWN_FAMILIES]"),
    ("the string branch stops naming families",
     '    if isinstance(t, str):\n        import re as _re',
     '    if False:\n        import re as _re',
     "...and names the families it does contain",
     "if isinstance(t, str):"),
    ("the base item echo goes back to the raw envelope",
     '                _ar = _mcp_call(access_token, "edit_item",\n                                {"projectId": pid, "adds": [_add]}, expect="adds")',
     '                _ar = call("edit_item", {"projectId": pid, "adds": [_add]}, 23)',
     "the base item's echo is parsed (expect='adds'), not read off the envelope",
     'expect="adds")'),
    ("the ceiling counts every event again",
     '        if _mid in _seen:\n            return 0\n        _seen.add(_mid)',
     '        if False:\n            return 0\n        _seen.add(_mid)',
     "the ceiling counts a message id once, however many events carry it",
     "if _mid in _seen:"),
    ("the ledger sums every event again",
     '        if _mid and _mid in _seen_ids:\n            continue',
     '        if False:\n            continue',
     "the ledger's cache sums are deduped by message id",
     "if _mid and _mid in _seen_ids:"),
    ("the eight leave the tool block",
     '             "--tools", "Bash,Read,Write,Glob,Grep," + _sel,',
     '             "--tools", "Bash,Read,Write,Glob,Grep",',
     "--tools names the builtins and the eight ChatCut tools",
     '"--tools", "Bash,Read,Write,Glob,Grep," + _sel,'),
    ("only the first result event is billed again",
     '    _results = [e for e in ev if e.get("type") == "result" and e.get("result_usage")]',
     '    _results = [e for e in ev if e.get("type") == "result" and e.get("result_usage")][:1]',
     "the bill sums every result event, one per user turn",
     '_results = [e for e in ev if e.get("type") == "result"'),
    # AIMED AT THE FUNCTION THE LEG DRIVES: the leg calls slim_tool directly,
    # so a mutation to its caller cannot bite (NOT RED the first time).
    ("the shim keeps the tool description",
     '    out = {"name": t.get("name"), "description": t.get("name", "").replace("_", " "),',
     '    out = {"name": t.get("name"), "description": t.get("description") or t.get("name", ""),',
     "the shim cuts a tool to name and arguments",
     '"description": t.get("name", "").replace("_", " ")'),
    ("the source watch samples one call of frames",
     '    for ci in range(0, len(times), 25):',
     '    for ci in range(0, min(len(times), 25), 25):',
     "the source is watched through inspect_asset: 40 exact frames at 2fps in two calls",
     "for ci in range(0, len(times), 25):"),
    ("the record Write comes back to the paragraph",
     '            "\\"propertyOverrides\\": {...}, \\"why\\": \\"one line: what it is for\\"}. "',
     '            "\\"propertyOverrides\\": {...}}. Then Write /work/record.json as one line per item you placed. "',
     "the paragraph asks for the why inside each op, and for no record",
     '\\"why\\": \\"one line: what it is for\\"'),
    # AIMED AT THE LIVE BRANCH: the loop never REQUESTS a fifth turn, so the
    # `if n > cap` guard is defensive and a mutation there is vacuous (NOT RED
    # the first time). The cap that fires on a runaway is the contingency
    # turn's own branch: fix ops at turn 4 are terminal.
    ("the contingency turn's fix ops stop being terminal",
     '    if _edit_ops(r4.get("tool_calls")):\n        tm["terminal"] = {"kind": "TURN CAP", "at": 4,',
     '    if False:\n        tm["terminal"] = {"kind": "TURN CAP", "at": 4,',
     "a forced runaway hits the cap: four calls, the fifth is terminal",
     'if _edit_ops(r4.get("tool_calls")):'),
    ("the cache gate accepts any read",
     '    return r >= fraction * prefix, "read %d against %.2f x %d" % (r, fraction, prefix)',
     '    return True, "read %d against %.2f x %d" % (r, fraction, prefix)',
     "a call that does not read the prefix call 1 established is terminal",
     'return r >= fraction * prefix'),
    ("an empty timeline stops being a fault",
     '    if not placed and brief_mode == "full_edit":',
     '    if False:',
     "an empty timeline on a full-edit brief is a fault the agent is told",
     'if not placed and brief_mode == "full_edit":'),
    ("a placement-less turn 1 gets a second try",
     '    if not _edit_ops(r1.get("tool_calls")):\n        tm["terminal"] = {"kind": "NO PLACEMENT", "at": 1,',
     '    if False:\n        tm["terminal"] = {"kind": "NO PLACEMENT", "at": 1,',
     "turn 1 without an edit op is terminal, not a second try",
     'tm["terminal"] = {"kind": "NO PLACEMENT", "at": 1,'),
    ("the invocation waits for a next message that never comes",
     '                _res.update(ev)\n                # THE TURN IS OVER WHEN THE RESULT ARRIVES.',
     '                _res.update(ev)\n                return\n                # THE TURN IS OVER WHEN THE RESULT ARRIVES.',
     "each invocation closes stdin when the result event arrives",
     '_res.update(ev)'),
    ("the reference instrument is unmounted again",
     '    .add_local_file(os.path.join(_HERE, "chatcut_reference.py"),\n                    "/root/chatcut_reference.py", copy=True)\n',
     '',
     "every lane module imported at run time is mounted in the image",
     '"/root/chatcut_reference.py"'),
    ("the reader goes back to json.loads (JSON-then-prose raises again)",
     "                parsed, _endpos = json.JSONDecoder().raw_decode(t.strip())",
     "                parsed, _endpos = json.loads(t.strip()), 0",
     "a JSON-then-prose edit_item envelope parses (four landed plants read as 'no adds')",
     "raw_decode(t.strip())"),
    ("--effort is dropped from the invocation",
     '            + (["--effort", str(effort)] if effort else [])\n',
     '',
     "--effort <level> is sent when given and absent otherwise",
     '"--effort", str(effort)'),
    ("the rewatch pays for an export again",
     "            _sheets, _times = _preview_frames(tok, _stage[\"projectId\"], _end, fps=float(_rb.get(\"fps\") or 30),\n                                              mark=lambda k: mark(\"rewatch%d.%s\" % (n, k)))",
     "            _sheets, _times = _edit_frames(tok, _stage[\"projectId\"], _end, mark=lambda k: mark(\"rewatch%d.%s\" % (n, k)))",
     "the rewatch watches through preview_timeline, never the export (paid once, for the final)",
     "_preview_frames(tok, _stage["),
    ("5-minute writes are priced as 1-hour writes",
     "    _usd = (_rd * 0.30 + _wr5 * 3.75 + (_wr - _wr5) * 6.00 + _in * 3.00 + _ou * 15.00) / 1e6",
     "    _usd = (_rd * 0.30 + _wr5 * 6.00 + (_wr - _wr5) * 6.00 + _in * 3.00 + _ou * 15.00) / 1e6",
     "cache writes are priced 5m at $3.75/M and the rest at $6/M, by the measured split",
     "_wr5 * 3.75"),
    ("the TTL split is no longer recorded per call",
     '                         "write_1h": (u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens"),\n                         "write_5m": (u.get("cache_creation") or {}).get("ephemeral_5m_input_tokens")},',
     '                         },',
     "every API call records which TTL it wrote (write_1h / write_5m)",
     '"write_5m": (u.get("cache_creation")'),
    ("a planted label carries the detector's word again",
     '             "propertyOverrides": {"label": "REVENUE", "value": "10x", "offsetY": 0}},',
     '             "propertyOverrides": {"label": "ON THE FACE", "value": "10x", "offsetY": 0}},',
     "the planted labels contain none of the detector's words (the first probe scored its own labels)",
     '"label": "REVENUE"'),
    ("the CLI version is no longer read in the job",
     '    _cli_ver = cli_version()\n',
     '    _cli_ver = "unread"\n',
     "cli_version reads `claude --version` in the container and names a failure; edit and keep_warm both record it",
     "_cli_ver = cli_version()"),
    ("the upstream leg goes untraced again",
     "        finally:\n            conn.close()\n            _trace(row)",
     "        finally:\n            conn.close()",
     "every upstream leg is traced: status, first byte, bytes relayed, redacted key",
     "_trace(row)"),
    ("a 5-minute ping is treated as an hour",
     '    if int(warm_rec.get("write_5m") or 0) > 0:\n        return 5',
     '    if int(warm_rec.get("write_5m") or 0) > 0:\n        return 60',
     "a ping's TTL is read from what it wrote: 1h -> 60 min, 5m -> 5 min, no split -> unknown",
     'return 5'),
    ("the cold-write verdict goes back to a literal hour",
     '" — a DEFECT, the ping was alive" if (_mins is not None and _ttl and _mins < _ttl) else ""',
     '" — a DEFECT, the ping was alive" if (_mins is not None and _ttl and _mins < 60) else ""',
     "the cold-write defect verdict compares against the ping's own TTL",
     "_mins < _ttl"),
    ("the CLI install is unpinned again",
     '        "npm install -g @anthropic-ai/claude-code@" + CLI_PIN,',
     '        "npm install -g @anthropic-ai/claude-code",',
     "the image installs a PINNED claude-code (name@CLI_PIN), and the pin is a version",
     'claude-code@" + CLI_PIN'),
    ("the job goes back to ANTHROPIC_BASE_URL",
     '        _env.update(_px.mitm_env(_px_port, _px_ca))\n',
     '        _env["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:%d" % _px_port\n',
     "the job starts the transparent proxy and never names ANTHROPIC_BASE_URL",
     "_env.update(_px.mitm_env(_px_port, _px_ca))"),
    ("the CA is no longer handed to the CLI",
     '            "NODE_EXTRA_CA_CERTS": ca_pem}',
     '            }',
     "the CLI is routed by HTTPS_PROXY + NODE_EXTRA_CA_CERTS, never by ANTHROPIC_BASE_URL",
     '"NODE_EXTRA_CA_CERTS": ca_pem'),
    ("CONNECT is answered without TLS termination",
     "        self.send_response(200, \"Connection established\")",
     "        self.send_response(502, \"Connection refused\")",
     "a CONNECT to api.anthropic.com is terminated with the throwaway CA, recorded, fingerprinted and relayed",
     '"Connection established"'),
    ("the shim keeps the tunnel it inherited",
     "def main():\n    scrub_proxy_env(os.environ)",
     "def main():\n    pass",
     "the shim scrubs the proxy variables it inherits before its first ChatCut call (5 tools instead of 13 on the tunnelled ping)",
     "scrub_proxy_env(os.environ)"),
    ("NO_PROXY no longer names the ChatCut host",
     '"NO_PROXY": "api.chatcut.io,localhost,127.0.0.1", "no_proxy": "api.chatcut.io,localhost,127.0.0.1",',
     '"NO_PROXY": "localhost,127.0.0.1", "no_proxy": "localhost,127.0.0.1",',
     "the CLI is routed by HTTPS_PROXY + NODE_EXTRA_CA_CERTS, never by ANTHROPIC_BASE_URL",
     '"NO_PROXY": "api.chatcut.io'),
    ("a per-turn constant kills the turn again",
     "            _cmd + [\"--max-turns\", \"1\"], \"/work\", _stream, _tfile, _left,",
     "            _cmd + [\"--max-turns\", \"1\"], \"/work\", _stream, _tfile, 120,",
     "a turn's bound is what is left of the RUN budget, never a per-turn constant",
     "_stream, _tfile, _left,"),
    ("the wire's thinking field is no longer recorded",
     '    row["request_fields"] = {"thinking": body.get("thinking"), "output_config": body.get("output_config"),',
     '    row["request_fields"] = {"thinking": None, "output_config": body.get("output_config"),',
     "every fingerprint row carries what was sent beside the prefix: thinking, effort, max_tokens",
     '"thinking": body.get("thinking")'),
    ("the off arm goes back to the env var that only omits the field",
     '        _env = {"MAX_THINKING_TOKENS": "0"}',
     '        _env = {"CLAUDE_CODE_DISABLE_THINKING": "1"}',
     "think_tokens=0 sends MAX_THINKING_TOKENS=0 (wire: thinking disabled), never the env var that only omits the field",
     '_env = {"MAX_THINKING_TOKENS": "0"}'),
    ("the paragraph loses the add shape",
     '            "exactly this shape: {\\"type\\": \\"motion-graphic\\", \\"assetId\\": "',
     '            "exactly the usual shape: {\\"kind\\": \\"graphic\\", \\"assetId\\": "',
     "the deciding paragraph shows the exact add shape, names type motion-graphic, forbids the json field, routes captions to edit_captions, and never mentions /work/DONE",
     'exactly this shape: {\\"type\\": \\"motion-graphic\\"'),
    ("sheets go back to PNG",
     '        fp = os.path.join(out_dir, "sheet_%02d.jpg" % (len(out) + 1))\n        sheet.convert("RGB").save(fp, "JPEG", quality=85, optimize=True)',
     '        fp = os.path.join(out_dir, "sheet_%02d.png" % (len(out) + 1))\n        sheet.save(fp, "PNG", optimize=True)',
     "a 20-frame sheet is JPEG under 400 KB (PNG sheets at ~1.5 MB pushed call 4 past the 32 MB request limit)",
     'sheet.convert("RGB").save(fp, "JPEG"'),
    ("the json escape hatch is offered again",
     'HIDDEN_PROPS = {"json"}',
     'HIDDEN_PROPS = set()',
     "the slimmed edit_item schema does not offer `json`, and a json-string call is unwrapped into real fields",
     'HIDDEN_PROPS = {"json"}'),
    ("the shim strips whys without unwrapping the json string",
     '        args, unwrapped = unwrap_json_arg(args) if name == "edit_item" else (args, False)',
     '        unwrapped = False',
     "the shim unwraps before it strips the whys (the strip sees the real ops)",
     'unwrap_json_arg(args) if name == "edit_item"'),
    ("the billing header goes back into the system hash",
     '    sys_hashed = [b for b in system if not _is_billing(b)] if isinstance(system, list) else system',
     '    sys_hashed = system',
     "the billing-header block is outside the system hash and counted; the first differing message is reported even when the system differs",
     'if not _is_billing(b)'),
    ("the system prompt asks for the record files again",
     '        "You write no files. The record is read back from the timeline; the "',
     '        "WRITE /work/spec.json BEFORE YOU FINISH, then /work/DONE. The record is read back from the timeline; the "',
     "the no-preview sentence sits where the placement is decided, and no DONE mark is asked for anywhere the agent reads",
     '"You write no files. The record is read back'),
    ("the proxy stops placing the watch-end breakpoint",
     '    tail[-1]["cache_control"] = {"type": "ephemeral", "ttl": "1h"}',
     '    pass',
     "the proxy marks the watch's last block with a 1h breakpoint, raises the system markers to 1h, drops the CLI's second-to-last message marker, and stays within four",
     'tail[-1]["cache_control"] = {"type": "ephemeral", "ttl": "1h"}'),
    ("the system markers stay 5-minute (a 1h entry after them is refused)",
     '                x["cache_control"] = {**x["cache_control"], "ttl": "1h"}',
     '                x["cache_control"] = {**x["cache_control"]}',
     "the proxy marks the watch's last block with a 1h breakpoint, raises the system markers to 1h, drops the CLI's second-to-last message marker, and stays within four",
     '"ttl": "1h"}\n                raised += 1'),
    ("the rewritten body is fingerprinted but the original goes upstream",
     '                if inj.get("injected") or thk.get("rewritten"):\n                    raw = json.dumps(body).encode("utf-8")',
     '                if inj.get("injected") or thk.get("rewritten"):\n                    pass',
     "upstream receives the REWRITTEN body and the fingerprint row records the breakpoint",
     'raw = json.dumps(body).encode("utf-8")'),
    ("a 4xx from the API reads as the agent placing nothing",
     '        if isinstance(r.get("api_status"), int) and r["api_status"] >= 400:',
     '        if isinstance(r.get("api_status"), int) and r["api_status"] >= 600:',
     "a 4xx from the API is the terminal API ERROR at that turn, carrying the status and the API's words, and is never retried",
     'r["api_status"] >= 400'),
    ("the untouched source is exported after a terminal again",
     '    if _tm.get("terminal"):\n        _export = {"state": "WITHHELD"',
     '    if False:\n        _export = {"state": "WITHHELD"',
     "the export is WITHHELD after any terminal (the floor once exported the untouched source after a 400)",
     '_export = {"state": "WITHHELD"'),
    ("the job hands the proxy a text its first message does not carry",
     'RUN_FIRST_TEXT_JOB = "THE COMPONENT INVENTORY"',
     'RUN_FIRST_TEXT_JOB = "THE SOURCE FOOTAGE"',
     "job and ping both hand the proxy their run-first text, and the job's first message really starts with it",
     'RUN_FIRST_TEXT_JOB = "THE COMPONENT INVENTORY"'),
    ("development runs inject the 1h breakpoint too",
     '        _px.RUN_FIRST_TEXT = RUN_FIRST_TEXT_JOB if (prefix_ttl == "1h" and not no_watch) else ""',
     '        _px.RUN_FIRST_TEXT = RUN_FIRST_TEXT_JOB if not no_watch else ""',
     "the job hands the proxy its run-first text only at prefix_ttl 1h (development: 5m, no injection)",
     'if (prefix_ttl == "1h" and not no_watch) else ""'),
    ("the proxy stops writing the thinking budget",
     '    b["thinking"] = {"type": "enabled", "budget_tokens": budget}\n    return b, {"rewritten": True',
     '    return b, {"rewritten": True',
     "a budget rewrites adaptive thinking to {enabled, budget_tokens}; disabled stays disabled; no budget leaves the body alone; max_tokens is lifted above the budget",
     'b["thinking"] = {"type": "enabled", "budget_tokens": budget}'),
    ("the no-watch run resumes the watch anyway",
     '    _watch_sid = None if no_watch else install_watch("/work")',
     '    _watch_sid = install_watch("/work")',
     "no_watch skips the resume (no --resume in the command), skips the watch-end breakpoint, and the record says so",
     'None if no_watch else install_watch("/work")'),
    ("the export returns before the file is fetched",
     '        if not url:\n            return out\n        import urllib.request as _ur, hashlib as _hl',
     '        if not url:\n            return out\n        return out\n        import urllib.request as _ur, hashlib as _hl',
     "harness_export polls to the file, downloads it, and keeps bytes + sha beside the record",
     'import urllib.request as _ur, hashlib as _hl'),
    ("any role can be the run's first message again",
     '        if m.get("role") != "user":\n            continue\n        c = m.get("content")',
     '        c = m.get("content")',
     "only user-role messages count and the LAST match is the run's first message (a system-role 'skipping' once stole the mark)",
     'if m.get("role") != "user":'),
    ("request MB goes back to the record field that is empty when it is read",
     '    _req_mb = [round(float(x.get("req_bytes") or 0) / 1e6, 2) for x in _read_trace_rows() if isinstance(x, dict)',
     '    _req_mb = [round(float(x.get("req_bytes") or 0) / 1e6, 2) for x in (out.get("proxy_trace") or []) if isinstance(x, dict)',
     "request MB per call is read from the trace file, not from a record field built later (it printed [] on every run)",
     'for x in _read_trace_rows() if isinstance(x, dict)'),
    ("the system blocks are no longer named",
     '                      "block_shas": [(_sha(b)[0], _sha(b)[1], (b.get("text", "")[:60] if isinstance(b, dict) else ""))',
     '                      "block_shas": [(_sha(b)[0], _sha(b)[1], "")',
     "the fingerprint names every system block's sha and size (the billing header excluded)",
     '(b.get("text", "")[:60] if isinstance(b, dict) else "")'),
    ("the Skill tool is offered again",
     '         "--disallowedTools", "Skill,Task,Agent",',
     '         "--disallowedTools", "Task,Agent",',
     "the Skill tool is withheld, not asked",
     '"--disallowedTools", "Skill,Task,Agent"'),
]


def run_smoke():
    r = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def leg_failed(out, leg):
    return re.search(r"^\s+%s\s+FAIL\s*$" % re.escape(leg), out, re.M) is not None


def main():
    srcs = {t: io.open(t, encoding="utf-8").read() for t in ("chatcut_job_app.py", "chatcut_gate.py", "turn_clock.py", "mcp_shim.py", "api_proxy.py")}

    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: the unmutated smoke is not green (rc=%d)\n%s"
              % (rc, out[-1200:]))
        sys.exit(2)

    red, bad = 0, []
    for label, anchor, repl, leg, pre in MUTATIONS:
        TARGET = next((t for t in ("chatcut_gate.py", "turn_clock.py", "mcp_shim.py", "api_proxy.py") if anchor in srcs[t]), "chatcut_job_app.py")
        src = srcs[TARGET]
        if pre is not None and pre not in src:
            bad.append("VACUOUS: %s — %r absent from the source" % (label, pre))
            print("  [VACUOUS] %s" % label)
            continue
        mode, mutant = RA.apply_one(src, anchor, repl)
        if mutant is None:
            bad.append("HARNESS FAILURE: %s — anchor %s" % (label, mode))
            print("  [ANCHOR %s] %s" % (mode, label))
            continue
        try:
            ast.parse(mutant)
        except SyntaxError as e:
            bad.append("HARNESS FAILURE: %s — will not parse: %s" % (label, e))
            print("  [UNPARSEABLE] %s" % label)
            continue
        io.open(TARGET, "w", encoding="utf-8").write(mutant)
        try:
            rc2, out2 = run_smoke()
        finally:
            io.open(TARGET, "w", encoding="utf-8").write(src)
        hit = leg_failed(out2, leg)
        if rc2 != 0 and hit:
            red += 1
            print("  [RED]  %-44s (%s) -> %r failed" % (label, mode, leg))
        else:
            bad.append("NOT RED: %s — rc=%d leg_failed=%s" % (label, rc2, hit))
            print("  [NOT RED] %-42s rc=%d leg_failed=%s" % (label, rc2, hit))

    for _t, _s in srcs.items():
        if io.open(_t, encoding="utf-8").read() != _s:
            print("\nRESIDUE: %s left MUTATED — restoring" % _t)
            io.open(_t, "w", encoding="utf-8").write(_s)
            bad.append("RESIDUE: %s did not match the pre-sweep source" % _t)

    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    for b in bad:
        print("  " + b)
    sys.exit(0 if red and red == len(MUTATIONS) and not bad else 1)


if __name__ == "__main__":
    main()
