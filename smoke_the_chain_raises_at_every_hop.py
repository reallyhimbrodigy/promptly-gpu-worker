#!/usr/bin/env python3
"""SMOKE — ruling -> plan -> prestage -> placement -> the delivered item.

EVERY GATE BUILT FOR THIS CLASS HAS SAT DOWNSTREAM OF THE LOSS:
  * the PLACEMENTS gate compares the plan's add count against the agent's own
    tool calls — it confirmed 8 of 8 while the translator had already dropped
    half the rulings.
  * `items_added` counts adds SENT, and ChatCut resolves an id PREFIX and
    returns ok, so a send is not a landing.
  * and the card reached the plan, was counted as emitted, registered into an
    asset with no card properties, placed, and rendered nothing. Green.

So each hop is checked where it happens, and each one RAISES BY NAME.

  HOP 1  ruling  -> plan       plan_for_chatcut raises on a lost family
  HOP 2  plan    -> prestage   every assetId named is registered, before the
                               agent starts
  HOP 3  prestage-> placement  every add became an ITEM on the timeline
  HOP 4  placement-> item      every item carries the asset AND the overrides

Each leg RED-proven here.
"""
import ast
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan_for_chatcut as P                                   # noqa: E402
import verify_chain as V                                       # noqa: E402

APP = open(os.path.join(HERE, "chatcut_job_app.py"), encoding="utf-8").read()


def _beat(t0, t1, tr, **kw):
    d = {"treatment": list(tr), "src_t0": t0, "src_t1": t1,
         "text_content": "WORDS", "size": "medium", "case": "upper",
         "where": "upper_third", "colour": "white_on_footage", "hold_s": 2.0,
         "why": "smoke", "purpose": "hook", "zoom_arc": "payoff",
         "sfx_name": "transition-sfx", "card_condition": "WHEN A NUMBER LANDS",
         "card_hero": "5 MINUTES", "card_label": "to edit"}
    d.update(kw)
    return d


RULING = {"ledger": {"keep_spans": [[0.0, 20.0]], "source_duration_s": 20.0,
                     "spec": {"mode": "full_edit", "families": None}},
          "plan": [_beat(1.0, 3.0, ["text"]),
                   _beat(10.0, 14.0, ["text", "card"])]}


def plan_text(ruling=None):
    fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(ruling or RULING, fh)
    fh.close()
    try:
        return P.render(fh.name, staged=True, allow_drop=True)
    finally:
        os.unlink(fh.name)


def legs():
    bad = []
    t = plan_text()
    man = V.plan_manifest(t)

    # HOP 1 — the card reaches the plan AS ITS OWN ADD, not as prose.
    cards = [r for r in man if (r.get("overrides") or {}).get("value") is not None]
    if len(cards) != 1:
        bad.append(("hop1", "the card ruling produced %d add(s), not 1 — the "
                            "house title has no card properties, so a card "
                            "folded into it renders nothing" % len(cards)))
    elif cards[0]["overrides"].get("value") != 5:
        bad.append(("hop1", "the card's value is %r, not the ruled 5"
                            % cards[0]["overrides"].get("value")))

    # HOP 2 — wired into the job, ahead of the agent.
    if "HOP 2 (plan -> prestage)" not in APP:
        bad.append(("hop2", "the job does not raise when an assetId the plan "
                            "names was never registered"))
    _tree = ast.parse(APP)
    _fn = next((n for n in ast.walk(_tree) if isinstance(n, ast.FunctionDef)
                and n.name == "edit"), None)
    if _fn is not None:
        _h2 = [n.lineno for n in ast.walk(_fn) if isinstance(n, ast.Constant)
               and isinstance(n.value, str) and "HOP 2 (plan" in n.value]
        _ag = [n.lineno for n in ast.walk(_fn) if isinstance(n, ast.Call)
               and getattr(n.func, "id", "") == "run_three_turns"]   # the launch is the loop
        if not (_h2 and _ag and min(_h2) < min(_ag)):
            bad.append(("hop2", "hop 2 does not run BEFORE the agent — a gate "
                                "that fires after the turn is spent is a "
                                "report"))

    # HOP 3 — a send is not a landing.
    miss = V.hop3_placed(man, [])
    if not miss:
        bad.append(("hop3", "an empty timeline reports every add as placed"))

    # HOP 4 — the overrides must arrive on the item.
    empty = {r["from"]: {"propertyOverrides": {}} for r in man}
    if not V.hop4_carries(man, empty):
        bad.append(("hop4", "an item carrying NO overrides passes"))
    full = dict(empty)
    for r in man:
        if r.get("overrides"):
            full[r["from"]] = {"propertyOverrides": dict(r["overrides"])}
    if V.hop4_carries(man, full):
        bad.append(("hop4", "an item carrying exactly the ruling is rejected"))
    return bad


if __name__ == "__main__":
    bad = legs()
    for k, w in bad:
        print("  [FAIL] %-5s %s" % (k, w))
    if not bad:
        print("  [ok] HOP 1  the card reaches the plan as its own add, value=5")
        print("  [ok] HOP 2  the job raises on an unregistered assetId, before "
              "the agent")
        print("  [ok] HOP 3  an empty timeline fails rather than passing")
        print("  [ok] HOP 4  a missing override fails, a correct one passes")

    print("\n  RED PROOF")
    red = True
    # a card ruling whose hero carries no number must RAISE, not silently drop
    try:
        plan_text({"ledger": RULING["ledger"],
                   "plan": [_beat(1.0, 3.0, ["text", "card"],
                                  card_hero="everything")]})
        print("    a card with no number     -> NOT RAISED")
        red = False
    except P.Incomplete as e:
        print("    a card with no number     -> raised, names it: %s"
              % ("card_hero" in str(e)))
        red &= "card_hero" in str(e)

    man = V.plan_manifest(plan_text())
    r2 = V.hop2_prestage(man, {})
    print("    nothing registered        -> %d add(s) refused" % len(r2))
    red &= bool(r2)

    r3 = V.hop2_prestage(man, {"GRAPHIC 1": "x", "GRAPHIC 2": "y",
                               "StatCard": "z", "caption:TwoTone": "w"})
    print("    everything registered     -> %d refused" % len(r3))
    red &= not r3

    print("\n  %s" % ("OK" if (not bad and red) else "FAIL"))
    sys.exit(0 if (not bad and red) else 1)
