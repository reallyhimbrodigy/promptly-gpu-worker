#!/usr/bin/env python3
"""Two mechanisms, one rule, nothing dropped.

THE PROBLEM. ChatCut has no array or object property type. Eight components
were registered with their CONTENT typed `text`, defaulting to "" — they
rendered blank and every validator passed them. Eleven more were refused
outright for the same reason. Nineteen of twenty-nine components could not be
given the thing they exist to show.

THE ROUTE, ruled by Zac 2026-09-14 and proven on RankedList before it was
generalised: `create_motion_graphic_from_code` takes ARBITRARY JSX, and the
planner knows the items when it writes the plan. So structured content does not
have to be a runtime property at all — it is BAKED INTO THE CODE at
registration, and a single-value prop keeps `propertyOverrides`.

    structured (list / dict / function)  ->  literal in the component code
    scalar (number, text, colour, bool)  ->  propertyOverrides at placement

BOTH HALVES OF THE BAKE MOVE TOGETHER. The read `items: props.items` becomes a
literal AND the `items` declaration is dropped, because ChatCut refuses a
declared property the code does not read exactly as firmly as it refuses a read
that is not declared. Changing one without the other trades one refusal for the
other — which is how the first hoist fix traded one use-before-declare for
another.

PROVEN BEFORE GENERALISED. RankedList, baked with three real rows, went
0.000% -> 2.838% of frame and the FRAME was read: "1 Hook them fast 98%",
"2 Cut the filler 71%", accent on #1. A pixel diff alone would not have told
rendering from rendering-a-smear.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import derive_prop_types                                       # noqa: E402
import build_chatcut_registry as B                             # noqa: E402

PORTED = os.path.join(HERE, "ported_mg")
FIXTURES = os.path.join(HERE, "catalogue_props.json")
OUT = os.path.join(HERE, "chatcut_registry_baked.json")


def bake_absent(code, props, keys):
    """Bake `undefined` for a prop ChatCut cannot type and no fixture supplies.

    ProgressBar reads `formatValue` (a FUNCTION — no property type can hold
    one) and `percentage` (the union variant this registry does not offer).
    Neither is content; both are props whose correct value is ABSENT, so the
    component falls back to its own formatter and its own value/total branch.
    Baking `undefined` is the same rule as everywhere else in this lane — ask
    what the component does when the prop is not there — spelled for a prop
    that cannot be declared at all.
    """
    done = []
    for key in sorted(keys):
        needle = "    %s: props.%s,\n" % (key, key)
        if needle not in code:
            continue
        code = code.replace(needle, "    %s: undefined,\n" % key)
        props = [p for p in props if p["key"] != key]
        done.append(key)
    return code, props, done


def bake(code, props, data):
    """Replace `KEY: props.KEY,` in __mapped with a literal; drop the decl.

    Returns (code, props, baked_keys, unbakeable). `unbakeable` names a key the
    fixture supplies that the component's mapping never reads — a value with
    nowhere to go, which is worth saying rather than dropping.
    """
    baked, unbakeable = [], []
    for key, value in sorted(data.items()):
        if not isinstance(value, (list, dict)):
            continue
        needle = "    %s: props.%s,\n" % (key, key)
        if needle not in code:
            unbakeable.append(key)
            continue
        code = code.replace(needle, "    %s: %s,\n" % (key, json.dumps(value)))
        props = [p for p in props if p["key"] != key]
        baked.append(key)
    return code, props, baked, unbakeable


def build(verbose=True):
    fx = json.load(open(FIXTURES, encoding="utf-8"))
    names = sorted(f[:-4] for f in os.listdir(PORTED) if f.endswith(".jsx"))
    comps, refused, report = {}, {}, []
    for n in names:
        props, skipped, arrays_lost, _cu = derive_prop_types.derive(n)
        if props is None:
            refused[n] = {"reason": "not a single component", "detail": skipped}
            continue
        src = os.path.join(PORTED, n + ".jsx")
        out = os.path.join(HERE, "_baked.jsx")
        r = subprocess.run(["node", os.path.join(HERE, "chatcut_wrap.mjs"),
                            src, out], capture_output=True, text=True, cwd=HERE)
        if r.returncode != 0:
            refused[n] = {"reason": "wrap refused", "detail": r.stdout[:300]}
            continue
        code = open(out, encoding="utf-8").read()
        os.remove(out)

        # THE STRUCTURED PROPS THE INTERFACE DECLARES, whether or not
        # derive_prop_types could type them — `skipped` holds the ones it could
        # not, and those are exactly the ones that must be baked.
        data = dict(fx.get(n) or {})
        code, props, baked, unbakeable = bake(code, props, data)
        code, props, absent = bake_absent(
            code, props, [k for k, _ in (skipped or []) if k not in data])
        baked = baked + ["%s=undefined" % k for k in absent]

        # Anything still declared-but-unread, or read-but-undeclared, is a
        # refusal waiting to happen. Reconcile against the CODE, as ever.
        # A READ THE REGISTRY DOES NOT OFFER IS AN ABSENT PROP, NOT A REFUSAL.
        # ProgressBar is a discriminated union and this registry offers the
        # VALUE variant, so the flattened blob still reads `props.percentage`
        # — the other variant's field, which by construction is not there.
        # Refusing the whole component for it threw away a component over a
        # field whose correct value is `undefined`. Bake that, and record it.
        read = set(re.findall(r"\bprops\??\.([A-Za-z_$][\w$]*)", code))
        undeclared = sorted(read - set(p["key"] for p in props))
        if undeclared:
            code, props, more = bake_absent(code, props, undeclared)
            baked += ["%s=undefined" % k for k in more]
            read = set(re.findall(r"\bprops\??\.([A-Za-z_$][\w$]*)", code))
            still = sorted(read - set(p["key"] for p in props))
            if still:
                # READ IN THE BODY, NOT IN __mapped — so it cannot be baked
                # there, and ChatCut matches `props.X` STATICALLY so it must
                # be declared. ProgressBar's inner component takes `(props)`
                # directly and reads `props.percentage ?? 0`; the validator
                # cannot tell that from an item prop. Declare it at the value
                # its OWN fallback gives — the absent-prop rule once more,
                # spelled for a read the mapping never sees.
                _consts = B._consts(code)
                _phase = B._use_mg_phase_options(code)
                _peers = {q["key"]: q["defaultValue"] for q in props}
                _hard = []
                for k in still:
                    m2 = re.search(r"props\??\.%s\s*\?\?\s*" % re.escape(k),
                                   code)
                    if not m2:
                        _hard.append(k)
                        continue
                    v, _why = B.resolve(B._expr_after(code, m2.end()), code,
                                        _consts, _phase, _peers)
                    if v is None:
                        _hard.append(k)
                        continue
                    _t = ("number" if isinstance(v, (int, float))
                          and not isinstance(v, bool)
                          else "boolean" if isinstance(v, bool) else "text")
                    props.append({"key": k, "label": k, "type": _t,
                                  "defaultValue": v})
                    baked.append("%s=declared(%r)" % (k, v))
                if _hard:
                    refused[n] = {"reason": "a prop is read outside __mapped "
                                            "with no resolvable fallback",
                                  "detail": ", ".join(_hard)}
                    continue
        props = [p for p in props if p["key"] in read]

        fr = subprocess.run(["node", os.path.join(HERE, "free_identifiers.mjs"),
                             "/dev/stdin"], input=code, capture_output=True,
                            text=True, cwd=HERE)
        free = json.loads((fr.stdout or "[]").strip() or "[]")
        if free:
            refused[n] = {
                "reason": "the blob reads an identifier ChatCut does not have",
                "detail": ", ".join(x["name"] for x in free)}
            continue

        props, changes, divergences = B.reconcile(n, code, props)
        overrides = {k: v for k, v in data.items()
                     if not isinstance(v, (list, dict))
                     and k in set(p["key"] for p in props)}
        comps[n] = {"code": code, "properties": props, "baked": baked,
                    "overrides": overrides,
                    "divergences": [{"key": k, "kind": kk, "detail": d}
                                    for k, kk, d in divergences],
                    "unbakeable": unbakeable}
        report.append((n, baked, unbakeable, len(overrides)))

    if verbose:
        print("  %-18s %-30s %s" % ("component", "baked into the code",
                                    "overrides"))
        for n, baked, unb, nov in report:
            print("  %-18s %-30s %d%s" % (n, ",".join(baked) or "-", nov,
                                          ("   UNBAKEABLE: " + ",".join(unb))
                                          if unb else ""))
        print("  registered %d, refused %d" % (len(comps), len(refused)))
        for n, v in sorted(refused.items()):
            print("    REFUSED %-18s %s — %s" % (n, v["reason"][:40],
                                                 str(v["detail"])[:60]))
    return {"components": comps, "refused": refused}


def component_keys(reg):
    """Every component name in a registry object, however it is nested.

    Keyed by NAME and not by position: the artifact nests components under
    several parents and a positional read would call a reordering a loss.
    """
    out = set()

    def walk(o, key=None):
        if isinstance(o, dict):
            if isinstance(o.get("code"), str) and "const Component" in o["code"]:
                # THE DICT KEY THAT LED HERE IS THE NAME. The blobs carry
                # baked/code/divergences/overrides/properties and NO name field,
                # so my first version fell back to a counter and named the lost
                # nine "<unnamed:32>".."<unnamed:36>" — a refusal that says
                # "fewer" without saying which, which is a second puzzle rather
                # than an answer, and unstable besides: a counter is positional,
                # so a reordering would rename everything.
                out.add(str(key) if key is not None else "<no key>")
                return
            for k, v in o.items():
                walk(v, k)
        elif isinstance(o, list):
            for v in o:
                walk(v, key)
    walk(reg)
    return out


def shrink_guard(new_reg, path):
    """-> (ok, message). REFUSES a write that LOSES a component.

    WHY THIS EXISTS, measured 2026-09-22: `bake_registry.py --write` took the
    artifact from 37 blobs to 28. It emits the 28 components it builds and
    overwrites the file wholesale, and THE NINE CAPTION STYLES IN THE COMMITTED
    ARTIFACT ARE NOT IN ITS OUTPUT. Running the documented build step destroys
    nine registered caption styles, silently, inside whatever commit happened to
    run it.

    A SHRINK GUARD AND NOT AN EQUALITY GUARD, deliberately. A deliberate
    ADDITION must still write, or the guard blocks every legitimate bake and
    gets removed within a week. Only a LOSS refuses, and the lost keys are
    NAMED — a refusal that says "fewer" without saying which is a second puzzle
    rather than an answer.
    """
    import os as _os
    if not _os.path.exists(path):
        return True, "no artifact on disk — first write, nothing to lose"
    try:
        old_reg = json.load(open(path, encoding="utf-8"))
    except Exception as e:                                     # noqa: BLE001
        # UNREADABLE IS NOT EMPTY. Treating a corrupt artifact as zero
        # components would let the guard wave through the very write that
        # destroys it.
        return False, ("the artifact on disk is UNREADABLE (%s). Refusing: an "
                       "unreadable file is not an empty one, and overwriting it "
                       "is exactly what cannot be undone." % e)
    lost = sorted(component_keys(old_reg) - component_keys(new_reg))
    if lost:
        return False, ("REFUSING TO WRITE — this bake LOSES %d component(s) that "
                       "are in the artifact on disk:\n    %s\n  A bake that "
                       "removes components is how nine caption styles disappear "
                       "inside a commit about something else. If the removal is "
                       "deliberate, remove them from the artifact in their own "
                       "commit and re-run."
                       % (len(lost), "\n    ".join(lost)))
    return True, "no component lost"


if __name__ == "__main__":
    reg = build()
    if "--write" in sys.argv:
        ok, why = shrink_guard(reg, OUT)
        if not ok:
            print("\n  " + why)
            sys.exit(1)
        json.dump(reg, open(OUT, "w", encoding="utf-8"), indent=1)
        print("wrote", OUT, "-", why)
