#!/usr/bin/env python3
"""Did the output contain what was asked, and NOTHING THAT WAS NOT?

THE REQUIREMENT. The user's prompt is the source of truth. "Just add captions"
gets captions and nothing else; "make it viral" gets the full treatment; "cut
the bit where I stumble" gets exactly that. A BRIEF THAT ASKS FOR LITTLE MUST
PRODUCE LITTLE — placing more than was asked is a failure, not generosity. It is
the edit the user did not request, delivered over the one they did.

TWO DIRECTIONS, AND ONLY ONE WAS EVER MEASURED. `not_asked_for` recorded
families built outside a targeted scope at build time. Nothing recorded a family
ASKED FOR AND NEVER DELIVERED — an edit that quietly drops the one thing
requested reads as a successful run, and "0 blocks" with no denominator is how
that stays invisible.

FOUR STATES, and UNSCOPED is not a pass:

    FAITHFUL     asked for X, delivered X
    SHORT        asked for X, did not deliver it
    OVERREACHED  delivered Y that was not asked for
    UNSCOPED     the run declared full_edit, so there IS no scope to judge
                 against. That is the ABSENCE of the question, not an answer to
                 it, and it is reported so a minimal brief declared full_edit is
                 visible rather than excused.

RED-proven by red_proof_prompt_fidelity.py.
"""
import ast
import pathlib
import sys

src = pathlib.Path("agentic_editor_app.py").read_text()
tree = ast.parse(src)
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


_ns = {}
for _n in tree.body:
    if isinstance(_n, ast.Assign) and any(
            getattr(_x, "id", "").startswith("FIDELITY_")
            for _t in _n.targets for _x in ast.walk(_t)):
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
    if isinstance(_n, ast.FunctionDef) and _n.name == "spec_fidelity":
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
check("spec_fidelity is module-level and pure", "spec_fidelity" in _ns)
if "spec_fidelity" not in _ns:
    print("\nPROMPT-FIDELITY: FAIL"); sys.exit(1)
f = _ns["spec_fidelity"]
OK, SHORT, OVER, UNSCOPED = (_ns["FIDELITY_OK"], _ns["FIDELITY_SHORT"],
                             _ns["FIDELITY_OVER"], _ns["FIDELITY_UNSCOPED"])


def _P(*fams):
    return [{"family": x} for x in fams]


T = lambda *f: {"mode": "targeted_change", "families": list(f)}   # noqa: E731

# ── THE REQUIREMENT, CASE BY CASE ───────────────────────────────────────────
check("'just add captions' delivering text only is FAITHFUL",
      f(T("text"), _P("text"))[0] == OK)
check("'just add captions' that also ships zooms has OVERREACHED",
      f(T("text"), _P("text", "zoom"))[:3] == (OVER, [], ["zoom"]),
      f"{f(T('text'), _P('text', 'zoom'))}")
check("and the overreach NAMES what was not asked for",
      "zoom" in f(T("text"), _P("text", "zoom"))[3])
check("'just add captions' delivering nothing is SHORT",
      f(T("text"), _P())[:2] == (SHORT, ["text"]),
      "an edit that drops the one thing requested reads as a successful run")
check("asked two families, delivered a third: both directions reported",
      f(T("text", "sfx"), _P("zoom"))[1:3] == (["sfx", "text"], ["zoom"]),
      f"{f(T('text','sfx'), _P('zoom'))}")

# ── UNSCOPED IS NOT A PASS ──────────────────────────────────────────────────
_u = f({"mode": "full_edit"}, _P("text", "card", "zoom"))
check("a full_edit is UNSCOPED, not FAITHFUL", _u[0] == UNSCOPED, f"{_u[0]}")
check("and it says a minimal brief declared full_edit would be invisible here",
      "full_edit" in _u[3] and "cannot be judged" in _u[3], _u[3])
check("it still reports what WAS placed, so the reader can judge the brief",
      _u[2] == ["card", "text", "zoom"], f"{_u[2]}")

# ── THE CUT COUNTS AS A FAMILY WHEN ONE WAS MADE ────────────────────────────
check("'cut the bit where I stumble' is FAITHFUL when only a cut happened",
      f(T("cut"), _P(), cut_made=True)[0] == OK,
      "a cut leaves no placement, so without this a cut-only request always "
      "reads SHORT")
check("and a cut nobody asked for is an overreach",
      f(T("text"), _P("text"), cut_made=True)[:3] == (OVER, [], ["cut"]))

# ── CAPTIONS ARE BURNED, NEVER A PLACEMENT ──────────────────────────────────
# "Just add captions" is THE canonical minimal brief, and captions leave no
# manifest entry — without the captions_made channel it reads SHORT by
# construction even when 29 pages composited. Never tested until now; the check
# existed and the case did not.
check("'just add captions' with captions burned is FAITHFUL",
      f(T("caption"), _P(), captions_made=True)[0] == OK)
check("'just add captions' with captions AND four zooms has OVERREACHED",
      f(T("caption"), _P("zoom", "zoom", "zoom", "zoom"), captions_made=True)[:3]
      == (OVER, [], ["zoom"]))
check("'just add captions' with no captions is SHORT — the one thing missing",
      f(T("caption"), _P(), captions_made=False)[:2] == (SHORT, ["caption"]))
# Wiring read from the AST — the call's keyword must be an EXPRESSION over the
# ledger, never a constant. `captions_made=False` keeps every substring a grep
# would look for and disconnects the wire.
_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
          and getattr(n.func, "id", "") == "spec_fidelity"]
_kw = {k.arg: k.value for c in _calls for k in c.keywords}
# THE KEYWORD IS FOLLOWED TRANSITIVELY, not one hop. The call site used to be
# `captions_made=bool(led.get("caption_composited"))`; the re-edit fidelity work
# made it `captions_made=_cap_for_fid`, bound through a TUPLE assignment. A
# one-hop resolver reported both wires as cut when neither was — a leg testing
# the SPELLING of the call rather than the property. Follow the name through
# every binding, tuple targets included, and ask whether the required evidence
# appears anywhere in its derivation.
def _sources_of(node, depth=6):
    """Every expression a keyword's value can be derived from."""
    _out, _front = [], [node]
    for _ in range(depth):
        _next = []
        for _n in _front:
            if _n is None:
                continue
            _out.append(_n)
            if not isinstance(_n, ast.Name):
                continue
            for _a in ast.walk(tree):
                _tgts = []
                if isinstance(_a, ast.Assign):
                    for _t in _a.targets:
                        _tgts.extend(_t.elts if isinstance(_t, ast.Tuple) else [_t])
                    for _i, _t in enumerate(_tgts):
                        if getattr(_t, "id", "") != _n.id:
                            continue
                        _v = _a.value
                        if isinstance(_v, ast.Tuple) and isinstance(
                                _a.targets[0], ast.Tuple) and _i < len(_v.elts):
                            _next.append(_v.elts[_i])
                        else:
                            _next.append(_v)
        _front = _next
        if not _front:
            break
    return _out

def _derivation_text(kw):
    return " ".join(ast.unparse(n) for n in _sources_of(_kw.get(kw))
                    if n is not None)

check("the call site passes captions_made from the ledger, not a constant",
      "captions_made" in _kw
      and not isinstance(_kw["captions_made"], ast.Constant)
      and "caption_composited" in _derivation_text("captions_made"),
      "the wire is cut or constant: " + _derivation_text("captions_made")[:160])

# ── cut_made IS NOT PRESENCE ────────────────────────────────────────────────
# Round 52 screen_recording: keep_spans=[[0.0, 90.46]] — the whole source kept —
# beside built[cut]=35. bool(keep_spans) calls that a cut. A cut was made when
# the KEPT TOTAL IS LESS THAN THE SOURCE.
_cm_has_lt = any(
    isinstance(x, ast.Compare) and any(isinstance(o, ast.Lt) for o in x.ops)
    and "_kept" in ast.unparse(x) and "_srcd" in ast.unparse(x)
    for n in _sources_of(_kw.get("cut_made")) for x in ast.walk(n))
check("cut_made is derived from kept total < source duration, not from "
      "keep_spans existing",
      _cm_has_lt,
      "presence tested where shape was needed — in my own wiring, the class I "
      "wrote into the wire contract three times today")

# ── ONE FIDELITY STANDARD, BOTH PATHS ───────────────────────────────────────
# The rule does not change on a re-edit; the POPULATION does. A re-edit's
# placements are the whole prior plan, so "make the captions bigger" reads
# FAITHFUL on a run that changed nothing — the paid re-edit no-op scored as a
# success. The caller must hand spec_fidelity the placements on beats this run
# actually changed.
check("there is exactly ONE spec_fidelity call site — one standard, not two",
      len(_calls) == 1, f"{len(_calls)} call sites")
check("the re-edit delta rule is hoisted, so the check drives the shipped rule",
      any(isinstance(n, ast.FunctionDef) and n.name == "reedit_delta"
          for n in ast.walk(tree)))
# THE POSITIONAL ARGUMENT, FOLLOWED. Not a source-presence grep: `_rd_beats`
# appears several times in the file, so `"_rd_beats" in src` would pass with the
# wire cut. Resolve the placements argument through its bindings and require the
# delta to be in its derivation.
_pl_arg = _calls[0].args[1] if _calls and len(_calls[0].args) > 1 else None
_pl_txt = " ".join(ast.unparse(n) for n in _sources_of(_pl_arg) if n is not None)
# BOTH COORDINATES. Narrowing on the beat alone drags in that beat's
# PRE-EXISTING placements — "remove the last clip" changes beat 2's `cut`, and a
# sound effect the beat has carried since the first edit gets attributed to this
# run and reads OVERREACHED. The delta knows which FAMILIES moved too, and the
# narrowing must use both or it answers a question about the wrong placements.
_beat_named = any(_n in _pl_txt for _n in ("_rd_beats", "_rd_set"))
check("the placements handed to spec_fidelity are narrowed by the re-edit "
      "delta — by BEAT and by FAMILY, not the whole prior plan",
      _beat_named and "_rd_fams" in _pl_txt,
      "a re-edit that changed nothing would read FAITHFUL, or an untouched "
      "placement on a changed beat would read OVERREACHED; derivation was: "
      + _pl_txt[:200])
_rd = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
       and getattr(n.func, "id", "") == "reedit_delta"]
check("reedit_delta is CALLED, not merely defined", len(_rd) >= 1,
      f"{len(_rd)} call sites")
# AN ACTUAL print() CALL, not the literal's presence. Mutating `print(` to
# `_no_print = (` left the string in the file and a source-presence leg stayed
# green with nothing printed — the same shape as `for _r in []` keeping `_r`
# inside a print. Ask the AST whether a print carries it.
_delta_prints = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "id", "") == "print"
                 and "RE-EDIT DELTA" in ast.unparse(n)]
check("the delta reaches the ledger AND a real print() call",
      'led["reedit_delta_beats"]' in src and len(_delta_prints) >= 1,
      "a counter in the ledger and nowhere else answers no question anyone "
      "can ask")

# ── THE CAPTION SIGNAL ──────────────────────────────────────────────────────
# Captions are BURNED, not ruled per beat: no verdict, no manifest entry. The
# beat delta is structurally blind to them, so before this a caption re-edit and
# a caption no-op were indistinguishable and fidelity fell back to
# `caption_composited`, which is true in both. That is the paid re-edit no-op
# scored as a success — the exact shape the delta catches everywhere else.
import agentic_editor_app as _AA
_cs = _AA.caption_signature
check("`caption_signature` and `captions_changed` are hoisted, so the check "
      "drives the shipped rules",
      callable(getattr(_AA, "caption_signature", None))
      and callable(getattr(_AA, "captions_changed", None)))

_a = _cs("CleanCut", 15, [["hello", "world"], ["again"]])
check("no captions is ABSENT, not an empty signature — a run that burned none "
      "and a run identical to last time are different facts",
      _cs("CleanCut", 15, [])[0] == "ABSENT")
check("an identical caption run is MEASURED False — the no-op is CAUGHT",
      _AA.captions_changed(_a[1], _a[0], _a[1])[:2] == ("MEASURED", False))
_b = _cs("TypewriterReveal", 30, [["hello", "world"], ["again"]])
check("a restyle is MEASURED True",
      _AA.captions_changed(_a[1], _b[0], _b[1])[:2] == ("MEASURED", True))
# PAGE LAYOUT IS IN THE FINGERPRINT ON PURPOSE: a re-edit that keeps the style
# name but regroups the words is a real change the user sees, and a signature
# over the style alone would call it a no-op.
_c = _cs("CleanCut", 15, [["hello"], ["world", "again"]])
check("the same style with the words REGROUPED still counts as changed",
      _AA.captions_changed(_a[1], _c[0], _c[1])[:2] == ("MEASURED", True))
check("no prior fingerprint is ABSENT — not 'unchanged', which would invent a "
      "fact, and not 'changed', which would excuse a no-op",
      _AA.captions_changed(None, _a[0], _a[1])[0] == "ABSENT")
check("captions present last turn and gone this turn is REMOVED",
      _AA.captions_changed(_a[1], "ABSENT", None)[0] == "REMOVED")

# IT MUST SURVIVE THE TURN. The plan is the only thing the server persists and
# hands back, so a signature that is not on the plan cannot be compared.
check("the signature rides the durable plan under its own kind",
      _AA.caption_from_plan(_AA.plan_with_caption([{"src_t0": 0.0}], _a[1]))[1]
      is not None)
check("a plan written before the fingerprint existed still loads its rulings",
      _AA.caption_from_plan([{"src_t0": 0.0}]) == ([{"src_t0": 0.0}], None),
      "reading `kind` as required would discard every prior plan")
# CALLS, BY AST. `"plan_with_caption(" in src` is satisfied by the function's
# own DEFINITION, so deleting the call site left the leg green — a
# source-presence check that cannot see the wire it is about.
def _calls_named(nm):
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and getattr(n.func, "id", "") == nm]
check("the signature is recorded in the ledger", 'led["caption_signature"]' in src)
check("it is PERSISTED on the durable plan — the only thing that survives the "
      "turn, so a signature not on it can never be compared",
      len(_calls_named("plan_with_caption")) >= 1,
      "defined but never called")
check("and SPLIT back out of the prior plan on a re-edit",
      len(_calls_named("caption_from_plan")) >= 1,
      "defined but never called")
_cap_prints = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
               and getattr(n.func, "id", "") == "print"
               and "CAPTION DELTA" in ast.unparse(n)]
check("the caption delta reaches a real print() call, not only the ledger",
      len(_cap_prints) >= 1)
check("fidelity's caption evidence is gated on captions_changed, not on "
      "caption_composited alone",
      "_cap_for_fid = _cap_for_fid and _cc_changed" in src,
      "an ungated caption family makes every no-op read FAITHFUL")

# ── THE NEGATIVE-CONSTRAINT CLASS ───────────────────────────────────────────
# MEASURED on real traffic: 425 of 5,943 distinct briefs (7.2%) and 338 of 7,958
# users (4.2%) name something the edit must NOT do. The pipeline had never been
# tested on one and could not have passed: set_spec had no field to carry an
# exclusion, so the commonest shape — "viral and engaging no captions in video"
# — declared full_edit and returned UNSCOPED while the captions the user had
# just refused were burned.
check("FIDELITY_FORBIDDEN exists as its own state — an instruction disobeyed "
      "is not the same failure as scope overshot",
      getattr(_AA, "FIDELITY_FORBIDDEN", None) == "FORBIDDEN")
_sp_props = None
for _t in list(_AA.TOOLS) + list(_AA.KNOWLEDGE_TOOLS):
    if _t.get("name") == "set_spec":
        _sp_props = (_t.get("input_schema") or {}).get("properties") or {}
check("`forbidden` is offered on set_spec — an exclusion the agent cannot "
      "express is one the run cannot honour",
      _sp_props is not None and "forbidden" in _sp_props)
if _sp_props and "forbidden" in _sp_props:
    _fd = str(_sp_props["forbidden"].get("description") or "")
    check("its description says it applies in ANY mode, not targeted_change "
          "only — the commonest real shape is a full_edit with one exclusion",
          "ANY MODE" in _fd.upper())
    check("and that a vague brief does not soften an explicit exclusion",
          "vagueness" in _fd.lower())

# THE RULE RUNS BEFORE THE MODE GATE. This is the whole fix: behind it, a
# full_edit escapes the check entirely.
check("a FULL_EDIT that delivers a forbidden family is FORBIDDEN, not UNSCOPED",
      f({"mode": "full_edit", "forbidden": ["caption"]}, _P(),
        captions_made=True)[0] == _AA.FIDELITY_FORBIDDEN)
check("a full_edit that honours the exclusion is still UNSCOPED — the rest of "
      "a vague brief remains unjudgeable and is not promoted to a pass",
      f({"mode": "full_edit", "forbidden": ["caption"]}, _P(),
        captions_made=False)[0] == UNSCOPED)
check("a targeted_change that delivers a forbidden family is FORBIDDEN rather "
      "than OVERREACHED — it was only ever right there by accident",
      f({"mode": "targeted_change", "families": ["zoom"],
         "forbidden": ["caption"]}, _P("zoom"),
        captions_made=True)[:3] == (_AA.FIDELITY_FORBIDDEN, [], ["caption"]))
check("a forbidden family that was NOT delivered passes",
      f({"mode": "targeted_change", "families": ["zoom"],
         "forbidden": ["caption"]}, _P("zoom"), captions_made=False)[0] == OK)
check("cut counts as a deliverable family for the forbidden check — "
      "'no trimming no cutting anything' is the exclusive shape",
      f({"mode": "targeted_change", "families": ["zoom"],
         "forbidden": ["cut"]}, _P("zoom"), cut_made=True)[0]
      == _AA.FIDELITY_FORBIDDEN)
_ff = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
       and getattr(n.func, "id", "") == "fail"
       and n.args and isinstance(n.args[0], ast.Constant)
       and n.args[0].value == "fidelity_forbidden"]
check("and it FAILS LOUDLY — a state nobody fails on is a diagnostic",
      len(_ff) >= 1)

# ── THE UNSCOPED HALF, WHICH IS MOST OF THE TRAFFIC ─────────────────────────
# 48.2% of users declare no family scope, and ALL 37 fixture runs to date are
# that case — so until this shipped, nothing judged the majority shape at all.
# Scored over that history: 20 of 37 runs INCOHERENT (54%).
_uc = _AA.unscoped_coherence
check("`unscoped_coherence` is hoisted and pure, so the check drives the "
      "shipped rule", callable(_uc))
check("the builder set is ONE declaration shared with the dispatch — a hand "
      "copy is how 'the pipeline never built it' gets blamed on the agent",
      isinstance(getattr(_AA, "BUILT_FAMILIES", None), dict)
      and "_TYPE = dict(BUILT_FAMILIES)" in src)

check("a run that ruled a family with a builder and did not build it is "
      "INCOHERENT — its own rulings are the standard",
      _uc({"text": {"ruled": 20, "built": 18}}, [1])[0] == "INCOHERENT")
check("a run that built everything it ruled is COHERENT",
      _uc({"text": {"ruled": 3, "built": 3}}, [1])[0] == "COHERENT")
# NOT A RATE, AND THIS IS THE LEG THAT KEEPS IT HONEST. The standing law is
# that the density rates GRADE and never instruct. A run that places two things
# because two moments deserved them must pass.
check("a SMALL edit that delivered everything it ruled is COHERENT — this is a "
      "grade, not a floor, and no count here is a target",
      _uc({"zoom": {"ruled": 1, "built": 1}}, [{"family": "zoom"}])[0]
      == "COHERENT")
check("VACANT is its own state — placing nothing is a different failure from "
      "placing things you ruled away",
      _uc({}, [], cut_made=False, captions_made=False)[0] == "VACANT"
      and _uc({}, [], cut_made=True)[0] == "COHERENT")
# THE TWO GAPS HAVE DIFFERENT OWNERS.
_st, _dr, _un, _w = _uc({"cutaway": {"ruled": 3, "built": 0}}, [1])
check("a family this pipeline has NO builder for is UNBUILDABLE, not the run's "
      "incoherence — it is the capability gap list",
      _st == "COHERENT" and "cutaway" in _un and not _dr)
check("and the run is not FAILED for it — failing here would attribute the "
      "pipeline's hole to the agent",
      "unbuildable" not in src.split("fail(\"unscoped_incoherent\"")[0][-400:])

check("the grade reaches the ledger AND a real print()",
      'led["coherence"]' in src
      and any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print"
              and "COHERENCE" in ast.unparse(n) for n in ast.walk(tree)))
for _nm in ("unscoped_vacant", "unscoped_incoherent"):
    check("`%s` fails loudly — a state nobody fails on is a diagnostic" % _nm,
          any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "fail"
              and n.args and isinstance(n.args[0], ast.Constant)
              and n.args[0].value == _nm for n in ast.walk(tree)))
check("it runs ONLY on the unscoped path — a scoped brief is judged by what "
      "was asked, not by what the run decided",
      "if _fid_state == FIDELITY_UNSCOPED:" in src)

# ── ONE VOCABULARY FOR SFX ──────────────────────────────────────────────────
# 25 of 75 ruled sfx placements were lost, and it was never a missing
# capability: place_sfx exists and built the other 50. The agent says "this beat
# has a sound" by putting `sfx` in `treatment`; the BUILD reads the separate
# `sfx: "yes"` field. The guard that should have caught the mismatch read the
# FIELD too — while its siblings `_nocopy` and `_nocard` read TREATMENT — so a
# beat with treatment and no field was invisible on both ends.
_hrr = _AA.half_ruling_refusal
# ZAC'S RULING 2026-09-11: OFFERED **AND** DERIVED. I had deleted the `sfx`
# field because two ways to state one thing lost 25 of 75 placements. Deleting
# it also deleted a DISTINCTION: `sfx: "yes"` with no name means "a sound
# belongs here, you choose it" and `sfx_name` means "this sound". Naming the
# sound is craft, not bookkeeping.
check("`sfx` is OFFERED on the ruling schema, so 'a sound here, you pick' is "
      "sayable without naming one",
      "sfx" in set(_AA.VERDICT_FIELDS))
check("and it is DERIVED, so the agent need not say it twice",
      "sfx" in _AA.DERIVED_VERDICT_FIELDS
      and "sfx" in set(_AA.STORED_VERDICT_FIELDS))

# NO SFX ARM FOR THE NAMELESS CASE. `sfx_name` is DERIVABLE from the beat's
# role, and half_ruling_refusal is pure and runs before any beat is in hand —
# so refusing there pre-empts a live deriver and turns "you pick" into an
# unsatisfiable demand. That is the refused-forever failure, and it is worse
# than the silent drop it replaces: one costs a placement, the other the run.
check("a nameless sfx ruling is NOT refused at ruling time — the deriver has "
      "not run yet and may supply the name from the beat's role",
      _hrr({"beat": 1, "treatment": ["sfx"]}) is None)
check("a named sfx ruling passes",
      _hrr({"beat": 1, "treatment": ["sfx"], "sfx_name": "boom"}) is None)

# A CONTRADICTION IS REFUSED, because nothing downstream can resolve it:
# fill-when-empty gives one source of truth for a BLANK field, never for a
# field that disagrees.
check("`treatment: ['sfx']` with `sfx: 'no'` is REFUSED — opposite answers to "
      "one question, and the build follows the field",
      bool(_hrr({"beat": 1, "treatment": ["sfx"], "sfx": "no"})))
check("and the refusal names both sides, so it is satisfiable from either",
      "treatment" in (_hrr({"beat": 1, "treatment": ["sfx"], "sfx": "no"}) or "")
      and "field" in (_hrr({"beat": 1, "treatment": ["sfx"], "sfx": "no"}) or ""))

# FILLED WHEN EMPTY, NEVER OVERRIDDEN — the agent's own answer wins.
_led = {"beat_verdicts": []}
_AA.admit_verdict(_led, {"beat": 0, "treatment": ["sfx"],
                         "sfx_name": "boom"}, set())
_AA.admit_verdict(_led, {"beat": 1, "treatment": ["text"],
                         "text_content": "hi"}, set())
check("a blank field is filled from the treatment: 'yes' on an sfx beat, 'no' "
      "otherwise",
      _led["beat_verdicts"][0].get("sfx") == "yes"
      and _led["beat_verdicts"][1].get("sfx") == "no")
# THE FIXTURE MUST DISAGREE WITH THE DERIVATION, or the leg cannot see an
# override. `treatment: ["none"], sfx: "no"` derives "no" as well, so overriding
# changes nothing and the leg passed with the fill unconditional — satisfied by
# its own mutant. The agent says YES on a beat whose treatment says otherwise.
_led2 = {"beat_verdicts": []}
_AA.admit_verdict(_led2, {"beat": 2, "treatment": ["none"], "sfx": "yes"}, set())
check("an answer the agent DID give is not overwritten, even where the "
      "derivation would say the opposite",
      _led2["beat_verdicts"][0].get("sfx") == "yes",
      "the fill must be blank-only, or the field stops being the agent's")

# THE THREE FIELD-KEYED READS. The guard, the DERIVER and the build all read
# the `sfx` field while the intent was in `treatment`. Filling the field at the
# boundary is what makes the deriver reachable at all.
check("both stripper passes key on TREATMENT, not the field alone",
      src.count('"sfx" in [str(t).lower()') >= 2,
      "a guard reading a different field from its siblings is the bug")

# ── IT RUNS ON EVERY RUN, AND SAYS SO ───────────────────────────────────────
check("fidelity reaches the ledger", 'led["fidelity"]' in src)
check("and is PRINTED", "FIDELITY        :" in src,
      "a measure that reaches only the ledger answers nothing")
check("SHORT fails loudly", 'fail("fidelity_short"' in src)
check("OVERREACHED fails loudly", 'fail("fidelity_overreached"' in src)
check("it is computed for EVERY run, not only targeted ones",
      src.index("spec_fidelity(") < src.index('led["fidelity"]') + 400
      and 'if _sc2 and _sc2.get("mode") == "targeted_change"' in src,
      "the build-time gate stays scoped to targeted_change; the REPORT is "
      "unconditional, which is how an unscoped run becomes visible")

# ── THE RULE REACHES THE AGENT ──────────────────────────────────────────────
# MATCH THE ASSEMBLED DESCRIPTION, NOT THE RAW SOURCE. The prompt is built from
# adjacent string fragments, so "never because you are unsure" is split across
# two of them and appears NOWHERE contiguously in the file. Grepping the source
# for prompt text asserts something about the LAYOUT of the literal rather than
# about what the agent reads — the third time today a check of mine matched
# rendered text instead of the value.
_spec_desc = ""
for _n2 in ast.walk(tree):
    if isinstance(_n2, ast.Dict):
        _kv = {k.value: v for k, v in zip(_n2.keys, _n2.values)
               if isinstance(k, ast.Constant)}
        if getattr(_kv.get("name"), "value", "") == "set_spec" \
                and "description" in _kv:
            _spec_desc = "".join(
                c.value for c in ast.walk(_kv["description"])
                if isinstance(c, ast.Constant) and isinstance(c.value, str))
check("the set_spec description could be assembled (non-vacuity)",
      len(_spec_desc) > 400, f"{len(_spec_desc)} chars")
check("set_spec tells the agent a small brief must produce a small edit",
      "LITTLE MUST PRODUCE LITTLE" in _spec_desc)
check("and warns that full_edit is how a narrow request escapes scope",
      "never because you are unsure" in _spec_desc,
      "full_edit has no family scope, so nothing downstream can object")

print()
if fails:
    print("PROMPT-FIDELITY: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("PROMPT-FIDELITY: PASS — four states, both directions, cut counted, "
      "reported on every run and failing loudly in each direction")
