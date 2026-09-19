#!/usr/bin/env python3
"""ONE SESSION decides, places, looks and fixes — and nothing is keyed to a plan.

RULED BY ZAC 2026-09-16: "One session: watches the source, has the references
cached, decides, places, looks, fixes, exports. No plan document, no
translation, no second prefix."

THE FAILURE CLASS THIS IS AIMED AT, and both instances were real and found by
writing it: the ChatCut harness was built around a PLAN, and removing the plan
leaves every number derived from it silently at its `or` default rather than
raising.

    _n_calls      = len({...}) or 1     -> PASS 2 fired after the FIRST
                                           placement, handing the agent review
                                           frames of an edit barely started
    _total_frames = max([...] or [0])   -> the review render was asked for a
                                           ZERO-frame window, and reported
                                           "the harness could not render the
                                           edit" about a good timeline

Both are absence rendered as a value, in a harness whose own rule file names
that as the oldest defect here. Neither would have raised; both would have read
as the agent ignoring its review pass.

THE LEGS:
  1. the agent can WATCH THE SOURCE — inspect_asset, source time, its words
  2. the agent is NOT offered the authoring tool. This leg is INVERTED from
     what I first wrote, and the inversion is the finding: `prestage`
     registers the whole 35-component registry regardless of titles, so
     offering `create_motion_graphic_from_code` contradicted the prefix's own
     "you never author component code" — and a contradiction the agent has to
     resolve is a decision this path exists to remove
  3. PASS 2 is triggered by the agent SAYING SO, not by a count from a plan
  4. the review window is read from the TIMELINE, not from a plan manifest
  5. the single prefix carries what the planner's prefix carried — driven by
     CALLING build_system_prompt, not by reading its source
  6. the mode rule has ONE copy and both surfaces read it
  7. the first message matches the agent's ROLE and carries the standard
  8. the pixel hops run WITHOUT a plan, and BEFORE the export
  9. the deciding branch gets a two-pass loop, and no surface the agent reads
     instructs a step it cannot take

WHAT LEG 5 DOES NOT PROVE, said rather than implied: /craft does not exist on a
developer machine, so the mode rule, the sound library and the component sheet
come back ABSENT here. This asserts the section is emitted and that its absence
is LOUD. That the file is actually in the image is a different question and
`smoke_the_mode_is_read_not_weighed.py` asks it, of the mounts.

RED-proven at the bottom.
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modal_stub                                                 # noqa: E402
modal_stub.install()
import chatcut_job_app as J                                       # noqa: E402

SRC = open(os.path.join(HERE, "chatcut_job_app.py"), encoding="utf-8").read()
fail = []


def _needed(src):
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "NEEDED_TOOLS"
                for t in n.targets):
            return [e.value for e in n.value.elts
                    if isinstance(e, ast.Constant)]
    return None


def _lit(src, name):
    """A module-level string constant's VALUE, for checking what it says."""
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in n.targets):
            try:
                return ast.literal_eval(n.value)
            except Exception:                                     # noqa: BLE001
                return ast.unparse(n.value)
    return ""


def _fn(src, name):
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.FunctionDef,)) and n.name == name:
            return n
    return None


def _module_of(src):
    """Exec a mutated chatcut_job_app source and hand back the module.

    THE TRAP THIS CLOSES, AND I WALKED INTO IT AGAIN. The role and references
    legs called `J.pass1_message` — the LIVE import — while the mutations
    edited SOURCE TEXT. The two never meet, so both mutations changed real
    bytes and could not change the verdict: a check exercising a copy of the
    thing it claims to test. It is written down in
    smoke_the_mode_is_read_not_weighed.py, by me, about the same mistake.
    """
    if src is SRC:
        return J
    ns = {"__name__": "cja_mutant", "__file__": J.__file__}
    exec(compile(src, "<mutant>", "exec"), ns)

    class _Mod:
        """A view whose writes reach the exec'd GLOBALS, not a copy of them.

        `types.ModuleType()` + `__dict__.update(ns)` COPIES the namespace, so
        stubbing `mod._frames_of` left the function's own `__globals__`
        untouched and it went on calling the real one. The same
        check-exercising-a-copy shape one level down, inside the fix for it.
        """
        def __getattr__(self, k):
            try:
                return ns[k]
            except KeyError:
                raise AttributeError(k)

        def __setattr__(self, k, v):
            ns[k] = v

    return _Mod()


def legs(src=None, prompt=None):
    src = src if src is not None else SRC
    mod = _module_of(src)
    out = []

    tools = _needed(src)
    if not tools:
        out.append(("tools", "NEEDED_TOOLS did not resolve — every tool leg "
                             "below would assert nothing"))
        return out

    # 1 + 2. IT DECIDES, SO IT MUST BE ABLE TO SEE AND TO AUTHOR
    if "inspect_asset" not in tools:
        out.append(("watch", "the agent has no inspect_asset — it decides "
                             "what to place without ever seeing the source at "
                             "source time"))
    # THE LEG INVERTED, and the inversion is the finding. I first asserted the
    # agent MUST have `create_motion_graphic_from_code`, reasoning that the
    # harness cannot prestage a title it does not know. It does not need to:
    # `prestage` registers the whole 35-component registry with assetIds
    # regardless of titles, and the agent sets the words through
    # `propertyOverrides`. Offering the authoring tool contradicted the
    # prefix's own "you never author component code", and a contradiction the
    # agent has to resolve is a decision this path exists to remove.
    if "create_motion_graphic_from_code" in tools:
        out.append(("author", "the agent is offered "
                              "create_motion_graphic_from_code while the "
                              "prefix tells it never to author component "
                              "code — one of the two is wrong and the agent "
                              "has to decide which"))
    if "edit_item" not in tools:
        out.append(("author", "the agent cannot place anything at all"))

    # 3. THE REWATCH FOLLOWS THE PLACING TURN, IN THE LOOP (2026-09-17).
    # The DONE-mark machine and rewatch_decision are gone; run_three_turns
    # serves rewatch 1 after turn 1's ops and rewatch 2 after turn 2. Asked of
    # the loop's own source, and driven in smoke_the_machine_holds_off_the_happy_path.
    _edit = _fn(src, "edit")
    _loop = _fn(src, "run_three_turns")
    if _edit is None or "run_three_turns(" not in ast.unparse(_edit):
        out.append(("trigger", "edit() does not run the three-turn loop"))
    if _loop is None or "rewatch(1, False)" not in ast.unparse(_loop) or "rewatch(2, True)" not in ast.unparse(_loop):
        out.append(("trigger", "the loop does not serve a rewatch after the placing turn and the review turn"))
    # 4. THE REVIEW WINDOW COMES FROM THE TIMELINE
    if _edit is not None:
        _e = ast.unparse(_edit)
        # AIMED AT THE PROPERTY, NOT AT THE NAME. My first version refused
        # any mention of plan_manifest in edit(); HOP 2 legitimately still
        # calls it for a run that DOES carry a plan, and the leg reported a
        # correct implementation as broken. A check tight enough to reject
        # correct work is not a check. What must not happen is a plan-derived
        # number silently becoming the review window.
        if "_edit_frames(tok, _stage[\"projectId\"], _total_frames)" in _e:
            out.append(("window", "the review window is _total_frames, which "
                                  "is derived from a plan manifest — with no "
                                  "plan that is zero, and a zero-frame render "
                                  "reports as a harness failure"))
        if "hop2_prestage" in _e and "if not _manifest:" not in _e:
            out.append(("hop2", "HOP 2 runs against a possibly-empty "
                                  "manifest with no ABSENT branch — it prints "
                                  "MEASURED 0 add(s) and asserts nothing"))
        # THE PROPERTY: inside the REWATCH, the window handed to the frame
        # instrument is bound from a timeline_end(...) call. (The first form
        # asked whether the word appeared anywhere in edit(); a second,
        # unrelated timeline_end call — the constraint check's — made the
        # mutation vacuous. Substring presence over a whole function is not
        # a property of the rewatch.)
        _rwf = next((n for n in ast.walk(_edit) if isinstance(n, ast.FunctionDef) and n.name == "_rewatch"), None)
        _win_from_timeline = False
        if _rwf is not None:
            _bound = {t.id for n in ast.walk(_rwf) if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                      and ast.unparse(n.value.func).endswith("timeline_end") for t in n.targets
                      for t in ([t] if isinstance(t, ast.Name) else [e for e in getattr(t, "elts", []) if isinstance(e, ast.Name)])}
            _win_from_timeline = any(isinstance(n, ast.Call) and ast.unparse(n.func).endswith("_preview_frames") and len(n.args) > 2
                                     and isinstance(n.args[2], ast.Name) and n.args[2].id in _bound for n in ast.walk(_rwf))
        if not _win_from_timeline:
            out.append(("window", "the rewatch's review window is not bound from a "
                                  "timeline_end(...) call on the timeline read back"))

    # 8. THE PIXEL HOPS RUN WITHOUT A PLAN, AND BEFORE THE EXPORT.
    # Four of seven hops guarded on `plan`, so removing the plan turned them
    # ABSENT — including BOTH pixel checks, the only ones that can see a
    # placement that is present but illegible, covered, or on a face. And the
    # export ran 150 lines ABOVE them, so even when they did run they were
    # post-hoc diagnostics wearing a gate's name.
    for nm in ("verify_hop5_composition", "verify_hop6_clear"):
        fn = _fn(src, nm)
        if fn is None:
            out.append(("hops", "%s is gone" % nm))
            continue
        guard = next((l.strip() for l in ast.unparse(fn).splitlines()
                      if l.strip().startswith("if not")), "")
        if "plan and" in guard.replace("(plan or items)", ""):
            out.append(("hops", "%s still requires a plan, so it is ABSENT on "
                                "every single-agent run: %s" % (nm, guard[:70])))
    if _edit is not None:
        _e2 = ast.unparse(_edit)
        _i_hop = _e2.find("verify_hop5_composition")
        _i_exp = _e2.find("harness_export")
        if _i_hop < 0 or _i_exp < 0:
            out.append(("order", "the hop or the export is missing from edit()"))
        elif _i_exp < _i_hop:
            out.append(("order", "the EXPORT runs before the pixel hops — they "
                                 "are diagnostics, not a gate, and the ruling "
                                 "was checks BETWEEN the placement and the "
                                 "export"))
        # TWO SITES READ THE CAPTION BAND AND BOTH ARE LOAD-BEARING, so one
        # substring over edit() is a FLOOR ON A SUM: killing either site leaves
        # "caption_band(tok" in the source and the leg green. Measured — the
        # hop-6 mutation applied cleanly and the leg did NOT fire, because the
        # review site still carried the words.
        #
        # ASKED OF THE AST, NOT OF THE TEXT. `_e2` is `ast.unparse` output, so
        # it is NORMALISED source: it drops the redundant parens around the
        # hop-6 conditional, and a needle written from the file as typed can
        # never match it. My first split used one and reported a defect in
        # working code — a reader keyed to wording, inside the fix for a reader
        # keyed to wording. Bind each reader to the NAME it assigns.
        _cap_readers = set()
        for _n in ast.walk(_edit):
            if not isinstance(_n, ast.Assign):
                continue
            if not any(isinstance(_c, ast.Call)
                       and getattr(_c.func, "id", "") == "caption_band"
                       for _c in ast.walk(_n.value)):
                continue
            for _t in _n.targets:
                for _el in (getattr(_t, "elts", None) or [_t]):
                    if isinstance(_el, ast.Name):
                        _cap_readers.add(_el.id)
        if "_cap_band" not in _cap_readers:
            out.append(("caption", "HOP 6 no longer reads the caption band, so "
                                   "a card landing on the captions is seen by "
                                   "neither hop 5 (no track item) nor hop 6"))
        if "_cb" not in _cap_readers:
            out.append(("capreview", "the REVIEW no longer reads the caption "
                                     "band, so the acceptance criteria fall "
                                     "back to 'judge that one BY EYE' for "
                                     "every placement"))
        # the withheld placement is confirmed gone by a READ, not by a response
        if "IS STILL ON THE TIMELINE after the delete" not in _e2:
            out.append(("delete", "the withheld placement is trusted to the "
                                  "delete response — the element shape and "
                                  "the response key are both unobserved, and "
                                  "a wrong one renders as success"))
    # THE GATE'S OWN REPORT MUST REACH SOMEWHERE A PERSON READS.
    # ASKED OF THE AST. My first version was `"report_lines" not in src`, and
    # the mutation that removed the CALL left the name in the comment above it
    # — a substring that survives the change it exists to catch, for the sixth
    # consecutive session this repo has recorded.
    _gb = _fn(src, "gate_b")
    if _gb is None:
        out.append(("report", "gate_b is gone"))
    elif not any(isinstance(c, ast.Call)
                 and ast.unparse(c.func).endswith("report_lines")
                 for c in ast.walk(_gb)):
        out.append(("report", "gate_b never calls report_lines — the "
                              "findings' `read:` evidence goes nowhere, and a "
                              "producer with no consumer is the class this "
                              "lane keeps paying for"))

    # 9. THE DECIDING BRANCH GETS A TWO-PASS LOOP, AND NO DEAD INSTRUCTIONS.
    # `TWO_TURN_LOOP` reached ONLY the plan branch, so the single agent — the
    # one that has to rule AND place — never received the instruction to batch
    # at all. The last recorded run spent 9 model turns on 8 tool calls: two
    # edit_item where one batch was asked for, three preview_timeline, and an
    # inspect_item re-reading an id edit_item had already returned.
    # THE BRANCH, FOUND BY STRUCTURE. `ast.unparse(edit).split("else:")[-1]`
    # takes the LAST `else` in a 900-line function, which is not the prompt's —
    # so the leg read an unrelated block and both it and its mutation were
    # about nothing. Find the `if` whose two arms each assign `prompt`.
    # RE-AIMED 2026-09-18: the plan path is gone (ruling C); the deciding
    # prompt is the ONE assignment to `prompt` that carries THE BRIEF.
    _branch = None
    for _n3 in ast.walk(_edit or ast.parse("")):
        if isinstance(_n3, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "prompt" for t in _n3.targets) \
                and any(isinstance(c, ast.Constant) and isinstance(c.value, str) and "THE BRIEF" in c.value for c in ast.walk(_n3.value)):
            _branch = _n3
            break
    if _branch is None:
        out.append(("loop", "the deciding prompt (the `prompt =` carrying THE BRIEF) was not found — "
                            "every leg below it would assert nothing"))
    else:
        _else = ast.unparse(_branch.value)
        # THE PROPERTY, NOT THE CONSTANT. This required `TWO_TURN_LOOP`
        # by name. That block was 3,578 characters of procedure the agent had
        # already been told, and it was replaced by one paragraph carrying the
        # same loop — so the leg went red on correct code. What must hold is
        # that the deciding prompt tells the agent to BATCH and names BOTH
        # marks; how it says so is not the check's business.
        _l = _else.lower()
        if "one edit_item call" not in _l:
            out.append(("loop", "the deciding prompt never tells the agent to "
                                "place in ONE call — placing item by item "
                                "spends a model turn each"))
        # REVERSED 2026-09-18 (rulings 2-4): there are no marks. The harness
        # renders after every call; the prompt must name NO /work/DONE file and
        # must tell the agent the frames are sent to it.
        if "/work/done" in _l:
            out.append(("loop", "the deciding prompt still names a /work/DONE mark — "
                                "the harness renders after every call and waits for nothing"))
        if "call no preview" not in _l or "sends you the frames" not in _l:
            out.append(("loop", "the deciding prompt does not tell the agent the frames are "
                                "sent to it and that it previews nothing itself"))
        # ...and nothing may instruct a step the agent cannot take
        # THE POPULATION WAS TOO NARROW. This looked only at the PROMPT
        # branch, and `pass2_message` — the message the agent reads before it
        # fixes anything — still ended "If it is right, submit the export",
        # naming a tool that is not in its list. A dead instruction is dead
        # wherever it is written, so the check covers every surface the agent
        # reads, not the one I happened to have edited.
        _surfaces = dict(_else=_else,
                         pass2=ast.unparse(_fn(src, "rewatch_message")
                                           or ast.parse("")),
                         loop=_lit(src, "TWO_TURN_LOOP"))
        for dead, why in (
                ("BEFORE RENDER", "the agent does not render; the harness "
                                  "does, when /work/DONE is written"),
                ("submit the export", "the agent has no submit_export tool")):
            _where = [k for k, v in _surfaces.items() if dead in v]
            if _where:
                out.append(("deadinstr",
                            "%s still says %r — %s. An instruction that "
                            "survives the thing it instructed is read as "
                            "current by the model." % (_where, dead, why)))

    # 5. THE SINGLE PREFIX CARRIES THE PLANNER'S MATERIAL — BY CALLING IT
    p = prompt if prompt is not None else J.build_system_prompt()
    # "HOW TO SCOPE THIS JOB" left the prefix by ruling (mode_rule -> 0).
    for kind, needle in (("prefix", "HOW EACH FAMILY IS BUILT"),
                         ("prefix", "THE SOUND LIBRARY"),
                         ("record", "You write no files"),
                         ("record", '"why" field'),
                         ("record", "You have no submit_export tool")):
        if needle not in p:
            out.append((kind, "the prefix does not carry %r" % needle))
    # REVERSED 2026-09-18: the record is DERIVED from the read-back; the prefix
    # must NOT ask for the files it used to.
    for gone in ("/work/rulings.json", "/work/spec.json", "/work/DONE"):
        if gone in p:
            out.append(("record", "the prefix still asks for %r — the record is derived" % gone))
    # 7. THE FIRST MESSAGE MATCHES THE AGENT'S ROLE, AND CARRIES THE STANDARD.
    # DRIVEN BY CALLING pass1_message, both ways. This is the defect where a
    # rule written for the old role survives the promotion: handed to the agent
    # that MAKES the editorial decisions, "every editorial decision is already
    # made, and inventing more is the failure" is an instruction to place
    # nothing — and it would read as the model being timid.
    _of = mod.watch_asset
    try:
        mod.watch_asset = lambda *a, **k: {"state": "ABSENT", "why": "stubbed", "sheets": []}
        _dec = mod.pass1_message("", [], None, None, deciding=True)
        _exe = mod.pass1_message("P", [], None, None, deciding=False)
    finally:
        mod.watch_asset = _of
    _dtxt = " ".join(b.get("text", "") for b in _dec["message"]["content"])
    _etxt = " ".join(b.get("text", "") for b in _exe["message"]["content"])
    # RETIRED 2026-09-17 by ruling: the executor/decider rubric ("inventing
    # more is the failure" / "the decisions are yours") and the
    # reference-standard block left the first message — one session, no plan,
    # and the watch holds the ten readings while the paragraph names them as
    # the bar. What the message must still never do is omit the SOURCE
    # silently: served from watch_asset, or a named absence.
    if "THE SOURCE —" not in _dtxt and "THE SOURCE FRAMES: " not in _dtxt:
        out.append(("source", "pass 1 carries neither the source watch nor a "
                              "named absence — an agent placing on footage it "
                              "was never shown, for reasons nobody can see"))

    # ...and an absent section must be LOUD, never silently dropped
    if "HOW TO SCOPE THIS JOB : ABSENT" in p and "43%" not in p:
        out.append(("prefix", "the mode rule is ABSENT and the prompt does "
                              "not say what that costs"))
    return out


for k, m in legs():
    fail.append("[%s] %s" % (k, m))

# ── 6. THE MODE RULE HAS ONE COPY ───────────────────────────────────────────
_rule = os.path.join(HERE, "mode_rule.txt")
if not os.path.exists(_rule):
    fail.append("[onecopy] mode_rule.txt is gone — the rule is back to living "
                "inside one of the two surfaces that need it")
else:
    _txt = open(_rule, encoding="utf-8").read()
    _probe = "ANSWER THIS BY MATCHING"
    _dupes = [f for f in ("agentic_editor_app.py", "chatcut_job_app.py")
              if _probe in open(os.path.join(HERE, f), encoding="utf-8").read()]
    if _dupes:
        fail.append("[onecopy] the rule text is ALSO inline in %s. Two copies "
                    "of a rule is how a rule ends up enforced on one of them."
                    % _dupes)
    if len(_txt) < 2000:
        fail.append("[onecopy] mode_rule.txt is %d chars — too short to be the "
                    "rule; a truncated file would satisfy every other leg"
                    % len(_txt))

# ── RED PROOF ───────────────────────────────────────────────────────────────
red = 0
MUT = (
    ("the agent loses its view of the source", "watch",
     lambda s: s.replace('    "inspect_asset",', '')),
    ("the authoring tool is offered again, against the prefix", "author",
     lambda s: s.replace('    "edit_item",          # place',
                         '    "create_motion_graphic_from_code",\n'
                         '    "edit_item",          # place')),
    # RE-AIMED when the loop became three turns: the old single gate
    # `if not _state.get("done_seen") or not _stage:` no longer exists, so
    # this anchored 0x and the leg went unproven while reading green.
    # RE-AIMED again when the hard stop landed: the dispatch now gates on
    # `done_seen OR batches`, so the old single-condition anchor went 0x.
    # RE-AIMED when the dispatch was hoisted into `rewatch_decision`. The
    # in-line condition it targeted no longer exists — the rule is a module
    # function now, which is the point: it can be driven by a check instead of
    # only by a $2 live run.
    ("the review window comes from a plan again", "window",
     lambda s: s.replace("_end, _est, _ewhy = _cgf.timeline_end(_sp)",
                         "_end, _est, _ewhy = (0, 'MEASURED', '')")),
    # THE SECOND ARM OF THE SAME LEG, ISOLATED. A case that trips both arms of
    # a two-arm rule proves neither, and the mutation above leaves HOP 2's
    # ABSENT branch untouched — so without this one, the arm that catches a
    # check comparing against an empty set was never exercised.
    # RE-INDENTED 2026-09-16: prestage and HOP 2 were hoisted out of
    # `if plan:` (which made them dead on the single-agent path), so this block
    # dedented by four and the anchor went 0x. A refactor orphaning a mutation
    # is the recorded way a red proof stops proving anything while still
    # counting the leg.
    ("HOP 2 goes back to passing on an empty manifest", "hop2",
     lambda s: s.replace("    if not _manifest:", "    if False:")),
    # RETIRED 2026-09-17 by ruling: the executor/decider rubric and the
    # reference-standard block no longer ride in the first message (the watch
    # holds the readings; the paragraph names them as the bar). Two mutations
    # aimed at removed material would report `anchor 0x` forever.
    ("hop 6 needs a plan again", "hops",
     lambda s: s.replace("    if not ((plan or items) and os.path.exists(source)):",
                         "    if not (plan and os.path.exists(source)):")),
    ("the caption band stops being read", "caption",
     lambda s: s.replace("    _cap_band, _cap_why = (caption_band(tok, _stage) if _stage",
                         "    _cap_band, _cap_why = ((None, 'off') if _stage")),
    ("the review stops reading the caption band", "capreview",
     lambda s: s.replace("            _cb, _cbw = caption_band(tok, _stage)",
                         "            _cb, _cbw = (None, 'off')")),
    ("the delete is trusted to its response again", "delete",
     lambda s: s.replace('"%s IS STILL ON THE TIMELINE after the delete — the "',
                         '"%s ok — the "')),
    # RE-AIMED at the paragraph that replaced TWO_TURN_LOOP.
    ("the deciding branch loses its two-pass loop", "loop",
     # RE-AIMED 2026-09-18 at the three-turn paragraph
     lambda s: s.replace(
         '"Place everything in ONE edit_item call, using the adds/updates/"',
         '"Place things however you like, using the adds/updates/"')),
    # RE-AIMED: the ToolSearch paragraph it injected into no longer exists.
    ("a dead render instruction comes back", "deadinstr",
     lambda s: s.replace(
         '"You are editing this video. The project is open — %s. The %d "',
         '"BEFORE RENDER, call preview_timeline.\\n"\n            '
         '"You are editing this video. The project is open — %s. The %d "')),
    ("the gate report loses its consumer", "report",
     lambda s: s.replace("    for _l in _g.report_lines(rep):", "    for _l in []:")),
)
_P = J.build_system_prompt()
for label, kind, mut in MUT:
    m = mut(SRC)
    if m == SRC:
        print("  *** MUTATION DID NOT APPLY: %s (anchor 0x)" % label)
        red += 1
        continue
    try:
        ast.parse(m)
    except SyntaxError as e:
        print("  *** MUTANT DOES NOT PARSE: %s (%s)" % (label, e))
        red += 1
        continue
    hits = legs(src=m, prompt=_P)
    hit = any(k == kind for k, _ in hits)
    print("    %-44s -> names %s: %s" % (label, kind, hit))
    if not hit:
        red += 1

if not MUT:
    print("  *** NO MUTATIONS — this proof asserts nothing")
    red += 1
for m in fail:
    print("  *** " + m)
print("\nsmoke_one_agent_decides_and_places: %d wrong, %d not red (of %d)"
      % (len(fail), red, len(MUT)))
sys.exit(1 if (fail or red or not MUT) else 0)
