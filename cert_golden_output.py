#!/usr/bin/env python3
"""
cert_golden_output.py — OFFLINE golden-output harness cert (LANE 2 / HARNESS).

Zero Modal, zero Gemini, zero network: judges the STORED golden corpus and the
differ against each other. This is the deploy-gate-shaped check; the FULL
harness run (re-planning a candidate through golden_freeze_app.py) costs
Gemini money and is therefore the SEAM lane's pre-flip step, not a deploy gate
— see golden/README.md.

Asserts:
  1. golden/manifest.json loads; >= 20 sources; ids unique; every source
     carries s3_key + sha256 + route_expected (frozen provenance).
  2. Every manifest source has >= 3 stored golden runs that load and are
     capture-kind editorial or light_route (no error tombstones).
  3. harness_plan_diff self-test passes (11 planted defect classes behave —
     the non-vacuity core; a differ that can't go RED is not a gate).
  4. Golden-vs-golden baseline diff is GREEN (the envelope tolerates its own
     variance — no false-alarm floor).
  5. Writes golden/baseline_report.json with the defect-rate number the JUDGE
     lane's scoreboard reads: {"verdict", "defect_rate", "dims_total", ...}.

Run: python3 cert_golden_output.py            (exit 0 pass / 1 fail)
     python3 cert_golden_output.py --quiet
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness_plan_diff as hpd  # noqa: E402

GOLDEN_DIR = os.path.join(HERE, "golden")
MANIFEST = os.path.join(GOLDEN_DIR, "manifest.json")
PLANS = os.path.join(GOLDEN_DIR, "plans")
REPORT = os.path.join(GOLDEN_DIR, "baseline_report.json")

MIN_SOURCES = 20
MIN_RUNS = 3


def main(argv=None):
    quiet = "--quiet" in (argv or sys.argv[1:])

    def say(msg):
        if not quiet:
            print(msg)

    fails = []

    # 1. manifest integrity
    try:
        mf = hpd.load_manifest(MANIFEST)
        n = len(mf["sources"])
        assert n >= MIN_SOURCES, "only %d sources (< %d)" % (n, MIN_SOURCES)
        for s in mf["sources"]:
            for field in ("id", "s3_key", "sha256", "route_expected",
                          "video_url"):
                assert s.get(field), "source %r missing %s" % (
                    s.get("id", "?"), field)
        say("[PASS] manifest: %d sources, provenance complete" % n)
    except Exception as e:
        fails.append("manifest: %s" % e)
        say("[FAIL] manifest: %s" % e)
        mf = None

    # 2. stored golden runs
    golden = {}
    if mf:
        try:
            golden = hpd.load_run_dir(PLANS, mf)
            bad = []
            for s in mf["sources"]:
                runs = golden.get(s["id"], [])
                if len(runs) < MIN_RUNS:
                    bad.append("%s: %d runs" % (s["id"], len(runs)))
                    continue
                kinds = {r["kind"] for r in runs}
                if not kinds <= {"editorial", "light_route"}:
                    bad.append("%s: kinds %s" % (s["id"], sorted(kinds)))
                structural = [f for r in runs
                              for f in r["m"].get("structural_fails", [])]
                if structural:
                    bad.append("%s: %s" % (s["id"], structural[0]))
            assert not bad, "; ".join(bad[:5])
            say("[PASS] goldens: %d sources x >=%d clean runs"
                % (len(golden), MIN_RUNS))
        except Exception as e:
            fails.append("goldens: %s" % e)
            say("[FAIL] goldens: %s" % e)

    # 3. differ non-vacuity self-test
    try:
        hpd.self_test()
        say("[PASS] differ self-test: 11 planted defect classes behave")
    except Exception as e:
        fails.append("self-test: %s" % e)
        say("[FAIL] self-test: %s" % e)

    # 4 + 5. baseline (golden vs golden) must be GREEN; emit the JUDGE feed
    if mf and golden and not fails:
        try:
            env = hpd.build_envelope(golden, mf)
            report = hpd.diff(env, golden, mf)
            report["golden_sources"] = len(golden)
            report["candidate_sources"] = len(golden)
            report["baseline"] = True
            report["frozen_at_commit"] = mf.get("frozen_at_commit")
            with open(REPORT, "w") as f:
                json.dump(report, f, indent=2, sort_keys=True)
                f.write("\n")
            assert report["verdict"] == "GREEN", (
                "baseline not GREEN: %s (first items: %r)"
                % (report["verdict"], report["items"][:3]))
            say("[PASS] baseline GREEN, defect_rate=%.3f over %d dims -> %s"
                % (report["defect_rate"], report["dims_total"],
                   os.path.relpath(REPORT, HERE)))
        except Exception as e:
            fails.append("baseline: %s" % e)
            say("[FAIL] baseline: %s" % e)

    if fails:
        print("cert_golden_output: FAIL (%d)" % len(fails))
        for f in fails:
            print("  - %s" % f)
        return 1
    print("cert_golden_output: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
