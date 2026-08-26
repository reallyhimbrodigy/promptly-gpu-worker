#!/usr/bin/env python3
"""cert_dead_air_attrition.py — ONE NUMBER WAS DOING TWO JOBS.

`preserved_silences: []` is the SCHEMA DEFAULT. Alone it cannot distinguish

    the model was asked about N spans and chose to cut them all   (working)
    the model was never asked                                     (inert)

and those point at opposite fixes. detect_dead_air once LOCATED 116 silences
and RETURNED 0 — the model was never asked — and nothing recorded the gap, so
v561's Arabic fix ("an ASR's punctuation habits must not gate a language route")
was UNCONFIRMABLE on real traffic regardless of volume. Measured 2026-08-25:
completion rate 100% pre and 100% post, which is the wrong instrument entirely,
because a passthrough completes.

Three numbers instead of one:

    located   cleared the SILENCE bar, before any linguistic gate
    offered   survived every gate and reached the model
    preserved the model chose to keep

    located > offered   -> a GATE is eating spans          (the Arabic defect)
    offered > 0, preserved == 0 -> the model is deciding   (working as designed)

    python3 cert_dead_air_attrition.py
"""
import ast
import os
import re
import sys

os.environ.setdefault("APP_URL", "")
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "handler.py"), encoding="utf-8").read()
NC = "\n".join(re.sub(r"#.*$", "", ln) for ln in SRC.splitlines())


def enclosing(src, needle):
    ln = src[:src.index(needle)].count("\n") + 1
    best = None
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno <= ln <= (n.end_lineno or 0):
            if best is None or n.lineno > best.lineno:
                best = n
    return best


def main():
    fails = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if not cond and detail else ""))
        if not cond:
            fails.append(name)

    import handler as H

    check("both holders exist", hasattr(H, "_DEAD_AIR_LOCATED") and hasattr(H, "_DEAD_AIR_OFFERED"))

    # LOCATED is counted BEFORE the linguistic gate, or it cannot expose a gate
    # eating spans — which is the entire point.
    i_loc = NC.index("_DEAD_AIR_LOCATED[0] += 1")
    i_gate = NC.index("_sentence_final_word(words[a])")
    check("located is counted BEFORE the linguistic gate", i_loc < i_gate,
          "counted after the gate, so located == offered always and the gap is invisible")

    # ...and AFTER the silence bar, or it counts every gap in the transcript.
    i_sil = NC.index("if silence_in_gap < _WITHIN_CLIP_TRIM_TRIGGER_S:")
    check("located is counted AFTER the silence bar", i_sil < i_loc,
          "would count every word gap, not silences")

    check("offered is set from the list the prompt iterates",
          "_DEAD_AIR_OFFERED[0] = len(_located_silences)" in NC,
          "a separately-derived number can drift from what was shown")

    # SCOPE. The persist site is in handler(); _located_silences lives in
    # generate_edit_gemini. Reading it directly would NameError into a fail-safe.
    fn = enclosing(SRC, '"dead_air_spans_offered"')
    check("the persist site uses the holder, not the out-of-scope local",
          '"dead_air_spans_offered": _DEAD_AIR_OFFERED[0]' in NC,
          f"persist is in {fn.name}(); _located_silences is not in scope there")

    check("both fields are persisted", '"dead_air_spans_located"' in NC and '"dead_air_spans_offered"' in NC)

    # NESTED, not top-level: content-studio strips top-level keys and that
    # already ate gemini_tokens, vad_coverage, _lang_bundle and source_duration.
    i_tl = NC.index('"timeline": _tl_report()')
    i_da = NC.index('"dead_air_spans_located"')
    check("nested beside timeline, not top-level", abs(i_da - i_tl) < 2000,
          "a top-level key is stripped before any reader sees it")

    # RESET PER JOB, or one job's attrition is attributed to the next.
    check("both reset per job at handler entry",
          "_DEAD_AIR_LOCATED[0] = 0" in NC and "_DEAD_AIR_OFFERED[0] = 0" in NC)
    i_reset = NC.index("_DEAD_AIR_LOCATED[0] = 0")
    check("the reset sits beside the component-ledger reset",
          abs(i_reset - NC.index("_component_ledger_reset()", i_reset - 900)) < 900)

    # ── THE THIRD NUMBER, AND THE EXPERIMENT KNOB ──────────────────────────
    check("preserved is persisted as the third number",
          '"dead_air_spans_preserved"' in NC,
          "located->offered alone cannot show the model REJECTING what it is offered")
    check("preserved counts the PARSED set, not the raw list",
          "_DEAD_AIR_PRESERVED[0] = len(_preserved_nums)" in NC,
          "a duplicate or unparseable entry would inflate the count while "
          "changing nothing downstream")
    check("all three reset per job",
          NC.count("_DEAD_AIR_PRESERVED[0] = 0") == 1
          and NC.count("_DEAD_AIR_OFFERED[0] = 0") == 1
          and NC.count("_DEAD_AIR_LOCATED[0] = 0") == 1)

    # THE ARM MUST BE RECORDED ON THE ROW. Modal mounts secrets at CONTAINER
    # START, so after a flip production runs BOTH arms at once and a cut by
    # timestamp is a mixture — the exact confound that made the fps read
    # unreadable until it was re-cut by the persisted arm.
    check("the stall value in force is persisted per job",
          '"midsentence_stall_s": _midsentence_stall_s()' in NC,
          "a cohort could only be cut by clock, which is a mixture not a cohort")

    check("the knob is DARK by default", "_MIDSENTENCE_STALL_S = 0.70" in NC
          and 'PROMPTLY_MIDSENTENCE_STALL_S' in NC)

    # SCOPED TO THE TWO SITES THAT ARE THE SAME DECISION. The detector's offer
    # gate and the downstream trim filter re-apply an identical test; moving
    # only the first would raise `offered` while the cut never happened, and the
    # experiment would read as a null. The connector-word rule (dead air on BOTH
    # sides) is a DIFFERENT question and must stay fixed, or the arms differ in
    # more than one way and nothing is interpretable.
    # EXACT TEXT, NOT A COUNT. The first cut of this check counted occurrences
    # and failed on correct code: `re.sub(r"#.*$")` strips comments but NOT
    # DOCSTRINGS, so two lines of prose naming the constant counted as reads.
    # A count over a body it cannot parse is the instrument being wrong about
    # the code — the exact class this session keeps paying for.
    check("gate site 1: the detector's offer gate reads the knob",
          "and silence_in_gap < _midsentence_stall_s()" in NC,
          "located -> offered would not move with the arm")
    check("gate site 2: the downstream trim filter reads the same knob",
          "and (_tb4 - _ta4) < _midsentence_stall_s()" in NC,
          "offered would rise while the cut still never happened — the "
          "experiment would read as a null for a wiring reason")
    n_knob = NC.count("_midsentence_stall_s()")
    check("the knob is read NOWHERE ELSE",
          n_knob == 4,   # def + 2 gate sites + the per-job persist
          f"{n_knob} reads; expected 4 (def, 2 gates, persist)")

    # THE CONNECTOR-WORD RULE IS A DIFFERENT QUESTION and must stay on the fixed
    # constant, or the arms differ in two ways at once and nothing is readable.
    check("the both-sides connector rule still uses the FIXED constant",
          "and (silence_before_s or 0.0) >= _MIDSENTENCE_STALL_S" in NC
          and "and (silence_after_s or 0.0) >= _MIDSENTENCE_STALL_S" in NC,
          "the both-sides rule moved with the experiment")

    # ── A SPLIT, NOT A FLIP ────────────────────────────────────────────────
    # Reading the env var directly gives ONE value per container, so arming it
    # puts 100% of traffic on the arm — a before/after against yesterday. The
    # only concurrency that yields is the warm/cold container mixture after a
    # flip, and container age correlates with load and time of day. That is the
    # confound that made the proxy-fps read AGREE with its own prediction
    # (-34.3% vs -36% predicted) while being pure noise.
    check("the arm is a per-job SPLIT keyed on job_id",
          "def _resolve_stall_arm(job_id" in NC
          and "sha256(str(job_id).encode(" in NC,
          "a single env read is a flip, not a split — both arms cannot run "
          "concurrently and the comparison is temporal")
    check("resolved ONCE per job, beside the other per-job resets",
          NC.count("_STALL_ARM[0] = _resolve_stall_arm(") == 1,
          "resolved more than once, or never — a mid-job change would split one "
          "job's spans across both arms")
    check("the gate sites read the RESOLVED arm, not the env",
          "return _STALL_ARM[0]" in NC
          and NC.count('os.environ.get("PROMPTLY_MIDSENTENCE_STALL_S"') == 1,
          "more than one reader of the env — the two gate sites could disagree "
          "within a single job")
    # DETERMINISTIC. A retried job that changed arms would attribute one job's
    # spans to BOTH arms and quietly break the per-user cut (Rule 7).
    check("assignment is deterministic — no randomness in the arm",
          "random" not in NC.split("def _resolve_stall_arm")[1].split("def ")[0],
          "a retry would flip arms and contaminate both")
    check("an unidentifiable job goes to CONTROL",
          "if not raw or not job_id:" in NC,
          "a job we cannot attribute must never enter the experimental arm")

    print()
    if fails:
        print(f"  CERT DEAD-AIR-ATTRITION: FAIL ({len(fails)})")
        return 1
    print("  NOTE: asserts the WRITE. That located>offered actually EXPOSES a gate")
    print("  is proven by an Arabic job on real traffic, not by this file.")
    print("  CERT DEAD-AIR-ATTRITION: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
