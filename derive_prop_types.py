#!/usr/bin/env python3
"""Derive each component's ChatCut property TYPES from its types.ts.

WHY. The first registry typed props by NAME: anything matching ms|frames|size|
width|seed|offset|rate|count|index|duration became a number, everything else
text. `value` matched nothing, so StatCard's hero figure was registered as
`type: "text"` — and the component's first line is

    if (typeof value !== "number" || !Number.isFinite(value)) return null;

so it renders a transparent frame and reports success. 29 of 29 registered;
1 of 1 tested; 0 of 1 rendered.

Reading the interface instead of guessing at the name is the third instance of
one move today — the edit_item write vocabulary from inspect_item, the five
fixture shapes from their types.ts, and now this.
"""
import os
import re
import sys

ROOT = ("/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/src/remotion"
        "/src/motion-graphics")

# TIMING DEFAULTS THAT ARE NOT ZERO. `useMGPhase` computes durationFrames from
# durationMs; at 0 the component is out of phase before `value` is read, so a
# correct value still renders nothing. Zero is a legal number and the wrong
# default — the absence-as-zero family, in a property schema.
# DEFAULTS THAT ARE LEGAL NUMBERS AND WRONG ANSWERS. Zero is a valid number
# for all of these and a broken value for each: durationMs=0 puts useMGPhase
# out of phase before `value` is read; scale=0 is clamped to 0.1 by
# resolveMGPosition and renders a tenth-size graphic; decimals=0 sends the
# component down toFixed(0) instead of the plain integer path. The
# absence-as-zero family, in a property schema — a default nobody ruled.
REAL_DEFAULTS = {"startMs": 0, "durationMs": 4000, "scale": 1,
                 "enterFrames": None, "exitFrames": None, "decimals": None,
                 "offsetX": 0, "offsetY": 0, "fromValue": 0}


def _interfaces():
    out = {}
    for d, _, fs in os.walk(ROOT):
        if "types.ts" not in fs:
            continue
        src = open(os.path.join(d, "types.ts"), encoding="utf-8").read()
        for m in re.finditer(
                # `\s*` BEFORE THE BRACE. Without it this matched only interfaces that have an
                # `extends` clause — the `[^{]+` swallowed the space — so it found exactly the
                # 29 components and missed MGTimingProps and MGPositionProps, the two bases
                # every one of them inherits from. 29 hits read as success.
                r"(?:export )?interface (\w+)(?:\s+extends\s+([^{]+?))?\s*\{(.*?)\n\}",
                src, re.S):
            out[m.group(1)] = (m.group(2) or "", m.group(3))
    # the shared bases the components extend
    for extra in ("shared/types.ts", "shared/positioning.ts"):
        p = os.path.join(ROOT, extra)
        if os.path.exists(p):
            src = open(p, encoding="utf-8").read()
            for m in re.finditer(
                    # `\s*` BEFORE THE BRACE. Without it this matched only interfaces that have an
                # `extends` clause — the `[^{]+` swallowed the space — so it found exactly the
                # 29 components and missed MGTimingProps and MGPositionProps, the two bases
                # every one of them inherits from. 29 hits read as success.
                r"(?:export )?interface (\w+)(?:\s+extends\s+([^{]+?))?\s*\{(.*?)\n\}",
                    src, re.S):
                out[m.group(1)] = (m.group(2) or "", m.group(3))
    return out


def _fields(name, ifaces, seen=None):
    seen = seen or set()
    if name in seen or name not in ifaces:
        return {}
    seen.add(name)
    ext, body = ifaces[name]
    got = {}
    for base in re.findall(r"\w+", ext):
        got.update(_fields(base, ifaces, seen))
    body = re.sub(r"//[^\n]*", "", body)
    for m in re.finditer(r"^\s*(\w+)(\??):\s*([^;\n]+);", body, re.M):
        got[m.group(1)] = (m.group(3).strip(), m.group(2) != "?")
    return got


def _aliases():
    """{name: union-text} for every `export type X = "a" | "b"` in the tree.

    A NAMED UNION IS STILL A UNION. `anchor: MGAnchor` returned "no ChatCut
    type" and refused StatCard, MouseDrag, PillCluster and Reticle outright —
    but MGAnchor is `"center" | "top" | ...`, which is exactly a ChatCut
    `select`. "Cannot be expressed" and "I did not look it up" are different
    findings and only one of them is about ChatCut.
    """
    out = {}
    for d, _, fs in os.walk(ROOT):
        for f in fs:
            if not f.endswith(".ts") and not f.endswith(".tsx"):
                continue
            src = open(os.path.join(d, f), encoding="utf-8").read()
            for m in re.finditer(r"export type (\w+)\s*=\s*([^;]+);", src, re.S):
                out[m.group(1)] = re.sub(r"\s+", " ", m.group(2)).strip()
    return out


_ALIAS = None


def chatcut_type(key, ts):
    """TS type -> ChatCut property type. The TYPE decides, then the name."""
    global _ALIAS
    if _ALIAS is None:
        _ALIAS = _aliases()
    ts = ts.strip()
    seen = 0
    while ts in _ALIAS and seen < 4:          # resolve named unions
        ts = _ALIAS[ts].strip()
        seen += 1
    ts = ts.lstrip("| ").strip()
    # AN ARRAY IS NOT A SCALAR, AND `startswith` CANNOT TELL. `tags: string[]`
    # matched `ts.startswith("string")` and registered as a TEXT property with
    # default "" — so PillCluster's pills and PillMarquee's stream, the CONTENT
    # of both components, arrived as an empty string and each rendered a blank
    # frame that no validator objected to. Same shape as `value` typed `text`
    # (StatCard returned null on its second line) and the same lesson: the
    # prefix of a type name is not the type. Arrays are refused here, which
    # sends the component to the same honest REFUSED list as the thirteen
    # others ChatCut cannot express.
    if ts.endswith("[]") or ts.startswith(("Array<", "ReadonlyArray<")):
        return "__array__", None
    if re.fullmatch(r"(\s*-?\d+\s*\|?)+", ts):     # numeric union, e.g. 1 | -1
        return "number", None
    if re.fullmatch(r'(\s*"[^"]+"\s*\|?)+', ts):
        return "select", [o.strip('" ') for o in ts.split("|")]
    if ts.startswith("number"):
        return "number", None
    if ts.startswith("boolean"):
        return "boolean", None
    if ts.startswith("string"):
        # only a string may be a colour, and only if the NAME says so
        if re.search(r"colou?r", key, re.I):
            return "color", None
        return "text", None
    return None, None          # objects/arrays: not a ChatCut property type


def derive(component):
    ifaces = _interfaces()
    nm = next((k for k in ifaces if k.lower() == component.lower() + "props"),
              None)
    # ── DISCRIMINATED UNIONS ARE NOT FLAT SCHEMAS ──────────────────────────
    # `ProgressBarProps = ProgressBarValueProps | ProgressBarPercentProps` and
    # `SpeechBubbleProps` = the four platform shapes. A ChatCut property schema
    # is FLAT: merging a union offers every variant's fields at once, and these
    # unions are mutually exclusive by construction (`value?: never`). Flatten
    # one and the agent can set a combination the component refuses.
    #
    # So each union is answered explicitly rather than merged:
    #   ProgressBar  -> the VALUE/TOTAL variant, named. The percentage form is
    #                   simply not offered; that is a stated choice, not a gap.
    #   SpeechBubble -> REFUSED. It is a dispatcher with no MG_MAP entry and no
    #                   still; the four platform components are the real ones.
    UNION_PICK = {"ProgressBar": "ProgressBarValueProps"}
    UNION_REFUSE = {"SpeechBubble": ("a DISPATCHER, not a component — it "
                                     "switches on `platform` to TweetBubble / "
                                     "InstagramComment / IMessageBubble / "
                                     "TikTokComment. Register those instead.")}
    if component in UNION_REFUSE:
        return None, UNION_REFUSE[component], [], []
    if not nm and component in UNION_PICK:
        nm = UNION_PICK[component]
    if not nm:
        return None, f"no `{component}Props` interface found", [], []
    props, skipped, unavailable = [], [], []
    for key, (ts, required) in sorted(_fields(nm, ifaces).items()):
        t, opts = chatcut_type(key, ts)
        if t is None:
            skipped.append((key, ts))
            continue
        # AN ARRAY IS ONLY FATAL WHEN IT IS THE CONTENT. Refusing every
        # component with any array prop threw away PullQuote, which had
        # rendered 2.34% of the frame the run before: `keywords` is OPTIONAL
        # highlighting, and the quote draws without it. A check tight enough
        # to reject a working implementation is not a check. So a REQUIRED
        # array refuses the component — it cannot be driven at all — and an
        # OPTIONAL one is declared as the empty text ChatCut can carry, with
        # the lost feature recorded. Whether what remains is worth offering is
        # then decided by the render check, not by this guess.
        if t == "__array__":
            if required:
                skipped.append((key, ts))
                continue
            t, opts = "text", None
            unavailable.append((key, ts))
        dv = ({"number": 0, "text": "", "boolean": False,
               "color": "#FFFFFF", "select": (opts or [""])[0]})[t]
        if key in REAL_DEFAULTS and REAL_DEFAULTS[key] is not None:
            dv = REAL_DEFAULTS[key]
        # OPTIONAL-BY-ABSENCE WAS RIGHT ABOUT THE COMPONENT AND WRONG ABOUT
        # THE VALIDATOR. Declaring `enterFrames` at 0 does turn "unset" into a
        # decision — but ChatCut matches `props.X` STATICALLY IN THE CODE, so
        # dropping the declaration does not make the prop optional, it makes
        # the whole component unregistrable:
        #   "props.enterFrames is used in code but not declared in properties"
        # Every prop the wrapped code reads must be declared. propertyOverrides
        # supplies the real value at placement, so the default is a formality.
        p = {"key": key, "label": key, "type": t, "defaultValue": dv}
        if opts:
            p["options"] = opts
        props.append(p)
    # IS THE ARRAY THE CONTENT, OR AN ENHANCEMENT? Both are optional arrays and
    # they are not the same finding. PullQuote's `keywords` only picks which
    # words get highlighted — the quote itself arrives through `text`, which is
    # REQUIRED and carryable, so PullQuote can carry the edit. Timeline's
    # `steps` IS the edit, and with nothing else required it falls back to its
    # own DEFAULT_STEPS: it renders placeholder content, passes a pixel diff,
    # and would put lorem on the video.
    #
    # The separator is measured, not named: does the component have any
    # REQUIRED prop that is carryable and is not timing or position? Where that
    # is ambiguous the component is marked unavailable, because under-offering
    # costs a component and over-offering costs a frame of someone else's
    # placeholder text in Zac's edit.
    _TIMING = {"startMs", "durationMs", "enterFrames", "exitFrames", "anchor",
               "offsetX", "offsetY", "scale", "textShadow"}
    carryable_required = [
        k for k, (ts, req) in _fields(nm, ifaces).items()
        if req and k not in _TIMING
        and chatcut_type(k, ts)[0] not in (None, "__array__")]
    # AN ARRAY OF OBJECTS IS THE BODY. `keywords: string[]` is a list of words
    # that already appear in PullQuote's `text` — losing it loses the
    # highlighting, and the quote still reads. `points: DropBannerPoint[]` is
    # the banner's whole content, and DropBanner passed the carryable-required
    # test above only because it also has a `title`. The frame settled it:
    # DropBanner and DropCard each rendered a blank white shape across ~40% of
    # the picture, title and all, with nothing in it — which the pixel diff
    # scored MEASURED. The element TYPE separates the two cases without a hand
    # list and without reading a prop's name.
    structured = [(k, ts) for k, ts in unavailable
                  if not re.match(r"^(string|number|boolean)\s*\[\]$", ts.strip())]
    content_unavailable = (unavailable if not carryable_required
                           else structured)
    return props, skipped, unavailable, content_unavailable


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "StatCard"
    props, skipped, _, _ = derive(c)
    if props is None:
        print("FAILED:", skipped); sys.exit(1)
    for p in props:
        print(f"  {p['key']:16s} {p['type']:8s} default={p['defaultValue']!r}"
              + (f" options={p['options']}" if p.get("options") else ""))
    print(f"  -- skipped (not a ChatCut property type): {skipped}")
