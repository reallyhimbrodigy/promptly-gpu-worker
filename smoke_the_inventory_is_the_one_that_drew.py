#!/usr/bin/env python3
"""SMOKE — the component sheet the agent is shown is the one that was PROVEN.

WHAT WAS ACTUALLY WIRED, measured 2026-09-14. Two files sat side by side:

    component_sheet.png   329,679 bytes   Sep 13 23:41   <- MOUNTED
    sheet/INVENTORY.png   234,853 bytes   Sep 14 19:40   <- the one built from
                                                            actual renders

and the prompt's library index was built from `chatcut_catalogue.json`, which
names 29 components. Against the render check:

    in the catalogue, NOT proven to draw : SpeechBubble  (REFUSED — a
                                            dispatcher, it cannot be placed)
    proven to draw, NOT in the catalogue : all NINE caption styles

So the agent was offered one component it could not use, and none of the nine
that were built specifically to be offered. "Is the inventory consulted?" had a
worse answer than decoration: a STALE inventory was consulted, and the real one
was never wired.

THE SHEET IS ONLY AN INVENTORY IF IT IS THE INVENTORY OF WHAT DREW. The legs:
  MOUNTED  the image the job mounts is the file the render check wrote
  INDEX    the prompt's index is built from sheet.json, not the old catalogue
  EXACT    every name offered drew, and everything that drew is offered
  SEEN     the prompt tells the agent to read the picture before choosing

Each RED-proven.
"""
import ast
import json
import os
import pathlib
import sys

HERE = pathlib.Path(os.path.dirname(os.path.abspath(__file__)))
APP = HERE / "chatcut_job_app.py"
SRC = APP.read_text(encoding="utf-8")
TREE = ast.parse(SRC)


def mounts(src_tree):
    """{container path: local expression} for every add_local_file."""
    out = {}
    for n in ast.walk(src_tree):
        if (isinstance(n, ast.Call)
                and getattr(n.func, "attr", "") == "add_local_file"
                and len(n.args) >= 2
                and isinstance(n.args[1], ast.Constant)):
            out[n.args[1].value] = ast.unparse(n.args[0])
    return out


def prompt_reads(src_tree):
    """Container paths the craft block actually `open()`s.

    NOT every `/craft/...` string in the file. The first version of this leg
    collected every constant with that prefix — which includes the MOUNT
    TARGETS — so it reported "the prompt still reads chatcut_catalogue.json"
    about a file that is merely still mounted and no longer read. Mounting a
    file and reading it are different operations, and a scan that cannot tell
    them apart is wrong about correct code. Ninth of these in one session, and
    this one was mine within a minute of writing it: the population is real.
    """
    out = set()
    for n in ast.walk(src_tree):
        if not (isinstance(n, ast.Call)
                and getattr(n.func, "id", "") == "open"):
            continue
        for a in n.args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                    and a.value.startswith("/craft/"):
                out.add(a.value)
    return out


def legs(src, tree):
    bad = []
    m = mounts(tree)

    # MOUNTED — the picture comes from the render check's output directory.
    png = m.get("/craft/component_sheet.png", "")
    if "sheet" not in png or "INVENTORY" not in png:
        bad.append(("mounted", "the mounted sheet is %s, not the INVENTORY the "
                               "render check wrote" % (png or "ABSENT")))
    if "/craft/component_sheet.json" not in m:
        bad.append(("mounted", "sheet.json is not mounted — the index cannot "
                               "be built from what drew"))

    # INDEX — built from sheet.json, not the superseded catalogue.
    if "/craft/component_sheet.json" not in prompt_reads(tree):
        bad.append(("index", "the prompt never reads component_sheet.json"))
    if "/craft/chatcut_catalogue.json" in prompt_reads(tree):
        bad.append(("index", "the prompt still reads chatcut_catalogue.json, "
                             "which names SpeechBubble and no caption style"))

    # SEEN — the agent is told to look at the picture, not just the names.
    if "READ IT" not in src:
        bad.append(("seen", "nothing tells the agent to read the sheet image "
                            "before choosing"))
    return bad


def exact():
    """Every offered name drew; everything that drew is offered."""
    rows_p, sheet_p = HERE / "sheet" / "rows.json", HERE / "sheet" / "sheet.json"
    if not (rows_p.exists() and sheet_p.exists()):
        # ABSENT, NOT PASS.
        return [("exact", "sheet/rows.json or sheet/sheet.json is ABSENT — "
                          "this leg inspected nothing")]
    rows = json.loads(rows_p.read_text())
    drew = {k for k, v in rows.items() if v.get("state") == "MEASURED"}
    offered = {e["name"] for e in json.loads(sheet_p.read_text())["entries"]}
    bad = []
    for n in sorted(offered - drew):
        bad.append(("exact", "%s is OFFERED and did not draw" % n))
    # the reverse is a WARNING not a failure: a component can draw and still
    # lack a WHEN condition, in which case not offering it is correct.
    return bad


if __name__ == "__main__":
    bad = legs(SRC, TREE) + exact()
    for kind, why in bad:
        print("  [FAIL] %-7s %s" % (kind, why))
    if not bad:
        rows = json.loads((HERE / "sheet" / "rows.json").read_text())
        sheet = json.loads((HERE / "sheet" / "sheet.json").read_text())
        drew = sum(1 for v in rows.values() if v.get("state") == "MEASURED")
        print("  [ok] the mounted sheet is the INVENTORY the render check wrote")
        print("  [ok] the prompt index is built from sheet.json, not the "
              "superseded catalogue")
        print("  [ok] all %d offered components drew (%d drew in total)"
              % (len(sheet["entries"]), drew))
        print("  [ok] the agent is told to read the picture before choosing")
        _un = sheet.get("rendered_but_unconditioned") or []
        if _un:
            print("  [--] drew but carries no WHEN, so NOT offered: %s"
                  % ", ".join(_un))

    print("\n  RED PROOF")
    red = True
    r1 = legs(SRC.replace('os.path.join(_HERE, "sheet", "INVENTORY.png")',
                          'os.path.join(_HERE, "component_sheet.png")'), TREE)
    m1 = legs(SRC, ast.parse(
        SRC.replace('os.path.join(_HERE, "sheet", "INVENTORY.png")',
                    'os.path.join(_HERE, "component_sheet.png")')))
    print("    the stale sheet remounted -> %d leg(s) red" % len(m1))
    red &= any(k == "mounted" for k, _ in m1)

    m2 = legs(SRC, ast.parse(
        SRC.replace('"/craft/component_sheet.json"',
                    '"/craft/chatcut_catalogue.json"')))
    print("    index back on the old catalogue -> %d leg(s) red" % len(m2))
    red &= any(k == "index" for k, _ in m2)

    m3 = legs(SRC.replace("READ IT", "there it is"), TREE)
    print("    the 'read the picture' line gone -> %d leg(s) red" % len(m3))
    red &= any(k == "seen" for k, _ in m3)

    # EXACT: pretend a refused component is offered.
    _sp = HERE / "sheet" / "sheet.json"
    _orig = _sp.read_text()
    _d = json.loads(_orig)
    _d["entries"].append({"name": "SpeechBubble", "when": "X", "size": "S",
                          "claim": "", "what": "", "frame": "x.jpg"})
    _sp.write_text(json.dumps(_d))
    r4 = exact()
    _sp.write_text(_orig)
    print("    a refused component offered -> %d leg(s) red" % len(r4))
    red &= any(k == "exact" for k, _ in r4)

    ok = not bad and red
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
