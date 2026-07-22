"""Preservation harness — Brick 1 of the general-editor build.

Freezes today's behavior at four seams so the general-editor refactor
(assemble(CORE, blocks), PerceptionResult, timeline currency, router) can be
proven byte-identical / inert for the live talking-head + Lumen paths BEFORE
any of it is touched. Same discipline as the multilingual inert proofs.

Locks:
  1. golden-diff        — _build_post_cuts_prompt output frozen per fixture.
  2. additive-inert     — a today-plan round-trips through PromptlyRenderInput
                          under extra="forbid" with no semantic change.
  3. router-inertness   — _route_guidance (Step 1) returns {"TALKING_HEAD"} for
                          the TH + Lumen perception fixtures.
  4. n1-anchor-identity — the isolatable anchoring walker
                          (_translate_post_cut_anchors_to_src) is frozen; N=1
                          projection must reproduce it exactly.

Run modes:
  python preservation_harness.py capture   # freeze goldens (against today's code)
  python preservation_harness.py verify    # assert current == goldens (the gate)

validate_deploy.py wraps verify() lock-by-lock as @check gates.
"""
import os
import sys
import json
import hashlib
import difflib

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
GOLDEN_DIR = os.path.join(_HERE, "preservation_golden")

# Env vars whose state changes prompt BYTES — pinned per fixture so the golden
# is deterministic regardless of the shell the gate runs in.
_ENV_KEYS = ["PROMPTLY_LEVER3", "PROMPTLY_EDIT_IN_LANGUAGE"]


def _with_env(env, fn):
    saved = {k: os.environ.get(k) for k in _ENV_KEYS}
    try:
        for k in _ENV_KEYS:
            v = env.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return fn()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ── Lock 1 fixtures — cover EVERY conditional branch of _build_post_cuts_prompt
# so the refactor cannot silently drop one. Prod runs LEVER3=1 + EDIT_IN_LANGUAGE=1
# baked; we also freeze the flags-off state to catch env-conditional drift.
_SIGNALS = dict(
    shot_changes=[2.3, 5.1, 9.8, 14.2, 21.7],
    vocal_emphasis=[{"t": 3.1, "score": 0.82}, {"t": 12.4, "score": 0.61}, {"t": 19.0, "score": 0.74}],
    source_loudness={"peak_db": -3.2, "rms_db": -18.5, "noise_floor_db": -52.0},
    face_visibility=[{"from_s": 0.0, "to_s": 8.0, "visible": True},
                     {"from_s": 8.0, "to_s": 10.0, "visible": False},
                     {"from_s": 10.0, "to_s": 30.0, "visible": True}],
    speaker_positions={0: {"side": "center", "avg_cx": 540.0, "samples": 42}},
    off_center=False,
    shot_scale={"label": "close_up", "median_w": 380, "median_h": 420},
    face_zone=[{"from_s": 0.0, "to_s": 15.0, "zone": "upper_third_safe"},
               {"from_s": 15.0, "to_s": 30.0, "zone": "center_band"}],
    user_style_profile=None,
    platform_style_note=None,
)

_PRIOR = {
    "caption_style": "CleanCut",
    "broll_clips": [{"keyword": "city skyline", "start_word_index": 0, "end_word_index": 5}],
}


def lock1_fixtures():
    base = dict(vibe="punchy", duration=30.0)
    return [
        # name, env, kwargs
        ("th_base_flagsoff", {}, dict(base)),
        ("th_base_lever3", {"PROMPTLY_LEVER3": "1"}, dict(base)),
        ("th_signals", {"PROMPTLY_LEVER3": "1"}, {**base, "vibe": "make it punchy and viral", "duration": 45.0, **_SIGNALS}),
        ("lumen_premium", {"PROMPTLY_LEVER3": "1"}, {**base, "premium": True}),
        ("th_lang_es", {"PROMPTLY_LEVER3": "1", "PROMPTLY_EDIT_IN_LANGUAGE": "1"}, {**base, "source_language": "Spanish"}),
        ("th_guided_redraft", {"PROMPTLY_LEVER3": "1"}, {**base, "prior_plan": _PRIOR, "prior_plan_change_request": "pace the middle faster"}),
        ("combo_all", {"PROMPTLY_LEVER3": "1", "PROMPTLY_EDIT_IN_LANGUAGE": "1"},
         {**base, "vibe": "viral", "duration": 52.0, "premium": True, "source_language": "Spanish", **_SIGNALS}),
    ]


def lock1_build(fx_env, fx_kwargs):
    import handler
    return _with_env(fx_env, lambda: handler._build_post_cuts_prompt(**fx_kwargs))


def _lock1_path(name, part):
    return os.path.join(GOLDEN_DIR, f"prompt__{name}.{part}.txt")


def capture_lock1():
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    manifest = {}
    for name, env, kwargs in lock1_fixtures():
        # determinism self-check: build twice, must match
        sys1, usr1 = lock1_build(env, kwargs)
        sys2, usr2 = lock1_build(env, kwargs)
        assert sys1 == sys2 and usr1 == usr2, f"NON-DETERMINISTIC prompt for fixture {name}"
        with open(_lock1_path(name, "system"), "w") as f:
            f.write(sys1)
        with open(_lock1_path(name, "user"), "w") as f:
            f.write(usr1)
        manifest[name] = {
            "system_sha": _sha(sys1), "user_sha": _sha(usr1),
            "system_len": len(sys1), "user_len": len(usr1),
        }
    with open(os.path.join(GOLDEN_DIR, "lock1_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    return manifest


def verify_lock1():
    """Returns (ok, failures[]). The gate for the prompt refactor."""
    with open(os.path.join(GOLDEN_DIR, "lock1_manifest.json")) as f:
        manifest = json.load(f)
    failures = []
    for name, env, kwargs in lock1_fixtures():
        if name not in manifest:
            failures.append(f"{name}: no golden (fixture set changed — recapture intentionally)")
            continue
        sysp, usrp = lock1_build(env, kwargs)
        for part, cur in (("system", sysp), ("user", usrp)):
            exp_sha = manifest[name][f"{part}_sha"]
            if _sha(cur) != exp_sha:
                with open(_lock1_path(name, part)) as f:
                    golden = f.read()
                diff = "\n".join(list(difflib.unified_diff(
                    golden.splitlines(), cur.splitlines(),
                    fromfile=f"golden/{name}.{part}", tofile=f"current/{name}.{part}", lineterm=""))[:25])
                failures.append(f"{name}.{part}: BYTE DRIFT vs golden\n{diff}")
    return (len(failures) == 0, failures)


# ══ LOCK 2 — additive-inert vocabulary ═══════════════════════════════════════
# A today-plan must validate under extra="forbid" and round-trip through
# model_dump(exclude_defaults=True) unchanged, so a NEW optional []/None field
# (Step 1+) is provably inert: it never appears in an existing plan's dump.

def lock2_render_inputs():
    clip0 = {"id": "c0", "startFromFrames": 0, "playbackRate": 1.0, "durationInFrames": 120}
    clip1 = {"id": "c1", "startFromFrames": 120, "playbackRate": 1.0, "durationInFrames": 90}
    ri_min = {
        "sourceUrl": "s3://bucket/src.mp4", "fps": 60.0, "width": 1080, "height": 1920,
        "totalDurationInFrames": 120, "clips": [clip0],
        "transitions": [], "broll": [], "textOverlays": [], "motionGraphics": [],
    }
    ri_tco = {
        **ri_min, "clips": [clip0, clip1], "totalDurationInFrames": 210,
        "tightCutOverlays": [
            {"atFrame": 50, "type": "LightLeak", "durationInFrames": 11},
            {"atFrame": 130, "type": "ShutterFlash", "durationInFrames": 11},
        ],
    }
    return {"ri_min": ri_min, "ri_tco": ri_tco}


def _lock2_dump(blob):
    import render_schemas
    parsed = render_schemas.PromptlyRenderInput.model_validate(blob)
    return parsed.model_dump(exclude_defaults=True)


def capture_lock2():
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    golden = {name: _lock2_dump(blob) for name, blob in lock2_render_inputs().items()}
    with open(os.path.join(GOLDEN_DIR, "lock2_golden.json"), "w") as f:
        json.dump(golden, f, indent=2, sort_keys=True)
    return golden


def verify_lock2():
    with open(os.path.join(GOLDEN_DIR, "lock2_golden.json")) as f:
        golden = json.load(f)
    failures = []
    for name, blob in lock2_render_inputs().items():
        dump = _lock2_dump(blob)
        # normalize through json so tuple/list + key-order match the stored golden
        cur = json.loads(json.dumps(dump, sort_keys=True))
        exp = golden.get(name)
        if cur != exp:
            failures.append(f"{name}: render-input dump drift (a schema change altered an EXISTING plan's semantics)")
        # inertness demonstration: empty additive fields must NOT appear in the dump
        for additive in ("generatedScenes", "tightCutOverlays", "caption", "outro"):
            if name == "ri_min" and additive in cur:
                failures.append(f"{name}: additive field {additive!r} leaked into a minimal plan's dump — not inert")
    return (len(failures) == 0, failures)


# ══ LOCK 3 — router inertness ════════════════════════════════════════════════
# _route_guidance must resolve TALKING_HEAD + Lumen(premium) perception to
# exactly {"TALKING_HEAD"}. When Step 1 adds the MUSIC branch, this stays green,
# proving a real talking-head can never reach a changed block set.

def _lock3_perceptions():
    import general_editor as ge
    th = ge.PerceptionResult(content_class="talking_head", has_speech=True,
                             has_audio=True, faces=True, loudness={"rms_db": -18.0})
    music = ge.PerceptionResult(content_class="music", has_speech=False,
                                has_audio=True, faces=False, beat_grid=[0.5, 1.0, 1.5])
    return th, music


def _with_hype_flag(value, fn):
    saved = os.environ.get("PROMPTLY_HYPE_MODE")
    try:
        if value is None:
            os.environ.pop("PROMPTLY_HYPE_MODE", None)
        else:
            os.environ["PROMPTLY_HYPE_MODE"] = value
        return fn()
    finally:
        if saved is None:
            os.environ.pop("PROMPTLY_HYPE_MODE", None)
        else:
            os.environ["PROMPTLY_HYPE_MODE"] = saved


def verify_lock3():
    import general_editor as ge
    th, music = _lock3_perceptions()
    failures = []

    def _chk(label, perception, req, expected):
        got = ge._route_guidance(perception, req)
        if got != expected:
            failures.append(f"{label}: _route_guidance -> {got}, expected {expected}")

    # (1) FLAG OFF = production default = fully INERT/DARK. A no-speech music clip
    # routes to TALKING_HEAD (today's NO_SPEECH reject then fires) — byte-identical.
    _with_hype_flag(None, lambda: (
        _chk("flagoff/talking_head", th, None, {"TALKING_HEAD"}),
        _chk("flagoff/lumen_premium", th, {"premium": True}, {"TALKING_HEAD"}),
        _chk("flagoff/music_no_speech_INERT", music, None, {"TALKING_HEAD"}),
    ))
    # (2) FLAG ON: a real talking-head STILL routes to TALKING_HEAD (speech always
    # wins) — the flag can never touch the live path. Only a no-speech+audio+beat
    # clip activates HYPE_MUSIC.
    _with_hype_flag("1", lambda: (
        _chk("flagon/talking_head_UNTOUCHED", th, None, {"TALKING_HEAD"}),
        _chk("flagon/lumen_UNTOUCHED", th, {"premium": True}, {"TALKING_HEAD"}),
        _chk("flagon/music_no_speech_ACTIVATES", music, None, {"HYPE_MUSIC"}),
    ))
    return (len(failures) == 0, failures)


# ══ LOCK 4 — N=1 anchor identity ═════════════════════════════════════════════
# Freeze the isolatable word-index→source walker (_translate_post_cut_anchors_to_src).
# When Step 0 demotes word_index to the N=1 timeline projection, this math must be
# byte-identical. (Full end-to-end frame identity is additionally frozen from a real
# TH render before the projection SEAM is touched — see report note.)

def lock4_fixtures():
    plan = {
        "thumbnail_word_index": 3,
        "caption_position_changes": [{"word_index": 2, "position": "top"},
                                     {"word_index": 6, "position": "bottom"}],
        "emphasis_moments": [{"word_indices": [1, 2], "type": "punch"},
                             {"word_indices": [7], "type": "reveal"}],
        "motion_graphics": [{"start_word_index": 0, "end_word_index": 4, "type": "StatCard"}],
        "broll_clips": [{"start_word_index": 3, "end_word_index": 8, "keyword": "city"}],
        "cut_refinements": [{"start_word_index": 5, "end_word_index": 6, "reason": "filler"}],
        "caption_style": "Gadzhi",
    }
    new_to_src = {i: i * 2 for i in range(10)}   # kept idx -> src idx
    return {"plan_full": (plan, new_to_src)}


def capture_lock4():
    import handler
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    golden = {}
    for name, (plan, n2s) in lock4_fixtures().items():
        out = handler._translate_post_cut_anchors_to_src(plan, n2s)
        golden[name] = json.loads(json.dumps(out, sort_keys=True, default=str))
    with open(os.path.join(GOLDEN_DIR, "lock4_golden.json"), "w") as f:
        json.dump(golden, f, indent=2, sort_keys=True)
    return golden


def verify_lock4():
    import handler
    with open(os.path.join(GOLDEN_DIR, "lock4_golden.json")) as f:
        golden = json.load(f)
    failures = []
    for name, (plan, n2s) in lock4_fixtures().items():
        out = handler._translate_post_cut_anchors_to_src(plan, n2s)
        cur = json.loads(json.dumps(out, sort_keys=True, default=str))
        if cur != golden.get(name):
            failures.append(f"{name}: anchor-walker output drift (N=1 projection math changed)")
    return (len(failures) == 0, failures)


# ══ LOCK 5 — assemble() dispatch seam byte-identity (Step 0) ═════════════════
# assemble_editorial_prompt({TALKING_HEAD}, **kwargs) must reproduce the frozen
# _build_post_cuts_prompt golden EXACTLY — proves the refactored dispatch is
# byte-identical for pure-speech (same Gemini cache key).

def verify_lock5():
    import handler
    with open(os.path.join(GOLDEN_DIR, "lock1_manifest.json")) as f:
        manifest = json.load(f)
    failures = []
    for name, env, kwargs in lock1_fixtures():
        if name not in manifest:
            continue
        sysp, usrp = _with_env(env, lambda k=kwargs: handler.assemble_editorial_prompt({"TALKING_HEAD"}, **k))
        for part, cur in (("system", sysp), ("user", usrp)):
            if _sha(cur) != manifest[name][f"{part}_sha"]:
                failures.append(f"{name}.{part}: assemble seam DRIFT vs golden (dispatch not byte-identical)")
    return (len(failures) == 0, failures)


# ══ LOCK 6 — perception + timeline contract sanity / new-field inertness ══════

def verify_lock6():
    import general_editor as ge
    import dataclasses, json as _j
    failures = []
    p = ge.build_perception(has_speech=True, has_audio=True, faces=True,
                            loudness={"rms_db": -18.0}, scenes=[1.0, 2.0], content_class="talking_head")
    d = dataclasses.asdict(p)
    try:
        _j.dumps(d)   # must be JSON-safe — it is stored on edit_plan
    except Exception as e:
        failures.append(f"PerceptionResult asdict not JSON-safe: {e}")
    for k, exp in (("has_music", False), ("beat_grid", []), ("motion_curve", [])):
        if d.get(k) != exp:
            failures.append(f"perception new field {k!r} not inert-default (got {d.get(k)!r})")
    if not (d.get("has_speech") and d.get("content_class") == "talking_head"):
        failures.append("perception did not carry today's speech signals")
    tl = ge.Timeline(clips=[ge.TimelineClip(source_index=0, in_frame=0, out_frame=120)])
    if not tl.is_single_source:
        failures.append("N=1 Timeline not recognized as single-source (would divert N=1 off the current path)")
    return (len(failures) == 0, failures)


_LOCKS = [
    ("lock1_prompt_golden_diff", verify_lock1),
    ("lock2_additive_inert_vocab", verify_lock2),
    ("lock3_router_inertness", verify_lock3),
    ("lock4_n1_anchor_identity", verify_lock4),
    ("lock5_assemble_seam_identity", verify_lock5),
    ("lock6_perception_timeline_contract", verify_lock6),
]


def capture_all():
    m1 = capture_lock1()
    g2 = capture_lock2()
    g4 = capture_lock4()
    return {"lock1": len(m1), "lock2": len(g2), "lock4": len(g4)}


def verify_all():
    results = []
    for name, fn in _LOCKS:
        ok, fails = fn()
        results.append((name, ok, fails))
    return results


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if mode == "capture":
        counts = capture_all()
        m = capture_lock1()
        print(f"[capture] froze goldens: {counts}")
        for n, v in m.items():
            print(f"  lock1 {n}: system={v['system_len']}b user={v['user_len']}b")
    elif mode == "verify":
        allok = True
        for name, ok, fails in verify_all():
            print(f"[verify] {name}: {'GREEN' if ok else 'RED'}")
            for fl in fails:
                print("   FAIL:", fl[:400])
            allok = allok and ok
        print(f"\nBRICK 1: {'ALL GREEN' if allok else 'RED'}")
        sys.exit(0 if allok else 1)
