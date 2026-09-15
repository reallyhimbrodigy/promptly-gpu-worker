#!/usr/bin/env python3
"""Build chatcut_registry.json from ported_mg/ — reproducibly, with the
property DEFAULTS derived from the components rather than invented.

THE DEFECT THIS EXISTS TO KILL. Fourteen of fourteen ported components
registered clean, placed clean, and drew ZERO pixels. Not one of them was
broken. The registry declared

    { "key": "enterFrames", "type": "number", "defaultValue": 0 }

because a number-typed property needs a default and zero looked like the
harmless one. It is not harmless, for a reason ChatCut states out loud in its
own validator:

    props.X has a hardcoded fallback via "??". Remove it — the property
    system guarantees values are always present via defaultValue.

There is NO UNSET in ChatCut's property system. The registered default IS the
value the component sees. So `timing.enterFrames ?? defaultEnterFrames` never
reaches its fallback, `effectiveEnterFrames` becomes 0, and the component's
first hook calls

    interpolate(localFrame, [0, 0], [0, 1])

which Remotion refuses — `inputRange must be strictly monotonically increasing`
— on every frame, of every component that uses useMGPhase. All fourteen.
Proven the other way on 2026-09-14: the same asset, same project, same frame,
with enterFrames 0 -> 32 and exitFrames 0 -> 12 supplied as propertyOverrides,
renders the full card.

So the rule this file enforces:

    A REGISTERED DEFAULT MUST EQUAL WHAT THE COMPONENT DOES WHEN THE PROP IS
    ABSENT. Where the code says `X ?? D`, the default is D's VALUE. Where D
    cannot be resolved to a literal, the component is REFUSED rather than
    guessed at — a guess there is a silent override wearing a schema's clothes.

It is the same family as `value` typed `text` (which made StatCard return null
on its second line), and the same family as every absence-as-zero finding in
CLAUDE.md: a legal value standing in for a question nobody asked.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PORTED = os.path.join(HERE, "ported_mg")
OUT = os.path.join(HERE, "chatcut_registry.json")

sys.path.insert(0, HERE)
import derive_prop_types                                       # noqa: E402

_LIT = re.compile(
    r'^(?:(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|"([^"]*)"|\'([^\']*)\'|(true|false))$')


def _lit(tok):
    """A JS literal -> a Python value, or None if it is not a literal."""
    m = _LIT.match(tok.strip())
    if not m:
        return None
    if m.group(1) is not None:
        t = m.group(1)
        v = float(t)
        return int(v) if v.is_integer() and "." not in t.split("e")[0] else v
    if m.group(2) is not None:
        return m.group(2)
    if m.group(3) is not None:
        return m.group(3)
    return m.group(4) == "true"


def _expr_after(code, at):
    """The expression starting at `at`, to the first depth-0 terminator."""
    depth, i = 0, at
    while i < len(code):
        c = code[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and (c in ",;\n"):
            break
        i += 1
    return code[at:i].strip()


def _use_mg_phase_options(code):
    """{defaultEnterFrames: 32, defaultExitFrames: 12} at THIS component's own
    useMGPhase call site — the binding the fallback identifier refers to."""
    m = re.search(r"useMGPhase\(\s*\{[^}]*\}\s*,\s*\{([^}]*)\}", code, re.S)
    if not m:
        return {}
    got = {}
    for k, v in re.findall(r"(\w+):\s*([^,\s}]+)", m.group(1)):
        got[k] = v.strip()
    return got


def _consts(code):
    """`var X = <literal>;` declared in the blob."""
    got = {}
    for k, v in re.findall(r"^\s*(?:var|const|let)\s+(\w+)\s*=\s*([^;\n]+);",
                           code, re.M):
        lv = _lit(v)
        if lv is not None:
            got[k] = lv
    return got


def resolve(expr, code, consts, phase_opts, peers, depth=0):
    """Evaluate a `??` fallback to a concrete value, or return (None, why).

    Only the forms that actually occur, each resolved rather than assumed.
    Anything else refuses — an unresolvable fallback is exactly where a guess
    would become a silent override.
    """
    expr = expr.strip()
    # An unbalanced trailing `)` left over from splitting a parenthesised
    # ternary — `d.fontSize)` is `d.fontSize`, and without this the lookup that
    # would have answered 64 reports "cannot resolve" instead.
    while expr.count(")") > expr.count("(") and expr.endswith(")"):
        expr = expr[:-1].strip()
    while expr.count("(") > expr.count(")") and expr.startswith("("):
        expr = expr[1:].strip()
    if depth > 4:
        return None, "fallback nests too deep to resolve"
    v = _lit(expr)
    if v is not None:
        return v, f"literal {expr}"
    # `defaults.offsetX ?? 0` — `defaults` is undefined at every call site in
    # this corpus (resolveMGPosition is called with `undefined`), so the chain
    # continues to the trailing literal.
    m = re.match(r"^defaults\.\w+\s*\?\?\s*(.+)$", expr, re.S)
    if m:
        return resolve(m.group(1), code, consts, phase_opts, peers, depth + 1)
    # A TERNARY CHAIN OVER ANOTHER PROP'S LENGTH. Stamp sizes its type from the
    # text it was given: `text.length > 14 ? 78 : text.length > 11 ? 94 :
    # d.fontSize`. Unresolved, the registry's 0 stood and the seal rendered its
    # ring with no words in it. Evaluated against the component's OWN defaults
    # it answers 64, which is what Stamp picks for a short stamp — the same
    # rule as everywhere else here: ask the component, do not invent a number.
    # A longer stamp would authored-pick 78 or 94; that stays a recorded
    # divergence rather than a blank frame.
    m = re.match(r"^\(?(.+?)\s*\?\s*(.+?)\s*:\s*(.+)\)?$", expr, re.S)
    if m and "?" not in m.group(1):
        cond, then_, else_ = m.group(1), m.group(2), m.group(3)
        c = re.match(r"^(\w+)\.length\s*(>|>=|<|<=|===|!==)\s*(-?\d+)$",
                     cond.strip())
        if c:
            base = peers.get(c.group(1))
            if isinstance(base, str):
                n, op, lim = len(base), c.group(2), int(c.group(3))
                truth = {">": n > lim, ">=": n >= lim, "<": n < lim,
                         "<=": n <= lim, "===": n == lim, "!==": n != lim}[op]
                return resolve(then_ if truth else else_, code, consts,
                               phase_opts, peers, depth + 1)
    m = re.match(r"^Math\.(max|min)\((.+)\)$", expr, re.S)
    if m:
        parts, d, cur = [], 0, ""
        for ch in m.group(2):
            if ch in "([{":
                d += 1
            elif ch in ")]}":
                d -= 1
            if ch == "," and d == 0:
                parts.append(cur); cur = ""
            else:
                cur += ch
        parts.append(cur)
        vals = []
        for p in parts:
            pv, why = resolve(p, code, consts, phase_opts, peers, depth + 1)
            if pv is None:
                return None, f"Math.{m.group(1)} operand: {why}"
            vals.append(pv)
        return (max(vals) if m.group(1) == "max" else min(vals)), \
            f"Math.{m.group(1)}{tuple(vals)}"
    # `size = d.size`, where `const d = STYLE_DEFAULTS[style]`. Stamp's whole
    # geometry hangs off this: the registry sent `size: 0` and the seal
    # rendered at diameter zero — a blank frame with every property "set".
    # The table IS in the blob and the selector IS another prop's default, so
    # this is a lookup, not a guess.
    m = re.match(r"^([A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)$", expr)
    if m:
        holder, key = m.group(1), m.group(2)
        b = re.search(r"(?:var|const|let)\s+" + re.escape(holder)
                      + r"\s*=\s*([A-Za-z_$][\w$]*)\[([A-Za-z_$][\w$]*)\]", code)
        if b:
            table, sel = b.group(1), b.group(2)
            selv = peers.get(sel)
            if selv is None:
                s2 = re.search(re.escape(sel) + r"\s*=\s*props\.\w+\s*\?\?\s*([^;\n]+)",
                               code)
                if s2:
                    selv = _lit(s2.group(1).strip())
            if selv is not None:
                t = re.search(r"(?:var|const|let)\s+" + re.escape(table)
                              + r"\s*=\s*\{", code)
                if t:
                    depth, i = 0, t.end() - 1
                    while i < len(code):
                        if code[i] == "{":
                            depth += 1
                        elif code[i] == "}":
                            depth -= 1
                            if depth == 0:
                                break
                        i += 1
                    blob = code[t.end():i]
                    ent = re.search(re.escape(str(selv)) + r"\s*:\s*\{([^}]*)\}",
                                    blob)
                    if ent:
                        f = re.search(re.escape(key) + r"\s*:\s*([^,\n}]+)",
                                      ent.group(1))
                        if f:
                            v = _lit(f.group(1).strip())
                            if v is not None:
                                return v, f"{table}[{selv!r}].{key}"
        return None, f"cannot resolve `{expr[:48]}`"
    if re.fullmatch(r"[A-Za-z_$][\w$]*", expr):
        if expr in phase_opts:                      # defaultEnterFrames etc.
            return resolve(phase_opts[expr], code, consts, phase_opts, peers,
                           depth + 1)
        if expr in consts:
            return consts[expr], f"blob const {expr}={consts[expr]!r}"
        if expr in peers:
            return peers[expr], f"peer prop {expr}={peers[expr]!r}"
    return None, f"cannot resolve `{expr[:48]}`"


def _param_defaults(code, name):
    """`key = <literal>` in the component's own destructuring parameter list.

    THE THIRD DEAD-FALLBACK MECHANISM, and the quietest. `var StepDivider = ({
    step = 1, ... })` never fires once the registry declares `step` at 0 —
    exactly like `??`, but with no operator to grep for.
    """
    m = re.search(r"var " + re.escape(name) + r" = \(\{(.*?)\}\)\s*=>",
                  code, re.S)
    if not m:
        # THE THREE THAT TAKE `(props)` DIRECTLY destructure in the body, and
        # their defaults live there instead. Same question, second spelling.
        m2 = re.search(r"var " + re.escape(name) + r" = \(props\)\s*=>(.*?)\n  \};",
                       code, re.S)
        if not m2:
            return {}
        m = re.search(r"const \{(.*?)\} = props", m2.group(1), re.S)
        if not m:
            return {}
    # THE RAW EXPRESSION, NOT ONLY LITERALS. `size = d.size` is a parameter
    # default too, and dropping it because it is not a literal is what left
    # Stamp registered at diameter 0.
    #
    # SPLIT ON TOP-LEVEL COMMAS ONLY. A naive split cut
    # `scrimColor = "rgba(0, 0, 0, 0.55)"` into four fragments and reported the
    # default as unresolvable — the same comma-splitting mistake that lost
    # NamePlate's `startMs` inside a comment, one file along.
    txt = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)
    txt = re.sub(r"//[^\n]*", "", txt)
    parts, depth, cur = [], 0, ""
    for ch in txt:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur); cur = ""
        else:
            cur += ch
    parts.append(cur)
    got, renamed = {}, {}
    for part in parts:
        mm = re.match(r"\s*(\w+)\s*=\s*(.+)$", part, re.S)
        if mm:
            got[mm.group(1)] = mm.group(2).strip()
            continue
        # A DESTRUCTURE CAN RENAME, AND THE FALLBACK THEN LIVES ON THE NEW NAME.
        # Stamp takes `{ fontSize: fontSizeProp }` and later writes
        # `fontSizeProp ?? (text.length > 14 ? 78 : ... : d.fontSize)`. Every
        # search here keyed on the PROP name, found no `fontSize ??`, and left
        # the registry's 0 standing — so `0 ?? …` returned 0 and the seal
        # rendered its ring with NO TEXT INSIDE. The pixel diff called that
        # MEASURED at 3.8%; only looking at the frame showed the words missing.
        rn = re.match(r"\s*(\w+)\s*:\s*(\w+)\s*$", part)
        if rn:
            renamed[rn.group(1)] = rn.group(2)
    return got, renamed


def reconcile(name, code, props):
    """Rewrite each default to the component's own absent-prop behaviour.

    Returns (props, changes, divergences).

    A DIVERGENCE IS RECORDED, NOT SILENTLY ACCEPTED, AND NEVER REFUSES THE
    COMPONENT. Seven components derive a colour default from another colour
    (`withAlpha(textColor, 0.7)`, `inkFor(backdropColor)`); those cannot be
    resolved to a literal and the type default stands instead. That is a
    COSMETIC difference on a component that renders — a different class from
    `enterFrames: 0`, which renders nothing at all. Refusing the whole
    component over a derived tint would be the tight-pattern mistake again:
    a check that rejects a working implementation is not a check.
    """
    consts = _consts(code)
    phase_opts = _use_mg_phase_options(code)
    params_raw, renamed = _param_defaults(code, name)
    peers = {p["key"]: p["defaultValue"] for p in props}
    params = {}
    for k, raw in params_raw.items():
        lv = _lit(raw)
        if lv is not None:
            params[k] = lv
    peers.update(params)              # the parameter default is what the body sees
    changes, divergences = [], []
    for p in props:
        k, val, why = p["key"], None, None
        # 1. the parameter list wins: its default is what the body reads.
        if k in params:
            val, why = params[k], f"parameter default `{k} = {params[k]!r}`"
        elif k in params_raw:
            val, why = resolve(params_raw[k].strip(), code, consts, phase_opts,
                               peers)
            why = f"parameter default `{k} = {params_raw[k].strip()}` -> {why}"
            if val is None:
                divergences.append((k, "unresolvable parameter default",
                                    params_raw[k].strip()[:60]))
        else:
            # 2. a `??` in the body — on the prop's own name, or on the
            #    local it was renamed to in the parameter list.
            local = renamed.get(k, k)
            m = re.search(r"(?:\.|\b)" + re.escape(local) + r"\s*\?\?\s*", code)
            if m:
                expr = _expr_after(code, m.end())
                val, why = resolve(expr, code, consts, phase_opts, peers)
                if val is None:
                    divergences.append((k, "unresolvable fallback", why))
            # 3. no fallback at all: the body sees the registered value. But a
            #    body that BRANCHES on `!== undefined` has no value meaning
            #    absent — say so rather than pretend a number covers it.
            elif re.search(r"\b" + re.escape(k)
                           + r"\s*(?:!==|===)\s*(?:void 0|undefined)", code):
                divergences.append(
                    (k, "unset-sensitive",
                     "the code branches on `!== undefined`; no default means absent"))
        if val is None:
            continue
        if p["type"] == "number" and isinstance(val, float) and val.is_integer():
            val = int(val)
        if val != p["defaultValue"]:
            changes.append((k, p["defaultValue"], val, why))
            p["defaultValue"] = val
    return props, changes, divergences


def build(verbose=True):
    comps, refused, report = {}, {}, []
    names = sorted(f[:-4] for f in os.listdir(PORTED) if f.endswith(".jsx"))
    for n in names:
        props, skipped, arrays_lost, content_unavailable = \
            derive_prop_types.derive(n)
        if props is None:
            refused[n] = {"reason": "not a single component", "detail": skipped}
            continue
        if skipped:
            refused[n] = {
                "reason": "structured props ChatCut cannot express",
                "detail": ", ".join(f"{k}: {t}" for k, t in skipped)}
            continue
        src = os.path.join(PORTED, n + ".jsx")
        r = subprocess.run(["node", os.path.join(HERE, "chatcut_wrap.mjs"), src],
                           capture_output=True, text=True, cwd=HERE)
        if r.returncode != 0:
            refused[n] = {"reason": "wrap refused", "detail": r.stdout[:300]}
            continue
        out = os.path.join(HERE, "_wrapped.jsx")
        subprocess.run(["node", os.path.join(HERE, "chatcut_wrap.mjs"), src, out],
                       capture_output=True, text=True, cwd=HERE, check=True)
        code = open(out, encoding="utf-8").read()
        os.remove(out)
        # THE PROPERTY LIST AND THE CODE MUST NAME THE SAME SET, BOTH WAYS.
        # ChatCut refuses either mismatch by name:
        #   "property `startMs` is declared in properties array but not used"
        #   "props.X is used in code but not declared in properties"
        # The two lists come from different places — the declarations from
        # types.ts, the reads from the component's own parameter list via
        # chatcut_wrap — so they drift. Six of fourteen were refused on this
        # alone, and the refusal was being filed as ABSENT next to genuine
        # blank frames: two states, one number. Reconcile against the CODE,
        # which is the thing ChatCut runs.
        # EVERY NAME THE BLOB READS MUST EXIST. ChatCut answers this with
        # `Undefined identifier "MessageBubble"` and nothing local did — so
        # ask it here, against the same global set a probe MG measured from
        # inside ChatCut's own renderer.
        fr = subprocess.run(["node", os.path.join(HERE, "free_identifiers.mjs"),
                             "/dev/stdin"], input=code, capture_output=True,
                            text=True, cwd=HERE)
        try:
            free = json.loads((fr.stdout or "[]").strip() or "[]")
        except ValueError:
            free = [{"name": "scanner failed: " + (fr.stderr or "")[:80],
                     "line": 0}]
        if free:
            refused[n] = {
                "reason": "the blob reads an identifier ChatCut does not have",
                "detail": ", ".join("%s (line %d)" % (x["name"], x["line"])
                                    for x in free)}
            continue
        read = set(re.findall(r"\bprops\.([A-Za-z_$][\w$]*)", code))
        undeclared = sorted(read - set(p["key"] for p in props))
        if undeclared:
            refused[n] = {"reason": "the code reads a prop that cannot be typed",
                          "detail": ", ".join(undeclared)}
            continue
        dropped = [p["key"] for p in props if p["key"] not in read]
        props = [p for p in props if p["key"] in read]
        props, changes, divergences = reconcile(n, code, props)
        for k, ts in arrays_lost:
            divergences.append(
                (k, "array prop, optional",
                 f"{ts} cannot be carried; the feature is unavailable"))
        if dropped:
            divergences.append(
                (", ".join(dropped), "declared but never read",
                 "dropped: ChatCut refuses a property the code does not read"))
        comps[n] = {"code": code, "properties": props, "skipped": skipped,
                    "divergences": [{"key": k, "kind": kind, "detail": why}
                                    for k, kind, why in divergences],
                    # DRAWING PIXELS IS NOT BEING DRIVABLE. Timeline, RankedList,
                    # RecordingFrame and TimelineRoadmap each take their whole
                    # content as an array, and each falls back to its own
                    # DEFAULT_STEPS when it does not arrive — so they render
                    # cleanly, pass the pixel diff, and put placeholder content
                    # on the video. The render check cannot tell that apart from
                    # a working component, so the registry says it here and the
                    # sheet leaves them off: a component that cannot carry the
                    # edit's content is not offered, whatever it draws.
                    "content_unavailable": [k for k, _ in content_unavailable]}
        report.append((n, changes, divergences))
    if verbose:
        print("  %-18s %-14s %s" % ("component", "prop", "default corrected to the code's own"))
        tot = 0
        for n, changes, _ in report:
            for k, was, now, why in changes:
                print("  %-18s %-14s %r -> %r   (%s)" % (n, k, was, now, why))
                tot += 1
        print("  %d defaults corrected across %d components" % (tot, len(comps)))
        print()
        print("  DIVERGENCES — recorded, not silently accepted. The component "
              "renders; this default is not the authored one.")
        nd = 0
        for n, _, divergences in report:
            for k, kind, why in divergences:
                print("  %-18s %-14s %-22s %s" % (n, k, kind, why[:64]))
                nd += 1
        print("  %d divergences across %d components" % (nd, len(comps)))
        print("  registered %d, refused %d" % (len(comps), len(refused)))
    return {"components": comps, "refused": refused}


if __name__ == "__main__":
    reg = build()
    if "--write" in sys.argv:
        json.dump(reg, open(OUT, "w", encoding="utf-8"), indent=1)
        print("wrote", OUT)
    else:
        print("(dry run — pass --write to update chatcut_registry.json)")
