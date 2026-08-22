#!/usr/bin/env python3
"""cert_model_attributed.py — EVERY JOB MUST NAME THE MODEL THAT MADE IT.

MEASURED 2026-08-22: 48 of 48 editorial jobs carried NO gemini model string
anywhere in their envelope. The only site that emitted one was
_analysis_stamp(), which rides `analysis_data` — and analysis_data is None on
most jobs, so in practice the model was never persisted.

WHY THIS IS NOT COSMETIC. Reading the SOURCE gives the wrong answer:

    GEMINI_EDITORIAL_MODEL defaults to "gemini-3.1-pro-preview"
    PROMPTLY_EDITORIAL_MODEL in the secret overrides it to "gemini-3.7-flash"

Those differ by roughly an order of magnitude in input price. A cost model built
from the default is wrong by that ratio — which is exactly how the L1/L2 ranking
came out 6-8x too large — and a model swap could never be attributed to a cohort
afterwards. Same class as the component ledger the slow jobs erased and the
timeline the burst container threw away: the fact existed, nothing wrote it down.

  1  editorial_model is persisted, and it reads the OVERRIDABLE constant, not a
     hardcoded string. A literal would be right today and silently wrong the
     hour someone flips the secret — which is the failure this closes.
  2  It is NESTED with timeline/gemini_tokens, not top-level. content-studio
     strips top-level keys, and that strip already ate gemini_tokens,
     vad_coverage, _lang_bundle and source_duration.
  3  The env override actually reaches the constant, so a secret flip is
     REFLECTED rather than merely accepted.
  4  utility_model is persisted too — the two tiers differ, and a bill split
     between them cannot be reconstructed from one of them.

    python3 cert_model_attributed.py
"""
import os
import re
import sys

os.environ.setdefault("APP_URL", "")
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    fails = []
    raw = open(os.path.join(HERE, "handler.py"), encoding="utf-8").read()
    src = "\n".join(re.sub(r"#.*$", "", ln) for ln in raw.splitlines())

    # ── 1: persisted, from the CONSTANT ────────────────────────────────────
    # Matches a bare identifier OR a quoted literal, so the two failure modes
    # report DIFFERENTLY. The first cut only matched identifiers, so writing a
    # hardcoded string produced "not persisted" — which is false and would send
    # the next reader looking for a missing write instead of a wrong one.
    present = re.search(r'"editorial_model"\s*:\s*("?[\w.\-]+"?)', src)
    m = re.search(r'"editorial_model"\s*:\s*([A-Za-z_][\w.]*)\s*,', src)
    print(f"  [1] editorial_model persisted from: "
          f"{(m.group(1) if m else (present.group(1) if present else None))}")
    if not present:
        fails.append("editorial_model is not persisted — no job records which "
                     "brain made it, so a model swap cannot be attributed")
    elif not m:
        fails.append(f"editorial_model is written from a LITERAL "
                     f"({present.group(1)}), not the overridable constant — it "
                     f"is right today and silently wrong the hour the secret "
                     f"flips, which is the exact failure this closes")
    m2 = re.search(r'"utility_model"\s*:\s*([A-Za-z_][\w.]*)', src)
    print(f"  [4] utility_model persisted from  : {m2.group(1) if m2 else None}")
    if not m2 or m2.group(1) != "GEMINI_MODEL":
        fails.append("utility_model is not persisted from GEMINI_MODEL — a bill "
                     "split across two tiers cannot be reconstructed from one")

    # ── 2: nested, not top-level ───────────────────────────────────────────
    i_model = src.find('"editorial_model"')
    i_tl = src.find('"timeline": _tl_report()')
    i_tok = src.find('"gemini_tokens"')
    near = i_model > 0 and i_tl > 0 and abs(i_model - i_tl) < 8000
    print(f"  [2] nested with timeline/gemini_tokens: {near}")
    if not near:
        fails.append("editorial_model is not nested beside timeline — a "
                     "top-level key is stripped by content-studio, the class "
                     "that already hid five other fields")

    # ── 3: the override actually reaches the constant ──────────────────────
    # Drive the real module twice: default, then with the env set.
    import importlib
    import handler as H
    before = H.GEMINI_EDITORIAL_MODEL
    os.environ["PROMPTLY_EDITORIAL_MODEL"] = "gemini-test-sentinel"
    H2 = importlib.reload(H)
    after = H2.GEMINI_EDITORIAL_MODEL
    os.environ.pop("PROMPTLY_EDITORIAL_MODEL", None)
    importlib.reload(H2)
    print(f"  [3] env override reaches the constant: {before!r} -> {after!r}")
    if after != "gemini-test-sentinel":
        fails.append(f"PROMPTLY_EDITORIAL_MODEL did not reach the constant "
                     f"(got {after!r}) — the secret that selects the model in "
                     f"production would be inert, and the persisted value would "
                     f"be a lie about which brain ran")

    # The canonical mirrors must agree on what production is actually using —
    # this is the value the persisted field will report.
    mm = re.search(r'"PROMPTLY_EDITORIAL_MODEL"\s*:\s*"([^"]+)"',
                   open(os.path.join(HERE, "modal_app.py"), encoding="utf-8").read())
    vv = re.search(r'"PROMPTLY_EDITORIAL_MODEL"\s*:\s*"([^"]+)"',
                   open(os.path.join(HERE, "validate_deploy.py"), encoding="utf-8").read())
    print(f"      canonical mirrors: modal_app={mm.group(1) if mm else None!r} "
          f"validate_deploy={vv.group(1) if vv else None!r}")
    if not mm or not vv or mm.group(1) != vv.group(1):
        fails.append("the two canonical mirrors disagree on "
                     "PROMPTLY_EDITORIAL_MODEL — the flag-drift sentinel's own "
                     "failure mode, and the persisted model would be unverifiable")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT MODEL-ATTRIBUTED: FAIL")
        return 1
    print("  NOTE: asserts the WRITE. That production rows actually carry it is "
          "proven by reading stage_timings.editorial_model on a real job.")
    print("  CERT MODEL-ATTRIBUTED: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
