#!/usr/bin/env python3
"""The plan says what RIGHT means, per placement, and when the agent is done.

WHAT THIS IS FOR, measured rather than supposed. On the execution half,
**102.7 of 112.0 thinking seconds** sat on the two model messages that follow
the review frames arriving — messages emitting almost no tool payload. The
placement messages thought 3.0s and 6.3s. So the agent was not re-deriving the
plan and was not working out the tools: it was deciding, from scratch and on
every graphic, what "wrong" would even look like.

All three criteria were already computed in `plan_for_chatcut.py` and none were
written down:

    the band it must stay inside   the ladder picked it (`place_gracefully`)
    what it must not collide with  the face detector ran at plan time, the
                                   caption band is MEASURED from the component,
                                   and the other placements' windows are known
    the frame it must be legible at `_settle` names it three lines above

And nothing said when to STOP. "Have I looked enough" was part of what the
agent was deciding on every review turn.

THE LEGS ARE THE PROPERTY, not the wording:
  1. every placement that reaches the plan gets an acceptance block
  2. that block names all three criteria and the frame
  3. the criteria are COMPUTED, not boilerplate — two different plans get
     different bands and different collision lists
  4. there is a stop condition, and it terminates (export), rather than
     inviting another look
  5. the stop condition does not re-impose a bound on LOOKING — that was
     reversed 2026-09-14 and the cheap fix for a slow review is to put it back

RED-proven at the bottom.
"""
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plan_for_chatcut as T                                     # noqa: E402

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  [{detail}]" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


def _beat(i, t0, t1, where, text, extra=None):
    d = dict(beat=i, treatment=["text"], text_content=text, src_t0=t0,
             src_t1=t1, purpose="hook" if i == 0 else "evidence", why="w",
             size="large", case="upper", where=where,
             colour="white_on_footage", hold_s=1.5)
    d.update(extra or {})
    return d


def plan_for(rows, spec_families=("caption", "cut")):
    """Render a plan from a synthetic ledger. Returns the text."""
    doc = {"ledger": {"spec": {"mode": "full_edit",
                               "families": list(spec_families)},
                      "source_duration_s": 20.0,
                      "keep_spans": [[0.0, 20.0]],
                      "caption_render": {"style": "TwoTone", "pages": 8}},
           "plan": rows}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(doc, fh)
        p = fh.name
    try:
        return T.render(p, staged=True)
    finally:
        os.unlink(p)


# ── THE POPULATION, WITH A FLOOR ────────────────────────────────────────────
ROWS = [_beat(0, 0.0, 2.0, "upper_third", "THE GRIND IS REAL"),
        _beat(1, 4.0, 6.5, "lower_third", "10X A DAY"),
        _beat(2, 8.0, 11.0, "upper_third", "THE SOLUTION")]
try:
    TXT = plan_for(ROWS)
except Exception as e:                                            # noqa: BLE001
    print("  *** the fixture does not render: %s: %s" % (type(e).__name__, e))
    print("smoke_the_review_is_a_check: 1 wrong")
    sys.exit(1)

_n_graphics = len(re.findall(r"^  GRAPHIC \d+", TXT, re.M))
check("the fixture actually places graphics", _n_graphics >= 2,
      "%d placed — a plan with no placements asserts nothing about acceptance"
      % _n_graphics)


def legs(txt, n_expected):
    out = []
    if "ACCEPTANCE" not in txt:
        out.append(("block", "no ACCEPTANCE section"))
    _blocks = re.findall(r"^    (GRAPHIC|CARD) (\d+)", txt, re.M)
    # one acceptance entry per placement
    _acc = len(re.findall(r"^      judged at frame :", txt, re.M))
    if _acc < n_expected:
        out.append(("block", "%d acceptance entr(ies) for %d placement(s)"
                    % (_acc, n_expected)))
    # A MEASUREMENT IS NEVER CLAIMED WHEN NOBODY LOOKED. The ladder fails open
    # with no face regions — correctly, as production does — and this block
    # turned that fail-open into "MEASURED clear over frames 0-60". An
    # acceptance criterion asserting a measurement that never happened is
    # worse than an open question, because the agent stops looking.
    if "MEASURED clear" in txt:
        import re as _re3
        _has_regions = _re3.search(r"face_state.{0,20}MEASURED", txt)
        if not _has_regions:
            out.append(("absence", "the plan claims 'MEASURED clear' for a "
                                   "face check on a ruling that carries no "
                                   "face regions — the ladder failed open and "
                                   "the wording made it a measurement"))
    for _crit, _why in (
            (r"^      stays inside    :", "the band it must stay inside"),
            (r"^      clear of a face :", "what it must not collide with"),
            (r"^      must not touch  :", "the other placements"),
            (r"^      legible         :", "legibility"),
            (r"^      judged at frame :", "the frame it is judged at")):
        if len(re.findall(_crit, txt, re.M)) < n_expected:
            out.append(("criteria", "%s is missing from some acceptance block"
                        % _why))
    # the stop condition, and it must TERMINATE
    if "WHEN YOU ARE DONE" not in txt:
        out.append(("stop", "there is no stop condition"))
    elif not re.search(r"submit_export and stop", txt):
        out.append(("stop", "the stop condition does not end in an export"))
    # and it must not bound the looking
    for _bound in ("do not call preview_timeline twice", "do not pick your own",
                   "only once", "one preview"):
        if _bound.lower() in txt.lower():
            out.append(("unbounded",
                        "the plan bounds the looking again (%r) — reversed "
                        "2026-09-14" % _bound))
    return out


for kind, msg in legs(TXT, _n_graphics):
    check("[%s] %s" % (kind, msg), False)
if not legs(TXT, _n_graphics):
    check("every placement carries band, collisions, frame and legibility, "
          "and the plan says when to stop", True)

# ── 3. THE CRITERIA ARE COMPUTED, NOT BOILERPLATE ───────────────────────────
# A block that says the same thing for every placement in every plan is prose
# wearing a check's clothes. Two plans whose placements sit in DIFFERENT bands
# must produce different `stays inside` lines.
_bands = set(re.findall(r"stays inside    : the (\w+) band", TXT))
check("the band is read from the placement, not fixed", len(_bands) >= 2,
      "every acceptance block names the same band %s — with an upper_third and "
      "a lower_third in the fixture, that is boilerplate" % sorted(_bands))

# and the collision list distinguishes an overlapping pair from a lone one
_touch = re.findall(r"must not touch  : (.+)$", TXT, re.M)
check("the collision list is computed per placement",
      any(t.strip() == "nothing" for t in _touch)
      or len(set(_touch)) > 1,
      "every placement was given the identical collision list %s" % _touch[:3])

# overlapping placements MUST see each other
OVER = [_beat(0, 0.0, 3.0, "upper_third", "A"),
        _beat(1, 1.0, 4.0, "lower_third", "B")]
try:
    TXT2 = plan_for(OVER)
    _t2 = re.findall(r"must not touch  : (.+)$", TXT2, re.M)
    check("two overlapping placements are told about each other",
          _t2 and all("GRAPHIC" in t for t in _t2), str(_t2))
except Exception as e:                                            # noqa: BLE001
    check("the overlapping fixture renders", False,
          "%s: %s" % (type(e).__name__, e))

# ── RED PROOF ───────────────────────────────────────────────────────────────
red = 0
SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "plan_for_chatcut.py"), encoding="utf-8").read()
MUT = (
    ("the fail-open is reported as a measurement", "absence",
     lambda s: s.replace('if not _face_known.startswith("MEASURED"):',
                         'if False:')),
    ("the acceptance section is not emitted", "block",
     lambda s: s.replace('    if _accept:\n', '    if False:\n')),
    ("the stop condition is removed", "stop",
     lambda s: s.replace('"  WHEN YOU ARE DONE. Look at the settled frames. '
                         'For each "', '"  (removed) "')),
    ("the looking is bounded again", "unbounded",
     lambda s: s.replace('"  any moment, as often as you need. Nobody is '
                         'counting.", ""]',
                         '"  Do not pick your own.", ""]')),
)
for label, kind, mut in MUT:
    m = mut(SRC)
    if m == SRC:
        print("  *** MUTATION DID NOT APPLY: %s (anchor 0x)" % label)
        red += 1
        continue
    ns = {"__name__": "mutant"}
    try:
        exec(compile(m, "<mutant>", "exec"), ns)
    except Exception as e:                                        # noqa: BLE001
        print("  *** MUTANT DOES NOT IMPORT: %s (%s)" % (label, e))
        red += 1
        continue
    _save = T.render
    try:
        T.render = ns["render"]
        t = plan_for(ROWS)
        hit = any(k == kind for k, _ in legs(t, _n_graphics))
    except Exception as e:                                        # noqa: BLE001
        print("    %-40s -> mutant raised %s" % (label, type(e).__name__))
        red += 1
        continue
    finally:
        T.render = _save
    print("    %-40s -> names %s: %s" % (label, kind, hit))
    if not hit:
        red += 1

print("\nsmoke_the_review_is_a_check: %d wrong, %d mutation(s) not red (of %d)"
      % (len(fails), red, len(MUT)))
sys.exit(1 if (fails or red) else 0)
