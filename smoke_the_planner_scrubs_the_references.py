#!/usr/bin/env python3
"""The planner can look at Zac's ten while it rules, and the harness fetches.

WHAT THIS PROTECTS. The ten are a persistent ChatCut project, so the standard
stopped being a frozen cache of 37 moments somebody else chose. `inspect_asset`
addresses ORIGINAL SOURCE TIME, returns up to 25 exact frames per call at
native resolution, and carries WORD-LEVEL transcript for the same window —
measured live, not read off a doc:

    in@7.00 the@7.16 style@7.28 of@7.48 some@7.60 of@7.72 the@7.84 most@7.92

The failure this makes impossible is the one this repo keeps paying for: a
capability that is mounted, wired, and offered to nobody. `read_knowledge` was
called 0 times in 37 runs and the zero was quoted in a scope document as
evidence the agent did not need it — when the truth was that the reader had
been WITHHELD in all 37.

THE LEGS, written against the property:
  1. `scrub_reference` is in the offered set
  2. and is NOT stripped with the readers — it is the opposite of a reader:
     the only way to see the standard at all once the frozen frames come out
  3. the frames reach the model as IMAGE blocks on the tool result, not as a
     path, a URL, or a promise
  4. every absence is a STATE with a reason — no manifest, no credential, a
     time past the end of the clip
  5. whether it was offered is RECORDED, so a run where nobody called it cannot
     be read as a run where nobody wanted it

RED-proven at the bottom.
"""
import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                   # noqa: E402
import chatcut_reference as C                                    # noqa: E402

SRC = open(os.path.join(HERE, "agentic_editor_app.py"), encoding="utf-8").read()
fail = []


def bad(m):
    fail.append(m)


def legs(src=None, tree=None):
    src = src if src is not None else SRC
    tree = tree if tree is not None else ast.parse(src)
    out = []

    # 1 & 2. OFFERED, AND NOT STRIPPED WITH THE READERS
    _names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if isinstance(k, ast.Constant) and k.value == "name" \
                        and isinstance(v, ast.Constant):
                    _names.add(v.value)
    if "scrub_reference" not in _names:
        out.append(("offered", "scrub_reference is in no tool schema"))
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(
                getattr(t, "id", "") == "_READERS" for t in n.targets):
            try:
                if "scrub_reference" in set(ast.literal_eval(n.value)):
                    out.append(("notareader",
                                "scrub_reference is in _READERS — it would be "
                                "withheld on the cheap arm, which is where the "
                                "planner most needs to see the standard"))
            except Exception:                                     # noqa: BLE001
                pass

    # 3. THE FRAMES REACH THE MODEL AS PIXELS
    _fn = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == "scrub_reference":
            _fn = n
    if _fn is None:
        out.append(("pixels", "there is no scrub_reference handler"))
    else:
        b = ast.unparse(_fn)
        if '"type": "image"' not in b and "'type': 'image'" not in b:
            out.append(("pixels", "the handler returns no image block — the "
                                  "planner would get a URL and type it"))
        if "fetch" not in b:
            out.append(("pixels", "the handler never fetches the frames"))
    # and the result path must send a LIST, or the blocks are stringified away
    if "_scrub_blocks" not in src:
        out.append(("pixels", "nothing carries the blocks to the tool_result"))
    else:
        _ok = False
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                    and n.func.attr == "append":
                u = ast.unparse(n)
                if "tool_result" in u and "_scrub_blocks" in u:
                    _ok = True
        if not _ok:
            out.append(("pixels", "the blocks never reach a tool_result"))

    # 5. OFFERED-NESS IS RECORDED
    if "scrub_offered" not in src:
        out.append(("recorded", "nothing records whether it was offered — a "
                                "zero call count would be unreadable"))
    return out


for k, m in legs():
    bad("[%s] %s" % (k, m))

# ── 4. ABSENCE IS A STATE, on the real functions ────────────────────────────
_save = C._MANIFEST
try:
    C._MANIFEST = ["/nope/reference_project.json"]
    m, st = C.manifest()
    if m is not None or not st.startswith("ABSENT"):
        bad("[state] a missing manifest returned %r / %r" % (m, st[:60]))
finally:
    C._MANIFEST = _save

m, st = C.manifest()
if not m:
    bad("[library] the reference manifest is not readable here: %s" % st)
else:
    if len(m.get("assets") or []) != 10:
        bad("[library] %d assets, expected Zac's ten"
            % len(m.get("assets") or []))
    for a in (m.get("assets") or []):
        if not (a.get("assetId") and a.get("duration_s")):
            bad("[library] an asset has no id or no duration: %s" % a)
            break

# the URL extractor reads the block type ChatCut actually uses
_res = {"result": {"content": [
    {"type": "resource_link", "uri": "https://x/out.jpeg?sig=1"},
    {"type": "text", "text": "{\"frames\": {\"status\": \"available\"}}"}]}}
if C.frame_urls(_res) != ["https://x/out.jpeg?sig=1"]:
    bad("[extract] resource_link URLs are not read: %s" % C.frame_urls(_res))
if (C.structured(_res).get("frames") or {}).get("status") != "available":
    bad("[extract] the JSON half of the result is not read")
if C.frame_urls({"result": {"content": []}}):
    bad("[extract] found a URL in an empty result")

# ── RED PROOF ───────────────────────────────────────────────────────────────
red = 0
MUT = (
    ("the tool is withheld with the readers", "notareader",
     lambda s: s.replace('_READERS = {"read_knowledge", "search_skills"}',
                         '_READERS = {"read_knowledge", "search_skills",\n'
                         '                "scrub_reference"}')),
    ("the frames come back as a URL, not pixels", "pixels",
     lambda s: s.replace("""            _blocks.append({"type": "image", "source": {""",
                         """            _blocks.append({"type": "link", "source": {""")),
    ("the blocks never reach the tool_result", "pixels",
     lambda s: s.replace("""                                + _scrub_blocks.pop(tu.id)})""",
                         """                                })""")),
)
for label, kind, mut in MUT:
    m2 = mut(SRC)
    if m2 == SRC:
        print("  *** MUTATION DID NOT APPLY: %s (anchor 0x)" % label)
        red += 1
        continue
    try:
        r = legs(m2, ast.parse(m2))
    except SyntaxError as e:
        print("  *** MUTANT DOES NOT PARSE: %s (%s)" % (label, e))
        red += 1
        continue
    hit = any(k == kind for k, _ in r)
    print("    %-44s -> names %s: %s" % (label, kind, hit))
    if not hit:
        red += 1

for m in fail:
    print("  *** " + m)
print("\nsmoke_the_planner_scrubs_the_references: %d wrong, %d not red (of %d)"
      % (len(fail), red, len(MUT)))
sys.exit(1 if (fail or red) else 0)
