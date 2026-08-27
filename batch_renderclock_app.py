"""FORCED RENDER BATCH — RENDERCLOCK curve x offthread arm. PRICED: ~$0.84-1.20.

WHY FORCED, NOT ORGANIC. 155 makers/day split across two live experiments does
not produce a readable duration curve today, and `preserved=1 in both arms` is a
SAMPLING problem rather than a traffic problem. The per-job overrides
(offthread_test / stall_test) exist so a batch can AIM at an arm instead of
hoping the hash cooperates.

THE READ IS A CURVE, NOT A VERDICT. Fixed overhead does not scale with clip
length, so a 20s leg can read stitch- or frames-dominant for reasons that wash
out by 120s. Three durations; no single leg decides it.

WHAT THE SPLIT DECIDES (stated before the run, so it cannot be fitted after):
  stitch_ms dominant                  -> NVENC (B.2) is the lever; the GPU
                                         re-run is worth its $0.50, DECOMPOSED.
  frames_ms dominant                  -> does NOT reopen B.1 (settled dead:
                                         Vulkan unrecoverable, angle-egl never
                                         verified). ~110s/chunk needs a
                                         different attack.
  browser/select/unaccounted dominant -> not a GPU question at all. A cold
                                         Chromium launch is a WARM-POOL problem.

SOURCES — CORRECTED TWICE BY MEASUREMENT (probe_corpus_app.py):
  1. THE BUCKET. The first version read Supabase "videos" and 404'd: wrong
     client AND wrong bucket. Measured, S3_BUCKET_NAME=thisismybucketagainwooo
     holds the corpus; promptly-video-storage (handler's default) holds ZERO.
  2. THE CORPUS. failure-corpus/ CANNOT serve this batch — 10 of 12 objects are
     1.3-2.8s (being tiny is WHY they are failures), max 30.0s so 60s/120s are
     unconstructible, and ZERO gaps in the 0.25-0.70s band across all 12.
     Firing at it would have reproduced preserved=1 at full render cost.

  So the sources are the OWNER-SELECTED references, uploaded to batch-corpus/,
  chosen by measured in-band gap count (silencedetect -30dB/0.20s):
     38.6s  15 in-band  d7akrh7og65p1f3s1ua0   <- short base / stall clip
     59.5s   2 in-band  d2rj4k7og65tcgn43lr0   <- long base, the 60s point
  HONEST LIMIT: ffmpeg finds SILENCE, not SENTENCE POSITION. No ASR runs here,
  so a high band count is ENRICHMENT, not a guarantee — better-than-random is
  the bar for a calibration pass, and it is the bar this clears.

  ./run_modal.sh batch_renderclock_app.py                 # dry
  ./run_modal.sh batch_renderclock_app.py --no-dry        # fire
     (Modal treats bool params as FLAGS: `--dry=False` is a CLI error,
      not a fire. It failed loudly rather than silently doing nothing.)
"""
import json
import sys

import modal

# modal_app is the app DEFINITION and is NOT in the image by default, so the
# container's re-import of THIS module dies at `import modal_app` — which is
# exactly what killed the first fire: 12 cells, all UserCodeException, all at
# import time, before a single frame was rendered.
#
# cert_gpu_fps.py already solved it: mount modal_app.py and put / on sys.path.
# I had diagnosed and written up this precise fix hours earlier and then did not
# apply it here.
sys.path.insert(0, "/")
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("batch-renderclock", image=image)

BUCKET = "thisismybucketagainwooo"
PREFIX = "batch-corpus"
STALL_CLIP = "v15044gf0000d7akrh7og65p1f3s1ua0.mp4"   # 38.6s, 15 in-band gaps
LONG_CLIP = "v24044gl0000d2rj4k7og65tcgn43lr0.mp4"    # 59.5s, 2 in-band gaps


def _url(key):
    return f"https://{BUCKET}.s3.amazonaws.com/{key}"


@app.function(secrets=modal_app.secrets, cpu=16, memory=12288,
              region="us", timeout=3600)
def render_cell(target_s: int, arm: str, rep: int) -> dict:
    """ONE forced render. Returns RENDERCLOCK legs + stage_timings.

    The source is CONSTRUCTED to `target_s` in-container — trimmed from a
    durable base, or concatenated when the target exceeds it — so only LENGTH
    varies across the curve. Stream-copy throughout, so the encode path is
    identical in every cell and a duration difference cannot be a codec
    difference wearing its clothes.
    """
    import os as _os, sys as _sys, uuid as _uuid, time as _time, subprocess as _sp
    import boto3

    _os.environ["APP_URL"] = ""                     # prod-isolate the render
    _os.environ["PROMPTLY_RENDER_CORE_BUDGET"] = "16"
    _sys.path.insert(0, "/")

    s3 = boto3.client("s3", region_name=_os.environ.get("AWS_REGION") or "us-west-2")
    base = STALL_CLIP if target_s <= 40 else LONG_CLIP
    src = f"/tmp/base_{target_s}_{arm}_{rep}.mp4"
    try:
        s3.download_file(BUCKET, f"{PREFIX}/{base}", src)
    except Exception as e:
        return {"target_s": target_s, "arm": arm, "rep": rep,
                "error": f"SOURCE DOWNLOAD FAILED: {type(e).__name__}: {e}", "clip": None}

    _d = _sp.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                  "-of", "default=nw=1:nk=1", src], capture_output=True, text=True)
    try:
        dur = float((_d.stdout or "").strip())
    except ValueError:
        return {"target_s": target_s, "arm": arm, "rep": rep,
                "error": "BASE PROBE FAILED — a FAILED measurement, not a zero", "clip": None}

    cut = f"/tmp/cut_{target_s}_{arm}_{rep}.mp4"
    if target_s <= dur:
        _sp.run(["ffmpeg", "-y", "-i", src, "-t", str(target_s), "-c", "copy", cut],
                capture_output=True, timeout=300)
    else:
        n = int(target_s // dur) + 1
        lst = f"/tmp/list_{target_s}_{arm}_{rep}.txt"
        with open(lst, "w") as fh:
            for _ in range(n):
                fh.write(f"file '{src}'\n")
        _sp.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                 "-t", str(target_s), "-c", "copy", cut],
                capture_output=True, timeout=600)
    if not _os.path.exists(cut) or _os.path.getsize(cut) < 10000:
        return {"target_s": target_s, "arm": arm, "rep": rep,
                "error": "CONSTRUCTION FAILED — no usable cut. A render on a bad "
                         "source would time something nobody can attribute.", "clip": None}

    key = f"{PREFIX}/_batch/{target_s}s_{arm}_{rep}.mp4"
    s3.upload_file(cut, BUCKET, key)
    out_url = _url(f"{PREFIX}/_batch/out_{target_s}s_{arm}_{rep}.mp4")

    import handler
    body = {"job_id": str(_uuid.uuid4()), "video_url": _url(key), "vibe": "viral",
            "user_id": str(_uuid.uuid4()), "upload_url": out_url,
            "public_url": out_url,
            # THE ARM. "control" forces control even with the flag armed.
            "offthread_test": arm}
    t0 = _time.time()
    try:
        r = handler.handler({"input": body})
    except Exception as e:
        return {"target_s": target_s, "arm": arm, "rep": rep,
                "error": f"{type(e).__name__}: {str(e)[:300]}",
                "wall_s": round(_time.time() - t0, 1)}
    st = (r or {}).get("stage_timings") or {}
    rec = {"target_s": target_s, "arm": arm, "rep": rep,
            "status": (r or {}).get("status"),
            "wall_s": round(_time.time() - t0, 1),
            "render_s": st.get("render"),
            "normalize_s": st.get("normalize_transcribe_upload"),
            "total_s": st.get("total"),
            "offthread_arm": st.get("offthread_arm"),
            "render_offthread_threads": st.get("render_offthread_threads"),
            "render_concurrency": st.get("render_concurrency"),
            "render_legs": st.get("render_legs"),
            "dead_air": {k: st.get(k) for k in
                         ("dead_air_spans_located", "dead_air_spans_offered",
                          "dead_air_spans_preserved", "midsentence_stall_s")},
            "timeline": st.get("timeline"),
           # SELF-DESCRIBING: the record names its own cell, so a result found
           # later needs no external index to be interpretable.
           "clip": base, "source_duration_s": st.get("source_duration_s"),
           "pool_task_s": st.get("pool_task_s")}
    _persist(s3, rec)
    return rec


def _persist(s3, rec):
    """DURABLE THE MOMENT IT EXISTS — written from the CELL, not the harness.

    fire3 rendered 10 of 12 cells and then died on GRPCError UNAVAILABLE while
    collecting. Every result lived only in returned dicts and died with the
    client: the `.remote()`-dies-with-client trap already written in this repo's
    notes. The harness printed a warning about durable records and had none.

    The harness is a DISPATCHER and a READER, never a HOLDER.
    """
    import json as _j
    try:
        key = (f"{PREFIX}/_results/{rec['target_s']}s_{rec['arm']}_r{rec['rep']}.json")
        s3.put_object(Bucket=BUCKET, Key=key,
                      Body=_j.dumps(rec, default=str).encode(),
                      ContentType="application/json")
        print(f"[batch] persisted {key}", flush=True)
    except Exception as e:
        # A cell that rendered and could not persist must SAY so — silence here
        # would look identical to a cell that never ran.
        print(f"[batch] ✗ PERSIST FAILED for {rec.get('target_s')}s/"
              f"{rec.get('arm')}: {type(e).__name__}: {e}", flush=True)


def _find(n, want):
    if isinstance(n, dict):
        if n.get("name") == want:
            return n
        for c in (n.get("children") or []):
            f = _find(c, want)
            if f:
                return f
    return None


def _report(results):
    ok = [r for r in results if not r.get("error") and r.get("render_legs")]
    print(f"\n  ════ RENDERCLOCK — {len(ok)} of {len(results)} cells usable ════")
    if not ok:
        print("  NO CELL PRODUCED LEGS. An EMPTY READ, not a zero.")
        for r in results[:6]:
            print(f"    {r.get('target_s')}s/{r.get('arm')}: "
                  f"{(r.get('error') or r.get('status') or '?')[:100]}")
        return
    print(f"  {'dur':>4} {'arm':>7} {'leg':>24} {'frames':>7} {'frames_ms':>10} "
          f"{'stitch_ms':>10} {'browser':>8} {'ms/frm':>8}")
    agg = {}
    for r in ok:
        for lg in r["render_legs"]:
            print(f"  {r['target_s']:>4} {r['arm']:>7} {str(lg.get('leg'))[:24]:>24} "
                  f"{lg.get('frames', 0):>7} {lg.get('frames_ms', 0):>10} "
                  f"{lg.get('stitch_ms', 0):>10} {lg.get('browser_ms', 0):>8} "
                  f"{lg.get('ms_per_frame', 0):>8}")
            a = agg.setdefault((r["target_s"], r["arm"]),
                               {"frames_ms": 0, "stitch_ms": 0, "browser_ms": 0,
                                "select_ms": 0, "unacc": 0, "frames": 0})
            for f in ("frames_ms", "stitch_ms", "browser_ms", "select_ms"):
                a[f] += lg.get(f, 0) or 0
            a["unacc"] += lg.get("unaccounted_ms", 0) or 0
            a["frames"] += lg.get("frames", 0) or 0

    print(f"\n  ════ WHICH TERM DOMINATES (summed over legs) ════")
    print(f"  {'dur':>4} {'arm':>7} {'frames_ms':>10} {'stitch_ms':>10} "
          f"{'browser_ms':>11} {'select_ms':>10} {'unacc_ms':>9}  verdict")
    for (d, a_), v in sorted(agg.items()):
        terms = {"frames": v["frames_ms"], "stitch": v["stitch_ms"],
                 "browser": v["browser_ms"], "select": v["select_ms"],
                 "unaccounted": v["unacc"]}
        print(f"  {d:>4} {a_:>7} {v['frames_ms']:>10} {v['stitch_ms']:>10} "
              f"{v['browser_ms']:>11} {v['select_ms']:>10} {v['unacc']:>9}  "
              f"{max(terms, key=terms.get)}")
    print("\n  READ AS A CURVE across durations, not a verdict from one row.")

    print(f"\n  ════ normalize_transcribe_upload — wait_* decomposition ════")
    for r in ok:
        node = _find(r.get("timeline") or {}, "normalize_transcribe_upload")
        if node:
            kids = ", ".join(f"{c.get('name')}={c.get('dur')}s"
                             for c in (node.get("children") or []))
            print(f"  {r['target_s']:>4}s {r['arm']:>7} total={node.get('dur')}s "
                  f"[{kids or 'NO CHILDREN'}]")
        else:
            print(f"  {r['target_s']:>4}s {r['arm']:>7} NODE ABSENT from timeline")

    print(f"\n  ════ offthread arms (frames identical => length matched) ════")
    for (d, a_), v in sorted(agg.items()):
        print(f"  {d:>4}s {a_:>7} frames={v['frames']:>6} "
              f"frames_ms={v['frames_ms']:>8} stitch_ms={v['stitch_ms']:>7}")

    print(f"\n  ════ dead-air (stall clip: 15 measured in-band gaps) ════")
    for r in ok:
        da = r.get("dead_air") or {}
        print(f"  {r['target_s']:>4}s {r['arm']:>7} stall={da.get('midsentence_stall_s')} "
              f"located={da.get('dead_air_spans_located')} "
              f"offered={da.get('dead_air_spans_offered')} "
              f"preserved={da.get('dead_air_spans_preserved')}")


@app.function(secrets=modal_app.secrets, timeout=900)
def collect() -> list:
    """Read every persisted cell record back from S3.

    THE RECOVERY PATH. Because each cell writes itself, results survive the
    harness dying — which is not hypothetical: fire3 lost 10 completed renders
    to a GRPCError while collecting. This can be run STANDALONE after any crash.
    """
    import boto3, json as _j, os as _os
    s3 = boto3.client("s3", region_name=_os.environ.get("AWS_REGION") or "us-west-2")
    out = []
    tok = None
    while True:
        kw = {"Bucket": BUCKET, "Prefix": f"{PREFIX}/_results/"}
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", []):
            try:
                b = s3.get_object(Bucket=BUCKET, Key=o["Key"])["Body"].read()
                out.append(_j.loads(b))
            except Exception as e:
                out.append({"error": f"UNREADABLE {o['Key']}: {type(e).__name__}"})
        if not r.get("IsTruncated"):
            break
        tok = r.get("NextContinuationToken")
    return out


@app.local_entrypoint()
def main(durations: str = "20,60,120", repeats: int = 3, dry: bool = True,
         read_only: bool = False):
    if read_only:
        # RECOVER, don't re-render. Costs one small container.
        _report(collect.remote())
        return

    want = [int(x) for x in durations.split(",") if x.strip()]
    arms = ["2", "control"]
    cells = [(d, a, r) for d in want for a in arms for r in range(repeats)]
    print(f"  PLAN: {len(want)} durations x {len(arms)} arms x {repeats} reps "
          f"= {len(cells)} renders")
    print(f"  bucket {BUCKET}/{PREFIX}   results -> {PREFIX}/_results/")
    print(f"  PRICED ~$0.07-0.10 each -> ~${0.07 * len(cells):.2f}-"
          f"${0.10 * len(cells):.2f}")
    if dry:
        print("\n  DRY RUN — nothing rendered. Pass --no-dry to fire.")
        return

    # SPAWN + from_id. The harness dispatches and then READS S3; it never holds
    # a result. If this process dies, `--read-only` recovers everything.
    print(f"\n  spawning {len(cells)} cells...\n")
    calls = []
    for (d, a, r) in cells:
        c = render_cell.spawn(d, a, r)
        calls.append((d, a, r, c.object_id))
        print(f"  → {d:>4}s {a:>7} r{r}  {c.object_id}")
    with open("/tmp/batch_call_ids.json", "w") as fh:
        json.dump([{"target_s": d, "arm": a, "rep": r, "call_id": cid}
                   for (d, a, r, cid) in calls], fh, indent=1)
    print(f"\n  call ids -> /tmp/batch_call_ids.json "
          f"(recover with --read-only even if this process dies)")

    done = 0
    for (d, a, r, cid) in calls:
        try:
            fc = modal.FunctionCall.from_id(cid)
            res = fc.get(timeout=3600)
            done += 1
            if res.get("error"):
                print(f"  ✗ {d:>4}s {a:>7} r{r}: {str(res['error'])[:90]}")
            else:
                print(f"  ✓ {d:>4}s {a:>7} r{r}  render={res.get('render_s')}s "
                      f"norm={res.get('normalize_s')}s "
                      f"legs={len(res.get('render_legs') or [])}")
        except Exception as e:
            # The cell may still have PERSISTED. Say which is unknown.
            print(f"  ? {d:>4}s {a:>7} r{r}: collect failed "
                  f"({type(e).__name__}) — the cell may still have written its "
                  f"record; recover with --read-only")
    print(f"\n  {done}/{len(calls)} collected in-process; "
          f"reading the durable record for the report")
    _report(collect.remote())
