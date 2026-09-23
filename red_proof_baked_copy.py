#!/usr/bin/env python3
"""RED proof for smoke_baked_copy.py — mutations aimed at the FIXTURE.

The baked copy comes from catalogue_props.json, so that is where the defect
lives and that is what each mutation corrupts. Loosening a pattern the corpus
already satisfies would change bytes and no verdict.
"""
import io
import json
import os
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


def rebake(names):
    sys.path.insert(0, HERE)
    import importlib
    import bake_registry as B
    importlib.reload(B)
    fresh = B.build(verbose=False)["components"]
    art = json.load(io.open(ART, encoding="utf-8"))
    for n in names:
        if n in fresh:
            art["components"][n] = fresh[n]
    io.open(ART, "w", encoding="utf-8").write(json.dumps(art, indent=1))


def brand_returns(d):
    d["EndCard"]["lines"] = [{"text": "@promptly", "kind": "handle"}]
    return d, ["EndCard"]


def money_returns(d):
    d["Notification"]["notifications"] = [
        {"app": "apple-pay", "title": "Payment Received", "body": "$249.00 from Kellan"}]
    return d, ["Notification"]


def new_component_gains_copy(d):
    """A STRUCTURAL baked payload acquires a word, so its component joins the set.

    MY FIRST VERSION ADDED A KEY TO Stamp'S FIXTURE AND DID NOT BITE. `bake()`
    only bakes a key the component's own __mapped reads as `key: props.key`;
    Stamp has no such mapping, so the value was `unbakeable` — a value with
    nowhere to go — and the mutant changed real bytes and no verdict. Wrong
    population, the eighth way a mutation stops mutating, and the second time
    it has caught me today.

    TweetBubble.stats IS baked and is currently structural (four numbers), so
    adding a label is both the realistic defect and one the bake will carry.
    """
    d["TweetBubble"]["stats"] = dict(d["TweetBubble"]["stats"])
    d["TweetBubble"]["stats"]["label"] = "Sponsored by Promptly"
    return d, ["TweetBubble"]


MUT = [
    ("our_brand_returns_to_a_baked_line", brand_returns,
     "L2 no_brand_mark_in_baked_copy"),
    ("a_fabricated_payment_returns", money_returns,
     "L3 no_money_amount_in_baked_copy"),
    ("a_component_quietly_gains_baked_copy", new_component_gains_copy,
     "L0 baked_copy_population_is_pinned"),
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
    fix_raw = io.open(FIX, encoding="utf-8").read()
    art_raw = io.open(ART, encoding="utf-8").read()
    red = 0
    for name, apply_, phrase in MUT:
        d, touched = apply_(json.loads(fix_raw))
        io.open(FIX, "w", encoding="utf-8").write(json.dumps(d, indent=1, ensure_ascii=False))
        try:
            rebake(touched)
            rc2, out2 = run()
        finally:
            io.open(FIX, "w", encoding="utf-8").write(fix_raw)
            io.open(ART, "w", encoding="utf-8").write(art_raw)
        ok = rc2 != 0 and failed(out2, phrase)
        red += 1 if ok else 0
        print("  %-42s %s   rc=%d leg_failed=%s"
              % (name, "RED " if ok else "NOT RED", rc2, failed(out2, phrase)))
    if (io.open(FIX, encoding="utf-8").read() != fix_raw
            or io.open(ART, encoding="utf-8").read() != art_raw):
        print("\nHARNESS FAILURE: residue left on disk")
        return 2
    print("\n%d/%d RED-proven" % (red, len(MUT)))
    return 0 if (MUT and red == len(MUT)) else 1


if __name__ == "__main__":
    sys.exit(main())
