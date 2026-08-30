"""CERT — the Lane 3 ingest-bundle contract (RULE-1 check for the relocation).

WHAT IS BEING RELOCATED, so the next reader does not re-derive it: four ingest
tasks (gemini_proxy, loudness, shot_changes, face_detect) move off the cpu=16
orchestrator onto ONE cpu=8 box before the plan, so the planner can floor at
cpu=8 instead of holding 16 cores for ~450s of planner wall that only these
four ever needed.

THE THREE FAILURE CLASSES THIS EXISTS TO MAKE IMPOSSIBLE, each earned:

  1. THE DRIFTING COPY. 15acc4f extracted this exact code, updated ONE of two
     call sites, and killed 17 jobs / 7 users with `__round__`. A relocation
     that COPIES the four closures re-arms that gun with four more triggers.
     C2 asserts every in-process closure DELEGATES to the shared implementation
     and no longer calls the primitive itself — a copy cannot exist to drift.

  2. THE INVISIBLE SECOND CONSUMER. Four separate futures means four return
     shapes, each with consumers nobody grepped for. C4/C5 assert the ONE
     bundle result is read through slice views, so there is no second value
     that can diverge from the first.

  3. THE SILENT EMPTY. An out-parameter arriving empty, a zero-byte proxy, a
     None where a list belongs — none of these raise. Downstream reads the
     empty thing, the plan degrades, and every gate stays green. C6 runs the
     real validator on the real broken values and requires it to PAGE.

WHY NOT A REGEX. A regex reads text; every one of these defects is a SHAPE or a
SCOPE. C2/C3/C9 walk the AST; C4-C7 execute the real functions on real values.

WHAT THIS CERT DOES NOT COVER, stated so it is not mistaken for coverage:
byte-identity of a bundle-path plan against an in-process baseline. That is the
SECOND check and it needs a real job through the real boundary — cert-green is
not deploy-green, and an in-process signature proof says nothing about the
crossing. See the verification job in the session report.

Offline. Zero network, zero Modal, zero Gemini.
"""
import ast
import sys

import handler as H

PASS, FAIL = 0, 0


def ok(label):
    global PASS
    PASS += 1
    print(f"[PASS] {label}")


def bad(label, why):
    global FAIL
    FAIL += 1
    print(f"[FAIL] {label}\n       {why}")


def check(label, fn):
    try:
        fn()
        ok(label)
    except AssertionError as e:
        bad(label, str(e))
    except Exception as e:
        bad(label, f"{type(e).__name__}: {e}")


def pages(label, fn, must_say=None):
    """The value under test MUST raise. A check that cannot fail is not a check."""
    try:
        fn()
    except Exception as e:
        if must_say and must_say.lower() not in str(e).lower():
            bad(label, f"raised, but the message never says {must_say!r}: {e}")
            return
        ok(f"{label} — PAGES: {str(e)[:72]}")
        return
    bad(label, "did NOT raise — a silent empty would reach the 11 consumers")


SRC = open("handler.py").read()
TREE = ast.parse(SRC)
MSRC = open("modal_app.py").read()

# The four relocated tasks: (closure, shared impl, the primitive it must NOT
# call itself any more — that primitive call is what a drifting copy looks like)
FOUR = [
    ("_do_loudness", "_ingest_loudness", "measure_source_loudness"),
    ("_do_shot_changes", "_ingest_shot_changes", "detect_shot_changes"),
    ("_do_gemini_proxy_impl", "_ingest_gemini_proxy", "subprocess"),
    ("_do_face_detect_overlapped", "_ingest_face_detect", "detect_face_positions_dense"),
]


def _fn_node(name):
    for n in ast.walk(TREE):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    raise AssertionError(f"{name} not found in handler.py")


def _called_names(node):
    out = set()
    for t in ast.walk(node):
        if isinstance(t, ast.Call):
            f = t.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
                if isinstance(f.value, ast.Name):
                    out.add(f.value.id)
    return out


print("\n=== C1 — the shared implementations exist at MODULE level ===")
print("    (a closure cannot be called from another container; only these can)")
for _c, impl, _p in FOUR:
    check(f"{impl} is a module-level function",
          lambda impl=impl: (_ for _ in ()).throw(AssertionError(
              f"{impl} missing")) if not any(
              isinstance(n, ast.FunctionDef) and n.name == impl
              for n in TREE.body) else None)

print("\n=== C2 — NO DRIFTING COPY: every closure delegates to the shared impl ===")
print("    (this is the check that would have caught 15acc4f)")
for clo, impl, prim in FOUR:
    def _t(clo=clo, impl=impl, prim=prim):
        n = _fn_node(clo)
        called = _called_names(n)
        assert impl in called, (
            f"{clo} does not call {impl} — it is a COPY, free to drift from the "
            f"code the bundle runs. That is exactly the 15acc4f shape.")
        assert prim not in called, (
            f"{clo} still calls {prim} directly — two implementations of the "
            f"same task now exist, and only one of them will be fixed next time.")
    check(f"{clo} delegates to {impl} (and no longer calls {prim})", _t)

print("\n=== C3 — no out-parameter survives on the shared implementations ===")
print("    (an AST scan of a closure body CANNOT see a callee-side write)")


def _no_outparam():
    n = _fn_node("_ingest_shot_changes")
    args = [a.arg for a in n.args.args] + [a.arg for a in n.args.kwonlyargs]
    for banned in ("out_scores", "scores_out"):
        assert banned not in args, (
            f"_ingest_shot_changes still takes {banned!r} — a dict filled by the "
            f"callee would arrive EMPTY across a container boundary and nothing "
            f"would raise")
    rets = [t for t in ast.walk(n) if isinstance(t, ast.Return)]
    assert rets and all(isinstance(r.value, ast.Tuple) and len(r.value.elts) == 2
                        for r in rets), (
        "_ingest_shot_changes must return an explicit (changes, scores) pair on "
        "every path — the second output must not wear an input's clothes")


check("_ingest_shot_changes takes no out-param and returns an explicit pair",
      _no_outparam)


def _makes_own_dict():
    """The dict handed to the callee must be the SAME OBJECT that is returned.

    A text check ("_scores = {}" appears) is not enough and this is the second
    time that lesson has been paid for: a body can create `_scores = {}`, hand
    the callee a THROWAWAY `{}`, and return the still-empty `_scores`. Every
    downstream read then gets an empty dict, nothing raises, the plan quietly
    degrades — the exact silent-empty this whole contract exists to prevent.
    So: bind the identity, don't grep for the literal.
    """
    n = _fn_node("_ingest_shot_changes")
    calls = [t for t in ast.walk(n) if isinstance(t, ast.Call)
             and isinstance(t.func, ast.Name) and t.func.id == "detect_shot_changes"]
    assert len(calls) == 1, f"expected 1 detect_shot_changes call, found {len(calls)}"
    kw = {k.arg: k.value for k in calls[0].keywords}
    assert "out_scores" in kw, "detect_shot_changes is called without out_scores"
    passed = kw["out_scores"]
    assert isinstance(passed, ast.Name), (
        "out_scores is given a throwaway literal — the callee fills an object "
        "nobody can read, and the returned scores are empty forever")
    name = passed.id

    rets = [t for t in ast.walk(n) if isinstance(t, ast.Return)]
    assert all(isinstance(r.value, ast.Tuple)
               and isinstance(r.value.elts[1], ast.Name)
               and r.value.elts[1].id == name for r in rets), (
        f"the returned scores are not the same object passed as out_scores "
        f"({name!r}) — the second return would always be empty")

    assigns = [t for t in ast.walk(n) if isinstance(t, ast.Assign)
               and any(isinstance(x, ast.Name) and x.id == name for x in t.targets)]
    assert assigns, f"{name} is never assigned in _ingest_shot_changes"
    assert all(isinstance(a.value, ast.Dict) and not a.value.keys for a in assigns), (
        f"{name} is not initialised to a fresh empty dict — it may be a caller's "
        f"object, which is an out-parameter wearing a local's clothes")
    # MAX, not min: one assignment before the call and another after it leaves
    # min() happily passing while the second assignment WIPES every score the
    # callee wrote. Every binding of the name must precede the call.
    assert max(a.lineno for a in assigns) < calls[0].lineno, (
        f"{name} is re-assigned at or after the call that fills it (line "
        f"{max(a.lineno for a in assigns)} vs call at {calls[0].lineno}) — the "
        f"later assignment wipes the callee's writes and the scores are empty")


check("_ingest_shot_changes returns the SAME dict it hands the callee",
      _makes_own_dict)

print("\n=== C4 — the bundle view returns the right slice for each consumer ===")


class _F:
    def __init__(self, v):
        self._v = v

    def result(self, *a):
        return self._v

    def done(self):
        return True


_GOOD = {
    "gemini_proxy": b"x" * 4096,
    "loudness": {"i": -14.0},
    "shot_changes": [1.5, 3.25, 9.0],
    "shot_scores": {"1.5": 8.2},
    "faces_dense": [{"t": 0.0}],
    "faces_smoothed": [{"t": 0.0}, {"t": 1.0}],
}


def _view(keys, label="t", d=None):
    return H._IngestBundleView(_F(_GOOD if d is None else d), keys, label)


check("proxy view returns bytes (single key -> bare value)",
      lambda: (lambda v: (_ for _ in ()).throw(AssertionError(f"got {type(v)}"))
               if not isinstance(v, bytes) else None)(
          _view(("gemini_proxy",)).result()))
check("loudness view returns the dict",
      lambda: (lambda v: (_ for _ in ()).throw(AssertionError(f"got {v!r}"))
               if v != {"i": -14.0} else None)(_view(("loudness",)).result()))


def _pair_shots():
    v = _view(("shot_changes", "shot_scores")).result()
    assert isinstance(v, tuple) and len(v) == 2, f"expected a 2-tuple, got {v!r}"
    changes, scores = v
    H._assert_flat_times("cert: shot_changes via the view", changes)
    assert isinstance(scores, dict), f"scores is {type(scores).__name__}"


check("shot_changes view UNPACKS to (changes, scores) and changes is flat",
      _pair_shots)


def _pair_faces():
    v = _view(("faces_dense", "faces_smoothed")).result()
    assert isinstance(v, tuple) and len(v) == 2, f"expected a 2-tuple, got {v!r}"
    d, s = v
    assert isinstance(d, list) and isinstance(s, list)


check("faces view UNPACKS to (dense, smoothed)", _pair_faces)

print("\n=== C5 — the view PAGES rather than handing back a confident null ===")
pages("view on a missing key",
      lambda: _view(("shot_changes",), "shot_changes", {"loudness": {}}).result(),
      must_say="SILENTLY")
pages("view on a non-dict bundle result",
      lambda: _view(("loudness",), "loudness", ["not", "a", "dict"]).result(),
      must_say="not a dict")

print("\n=== C6 — the boundary validator PAGES on every silent-empty shape ===")
print("    (run on the REAL validator, with the REAL broken values)")
_P = {"want_proxy": True}
check("a well-formed bundle result VALIDATES (the control: the check can pass)",
      lambda: H._ingest_bundle_validate(dict(_GOOD), _P))

pages("shot_changes arriving as the 2-TUPLE (the v584 __round__ shape)",
      lambda: H._ingest_bundle_validate(
          dict(_GOOD, shot_changes=([1.5, 3.0], {"1.5": 8.2})), _P),
      must_say="without unpacking")
pages("shot_scores arriving as a list instead of a dict",
      lambda: H._ingest_bundle_validate(dict(_GOOD, shot_scores=[]), _P),
      must_say="out-parameter")
pages("a ZERO-BYTE proxy (Gemini would plan blindly from a zero-frame video)",
      lambda: H._ingest_bundle_validate(dict(_GOOD, gemini_proxy=b""), _P),
      must_say="empty video")
pages("a proxy that arrives as None",
      lambda: H._ingest_bundle_validate(dict(_GOOD, gemini_proxy=None), _P))
pages("EMPTY loudness (the plan would silently degrade)",
      lambda: H._ingest_bundle_validate(dict(_GOOD, loudness={}), _P),
      must_say="degrade")
pages("faces arriving as None instead of a list",
      lambda: H._ingest_bundle_validate(dict(_GOOD, faces_smoothed=None), _P),
      must_say="expected list")
pages("a far-side failure reported as a far-side failure",
      lambda: H._ingest_bundle_validate(dict(_GOOD, error="boom"), _P),
      must_say="far side")


def _empty_scores_is_legal():
    """RED-PROOF OF THE INVERSE: empty scores must NOT page. The legacy-parse
    path in detect_shot_changes recovers timestamps but no parsable scores and
    leaves out_scores empty ON PURPOSE, so `len(scores)==len(changes)` is not an
    invariant. A validator that paged here would fire on real traffic."""
    H._ingest_bundle_validate(dict(_GOOD, shot_scores={}), _P)


check("EMPTY shot_scores is accepted (legacy-parse path is real, must not page)",
      _empty_scores_is_legal)


def _no_proxy_wanted():
    """want_proxy=False (render_only / _skip_edit_gen): a None proxy is correct."""
    H._ingest_bundle_validate(dict(_GOOD, gemini_proxy=None), {"want_proxy": False})


check("a None proxy is accepted when want_proxy is False (render_only)",
      _no_proxy_wanted)

print("\n=== C7 — the bundle is DARK by default ===")
check("_ingest_bundle_enabled() is False with no flag and no override",
      lambda: (_ for _ in ()).throw(AssertionError(
          "the bundle is ARMED by default — a relocation must ship dark"))
      if H._ingest_bundle_enabled({}) or H._ingest_bundle_enabled(None) else None)
check("the per-job override arms it (so the boundary job needs no traffic flip)",
      lambda: (_ for _ in ()).throw(AssertionError("override does not arm"))
      if not H._ingest_bundle_enabled({"ingest_bundle_test": True}) else None)

print("\n=== C8 — the far side mounts /prewarm and is sized cpu=8 ===")
print("    (61% of jobs hit the proxy cache; unmounted turns each into a re-encode)")
_i = MSRC.index("def ingest_bundle(")
_dec = MSRC[MSRC.rfind("@app.function", 0, _i):_i]
# The BODY lives in the shared _run_ingest_bundle that the cpu=16 verification
# baseline calls too — a second copy of it here would be the very mistake this
# relocation removes. Follow the delegation for the body checks; the DECORATOR
# checks stay pinned to ingest_bundle, because the mount and the cpu= are
# properties of that function and not of the shared body.
_bi = MSRC.index("def _run_ingest_bundle(")
_body = MSRC[_bi:_bi + 7000]
check("ingest_bundle mounts the prewarm volume at /prewarm",
      lambda: (_ for _ in ()).throw(AssertionError(
          "no /prewarm mount — every one of the 61% cache hits becomes a full "
          "480p encode, and the relocation ADDS cost while looking fine"))
      if '"/prewarm": prewarm_volume' not in _dec else None)
check("ingest_bundle is declared cpu=8",
      lambda: (_ for _ in ()).throw(AssertionError(
          f"cpu= is not 8 in: {_dec[:120]!r}"))
      if "cpu=8, memory=" not in _dec else None)
check("ingest_bundle reloads the prewarm volume before reading it",
      lambda: (_ for _ in ()).throw(AssertionError(
          "no prewarm_volume.reload() — a source committed by the prewarm "
          "container is invisible and the cache hit reads as a miss"))
      if "prewarm_volume.reload()" not in _body else None)

print("\n=== C9 — NO LOCAL PATH CROSSES THE BOUNDARY ===")
print("    (the contract rule: artifacts + plain data, never a path/future/out-param)")


def _payload_is_plain():
    i = SRC.index('_timed("ingest_bundle", _ingest_bundle_dispatch)')
    seg = SRC[i:i + 700]
    call = ast.parse("f(" + seg[seg.index("{"):seg.index("})") + 1] + ")").body[0].value
    keys = [k.value for k in call.args[0].keys]
    allowed = {"job_id", "app_url", "dl_bucket", "dl_key", "proxy_video_url",
               "source_duration", "want_proxy"}
    extra = set(keys) - allowed
    assert not extra, (
        f"the bundle payload carries {sorted(extra)} — every crosser must be "
        f"plain data. A work_dir/source path here would be a path that only "
        f"exists on the orchestrator, and the far side would read nothing.")
    for banned in ("work_dir", "source_path", "raw_source", "_raw_source"):
        assert banned not in keys, f"{banned} is a LOCAL PATH and cannot cross"


check("the bundle payload is plain data only (no path, no future, no out-param)",
      _payload_is_plain)


def _far_side_fetches_its_own_source():
    seg = _body
    assert "_prewarm_cached_source_path" in seg and "download_file" in seg, (
        "the far side does not resolve the source itself — if the source is not "
        "fetched there, someone will be tempted to pass a path")
    assert "mkdtemp" in seg, (
        "the far side does not make its own work_dir — the proxy file must live "
        "and die on the box that encodes it")


check("the far side resolves its OWN source and work_dir", _far_side_fetches_its_own_source)


def _no_second_copy_of_the_body():
    """ingest_bundle and the cpu=16 verification baseline must call ONE body.

    Two copies is the exact mistake the relocation removes, and a fixture that
    re-implements the thing under test measures the fixture. Also pins the
    baseline's shape: it must be cpu=16 with /prewarm mounted, or the boundary
    comparison is confounded by a different box AND a different source path,
    and a proxy mismatch could not be attributed to the crossing.
    """
    import ast as _a
    t = _a.parse(MSRC)
    fns = {n.name: n for n in t.body if isinstance(n, _a.FunctionDef)}
    for f in ("ingest_bundle", "ingest_baseline_probe"):
        assert f in fns, f"{f} is missing from modal_app.py"
        called = {c.func.id for c in _a.walk(fns[f])
                  if isinstance(c, _a.Call) and isinstance(c.func, _a.Name)}
        assert "_run_ingest_bundle" in called, (
            f"{f} does not call the shared _run_ingest_bundle — a second copy "
            f"of the ingest body can now drift from the one under test")
    assert fns["ingest_bundle"].decorator_list, (
        "ingest_bundle lost its @app.function decorator — it would vanish from "
        "the deployed app while still existing as a plain Python function")
    bdec = MSRC[MSRC.rfind("@app.function", 0, MSRC.index("def ingest_baseline_probe(")):
                MSRC.index("def ingest_baseline_probe(")]
    assert "cpu=16, memory=" in bdec, (
        "the verification baseline must be cpu=16 — the orchestrator's shape")
    assert '"/prewarm": prewarm_volume' in bdec, (
        "the verification baseline must mount /prewarm too, or the two sides "
        "resolve the source differently and the comparison is confounded")


check("ingest_bundle and the verification baseline share ONE body",
      _no_second_copy_of_the_body)


print(f"\n{'=' * 70}\n  cert_ingest_bundle_contract: {PASS} passed, {FAIL} failed\n{'=' * 70}")
if FAIL:
    print("\n  The relocation is NOT safe to arm. Fix the contract, not the cert.")
sys.exit(1 if FAIL else 0)
