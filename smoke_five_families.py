"""SMOKE — the family surface, and an unsupported request is ANSWERED not edited.

CUTAWAY, TWICE. It was REMOVED 2026-09-06 and RULED BACK IN 2026-09-09, and the
guard had to be rewritten rather than reversed, because the two decisions are
about different things that share a name.

  removed   a TOOL that FETCHED footage — stock b-roll from a library. Priced
            per second, a different product. `place_cutaway` stays deleted.
  ruled in  a RULING on a beat: another moment in the material THE USER ALREADY
            UPLOADED, under the same narration. 72 of the 153 reference beats.

THE OLD GUARD CHECKED THE NAME. `"cutaway" not in fams` blocked both the fetch
and the thing that was never a fetch, so obeying it would have meant refusing a
ruling on grounds that never applied — and quietly deleting it would have thrown
away the protection that DID apply. So the name checks are gone and MECHANISM
checks replace them: no http, no library, no generator anywhere in the cutaway
path, and a cutaway must name the source moment it comes from.

WHY A SMOKE AND NOT A NOTE. This lane's own law is that A CAPABILITY IN THE
SCHEMA WILL BE USED — the prompt said "do not orchestrate" and the agent
orchestrated anyway. So the fetch has to be checked as an ABSENCE from the tool
surface and the code, or the next person to add a convenience helper quietly
restores a family with a per-second bill behind it.
"""
import ast
import sys

SRC = open("agentic_editor_app.py", encoding="utf-8").read()
TREE = ast.parse(SRC)
FAIL = []
ok = lambda c, m: None if c else FAIL.append(m)

_top = {}
for _n in TREE.body:
    if isinstance(_n, ast.Assign) and isinstance(_n.targets[0], ast.Name):
        try:
            _top[_n.targets[0].id] = ast.literal_eval(_n.value)
        except Exception:
            pass

# ── 1. the family vocabulary ────────────────────────────────────────────────
fams = _top.get("_TREATMENT_FAMILIES")
ok(fams is not None, "_TREATMENT_FAMILIES is gone")
# SIX now: `transition` joined when the seam-dressing family was wired. The
# count is asserted so a family cannot quietly leave, and the MEMBERS are
# asserted so it cannot quietly change identity either.
ok(set(fams or []) == {"card", "text", "sfx", "zoom", "cutaway",
                       "transition", "none"},
   f"the treatment families are {sorted(fams or [])}, not the seven expected — "
   f"a family that leaves this list stops being rulable while every other "
   f"surface still mentions it")


# GRADED, because the family builds. The 09-06 removal took the rate out on the
# correct grounds that grading a run against a capability the pipeline lacks is
# a standing false alarm; the reverse is worse now — the largest visual
# treatment in the reference shipping with nothing able to see whether it fires
# is precisely the "gate-green and did nothing" class.
ref = _top.get("REFERENCE_PER_25S") or {}
ok("cutaway" in ref,
   "cutaway has no rate in REFERENCE_PER_25S — the family builds and NOTHING "
   "grades it, so a run that places zero and a run that places four report the "
   "same")
nos = _top.get("REFERENCE_PER_25S_NOSPEECH") or {}
ok(set(ref) == set(nos),
   f"the two reference dicts have different families — speech {sorted(ref)} vs "
   f"no-speech {sorted(nos)}. derive_rubric picks one by beat_source, so a "
   f"family in only one of them is graded on one route and invisible on the "
   f"other, with nothing saying which happened")
# PLACEMENT_FAMILY is the declare_placement vocabulary, and cutaway is NOT a
# declared placement — the harness composites it from the beat ruling. Its
# absence here is correct and is asserted so nobody "completes" the table.
ok("cutaway" not in (_top.get("PLACEMENT_FAMILY") or {}),
   "cutaway is in PLACEMENT_FAMILY — it is not a declare_placement type, and "
   "adding it makes the scope check expect a manifest entry that never comes")

# ── 2. THE TOOL IS GONE FROM THE SURFACE ────────────────────────────────────
# Withholding the capability is the property; forbidding it in prose is only a
# preference.
# THE RETIRED SHAPE STAYS RETIRED. `place_cutaway` was a TOOL the agent called
# to fetch footage; the family Zac ruled in is a RULING on a beat that the
# harness builds from the upload. No tool, no fetch.
ok("def place_cutaway" not in SRC, "place_cutaway is implemented again")
# NOTHING IS FETCHED. This is the property the 2026-09-06 removal protected and
# the reason the name check existed. A cutaway may only come from material the
# user already gave us.
# ON THE AST, AND WITH THE DOCSTRING DROPPED. The first version of this scanned
# the function's SOURCE TEXT and failed on the word "stock" inside the docstring
# sentence "No stock, no generated footage" — the prose PROMISING the property
# tripped the check FOR the property. That is this repo's standing law arriving
# from the other direction: grep proves a string is present, and here it was
# present in a comment. Identifiers and real string constants only.
_cut_fn = next((n for n in ast.walk(TREE)
                if isinstance(n, ast.FunctionDef) and n.name == "cutaway_plan"),
               None)
ok(_cut_fn is not None, "cutaway_plan does not exist — the family has no "
                        "planner and every check below is vacuous")
_cut_tokens = set()
if _cut_fn is not None:
    _body = list(_cut_fn.body)
    if (_body and isinstance(_body[0], ast.Expr)
            and isinstance(_body[0].value, ast.Constant)
            and isinstance(_body[0].value.value, str)):
        _body = _body[1:]                       # the docstring is prose, not code
    for _st in _body:
        for _x in ast.walk(_st):
            if isinstance(_x, ast.Name):
                _cut_tokens.add(_x.id.lower())
            elif isinstance(_x, ast.Attribute):
                _cut_tokens.add(_x.attr.lower())
            elif isinstance(_x, ast.Constant) and isinstance(_x.value, str):
                _cut_tokens.add(_x.value.lower())
_cut_blob = " ".join(sorted(_cut_tokens))
for _bad in ("http://", "https://", "requests", "urlopen", "urllib", "boto3",
             "pexels", "getty", "unsplash", "stock_footage", "generate_video",
             "veo", "sora"):
    ok(_bad not in _cut_blob,
       f"the cutaway path references {_bad!r} in CODE — cutaway is the user's "
       f"own material only, and an external fetch is the retired family "
       f"returning under a name that is now allowed")
# NON-VACUITY: a token scan that found nothing forbids nothing.
ok(len(_cut_tokens) >= 20,
   f"only {len(_cut_tokens)} tokens read out of cutaway_plan — the AST walk is "
   f"not reaching its body, so every mechanism check above passes vacuously")
ok("set `cutaway_from_s` to one of these timestamps" in SRC,
   "cutaway has no source-moment field — it would name nothing, which is the "
   "ungrounded shape the intent requirement exists to prevent")
# BOTH LISTS. The agent's surface is `TOOLS + KNOWLEDGE_TOOLS` (see the
# dispatch), and TOOLS holds only 5 entries — execute_plan, probe_source,
# build_zoom, place_sfx, inspect_output. set_spec, rule_all_beats and
# place_cutaway all live in KNOWLEDGE_TOOLS. The first version of this smoke
# read TOOLS alone, so "place_cutaway not in names" was TRUE about a list that
# never contained it, and a mutation re-adding the tool passed clean. Checking
# the wrong collection is indistinguishable from checking nothing.
# IMPORTED, NOT literal_eval'd. The schemas stopped being pure literals the
# moment an enum was built from a constant (`"enum": list(MG_SELECTABLE_TYPES)`)
# — literal_eval returned nothing for the whole TOOLS assignment and this walk
# found ZERO enums. The non-vacuity leg below caught it, which is the only
# reason it was not a silent hole.
#
# The categorical fix is this repo's own law: IMPORT THE MODULE AND ASSERT THE
# SYMBOL. Source is where code might be; runtime is where it is.
import types as _types
import modal_stub                                         # noqa: E402
modal_stub.install()
import agentic_editor_app as _A5                                  # noqa: E402
tools = list(_A5.TOOLS) + list(_A5.KNOWLEDGE_TOOLS)
ok(getattr(_A5, "TOOLS", None) is not None, "TOOLS could not be read")
ok(getattr(_A5, "KNOWLEDGE_TOOLS", None) is not None,
   "KNOWLEDGE_TOOLS could not be read")
names = [t.get("name") for t in tools]
# Non-vacuity: the surface must contain the tools we know are there.
for _must in ("set_spec", "rule_all_beats", "execute_plan"):
    ok(_must in names,
       f"{_must!r} is not in the tool surface this smoke reads — it is "
       f"inspecting the wrong collection and every absence check below is vacuous")
ok("place_cutaway" not in names,
   "place_cutaway is back in the TOOLS schema — the agent will call it")
ok(len(names) == len(set(names)), f"duplicate tool names: {names}")

# Every enum the agent reads must be free of it — RECURSIVELY. The first
# version of this walked only input_schema.properties and MISSED the one that
# matters: `treatment` is an array, so its enum lives at
# properties.beats.items.properties.treatment.items.enum, two levels down. A
# mutation re-adding "cutaway" there passed cleanly. Depth is exactly where a
# schema check gets fooled, so walk the whole tree.
def _enums(node, path="input_schema"):
    if isinstance(node, dict):
        if isinstance(node.get("enum"), list):
            yield path, node["enum"]
        for k, v in node.items():
            yield from _enums(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _enums(v, f"{path}[{i}]")

# THE POSITIVE FORM, and it is the one that matters now. The removal-era check
# asserted cutaway was ABSENT from every enum; the family is back, so the same
# walk is turned around to prove it is actually OFFERED. A family in
# _TREATMENT_FAMILIES that no tool schema exposes is unrulable — the agent
# cannot name what it is not shown, and the run reports 0/4.22 forever with
# nothing anywhere saying why.
_seen_enums, _treat_enums, _cut_enums = 0, 0, 0
for t in (tools or []):
    for path, vals in _enums(t.get("input_schema") or {}):
        _seen_enums += 1
        if path.endswith("treatment.items") or path.endswith("treatment"):
            _treat_enums += 1
            if "cutaway" in vals:
                _cut_enums += 1
            else:
                FAIL.append(f"tool {t.get('name')!r} does NOT offer 'cutaway' "
                            f"at {path} — the family is rulable in "
                            f"_TREATMENT_FAMILIES and invisible to the agent")
# A walk that finds nothing asserts nothing.
ok(_seen_enums >= 5,
   f"only {_seen_enums} enums found in the tool schemas — the walk is not "
   f"reaching them, so this check passes vacuously")
ok(_treat_enums >= 2,
   f"only {_treat_enums} treatment enum(s) found — both rule_all_beats and "
   f"beat_verdict declare one, so a lower count means the walk is missing the "
   f"depth at which treatment lives and the check above is vacuous")
ok(_cut_enums == _treat_enums,
   f"cutaway is in {_cut_enums} of {_treat_enums} treatment enums — the two "
   f"declaration sites have DRIFTED, which is exactly the bug that made the "
   f"repair path declare treatment as a string while rule_all_beats declared "
   f"an array")

# ── 3. THE UNSUPPORTED CLASS ────────────────────────────────────────────────
modes = _top.get("SPEC_MODES") or ()
ok("unsupported" in modes, "set_spec has no 'unsupported' mode")
classes = _top.get("UNSUPPORTED_CLASSES") or ()
ok(set(classes) == {"generate_footage", "change_in_frame"},
   f"UNSUPPORTED_CLASSES changed: {classes}")

_ns = {}
for _n in TREE.body:
    if isinstance(_n, ast.Assign) and getattr(_n.targets[0], "id", "") in (
            "SPEC_MODES", "SPEC_FAMILIES", "UNSUPPORTED_CLASSES",
            "REFERENCE_PER_25S"):
        exec(compile(ast.Module([_n], []), "<s>", "exec"), _ns)
# The router's constants and its two pure functions, so the checks below DRIVE
# the shipped rule instead of restating it.
for _n in TREE.body:
    if isinstance(_n, ast.Assign) and getattr(_n.targets[0], "id", "").startswith(
            ("ROUTE_", "ROUTES_", "_ADDITIVE_MARKERS", "_ROUTE_COST",
             "_PLAN_KIND_INSERT")):
        exec(compile(ast.Module([_n], []), "<s>", "exec"), _ns)
for _fname in ("normalize_spec", "capability_route", "route_cost"):
    _f = next((n for n in TREE.body
               if isinstance(n, ast.FunctionDef) and n.name == _fname), None)
    if _f is not None:
        exec(compile(ast.Module([_f], []), "<s>", "exec"), _ns)
norm = _ns["normalize_spec"]

got = norm({"mode": "unsupported", "unsupported_class": "generate_footage"})
ok(got.get("unsupported_class") == "generate_footage",
   "normalize_spec drops the unsupported class")
try:
    norm({"mode": "unsupported"})
    FAIL.append("an unsupported request with NO class is accepted — an unnamed "
                "refusal cannot be counted, and the count is the demand signal")
except ValueError:
    pass
try:
    norm({"mode": "unsupported", "unsupported_class": "make_it_cool"})
    FAIL.append("an arbitrary unsupported_class is accepted")
except ValueError:
    pass
ok("cutaway" in _ns["SPEC_FAMILIES"],
   "cutaway is not in SPEC_FAMILIES — 'redo the cutaway on beat 4' could not "
   "be scoped, and a re-edit that cannot name the family it is changing "
   "re-runs the whole edit")

# ── 4. THE TERMINAL PATH IS REAL ────────────────────────────────────────────
# A flag that nothing reads is the producer-with-no-consumer defect this repo
# keeps rediscovering; assert BOTH ends exist.
ok(SRC.count("_unsupported_stop = False") == 1,
   "_unsupported_stop is not initialised before the loop — the ordinary path "
   "would raise NameError")
ok(SRC.count("if _unsupported_stop:") == 1,
   "nothing READS _unsupported_stop — the run would continue and produce an "
   "edit that ignores the request, and charge for it")

# PER TERMINAL, DISCOVERED FROM THE SOURCE — not counted. These three legs were
# `count(...) == 1` and `count(...) == 2`, fitted to a world with exactly ONE
# terminal (`unsupported`). K5's `needs_input` is a second, and the counts went
# red on correct code while asserting nothing about the new branch: a count
# tells you the number changed, never which terminal is unguarded. The property
# is per-terminal — EVERY terminal stops the loop and charges NOTHING — so the
# terminals are enumerated from the source and each is checked. A third one
# added later is covered the day it lands.
_terms = {}
for _if in ast.walk(TREE):
    if not isinstance(_if, ast.If):
        continue
    _names = [n.value.value for n in ast.walk(_if)
              if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
              and any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                      and t.slice.value == "terminal" for t in n.targets)]
    for _nm in _names:
        # the TIGHTEST enclosing If wins — a nested branch is the real owner
        _prev = _terms.get(_nm)
        if _prev is None or len(ast.dump(_if)) < len(ast.dump(_prev)):
            _terms[_nm] = _if
ok(len(_terms) >= 2,
   f"expected at least two terminals (unsupported_request, needs_input), "
   f"found {sorted(_terms)} — a terminal that stops the run without being "
   f"named here is one nobody checked for charging")
for _nm, _if in sorted(_terms.items()):
    _charged = [n for n in ast.walk(_if) if isinstance(n, ast.Dict)
                for k, v in zip(n.keys, n.values)
                if isinstance(k, ast.Constant) and k.value == "credit_charged"]
    _vals = [v.value for n in ast.walk(_if) if isinstance(n, ast.Dict)
             for k, v in zip(n.keys, n.values)
             if isinstance(k, ast.Constant) and k.value == "credit_charged"
             and isinstance(v, ast.Constant)]
    ok(len(_vals) >= 2,
       f"terminal {_nm!r} states credit_charged at {len(_vals)} site(s) — it "
       f"must say so at BOTH the ledger and the tool-result site, because an "
       f"existence check cannot see one of two flipped")
    ok(_vals and all(v is False for v in _vals),
       f"terminal {_nm!r} records credit_charged {_vals} — the user must not "
       f"be charged for a request we did not serve")
    ok(any(isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
           and n.value.value is True
           and any(getattr(t, "id", "") == "_unsupported_stop" for t in n.targets)
           for n in ast.walk(_if)),
       f"terminal {_nm!r} does not set _unsupported_stop — it names itself "
       f"terminal and then lets the run continue")
ok('"credit_charged": True' not in SRC,
   "something records credit_charged: True on a terminal path")

# ── THE CAPABILITY ROUTER ───────────────────────────────────────────────────
# set_spec's fourth branch was a refusal; it is a ROUTE now. One route is
# built, the others terminate and are COUNTED — unsupported_request has fired
# zero times across rounds 51-59, so what gets built next currently rests on a
# count nobody has taken.
_cr, _rcost = _ns.get("capability_route"), _ns.get("route_cost")
ok(callable(_cr) and callable(_rcost),
   "capability_route/route_cost are not importable — a router that can only be "
   "exercised through the dispatch is a rule the check has to restate")
if callable(_cr) and callable(_rcost):
    ok(_cr("full_edit", None, "punchy")[0] == "edit",
       "an editable request does not route to edit")
    ok(_cr("question", None, "what is this")[0] == "question",
       "a question does not route to question")
    ok(_cr("unsupported", "change_in_frame", "remove the background")[0]
       == "change_in_frame",
       "an in-frame change routes to a CLIP GENERATOR, which cannot serve it")
    # THE ADDITIVE RULE, both directions. "Add a shot OVER THIS" keeps the
    # user's edit; answering it as pure generation throws their footage away.
    ok(_cr("unsupported", "generate_footage", "add a shot of a city over this")[0]
       == "hybrid",
       "an ADDITIVE generate request does not route to hybrid — the user's own "
       "edit would be discarded")
    ok(_cr("unsupported", "generate_footage", "make a scene where a car drives")
       [1] == "AMBIGUOUS",
       "a non-additive generate request is answered silently instead of asked "
       "about — two readings differing by minutes and dollars")
    ok(_cr("weird_mode", None, "x")[1] == "AMBIGUOUS",
       "an unrecognised mode resolves silently rather than recording the "
       "ambiguity")
    ok(_cr("weird_mode", None, "x")[0] == "edit",
       "an unrecognised mode does not default to the BUILT route, which is the "
       "safe direction")
    # COST: measured where it was measured, ABSENT where nothing ever ran.
    ok(_rcost("edit")[0] == "MEASURED" and _rcost("edit")[1]["n"] == 15,
       "the edit route's cost is not MEASURED with its denominator")
    for _r in ("generate", "hybrid", "change_in_frame"):
        ok(_rcost(_r)[0] == "ABSENT",
           f"route {_r} quotes a cost figure — nothing here has ever run it, "
           f"and a router that quotes a number it does not have is probe "
           f"collapse making a product decision")
        ok("never been run" in str(_rcost(_r)[1]),
           f"route {_r}'s ABSENT does not say what must be measured first")
# COUNTED, not merely mentioned. `"route_demand" in SRC` survived deleting the
# increment, because the setdefault that creates the dict is a separate line —
# so the demand signal would have stayed permanently empty while the check read
# green. That is the exact defect this counter exists to end.
_inc = [n for n in ast.walk(TREE) if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Subscript)
                and isinstance(getattr(t, "value", None), ast.Subscript)
                and isinstance(t.value.slice, ast.Constant)
                and t.value.slice.value == "route_demand" for t in n.targets)
        and "+ 1" in ast.unparse(n.value)]
ok(bool(_inc) and "capability_route" in SRC,
   "nothing INCREMENTS led['route_demand'] — the demand signal would stay "
   "empty while the ledger key exists, which is how unsupported_request read "
   "zero for nine rounds")
ok('fail("route_ambiguous"' in SRC,
   "an AMBIGUOUS route does not fail loudly — it would be chosen silently")

# ── THE HYBRID ROUTE DELIVERS THE HALF IT CAN ───────────────────────────────
# "Add a shot of a city over this" is ADDITIVE: the user asked for their edit
# PLUS something. Refusing the whole job throws away the half we can serve.
for _fn in ("insert_request", "hybrid_delivery"):
    _f = next((n for n in TREE.body
               if isinstance(n, ast.FunctionDef) and n.name == _fn), None)
    if _f is not None:
        exec(compile(ast.Module([_f], []), "<s>", "exec"), _ns)
_ir, _hd = _ns.get("insert_request"), _ns.get("hybrid_delivery")
ok(callable(_ir) and callable(_hd),
   "insert_request/hybrid_delivery are not importable")
if callable(_ir) and callable(_hd):
    _r = _ir("add a shot of a city over this", "establishing")
    ok(_r["state"] == "UNFILLED",
       "an insert request does not record itself UNFILLED — a hole nobody can "
       "see is the same as a refusal nobody logged")
    ok(_r["asked_for"] and "fillable_by" in _r,
       "the insert request does not record WHAT was asked for and what could "
       "fill it — a tally that cannot justify building anything")
    ok(_hd([], True)[0] == "ABSENT",
       "a run with no insert requests is treated as a hybrid delivery")
    ok(_hd([1], True)[0] == "PARTIAL",
       "an edit that came out with an unfilled insert is not reported PARTIAL")
    ok(_hd([1, 2], False)[0] == "REFUSED",
       "a hybrid whose EDIT also failed is reported as a partial delivery — "
       "there is nothing to hand over")
    # IT MUST NEVER CLAIM THE INSERT HAPPENED.
    for _n2, _okk in (([1], True), ([1, 2], False)):
        _msg = _hd(_n2, _okk)[1].lower()
        ok("added" not in _msg and "i've added" not in _msg,
           "the hybrid message implies the insert was made")
        # THE NEGATION AS A PHRASE. "can create" alone survived cutting the
        # explanation down to "something I can create." — which says the
        # OPPOSITE and kept every word the check looked for. A disjunction of
        # loose substrings is not a test of a sentence's meaning.
        ok(("isn't something i can create" in _msg
            or "aren't something i can create" in _msg
            or "isn't something this editor can create" in _msg
            or "aren't something this editor can create" in _msg),
           "the hybrid message does not say, as a phrase, that the insert "
           "CANNOT be created — silence about the missing half is what reads "
           "as the product not working, and a message that says 'something I "
           "can create' says the opposite")
    ok("charged" in _hd([1], False)[1].lower(),
       "a REFUSED hybrid does not say nothing was charged")
ok("insert_requests" in SRC and 'led["capability_route"]["delivered"]' in SRC,
   "the hybrid route does not record its insert requests or what it delivered")
# THE HOLE SURVIVES A RE-EDIT. The plan is what the server persists and hands
# back, so anything not in it does not survive the turn — and an UNFILLED
# insert that vanishes is worse than a refusal, because the user was told it
# was recorded.
for _fn in ("plan_with_inserts", "inserts_from_plan"):
    _f = next((n for n in TREE.body
               if isinstance(n, ast.FunctionDef) and n.name == _fn), None)
    if _f is not None:
        exec(compile(ast.Module([_f], []), "<s>", "exec"), _ns)
_pwi, _ifp = _ns.get("plan_with_inserts"), _ns.get("inserts_from_plan")
ok(callable(_pwi) and callable(_ifp),
   "plan_with_inserts/inserts_from_plan are not importable")
if callable(_pwi) and callable(_ifp):
    _ruling = {"src_t0": 0.0, "src_t1": 2.0, "id": "a", "treatment": ["text"]}
    _hole = {"asked_for": "a city shot", "state": "UNFILLED"}
    _merged = _pwi([_ruling], [_hole])
    ok(len(_merged) == 2,
       "an UNFILLED insert does not reach the durable plan — it would vanish on "
       "the next turn after the user was told it was recorded")
    _r, _i = _ifp(_merged)
    ok(len(_r) == 1 and len(_i) == 1 and _i[0]["state"] == "UNFILLED",
       "a loaded plan does not split back into rulings and inserts")
    ok("kind" not in _i[0],
       "the insert keeps its transport marker after loading, which would reach "
       "the ruling path as a stray field")
    # BACKWARD COMPATIBILITY, or the first re-edit after this shipped discards
    # every plan written before it.
    _r2, _i2 = _ifp([_ruling])
    ok(len(_r2) == 1 and not _i2,
       "a plan written BEFORE inserts existed is not read as rulings — every "
       "prior plan would be discarded on its first re-edit")
    # A FILLED insert must NOT be carried forward as a hole.
    ok(len(_pwi([], [dict(_hole, state="FILLED")])) == 0,
       "a FILLED insert is carried forward as an unfilled hole")
# THE RESTORE, read from the AST. `"insert_requests" in SRC` appears in this
# file twice now and in the app many times, so it says nothing about whether
# the RE-EDIT path restores them. The ratchet caught this one before it
# shipped, which is what it is for.
_rest = [n for n in ast.walk(TREE) if isinstance(n, ast.Assign)
         and any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                 and t.slice.value == "insert_requests" for t in n.targets)
         and "_prior_inserts" in ast.unparse(n.value)]
ok(bool(_rest),
   "the re-edit path does not assign the carried inserts back into the ledger "
   "— a hole the user was told we recorded would be dropped on the next turn")

_hyb = [n for n in ast.walk(TREE) if isinstance(n, ast.If)
        and any(isinstance(x, ast.Name) and x.id == "ROUTE_HYBRID"
                for x in ast.walk(n.test))
        and any(isinstance(x, ast.Continue) for x in ast.walk(n))
        and not any(isinstance(x, ast.Name) and x.id == "_unsupported_stop"
                    for x in ast.walk(n))]
ok(bool(_hyb),
   "the hybrid branch either does not exist or TERMINATES the run — it is the "
   "one route that must proceed to the edit")
_break = [n for n in ast.walk(TREE)
          if isinstance(n, ast.If)
          and any(getattr(t, "id", "") == "_unsupported_stop" for t in ast.walk(n.test))
          and any(isinstance(b, ast.Break) for b in ast.walk(n))]
ok(len(_break) == 1,
   "the _unsupported_stop branch does not BREAK the turn loop — it would fall "
   "through and keep spending turns")

# ── 5. THE UNSUPPORTED BRANCH MUST SHORT-CIRCUIT derive_rubric ─────────────
# derive_rubric REJECTS mode 'unsupported' (RUBRIC_MODES is the three editing
# modes), which is correct — an unsupported request has no rubric. It is safe
# only because the handler `continue`s first. Reorder those and every
# unsupported request raises ValueError instead of answering the user, so the
# ordering is asserted rather than remembered.
_ifs = [n for n in ast.walk(TREE)
        if isinstance(n, ast.If)
        and any(isinstance(c, ast.Constant) and c.value == "unsupported"
                for c in ast.walk(n.test))]
_guard = [n for n in _ifs if any(isinstance(x, ast.Continue) for x in ast.walk(n))]
ok(len(_guard) >= 1,
   "the set_spec 'unsupported' branch does not `continue` — control would fall "
   "through to derive_rubric, which rejects the mode, and the user would get a "
   "ValueError instead of the plain answer")
_dr = [n for n in ast.walk(TREE)
       if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "derive_rubric"]
ok(_dr and _guard and min(g.lineno for g in _guard) < min(d.lineno for d in _dr),
   "derive_rubric is called BEFORE the unsupported branch short-circuits")
# And the rubric never carries the removed family.
_rm = {}
for _n in TREE.body:
    if isinstance(_n, ast.Assign) and isinstance(_n.targets[0], ast.Name):
        try:
            exec(compile(ast.Module([_n], []), "<s>", "exec"), _rm)
        except Exception:
            pass
for _n in TREE.body:
    if isinstance(_n, ast.FunctionDef) and _n.name == "derive_rubric":
        exec(compile(ast.Module([_n], []), "<s>", "exec"), _rm)
_r = _rm["derive_rubric"](None, "full_edit")
ok(_r["targets"].get("cutaway") == 4.22,
   f"derive_rubric does not carry the corpus cutaway rate: {_r}")
ok(_r["source"].get("cutaway") == "corpus",
   "the cutaway target is not marked 'corpus' — a rate that is not attributed "
   "cannot be told from a vibe-directed one at ruling time")
ok(set(_r["targets"]) == {"text", "cut", "card", "sfx", "zoom", "cutaway",
                          "transition"},
   f"the rubric target set changed: {sorted(_r['targets'])}")

# ── 6. ONE MANIFEST PER RUN, NOT A UNION OF EVERY ATTEMPT ──────────────────
# execute_plan rebuilds the whole pipeline, so a second call REPLACES the first
# one's output — but placements were appended, so two calls declared both builds
# while `built` reported only the last. Round 13 measured it exactly: 3 calls ->
# text BUILT 2 / DECLARED 4, 2 calls -> 3 / 5, 1 call -> no gap.
_ep = [n for n in ast.walk(TREE)
       if isinstance(n, ast.FunctionDef) and n.name == "execute_plan"]
ok(len(_ep) == 1, "execute_plan not found (or defined more than once)")
if _ep:
    _resets = [n for n in ast.walk(_ep[0])
               if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Subscript)
                       and getattr(t.value, "id", "") == "led"
                       and getattr(getattr(t, "slice", None), "value", None) == "placements"
                       for t in n.targets)
               and isinstance(n.value, ast.List) and not n.value.elts]
    ok(len(_resets) == 1,
       "execute_plan does not reset led['placements'] to [] — a second call "
       "appends to the first call's manifest, so the declared count becomes a "
       "union of every attempt while `built` reports only the last")
    _appends = [n for n in ast.walk(_ep[0])
                if isinstance(n, ast.Call)
                and getattr(n.func, "attr", "") == "append"
                and "placements" in ast.dump(n.func)]
    if _resets and _appends:
        ok(_resets[0].lineno < min(a.lineno for a in _appends),
           "the placements reset runs AFTER the declare loop — it would erase "
           "the manifest it just wrote")

# ── 7. A SILENT CLIP IS NOT A TALKING HEAD WITH THE SOUND OFF ─────────────
# REFERENCE_PER_25S is a TALKING-HEAD corpus — its text rate is
# transcript-derived. Round 20 was GREEN with four of five fixtures placing one
# family, and the mix check would have fired forever against a target never
# measured for these sources.
#
# MEASURED over 1,463 shipped no-speech jobs (moodreel + minimal, 30 days):
# cut 4.26, card 0.23 (91.7% place zero), transition 0.27, and text 0.00 —
# because the no-speech plan shape has NO text field at all.
_ns_ref = _top.get("REFERENCE_PER_25S_NOSPEECH")
ok(isinstance(_ns_ref, dict) and _ns_ref,
   "there is no no-speech reference — silent sources are being scored against a "
   "talking-head corpus whose text rate is transcript-derived")
if isinstance(_ns_ref, dict):
    ok(set(_ns_ref) == set(_top.get("REFERENCE_PER_25S") or {}),
       f"the two references cover different families: {sorted(_ns_ref)} vs "
       f"{sorted(_top.get('REFERENCE_PER_25S') or {})} — derive_rubric iterates "
       f"one of them, so a family present in only one silently loses its target")
    ok(_ns_ref.get("text") == 0.0,
       f"no-speech text reference is {_ns_ref.get('text')}, not 0.0 — production "
       f"cannot place text on these sources at all")
    ok(_ns_ref.get("cut", 0) > 3.0,
       "the no-speech cut reference collapsed — cut is the one family that "
       "transfers between the two corpora (4.26 vs 4.75)")

_dr = next((n for n in TREE.body
            if isinstance(n, ast.FunctionDef) and n.name == "derive_rubric"), None)
ok(_dr is not None and any(a.arg == "beat_source" for a in _dr.args.args),
   "derive_rubric cannot tell which corpus applies — it takes no beat_source")
_calls = [n for n in ast.walk(TREE)
          if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "derive_rubric"]
ok(_calls and all(any(k.arg == "beat_source" for k in c.keywords) for c in _calls),
   "a derive_rubric call site does not pass beat_source — it would silently "
   "score a silent clip against the talking-head corpus, which is the defect "
   "this exists to remove")

if FAIL:
    print("FAIL smoke_five_families:")
    for f in FAIL:
        print("  - " + f)
    sys.exit(1)
print("ok smoke_five_families — 7 families, no fetch path, cutaway offered in "
      "rates/rubric, unsupported class validated, terminal path breaks the loop "
      "and charges nothing")
