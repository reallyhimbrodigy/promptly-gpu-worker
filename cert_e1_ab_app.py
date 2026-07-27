"""E1+D2 A/B — drive handler.handler DIRECTLY (bypasses run_pipeline_bg, so NO
content-studio callback fires → zero analytics pollution / no push). Each arm is
one container via .map; returns edit_recipe + video_url + timing. Read density
locally before reporting. Validation pair first (density off/on), then fan out.
"""
import os, sys
sys.path.insert(0, "/")   # container mounts modal_app.py at /modal_app.py; / is NOT on sys.path at module-import time
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-e1-ab", image=image)
SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("promptly-cloudfront"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-lang-flags"),
]

# Real captioned showcase source (ca6202f9, 20s, "Clean and engaging edit").
SHOWCASE = "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1785106634357-F110DBA9-BD7B-4A59-9094-B2F22CF48D57_L0_001.mp4"


@app.function(secrets=SECRETS, cpu=16.0, memory=32768, timeout=2400)
def run_arm(arm: dict) -> dict:
    import time, uuid, traceback
    # Spread transcription starts: N identical concurrent Deepgram calls on the same
    # source overload it (2 arms fine, 6 time out). Stagger so calls barely overlap.
    if arm.get("stagger_s"):
        time.sleep(float(arm["stagger_s"]))
    os.environ["APP_URL"] = ""                     # no completion callback / progress posts
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""   # no phantom video_jobs rows (canonical cert setup)
    sys.path.insert(0, "/")
    import handler as H
    # upload_url AND public_url are REQUIRED (handler MISSING_FIELDS guard; and the HLS
    # export derives its manifest URL from public_url via splitext — omitting it raises
    # AFTER a fully-successful MP4 render → safe-edit rescue → corrupted recipe). Mirror
    # modal_app.py's canonical cert template (line ~1779): both point at the render key
    # in the CERT bucket (handler uploads with the container's OWN creds; only bucket/key
    # are parsed — never a presigned PUT).
    _render_key = f"e1-ab-cert/{arm['job_id']}/render.mp4"
    _url = f"https://thisismybucketagainwooo.s3.amazonaws.com/{_render_key}"
    body = {
        "job_id": arm["job_id"],
        "video_url": arm["src"],
        "vibe": arm.get("vibe", "Clean and engaging edit"),
        "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
        "upload_url": _url,
        "public_url": _url,
        "model": "flare",
        "supports_progressive": False,
        "premium_pipeline_enabled": False,
    }
    if arm.get("variant") is not None:
        body["density_variant"] = int(arm["variant"])  # 0=off 1=v1-add 2=L1-removal 3=L1+lever4
    elif arm.get("density"):
        body["density_test"] = True
    if arm.get("blur"):
        body["motion_blur_test"] = True
        body["motion_blur_samples"] = arm.get("samples", 6)
        body["motion_blur_shutter"] = arm.get("shutter", 180)
    t0 = time.time()
    # DEGRADATION SCAN (Zac's cert-validity rule 2026-07-27 (a)): tee the handler's
    # OWN stdout and scan for any salvage / rescue / safe-edit / render-degrade /
    # enhancement-drop / error-fallback signal. A rescued recipe is PLAUSIBLE, not
    # empty — a null check can't see it — so we detect it at the source. Tee (not
    # redirect) so live progress still reaches the modal log.
    import io
    _buf = io.StringIO(); _orig = sys.stdout
    class _Tee:
        def write(self, s):
            try: _orig.write(s)
            except Exception: pass
            _buf.write(s); return len(s)
        def flush(self):
            try: _orig.flush()
            except Exception: pass
    sys.stdout = _Tee()
    try:
        res = H.handler({"input": body})
    except Exception as e:
        sys.stdout = _orig
        return {"arm": arm["label"], "error": f"{type(e).__name__}: {str(e)[:300]}",
                "tb": traceback.format_exc()[-800:], "wall_s": round(time.time() - t0, 1)}
    finally:
        sys.stdout = _orig
    _logs = _buf.getvalue()
    _DEGRADE = ["[safe-edit] engaged", "safe_edit_rescue", "action=safe_edit",
                "[render-degrade]", "render_stripped", "[enhancement-guard]",
                "salvaged post-cuts plan", "[error-fallback]", "error-fallback]",
                "outer:UNKNOWN", "safe_edit_fallback", "recipe_wall_safe_edit"]
    _hits = sorted({m for m in _DEGRADE if m in _logs})
    rec = res.get("edit_recipe") if isinstance(res, dict) else None
    return {
        "arm": arm["label"],
        "status": res.get("status") if isinstance(res, dict) else "?",
        "raw_error": (res.get("error") or res.get("error_code")) if isinstance(res, dict) else None,
        "res_keys": list(res.keys())[:20] if isinstance(res, dict) else None,
        "model": res.get("model") if isinstance(res, dict) else None,
        "route_premium": res.get("route_premium") if isinstance(res, dict) else None,
        "degraded_markers": _hits,
        "video_url": res.get("video_url") if isinstance(res, dict) else None,
        "render_time": res.get("render_time") if isinstance(res, dict) else None,
        "pipeline_time": res.get("pipeline_time") if isinstance(res, dict) else None,
        "stage_timings": res.get("stage_timings") if isinstance(res, dict) else None,
        "edit_recipe": rec,
        "wall_s": round(time.time() - t0, 1),
    }


def _density(rec):
    """Component events/sec + max dead stretch from a recipe (flat OR {plan:...})."""
    r = rec.get("plan") if isinstance(rec, dict) and "plan" in rec else rec
    if not isinstance(r, dict):
        return None
    cuts = [c for c in (r.get("cuts") or []) if isinstance(c, dict)
            and isinstance(c.get("source_start"), (int, float))
            and isinstance(c.get("source_end"), (int, float))]
    if not cuts:
        return {"note": "no cuts in recipe", "keys": list(r.keys())[:20]}
    cum = 0.0; seg = []
    for c in cuts:
        sp = c.get("speed") or 1; d = (c["source_end"] - c["source_start"]) / sp
        seg.append((c["source_start"], c["source_end"], cum, sp)); cum += d
    outdur = cum

    def mp(ts):
        for ss, se, osf, sp in seg:
            if ts is not None and ss - 1e-6 <= ts <= se + 1e-6:
                return osf + (ts - ss) / sp
        return None
    ev = []
    for i in range(1, len(seg)):
        ev.append(seg[i][2])
    for i, c in enumerate(cuts):
        if c.get("_zoom_effect"):
            ev.append(seg[i][2])
        if c.get("transition_out") and c["transition_out"] != "none":
            ev.append(seg[i][2] + (seg[i][1] - seg[i][0]) / seg[i][3])
    for m in (r.get("motion_graphics") or []):
        t = mp(m.get("_source_start")); ev.append(t) if t is not None else None
    for o in (r.get("text_overlays") or []):
        t = mp(o.get("_source_start")); ev.append(t) if t is not None else None
    for b in (r.get("broll_clips") or []):
        t = mp(b.get("timestamp") if isinstance(b.get("timestamp"), (int, float)) else b.get("_source_start"))
        ev.append(t) if t is not None else None
    comp = sorted(e for e in ev if e is not None and 0 <= e <= outdur + 0.01)
    merged = []
    for e in comp:
        if not merged or e - merged[-1] > 0.25:
            merged.append(e)
    prev = 0.0; gaps = []
    for t in merged:
        gaps.append(t - prev); prev = t
    gaps.append(outdur - prev)
    byt = {"emph_zoom": sum(1 for c in cuts if c.get("_zoom_effect")),
           "mg": len(r.get("motion_graphics") or []),
           "broll": len(r.get("broll_clips") or []),
           "overlay": len(r.get("text_overlays") or [])}
    return {"outdur": round(outdur, 1), "events": len(merged),
            "events_per_s": round(len(merged) / outdur, 3) if outdur else 0,
            "max_dead_s": round(max(gaps + [0]), 1), "by_type": byt}


@app.local_entrypoint()
def main():
    import json, uuid, statistics
    N = 3  # arms per condition — noise-guard (n>1 so the ratio isn't a single draw)
    arms = []
    for i in range(N):
        arms.append({"label": f"OFF#{i}", "cond": "OFF", "variant": 0, "src": SHOWCASE,
                     "job_id": str(uuid.uuid4()), "stagger_s": len(arms) * 15})
        arms.append({"label": f"ON#{i}",  "cond": "ON",  "variant": 2, "src": SHOWCASE,
                     "job_id": str(uuid.uuid4()), "stagger_s": len(arms) * 15})
    spec = {a["label"]: a for a in arms}
    print(f"=== E1 A/B — OFF (variant 0) vs L1-REMOVAL (variant 2 = delete 3-5 cap ALONE), n={N} ===")
    out = list(run_arm.map(arms))
    by_label = {}
    for r in out:
        lbl = r.get("arm"); d = _density(r.get("edit_recipe")); by_label[lbl] = (r, d)
        print(f"\n--- {lbl} ---")
        if r.get("error"):
            print("  ERROR:", r["error"]); print("  tb:", r.get("tb", "")[-400:])
        else:
            print("  status:", r.get("status"), "model:", r.get("model"),
                  "degraded:", r.get("degraded_markers"), "video:", (r.get("video_url") or "")[:70])
            print("  wall_s:", r.get("wall_s"), "render:", r.get("render_time"), "pipeline:", r.get("pipeline_time"))
            if not r.get("edit_recipe"):
                print("  raw_error:", r.get("raw_error"), "res_keys:", r.get("res_keys"))
        print("  DENSITY:", json.dumps(d))

    def _valid(d):
        return (isinstance(d, dict) and isinstance(d.get("events_per_s"), (int, float))
                and isinstance(d.get("events"), int))

    # ── CERT VALIDITY (Zac's rule 2026-07-27): detect DEGRADED-BUT-VALID, not just
    #    null. A rescued recipe is plausible, not empty — a null check can't see it.
    failures = []
    for lbl in spec:
        r, d = by_label.get(lbl, (None, None))
        if r is None:
            failures.append(f"{lbl}: arm did not return"); continue
        if r.get("error"):
            failures.append(f"{lbl}: raised {r.get('error')} | tb={r.get('tb','')[-250:]}")
        if r.get("degraded_markers"):            # (a)
            failures.append(f"{lbl}: DEGRADATION fired {r['degraded_markers']} — arm INVALID "
                            f"(rescued recipe is plausible, not clean); status={r.get('status')}")
        if r.get("model") and r.get("model") != "flare":
            failures.append(f"{lbl}: model={r.get('model')} (expected flare) — wrong route")
        if r.get("wall_s") is None:              # (d)
            failures.append(f"{lbl}: wall_s is None")
        if not r.get("edit_recipe"):
            failures.append(f"{lbl}: no edit_recipe | raw_error={r.get('raw_error')} status={r.get('status')}")
        if not _valid(d):
            failures.append(f"{lbl}: no density | d={json.dumps(d)} raw_error={r.get('raw_error')}")

    off_d = [d for lbl, (r, d) in by_label.items() if spec[lbl]["cond"] == "OFF" and _valid(d)]
    on_d  = [d for lbl, (r, d) in by_label.items() if spec[lbl]["cond"] == "ON"  and _valid(d)]

    if off_d:                                    # (c) OFF matches known baseline (~0.23/s)
        _off_mean = statistics.mean(x["events_per_s"] for x in off_d)
        if not (0.10 <= _off_mean <= 0.55):
            failures.append(f"(c) OFF baseline: mean {_off_mean:.3f}/s outside [0.10,0.55] "
                            f"— control is not the control (baseline ≈ 0.23/s)")

    def _sig(d): return (d["events"], tuple(sorted((d.get("by_type") or {}).items())))
    if off_d and on_d:                           # (b) arms NOT identical
        if {_sig(x) for x in off_d} == {_sig(x) for x in on_d}:
            failures.append(f"(b) arms IDENTICAL: OFF and ON produced the same event-signature set "
                            f"{sorted({_sig(x) for x in off_d})} — flag never applied or both degraded")

    if failures:
        raise RuntimeError("E1 A/B INVALID — refusing to print a verdict.\n  " + "\n  ".join(failures))

    off = statistics.mean(x["events_per_s"] for x in off_d)
    on  = statistics.mean(x["events_per_s"] for x in on_d)
    ratio = on / off if off else 0
    off_dead = statistics.mean(x["max_dead_s"] for x in off_d)
    on_dead  = statistics.mean(x["max_dead_s"] for x in on_d)
    def _mean_bytype(series):
        return {k: round(statistics.mean(x["by_type"].get(k, 0) for x in series), 1)
                for k in ("emph_zoom", "mg", "broll", "overlay")}
    off_walls = [by_label[l][0].get("wall_s") for l in spec if spec[l]["cond"] == "OFF"]
    on_walls  = [by_label[l][0].get("wall_s") for l in spec if spec[l]["cond"] == "ON"]

    print(f"\n===== E1 VERDICT (n={len(off_d)} OFF / {len(on_d)} ON, all arms VALID) =====")
    print(f"EVENTS/S: OFF mean={off:.3f} (range {min(x['events_per_s'] for x in off_d):.3f}-{max(x['events_per_s'] for x in off_d):.3f})  "
          f"ON mean={on:.3f} (range {min(x['events_per_s'] for x in on_d):.3f}-{max(x['events_per_s'] for x in on_d):.3f})")
    print(f"RATIO:    {ratio:.2f}x  [{'MOVED >=2x — flip-eligible' if ratio >= 2 else 'INCONCLUSIVE <2x — do not flip'}]")
    print(f"TARGET:   reference 0.8-1.1/s — ON {'HITS' if 0.8 <= on <= 1.1 else f'MISSES ({on:.3f})'}")
    print(f"DEAD_MAX: OFF mean={off_dead:.1f}s  ON mean={on_dead:.1f}s  "
          f"(informational — a breather is a MISS only if it held a skipped beat, NOT a >3s quota)")
    print(f"BY_TYPE:  OFF {json.dumps(_mean_bytype(off_d))}  ON {json.dumps(_mean_bytype(on_d))}")
    print(f"WALL_S:   OFF {off_walls}  ON {on_walls}  (concurrent, cold — NOT a latency signal)")
    print(f"VALIDITY: (a) 0 degradation all arms  (b) arms differ  (c) OFF≈baseline  (d) all measured — PASS")
