#!/usr/bin/env python3
"""GATE B checks the agent's output against CHATCUT'S STATE, and ABSENT is not a pass.

RULED BY ZAC 2026-09-16, building the single agent: "Build them as harness
checks between the placement call and the export, not as things the agent asks
itself. The agent can't self-certify, but the harness can check its output
against ChatCut's state."

THE LEGS, and every one is driven by EXECUTING the shipped predicate on a
fixture rather than by reading the source — a check that reasons about text
cannot tell code from string content, and this repo has paid for that eight
times.

  1. AN EMPTY RECORD DOES NOT PASS. Found by driving my own gate: with no
     rulings, every other check returns PASS ("ruled 0, landed 0", "no sounds
     ruled", "no cards ruled") and the gate green-lights an export by an agent
     that recorded nothing. Absence rendered as success, inside the gate
     written to stop it.
  2. A ruling anchored at a source second THE CUT REMOVED is withheld.
  3. A ruling that never became an item is withheld — the check that is
     against ChatCut rather than against a plan written from the same ruling.
  4. A CUTAWAY IS NOT PART OF THE CUT. A cutaway is a video item on the same
     source; counting it into the kept spans would make a graphic anchored to
     a removed moment look like it survived — the failure of leg 2, wearing a
     pass.
  5. A READ-BACK THAT FAILED IS NOT A CLEAN TIMELINE. ABSENT withholds.
  6. THE AGENT CANNOT EXPORT. Asked of the shipped tool list, because telling
     the agent not to export is a preference and removing the tool is a
     property.
  7. THE HARNESS'S READ PASSES NO WINDOW AND PAGES. `preview_timeline` takes
     tracks/fromFrame/toFrame; an agent-chosen window is an agent-chosen gate,
     and a `limit` with no paging is a truncated list read as a total.
  8. withhold() keeps REMOVED and UNBUILT apart — a placement that landed and
     is wrong is not the same ledger fact as a ruling that never landed.

RED-proven at the bottom, and every mutation asserts the PHRASE its leg prints
rather than a non-zero exit: a red that is not about the property is exactly as
wrong as a green that is not.
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import chatcut_gate as G                                          # noqa: E402

JOB_SRC = open(os.path.join(HERE, "chatcut_job_app.py"), encoding="utf-8").read()
fail = []

FPS = 30
SPEC = {"mode": "full_edit", "why": "the brief says punchy"}


def _vid(i, a, b, f0, f1, track="V1"):
    return {"id": i, "itemType": "video", "trackAlias": track,
            # MICROSECONDS — the shape preview_timeline actually returns
            # (probe 2026-09-17); the seconds-keyed shape was a guess.
            "sourceRange": {"start": int(round(a * 1e6)), "end": int(round(b * 1e6))},
            "timelineRange": {"fromFrame": f0, "toFrame": f1}}


def _mg(i, f0, f1, track="V2", props=None):
    return {"id": i, "itemType": "motion-graphic", "trackAlias": track,
            "timelineRange": {"fromFrame": f0, "toFrame": f1},
            "propertyOverrides": props if props is not None else {}}


# the cut: source 0-10s kept, 10-20s REMOVED, 20-25s kept
CUT = [_vid("v0", 0, 10, 0, 300), _vid("v1", 20, 25, 300, 450)]


def legs(mod=None):
    """Every leg, against the module under test. Returns [(kind, phrase)]."""
    g = mod or G
    out = []

    # 1. AN EMPTY RECORD DOES NOT PASS
    r = g.gate([], {"items": list(CUT), "fps": FPS, "spec": SPEC})
    if r["verdict"] != g.WITHHOLD:
        out.append(("empty", "an empty record PASSED the gate"))

    # ...and a missing spec is its own withhold, because `why` is the field
    # the 43% was found in.
    r = g.gate([{"beat": 0, "treatment": ["text"], "src_t0": 1.0,
                 "hold_s": 1.0}],
               {"items": CUT + [_mg("m0", 30, 60)], "fps": FPS, "spec": {}})
    if r["verdict"] != g.WITHHOLD:
        out.append(("spec", "a run with no spec PASSED the gate"))

    # 2. A REMOVED MOMENT IS WITHHELD
    r = g.gate([{"beat": 1, "treatment": ["text"], "src_t0": 15.0,
                 "hold_s": 1.0}],
               {"items": CUT + [_mg("m1", 30, 60)], "fps": FPS, "spec": SPEC})
    if not any(f["check"] == "ruled_moment_survives"
               and f["verdict"] == g.WITHHOLD for f in r["findings"]):
        out.append(("removed", "a ruling at a CUT source second passed"))

    # 3. A RULING THAT NEVER LANDED IS WITHHELD
    r = g.gate([{"beat": 0, "treatment": ["text"], "src_t0": 1.0,
                 "hold_s": 2.0}],
               {"items": list(CUT), "fps": FPS, "spec": SPEC})
    if not any(f["check"] == "every_ruling_landed"
               and f["verdict"] == g.WITHHOLD for f in r["findings"]):
        out.append(("landed", "a ruling with NO item on the timeline passed"))

    # ...and one that DID land passes, or the check refuses correct work
    r = g.gate([{"beat": 0, "treatment": ["text"], "src_t0": 1.0,
                 "hold_s": 2.0}],
               {"items": CUT + [_mg("m2", 30, 90)], "fps": FPS, "spec": SPEC})
    if any(f["check"] == "every_ruling_landed"
           and f["verdict"] == g.WITHHOLD for f in r["findings"]):
        out.append(("landed", "a ruling that DID land was refused — a check "
                              "tight enough to reject correct work is not a "
                              "check"))

    # 4. A CUTAWAY IS NOT PART OF THE CUT
    # the cutaway plays source 10-13s (a REMOVED stretch) on V2. If base_track
    # or kept_spans counted it, source 12s would resolve and leg 2 would pass
    # on a moment that is not in the edit.
    with_cut = CUT + [_vid("c0", 10, 13, 60, 150, track="V2")]
    base, st, _w = g.base_track(with_cut)
    if base != "V1":
        out.append(("cutaway", "base track read as %r with a cutaway present"
                    % base))
    spans, _s2, _w2 = g.kept_spans(with_cut, base)
    frame, _s3, _w3 = g.source_to_timeline(spans, 12.0)
    if frame is not None:
        out.append(("cutaway", "source 12.0s (removed) resolved to frame %s "
                               "because a cutaway was counted into the cut"
                    % frame))

    # 4b. A CUTAWAY CUTS TO FOOTAGE THE EDIT REMOVED — THAT IS WHAT IT IS.
    # The fifth instance in this repo of a question written for text asked of
    # every family, and it was inside this module. `cutaway_from_s` was fed to
    # the survival check, so a cutaway pulling from a removed stretch — the
    # ordinary case, verified live as `source=[18000000,21000000)us` playing
    # while V1 is at second 2 — was withheld. 47% of Zac's reference beats are
    # cutaways, so the gate would have refused nearly every real edit.
    _cut_items = CUT + [_vid("c0", 14, 17, 90, 180, track="V2")]
    _ok_cut = [{"beat": 2, "treatment": ["cutaway"], "src_t0": 3.0,
                "hold_s": 3.0, "cutaway_from_s": 14.0}]
    r = g.gate(_ok_cut, {"items": _cut_items, "fps": FPS, "spec": SPEC,
                         "source_duration_s": 30.0})
    if r["verdict"] != g.PASS:
        out.append(("cutaway_ok",
                    "a CORRECT cutaway was withheld: %s"
                    % [f["why"][:90] for f in r["bad"]]))
    # ...and its address is still checked, on its own terms
    _bad_cut = [dict(_ok_cut[0], cutaway_from_s=99.0)]
    r = g.gate(_bad_cut, {"items": _cut_items, "fps": FPS, "spec": SPEC,
                          "source_duration_s": 30.0})
    if not any(f["check"] == "cutaway_addressable"
               and f["verdict"] == g.WITHHOLD for f in r["findings"]):
        out.append(("cutaway_addr",
                    "a cutaway addressed past the end of the source passed"))
    # ...and an unknown duration is ABSENT, never a pass
    r = g.gate(_ok_cut, {"items": _cut_items, "fps": FPS, "spec": SPEC})
    if not any(f["check"] == "cutaway_addressable"
               and f["state"] == g.ABSENT for f in r["findings"]):
        out.append(("cutaway_addr",
                    "an unread source duration let a cutaway address through"))

    # 4c. THE PLACEMENT LANDED WHERE THE RULING SAID. The inverted form of the
    # translator's "controls unanswered" refusal, and it was listed as
    # DELEGATED to hop 5 while nothing anywhere asked it. hop 5 measures masks
    # and asks only whether two overlap.
    _title = _mg("m0aaaaaa", 30, 90, props={"value": "40%"})
    _pc = [{"beat": 0, "treatment": ["text"], "src_t0": 1.0, "hold_s": 2.0,
            "where": "upper_third"}]
    _st = {"items": CUT[:1] + [_title], "fps": FPS, "spec": SPEC}
    r = g.gate(_pc, dict(_st, bands={"m0aaaaaa": {"band": [0.06, 0.33],
                                                  "names": ["top"]}}))
    if any(f["check"] == "placement_matches_control"
           and f["verdict"] == g.WITHHOLD for f in r["findings"]):
        out.append(("control_ok", "a placement that landed in the band it was "
                                  "ruled for was refused"))
    r = g.gate(_pc, dict(_st, bands={"m0aaaaaa": {"band": [0.66, 0.93],
                                                  "names": ["bottom"]}}))
    if not any(f["check"] == "placement_matches_control"
               and f["verdict"] == g.WITHHOLD for f in r["findings"]):
        out.append(("control", "a title ruled upper_third whose pixels landed "
                               "in the BOTTOM band passed"))
    r = g.gate(_pc, _st)
    if not any(f["check"] == "placement_matches_control"
               and f["state"] == g.ABSENT for f in r["findings"]):
        out.append(("control", "no measured bands and the control check still "
                               "passed — UNCHECKED read as correct"))

    # 4d. A CARD ARRIVES CARRYING WHAT THE COMPONENT DECLARES. The arm that
    # makes this a contract check rather than a presence check: an override on
    # a property nobody reads renders nothing.
    _cards = [{"beat": 1, "treatment": ["card"], "src_t0": 1.0, "hold_s": 2.0,
               "card_hero": "40%"}]
    r = g.gate(_cards, {"items": CUT[:1] + [_mg("m1", 30, 90,
                                               props={"heroNumber": "40%"})],
                        "fps": FPS, "spec": SPEC,
                        "component_props": ["value", "suffix", "label"]})
    if not any(f["check"] == "card_props_resolve"
               and f["verdict"] == g.WITHHOLD for f in r["findings"]):
        out.append(("cardprops", "an override the component does not declare "
                                 "(heroNumber) passed — that is the shape "
                                 "that shipped a graphic with no card"))

    # 5. A FAILED READ-BACK IS NOT A CLEAN TIMELINE
    r = g.gate([{"beat": 0, "treatment": ["text"], "src_t0": 1.0}],
               {"items": None, "read_why": "preview_timeline FAILED",
                "spec": SPEC})
    if r["verdict"] != g.WITHHOLD or r["state"] != g.ABSENT:
        out.append(("absent", "a read-back that FAILED read as a pass"))
    r = g.gate([{"beat": 0, "treatment": ["text"], "src_t0": 1.0}],
               {"items": [], "fps": FPS, "spec": SPEC})
    if r["verdict"] != g.WITHHOLD:
        out.append(("absent", "an EMPTY timeline read as a pass"))

    # 8. REMOVED AND UNBUILT ARE DIFFERENT LEDGER FACTS
    rep = {"bad": [{"check": "a", "why": "w", "item": "i1", "beat": 1,
                    "family": "card"},
                   {"check": "b", "why": "w", "item": None, "beat": 2,
                    "family": "text"}]}
    rm, ub = g.withhold(rep)
    if len(rm) != 1 or len(ub) != 1:
        out.append(("withhold", "withhold() did not separate REMOVED (%d) "
                                "from UNBUILT (%d)" % (len(rm), len(ub))))
    return out


for k, m in legs():
    fail.append("[%s] %s" % (k, m))


# ── 6. THE AGENT CANNOT EXPORT ───────────────────────────────────────────────
# Asked of the shipped list by AST, and the POPULATION IS ASSERTED: a walk that
# finds no NEEDED_TOOLS at all would otherwise report "export withheld" about
# a list it never read.
def _needed(src):
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "NEEDED_TOOLS"
                for t in n.targets):
            return [e.value for e in n.value.elts
                    if isinstance(e, ast.Constant)]
    return None


_tools = _needed(JOB_SRC)
if _tools is None:
    fail.append("[export] NEEDED_TOOLS was not found in chatcut_job_app.py — "
                "this leg would report 'withheld' about a list it never read")
elif len(_tools) < 4:
    fail.append("[export] NEEDED_TOOLS has %d entries; a list that small is a "
                "population this leg cannot reason about" % len(_tools))
else:
    for _t in ("submit_export", "track_export"):
        if _t in _tools:
            fail.append("[export] %r is in the agent's allowlist. Telling the "
                        "agent not to export is a preference; not giving it "
                        "the tool is the property this gate rests on." % _t)
    # ...AND THE HARNESS MUST ACTUALLY OWN THE EXPORT, or nothing delivers.
    # ASKED OF THE AST, NOT OF THE TEXT. My first version of this leg was
    # `"def harness_export(" not in JOB_SRC` and the text-reader census caught
    # it the same hour: a substring that asserts how code is SPELLED, in the
    # file whose whole subject is checks that test behaviour. The property is
    # a module-level function that actually calls submit_export.
    _he = next((n for n in ast.parse(JOB_SRC).body
                if isinstance(n, ast.FunctionDef)
                and n.name == "harness_export"), None)
    if _he is None:
        fail.append("[export] the agent cannot export and no module-level "
                    "harness_export exists — that is not a gate, it is a "
                    "dead end")
    elif not any(isinstance(c, ast.Constant) and c.value == "submit_export"
                 for c in ast.walk(_he)):
        fail.append("[export] harness_export() exists and never calls "
                    "submit_export — the deliverable has no producer")


# ── 7. THE HARNESS'S READ PASSES NO WINDOW, AND PAGES ────────────────────────
def _read_back_fn(src):
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.FunctionDef) and n.name == "read_back":
            return n
    return None


_rb = _read_back_fn(JOB_SRC)
if _rb is None:
    fail.append("[window] read_back() is not defined — the gate would be "
                "reading whatever the agent last asked for")
else:
    _body = ast.unparse(_rb)
    # the window keys, asked of the DICT KEYS passed to preview_timeline, not
    # of the whole function — `toFrame` legitimately appears in a comment.
    for _c in ast.walk(_rb):
        if not (isinstance(_c, ast.Call)
                and ast.unparse(_c.func).endswith("_mcp_call")):
            continue
        if not any(isinstance(a, ast.Constant) and a.value == "preview_timeline"
                   for a in _c.args):
            continue
        for a in _c.args:
            if not isinstance(a, ast.Dict):
                continue
            _keys = {k.value for k in a.keys
                     if isinstance(k, ast.Constant)}
            _win = _keys & {"tracks", "fromFrame", "toFrame"}
            if _win:
                fail.append("[window] read_back's preview_timeline passes %s — "
                            "an agent-chosen window is an agent-chosen gate"
                            % sorted(_win))
    if "nextOffset" not in _body:
        fail.append("[window] read_back does not follow nextOffset. A `limit` "
                    "with no paging is a truncated list read as a total, and "
                    "it would report placements that LANDED as never having "
                    "landed.")


# ── RED PROOF ────────────────────────────────────────────────────────────────
# Each mutation names the leg KIND it must fire, and the harness asserts that
# kind specifically — a red for any other reason is reported NOT RED.
GATE_SRC = open(os.path.join(HERE, "chatcut_gate.py"), encoding="utf-8").read()
red = 0
MUT = (
    ("an empty record goes back to passing", "empty",
     lambda s: s.replace("    if not rulings:\n        out.append(finding(",
                         "    if False:\n        out.append(finding(")),
    ("a removed moment stops being withheld", "removed",
     lambda s: s.replace(
         '    return None, MEASURED, (\n        "source %.2fs is in NO kept span',
         '    return 0, MEASURED, (\n        "source %.2fs is in NO kept span')),
    ("the cutaway is counted into the cut", "cutaway",
     lambda s: s.replace(
         '        if str(i.get("trackAlias") or "") != base:\n            continue',
         '        if False:\n            continue')),
    ("a failed read-back reads as a clean timeline", "absent",
     lambda s: s.replace('    if items is None:\n        return {"state": ABSENT',
                         '    if False:\n        return {"state": ABSENT')),
    ("the cutaway anchor goes back to being family-blind", "cutaway_ok",
     lambda s: s.replace(
         '    for k in ("src_t0", "keep_from_s"):',
         '    if v.get("cutaway_from_s") is not None:\n'
         '        return float(v["cutaway_from_s"]), "cutaway_from_s"\n'
         '    for k in ("src_t0", "keep_from_s"):')),
    ("the cutaway address stops being checked", "cutaway_addr",
     lambda s: s.replace(
         "        elif not (0 <= float(t) < float(source_duration_s)):",
         "        elif False:")),
    ("the control check stops comparing to the band", "control",
     lambda s: s.replace("        if expect not in names:",
                         "        if False:")),
    # MUTATE THE ANSWER, NOT THE GUARD. Disabling the `if not bands:` early
    # return left `bands` None and the ABSENT message then did `len(None)` —
    # the harness reported it as "a red that is not about the property",
    # which is exactly what that phrase check is for. Flipping the verdict
    # makes the property false without making the code invalid.
    ("missing bands read as a correct placement", "control",
     lambda s: s.replace(
         '        return [finding("placement_matches_control", ABSENT, WITHHOLD,\n'
         '                        "%d placement(s) name a band and hop 6 measured none, "',
         '        return [finding("placement_matches_control", MEASURED, PASS,\n'
         '                        "%d placement(s) name a band and hop 6 measured none, "')),
    ("a stray card override stops being refused", "cardprops",
     lambda s: s.replace("            stray = sorted({str(k) for k in po} - keys)",
                         "            stray = []")),
    ("withhold stops separating removed from unbuilt", "withhold",
     lambda s: s.replace('        if f.get("item"):',
                         '        if False:')),
)

for label, kind, mut in MUT:
    m = mut(GATE_SRC)
    if m == GATE_SRC:
        print("  *** MUTATION DID NOT APPLY: %s (anchor 0x)" % label)
        red += 1
        continue
    try:
        ast.parse(m)
    except SyntaxError as e:
        print("  *** MUTANT DOES NOT PARSE: %s (%s)" % (label, e))
        red += 1
        continue
    ns = {"__name__": "mutant"}
    try:
        exec(compile(m, "<mutant>", "exec"), ns)
    except Exception as e:                                        # noqa: BLE001
        print("  *** MUTANT DOES NOT IMPORT: %s (%s)" % (label, str(e)[:70]))
        red += 1
        continue
    _mod = type(sys)("mutant")
    _mod.__dict__.update(ns)
    try:
        hits = legs(_mod)
    except Exception as e:                                        # noqa: BLE001
        print("  *** LEGS RAISED on %s (%s) — a red that is not about the "
              "property" % (label, str(e)[:60]))
        red += 1
        continue
    hit = any(k == kind for k, _ in hits)
    print("    %-44s -> names %s: %s" % (label, kind, hit))
    if not hit:
        red += 1

if not MUT:
    print("  *** NO MUTATIONS — this proof asserts nothing")
    red += 1

for m in fail:
    print("  *** " + m)
print("\nsmoke_the_gate_checks_reality: %d wrong, %d not red (of %d)"
      % (len(fail), red, len(MUT)))
sys.exit(1 if (fail or red or not MUT) else 0)
