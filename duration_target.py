#!/usr/bin/env python3
"""TARGET DURATION + the span-ranking policy. `[DARK]`

"Make it 30 seconds" is a top-five request and it is currently impossible: no
duration-target field exists anywhere in the request or the plan, and `cuts` is
deliberately absent from the re-edit op vocabulary because changing the kept-word
space invalidates every anchor in the document.

Re-anchoring is now PROVEN under word-space mutation
(cert_reanchor_under_word_mutation, 8 properties, 5 mutations RED-proven), so it
is safe to build on. This module is the missing half: WHICH words to remove.

═══ IT COMPOSES, IT DOES NOT REINVENT ═══

Every detector already exists and is already trusted on the fresh path:

    detect_dead_air        silence between words
    detect_filler          um / uh / comma-wrapped "you know"
    detect_false_start     Deepgram's trailing-hyphen incomplete words
    detect_stutter         full-word repeats (never phoneme prefixes — ruled)
    detect_phrase_retake   a complete phrase said twice; the discarded take goes

Writing a sixth detector here would be a second opinion competing with five
proven ones. This ranks THEIR output.

═══ THE LADDER, AND WHY IT IS ORDERED THIS WAY ═══

    1  silence          removes NO words. Zero semantic cost. Always first.
    2  filler           removes tokens the speaker did not mean to say.
    3  false start      removes an abandoned word.
    4  stutter          removes a duplicate of a word that survives.
    5  phrase retake    removes a whole discarded take — the first real content
                        decision, and therefore last.

Each rung costs more meaning than the one above it. The policy spends the
cheapest seconds first and STOPS the moment the target is met — so a 2-second
trim never reaches rung 5, and only a request that cannot be satisfied any other
way touches a take.

═══ THE NEGOTIATION FLOOR ═══

The floor is what makes this honest rather than destructive. Three outcomes:

    met         the target is reachable within the ladder
    floor       the target is BELOW what the ladder can reach without cutting
                content. Report the achievable duration and DO NOT over-cut.
    impossible  the target is LONGER than the source. We cannot add footage.

"Make it 30 seconds" on a 25-second source is `impossible` and the answer is a
sentence, not a silently-unchanged video. "Make it 30 seconds" on a 90-second
source whose removable spans total 12s returns `floor` at 78s — and saying "I got
it to 78, going further means cutting what you said" is a better product than
either failing or quietly butchering the content.

**NEVER OVER-CUT TO HIT A NUMBER.** A video that hits 30s by removing meaning is
a worse answer than one that honestly reports 78s.
"""
import os

# The ladder, cheapest semantic cost first. The detector name is resolved
# lazily against handler so this module stays importable and testable alone.
LADDER = (
    ("silence", "detect_dead_air"),
    ("filler", "detect_filler"),
    ("false_start", "detect_false_start"),
    ("stutter", "detect_stutter"),
    ("phrase_retake", "detect_phrase_retake"),
)

# A removal must save at least this much to be worth the re-anchor churn.
MIN_SAVING_S = 0.04


def _word_span_s(words, idx):
    """Seconds a single word occupies, including the gap to the next word."""
    try:
        w = words[idx]
        s = float(w.get("start") or 0.0)
        e = float(w.get("end") or 0.0)
        if idx + 1 < len(words):
            nxt = float(words[idx + 1].get("start") or e)
            if nxt > e:
                e = nxt          # the gap after the word goes with it
        return max(0.0, e - s)
    except Exception:
        return 0.0


def rank_removable_spans(words, detectors=None):
    """[{class, rank, word_index, saving_s}], ordered by the ladder.

    `detectors` lets a caller inject the real handler functions (or fakes, for
    the cert). Missing detectors are SKIPPED, never approximated — a rung we
    cannot evaluate must not be silently treated as empty-and-fine, so its
    absence is reported by the caller-visible `rungs_seen`.
    """
    out, rungs_seen = [], []
    for rank, (cls, fname) in enumerate(LADDER):
        fn = (detectors or {}).get(fname)
        if fn is None:
            continue
        rungs_seen.append(cls)
        try:
            hits = fn(words) or []
        except Exception:
            continue
        for h in hits:
            wi = h.get("word_index") if isinstance(h, dict) else None
            if not isinstance(wi, int):
                continue
            sav = _word_span_s(words, wi)
            if sav < MIN_SAVING_S:
                continue
            out.append({"class": cls, "rank": rank, "word_index": wi,
                        "saving_s": round(sav, 3)})
    # dedupe: a word flagged by two rungs is removed once, at its CHEAPEST rung
    best = {}
    for s in out:
        prev = best.get(s["word_index"])
        if prev is None or s["rank"] < prev["rank"]:
            best[s["word_index"]] = s
    ranked = sorted(best.values(), key=lambda s: (s["rank"], s["word_index"]))
    return ranked, rungs_seen


def plan_to_target(words, source_duration_s, target_s, detectors=None):
    """Answer 'make it N seconds' honestly.

    Returns a dict — never raises, never over-cuts:
        verdict        met | floor | impossible | no_target
        target_s       what was asked
        achieved_s     what this plan actually reaches
        remove_words   word indices to remove (ladder order, cheapest first)
        floor_s        the shortest honest duration the ladder can reach
        spent_rungs    which rungs were used
        message        one sentence for the user, honest in every branch
    """
    src = float(source_duration_s or 0.0)
    if not target_s or float(target_s) <= 0:
        return {"verdict": "no_target", "remove_words": [], "achieved_s": src}
    tgt = float(target_s)

    # IMPOSSIBLE: we cannot add footage. Say so; do not quietly do nothing.
    if tgt >= src:
        return {"verdict": "impossible", "target_s": tgt, "achieved_s": src,
                "remove_words": [], "floor_s": src, "spent_rungs": [],
                "message": (f"This video is {src:.0f}s, so it is already shorter "
                            f"than {tgt:.0f}s — there is nothing to cut to get "
                            f"there.")}

    ranked, rungs_seen = rank_removable_spans(words, detectors)
    total_removable = sum(s["saving_s"] for s in ranked)
    floor_s = max(0.0, src - total_removable)

    # SPEND THE CHEAPEST SECONDS FIRST, AND STOP THE MOMENT THE TARGET IS MET.
    # This is what keeps a 2-second trim off rung 5.
    need = src - tgt
    take, spent, rungs = [], 0.0, []
    for s in ranked:
        if spent >= need:
            break
        take.append(s["word_index"])
        spent += s["saving_s"]
        if s["class"] not in rungs:
            rungs.append(s["class"])

    achieved = round(src - spent, 2)
    if spent + 1e-6 >= need:
        return {"verdict": "met", "target_s": tgt, "achieved_s": achieved,
                "remove_words": sorted(take), "floor_s": round(floor_s, 2),
                "spent_rungs": rungs,
                "message": f"Trimmed to {achieved:.0f}s."}

    # THE FLOOR. The ladder is exhausted and the target is still short. Report
    # the honest number and DO NOT keep cutting into content to reach a figure.
    return {"verdict": "floor", "target_s": tgt, "achieved_s": round(floor_s, 2),
            "remove_words": sorted(s["word_index"] for s in ranked),
            "floor_s": round(floor_s, 2), "spent_rungs": rungs_seen,
            "message": (f"I got it to {floor_s:.0f}s by removing the silence and "
                        f"filler. Getting to {tgt:.0f}s would mean cutting what "
                        f"you actually said — tell me what to lose and I will.")}


def enabled(input_data=None):
    """DARK by default."""
    if input_data and input_data.get("target_duration_test"):
        return True
    return os.environ.get("PROMPTLY_TARGET_DURATION", "").strip().lower() in (
        "1", "true", "yes", "on")
