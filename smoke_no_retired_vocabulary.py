#!/usr/bin/env python3
"""THE RETIRED VOCABULARY, AS A GATE OVER EVERY SURFACE THE AGENT READS.

Zac, 2026-09-18: "Second time a prompt has described a dead mechanism; a
third is coming without this." The third had already happened — CRAFT_CONTEXT
still described previews, ffmpeg contact sheets, importing the clip and a
fifteen-call budget while the loop paragraph described three turns.

Surfaces: the system prompt (built), the CLAUDE.md the harness writes, the
deciding paragraph, the loop constant and every module constant the message
builders reference, the first message and the rewatch message (driven), the
fault lines (driven), the shim's tool descriptions (driven), and every
knowledge document mounted under /craft/knowledge. Needles: the record files,
the DONE marks, any /work/ path, ToolSearch, and the retired instruments.
"""
import ast
import glob
import io
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import chatcut_job_app as J                                      # noqa: E402
import mcp_shim as MS                                            # noqa: E402

# THE MARK, NOT THE WORD: bare "DONE" is English in the craft docs ("DONE looks
# like this"); the retired mechanism is the FILE. "You have no submit_export
# tool" names an absence and stays.
NEEDLES = [r"spec\.json", r"rulings\.json", r"record\.json", r"/work/DONE", r"\bDONE2\b", r"\bwrite\W+(the file )?DONE\b",
           r"/work/", r"\bToolSearch\b", r"\bffmpeg\b", r"read_script", r"viewerFrameCount",
           r"preview_timeline yourself", r"fifteen ChatCut calls"]
SRC = io.open(os.path.join(HERE, "chatcut_job_app.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)
FNS = {n.name: n for n in ast.walk(TREE) if isinstance(n, ast.FunctionDef)}


def _consts(node):
    return [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def surfaces():
    """-> {name: text}. Built, driven, or read from disk — never from the source of a function
    whose strings are code (paths, prints)."""
    out = {}
    out["system.md (build_system_prompt)"] = J.build_system_prompt()
    # what write_cli_context WRITES: the string constants inside each .write(...) call
    wcc = FNS["write_cli_context"]
    writes = [n for n in ast.walk(wcc) if isinstance(n, ast.Call) and ast.unparse(n.func).endswith(".write")]
    out["CLAUDE.md/system.md (write_cli_context writes)"] = "\n".join(c for w in writes for a in w.args for c in _consts(a))
    # the deciding paragraph: the `prompt = (...)` assignment in edit() that carries THE BRIEF
    edit = FNS["edit"]
    para = [n for n in ast.walk(edit) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "prompt" for t in n.targets)
            and any("THE BRIEF" in c for c in _consts(n.value))]
    assert len(para) == 1, "deciding paragraph assignments: %d" % len(para)
    out["deciding paragraph"] = "".join(_consts(para[0].value))
    # every module-level str constant the paragraph and the builders reference by name
    names = {n.id for f in (para[0].value, FNS["pass1_message"], FNS["rewatch_message"], FNS["fault_lines"], FNS["timeline_lines"])
             for n in ast.walk(f) if isinstance(n, ast.Name)}
    for nm in sorted(names):
        v = getattr(J, nm, None)
        if isinstance(v, str) and len(v) > 40:
            out["const " + nm] = v
    out["const TWO_TURN_LOOP"] = J.TWO_TURN_LOOP
    # driven builders
    inv = os.path.join(HERE, "sheet", "INVENTORY.png")
    m1 = J.pass1_message(None, [], inv, source_watch=None, deciding="THE BRIEF: x")
    out["first message (pass1_message)"] = "\n".join(str(b.get("text") or "") for b in m1["message"]["content"] if b.get("type") == "text")
    w = {"frames": 0, "sheets": [], "state": "ABSENT", "why": "no sheets", "times": []}
    for final in (False, True):
        mr = J.rewatch_message(2, w, ["V1 base 0-610"], ["a fault"], ["a scan line"], final=final)
        out["rewatch message final=%s" % final] = "\n".join(str(b.get("text") or "") for b in mr["message"]["content"] if b.get("type") == "text")
    out["fault lines"] = "\n".join(J.fault_lines({"findings": []}, None, None, [{"id": "base-1", "itemType": "video"}], "base-1"))
    # the shim's tool surface: description is the name, nothing else
    slim = MS.slim_tool({"name": "edit_item", "description": "Write /work/DONE when finished", "inputSchema": {"type": "object", "properties": {"json": {"type": "string"}}}})
    out["shim tool description"] = slim.get("description", "")
    # knowledge on disk, as mounted
    for pth in sorted(glob.glob(os.path.join(HERE, "knowledge", "*.md"))) + [os.path.join(HERE, "chatcut_skill_basics.md")]:
        if os.path.exists(pth):
            out["doc " + os.path.relpath(pth, HERE)] = io.open(pth, encoding="utf-8").read()
    return out


def main():
    surf = surfaces()
    bad = []
    for name, text in surf.items():
        for nd in NEEDLES:
            for m in re.finditer(nd, text):
                ctx = text[max(0, m.start() - 50): m.end() + 50].replace("\n", " ")
                bad.append((name, nd, ctx))
    n_docs = sum(1 for k in surf if k.startswith("doc "))
    print("surfaces: %d (%d knowledge docs), needles: %d" % (len(surf), n_docs, len(NEEDLES)))
    if n_docs < 10 or len(surf) < 20:
        print("HARNESS: too few surfaces (%d) or docs (%d) — the population is not the one meant" % (len(surf), n_docs))
        return 2
    for name, nd, ctx in bad:
        print("  [RETIRED] %-44s %-24s ...%s..." % (name, nd, ctx))
    print("%d retired-vocabulary hit(s) across %d surfaces" % (len(bad), len(surf)))
    print("FAIL" if bad else "OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
