#!/usr/bin/env python3
"""The mode rule, run against briefs REAL USERS SENT — not the one that broke it.

Zac, 2026-09-16: "Zac's users write 5,943 distinct requests — 'make it viral,'
'just add captions,' 'no beauty filter.' Take ten real ones from vibe_input and
check the spec each produces. The mode decision produced 43% empty edits on one
brief; nobody has tested it against what users actually send."

WHY THIS CAN BE MECHANICAL, and what that does and does not prove. Q2 is now a
MATCH against a named list — that is the whole fix — so what the RULE
prescribes is computable without a model call. This checks the RULE against the
population. It does NOT check what the model does with the rule; that needs a
run, and the distinction is stated rather than blurred.

WHAT IT FOUND, on twelve verbatim production briefs:

  * NEGATIVE CONSTRAINTS HAD NO PATH. 'dont change face' names no family and
    carries no vibe word, so the procedure sent it to NEITHER -> "it is a
    question". The user uploaded a video and asked for an edit WITHOUT a named
    thing; answering with a question delivers NOTHING. That is the 43% failure
    shape on a real brief class — 4.2% of users, 7.2% of briefs — rather than
    on one invented fixture.
  * AND EXCLUSIONS WERE ROUTED INTO `families`. Q1 said "every one it names
    goes in `families`. These are GUARANTEED", with no carve-out, so 'viral and
    engaging no captions in video' NAMES captions while FORBIDDING them, and
    the guarantee would have delivered the one thing the user excluded. The
    `forbidden` FIELD described this correctly the whole time; the PROCEDURE
    did not mention it. A rule split across two surfaces is enforced on
    whichever one the agent reads first.

THE LEGS:
  1. the vibe list is read from the SHIPPED rule and is non-empty
  2. nothing falls through — only a genuinely contentless brief is a question
  3. a brief whose only content is a constraint does NOT become a question
  4. a forbidden family never lands in `families`
  5. the known answers hold (vibe briefs full_edit, named briefs targeted)

RED-proven at the bottom, against a mutated copy of mode_rule.txt.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RULE_PATH = os.path.join(HERE, "mode_rule.txt")
RULE = open(RULE_PATH, encoding="utf-8").read()
FIX = json.load(open(os.path.join(HERE, "smoke_fixtures", "real_briefs.json"),
                     encoding="utf-8"))
BRIEFS = FIX["briefs"]
fail = []

FAMILY_WORDS = {
    "caption": ("caption", "subtitle"), "text": ("text", "title"),
    "zoom": ("zoom",), "cut": ("cut", "trim", "stumble", "shorten"),
    "sfx": ("sound", "music", "audio"), "transition": ("transition",),
    "card": ("card", "graphic"),
}
# the shapes a user says "not this" in, taken from the corpus's own examples
NEG = re.compile(r"\b(no|not|without|dont|don't|nothing else|never)\b")


def vibe_list(rule):
    i = rule.find("Q2 IS YES:")
    j = rule.find("The list is not exhaustive", i + 1)
    if i < 0 or j <= i:
        return [], []
    block = rule[i + len("Q2 IS YES:"):j]
    phrases = re.findall(r"'([^']+)'", block)
    words = []
    for w in re.split(r"\s+", re.sub(r"'[^']+'", " ", block)):
        words.extend(w.split("/"))
    return (sorted({w.lower() for w in words
                    if len(w) > 2 and w.lower() not in ("like", "<something>")}),
            sorted({p.lower() for p in phrases}))


def spec_for(brief, rule):
    """(mode, families, forbidden, matched) — what the RULE prescribes.

    THIS IS A PROXY FOR Q1 AND AN EXACT READING OF Q2, and the asymmetry is
    deliberate. Q2 is a match against a list the rule names, so it is
    computable. Q1 asks a model whether the brief NAMES a change, and the
    keyword table below is this file's approximation of that — good enough to
    show which BRANCH the rule sends a brief down, not a claim about what the
    model will answer.
    """
    b = brief.lower()
    words, phrases = vibe_list(rule)
    matched = [w for w in words if re.search(r"\b%s\b" % re.escape(w), b)]
    matched += [p for p in phrases if p in b]
    fams, forb = [], []
    for fam, ws in FAMILY_WORDS.items():
        for w in ws:
            m = re.search(r"\b%s" % re.escape(w), b)
            if not m:
                continue
            # "no captions" / "no text on screen" — the clause just before it
            head = b[max(0, m.start() - 22):m.start()]
            (forb if NEG.search(head) else fams).append(fam)
            break
    # A CONSTRAINT NEED NOT BE A FAMILY, and this is the half that was missing.
    # `forbidden` is array-of-string and its own examples include 'no filters'
    # — not a family. 'dont change face' and 'no beauty filter' (two of the
    # three briefs Zac named) forbid something the family vocabulary has no
    # word for, so a detector that only looks for negated FAMILIES finds
    # nothing and the brief falls through to "this is a question".
    for m in NEG.finditer(b):
        tail = b[m.end():].strip()
        if not tail:
            continue
        words_after = tail.split()[:2]
        # TWO WORDS MINIMUM. One word turns 'no problem' — a filler phrase in
        # the viral/unspecific cluster, not a constraint — into
        # `forbidden: problem`, which is junk in the durable record. The MODE
        # was right either way (an unspecific brief is a full_edit); the
        # recorded reason was not, and a plausible wrong record is worse than
        # a missing one.
        if len(words_after) < 2:
            continue
        phrase = " ".join(words_after)
        if not any(phrase.startswith(w) for ws in
                   FAMILY_WORDS.values() for w in ws):
            forb.append(phrase)
    fams = sorted(set(fams) - set(forb))
    forb = sorted(set(forb))
    if "NEVER IN `families`" not in rule:
        fams = sorted(set(fams) | set(forb))     # the pre-fix behaviour
        forb = []
    if fams and matched:
        mode = "full_edit+families"
    elif matched:
        mode = "full_edit"
    elif fams:
        mode = "targeted_change"
    elif forb and "NEITHER, but it FORBIDS something" in rule:
        mode = "full_edit"                       # an edit WITHOUT the thing
    else:
        mode = "question"
    return mode, fams, forb, sorted(set(matched))


def legs(rule=None):
    rule = rule if rule is not None else RULE
    out = []
    words, _phrases = vibe_list(rule)
    if len(words) < 8:
        out.append(("list", "the vibe list read from the rule has %d word(s) "
                            "— every brief below would resolve against an "
                            "empty vocabulary" % len(words)))
        return out
    if not BRIEFS:
        out.append(("population", "no briefs in the fixture — every leg below "
                                  "asserts nothing"))
        return out

    specs = {b["text"]: spec_for(b["text"], rule) for b in BRIEFS}

    # 3. A CONSTRAINT-ONLY BRIEF IS NOT A QUESTION
    for t in ("dont change face",):
        mode, _fams, forb, _m = specs[t]
        if mode == "question":
            out.append(("negative", "%r resolves to a QUESTION. It names no "
                                    "family and carries no vibe, so the "
                                    "procedure asks instead of editing — and "
                                    "a question delivers nothing." % t))
        if not forb:
            out.append(("negative", "%r records no `forbidden`, so the one "
                                    "thing the user actually said is lost" % t))

    # 4. A FORBIDDEN FAMILY NEVER LANDS IN `families`
    for t in ("viral and engaging no captions in video",
              "add zooms. no text on screen or captions"):
        _mode, fams, forb, _m = specs[t]
        if "caption" in fams:
            out.append(("forbidden", "%r puts `caption` in families — the "
                                     "guarantee would deliver the one thing "
                                     "the user excluded" % t))
        if "caption" not in forb:
            out.append(("forbidden", "%r does not record caption as forbidden"
                        % t))

    # 5. THE KNOWN ANSWERS
    # `viral and engaging no captions in video` is full_edit and NOT
    # +families, and that is the fix working rather than a regression: the one
    # family it names is the one it FORBIDS, so `families` is correctly empty.
    # My first version of this table expected +families — written before the
    # exclusion routing existed, and kept as the correction.
    for t, want in (("just make it pop", "full_edit"),
                    ("viral and engaging no captions in video", "full_edit"),
                    ("just add captions", "targeted_change"),
                    ("only zooms", "targeted_change"),
                    ("make the captions bigger", "targeted_change")):
        got = specs[t][0]
        if got != want:
            out.append(("modes", "%r -> %s, expected %s" % (t, got, want)))

    # 2. NOTHING FALLS THROUGH except a genuinely contentless brief
    stray = [t for t, (m, _f, _fo, _x) in specs.items()
             if m == "question" and t != "no problem"]
    if stray:
        out.append(("coverage", "these real briefs resolve to a question and "
                                "deliver nothing: %s" % stray))
    return out


for _k, _m in legs():
    fail.append("[%s] %s" % (_k, _m))

# ── RED PROOF ────────────────────────────────────────────────────────────────
red = 0
MUT = (
    ("exclusions go back into families", "forbidden",
     lambda s: s.replace("NEVER IN `families`", "and also in `families`")),
    ("a constraint-only brief goes back to being a question", "negative",
     lambda s: s.replace("  NEITHER, but it FORBIDS something",
                         "  (retired branch)")),
    ("the vibe list is emptied", "list",
     lambda s: re.sub(r"Q2 IS YES:.*?The list is not exhaustive",
                      "Q2 IS YES:\nThe list is not exhaustive", s,
                      flags=re.S)),
)
for label, kind, mut in MUT:
    m = mut(RULE)
    if m == RULE:
        print("  *** MUTATION DID NOT APPLY: %s (anchor 0x)" % label)
        red += 1
        continue
    hit = any(k == kind for k, _ in legs(m))
    print("    %-48s -> names %s: %s" % (label, kind, hit))
    if not hit:
        red += 1

if not MUT:
    print("  *** NO MUTATIONS — this proof asserts nothing")
    red += 1

print()
print("  %-52s %-20s %s" % ("REAL BRIEF (production vibe_input)", "MODE",
                            "families / forbidden"))
for _b in BRIEFS:
    _mode, _fams, _forb, _mt = spec_for(_b["text"], RULE)
    print("  %-52s %-20s %s%s"
          % (_b["text"][:52], _mode, ",".join(_fams) or "-",
             ("  forbidden: %s" % ",".join(_forb)) if _forb else ""))

for _m2 in fail:
    print("  *** " + _m2)
print("\nsmoke_the_mode_survives_real_briefs: %d wrong, %d not red (of %d), "
      "%d real brief(s)" % (len(fail), red, len(MUT), len(BRIEFS)))
sys.exit(1 if (fail or red or not MUT) else 0)
