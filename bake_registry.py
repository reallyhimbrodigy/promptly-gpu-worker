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
import flatten_spec                                            # noqa: E402

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


def flatten(code, props, name, data):
    """Turn a baked ARRAY into numbered scalar properties. -> (code, props, note).

    THE ARRAY BECOMES N SLOTS AND THE COMPONENT REBUILDS IT. ChatCut still has
    no array type — that is why the content was baked at all — but it has
    scalar text properties, so `notes` becomes note1..note3 and the blob
    assembles the array at render time from `props.note1`, `props.note2`,
    `props.note3`.

    AN EMPTY SLOT IS DROPPED, NOT DRAWN. `.filter()` removes it before the
    component ever sees it, so the layout closes up: no gap, no placeholder,
    no empty row. That is the whole difference between a five-row component
    you can use for three rows and one that shows two blanks.

    AND THE AUTO FIELDS ARE COMPUTED AFTER THE FILTER. RankedList's rank is
    the DRAWN position, so filling rows 1, 3 and 4 draws 1, 2, 3 — if the
    numbering did not close up with the layout, leaving a row blank would
    produce a list that skips a number, which is worse than the gap.
    """
    import flatten_spec
    spec = flatten_spec.FLATTEN.get(name)
    if spec is None:
        return code, props, None
    # A COMPONENT CAN HAVE MORE THAN ONE STRUCTURED KEY. Two of the twelve do
    # — ChatThread carries `header` beside `messages`, DropCard carries `steps`
    # beside `points` — and the first version of this spec allowed one key per
    # component, so it flattened one and left the other BAKED while reporting
    # the component flattened. The survey is what caught it, not the spec.
    if isinstance(spec, list):
        notes = []
        for one in spec:
            code, props, note = _flatten_one(code, props, one)
            notes.append("%s:%s" % (one["key"], note))
        return code, props, " + ".join(notes)
    return _flatten_one(code, props, spec)


def _flatten_one(code, props, spec):
    key = spec["key"]
    needle = "    %s: props.%s,\n" % (key, key)
    if needle not in code:
        # WRONG POPULATION, SAID OUT LOUD. A spec entry whose component does
        # not read that key through __mapped cannot be flattened, and a silent
        # skip here would leave the array baked while the report said flattened.
        return code, props, "NOT READ IN __mapped — nothing flattened"

    fields = spec["fields"]
    fixed = spec.get("fixed") or {}
    auto = spec.get("auto") or {}
    bare = fields[0][0] is None

    if spec.get("object"):
        # An object, not a list: one slot, fixed property names, and NO filter
        # — dropping an empty header would remove the object the component
        # destructures, which is a different thing from drawing no header.
        parts = ["%s: props.%s" % (f, suf) for f, suf, _lab, _t in fields]
        code = code.replace(needle, "    %s: { %s },\n" % (key, ", ".join(parts)))
        props = [p for p in props if p["key"] != key]
        dflt = spec.get("defaults") or {}
        for f, suf, lab, typ in fields:
            # A COLOUR OR A COORDINATE IS NOT COPY, AND ITS EMPTY STATE IS NOT
            # BLANK — it is BROKEN. An empty colour renders as nothing and an
            # absent coordinate is the top-left corner, so these fields keep
            # the value the component was built around. Text slots keep "",
            # which is what smoke_default_text refuses a default ON.
            props.append({"key": suf, "label": lab, "type": typ,
                          "defaultValue": dflt.get(suf, 0 if typ == "number" else "")})
        return code, props, "1 object x %d field(s)" % len(fields)

    slots = []
    for i in range(1, spec["n"] + 1):
        if bare:
            slots.append("props.%s" % (fields[0][1] % i))
            continue
        parts = ["%s: props.%s" % (f, suf % i) for f, suf, _lab, _t in fields]
        for fk, vals in sorted(fixed.items()):
            parts.append("%s: %s" % (fk, json.dumps(vals[(i - 1) % len(vals)])))
        slots.append("{ %s }" % ", ".join(parts))

    first = fields[0][1] if bare else fields[0][0]
    empty = ("String(__x ?? \"\").trim() !== \"\"" if bare
             else "String(__x.%s ?? \"\").trim() !== \"\"" % first)
    expr = "[%s].filter((__x) => %s)" % (", ".join(slots), empty)
    if auto:
        adds = ", ".join("%s: %s" % (k, v) for k, v in sorted(auto.items()))
        expr += ".map((__x, __i) => Object.assign({}, __x, { %s }))" % adds
    code = code.replace(needle, "    %s: %s,\n" % (key, expr))

    props = [p for p in props if p["key"] != key]
    dflt = spec.get("defaults") or {}
    for i in range(1, spec["n"] + 1):
        for _f, suf, lab, typ in fields:
            props.append({"key": suf % i, "label": lab % i, "type": typ,
                          "defaultValue": dflt.get(suf % i,
                                                   0 if typ == "number" else "")})
    return code, props, "%d slot(s) x %d field(s)" % (spec["n"], len(fields))



# THE KEYS FLATTEN CREATES, per component — the population the DEFAULT_TEXT
# refusal is aimed at, and nothing else.
def flattened_keys(name):
    spec = flatten_spec.FLATTEN.get(name)
    if not spec:
        return set()
    out = set()
    for one in (spec if isinstance(spec, list) else [spec]):
        for _f, suf, _lab, _t in one["fields"]:
            if one.get("object"):
                out.add(suf)
            else:
                for i in range(1, one["n"] + 1):
                    out.add(suf % i)
    return out


# DEFAULT_TEXT — a content slot may not carry a default.
#
# This is the one way the flattening silently un-does itself. A baked literal
# is at least GREPPABLE: `{"replies": 128}` sits in the blob and a survey finds
# it. A DEFAULT does not. It is a well-formed property, it appears in
# `properties` like every other, the component reads it correctly — and because
# the registered default IS the value on every placement that does not override
# it (measured: 135 defaults wrong, 0 of 14 components drew), "1.2K" in
# statLikes puts our number on every TweetBubble exactly as firmly as the baked
# object did, with nothing left in the code to find it by.
#
# SCOPED TO THE KEYS FLATTEN CREATED, DELIBERATELY. Fourteen components carry
# a non-empty text default today — textShadow's rgba(), StickyNotes' "5%",
# StepDivider's "STEP" — and a blanket rule would arrive as a wave of red on
# working components and be reverted the same day for being right about
# nothing. Geometry is not copy, and a slot the user fills is not chrome.
def default_text_offenders(name, props):
    keys = flattened_keys(name)
    return sorted(
        "%s=%r" % (p["key"], p["defaultValue"])
        for p in props
        if p["key"] in keys
        # TYPE text, NOT "the value happens to be a string". The first draft
        # asked only whether the default was a non-empty str, and a COLOUR
        # default is a non-empty str — so it refused EndCard and PillMarquee
        # for keeping "#14141A" on a palette slot, which is chrome and not a
        # word anyone reads. The rule is about COPY; `text` is the only type
        # that carries copy. A check calibrated on the SHAPE of the value had
        # learned the shape rather than the property, one day after that
        # sentence was written down about a different check.
        and p.get("type") == "text"
        and isinstance(p.get("defaultValue"), str)
        and p["defaultValue"].strip() != ""
    )

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
        # FLATTEN FIRST. bake() would inline the array as a literal and drop
        # the property; flatten() takes the same key and turns it into numbered
        # scalars instead. Whichever runs first owns the key, so the order is
        # the whole ruling: no baked copy anywhere.
        code, props, flat = flatten(code, props, n, data)
        if flat:
            _sp = flatten_spec.FLATTEN[n]
            for _one in (_sp if isinstance(_sp, list) else [_sp]):
                data.pop(_one["key"], None)
        code, props, baked, unbakeable = bake(code, props, data)
        if flat:
            # THE MARKER KEEPS THE KEY, as `key=FLATTENED(...)`. Dropping the
            # key made the marker look like a key name to every reader of
            # `baked` — the copy survey then called payload() on
            # "FLATTENED(12 slot(s)...)", got None, and reported all twelve
            # flattened components as unparsed-so-treat-as-copy. A format
            # change in a list that other readers walk is a change to their
            # input, and `key=` is the shape they already skip.
            baked = ["%s=FLATTENED(%s)" % (
                "+".join(o["key"] for o in (_sp if isinstance(_sp, list) else [_sp])),
                flat)] + baked
        _dt = default_text_offenders(n, props)
        if _dt:
            refused[n] = {"reason": "DEFAULT_TEXT",
                          "detail": "a flattened content slot carries a "
                                    "default, which draws on every placement "
                                    "that does not override it: "
                                    + ", ".join(_dt)}
            continue

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
