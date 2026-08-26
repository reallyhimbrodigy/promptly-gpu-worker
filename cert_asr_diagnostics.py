#!/usr/bin/env python3
"""EVERY ASR DIVERSION CARRIES THE EVIDENCE FOR ITS OWN VERDICT. `[Rule 1]`

WHAT THIS PREVENTS FROM COMING BACK (2026-08-17)

  On the live worker version, 0 of 60 jobs (0 of 60 users) reached the
  editorial path. 82% of the diversions were ASR-driven — `no_speech`,
  `no_speech_muted`, `no_audio`, `transcription_incomplete`. The routing gate
  is `if len(_dg_words) == 0`, a literal zero, so the gate could only be as
  right as the transcript it was handed.

  Deciding whether those diversions were CORRECT cost a night of downloading
  production sources and re-transcribing them by hand, because a diverted row
  stored exactly this and nothing more:

      "transcript": []

  The word count that drove the gate, and the audio level that produced the
  word count, both died with the container. THE MEASUREMENT HOLE WAS THE
  OUTAGE'S LENGTH — not the bug.

  With the evidence in the row, the same question is one query:

      0 words @ -6.1 dBFS, bass-dominant   -> music, correctly routed
      0 words @ -26 dBFS, speech-dominant  -> a MISS

  Both are already confirmed in production. The miss was a Japanese source a
  replay transcribed (4 words) where production recorded `no_speech`.

WHY AST AND NOT SUBSTRING
  A grep for "asr_diagnostics" passes on this very docstring. Comment- and
  string-matching false PASSES/FAILURES are at 11 instances in this repo; the
  checks below resolve real call sites and real dict keys in the parsed tree.

    python3 cert_asr_diagnostics.py
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HANDLER = os.path.join(HERE, "handler.py")


def _fn(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _calls_in(node):
    """Every function NAME called anywhere inside `node`."""
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                out.append((f.id, n))
            elif isinstance(f, ast.Attribute):
                out.append((f.attr, n))
    return out


def _kwargs_of_calls(node, fname):
    """Keyword names passed to every call of `fname` inside `node`."""
    ks = set()
    for nm, call in _calls_in(node):
        if nm == fname:
            for kw in call.keywords:
                if kw.arg:
                    ks.add(kw.arg)
                else:
                    ks.add("**")          # _asr_diag_set(**_lv)
    return ks


def main():
    src = open(HANDLER).read()
    tree = ast.parse(src)
    fails = []

    # 1. PER-JOB RESET. Modal containers are reused; without this a diverted row
    #    inherits the PREVIOUS job's level and word count — a row that lies with
    #    a plausible number. That is worse than a row that says nothing.
    h = _fn(tree, "handler")
    if h is None:
        fails.append("handler() not found")
    elif "_asr_diag_reset" not in [n for n, _ in _calls_in(h)]:
        fails.append("handler() does not call _asr_diag_reset() — a warm "
                     "container would attribute the previous job's audio to "
                     "this one")

    # 2. THE LEVEL IS MEASURED ON THE BYTES ASR ACTUALLY RECEIVED, not on the
    #    source file — extraction sits between them and is exactly what we had
    #    to exonerate by hand.
    p = _fn(tree, "prepare_audio_for_deepgram")
    if p is None:
        fails.append("prepare_audio_for_deepgram() not found")
    else:
        names = [n for n, _ in _calls_in(p)]
        if "_measure_audio_levels" not in names:
            fails.append("prepare_audio_for_deepgram() does not measure the "
                         "extracted audio's level")
        if "_asr_diag_set" not in names:
            fails.append("prepare_audio_for_deepgram() measures but does not "
                         "record — the number must reach the row")

    # 3. THE WORD COUNT — the exact quantity the gate branches on.
    t = _fn(tree, "transcribe_audio")
    if t is None:
        fails.append("transcribe_audio() not found")
    else:
        ks = _kwargs_of_calls(t, "_asr_diag_set")
        if not ks:
            fails.append("transcribe_audio() never calls _asr_diag_set()")
        elif "word_count" not in ks and "**" not in ks:
            fails.append("transcribe_audio() records no word_count — the gate "
                         "branches on len(_dg_words)==0 and nothing persists it")

    # 4. BOTH PAYLOADS CARRY THE BLOCK. The diverted routes are where the
    #    question gets asked; the editorial payload is the DENOMINATOR — a
    #    diversion rate needs both sides measured the same way.
    #    STATED AS AN INVARIANT, NOT A COUNT. A threshold ("at least 2") passes
    #    when one of four sites is deleted — verified: removing the diverted
    #    payload's block left 3 and the check went green. So the rule is
    #    structural instead: a dict carrying BOTH a transcript and an
    #    edit_recipe IS a result payload, and every one of them must carry the
    #    evidence. (The render-burst RPC payload carries `edit_plan`, not
    #    `edit_recipe`, and is correctly out of scope — it is not a row.)
    n_payload = 0
    for n in ast.walk(tree):
        if not isinstance(n, ast.Dict):
            continue
        keys = {k.value for k in n.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if "transcript" in keys and "edit_recipe" in keys:
            if "asr_diagnostics" not in keys:
                fails.append(f"a result payload at line {n.lineno} records a "
                             f"transcript and an edit_recipe but NO "
                             f"asr_diagnostics — that row cannot justify its "
                             f"own route")
            else:
                n_payload += 1
    if n_payload < 4:
        fails.append(f"only {n_payload} result payloads carry asr_diagnostics; "
                     f"expected the 4 known sites (diverted payload + its "
                     f"durable write, editorial payload + its durable write)")

    # 4b. AND IT SURVIVES THE WRITE THAT KEEPS THE ROW. write_job_status(result=)
    #     is an explicit ALLOWLIST — "the only thing the export gate can read".
    #     A field present on result_payload but absent from the allowlist is
    #     BUILT, NOT WORKING: it never reaches the row, and the query that was
    #     the entire point of this work returns null forever. That exact
    #     omission already swallowed error_subcode and motionTokens here.
    n_durable = 0
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        nm = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
        if nm != "write_job_status":
            continue
        for kw in n.keywords:
            if kw.arg == "result" and isinstance(kw.value, ast.Dict):
                for k in kw.value.keys:
                    if isinstance(k, ast.Constant) and k.value == "asr_diagnostics":
                        n_durable += 1
    if n_durable < 2:
        fails.append(f"asr_diagnostics is in only {n_durable} write_job_status "
                     f"allowlist(s), need >=2 — it would never reach the row "
                     f"(built, not working)")

    # 5. FAILED MEASUREMENT IS NEVER A NUMBER. Reporting a failed probe as a
    #    value is the PROBE COLLAPSE class; it has already produced one false
    #    verdict here. The default must be a status, not a level.
    m = _fn(tree, "_measure_audio_levels")
    if m is None:
        fails.append("_measure_audio_levels() not found")
    else:
        first = None
        for n in ast.walk(m):
            if isinstance(n, ast.Dict):
                for k, v in zip(n.keys, n.values):
                    if isinstance(k, ast.Constant) and k.value == "level_status":
                        first = v if first is None else first
        if first is None:
            fails.append("_measure_audio_levels() has no level_status — a "
                         "failed measurement would be indistinguishable from "
                         "silence")
        elif not (isinstance(first, ast.Constant) and first.value == "failed"):
            fails.append("_measure_audio_levels() does not DEFAULT to "
                         "level_status='failed' — an unmeasured level would "
                         "read as a measured one")

    if fails:
        print("CERT ASR-DIAGNOSTICS: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("CERT ASR-DIAGNOSTICS: PASS")
    print("  handler() resets per job (warm containers cannot cross-attribute)")
    print("  level measured on the bytes ASR received, recorded to the row")
    print("  word_count persisted beside the level that produced it")
    print(f"  asr_diagnostics on {n_payload} payloads (diverted + editorial)")
    print(f"  and in {n_durable} durable write_job_status allowlists — it reaches the ROW")
    print("  a failed measurement records FAILED, never a number")
    return 0


if __name__ == "__main__":
    sys.exit(main())
