# STAGED ADDITION for validate_deploy.py — LANE 2 / HARNESS, via TRUTH's
# merge queue. DO NOT merge until golden/plans/ is frozen (the check fails
# loudly on an unfrozen corpus by design — that is not a bug).
#
# Placement: paste ABOVE the GATE INTEGRITY runner block (validate_deploy.py
# ~L11284) — a @check below the runner is dead code; the integrity counter
# counts "\n@check(" declarations, so pasting this file's single decorated
# check keeps declared == ran.
#
# Zero network, zero Modal: reads only committed files. The FULL harness run
# (candidate re-plan + diff) costs Gemini money and is the SEAM lane's
# pre-flip step, not a deploy-gate check — see golden/README.md.


@check("HARNESS: golden corpus frozen + differ non-vacuous + baseline GREEN")
def _golden_output_harness_wired():
    import importlib
    import os as _os
    import sys as _sys
    _here = _os.path.dirname(_os.path.abspath(__file__))
    if _here not in _sys.path:
        _sys.path.insert(0, _here)
    _hpd = importlib.import_module("harness_plan_diff")

    # corpus present, provenance complete
    _mf = _hpd.load_manifest(_os.path.join(_here, "golden", "manifest.json"))
    assert len(_mf["sources"]) >= 20, "golden corpus below 20 sources"
    for _s in _mf["sources"]:
        assert _s.get("sha256") and _s.get("s3_key"), \
            "source %r missing frozen provenance" % _s.get("id")

    # every source has >= 3 clean frozen runs
    _golden = _hpd.load_run_dir(_os.path.join(_here, "golden", "plans"), _mf)
    _bad = [_s["id"] for _s in _mf["sources"]
            if len(_golden.get(_s["id"], [])) < 3]
    assert not _bad, "sources without 3 frozen runs: %s" % _bad[:5]

    # the differ can actually go RED (11 planted defect classes) — a green
    # harness that has never been red is this project's signature failure
    assert _hpd.self_test()

    # the envelope tolerates its own variance (no false-alarm floor)
    _env = _hpd.build_envelope(_golden, _mf)
    _rep = _hpd.diff(_env, _golden, _mf)
    assert _rep["verdict"] == "GREEN", \
        "golden-vs-golden baseline not GREEN: %r" % (_rep["items"][:3],)
