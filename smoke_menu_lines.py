#!/usr/bin/env python3
"""Every asset on the menu has ONE line and that line is its name.

    <Name> — <what it is> for <when to use it>
    plain words, no jargon, <= 90 characters, no commas

THE LINE IS THE NAME because `asset.name` is the only per-asset free text a
motion graphic has, and for an audio asset the filename at import is the only
text at all. There is nowhere else to put it that their agent reads.

NO COMMAS IS NOT A STYLE RULE. A comma in a sound filename breaks the upload
helper — it builds an ffmpeg filter graph from the name and a comma is the
separator — and a failed import leaves an orphaned `status: processing`
placeholder that counts as an asset and never resolves. Measured.

ONE DEFINITION, N HOMES. If a description field or a style-guide index turns
out to be read by their agent, the SAME BYTES go there. L5 proves the
byte-identity rule on a fixture, because neither second home exists yet and a
leg over an empty population asserts nothing — the fourth time today that has
decided how a leg is built.
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lane_contract as lc                                     # noqa: E402

LINES = os.path.join(HERE, "measured", "MENU_LINES.json")
MAX_LEN = 90
FAILS = []
NLEGS = 0


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-46s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def split_line(line):
    """-> (name, what_and_when) or (None, None). Accepts either separator.

    The components and caption styles use an EM DASH; the thirteen sounds
    shipped with a HYPHEN in their filenames. Both parse. Normalising would mean
    thirteen re-uploads, so the difference is REPORTED rather than hidden.
    """
    for sep in (" — ", " - "):
        if sep in line:
            head, tail = line.split(sep, 1)
            return head.strip(), tail.strip()
    return None, None


def check(line):
    errs = []
    if len(line) > MAX_LEN:
        errs.append("over %d chars (%d)" % (MAX_LEN, len(line)))
    if "," in line:
        errs.append("contains a comma")
    name, rest = split_line(line)
    if name is None:
        errs.append("no separator")
    else:
        if not name:
            errs.append("no name")
        if " for " not in rest:
            errs.append("no 'for <when>' clause")
    return errs


def main():
    d = json.load(io.open(LINES, encoding="utf-8"))
    groups = {"components": 12, "caption_styles": 7, "sounds": 13}
    allof = [l for g in groups for l in d[g]]

    # L0 THE POPULATION IS THE WHOLE MENU. A subset that happens to pass is the
    # subset-as-total failure.
    counts = {g: len(d[g]) for g in groups}
    leg("L0 thirty_two_lines_one_per_asset",
        counts == groups and len(allof) == 32, "%s = %d" % (counts, len(allof)))

    # L1 EVERY LINE OBEYS THE RULE.
    bad = [(l, check(l)) for l in allof]
    bad = [(l, e) for l, e in bad if e]
    leg("L1 every_line_obeys_the_rule", not bad,
        "%d line(s) break it: %s" % (len(bad), [b[0][:28] for b in bad] or "none"))

    # L2 NO COMMAS, CALLED OUT SEPARATELY because it is a measured upload
    # failure rather than a style preference.
    commas = [l for l in allof if "," in l]
    leg("L2 no_commas_anywhere", not commas,
        "%d with a comma (a comma breaks the upload helper)" % len(commas))

    # L3 EVERY LINE SAYS WHEN TO USE IT, not just what it is. EmojiCard's old
    # line had the what and no when, which is the whole reason this leg exists.
    nowhen = [l for l in allof if (split_line(l)[1] or "") and " for " not in split_line(l)[1]]
    leg("L3 every_line_says_when_to_use_it", not nowhen,
        "%d missing a 'for <when>' clause" % len(nowhen))

    # L4 THE NAMES ARE THE REAL COMPONENTS. A line describing something that is
    # not in the live set is a menu entry for a thing their agent cannot place.
    live = set()
    for fam in ("text overlay", "frame composition", "motion graphic"):
        live |= set(lc.live_set()["by_family"].get(fam) or [])
    named = {split_line(l)[0] for l in d["components"]}
    unknown = sorted(named - live)
    leg("L4 component_lines_name_real_components", not unknown,
        "%d line(s) name something not in the live set: %s"
        % (len(unknown), unknown or "none"))

    # L5 ONE DEFINITION, N HOMES — proven on a fixture, and the REAL state
    # reported beside it. Neither second home exists yet: `description` is
    # write-only on assets and the style-guide index is not written. A leg that
    # passed on that would be asserting nothing.
    def homes_agree(a, b):
        return a is not None and b is not None and a == b
    same = homes_agree("X — y for z", "X — y for z")
    diff = homes_agree("X — y for z", "X — y for z ")   # one trailing space
    homes = d.get("_second_homes") or {}
    leg("L5 byte_identity_rule_discriminates", same and not diff,
        "identical=%s one-space-apart=%s | second homes live today: %s"
        % (same, diff, sorted(homes) or "NONE — description is write-only on "
           "assets and the style-guide index is unwritten"))

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
