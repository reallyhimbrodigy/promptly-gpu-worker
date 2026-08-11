"""cert_adapter_contract.py — Rule-1 gate for the input-adapter contract
(LANE-SEAM Step 1). Pure-local, stdlib-only, $0 — no Modal, no network.

What regression each check makes impossible:
  1. IDENTITY   — core_inputs() must return the SAME objects (is-identity)
                  that entered adapt_single_video(). If anyone ever makes the
                  adapter transform instead of carry, flag-ON stops being
                  plan-identical and this fails.
  2. DARK-OFF   — with env unset and no per-job override, enabled() is False.
                  A flipped default ships through here first.
  3. STRUCTURE  — adapter #1 rejects 0/2 attachments, image kind, missing
                  duration (loud ValueError, never a silent wrong plan).
  4. SOCKETS    — adapters #2/#3 stay honest stubs until a capability lane
                  fills them (NotImplementedError, not a quiet no-op).
  5. WIRING     — handler.py actually routes through the contract AND
                  modal_app.py mounts the module. Kills both halves of the
                  progressive_publish class: wiring-without-mount and
                  mount-without-wiring. Also fingerprints the off-path alias
                  lines so the byte-identical-off structure can't drift.

Run: python3 cert_adapter_contract.py   (exit 0 = PASS, prints per-check)
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

_checks = []


def check(name):
    def deco(fn):
        _checks.append((name, fn))
        return fn
    return deco


@check("identity: core_inputs returns the very same objects")
def _identity():
    import adapter_contract as adc
    words = [{"word": "hello", "start": 0.1, "end": 0.4}]
    path = "/tmp/source.mp4"
    vibe = "make it punchy"
    dur = 43.2
    env = adc.adapt_single_video(
        user_text=vibe,
        attachments=[adc.FootageRef(local_path=path, kind="video",
                                    duration_s=dur, source_url="s3://x")],
        user_context={"job_id": "j1", "mode": "full"},
        word_timings=words,
    )
    v_path, v_vibe, v_dur, v_words = adc.core_inputs(env)
    assert v_path is path, "video_path not identity-carried"
    assert v_vibe is vibe, "vibe not identity-carried"
    assert v_dur == dur, "duration changed"
    assert v_words is words, "word_timings not identity-carried (second clock!)"
    assert env.source_kind == adc.SINGLE_VIDEO
    assert env.intent_hints["job_id"] == "j1"


@check("dark-off: enabled() defaults False; per-job override works")
def _dark():
    import adapter_contract as adc
    saved = os.environ.pop("PROMPTLY_ADAPTER_V1", None)
    try:
        assert adc.enabled() is False
        assert adc.enabled({}) is False
        assert adc.enabled({"adapter_v1_test": True}) is True
        os.environ["PROMPTLY_ADAPTER_V1"] = "1"
        assert adc.enabled({}) is True
    finally:
        if saved is None:
            os.environ.pop("PROMPTLY_ADAPTER_V1", None)
        else:
            os.environ["PROMPTLY_ADAPTER_V1"] = saved


@check("structure: adapter #1 rejects malformed attachments loudly")
def _structure():
    import adapter_contract as adc
    ok = adc.FootageRef(local_path="/tmp/a.mp4", kind="video", duration_s=5.0)
    for bad_attachments in (
        [],
        None,
        [ok, ok],
        [adc.FootageRef(local_path="/tmp/a.png", kind="image", duration_s=1.0)],
        [adc.FootageRef(local_path="", kind="video", duration_s=5.0)],
        [adc.FootageRef(local_path="/tmp/a.mp4", kind="video", duration_s=0.0)],
    ):
        try:
            adc.adapt_single_video("v", bad_attachments)
        except ValueError:
            continue
        raise AssertionError("accepted malformed attachments: %r"
                             % (bad_attachments,))


@check("sockets: adapters #2/#3 are honest stubs")
def _sockets():
    import adapter_contract as adc
    for fn, args in ((adc.adapt_multi_clip, ("v", [])),
                     (adc.adapt_image_still, ("v", []))):
        try:
            fn(*args)
        except NotImplementedError:
            continue
        raise AssertionError("%s no longer raises NotImplementedError — if a "
                             "capability lane filled it, extend this cert with "
                             "its contract instead" % fn.__name__)


@check("wiring: handler routes through the contract; modal_app mounts it")
def _wiring():
    with open(os.path.join(HERE, "handler.py")) as f:
        h = f.read()
    with open(os.path.join(HERE, "modal_app.py")) as f:
        m = f.read()
    for needle, why in (
        ("import adapter_contract as _adc", "handler touchpoint import"),
        ("_adc.enabled(input_data)", "flag check at the call site"),
        ("_adc.adapt_single_video(", "adapter #1 invocation"),
        ("_adc.core_inputs(_seam_env)", "envelope→core mapping"),
        ('_ledger_defect("missing_module", "adapter_contract"',
         "loud missing-mount ledger"),
    ):
        assert needle in h, "handler.py lost: %s (%s)" % (needle, why)
    # off-path alias fingerprint — the structure that makes flag-off
    # provably value-identical (aliases, never rebinding closure vars)
    assert re.search(
        r"_seam_video_path, _seam_vibe = _raw_source, vibe\n"
        r"\s*_seam_duration, _seam_words = source_duration, _dg_words", h), \
        "off-path alias fingerprint drifted in handler.py"
    assert re.search(
        r"video_path=_seam_video_path,\s*\n\s*vibe=_seam_vibe,\s*\n"
        r"\s*duration=_seam_duration,", h), \
        "generate_edit_gemini no longer consumes the seam aliases"
    assert 'add_local_file("adapter_contract.py", "/adapter_contract.py")' \
        in m, "modal_app.py mount for adapter_contract.py missing " \
              "(the progressive_publish class)"


def main():
    failed = 0
    for name, fn in _checks:
        try:
            fn()
            print("PASS  %s" % name)
        except Exception as e:
            failed += 1
            print("FAIL  %s — %s: %s" % (name, type(e).__name__, e))
    print("cert_adapter_contract: %d/%d PASS"
          % (len(_checks) - failed, len(_checks)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
