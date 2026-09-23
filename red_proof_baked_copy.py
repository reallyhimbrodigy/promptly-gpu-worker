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


def one_string_is_baked(d):
    """ZAC'S NAMED MUTANT: a component bakes ONE string.

    The ceiling is zero, so the smallest possible violation is the right
    mutation — a single word that no placement can override. PullQuote is
    EndCard.palette is baked and today carries only colours, so ONE WORD added
    to it is the smallest possible violation of a ceiling of zero.

    MY FIRST VERSION ADDED A SCALAR AND DID NOT BITE. `bake()` only inlines
    lists and dicts — a scalar becomes a propertyOverride, which is SETTABLE,
    so PullQuote.subtitle was correctly not baked copy. Real bytes, no verdict:
    wrong population for the third time today, and the third different way in.
    The string has to ride inside an ARRAY the component's __mapped reads.
    """
    d["EndCard"] = dict(d.get("EndCard") or {})
    d["EndCard"]["palette"] = list(d["EndCard"].get("palette") or []) + ["BETA"]
    return d, ["EndCard"]


def _still_structurally_baked():
    """-> (component, key) whose payload the bake still INLINES, or (None, None).

    Read from the artifact rather than named in this file, because naming it
    is what broke twice: `baked` entries carrying no `=` are the keys that
    were genuinely inlined, and that set shrinks every time something is
    flattened. Picking from it means the mutation follows the population
    instead of pointing at where the population used to be.
    """
    import json
    reg = json.load(io.open(ART, encoding="utf-8"))["components"]
    for n in sorted(reg):
        for k in (reg[n].get("baked") or []):
            if "=" not in k:
                return n, k
    return None, None


def new_component_gains_copy(d):
    """A STRUCTURAL baked payload acquires a word, so its component joins the set.

    MY FIRST VERSION ADDED A KEY TO Stamp'S FIXTURE AND DID NOT BITE. `bake()`
    only bakes a key the component's own __mapped reads as `key: props.key`;
    Stamp has no such mapping, so the value was `unbakeable` — a value with
    nowhere to go — and the mutant changed real bytes and no verdict. Wrong
    population, the eighth way a mutation stops mutating, and the second time
    it has caught me today.

    MY SECOND VERSION SAID: "TweetBubble.stats IS baked and is currently
    structural (four numbers), so adding a label is both the realistic defect
    and one the bake will carry." THAT SENTENCE IS NOW WRONG, and it is kept
    here rather than replaced because being wrong is the evidence: on
    2026-09-23 `stats` was flattened into statReplies/statReposts/statLikes/
    statViews, the `stats: props.stats,` needle left the code, and this
    mutation went vacuous IN EXACTLY THE WAY THE PARAGRAPH ABOVE IT DESCRIBES.
    A note that is wrong is read as fact by the next person, including the
    person who wrote it — twice, four hours apart, in the same function.

    So the target is no longer named. It is READ from the artifact, so it
    follows the shrinking population of genuinely-inlined keys instead of
    pointing at where that population used to be.
    """
    n, k = _still_structurally_baked()
    if n is None:
        # NOT A PASS. Nothing is structurally baked any more, so this mutation
        # has nothing to aim at — which is a VACUOUS result to be reported,
        # never a green one.
        return d, None
    v = d.get(n, {}).get(k)
    d[n] = dict(d.get(n) or {})
    if isinstance(v, dict):
        d[n][k] = dict(v)
        d[n][k]["label"] = "Sponsored by Promptly"
    elif isinstance(v, list):
        d[n][k] = list(v) + ["Sponsored by Promptly"]
    else:
        return d, None
    return d, [n]


MUT = [
    ("our_brand_returns_to_a_baked_line", brand_returns,
     "L2 no_brand_mark_in_baked_copy"),
    ("a_fabricated_payment_returns", money_returns,
     "L3 no_money_amount_in_baked_copy"),
    ("a_component_quietly_gains_baked_copy", new_component_gains_copy,
     "L0 no_component_carries_baked_copy"),
    ("one_string_is_baked", one_string_is_baked,
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
