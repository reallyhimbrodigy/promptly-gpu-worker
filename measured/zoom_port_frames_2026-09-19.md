# The four ported zooms, proven by frame

Project `55d5dfd2-6cdf-423c-9882-cbb3ecdcaad6`, canvas 1080x1920 @30fps.
Source: `golden/lumen-refs/ref2-viral-creator-doc-vertical.mp4` — 720x1280, 30fps,
43.2s, on disk and durable. Never user media.

Base clip on V1 frames 0-599. Each component on V2 over its own span, with
`srcFrom` set to the span's own start so the layer plays the SAME MOMENT the base
would — the sync law, exercised rather than assumed.

| component | span | read back | what the frames show |
|---|---|---|---|
| SnapReframe | 120-209 | from=120 dur=90 | f128 wide, f140 tighter, f175 tightest, f205 released — the spring rising, holding and running back out |
| FocusWindow | 240-329 | from=240 dur=90 | f275 and f320 carry the INSET WINDOW with its white border over a zoomed, darkened plate. Two `<Video>` layers, one asset, one offset |
| LetterboxPush | 360-449 | from=360 dur=90 | f400 has bars top AND bottom with the inner image pushed in; f440 has them receding. Bars and push ride one progress |
| DepthPull | 480-569 | from=480 dur=90 | f525 is vignetted with the edges blurred and the centre sharp; f560 is clean. The depth stack rides the pull and releases with it |

All four registered `isValid: true` with zero validator errors.

## The finding: CHATCUT REWRITES THE CODE AT REGISTRATION

Every one of the four came back with the same warning:

    Auto-fixed: Stripped hardcoded fallbacks from props
    (property system provides defaults)

So `Number(props.scale) || 1.3` is registered as `Number(props.scale)`. **The blob
that runs is not the blob that was sent.** It is safe here only because every
registered `defaultValue` equals the fallback it replaced — which is exactly the
rule `build_chatcut_registry.py` already enforces for the other family:

    A REGISTERED DEFAULT MUST EQUAL WHAT THE COMPONENT DOES WHEN THE PROP IS ABSENT.

The four property tables in `port/zoom_properties.json` were written to satisfy
that before the warning was seen, so nothing moved. But the general hazard is
real and is the same shape as every absence-as-zero finding: a component whose
fallback and whose registered default DISAGREE will silently run the default,
and the code on disk will still read as though the fallback applies.

## What this run does NOT prove

The blobs registered here were sent through the MCP surface INLINE, and to fit
that path they carry only the cap functions each component actually calls —
comments and unused solver helpers dropped. They are behaviourally equivalent and
they are NOT byte-identical to `port/build/*.jsx`.

The shipping path is Builder 1's: `ported_code()` reads `/craft/port/<Name>.jsx`
from the image mount, which IS the built blob, and `PORTED_PROPS` carries the
tables (wired at 0a5c0e5, 13 blobs / 13 tables / 0 contract violations). These
frames prove the CURVES, the two-layer capability, the srcFrom law and the
property tables. Byte-exact registration is proven on that path, not this one.
