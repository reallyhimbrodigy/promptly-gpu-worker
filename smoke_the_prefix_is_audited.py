#!/usr/bin/env python3
"""What is cached is what the agent can act on, and no RATE reaches it.

Zac, 2026-09-16: "The prefix, properly cached in the merged shape. What's in
it, what each costs, what the agent actually reads. Cached and unread comes
out. Read every run and uncached goes in."

WHAT THIS CAN AND CANNOT ANSWER, said plainly. "What the agent actually reads"
is a fact about a RUN and there has not been one on this shape — so this file
does not pretend to measure it. What it does check is the half that is
structural: every cached thing has a tool that can use it, every thing the
agent would otherwise fetch is cached, and nothing in the prefix breaks a
standing law.

THE LAW IT ENFORCES. The density rates GRADE; they never instruct. They must
never reach the agent as a target or appear in the prompt. The audit found a
SECOND instance of the exact shape the first one is recorded under — a rate
surviving inside prose, because prose that DESCRIBES a rate reads as harmless
beside a schema field that DEMANDS one:

    01_cut_pass.md: "MEASURED 2026-08-04: transitions fire on only 4.9% of
    planned jobs (38 of 778), mean 0.05 per 25s." ... "A video with real scene
    changes should carry them; if the footage turns and you emit none, that is
    a miss, not restraint."

That is a measured production rate PLUS an instruction to raise it, in a
LOADBEARING craft document that is now in the single agent's prefix. The craft
point survives the numbers; the numbers are gone.

THE LEGS:
  1. no per-unit rate reaches anything the agent reads
  2. every prefix section is present or LOUDLY absent — never silently dropped
  3. a catalogue is CACHED exactly when its search tool is withheld: cached and
     unreachable is dead weight, uncached and unreachable is a capability the
     agent cannot name
  4. the prefix's cost is reported, per section, so it can be argued about

RED-proven at the bottom.
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modal_stub                                                 # noqa: E402
modal_stub.install()
import chatcut_job_app as J                                       # noqa: E402
import watched_reference as W                                     # noqa: E402

J._frames_of = lambda *a, **k: []
SRC = open(os.path.join(HERE, "chatcut_job_app.py"), encoding="utf-8").read()
fail = []

# a rate the agent could read as a target: "7.5 per 25s", "0.05/25s"
RATE = re.compile(r"\d+(?:\.\d+)?\s*(?:per|/)\s*\d+\s*s\b", re.I)


def read_by_agent():
    """Everything that reaches the model, by name. THE POPULATION, asserted."""
    out = {"system prompt": J.build_system_prompt(),
           "watched artefact": W.watched_moments(),
           "mode rule": open(os.path.join(HERE, "mode_rule.txt"),
                             encoding="utf-8").read()}
    for nm in J.LOADBEARING:
        p = os.path.join(HERE, "knowledge", nm)
        if os.path.exists(p):
            out["craft:" + nm] = open(p, encoding="utf-8").read()
    return out


def legs(sources=None, tools=None):
    sources = sources if sources is not None else read_by_agent()
    tools = tools if tools is not None else _needed(SRC)
    out = []
    if len(sources) < 4:
        out.append(("population", "only %d source(s) of prefix material — "
                                  "every leg below would assert almost nothing"
                    % len(sources)))
        return out

    # 1. NO RATE INSTRUCTS
    for nm, t in sources.items():
        for m in RATE.finditer(t):
            s0 = max(0, m.start() - 70)
            out.append(("rate", "[%s] a per-unit rate reaches the agent: ...%s"
                        % (nm, " ".join(t[s0:m.end() + 30].split()))))

    # 2. EVERY SECTION IS PRESENT OR LOUDLY ABSENT
    sysp = sources["system prompt"]
    # "HOW TO SCOPE THIS JOB" left the prefix by ruling (mode_rule 2k -> 0,
    # 2026-09-17); its absence is the design, not an omission.
    for head in ("HOW EACH FAMILY IS BUILT",
                 "THE SOUND LIBRARY", "THE COMPONENT LIBRARY",
                 "THE RECORD, AND WHO EXPORTS", "THE CRAFT DOCUMENTS"):
        if head not in sysp:
            out.append(("section", "the prefix carries no %r section at all — "
                                   "an omission is silent, an ABSENT is not"
                        % head))
    for m in re.finditer(r"=====\s*([A-Z][^=]*?):\s*ABSENT\s*\(([^)]*)\)", sysp):
        if not m.group(2).strip():
            out.append(("section", "%r is ABSENT without saying why"
                        % m.group(1).strip()))

    # 3. CACHED EXACTLY WHEN THE SEARCH TOOL IS WITHHELD
    if tools is None:
        out.append(("tools", "NEEDED_TOOLS did not resolve"))
        return out
    for cat, tool, head in (("sound library", "browse_library",
                             "THE SOUND LIBRARY"),
                            ("component library", "browse_assets",
                             "THE COMPONENT LIBRARY")):
        # CACHED MEANS THE PREFIX HAS A PRODUCER FOR IT, not that the file
        # happens to be readable on this machine. /craft is a container mount,
        # so locally these sections render "ABSENT (No such file)" — and a
        # first version of this leg read that as NOT CACHED and failed on a
        # clean tree. A check that is always red is a check nobody reads, and
        # this one would have been red on every developer machine forever.
        # The HEADER being emitted at all is what proves the producer exists;
        # whether the file loaded is leg 2's question, and it is asked there.
        cached = head in sysp
        reachable = tool in tools
        if reachable and cached:
            out.append(("cache", "the %s is BOTH cached and searchable (%s) — "
                                 "the cache is dead weight, or the tool is a "
                                 "turn nobody needs" % (cat, tool)))
        if not reachable and not cached:
            out.append(("cache", "the %s is neither cached nor reachable (%s "
                                 "withheld) — a capability the agent cannot "
                                 "name is one it cannot use" % (cat, tool)))
    return out


def _needed(src):
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "NEEDED_TOOLS"
                for t in n.targets):
            return [e.value for e in n.value.elts
                    if isinstance(e, ast.Constant)]
    return None


for _k, _m in legs():
    fail.append("[%s] %s" % (_k, _m))

# ── 4. THE COST, REPORTED ────────────────────────────────────────────────────
_src = read_by_agent()
_sysp = _src["system prompt"]
print("  PREFIX COST (chars measured; tokens are chars/4 and are an ESTIMATE)")
_rows = [("system prompt (this machine)", len(_sysp))]
for _nm in J.LOADBEARING:
    _p = os.path.join(HERE, "knowledge", _nm)
    if os.path.exists(_p):
        _rows.append(("  craft: " + _nm, os.path.getsize(_p)))
_rows.append(("mode_rule.txt", len(_src["mode rule"])))
_rows.append(("watched artefact (text)", len(_src["watched artefact"])))
_wb, _wst = W.watched_frames()
_rows.append(("watched artefact (%d sheets)" % len(_wb), 0))
for _n, _c in _rows:
    print("    %-40s %8d ch  ~%6d tok" % (_n, _c, _c // 4))
print("    %-40s %8s     ~%6d tok  (16 x ~1550, the 1568px cap)"
      % ("  the sheets, as images", "", len(_wb) * 1550))

# ── RED PROOF ────────────────────────────────────────────────────────────────
red = 0
MUT = (
    ("a density rate comes back into the craft", "rate",
     lambda s, t: (dict(s, **{"craft:x": "text is the WORKHORSE (~7.5 per 25s)"}),
                   t)),
    ("the sound library becomes searchable again", "cache",
     lambda s, t: (s, list(t) + ["browse_library"])),
    ("a prefix section is dropped silently", "section",
     lambda s, t: (dict(s, **{"system prompt":
                              s["system prompt"].replace(
                                  "THE SOUND LIBRARY", "xxx")}), t)),
)
_tools = _needed(SRC)
for label, kind, mut in MUT:
    _s2, _t2 = mut(dict(_src), list(_tools or []))
    hit = any(k == kind for k, _ in legs(_s2, _t2))
    print("    %-48s -> names %s: %s" % (label, kind, hit))
    if not hit:
        red += 1

if not MUT:
    print("  *** NO MUTATIONS — this proof asserts nothing")
    red += 1
for _m2 in fail:
    print("  *** " + _m2)
print("\nsmoke_the_prefix_is_audited: %d wrong, %d not red (of %d), %d source(s)"
      % (len(fail), red, len(MUT), len(_src)))
sys.exit(1 if (fail or red or not MUT) else 0)
