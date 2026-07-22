"""HYPE_MUSIC editorial-half unit tests — deterministic, local, no Gemini, no
render. Correctness bar: the projection always yields a schema-valid
PromptlyRenderInput; the prompt is beat-anchored and NEVER instructs adding music.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hype_editor as he
import render_schemas as rs


def _sample_plan():
    return he.HypePlan(
        clips=[he.HypeClip(start_s=0.0, end_s=1.5, zoom="SnapReframe", punch=True),
               he.HypeClip(start_s=1.5, end_s=3.0, speed=1.5),
               he.HypeClip(start_s=3.0, end_s=5.0, zoom="StagedPush", punch=True)],
        transitions=[he.HypeTransition(after_clip=1, type="ShutterFlash")],
        motion_graphics=[he.HypeMG(start_s=0.0, end_s=1.2, type="Stamp", text="SEND IT")],
        outro="fade_black")


def test_projection_is_schema_valid():
    ri = he.project_hype_plan(_sample_plan(), "s3://b/src.mp4", 30.0, 6.0)
    parsed = rs.PromptlyRenderInput.model_validate(ri)  # extra=forbid — the bar
    assert len(parsed.clips) == 3
    assert parsed.caption is None          # no speech -> caption-less first-class
    assert parsed.totalDurationInFrames > 0


def test_projection_fail_open_drops_invalid_types():
    bad = he.HypePlan(
        clips=[he.HypeClip(start_s=0, end_s=2, zoom="NotAZoom")],
        transitions=[he.HypeTransition(after_clip=0, type="Bogus")],
        motion_graphics=[he.HypeMG(start_s=0, end_s=1, type="Fake")])
    ri = he.project_hype_plan(bad, "s3://b/s.mp4", 30.0, 2.0)
    rs.PromptlyRenderInput.model_validate(ri)               # still valid
    assert ri["clips"][0].get("zoomEffect") is None        # invalid zoom dropped
    assert ri["transitions"] == [] and ri["motionGraphics"] == []


def test_speed_maps_to_output_frames():
    plan = he.HypePlan(clips=[he.HypeClip(start_s=0.0, end_s=3.0, speed=2.0)])
    ri = he.project_hype_plan(plan, "s3://b/s.mp4", 30.0, 3.0)
    # 3.0s src @30fps = 90 src frames; speed 2.0 -> ~45 output frames
    assert ri["clips"][0]["durationInFrames"] == 45
    assert ri["clips"][0]["playbackRate"] == 2.0


def test_prompt_is_beat_anchored_and_never_adds_music():
    sysp, usr = he.build_hype_prompt(vibe="car edit hype", duration=6.0,
                                     beat_grid=[0.5, 1.0, 1.5, 2.0], scenes=[3.0])
    low = (sysp + usr).lower()
    assert "beat" in low and "0.50" in usr            # beat grid injected
    # the no-music rule must be explicit and never contradicted
    assert "never add" in low and "own" in low
    # must NOT instruct supplying/adding a soundtrack
    assert "add a soundtrack" not in low and "supply music" not in low


def test_assemble_routes_hype_block():
    import handler
    sysp, usr = handler.assemble_editorial_prompt(
        {"HYPE_MUSIC"}, vibe="gym montage", duration=10.0, beat_grid=[0.5, 1.0])
    assert "HYPE" in sysp and "beat" in sysp.lower()
    # and it is NOT the talking-head monolith
    th_sys, _ = handler.assemble_editorial_prompt({"TALKING_HEAD"}, vibe="x", duration=10.0)
    assert sysp != th_sys


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t(); print(f"  PASS {t.__name__}"); passed += 1
        except Exception as e:
            print(f"  FAIL {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} hype-editor unit tests passed")
    sys.exit(0 if passed == len(tests) else 1)
