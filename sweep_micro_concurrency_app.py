"""4/2/1 MICRO-CONCURRENCY SWEEP — ON THE BURST PATH. ~$1.50, 12 renders.

WHY THIS DISPATCHES INSTEAD OF IMPORTING. Every prior batch did
`import handler; handler.handler(...)` inside an ephemeral `modal run`, so
`_render_burst_enabled` was ALWAYS False (it is deployed-app-only) and every
number described the LOCAL path. Production bursts. This calls the DEPLOYED
`run_pipeline_bg` with `.remote()`, so the job takes the real path — burst
container, real concurrency, real contention.

THE QUESTION. Micro frames cost 775-1,797 ms/frame in production against
108-110 ms/frame measured ISOLATED at concurrency 1 (micro-seek-cost.mjs, which
also refuted decode-once-per-segment at ~1%). A 7-16x gap on the same primitive.
Hypothesis: CONTENTION — several Chromium pages behind one lazy Rust compositor.
Never tested on the path production uses.

CAPTURED PER ARM, all four in one run so no arm needs a second spend:
  ms/frame PER COMPOSITION — PromptlyMicroSegments vs PromptlyOverlay. The gap
      is on MICRO specifically (overlay measured 17-75 ms/frame, micro 775-1797
      on the same job), so a blended ms/frame would hide the whole effect.
  core count and concurrent page count — so contention is answerable from data
      rather than argument.
  cost per job — because a speed win that raises cost is a RULING, not a ship.

DECISION RULE, fixed before the run so it cannot be fitted after:
  lower concurrency wins on BOTH speed and cost -> ship flag-gated, byte-identity
      verified (renders are byte-deterministic on a fixed plan: pass/fail, not
      "within noise").
  it TRADES on either axis -> STOP and report. Zac's ruling, not an autonomous flip.

  ./run_modal.sh sweep_micro_concurrency_app.py                    # dry
  ./run_modal.sh sweep_micro_concurrency_app.py --no-dry --confirm-only
  ./run_modal.sh sweep_micro_concurrency_app.py --no-dry
"""
import json
import os
import sys
import uuid

import modal

app = modal.App("sweep-micro-concurrency")

BUCKET = "thisismybucketagainwooo"
PREFIX = "batch-corpus"
# 59.5s owner-selected reference — long enough to clear the 45s burst floor
# (PROMPTLY_BURST_MIN_OUTPUT_S), which is what makes the job take the BURST path
# at all. A 20s source would silently stay local and measure the wrong thing.
# CLIP SELECTION IS A MEASUREMENT, NOT A PREFERENCE. v24044gl… was the original
# pick and it renders ZERO micro segments (confirmed 2026-08-29, job 17831389:
# 3 legs, all PromptlyOverlay) — which makes the whole sweep inert on it. The
# four durable corpus clips are tried in order and each must pass the
# micro-legs confirmation below before any arm is dispatched. Corpus sources
# only: organic jobs that produce micro are real users' media and are not
# eligible (feedback_ab_durable_sources).
CLIP = os.environ.get("SWEEP_CLIP") or "v15044gf0000d8slpi7og65utp063oi0.mp4"
ARMS = [4, 2, 1]


@app.function(image=modal.Image.debian_slim().pip_install("boto3"),
              secrets=[modal.Secret.from_name("promptly-secrets")], timeout=600)
def presign(cells: list) -> dict:
    """Presigned GET for the source + presigned PUT per output, made INSIDE Modal.

    THE BUG THIS FIXES (2026-08-28). This harness built a bare
    `https://{bucket}.s3.amazonaws.com/{key}` URL. The bucket is private, so the
    worker's HEAD returned 403 and the job died UPLOAD_STALLED at handler.py:40537
    after 600s of polling — "Source video did not arrive on S3", which reads like
    an upload fault and is really an ACCESS fault in the harness. Every other
    harness in this repo presigns (ab_pair_probe, cert_cap_rendertime,
    caption_proof); this one did not.

    It must be presigned HERE, not locally: the local AWS credentials are invalid
    (InvalidClientTokenId), while `promptly-secrets` carries the working pair. A
    presign is just an HMAC over the request — signing with a dead key yields a
    URL that is well-formed and 403s, i.e. a broken source wearing a valid URL's
    face, which is exactly the failure above.

    NON-VACUITY: HEAD the source first and return the byte size. A presigned URL
    for an object that does not exist is indistinguishable from one that does
    until the worker times out 600s later — and that timeout would land as
    UPLOAD_STALLED again and read, wrongly, as a pipeline failure.
    """
    import os as _os
    import boto3
    s3 = boto3.client("s3", region_name=_os.environ.get("AWS_REGION") or "us-west-1")
    src_key = f"{PREFIX}/{CLIP}"

    # RESOLVE THE BUCKET, DO NOT ASSUME IT. This harness hardcoded
    # `thisismybucketagainwooo`; the canonical source is S3_BUCKET_NAME and the
    # rest of the repo defaults to `promptly-video-storage`. probe_corpus_app.py
    # exists because this exact ambiguity already cost a session. Try each and
    # report which one actually holds the key — and if none does, LIST what is
    # there, so the next reader gets an inventory instead of another 403.
    _cands, _seen = [], set()
    for _b in (_os.environ.get("S3_BUCKET_NAME"), BUCKET, "promptly-video-storage"):
        if _b and _b not in _seen:
            _seen.add(_b)
            _cands.append(_b)

    _tried, _bucket, _size = [], None, 0
    for _b in _cands:
        try:
            _h = s3.head_object(Bucket=_b, Key=src_key)
            _bucket, _size = _b, _h.get("ContentLength", 0)
            break
        except Exception as e:
            _tried.append(f"{_b}: {type(e).__name__} {str(e)[:80]}")

    if _bucket is None:
        # INVENTORY, not just a failure. A 403 on one key cannot distinguish
        # "wrong bucket" from "no access at all" from "key renamed".
        _inv = {}
        for _b in _cands:
            try:
                _r = s3.list_objects_v2(Bucket=_b, Prefix=f"{PREFIX}/", MaxKeys=15)
                _inv[_b] = [o["Key"] for o in _r.get("Contents", [])]
            except Exception as e:
                _inv[_b] = f"LIST FAILED: {type(e).__name__} {str(e)[:80]}"
        return {"ok": False, "error": "no candidate bucket holds the source key",
                "key": src_key, "tried": _tried, "inventory": _inv,
                "env_S3_BUCKET_NAME": _os.environ.get("S3_BUCKET_NAME")}
    if not _size:
        return {"ok": False, "error": f"source is 0 bytes: {_bucket}/{src_key}"}

    src = s3.generate_presigned_url("get_object",
                                    Params={"Bucket": _bucket, "Key": src_key},
                                    ExpiresIn=14400)
    outs = {}
    for c in cells:
        k = f"{PREFIX}/_sweep/out_{c['conc']}_{c['rep']}_{c['job_id'][:8]}.mp4"
        outs[f"{c['conc']}_{c['rep']}"] = s3.generate_presigned_url(
            "put_object", Params={"Bucket": _bucket, "Key": k,
                                  "ContentType": "video/mp4"}, ExpiresIn=14400)
    return {"ok": True, "source_url": src, "outs": outs, "source_bytes": _size,
            "key": f"{_bucket}/{src_key}", "bucket": _bucket}


@app.function(image=modal.Image.debian_slim().pip_install("supabase"),
              secrets=[modal.Secret.from_name("promptly-secrets")], timeout=600)
def preinsert(rows: list) -> dict:
    """Create the video_jobs row BEFORE dispatch.

    ROOT CAUSE of two confident nulls: `write_job_status` UPDATEs a row it
    expects to already exist (`.eq("id", job_id)`) and early-returns when there
    is nothing to write to — it never INSERTs. The row is normally created by
    content-studio when a real user starts a job. A synthetic job_id therefore
    has NOWHERE to report, so a render that COMPLETED read back as status=None,
    render=None, legs=0 — a finished job wearing an empty result's face.

    REQUIRED COLUMNS, read from the OpenAPI spec rather than discovered one
    constraint error at a time: id, status, video_url, vibe_input, demo.
    (`demo` marks these as non-user rows, which also keeps them out of product
    metrics — a sweep job must never be counted as a maker.)
    """
    import os as _os
    from supabase import create_client
    sb = create_client(_os.environ.get("SUPABASE_URL"),
                       _os.environ.get("SUPABASE_SERVICE_KEY")
                       or _os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
                       or _os.environ.get("SUPABASE_KEY"))
    ok, errs = 0, []
    for r in rows:
        try:
            sb.table("video_jobs").insert({
                "id": r["job_id"], "status": "queued",
                "video_url": r["video_url"], "vibe_input": "viral",
                "demo": True,
            }).execute()
            ok += 1
        except Exception as e:
            errs.append({"job_id": r["job_id"], "err": str(e)[:200]})
    return {"inserted": ok, "errors": errs}


@app.function(image=modal.Image.debian_slim().pip_install("supabase"),
              secrets=[modal.Secret.from_name("promptly-secrets")], timeout=600)
def collect(job_ids: list) -> list:
    """Read the RESULT FROM video_jobs — the only place run_pipeline_bg puts it."""
    import os as _os
    from supabase import create_client
    sb = create_client(_os.environ.get("SUPABASE_URL"),
                       _os.environ.get("SUPABASE_SERVICE_KEY")
                       or _os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
                       or _os.environ.get("SUPABASE_KEY"))
    out = []
    for jid in job_ids:
        try:
            r = (sb.table("video_jobs")
                 .select("id, status, error_message, st:result->stage_timings")
                 .eq("id", jid).limit(1).execute())
            d = (r.data or [{}])[0]
            out.append({"job_id": jid, "status": d.get("status"),
                        "error": (d.get("error_message") or "")[:160],
                        "stage_timings": d.get("st")})
        except Exception as e:
            out.append({"job_id": jid, "status": f"READ FAILED: {type(e).__name__}"})
    return out


@app.local_entrypoint()
def main(dry: bool = True, confirm_only: bool = False, repeats: int = 2):
    cells = [(c, r) for c in ARMS for r in range(repeats)]
    if confirm_only:
        cells = [(4, 0)]
    print(f"  PLAN: {'CONFIRMATION (1 job)' if confirm_only else f'{len(ARMS)} arms x {repeats} reps'}"
          f" = {len(cells)} renders on the DEPLOYED worker (burst path)")
    print(f"  source: {CLIP} (59.5s — above the 45s burst floor, so it BURSTS)")
    print(f"  arms: {ARMS}   priced ~$0.10-0.13 each -> ~${0.10*len(cells):.2f}-${0.13*len(cells):.2f}")
    if dry:
        print("\n  DRY RUN — nothing dispatched. Pass --no-dry to fire.")
        return

    # PRESIGN FIRST — and prove the source is READABLE before spending on any
    # render. An unreadable source costs 600s per cell and lands UPLOAD_STALLED,
    # which reads as a pipeline failure and is not one.
    _cells = [{"conc": c, "rep": r, "job_id": str(uuid.uuid4())} for (c, r) in cells]
    _ps = presign.remote(_cells)
    if not _ps.get("ok"):
        print(f"  ❌ SOURCE NOT READABLE — {_ps.get('error')}")
        print(f"     key: {_ps.get('key')}   env S3_BUCKET_NAME="
              f"{_ps.get('env_S3_BUCKET_NAME')!r}")
        for _t in _ps.get("tried", []):
            print(f"       tried {_t}")
        for _b, _keys in (_ps.get("inventory") or {}).items():
            print(f"     inventory {_b}: "
                  + (_keys if isinstance(_keys, str) else f"{len(_keys)} keys"))
            if isinstance(_keys, list):
                for _k in _keys[:8]:
                    print(f"         {_k}")
        print("     Refusing to dispatch. This would land UPLOAD_STALLED on every "
              "cell and be misread as a pipeline failure.")
        sys.exit(2)
    print(f"  source readable: {_ps['key']} ({_ps['source_bytes']/1e6:.1f} MB), "
          f"presigned inside Modal")

    # PRE-INSERT SECOND, DISPATCH THIRD. Reversing these means the worker's
    # first status write races a row that does not exist yet.
    fn = modal.Function.from_name("promptly-gpu-worker", "run_pipeline_bg")
    _pending = []
    for c in _cells:
        out = _ps["outs"][f"{c['conc']}_{c['rep']}"]
        body = {"job_id": c["job_id"], "video_url": _ps["source_url"],
                "vibe": "viral", "user_id": str(uuid.uuid4()),
                "upload_url": out, "public_url": out,
                "micro_concurrency_test": str(c["conc"])}
        _pending.append({"conc": c["conc"], "rep": c["rep"], "fn": fn, "body": body,
                         "job_id": c["job_id"], "video_url": _ps["key"]})
    _pre = preinsert.remote([{ "job_id": p["job_id"], "video_url": p["video_url"]}
                             for p in _pending])
    print(f"  pre-inserted {_pre.get('inserted')}/{len(_pending)} rows"
          + (f"  ERRORS: {_pre['errors'][:2]}" if _pre.get("errors") else ""))
    if _pre.get("inserted", 0) != len(_pending):
        print("  ❌ NOT ALL ROWS EXIST — refusing to dispatch. A job with no row "
              "reports nowhere and returns a confident null.")
        sys.exit(2)

    ids = []
    for p in _pending:
        c, r, jid = p["conc"], p["rep"], p["job_id"]
        cid = p["fn"].spawn(p["body"]).object_id
        # SAVE THE job_id. run_pipeline_bg is FIRE-AND-FORGET — the `_bg` is
        # literal: it writes to video_jobs and returns NOTHING. The first run
        # read the return value and got None for every field, which looked like
        # "the render reported nothing" and was really "I read the wrong place".
        # Without the job_id there is also no way to pin WHICH row was ours.
        ids.append({"conc": c, "rep": r, "call_id": cid, "job_id": jid})
        print(f"  → conc={c} r{r}  job={jid[:8]}  {cid}")
    with open("/tmp/sweep_ids.json", "w") as fh:
        json.dump(ids, fh, indent=1)
    print(f"\n  call ids -> /tmp/sweep_ids.json (recoverable if this process dies)")

    # Wait for the dispatched calls to finish, then read the ROWS.
    for it in ids:
        try:
            modal.FunctionCall.from_id(it["call_id"]).get(timeout=2400)
        except Exception as e:
            print(f"  ! conc={it['conc']} r{it['rep']} call raised "
                  f"({type(e).__name__}) — the row may still exist; reading it")
    # COLLECTION MUST SURVIVE THIS APP DYING. On the 08-28 confirmation run the
    # ephemeral app was stopped while waiting, and `collect` — a function of THIS
    # app — raised FAILED_PRECONDITION "function is stopped". The JOB was fine;
    # only the reader died, and the run reported a hard failure for a render that
    # had already happened. The rendered work lives in video_jobs, so a dead
    # reader is a recoverable state, not a lost result.
    try:
        rows = collect.remote([i["job_id"] for i in ids])
    except Exception as e:
        print(f"\n  ! collect FAILED ({type(e).__name__}: {str(e)[:120]})")
        print("    The jobs are UNAFFECTED — they are spawned and write to "
              "video_jobs. Read them with:")
        print("      ./run_modal.sh read_sweep_row_app.py --jids "
              + ",".join(i["job_id"] for i in ids))
        print("    Do NOT read this exit as 'the renders failed'.")
        sys.exit(3)
    for it in ids:
        row = next((x for x in rows if x.get("job_id") == it["job_id"]), None) or {}
        it.update(row)
        st = row.get("stage_timings") or {}
        legs = st.get("render_legs") or []
        it.update({"render_s": st.get("render"), "total_s": st.get("total"),
                   "legs": legs, "conc_reported": st.get("render_concurrency")})
        # STATUS IS REPORTED, because a FAILED job writes no timings and would
        # otherwise read as "no legs" — a failure wearing a null result's face.
        print(f"  {'✓' if legs else '✗'} conc={it['conc']} r{it['rep']} "
              f"status={row.get('status')} render={st.get('render')}s "
              f"legs={len(legs)} conc_seen={st.get('render_concurrency')}")
    rows = ids
    with open("/tmp/sweep_rows.json", "w") as fh:
        json.dump(rows, fh, indent=1, default=str)
    _report(rows, confirm_only)


def _report(rows, confirm_only):
    ok = [r for r in rows if r.get("legs")]
    print(f"\n  ════ {len(ok)}/{len(rows)} cells returned RENDERCLOCK legs ════")
    if not ok:
        print("  NO LEGS — an EMPTY READ, not a zero. Either the job did not take")
        print("  the burst path, or the instrument is still not crossing. Do NOT")
        print("  read this as 'concurrency has no effect'.")
        return
    if confirm_only:
        for lg in ok[0]["legs"][:8]:
            print(f"    {str(lg.get('leg'))[:38]:>38}  frames={lg.get('frames')} "
                  f"ms/frame={lg.get('ms_per_frame')}")
        # LEGS ARE NOT ENOUGH — THE SWEEP MEASURES *MICRO*.
        #
        # 2026-08-29: the first confirmation returned 3 legs, all PromptlyOverlay,
        # and read as "CONFIRMATION PASSED: sweep unblocked". It was not. Micro
        # segments come from transitions and complex zooms (handler.py:31786), and
        # the micro_concurrency_test override lives INSIDE the micro render path
        # (handler.py:32251-32273). On a source with no micro work the sweep's
        # INDEPENDENT VARIABLE never executes and its DEPENDENT VARIABLE never
        # exists — 6 cells of identical overlay renders reading as "concurrency
        # has no effect". That is an instrument failure wearing a result's face,
        # and it would have cost the whole budget to learn nothing.
        #
        # Measured on organic traffic: 83/94 jobs with legs produce micro (88.3%),
        # micro p50 1047.8 ms/frame vs overlay 114.5 (9.2x). So a source with NO
        # micro is the unusual 11.7%, not a safe default.
        _micro = [lg for lg in ok[0]["legs"] if "Micro" in str(lg.get("leg"))]
        _conc = ok[0].get("conc_reported")
        print(f"\n  micro legs: {len(_micro)}   render_concurrency reported: {_conc}")
        if not _micro:
            print("\n  ❌ CONFIRMATION FAILED — legs, but ZERO PromptlyMicroSegments.")
            print("     This source produces no transitions/complex zooms, so the")
            print("     concurrency override has nothing to act on. Do NOT run the")
            print("     sweep on it: every arm would be identical and the null")
            print("     result would be the harness, not the renderer.")
            print("     Pick another corpus clip and re-confirm.")
            sys.exit(4)
        if _conc in (None, [], ""):
            print("\n  ⚠️  micro ran but render_concurrency is EMPTY — the arm cannot")
            print("     be verified as applied. A sweep whose independent variable")
            print("     is unobservable produces uninterpretable arms.")
            sys.exit(5)
        print("\n  CONFIRMATION PASSED: micro legs present AND concurrency observable.")
        return
    agg = {}
    for r in ok:
        for lg in r["legs"]:
            comp = "micro" if "Micro" in str(lg.get("leg")) else "overlay"
            a = agg.setdefault((r["conc"], comp), {"mspf": [], "frames": 0, "legs": 0})
            a["mspf"].append(lg.get("ms_per_frame") or 0)
            a["frames"] += lg.get("frames") or 0
            a["legs"] += 1
    import statistics as st_
    print(f"\n  {'conc':>5} {'composition':>12} {'ms/frame p50':>13} {'legs':>5} {'frames':>7}")
    for (c, comp), a in sorted(agg.items()):
        print(f"  {c:>5} {comp:>12} {st_.median(a['mspf']):>13.1f} {a['legs']:>5} {a['frames']:>7}")
    print(f"\n  {'conc':>5} {'render_s p50':>13} {'cost/job est':>13}")
    for c in ARMS:
        rs = [r["render_s"] for r in ok if r["conc"] == c and r.get("render_s")]
        if rs:
            med = st_.median(rs)
            # cpu=32 burst; cost tracks CORE-SECONDS, which is what a concurrency
            # change actually moves. Rate is indicative — the RATIO is the result.
            print(f"  {c:>5} {med:>13.1f} {32*med/3600*0.55:>13.4f}")
    print("\n  DECISION: lower conc must win on BOTH ms/frame and cost/job to ship.")
    print("  A trade on either axis stops here and goes to Zac.")
