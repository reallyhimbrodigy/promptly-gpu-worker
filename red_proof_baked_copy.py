#!/usr/bin/env python3
"""RED proof for smoke_baked_copy.py — mutations aimed at the FIXTURE.

The baked copy comes from catalogue_props.json, so that is where the defect
lives and that is what each mutation corrupts. Loosening a pattern the corpus
already satisfies would change bytes and no verdict.
"""
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_baked_copy.py")
FIX = os.path.join(HERE, "catalogue_props.json")
ART = os.path.join(HERE, "chatcut_registry_baked.json")


def _env():
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


# ── THE POPULATION MOVED, AND THE MUTATIONS MOVED WITH IT ────────────────
#
# Until 2026-09-23 these four mutations wrote a word into catalogue_props.json
# and re-baked: EndCard.lines, Notification.notifications, EndCard.palette.
# Every one of those payloads is now FLATTENED, so the fixture value is no
# longer read by anything — `bake()` reports it unbakeable — and ALL FOUR WENT
# VACUOUS IN THE SAME RUN. Byte-different fixtures, identical behaviour, and
# the tally would have said 4/4 if the harness had not crashed on its own
# VACUOUS return.
#
# That is not a harness bug to repair back to where it was. The defect class
# itself has been eliminated: with nothing structurally baked anywhere, a
# component CANNOT gain baked copy through a fixture any more. The only
# remaining way it can appear is a hand-edit of the artifact — someone pastes
# a literal back into a blob, or a bad merge restores one — so that is what
# these now do. The mutation follows the defect; when the defect moves, a
# mutation that stayed put is measuring nothing.

def _mutate_artifact(art, comp, key, literal):
    """Put a baked literal back into one component's blob, as a hand-edit would.

    BOTH HALVES MOVE TOGETHER, because that is how a bake works and how a
    regression would arrive: the __mapped read becomes a literal AND the
    `baked` marker loses its `=FLATTENED(...)` suffix, which is what makes the
    copy survey look at the key at all. Changing only one would produce a
    mutant that is byte-different and invisible to the check — vacuous again,
    one level down.
    """
    e = art["components"][comp]
    m = re.search(r"^(\s{4}%s: )(.+),$" % re.escape(key), e["code"], re.M)
    if not m:
        return False
    e["code"] = e["code"][:m.start()] + m.group(1) + json.dumps(literal) + "," \
        + e["code"][m.end():]
    e["baked"] = [b for b in (e.get("baked") or [])
                  if not b.startswith(key + "=")] + [key]
    return True


MUT = [
    # OUR BRAND ON SOMEONE ELSE'S VIDEO.
    ("our_brand_returns_to_a_baked_line",
     ("EndCard", "lines", [{"text": "@promptly", "icon": None}]),
     "L2 no_brand_mark_in_baked_copy"),
    # A FABRICATED FINANCIAL RECORD naming a person.
    ("a_fabricated_payment_returns",
     ("Notification", "notifications",
      [{"title": "Payment Received", "body": "$249.00 from Kellan",
        "appName": "Apple Pay", "app": "apple-pay"}]),
     "L3 no_money_amount_in_baked_copy"),
    # A COMPONENT QUIETLY GAINS BAKED COPY — the population leg, not a
    # content leg, so the words are ordinary rather than brand or money.
    ("a_component_quietly_gains_baked_copy",
     ("PillCluster", "tags", ["FAST", "CHEAP", "GOOD"]),
     "L0 no_component_carries_baked_copy"),
    # ZAC'S NAMED MUTANT: the ceiling is zero, so the smallest possible
    # violation is ONE WORD that no placement can override.
    ("one_string_is_baked",
     ("StickyNotes", "notes", [{"text": "BETA"}]),
     "L0 no_component_carries_baked_copy"),
]


def run():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True,
                       env=_env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def failed(out, phrase):
    return any(phrase in ln and "FAIL" in ln for ln in out.splitlines())


def main():
    rc, out = run()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-700:])
        return 2
    print("baseline green.\n")
    art_raw = io.open(ART, encoding="utf-8").read()
    red, faults = 0, 0
    for name, (comp, key, literal), phrase in MUT:
        art = json.loads(art_raw)
        if not _mutate_artifact(art, comp, key, literal):
            # VACUOUS, SAID OUT LOUD. The key is not in that component's
            # __mapped any more, so the mutation edits nothing — which is a
            # result to report, never a pass.
            print("  %-42s VACUOUS   %s.%s is not read in __mapped" % (name, comp, key))
            faults += 1
            continue
        io.open(ART, "w", encoding="utf-8").write(json.dumps(art, indent=1))
        try:
            rc2, out2 = run()
        finally:
            io.open(ART, "w", encoding="utf-8").write(art_raw)
        ok = rc2 != 0 and failed(out2, phrase)
        red += 1 if ok else 0
        print("  %-42s %s   rc=%d leg_failed=%s"
              % (name, "RED " if ok else "NOT RED", rc2, failed(out2, phrase)))
    if io.open(ART, encoding="utf-8").read() != art_raw:
        print("\nHARNESS FAILURE: residue left on disk")
        return 2
    print("\n%d/%d RED-proven" % (red, len(MUT)))
    return 0 if (MUT and red == len(MUT) and not faults) else 1


if __name__ == "__main__":
    sys.exit(main())
