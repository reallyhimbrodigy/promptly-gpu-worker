#!/usr/bin/env python3
"""A beat ruled twice is VISIBLE: which beats, what changed, what was lost,
and which ruling the build used.

WHY THIS GATE EXISTS. Round 63 `motion` carried 12 `beat_verdicts` for 10
beats, `screen_recording` 38-for-36, and nothing printed it. Four re-ruled
beats across the round, and EVERY ONE lost fields the first ruling had
supplied — `zoom_arc` 'hook'->None with "zoom" still in treatment,
`text_content` 'ChatGPT'->None with "text" still in treatment. The singular
`beat_verdict` tool appends with no duplicate check, writes 4 of the schema's
fields, skips the half-ruling refusal that `rule_all_beats` applies, and
answers with a DEDUPED `"ruled": N` so the agent is told "10 of 10" and cannot
see that it contradicted itself.

Bounding that is Builder-1's (the merge and the tool are his). This gate holds
the line that the disagreement is RECORDED AND PRINTED, because a ledgered
counter that reaches no output answers nothing — and this one hides a latent
defect: the frozen `executed_verdicts` copy kept the first ruling, but the
build's own per-beat lookup is `{v.get("beat"): v for v in beat_verdicts}`, a
dict comprehension, so LAST WINS there. On round 63 that was inert only
because the second execute_plan was refused every time.

Wiring legs are AST — grep proves a string is present, only the AST proves the
code runs. Behaviour legs drive the SHIPPED function, never a copy of it.
"""
import ast, importlib.util, pathlib, re, sys

APP = pathlib.Path("agentic_editor_app.py")
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


if not APP.exists():
    print("  [FAIL] the app is present"); print("         %s ABSENT" % APP)
    sys.exit(1)
_src = APP.read_text()
_tree = ast.parse(_src)

# ── WIRING, BY AST ────────────────────────────────────────────────────────────
_fns = {n.name: n for n in _tree.body if isinstance(n, ast.FunctionDef)}
check("`reruled_beats` is a module-level function (hoisted, so the gate can "
      "drive the shipped rule instead of a copy)",
      "reruled_beats" in _fns)

_calls = [n for n in ast.walk(_tree)
          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
          and n.func.id == "reruled_beats"]
check("the app CALLS it — a reporter nobody calls reports nothing",
      len(_calls) >= 1, f"{len(_calls)} call site(s)")

# It must be called with BOTH the ruling list and the frozen executed copy:
# `built_from` is DERIVED from the executed copy, and with one argument the
# question "which ruling built" cannot be answered at all.
check("it is called with the executed copy too, so `built_from` is derived "
      "rather than asserted",
      any(len(c.args) >= 2 for c in _calls),
      "every call site passes one argument — `built_from` would be unanswerable")

_assigned_names = {t.id for n in ast.walk(_tree)
                   if isinstance(n, ast.Assign) for t in n.targets
                   if isinstance(t, ast.Name)}
_assigned = set()
for n in ast.walk(_tree):
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if (isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                    and isinstance(t.slice.value, str)):
                _assigned.add(t.slice.value)
for _k in ("reruled_state", "reruled_beats", "reruled_count"):
    check(f"ledger key `{_k}` is assigned", _k in _assigned)

# PRINTED IN THE SAME COMMIT THAT ADDS IT. Three instances in one session of a
# counter reaching the ledger and no output; this leg is that rule, enforced.
_printed_names = set()
for n in ast.walk(_tree):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print":
        for sub in ast.walk(n):
            if isinstance(sub, ast.Name):
                _printed_names.add(sub.id)
check("the state reaches a print, not just the ledger",
      "_rr_state" in _printed_names,
      "sorted sample: %s" % sorted(x for x in _printed_names if x.startswith("_rr"))[:6])
# NOT "a name appears inside a print": the red proof mutated `for _r in _rr_rows`
# to `for _r in []` and that leg stayed green while nothing printed at all. The
# property is that the ROWS are iterated INTO a print, so assert the loop.
_row_loops = [n for n in ast.walk(_tree)
              if isinstance(n, ast.For) and isinstance(n.iter, ast.Name)
              and n.iter.id == "_rr_rows"
              and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                      and c.func.id == "print" for c in ast.walk(n))]
check("the per-beat rows are ITERATED into a print (a count alone cannot say "
      "WHICH beat or WHAT changed, and `for _r in []` prints nothing while "
      "still mentioning _r inside a print)",
      len(_row_loops) >= 1,
      "no `for _r in _rr_rows:` loop containing a print")

# ── BEHAVIOUR, DRIVING THE SHIPPED FUNCTION ──────────────────────────────────
_spec = importlib.util.spec_from_file_location("_app_rr", str(APP))
_app = importlib.util.module_from_spec(_spec)
sys.modules["_app_rr"] = _app
try:
    _spec.loader.exec_module(_app)
except Exception as _e:                      # noqa: BLE001
    check("the app imports so the shipped rule can be driven", False,
          f"{type(_e).__name__}: {_e}")
    print("\nRE-RULED VISIBLE: FAIL")
    sys.exit(1)
rb = _app.reruled_beats

# THREE STATES. The zero is ambiguous unless absence is its own answer.
check("a non-list is ABSENT, not a zero — 'never recorded rulings' and 'never "
      "re-ruled a beat' are different facts",
      rb(None)[0] == "ABSENT" and rb("nope")[0] == "ABSENT",
      f"{rb(None)[0]!r} / {rb('nope')[0]!r}")
check("a present list with no duplicate is a MEASURED zero",
      rb([{"beat": 0}, {"beat": 1}]) == ("MEASURED", []))

_dup = [{"beat": 0, "treatment": ["zoom"], "zoom_arc": "hook", "purpose": "hook"},
        {"beat": 1, "treatment": ["none"]},
        {"beat": 0, "treatment": ["zoom"], "zoom_arc": None, "purpose": None}]
_st, _rows = rb(_dup, executed=[_dup[0], _dup[1]])
check("a beat ruled twice is reported", _st == "MEASURED" and len(_rows) == 1,
      f"{_st} {_rows}")
_r = _rows[0] if _rows else {}
check("it names the beat and how many rulings",
      _r.get("beat") == 0 and _r.get("rulings") == 2, repr(_r)[:160])
check("it names the CHANGED field and both values",
      _r.get("changed", {}).get("zoom_arc") == ["hook", None],
      repr(_r.get("changed"))[:160])
check("it names the LOST field — non-empty then empty is the silent case, and "
      "the field that loses its value is the one nobody sees go",
      "zoom_arc" in _r.get("lost_fields", []) and "purpose" in _r.get("lost_fields", []),
      repr(_r.get("lost_fields")))
check("`built_from` reads `first` when the frozen copy kept the first ruling",
      _r.get("built_from") == "first", repr(_r.get("built_from")))

# built_from must actually FOLLOW the executed copy, or it is an assertion
# dressed as a measurement.
_st2, _rows2 = rb(_dup, executed=[_dup[2], _dup[1]])
check("`built_from` reads `later` when the frozen copy kept the later ruling — "
      "it is derived from the executed copy, not asserted from the merge rule",
      _rows2 and _rows2[0].get("built_from") == "later",
      repr(_rows2[0].get("built_from") if _rows2 else None))

_st3, _rows3 = rb(_dup, executed=[{"beat": 1, "treatment": ["none"]}])
check("a re-ruled beat missing from the executed copy reads NOT_EXECUTED, not "
      "`first`",
      _rows3 and _rows3[0].get("built_from") == "NOT_EXECUTED",
      repr(_rows3[0].get("built_from") if _rows3 else None))

# VACUITY: `all()` over an empty change set is True, so identical duplicates
# would read as a confident `first`. They are their own answer.
_ident = [{"beat": 3, "treatment": ["zoom"]}, {"beat": 3, "treatment": ["zoom"]}]
_st4, _rows4 = rb(_ident, executed=_ident[:1])
check("identical duplicate rulings read `identical`, not a vacuous `first` "
      "(all() over an empty change set is True)",
      _rows4 and _rows4[0].get("built_from") == "identical",
      repr(_rows4[0].get("built_from") if _rows4 else None))

check("a beat with no `beat` key cannot crash or count",
      rb([{"treatment": ["zoom"]}, {"treatment": ["zoom"]}]) == ("MEASURED", []))

# ── THE FREEZE MUST BE ABLE TO FAIL ──────────────────────────────────────────
# `built_from` is derived from `executed_verdicts`, the copy frozen at execute
# time. That derivation is worth nothing unless the freeze is verifiably
# untouched: if anything rewrites that copy in place, built_from returns the
# same confident value whether or not the freeze held. This file has paid for
# exactly that before — the half-ruling stripper rewriting `treatment` IN PLACE
# is why the frozen copy exists at all.
check("`verdicts_fingerprint` is a module-level function",
      "verdicts_fingerprint" in _fns)
check("the freeze records its own fingerprint at freeze time",
      "executed_verdicts_fp" in _assigned,
      "a fingerprint taken later describes whatever the copy became")
check("the call site passes the fingerprint, so built_from CAN fail",
      any(len(c.args) >= 3 for c in _calls),
      "two arguments means the freeze is trusted rather than checked")

_fp_ok = _app.verdicts_fingerprint([_dup[0], _dup[1]])
_st5, _rows5 = rb(_dup, executed=[_dup[0], _dup[1]], executed_fp=_fp_ok)
check("an intact freeze still answers `first`",
      _rows5 and _rows5[0].get("built_from") == "first",
      repr(_rows5[0].get("built_from") if _rows5 else None))

_st6, _rows6 = rb(_dup, executed=[dict(_dup[0], zoom_arc="TAMPERED"), _dup[1]],
                  executed_fp=_fp_ok)
check("a freeze that no longer matches its fingerprint reads FREEZE_MUTATED, "
      "not a confident `first` — a number that cannot fail is not a "
      "measurement",
      _rows6 and _rows6[0].get("built_from") == "FREEZE_MUTATED",
      repr(_rows6[0].get("built_from") if _rows6 else None))

check("a non-list fingerprints as None rather than raising",
      _app.verdicts_fingerprint(None) is None)

# ── THE SINGULAR TOOL'S REPLY MUST NOT DEDUPE ───────────────────────────────
# `"ruled": len({v["beat"] ...})` told an agent that had just re-ruled beat 0
# "ruled 10 of 10". It cannot see the contradiction, so it makes it again — and
# on round 63 it did, four times across two fixtures.
check("the singular beat_verdict reply reports RULINGS and BEATS separately",
      '"rulings": len(_bseen)' in _src and '"beats_ruled": len(set(_bseen))' in _src,
      "a deduped count cannot show the agent its own duplicate")
check("the reply NAMES the duplicated beat back to the agent",
      "DISCARDED_already_ruled" in _src,
      "a discarded re-ruling the agent cannot see is one it will make again")
check("no deduped `ruled` count survives in that reply",
      '"ruled": len({v["beat"] for v in led["beat_verdicts"]})' not in _src,
      "the lying count is still there")

# ── A KEY NEVER WRITTEN IS NOT A KEY SET TO None ────────────────────────────
# I reproduced the absent-as-zero family INSIDE the reporter built to expose it:
# `_r.get(k)` returned None for both, so round 63 printed `sfx 'yes' -> None`
# when the truth was `sfx 'yes' -> KEY ABSENT`. Not cosmetic — a STORED None
# defeats `.get("sfx", "no")` and the beat goes silently sfx-less, while an
# ABSENT key lets the default stand. A peer reported the stored-None failure
# from its own lane; on this lane the key is absent, and only a reporter that
# separates the two can say which lane has which.
_miss = [{"beat": 0, "sfx": "yes", "zoom_arc": "hook"},
         {"beat": 0, "sfx": None}]
_stm, _rm = rb(_miss, executed=_miss[:1])
check("a key present-then-ABSENT is rendered as absent, not as None",
      _rm and _rm[0]["changed"].get("zoom_arc") == ["hook", _app._MISSING],
      repr(_rm[0]["changed"].get("zoom_arc") if _rm else None))
check("a key present-then-None is rendered as None, distinct from absent",
      _rm and _rm[0]["changed"].get("sfx") == ["yes", None],
      repr(_rm[0]["changed"].get("sfx") if _rm else None))
check("both count as LOST — the field's guidance is gone either way",
      _rm and set(_rm[0]["lost_fields"]) == {"sfx", "zoom_arc"},
      repr(_rm[0]["lost_fields"] if _rm else None))

_noise = [{"beat": 0, "card_hero": None, "purpose": "hook"}, {"beat": 0}]
_stn, _rn = rb(_noise, executed=_noise[:1])
check("a field empty in EVERY ruling is not reported as a change — eleven "
      "`None -> <key absent>` rows per beat bury the ones that matter",
      _rn and "card_hero" not in _rn[0]["changed"] and "purpose" in _rn[0]["changed"],
      repr(sorted(_rn[0]["changed"]) if _rn else None))

# ── A TOOL MUST NOT ADVERTISE A FIELD ITS HANDLER DISCARDS ───────────────────
# `beat_verdict` declares 5 fields and its handler stores 4: `purpose` is
# offered to the agent and dropped on the floor. That is why `purpose` is LOST
# on all four of round 63's re-ruled beats. A field the schema invites and the
# code ignores is worse than one it never offered — the agent has no way to
# learn the difference.
_bv_decl = None
def _walk(o):
    global _bv_decl
    if isinstance(o, dict):
        if o.get("name") == "beat_verdict":
            _bv_decl = o
        for v in o.values():
            _walk(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            _walk(v)
for _n in dir(_app):
    try:
        _walk(getattr(_app, _n))
    except Exception:
        pass
check("the beat_verdict tool declaration is findable", _bv_decl is not None)
if _bv_decl:
    _sch = _bv_decl.get("input_schema") or _bv_decl.get("parameters") or {}
    _declared = set((_sch.get("properties") or {}))
    _lines = _src.splitlines()
    _st_i = next(i for i, l in enumerate(_lines)
                 if 'elif tu.name == "beat_verdict":' in l)
    _en_i = next(i for i, l in enumerate(_lines)
                 if i > _st_i and 'elif tu.name == "cut_verdict":' in l)
    _seg = "\n".join(_lines[_st_i:_en_i])
    # TWO ACCEPTABLE SHAPES, and the second is the stronger one. Originally
    # the handler named fields one by one and this counted the literals; it now
    # builds from VERDICT_FIELDS by comprehension, which reads EVERY schema
    # field rather than a hand list — so a literal count reports "all five
    # dropped" on a handler that drops none. Check the property, not the
    # spelling: either every declared field is named, or the handler projects
    # VERDICT_FIELDS and the declared set is inside it.
    _read = set(re.findall(r'tu\.input\.get\("([a-z_]+)"', _seg))
    _projects = ("for k in VERDICT_FIELDS" in _seg
                 and "tu.input.get(k)" in _seg)
    _covered = set(_app.VERDICT_FIELDS) if _projects else _read
    _dropped = sorted(_declared - _covered)
    check("every field beat_verdict DECLARES is read by its handler",
          not _dropped,
          "declared and silently discarded: %s — the schema invites the agent "
          "to supply it and the code throws it away" % _dropped)
    check("the singular handler projects the schema-derived field list rather "
          "than a hand-written one",
          _projects,
          "a hand list is a second vocabulary; it drifted silently once")

# ── BOTH PATHS EDIT EQUALLY WELL ────────────────────────────────────────────
# beat_verdict offered 5 of the 13 fields rule_all_beats offers. A re-edit
# surface missing eight fields is structurally worse at obeying the user, and
# NOTHING catches it: a field nobody offers produces no error anywhere. The
# agent is not offered it, cannot supply it, and the beat is ruled without it.
_p_props, _s_props = None, None
def _tool(nm):
    _hit = []
    def _w(o):
        if isinstance(o, dict):
            if o.get("name") == nm:
                _hit.append(o)
            for _v in o.values():
                _w(_v)
        elif isinstance(o, (list, tuple)):
            for _v in o:
                _w(_v)
    for _n in dir(_app):
        try:
            _w(getattr(_app, _n))
        except Exception:
            pass
    return _hit[0] if _hit else None

_pt, _st = _tool("rule_all_beats"), _tool("beat_verdict")
check("both verdict tools are declared", _pt is not None and _st is not None)
if _pt and _st:
    _p_props = set(((((_pt.get("input_schema") or {}).get("properties") or {})
                     .get("verdicts") or {}).get("items") or {})
                   .get("properties") or {})
    _s_props = set((_st.get("input_schema") or {}).get("properties") or {})
    check("the two ruling surfaces offer the SAME fields — neither path can "
          "make a ruling the other cannot",
          _p_props == _s_props,
          "only on rule_all_beats: %s   only on beat_verdict: %s"
          % (sorted(_p_props - _s_props), sorted(_s_props - _p_props)))
    check("and the set is the full schema vocabulary, not a shared subset",
          _s_props == set(_app.VERDICT_FIELDS),
          "beat_verdict offers %d of %d VERDICT_FIELDS"
          % (len(_s_props & set(_app.VERDICT_FIELDS)), len(_app.VERDICT_FIELDS)))

# DERIVED, NOT PASTED. Eight copied property blocks would drift the first time
# one side was edited — the divergence the fix exists to prevent, reintroduced
# by the fix. The singular tool's literal must NOT spell these out; they come
# from the plural tool's schema at import.
check("`_sync_verdict_surfaces` exists and runs at import",
      "_sync_verdict_surfaces" in _fns
      and "VERDICT_SURFACES_SYNCED" in _assigned_names,
      "a sync nobody calls leaves the surfaces as they were")
check("it reports WHICH fields it added, so a silent no-op is visible",
      isinstance(getattr(_app, "VERDICT_SURFACES_SYNCED", None), list))
_st_i = next(i for i, l in enumerate(_src.splitlines())
             if '"name": "beat_verdict",' in l)
_st_seg = "\n".join(_src.splitlines()[_st_i:_st_i + 120])
_pasted = [k for k in ("card_condition", "card_hero", "card_label",
                       "card_props", "sfx_name", "text_content", "zoom_arc")
           if '"%s":' % k in _st_seg]
check("the eight fields are DERIVED from rule_all_beats, not pasted into "
      "beat_verdict's literal",
      not _pasted,
      "hand-copied: %s — two declarations of one field is the divergence this "
      "closed, reintroduced by the fix for it" % _pasted)

# ── beat_verdict IS A RE-EDIT TOOL ──────────────────────────────────────────
# MEASURED over 24 runs in 8 rounds: 47 calls, 42 of them re-ruling a beat
# rule_all_beats had already ruled — 89% discarded by first-wins. That is a
# second ruling surface being reached for during a FIRST edit, where there is
# nothing to be surgical about, at ~4,400 prefix tokens.
_bv_filters = [n for n in ast.walk(_tree)
               if isinstance(n, ast.ListComp)
               and "beat_verdict" in ast.unparse(n)
               and "name" in ast.unparse(n)]
check("the tool list is filtered on `beat_verdict` at all",
      len(_bv_filters) >= 1)
_gate_src = _src
check("it is WITHHELD on a first edit, not merely discouraged — a capability "
      "in the schema will be used",
      "if not _reedit:" in _gate_src
      and 't.get("name") != "beat_verdict"' in _gate_src,
      "telling a model not to use a tool it has is a preference, not a "
      "property")

# THE SAVING IS CONDITIONAL. A first edit stops carrying it; a re-edit pays.
for _k in ("tool_prefix_tokens", "beat_verdict_offered",
           "beat_verdict_tokens_saved"):
    check("ledger key `%s` is assigned" % _k, _k in _assigned)
_ts_prints = [n for n in ast.walk(_tree) if isinstance(n, ast.Call)
              and getattr(n.func, "id", "") == "print"
              and "TOOL SURFACE" in ast.unparse(n)]
check("both numbers reach a real print() — a conditional saving reported as "
      "one number is the blended-metric failure",
      len(_ts_prints) >= 1)

# EQUAL CAPABILITY, ASSERTED IN THE APP. Withholding a tool from one path must
# not leave that path unable to do something the other can.
check("the app RAISES if rule_all_beats is ever absent from a path — "
      "withholding the singular tool is only safe while the plural one is "
      "universal",
      "rule_all_beats is not offered on this path" in _gate_src,
      "without that, a re-edit could only change beats one at a time")

# AND NO CAPABILITY IS LOST ON THE FIRST EDIT, because a re-ruling there is
# discarded whichever tool sends it. Driven through the shipped rule, not
# asserted from the source.
# THE FIVE CONTROLS ARE PART OF A `text` RULING, NOT DECORATION.
# `half_ruling_refusal` made size/case/where/colour/hold_s mandatory for any
# beat ruled `text`, and these fixtures predate it. Without them admit_verdict
# refuses, `beat_verdicts` comes back EMPTY, and the legs below die on an
# IndexError that reads as a defect in the admission surface. A FIXTURE GAP
# wearing a surface defect's clothes.
_CTL = {"purpose": "hook", "cut": "keep", "why": "w", "size": "medium",
        "case": "upper", "where": "upper_third",
        "colour": "white_on_footage", "hold_s": 2.0}

_led = {"beat_verdicts": []}
_seen = set()
_app.admit_verdict(_led, {**_CTL, "beat": 0, "treatment": ["text"],
                          "text_content": "a"}, _seen)
# NON-VACUITY, NAMED. If the first ruling is refused, every leg below is
# reading an empty list and the IndexError that follows names nothing.
assert _led["beat_verdicts"], (
    "the fixture ruling was REFUSED, so nothing below is being tested. "
    "admit_verdict has gained a requirement this fixture does not answer.")
_ok, _ = _app.admit_verdict(_led, {**_CTL, "beat": 0, "treatment": ["text"],
                                   "text_content": "CHANGED"}, _seen,
                            reedit=False)
check("on a FIRST edit a re-ruling is discarded whichever tool sends it, so "
      "withholding beat_verdict removes no working capability",
      _ok is False and _led["beat_verdicts"][0]["text_content"] == "a")
_led2 = {"beat_verdicts": [{"beat": 0, "treatment": ["text"],
                            "text_content": "a"}]}
_ok2, _ = _app.admit_verdict(_led2, {**_CTL, "beat": 0, "treatment": ["text"],
                                     "text_content": "CHANGED"}, {0},
                             reedit=True, reedit_targets={0})
check("on a RE-EDIT inside the declared scope the change LANDS — the tool does "
      "the job it is now named for",
      _ok2 is True and _led2["beat_verdicts"][0]["text_content"] == "CHANGED")
_led3 = {"beat_verdicts": [{"beat": 1, "treatment": ["text"],
                            "text_content": "b"}]}
_ok3, _ = _app.admit_verdict(_led3, {**_CTL, "beat": 1, "treatment": ["text"],
                                     "text_content": "NOPE"}, {1},
                             reedit=True, reedit_targets={0})
check("and a beat the instruction did NOT name is refused and counted",
      _ok3 is False and _led3["beat_verdicts"][0]["text_content"] == "b"
      and bool(_led3.get("reedit_refused")))

# IT REPAIRS A RULING, NOT A FILE — so the ordering rule written for the file
# tools must not hold it. Gated by the schema instead.
check("`beat_verdict` is no longer in _REPAIR_ONLY — refusing it until "
      "execute_plan has run would force a re-edit to rebuild the whole prior "
      "edit before changing one beat",
      '"author_component", "beat_verdict"}' not in _gate_src)

# THE WORDING IS THE OTHER HALF. It read as a general ruling surface, which is
# why it was picked up as an alternative to rule_all_beats.
if _bv_decl:
    _d = str(_bv_decl.get("description") or "")
    check("the description no longer tells the agent every beat needs one",
          "Every beat in your brief needs one" not in _d,
          "that sentence is what made it read as an alternative")
    check("it names itself a re-edit instrument",
          "RE-EDIT" in _d.upper())
    check("it points multi-beat changes at rule_all_beats rather than leaving "
          "the agent to infer it",
          "rule_all_beats" in _d)
    check("and it says a second ruling is DISCARDED, not merged",
          "DISCARDED" in _d.upper())

print()
if fails:
    print("RE-RULED VISIBLE: FAIL")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("RE-RULED VISIBLE: PASS — hoisted, called with both lists, three ledger "
      "keys, printed per beat; ABSENT/zero/changed/lost/built_from all hold")
