#!/usr/bin/env python3
"""cert_catalog_reaches_model.py — IS THE COMPONENT ACTUALLY TAUGHT, IN CHARACTERS?

THE GAP THIS CLOSES. A component family can be fully wired — module, MG_MAP,
adapter, VALID_MG_TYPES, types.ts, production counter, gate green, sweep says
reachable — and STILL be invisible to the model, because "taught in the prompt"
was only ever asserted from the SOURCE FILE. The catalog text lives inside a
~178,000-character f-string that is then mutated by reorder, dwell-swap,
payoff-swap and (on the v2 path) `_v2_catalog_slice`, which slices the catalog
by CHARACTER OFFSET. Any of those can move, truncate or drop a block, and
nothing downstream would notice: the pipeline does not fail when a component is
never requested. It just quietly renders without it.

So this cert refuses the source file as evidence. It ASSEMBLES the prompt by
calling the same `_build_post_cuts_prompt(...)` the pipeline calls at its one
call site, and then measures the assembled string:

    presence + CHARACTER OFFSET + the FITS:/FIGHTS: lines read back verbatim

CONTROLS, because a search that finds everything proves nothing:

  POSITIVE  StatCard — observed being requested twice by the live model on
            cada6a1b (2026-08-19), so it is known-reachable. If StatCard is not
            found, the PROBE is broken, not the prompt, and the run aborts
            rather than reporting a clean sheet.
  NEGATIVE  a type name that exists nowhere. Must NOT be found. Catches a
            matcher loose enough to "find" anything.

FITS/FIGHTS IS NOT DECORATION. Vibe selection is emergent from those two lines
(component fitness reframe, 59 components) — a catalog entry without them is
listed but not selectable, which is a different and quieter failure than being
absent.

    python3 cert_catalog_reaches_model.py            # both premium arms
"""
import os
import re
import sys

os.environ.setdefault("APP_URL", "")

# The four generation-free compositions (2026-08-19).
FOUR = ["EvidenceCard", "DeviceMockup", "NumberCard", "EmojiCard"]
POSITIVE_CONTROL = "StatCard"
NEGATIVE_CONTROL = "ZzNotARealComponentCard"


def _entry_span(sys_text, name):
    """The catalog entry for `name`: from its bolded header to the next header.

    Anchored on the `**Name**` header the catalog uses, NOT on a bare substring
    — a bare match would hit a passing mention in doctrine and report a
    component as taught when it only appears in prose.
    """
    m = re.search(r"^\*\*" + re.escape(name) + r"\*\*", sys_text, re.M)
    if not m:
        return None, None, None
    start = m.start()
    # Bound at the FIRST of: next bolded header, next blank line, next section.
    # A catalog entry is ONE paragraph. An unbounded span let the last entry in
    # a section run 15,763 chars, which would let a component with no
    # FITS/FIGHTS of its own borrow the next one's and pass.
    tail = sys_text[m.end():]
    ends = [x.start() for x in (
        re.search(r"^\*\*[A-Z][A-Za-z0-9]+\*\*", tail, re.M),
        re.search(r"\n[ \t]*\n", tail),
        re.search(r"^=== ", tail, re.M),
    ) if x]
    end = m.end() + (min(ends) if ends else 1200)
    return start, end, sys_text[start:end]


def _section_of(sys_text, off):
    """The `=== SECTION ===` header this offset falls under.

    PRESENCE IS NOT TEACHING. Measured 2026-08-19: all four compositions were
    present in the assembled prompt with intact FITS/FIGHTS — and requested ZERO
    times on a live render — because they had been appended under
    `=== SEAM TREATMENTS ... AUTHORED IN A DEDICATED PASS ===`, four lines below
    the sentence "You do not emit them here." A motion graphic documented in the
    seam section is a motion graphic the model has been told not to author.
    """
    heads = [m for m in re.finditer(r"^=== (.+?) ===", sys_text, re.M)
             if m.start() < off]
    return heads[-1].group(1) if heads else "<no section>"


def _fits_fights(block):
    fits = re.search(r"FITS:\s*(.+)", block)
    fights = re.search(r"FIGHTS:\s*(.+)", block)
    return (fits.group(1).strip() if fits else None,
            fights.group(1).strip() if fights else None)


def audit(premium):
    import handler as H
    sys_text, _user = H._build_post_cuts_prompt(
        vibe="Make it viral", duration=30.0, premium=premium)
    total = len(sys_text)
    print(f"\n  ── premium={premium}  assembled system_instruction = {total:,} chars")

    # CONTROLS FIRST. A clean sheet from a broken probe is worse than no probe.
    ps, _, pblock = _entry_span(sys_text, POSITIVE_CONTROL)
    if ps is None:
        print(f"  PROBE BROKEN: positive control {POSITIVE_CONTROL} not found in "
              f"{total:,} assembled chars — aborting rather than reporting zeros.")
        return None
    home = _section_of(sys_text, ps)          # where a WORKING MG actually lives
    print(f"  [control +] {POSITIVE_CONTROL:16} found @ char {ps:,} "
          f"({ps / total * 100:.1f}% in)  entry={len(pblock)} chars")
    print(f"              section: {home}   <- the required home for every MG")
    ns, _, _ = _entry_span(sys_text, NEGATIVE_CONTROL)
    if ns is not None:
        print(f"  PROBE BROKEN: negative control {NEGATIVE_CONTROL} 'found' — "
              f"matcher is too loose. Aborting.")
        return None
    print(f"  [control -] {NEGATIVE_CONTROL:16} correctly ABSENT")

    rows, missing = [], []
    for name in FOUR:
        s, e, block = _entry_span(sys_text, name)
        if s is None:
            print(f"  [MISSING ] {name:16} NOT IN THE ASSEMBLED PROMPT")
            missing.append(name)
            rows.append((name, None, None, None))
            continue
        fits, fights = _fits_fights(block)
        sect = _section_of(sys_text, s)
        bad = []
        if not (fits and fights):
            bad.append("fits/fights")
        # The SAME section as the known-reachable control. Not "a plausible
        # section" — the one a motion graphic is emitted from.
        if sect != home:
            bad.append("wrong-section")
        flag = "ok" if not bad else "/".join(bad).upper()
        print(f"  [{flag:12}] {name:16} @ char {s:,} ({s / total * 100:.1f}% in)  "
              f"entry={e - s} chars")
        print(f"                section: {sect}")
        print(f"                FITS:   {fits}")
        print(f"                FIGHTS: {fights}")
        if bad:
            missing.append(f"{name}:{'+'.join(bad)}")
        rows.append((name, s, fits, fights, sect))
    return {"total": total, "rows": rows, "missing": missing}


def main():
    ok = True
    for premium in (True, False):
        r = audit(premium)
        if r is None:
            return 2
        if r["missing"]:
            ok = False
            print(f"  FAIL premium={premium}: {r['missing']}")
    print("\n  " + ("PASS — all four are IN the assembled instruction with "
                    "FITS/FIGHTS, both arms."
                    if ok else "FAIL — see above."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
