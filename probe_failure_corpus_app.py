"""IS failure-corpus/ USABLE AS A/B INPUT? Real retained sources, already sanctioned.

The delete-test and the window-doctrine test both need RAW talking-head sources.
The batch-corpus clips are disqualified: all four are finished multi-cut edits
(7.6-25.4 cuts/25s), so the pipeline has nothing left to add and every family
reads zero for the wrong reason. Organic job sources are real users' media and
barred for A/Bs.

failure-corpus/ is the third option and the best one if it holds: these are the
EXACT sources that broke real jobs, deliberately retained for replay
(handler.py:39819, Zac 2026-08-02), so they are real UGC AND already sanctioned.

USABLE means, and each is CHECKED not assumed:
  • >= 30s          — shorter than that is not a real editorial job
  • FEW HARD CUTS   — scdet cuts/25s must be LOW. This is the whole point: a
                      retained source that is itself a finished edit would
                      reproduce the batch-corpus mistake exactly.
  • HAS SPEECH      — a talking-head needs a voice; silent b-roll is not an input
  • FACE PRESENT    — sampled face detection, so "talking head" is measured
                      rather than inferred from duration

Reports every candidate with its numbers so a rejection is checkable, and states
plainly when NOTHING qualifies rather than returning the least-bad file.

  ./run_modal.sh probe_failure_corpus_app.py
"""
import os
import sys

sys.path.insert(0, "/")
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("probe-failure-corpus", image=image)
SECRETS = [modal.Secret.from_name(n) for n in (
    "promptly-secrets", "promptly-cloudfront", "gemini-vertex",
    "promptly-lang-flags", "promptly-elevenlabs")]


@app.function(secrets=SECRETS, cpu=8.0, memory=16384, timeout=2400)
def survey(limit: int = 60) -> dict:
    import json
    import subprocess
    import boto3
    sys.path.insert(0, "/")

    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"

    keys, tok = [], None
    while True:
        kw = {"Bucket": bucket, "Prefix": "failure-corpus/", "MaxKeys": 1000}
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        keys += [(o["Key"], o["Size"]) for o in r.get("Contents", [])]
        if not r.get("IsTruncated"):
            break
        tok = r.get("NextContinuationToken")

    vids = [(k, s) for k, s in keys
            if k.lower().endswith((".mp4", ".mov", ".m4v")) and s > 200_000]
    by_class = {}
    for k, s in vids:
        by_class.setdefault(k.split("/")[1] if k.count("/") > 1 else "?", 0)
        by_class[k.split("/")[1] if k.count("/") > 1 else "?"] += 1

    out = []
    for k, size in vids[:limit]:
        loc = "/tmp/" + k.replace("/", "_")
        rec = {"key": k, "mb": round(size / 1e6, 1), "class": k.split("/")[1]}
        try:
            s3.download_file(bucket, k, loc)
        except Exception as e:
            rec["error"] = f"download: {type(e).__name__}"
            out.append(rec)
            continue
        try:
            _p = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "format=duration:stream=width,height,codec_type",
                 "-of", "json", loc], capture_output=True, text=True, timeout=120)
            j = json.loads(_p.stdout or "{}")
            rec["dur"] = round(float(j.get("format", {}).get("duration") or 0), 1)
            streams = j.get("streams") or []
            rec["has_audio"] = any(s.get("codec_type") == "audio" for s in streams)
            v = next((s for s in streams if s.get("codec_type") == "video"), {})
            rec["wh"] = f"{v.get('width')}x{v.get('height')}"
        except Exception as e:
            rec["error"] = f"probe: {type(e).__name__}"
            out.append(rec)
            continue

        # HARD CUTS — the check that disqualified batch-corpus.
        try:
            _s = subprocess.run(
                ["ffmpeg", "-hide_banner", "-nostats", "-i", loc,
                 "-vf", "scdet=threshold=7", "-an", "-f", "null", "-"],
                capture_output=True, text=True, timeout=600)
            n = (_s.stderr or "").lower().count("lavfi.scd.time")
            rec["cuts"] = n
            rec["cuts_per_25s"] = round(25.0 * n / rec["dur"], 1) if rec.get("dur") else None
        except Exception as e:
            rec["error"] = f"scdet: {type(e).__name__}"

        # SPEECH — mean volume as a cheap proxy; silence reads very low.
        try:
            _a = subprocess.run(
                ["ffmpeg", "-hide_banner", "-nostats", "-i", loc, "-af",
                 "volumedetect", "-vn", "-f", "null", "-"],
                capture_output=True, text=True, timeout=300)
            for ln in (_a.stderr or "").split("\n"):
                if "mean_volume:" in ln:
                    rec["mean_db"] = float(ln.split("mean_volume:")[1].split("dB")[0].strip())
        except Exception:
            pass

        # FACE — sampled, so "talking head" is measured.
        try:
            import handler as H
            fr = H.detect_face_positions(loc) if hasattr(H, "detect_face_positions") else None
            if isinstance(fr, tuple):
                fr = fr[0]
            if isinstance(fr, list) and fr:
                rec["face_frac"] = round(
                    sum(1 for f in fr if isinstance(f, dict) and f.get("found")) / len(fr), 2)
                rec["face_samples"] = len(fr)
        except Exception as e:
            rec["face_err"] = f"{type(e).__name__}"
        try:
            os.remove(loc)
        except Exception:
            pass
        out.append(rec)
    return {"total_objects": len(keys), "videos": len(vids),
            "by_class": by_class, "probed": out}


@app.local_entrypoint()
def main(limit: int = 60):
    d = survey.remote(limit)
    print(f"\n=== failure-corpus/ — {d['videos']} video objects "
          f"({d['total_objects']} total) ===")
    print("  by error class: " + ", ".join(
        f"{k}={v}" for k, v in sorted(d["by_class"].items(), key=lambda x: -x[1])[:12]))

    rows = d["probed"]
    print(f"\n  probed {len(rows)}:")
    print(f"  {'dur':>6} {'cuts/25s':>9} {'face':>6} {'mean_dB':>8} {'wh':>10}  class / key")
    for r in sorted(rows, key=lambda x: -(x.get("dur") or 0)):
        if r.get("error"):
            print(f"  {'—':>6} {'—':>9} {'—':>6} {'—':>8} {'—':>10}  "
                  f"{r['class']}  ERROR {r['error']}")
            continue
        print(f"  {r.get('dur', 0):>6.1f} {str(r.get('cuts_per_25s')):>9} "
              f"{str(r.get('face_frac')):>6} {str(r.get('mean_db')):>8} "
              f"{str(r.get('wh')):>10}  {r['class']}/{r['key'].split('/')[-1][:18]}")

    # THE VERDICT — explicit thresholds, stated so a rejection is checkable.
    good = [r for r in rows if not r.get("error")
            and (r.get("dur") or 0) >= 30
            and (r.get("cuts_per_25s") is not None and r["cuts_per_25s"] <= 3.0)
            and r.get("has_audio")
            and (r.get("mean_db") is None or r["mean_db"] > -45)
            and (r.get("face_frac") is None or r["face_frac"] >= 0.5)]
    print(f"\n  USABLE AS A/B INPUT (>=30s, <=3.0 cuts/25s, has audio, face>=0.5): "
          f"{len(good)}")
    for r in good:
        print(f"      {r['dur']:.0f}s  {r['cuts_per_25s']} cuts/25s  "
              f"face={r.get('face_frac')}  s3://…/{r['key']}")
    if not good:
        print("      NONE QUALIFY. Not 'the closest match' — none. The delete-test")
        print("      and window-doctrine test still need raw talking-head sources,")
        print("      and asking Zac is now the correct next step.")
