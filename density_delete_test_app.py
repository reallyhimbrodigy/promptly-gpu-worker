"""DENSITY DELETE-TEST — cap PRESENT vs REMOVED, plan-stage, no renders.

THE LEVER. The editorial prompt carries a rarity doctrine: "3-5 true peaks for a
typical 30s video". `density_variant=2` deletes exactly that cap and NOTHING
else (handler.py:7779 `_delete_rarity` -> `_peak_budget`); emphasis stays
zoom-by-default, no rhythm block, no variety ceiling. So the pair below isolates
ONE sentence. Variant 1 (the ADD approach) is already refuted at ~0.95x — adding
a density block loses to the base rarity doctrine, which is why removal is the
only arm worth running.

WHY PLAN_ONLY IS THE RIGHT INSTRUMENT, not a cheaper one. Density has TWO
candidate ceilings and a render cannot tell them apart:
    the MODEL won't emit more            (prompt-bound — this lever moves it)
    the GATES cull what it emits         (architectural — this lever cannot)
PLAN_ONLY returns `edit_plan` BEFORE recipe-build culling, so it measures
EMISSION. If emission rises and delivered density does not, the ceiling is
downstream and no prompt edit will ever reach it. That is the question worth
~$0.10 a run.

MEASURED PER 25s OF OUTPUT, BY FAMILY — never blended. A single events/s hides
which instrument moved, and the whole complaint is that the edit is zoom-heavy:
a rise that is all emphasis is monotony, a rise spread across MG/overlay/
transition/SFX is the intended shape. Families are read from the assembled plan:
emphasis_moments, motion_graphics, text_overlays, transitions, sound_effects,
plus broll_clips and tight_cut_overlays for completeness.

PAIRED ON THE SAME SOURCE so Zac can watch pairs, and because cross-source
variance dwarfs the arm effect — an unpaired comparison would be measuring the
sources, not the sentence.

HONEST ABOUT n. Gemini is stochastic; one pair per source cannot separate the
arm from run-to-run variance. Per-source deltas AND the spread are both
reported, and the verdict refuses to call a direction the spread does not
support.

  ./run_modal.sh density_delete_test_app.py                 # 2 sources x 2 arms
  ./run_modal.sh density_delete_test_app.py --n-sources 4   # all four
"""
import os
import sys

sys.path.insert(0, "/")
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("density-delete-test", image=image)

# FULL deployed secret set — a harness missing one measures a different world
# (promptly-lang-flags carries the live editorial flags).
SECRETS = [modal.Secret.from_name(n) for n in (
    "promptly-secrets", "promptly-cloudfront", "gemini-vertex",
    "promptly-lang-flags", "promptly-elevenlabs")]

BUCKET = "thisismybucketagainwooo"

# STAGED, VERIFIED TALKING HEADS — NOT batch-corpus.
#
# The first run of this test used batch-corpus clips and was invalid. All four
# of those are FINISHED MULTI-CUT EDITS (7.6-25.4 hard cuts/25s; v24044gl is 60
# cuts in 59s), i.e. Zac's reference edits fed back in as if they were raw
# sources. The planner had nothing left to add, every family read zero for the
# wrong reason, and BOTH cap arms tripped `salvaged post-cuts plan` — a rescued
# plan is not the arm.
#
# These three come from failure-corpus/ (real sources retained for replay,
# sanctioned), verified 2026-08-29: face in 100% of sampled frames, 0.0-0.7
# hard cuts/25s, real speech levels, distinct by sha256. Staged to an immutable
# content-addressed prefix so the fixtures cannot drift under the experiment.
CLIPS = [
    "ab-sources/talking-head-v1/625dfdc5-73s.mp4",
    "ab-sources/talking-head-v1/3b2e5346-35s.mp4",
    "ab-sources/talking-head-v1/0c17b20b-35s.mp4",
]

FAMILIES = ("emphasis_moments", "motion_graphics", "text_overlays",
            "transitions", "sound_effects", "broll_clips",
            "tight_cut_overlays")


@app.function(secrets=SECRETS, cpu=16.0, memory=32768, timeout=2400)
def presign(keys: list) -> dict:
    import boto3
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    b = os.environ.get("S3_BUCKET_NAME") or BUCKET
    out = {}
    for k in keys:
        s3.head_object(Bucket=b, Key=k)          # non-vacuity: prove it exists
        out[k] = s3.generate_presigned_url(
            "get_object", Params={"Bucket": b, "Key": k}, ExpiresIn=14400)
    return out


@app.function(secrets=SECRETS, cpu=16.0, memory=32768, timeout=2400)
def run_arm(arm: dict) -> dict:
    import io
    import time
    import traceback
    from build_lane import mark_build_lane
    mark_build_lane("density_delete_test_app.py")
    os.environ["APP_URL"] = ""                    # no callback, no push, no analytics
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""  # no phantom video_jobs rows
    # PER-ARM ENV. Flags like PROMPTLY_SEAM_CANDIDATES are read INSIDE the
    # container at plan time, so an arm that differs by flag must set it here —
    # setting it locally would change nothing and the arms would be identical
    # while reading as a comparison.
    for _k, _v in (arm.get("env") or {}).items():
        os.environ[str(_k)] = str(_v)
    sys.path.insert(0, "/")
    import handler as H

    if arm.get("stagger_s"):
        time.sleep(float(arm["stagger_s"]))       # Deepgram overloads on identical concurrent calls

    _key = f"density-dt/{arm['job_id']}/render.mp4"
    _url = f"https://{BUCKET}.s3.amazonaws.com/{_key}"
    body = {
        "job_id": arm["job_id"],
        "video_url": arm["src"],
        "vibe": arm.get("vibe", "Clean and engaging edit"),
        "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
        "upload_url": _url, "public_url": _url,
        "plan_only": True,                        # <- exits before any render
        "density_variant": int(arm["variant"]),   # 0 = cap present, 2 = cap deleted
        "supports_progressive": False,
        "premium_pipeline_enabled": False,
    }

    # DEGRADATION SCAN. A safe-edit rescue produces a PLAUSIBLE plan, not an
    # empty one — a null check cannot see it, and a rescued plan is not the arm.
    _buf, _orig = io.StringIO(), sys.stdout

    class _Tee:
        def write(self, s):
            try:
                _orig.write(s)
            except Exception:
                pass
            _buf.write(s)
            return len(s)

        def flush(self):
            try:
                _orig.flush()
            except Exception:
                pass

    t0 = time.time()
    sys.stdout = _Tee()
    try:
        res = H.handler({"input": body})
    except Exception as e:
        sys.stdout = _orig
        return {"label": arm["label"], "clip": arm["clip"], "variant": arm["variant"],
                "error": f"{type(e).__name__}: {str(e)[:300]}",
                "tb": traceback.format_exc()[-700:]}
    finally:
        sys.stdout = _orig
    _logs = _buf.getvalue()
    _DEGRADE = ["[safe-edit] engaged", "safe_edit_rescue", "[error-fallback]",
                "outer:UNKNOWN", "safe_edit_fallback", "salvaged post-cuts plan"]

    plan = res.get("edit_plan") if isinstance(res, dict) else None
    return {
        "label": arm["label"], "clip": arm["clip"], "variant": arm["variant"],
        "status": res.get("status") if isinstance(res, dict) else "?",
        "degraded": sorted({m for m in _DEGRADE if m in _logs}),
        "source_duration_s": res.get("source_duration_s") if isinstance(res, dict) else None,
        "gemini_output_tokens": res.get("gemini_output_tokens") if isinstance(res, dict) else None,
        "gemini_n_calls": res.get("gemini_n_calls") if isinstance(res, dict) else None,
        "plan_keys": sorted(plan.keys())[:40] if isinstance(plan, dict) else None,
        "counts": {f: len(plan.get(f) or []) for f in FAMILIES} if isinstance(plan, dict) else None,
        "n_cuts": len(plan.get("cuts") or []) if isinstance(plan, dict) else None,
        "out_dur_s": _out_dur(plan),
        "wall_s": round(time.time() - t0, 1),
    }


def _out_dur(plan):
    """OUTPUT seconds the plan describes — the denominator for 'per 25s'.

    Derived from the kept cuts, NOT from source duration: the edit deletes
    silence and filler, so source seconds would inflate the denominator and
    understate density by exactly the amount the cut pass removed. Returns None
    when cuts are absent so the caller reports an ABSENT denominator rather than
    dividing by a guess.
    """
    if not isinstance(plan, dict):
        return None
    tot = 0.0
    for c in (plan.get("cuts") or []):
        if not isinstance(c, dict):
            continue
        a, b = c.get("source_start"), c.get("source_end")
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b > a:
            tot += (b - a) / (c.get("speed") or 1)
    return round(tot, 1) if tot > 0 else None


@app.local_entrypoint()
def main(n_sources: int = 2, reps: int = 1, mode: str = "cap"):
    import statistics as st
    import uuid

    clips = CLIPS[:max(1, min(n_sources, len(CLIPS)))]
    urls = presign.remote(clips)
    arms = []
    # mode="cap"  : the rarity-doctrine delete-test (variant 0 vs 2)
    # mode="seam" : the seam-candidate widening — BOTH arms at variant 0, so the
    #               only difference is which splices are OFFERED to the
    #               transitions sub-call. The overlay class needs no room at any
    #               of them, so this is measurable with no exemption and no
    #               component change.
    if mode == "cap":
        _pairs = ((0, "CAP", {}), (2, "NOCAP", {}))
    elif mode == "seam":
        _pairs = ((0, "NARROW", {}), (0, "WIDE", {"PROMPTLY_SEAM_CANDIDATES": "wide"}))
    else:
        # LEAN vs CONTROL at the PLAN stage. Delivered density says lean carries
        # 41% less MG; this says whether the model EMITS fewer MGs under lean
        # (prompt-side — the stripped per-moment prose was load-bearing scaffold)
        # or emits the same and they are CULLED later (gate-side). An explicit
        # PROMPTLY_LEAN_SCHEMA overrides the hash A/B, so the arm is forced
        # rather than drawn.
        _pairs = ((0, "CONTROL", {"PROMPTLY_LEAN_SCHEMA": "0"}),
                  (0, "LEAN", {"PROMPTLY_LEAN_SCHEMA": "1"}))
    for ci, k in enumerate(clips):
        for r in range(reps):
            for variant, cond, env in _pairs:
                arms.append({
                    "label": f"{cond}#{ci}.{r}", "clip": k.split('/')[-1][:24],
                    "variant": variant, "src": urls[k], "job_id": str(uuid.uuid4()),
                    "stagger_s": len(arms) * 12, "env": env,
                })
    print(f"=== {'DENSITY DELETE-TEST — cap PRESENT vs REMOVED' if mode == 'cap' else 'SEAM-CANDIDATE WIDENING — shot+broll only vs +mechanical splices'} ===")
    print(f"    {len(clips)} source(s) x {reps} rep(s) x 2 arms = {len(arms)} PLAN_ONLY runs, "
          f"no renders (~$0.10 each)")

    out = list(run_arm.map(arms))
    ok = [r for r in out if r.get("counts") and not r.get("error")]
    bad = [r for r in out if r not in ok]
    for r in bad:
        print(f"  ! {r.get('label')} {r.get('clip')}: "
              f"{r.get('error') or r.get('status')} degraded={r.get('degraded')}")
    if not ok:
        print("\n  NO USABLE PLANS — an absent read, not a zero. Nothing below is measurable.")
        return
    _deg = [r for r in ok if r.get("degraded")]
    if _deg:
        print(f"\n  ⚠️  {len(_deg)} run(s) show DEGRADE markers — a rescued plan is not the arm:")
        for r in _deg:
            print(f"      {r['label']} {r['clip']}: {r['degraded']}")

    print(f"\n  {'run':>10} {'clip':>26} {'out_s':>6} {'cuts':>5}  "
          + " ".join(f"{f.split('_')[0][:5]:>6}" for f in FAMILIES))
    for r in sorted(ok, key=lambda x: (x["clip"], x["variant"])):
        print(f"  {r['label']:>10} {r['clip']:>26} {str(r['out_dur_s']):>6} "
              f"{str(r['n_cuts']):>5}  "
              + " ".join(f"{r['counts'][f]:>6}" for f in FAMILIES))

    # ── PER 25s OF OUTPUT, PAIRED BY SOURCE ─────────────────────────────────
    def per25(r, fam):
        d = r.get("out_dur_s")
        return None if not d else 25.0 * r["counts"][fam] / d

    print(f"\n  ══ EVENTS PER 25s OF OUTPUT, BY FAMILY (paired on the same source) ══")
    header = f"  {'family':>18} {_A:>8} {_B:>8} {'delta':>8} {'ratio':>7}   per-source deltas"
    print(header)
    pairs = {}
    for r in ok:
        pairs.setdefault(r["clip"], {}).setdefault(r["label"].split("#")[0], []).append(r)

    _A, _B = ({'cap': ('CAP','NOCAP'), 'seam': ('NARROW','WIDE')}
              .get(mode, ('CONTROL','LEAN')))
    usable = [c for c, v in pairs.items() if v.get(_A) and v.get(_B)]
    print(f"  (complete pairs: {len(usable)}/{len(pairs)} sources)")
    totals = {}
    for fam in FAMILIES:
        capv, nocapv, deltas = [], [], []
        for c in usable:
            a = [per25(r, fam) for r in pairs[c][_A] if per25(r, fam) is not None]
            b = [per25(r, fam) for r in pairs[c][_B] if per25(r, fam) is not None]
            if not a or not b:
                continue
            am, bm = st.mean(a), st.mean(b)
            capv.append(am); nocapv.append(bm); deltas.append(bm - am)
        if not capv:
            continue
        A, B = st.mean(capv), st.mean(nocapv)
        totals[fam] = (A, B, deltas)
        ratio = (B / A) if A else float("inf") if B else 1.0
        print(f"  {fam:>18} {A:>8.2f} {B:>8.2f} {B - A:>+8.2f} {ratio:>6.2f}x   "
              + ", ".join(f"{d:+.1f}" for d in deltas))

    # ── ALL-FAMILY TOTAL, against the reference points ──────────────────────
    tA = sum(v[0] for v in totals.values())
    tB = sum(v[1] for v in totals.values())
    print(f"\n  {'TOTAL/25s':>18} {tA:>8.2f} {tB:>8.2f} {tB - tA:>+8.2f} "
          f"{(tB / tA if tA else 0):>6.2f}x")
    print(f"\n  Reference points: 7.76 measured (2026-08-01 MG density off DB), "
          f"structural ceiling 12.5, Zac's reference edit 16.7 per 25s.")
    print(f"  NOTE: those are MG-family numbers off DELIVERED renders. The rows above")
    print(f"  are PLAN EMISSION per family — comparable to each other and across arms,")
    print(f"  NOT directly to 7.76 until the same family and the same stage are cut.")

    # ── VERDICT — refuses a direction the spread does not support ───────────
    _d = totals.get("emphasis_moments", (0, 0, []))[2]
    print(f"\n  VERDICT")
    if len(usable) < 2:
        print(f"    n={len(usable)} paired source(s). A direction from one pair is a")
        print(f"    single Gemini draw, not a result. Re-run with --n-sources 4.")
    elif _d and all(x > 0 for x in _d):
        print(f"    emphasis rose on ALL {len(_d)} sources — the cap IS binding on emission.")
    elif _d and all(x < 0 for x in _d):
        print(f"    emphasis FELL on all {len(_d)} sources — removing the cap did not free")
        print(f"    emission; the ceiling is not this sentence.")
    else:
        print(f"    emphasis deltas disagree in sign ({', '.join(f'{x:+.1f}' for x in _d)}) —")
        print(f"    the arm effect is not separable from run-to-run variance at this n.")
    print(f"    Emission is what this measures. If emission rises and DELIVERED density")
    print(f"    does not, the ceiling is downstream culling and no prompt edit reaches it.")
