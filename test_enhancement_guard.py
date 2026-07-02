"""Enhancement fail-open (P1b) — behavioral tests.

The guarded blocks live inline in handler(); these tests extract the REAL
wrapped blocks from handler.py source by their marker comments and exec them
with injected failures — the shipped code is what's proven, no reimplementation.
"""
import concurrent.futures
import contextlib
import io
import sys
import textwrap
import time

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

SRC_LINES = open("handler.py").read().split("\n")

def extract_block(marker):
    """Return the dedented try/except block whose try-line carries `marker`."""
    starts = [i for i, l in enumerate(SRC_LINES) if l.strip().startswith("try:") and marker in l]
    assert len(starts) == 1, f"marker not unique: {marker} ({len(starts)})"
    s = starts[0]
    indent = len(SRC_LINES[s]) - len(SRC_LINES[s].lstrip())
    e = s + 1
    seen_except = False
    while e < len(SRC_LINES):
        l = SRC_LINES[e]
        if l.strip():
            li = len(l) - len(l.lstrip())
            if li <= indent and not l.lstrip().startswith(("except", ")")):
                if seen_except:
                    break
            if l.lstrip().startswith("except Exception as _eg_err:") and li == indent:
                seen_except = True
        e += 1
    assert seen_except, f"except not found for {marker}"
    return textwrap.dedent("\n".join(SRC_LINES[s:e]))

def run_block(code, ns):
    ns.setdefault("_enhancement_guard", H._enhancement_guard)
    ns.setdefault("print", print)
    ns.setdefault("concurrent", concurrent)
    ns.setdefault("time", time)
    buf = io.StringIO()
    err = None
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(code, "<wrapped-block>", "exec"), ns)
    except Exception as e:
        err = e
    return err, buf.getvalue(), ns

print("=== E1: guard line format + divergence, grep-stable ===")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    H._enhancement_guard("broll", RuntimeError("x" * 300))
o = buf.getvalue()
check("dropped=<subsystem> err=<type>: <msg[:120]>",
      "[enhancement-guard] dropped=broll err=RuntimeError: " + "x" * 120 in o, o[:160])
check("message truncated at 120", "x" * 121 not in o)
check("divergence recorded", "[divergence]" in o and "drop_enhancement" in o)

print("\n=== E2: b-roll SUBMISSION block (1a72b344's site) — injected glue failure ===")
code = extract_block("P1b fail-open: b-roll submission")
def _boom_tx():
    raise RuntimeError("transcript resolver died mid-glue")
ep = {"broll_clips": [{"keyword": "k"}]}
err, o, ns = run_block(code, {
    "broll_clips": [{"keyword": "k", "start_word_index": 2, "end_word_index": 3,
                     "reason": "r", "duration": 2.0}],
    "edit_plan": ep, "_broll_fetch_pool": None, "_broll_fetch_futures": {},
    "send_progress": lambda *a, **k: None, "job_id": "j", "app_url": "u",
    "_get_resolved_transcript": _boom_tx, "fetch_broll_clip": lambda *a, **k: None,
    "work_dir": "/tmp", "_raw_source": "/x.mp4",
    "_broll_window_context": H._broll_window_context,
    "float": float, "len": len, "min": min, "enumerate": enumerate, "str": str,
    "isinstance": isinstance, "dict": dict,
})
check("block does not raise", err is None, repr(err))
check("guard line", "[enhancement-guard] dropped=broll err=RuntimeError" in o, o[:200])
check("b-roll dropped from plan", ep["broll_clips"] == [] and ns["broll_clips"] == [])
check("pool reset", ns["_broll_fetch_pool"] is None and ns["_broll_fetch_futures"] == {})

print("\n=== E3: b-roll submission — happy path is INERT (futures populated) ===")
ep = {"broll_clips": [{"keyword": "k"}]}
fetched = []
err, o, ns = run_block(code, {
    "broll_clips": [{"keyword": "k", "start_word_index": 2, "end_word_index": 3,
                     "reason": "r", "duration": 2.0}],
    "edit_plan": ep, "_broll_fetch_pool": None, "_broll_fetch_futures": {},
    "send_progress": lambda *a, **k: None, "job_id": "j", "app_url": "u",
    "_get_resolved_transcript": lambda: {"words": [
        {"word": f"w{i}", "start": i * 0.4, "end": i * 0.4 + 0.35} for i in range(10)]},
    "fetch_broll_clip": lambda *a, **k: fetched.append(k) or "/tmp/b.mp4",
    "work_dir": "/tmp", "_raw_source": "/x.mp4",
    "_broll_window_context": H._broll_window_context,
    "float": float, "len": len, "min": min, "enumerate": enumerate, "str": str,
    "isinstance": isinstance, "dict": dict,
})
if ns.get("_broll_fetch_pool"):
    ns["_broll_fetch_pool"].shutdown(wait=True)
check("no raise, no guard lines", err is None and "[enhancement-guard]" not in o, repr(err) + o[:200])
check("one future submitted with picker context",
      len(ns["_broll_fetch_futures"]) == 1 and fetched
      and fetched[0].get("dialogue_text") == "w2 w3"
      and fetched[0].get("source_mid_s") is not None, str(fetched))

print("\n=== E4: b-roll COLLECTION block — prefetch raises -> dropped, job lives ===")
code_c = extract_block("P1b fail-open: b-roll collection")
ep = {"broll_clips": [{"keyword": "k"}]}
def _boom_prefetch(*a, **k):
    raise ValueError("verify pass exploded")
class _P:
    def __init__(self): self.down = False
    def shutdown(self, wait=False): self.down = True
pool = _P()
err, o, ns = run_block(code_c, {
    "_broll_fetch_futures": {"f": 0}, "broll_clips": [{"keyword": "k"}],
    "edit_plan": ep, "_broll_fetch_pool": pool,
    "prefetch_and_verify_broll": _boom_prefetch,
    "isinstance": isinstance, "dict": dict,
})
check("no raise", err is None, repr(err))
check("guard + drop + shutdown",
      "dropped=broll err=ValueError" in o and ep["broll_clips"] == [] and pool.down)

print("\n=== E5: budget-shed block — poisoned duration -> proceeds UNSHED ===")
code_s = extract_block("P1b fail-open: proceed unshed")
ep = {"broll_clips": [{"keyword": "k"}], "generated_scenes": []}
err, o, ns = run_block(code_s, {
    "_pipeline_start": time.time(), "source_duration": None,  # float(None) -> TypeError
    "edit_plan": ep, "_broll_fetch_futures": {"f": 0},
    "broll_clips": [{"keyword": "k"}],
    "max": max, "float": float, "isinstance": isinstance, "dict": dict, "list": list,
})
check("no raise", err is None, repr(err))
check("guard fired, nothing shed",
      "dropped=budget_shed err=TypeError" in o and ep["broll_clips"] == [{"keyword": "k"}])

print("\n=== E6: all seven wrap sites present with expected subsystem names ===")
import re
names = re.findall(r"_enhancement_guard\(\s*['\"]([a-z_]+)['\"]", "\n".join(SRC_LINES))
from collections import Counter
c = Counter(names)
check("subsystem census",
      c == Counter({"broll": 2, "audio_denoise_remediation": 1, "generated_scenes": 1,
                    "budget_shed": 1, "cover_frame": 1, "user_style_profile": 1}), str(c))

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL ENHANCEMENT-GUARD CASES PASS")
