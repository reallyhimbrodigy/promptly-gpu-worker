#!/usr/bin/env python3
"""Run the input-shape corpus and rule each case against its STATED expectation.

The reliability round asks "does the pipeline work". This asks "what does it do
when the input is abnormal", which is a different question and needs a different
verdict vocabulary.

FOUR OUTCOMES, THREE PERMITTED:

    ACCEPT   produced something a user would take
    WRONG    produced something a user would NOT — wrong geometry, a truncated
             stream, a fraction of the source
    LOUD     refused, with a message saying why
    SILENT   crashed, produced nothing, or produced something broken while
             reporting success — THE ONLY FORBIDDEN OUTCOME

SILENT is separated from LOUD deliberately. Both are failures to produce a
video; only one of them tells anybody. Round 43 delivered 9.267s of video
against 30.960s of audio and printed "output: 30.96s 1080x1920 audio=True" — a
SILENT failure that read as success in every field the pipeline emitted, which
is precisely why the vocabulary needs the distinction.

ONE BRIEF FOR EVERY CASE, ON PURPOSE. The variable under test is the INPUT
SHAPE. Tailoring a brief per shape — asking for captions on the silent one,
sound on the short one — would vary two things at once and measure the brief,
which is the mistake the car_mid brief was written to avoid.

  python3 run_input_shapes.py --list
  python3 run_input_shapes.py --cases audio_longer_than_video,hdr_pq [--go]
  python3 run_input_shapes.py --all [--go]

Without --go it prices the run and launches nothing.
"""
import json
import os
import re
import subprocess
import sys

V4 = "ab-sources/input-shapes-v1"
BUCKET = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
OUT = "/tmp/input_shapes_runs"

# NEUTRAL, and the same for every case. It asks for a finished video and names
# no family, so a case cannot fail for being asked something its duration or
# audio cannot carry.
BRIEF = ("Make this into a finished short. Use your judgement about what the "
         "footage can carry — do not force anything the material does not "
         "support.")
MODEL = "claude-haiku-4-5"

# Measured from rounds 43-45 at Haiku's confirmed rates: $0.0247-$0.0964 per
# fixture, median ~$0.035, and cost tracks source duration more than anything.
_COST_PER_S = 0.035 / 20.0


def manifest():
    import boto3
    s3 = boto3.client("s3")
    return json.loads(s3.get_object(Bucket=BUCKET,
                                    Key=f"{V4}/manifest.json")["Body"].read())


def classify(log_text, case):
    """(outcome, evidence) from the run's own log, against the case's expectation.

    READS THE PIPELINE'S OWN VERDICTS rather than re-deriving them — the
    collector learned that lesson when it scraped a hardcoded list of violation
    kinds and missed the two it had never heard of.
    """
    t = log_text or ""
    if not t.strip():
        return "SILENT", "the run produced no log at all"
    crash = re.search(r"(Traceback|UnboundLocalError|NameError|TypeError|"
                      r"AttributeError|ValueError|KeyError|AssertionError|"
                      r"RemoteError)", t)
    got_summary = "RUN SIGNATURE" in t
    # A crash that never reached a summary is SILENT unless the pipeline said
    # something a user could act on.
    if crash and not got_summary:
        refused = re.search(r"(rejected|refus\w+|too short|too long|unsupported|"
                            r"cannot|not supported)", t, re.I)
        return (("LOUD", f"refused: {refused.group(0)}") if refused
                else ("SILENT", f"crashed with no verdict: {crash.group(1)}"))
    if not got_summary:
        return "SILENT", "the run never reached its own summary"

    viol = re.findall(r"^\s+- ([a-z_]+):", t, re.M)
    sl = re.search(r"STREAM LENGTH   : (\w+)", t)
    res = re.search(r"output          : [\d.]+s\s+(\d+)x(\d+)", t)
    cut = re.search(r"kept ([\d.]+)s of ([\d.]+)s \(([\d.]+)\)", t)

    bad = []
    if "video_truncated" in viol or (sl and sl.group(1) == "TRUNCATED"):
        bad.append("video stream shorter than its audio")
    if sl and sl.group(1) == "ABSENT":
        bad.append("stream length UNMEASURABLE")
    if res and (res.group(1), res.group(2)) != ("1080", "1920"):
        bad.append(f"delivered {res.group(1)}x{res.group(2)}")
    if cut and float(cut.group(3)) < 0.25:
        bad.append(f"kept only {float(cut.group(3)):.1%} of the source")
    if "no_output" in viol:
        return "SILENT", "no_output — nothing was produced and it reported a summary"
    if bad:
        return "WRONG", "; ".join(bad)
    return "ACCEPT", (f"kept {cut.group(3)} of source, "
                      f"{res.group(1)}x{res.group(2)}" if cut and res else "clean")


def main():
    argv = sys.argv[1:]
    man = manifest()
    by_case = {m["case"]: m for m in man}
    if "--list" in argv:
        print(f"{len(man)} case(s) in {V4}\n")
        for m in man:
            print(f"  {m['case']:26} {m.get('shape','')[:44]}")
            print(f"  {'':26} EXPECT {m['expect'][:88]}")
        return 0

    if "--all" in argv:
        want = [m["case"] for m in man]
    elif "--cases" in argv:
        want = [c.strip() for c in argv[argv.index("--cases") + 1].split(",")]
    else:
        print(__doc__)
        return 2
    unknown = [c for c in want if c not in by_case]
    if unknown:
        print(f"unknown case(s): {unknown}\nknown: {sorted(by_case)}")
        return 2

    total_s = sum(float(by_case[c].get("duration") or 0) for c in want)
    est = total_s * _COST_PER_S
    print(f"{len(want)} case(s), {total_s:.0f}s of source, "
          f"estimated model cost ${est:.2f} plus {len(want)} container run(s)\n")
    for c in want:
        m = by_case[c]
        print(f"  {c:26} {m.get('duration','?')}s  EXPECT {m['expect'][:66]}")
    if "--go" not in argv:
        print("\n  PRICED ONLY — nothing launched. Add --go to run.")
        return 0

    os.makedirs(OUT, exist_ok=True)
    import boto3
    s3 = boto3.client("s3")
    results = []
    for c in want:
        m = by_case[c]
        key = m["s3_key"]
        src = s3.generate_presigned_url("get_object",
                                        Params={"Bucket": BUCKET, "Key": key},
                                        ExpiresIn=3600)
        ok = f"input-shapes/{c}-out.mp4"
        dst = s3.generate_presigned_url(
            "put_object", Params={"Bucket": BUCKET, "Key": ok,
                                  "ContentType": "video/mp4"}, ExpiresIn=3600)
        log = os.path.join(OUT, f"{c}.log")
        print(f"[run] {c}", flush=True)
        with open(log, "w") as fh:
            subprocess.run(["modal", "run", "--detach", "agentic_editor_app.py",
                            "--source", key, "--brief", BRIEF, "--model", MODEL,
                            "--src-url", src, "--out-url", dst, "--out-key", ok],
                           stdout=fh, stderr=subprocess.STDOUT, timeout=5400)
        outcome, why = classify(open(log, encoding="utf-8",
                                     errors="ignore").read(), m)
        results.append((c, outcome, why, m["expect"]))
        print(f"      -> {outcome}: {why}", flush=True)

    print(f"\n{'case':26} {'outcome':8} evidence")
    counts = {}
    for c, o, why, exp in results:
        counts[o] = counts.get(o, 0) + 1
        print(f"  {c:26} {o:8} {why[:70]}")
        print(f"  {'':26} {'':8} EXPECTED {exp[:70]}")
    print(f"\n  {counts}")
    if counts.get("SILENT"):
        print(f"  {counts['SILENT']} SILENT — the one forbidden outcome")
    return 1 if counts.get("SILENT") else 0


if __name__ == "__main__":
    sys.exit(main())
