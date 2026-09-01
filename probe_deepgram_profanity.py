"""DEEPGRAM profanity_filter PROBE — measure before building.

Zac's ruling is mask-not-omit. Deepgram ships a native `profanity_filter`, and if
it masks server-side it applies to BOTH paths at once with no list to maintain.
Two disqualifying questions, and neither can be answered from the docs:

  1. What does it do to the TEXT — mask, replace with a euphemism, or REMOVE?
  2. Does it move the WORD TIMINGS?

The cutter runs on Deepgram timings at 33ms. Captions are Deepgram-verbatim
precisely BECAUSE the timings are the clock. A filter that drops a word or shifts
a boundary is disqualified no matter how good the masking is.

Same audio, extracted ONCE, transcribed twice. Anything else confounds the
comparison with re-encode differences.
"""
import json
import os

import modal

app = modal.App("probe-dg-profanity")
IMG = (modal.Image.debian_slim(python_version="3.11")
       .apt_install("ffmpeg")
       .pip_install(["deepgram-sdk==3.*", "boto3"]))
SECRETS = [modal.Secret.from_name("promptly-secrets")]
BUCKET = "thisismybucketagainwooo"


@app.function(image=IMG, secrets=SECRETS, timeout=1200, cpu=4, memory=8192)
def probe(source_key: str) -> dict:
    import subprocess
    import boto3
    from deepgram import DeepgramClient, PrerecordedOptions

    os.makedirs("/work", exist_ok=True)
    src = "/work/source.mp4"
    boto3.client("s3").download_file(BUCKET, source_key, src)
    aud = "/work/a.m4a"
    subprocess.run(["ffmpeg", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
                    "-b:a", "64k", aud], capture_output=True, timeout=300)
    blob = open(aud, "rb").read()

    dg = DeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])

    def run(profanity):
        # EXACTLY the production options, plus the one variable under test.
        kw = dict(model="nova-3", language="multi", smart_format=True,
                  punctuate=True, utterances=True, filler_words=True)
        if profanity is not None:
            kw["profanity_filter"] = profanity
        r = dg.listen.prerecorded.v("1").transcribe_file(
            {"buffer": blob}, PrerecordedOptions(**kw))
        d = r.to_dict() if hasattr(r, "to_dict") else json.loads(r.to_json())
        a = d["results"]["channels"][0]["alternatives"][0]
        return [{"w": w["word"], "pw": w.get("punctuated_word", w["word"]),
                 "s": round(w["start"], 3), "e": round(w["end"], 3)}
                for w in (a.get("words") or [])]

    try:
        base = run(None)
    except Exception as e:
        return {"ok": False, "stage": "baseline", "err": str(e)}
    try:
        filt = run(True)
    except Exception as e:
        # A rejected option is itself an answer: the feature is unavailable on
        # this model/plan and the caption-render path is the only route.
        return {"ok": False, "stage": "filtered", "err": str(e),
                "baseline_words": len(base)}

    out = {"ok": True, "baseline_words": len(base), "filtered_words": len(filt),
           "count_equal": len(base) == len(filt)}

    # TEXT DIFFS at matching indices — only meaningful if counts match.
    diffs, timing_shifts, max_shift = [], 0, 0.0
    for i in range(min(len(base), len(filt))):
        b, f = base[i], filt[i]
        if b["w"] != f["w"]:
            diffs.append({"i": i, "base": b["w"], "filtered": f["w"],
                          "base_pw": b["pw"], "filtered_pw": f["pw"]})
        ds, de = abs(b["s"] - f["s"]), abs(b["e"] - f["e"])
        if ds > 0.0005 or de > 0.0005:
            timing_shifts += 1
            max_shift = max(max_shift, ds, de)
    out["text_diffs"] = len(diffs)
    out["sample_diffs"] = diffs[:25]
    out["words_with_shifted_timing"] = timing_shifts
    out["max_timing_shift_s"] = round(max_shift, 4)

    # THE VERDICT, computed here rather than eyeballed later.
    if not out["count_equal"]:
        out["verdict"] = ("DISQUALIFIED — word COUNT changed; the filter adds or "
                          "removes tokens and the cut clock would move")
    elif timing_shifts:
        out["verdict"] = (f"DISQUALIFIED — {timing_shifts} words moved, max "
                          f"{max_shift:.4f}s; timings are the clock")
    elif not diffs:
        out["verdict"] = ("NO-OP — option accepted but changed nothing; either "
                          "unsupported on this model or no profanity detected")
    else:
        masked = sum(1 for d in diffs if "*" in d["filtered"])
        out["masked_with_asterisks"] = masked
        out["verdict"] = (
            f"USABLE — {len(diffs)} words changed, {masked} contain '*', "
            f"0 timing shifts, count identical")
    return out


@app.local_entrypoint()
def main(source: str = "ab-sources/talking-head-v1/625dfdc5-73s.mp4"):
    r = probe.remote(source)
    print("\n" + "=" * 68)
    print("  DEEPGRAM profanity_filter — PROBE")
    print("=" * 68)
    if not r.get("ok"):
        print(f"  FAILED at {r.get('stage')}: {r.get('err')[:300]}")
        return
    print(f"  baseline words        : {r['baseline_words']}")
    print(f"  filtered words        : {r['filtered_words']}   "
          f"(equal={r['count_equal']})")
    print(f"  text diffs            : {r['text_diffs']}")
    print(f"  words w/ moved timing : {r['words_with_shifted_timing']}  "
          f"(max {r['max_timing_shift_s']}s)")
    if r.get("masked_with_asterisks") is not None:
        print(f"  masked with '*'       : {r['masked_with_asterisks']}")
    print(f"\n  VERDICT: {r['verdict']}")
    if r["sample_diffs"]:
        print("\n  sample changes (base -> filtered):")
        for d in r["sample_diffs"][:12]:
            print(f"    [{d['i']:>4}] {d['base']!r} -> {d['filtered']!r}")
