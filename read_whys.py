#!/usr/bin/env python3
"""THE REASONS, VERBATIM — what the agent said it was doing and why.

  python3 read_whys.py 52            every ruling's `why`, per fixture
  python3 read_whys.py 51 52         the same fixtures, both rounds, side by side

THE BEAT'S OWN TEXT IS PRINTED ABOVE ITS REASON, and that is the point of
this reader. The failure to look for is not a bad reason, it is a FLUENT one:
a why that borrows the documents' vocabulary — "the claim needs its visual
proof" — on a beat where nobody made a claim. That is worse than "high motion,
zoom punches it", because it reads as craft and is not, and it is invisible
unless the beat and the reason are side by side. Source-to-output comparison
is the only thing that sees it; a step-to-step diff passes it honestly.

WHY VERBATIM AND NOT SCORED. The question is whether the reasons show an agent
reasoning from the craft documents or from nothing, and that is a reading, not
a number. Any lexical score I invent here would be the corpus mined into a
rate all over again — the exact move these documents exist to undo. So the
text is printed whole and a human reads it.

The one mechanical signal, and it is labelled as weak: whether a reason ties
its choice to a PROPERTY OF THE MOMENT ("after the claim", "because the number
lands here") or names a CATEGORY and stops ("Hook.", "adds variety"). It is
printed as a count of reasons carrying a linking construction, next to the
total. It is an indicator, not a verdict, and a reason can be excellent
without one.
"""
import glob
import json
import os
import re
import sys

# VOCABULARY THAT PRESUPPOSES SPEECH. Flagged — never failed — when it lands
# on a beat whose SAID is empty. This is the fluent failure in its mechanical
# form: a why that says "the claim needs its proof" on a beat where nobody
# claimed anything reads as craft and is not. It is a FLAG because it can be
# legitimately right (a why may refer to the video's overall claim from a
# silent beat), so it prints the beat's SAID beside it and a person rules.
# "[visual] motion 0.72" IS NOT SPEECH. The first version tested `not said`
# and fired on nothing, because a visual-route beat's text is not empty — it
# is a synthetic marker. A guard that only checks emptiness was blind to the
# exact case it was built for, and it read as a clean zero.
VISUAL_ONLY = re.compile(r"^\[visual\][^A-Za-z]*(motion|shot change|"
                         r"[\d.\s\u00b7]|$)*$", re.I)


def no_speech(said: str) -> bool:
    s = (said or "").strip()
    if not s:
        return True
    return bool(s.startswith("[visual]") and VISUAL_ONLY.match(s))


# THE SECOND SLIP CLASS, found on car_short in round 52: a why that uses the
# documents' vocabulary AGAINST the beat's own annotation. The harness wrote
# "[no narration] 5.7s of footage before the first word — visible content, not
# dead air"; the ruling said "5.7s of pre-speech setup is dead air" and cut
# 5.68s of a 10.0s source. That is not a taste call the documents licensed —
# the beat had already answered the question and the ruling overrode the
# answer. Mechanical and exact: the phrase is in both texts, negated in one.
CONTRADICTIONS = ((re.compile(r"not dead air", re.I),
                   re.compile(r"\bis dead air\b|\bdead air\b", re.I),
                   "the beat says NOT dead air; the ruling calls it dead air"),)

# 'state' IS NOT A SPEECH WORD. The first list matched "states?" and every one
# of screen_recording's flags in three rounds was "static state" / "typing
# state" — a UI description, not a claim. Five flags, one regex, zero slips.
# The counts I reported for that fixture were the regex, not the agent. Kept:
# only words that presuppose somebody SPOKE.
SPEECH_WORDS = re.compile(
    r"\b(claims?|claimed|says?|said|speaker|narrator|narration|spoken|"
    r"assertion|asserts?|sentence|voice|delivers? the line|"
    r"states? that|the words)\b", re.I)

LINK = re.compile(
    r"\b(because|so that|so the|so it|after the|before the|while the|"
    r"rather than|instead of|which is why|when the|as the|lands on|"
    r"holds on|leaves? the|gives? the|earns?|proves?|answers?)\b", re.I)


def whys(round_no):
    out = {}
    for f in sorted(glob.glob(f"/tmp/fixtures/round{round_no}/*.result.json")):
        name = os.path.basename(f).replace(".result.json", "")
        try:
            led = (json.load(open(f)).get("ledger")
                   or json.load(open(f)))
        except Exception as e:                                    # noqa: BLE001
            out[name] = ("UNREADABLE", str(e)[:80], [])
            continue
        bv = led.get("beat_verdicts")
        beats = {b.get("i"): b for b in (led.get("beats") or [])}
        if bv is None:
            out[name] = ("ABSENT", "no beat_verdicts in the ledger", [], {})
        elif not bv:
            out[name] = ("EMPTY", "beat_verdicts is an empty list", [], {})
        else:
            # A RULING WITH NO BEAT BEHIND IT is not a tidy zero either.
            orphans = [b.get("beat") for b in bv
                       if b.get("beat") not in beats]
            det = f"{len(bv)} rulings"
            if orphans:
                det += (f"  *** {len(orphans)} ruling(s) name a beat that is "
                        f"not in the ledger: {orphans[:6]}")
            out[name] = ("MEASURED", det, bv, beats)
    return out


def show(round_no, data):
    print("=" * 78)
    print(f"ROUND {round_no}")
    print("=" * 78)
    for name, (state, detail, bv, beats) in data.items():
        linked = sum(1 for b in bv if LINK.search(b.get("why") or ""))
        slips = contras = 0
        for b in bv:
            src = beats.get(b.get("beat")) or {}
            raw, vis = (src.get("text") or "").strip(), \
                (src.get("vision") or "").strip()
            sd = raw[:-len(vis)].rstrip(" \u00b7").strip() \
                if vis and raw.endswith(vis) else raw
            w = b.get("why") or ""
            if no_speech(sd) and SPEECH_WORDS.search(w):
                slips += 1
            for beat_pat, why_pat, _m in CONTRADICTIONS:
                if beat_pat.search(sd) and why_pat.search(w):
                    contras += 1
        print(f"\n--- {name}  [{state}] {detail}"
              + (f"  ({linked} of {len(bv)} reasons tie the choice to a "
                 f"property of the moment — weak indicator)" if bv else "")
              + (f"  [{slips} SPEECH-VOCAB FLAG(S) on silent beats]"
                 if slips else "")
              + (f"  [{contras} RULING(S) CONTRADICT THE BEAT]"
                 if contras else ""))
        for b in bv:
            fam = ",".join(b.get("treatment") or []) or "-"
            src = beats.get(b.get("beat")) or {}
            # SAID AND SEEN ARE DIFFERENT QUESTIONS and `text` carries both,
            # joined by " · ". My first version printed `vision` alone, which
            # hides the transcript — and would have made every why that
            # mentions a claim look unmoored from a beat that in fact contains
            # one. That is a manufactured finding, the same class as the
            # instrument failures this reader exists to catch.
            raw = (src.get("text") or "").strip()
            vis = (src.get("vision") or "").strip()
            said = raw
            if vis and raw.endswith(vis):
                said = raw[:-len(vis)].rstrip(" ·").strip()
            t = (f"{src.get('t_start', 0):.1f}-{src.get('t_end', 0):.1f}s"
                 if src else "NO BEAT")
            print(f"\n  [{b.get('beat')}] {t:>12s}")
            print(f"       SAID: {said[:160] or '(nothing — no speech here)'}")
            print(f"       SEEN: {vis[:160] or '(no vision description)'}")
            print(f"       {fam:22s} WHY: {b.get('why') or '(NO WHY)'}")
            why = b.get("why") or ""
            for beat_pat, why_pat, msg in CONTRADICTIONS:
                if beat_pat.search(said) and why_pat.search(why):
                    print(f"       *** CONTRADICTS THE BEAT: {msg}")
            if no_speech(said) and SPEECH_WORDS.search(why):
                hit = SPEECH_WORDS.search(why).group(0)
                print(f"       *** SPEECH VOCABULARY ON A SILENT BEAT: "
                      f"{hit!r} — SAID is {said or '(empty)'!r}, nothing was "
                      f"spoken here. Read it.")


def main():
    rounds = [a for a in sys.argv[1:] if a.isdigit()]
    if not rounds:
        sys.stderr.write(__doc__)
        return 2
    for r in rounds:
        d = whys(r)
        if not d:
            print(f"ROUND {r}: no result files")
            continue
        show(r, d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
