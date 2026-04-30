#!/usr/bin/env bash
# Smoke-render every Remotion composition against synthetic inputs.
#
# Goal: catch the entire class of "Remotion bundle compiles but blows up at
# render time" bugs (e.g. today's `staticFile() does not support absolute
# paths` fault) on a developer laptop in <2 minutes — before paying for a
# Modal deploy + render cycle.
#
# What this exercises end-to-end:
#   1. TypeScript still compiles  (tsc --noEmit)
#   2. Remotion bundle still produces an index.html  (prebundle.mjs)
#   3. Each composition's React tree mounts without throwing
#      (PromptlyOverlay, PromptlyMicroSegments, PromptlyBlendCaptionsOnly)
#   4. Each composition renders at least one frame and writes a non-empty
#      output file
#
# What it deliberately does NOT exercise:
#   - real assets from S3 / Pexels / Gemini / Deepgram (no network)
#   - audio pipeline (handler.py-side; orthogonal)
#   - long-form timing edge cases (smoke uses a 1-second timeline)
#
# Visual regression: each rendered output is decoded to raw RGBA/YUV pixels
# and md5-hashed. Hashes are pinned in scripts/smoke-baselines.json. A
# mismatch is a regression — either an unintended visual change in
# Remotion components, or an intentional one that wasn't checked in. Run
# with BASELINE=update to overwrite the baselines after intentional
# changes (review the diff before committing).
#
# Output: /tmp/promptly-smoke-<unix>/  (deleted on success unless KEEP=1).
# A pre-bundle cache is reused at .smoke-bundle/ — first run pays ~30-60s
# for the bundle, subsequent runs reuse it.
#
# Usage:
#   bash scripts/smoke.sh                # run smoke + regression check
#   KEEP=1 bash scripts/smoke.sh         # keep temp dir for inspection
#   FRESH=1 bash scripts/smoke.sh        # rebuild the prebundle cache
#   BASELINE=update bash scripts/smoke.sh  # overwrite scripts/smoke-baselines.json

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
REMOTION_DIR="$REPO_ROOT/src/remotion"
BUNDLE_CACHE="$REMOTION_DIR/.smoke-bundle"
SMOKE_DIR="$(mktemp -d "/tmp/promptly-smoke-XXXXXX")"
KEEP="${KEEP:-0}"
FRESH="${FRESH:-0}"
BASELINE="${BASELINE:-0}"
BASELINES_FILE="$REPO_ROOT/scripts/smoke-baselines.json"

cleanup() {
  # Always remove the staged fixture from the bundle cache — leaving it
  # behind would shadow the production assets the next prebundle pulls in.
  rm -f "$BUNDLE_CACHE/public/smoke-fixture.mp4" 2>/dev/null || true
  if [[ "$KEEP" == "1" ]]; then
    echo "smoke: KEEP=1, leaving $SMOKE_DIR for inspection"
  else
    rm -rf "$SMOKE_DIR"
  fi
}
trap cleanup EXIT

echo "smoke: working dir = $SMOKE_DIR"
echo "smoke: bundle cache = $BUNDLE_CACHE"

# ── 1. Tooling sanity ──────────────────────────────────────────────────────
for bin in node ffmpeg; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "smoke: ERROR — $bin not on PATH" >&2
    exit 1
  fi
done

# ── 2. TypeScript check ────────────────────────────────────────────────────
echo "smoke: tsc --noEmit"
( cd "$REMOTION_DIR" && npx tsc --noEmit )

# ── 3. Prebundle (cached unless FRESH=1) ───────────────────────────────────
if [[ "$FRESH" == "1" ]]; then
  rm -rf "$BUNDLE_CACHE"
fi
if [[ ! -f "$BUNDLE_CACHE/index.html" ]]; then
  echo "smoke: building Remotion bundle into $BUNDLE_CACHE (first run / FRESH=1)"
  ( cd "$REMOTION_DIR" && PROMPTLY_BUNDLE_DIR="$BUNDLE_CACHE" node prebundle.mjs )
else
  echo "smoke: reusing prebundle cache (set FRESH=1 to rebuild)"
fi

# ── 4. Public dir + fixture source video ───────────────────────────────────
# In production the public dir IS the bundle's public/ subdirectory (handler
# stages source video and B-roll in there). Match that arrangement here so
# the smoke test exercises the same staticFile resolution path.
PUBLIC_DIR="$BUNDLE_CACHE/public"
mkdir -p "$PUBLIC_DIR"

FIXTURE_BASENAME="smoke-fixture.mp4"
FIXTURE_PATH="$PUBLIC_DIR/$FIXTURE_BASENAME"

# 1-second 1080x1920 30fps test pattern. Real h264 + yuv420p so OffthreadVideo
# treats it the same as a production source. Silent — audio is orthogonal.
echo "smoke: generating fixture $FIXTURE_BASENAME"
ffmpeg -y -loglevel error \
  -f lavfi -i "testsrc2=size=1080x1920:rate=30:duration=1" \
  -c:v libx264 -preset ultrafast -crf 23 -pix_fmt yuv420p \
  -movflags +faststart \
  "$FIXTURE_PATH"

# ── 5. Synthetic input JSONs ───────────────────────────────────────────────
# Tiny but real: each composition mounts every layer it owns at least once.
# Caption pages have one token each so CaptionsLayer renders the actual
# caption component (not a no-op early-return). One MG and one text overlay
# per layer to catch import/mount regressions in those modules.

cat > "$SMOKE_DIR/overlay.json" <<EOF
{
  "sourceUrl": "$FIXTURE_BASENAME",
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "totalDurationInFrames": 30,
  "clips": [],
  "transitions": [],
  "broll": [],
  "caption": {
    "style": "PaperII",
    "pages": [
      {
        "text": "smoke",
        "startMs": 0,
        "durationMs": 1000,
        "tokens": [{ "text": "smoke", "fromMs": 0, "toMs": 1000 }]
      }
    ],
    "keywords": ["smoke"],
    "positionSegments": [{ "fromFrame": 0, "toFrame": 30, "position": "bottom" }],
    "extraProps": {}
  },
  "textOverlays": [
    {
      "variant": "torn_paper",
      "fromFrame": 0,
      "durationInFrames": 30,
      "topText": "smoke",
      "bottomText": "test"
    }
  ],
  "motionGraphics": [
    {
      "type": "Notification",
      "fromFrame": 0,
      "durationInFrames": 30,
      "props": {
        "anchor": "top",
        "platform": "ios",
        "notifications": [
          { "app": "imessage", "title": "smoke", "body": "ok" }
        ]
      }
    }
  ],
  "outro": "none"
}
EOF

cat > "$SMOKE_DIR/micro.json" <<EOF
{
  "sourceUrl": "$FIXTURE_BASENAME",
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "totalDurationInFrames": 30,
  "segments": [
    {
      "type": "transition",
      "outputStartFrame": 0,
      "durationInFrames": 15,
      "transition": {
        "afterClipIndex": 0,
        "type": "CrossfadeZoom",
        "durationInFrames": 15,
        "clipAStartFromFrames": 0,
        "clipBStartFromFrames": 0,
        "clipAPlaybackRate": 1,
        "clipBPlaybackRate": 1
      }
    },
    {
      "type": "zoom_clip",
      "outputStartFrame": 15,
      "durationInFrames": 15,
      "clip": {
        "id": "smoke-zoom",
        "startFromFrames": 0,
        "playbackRate": 1,
        "durationInFrames": 15,
        "zoomEffect": {
          "type": "FocusWindow",
          "events": [{ "startMs": 0, "durationMs": 500, "scale": 1.2, "originX": 0.5, "originY": 0.5 }]
        }
      }
    }
  ]
}
EOF

cat > "$SMOKE_DIR/blend.json" <<EOF
{
  "videoUrl": "$FIXTURE_BASENAME",
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "totalDurationInFrames": 30,
  "caption": {
    "style": "NegativeFlash",
    "pages": [
      {
        "text": "blend test smoke",
        "startMs": 0,
        "durationMs": 1000,
        "tokens": [
          { "text": "blend", "fromMs": 0,   "toMs": 333 },
          { "text": "test",  "fromMs": 333, "toMs": 666 },
          { "text": "smoke", "fromMs": 666, "toMs": 1000 }
        ]
      }
    ],
    "keywords": ["smoke"],
    "positionSegments": [{ "fromFrame": 0, "toFrame": 30, "position": "bottom" }],
    "extraProps": {}
  },
  "captionMatchOverlays": []
}
EOF

# ── 6. Validate inputs against Pydantic schemas ────────────────────────────
# render_schemas.py mirrors src/remotion/src/types.ts. If the schemas drift
# from what the React tree actually accepts, the synthetic JSONs would
# render successfully (TS side doesn't enforce them) but Python's runtime
# validation in handler.py would reject real render inputs in production.
# Cheaper to catch the drift here.
echo "smoke: python schema validation"
python3 -c "
import json, sys
sys.path.insert(0, '$REPO_ROOT')
from render_schemas import (
    PromptlyRenderInput,
    PromptlyMicroSegmentsInput,
    PromptlyBlendCaptionsOnlyInput,
)
PromptlyRenderInput.model_validate(json.load(open('$SMOKE_DIR/overlay.json')))
PromptlyMicroSegmentsInput.model_validate(json.load(open('$SMOKE_DIR/micro.json')))
PromptlyBlendCaptionsOnlyInput.model_validate(json.load(open('$SMOKE_DIR/blend.json')))
print('smoke: schemas OK')
"

# ── 7. Render each composition ─────────────────────────────────────────────
# Track each render's visual hash (computed by decoding to raw pixels and
# md5'ing the stream — encoder thread counts and container muxing don't
# affect the hash, only frame content does). Compared to baselines after
# all renders complete.
declare -a OBSERVED_LABELS=()
declare -a OBSERVED_HASHES=()

run_render() {
  local label="$1"
  local composition="$2"
  local input="$3"
  local output="$4"
  local pix_fmt="$5"
  local t0
  t0=$(date +%s)
  echo "smoke: rendering $label ($composition)"
  PROMPTLY_BUNDLE_DIR="$BUNDLE_CACHE" \
    node "$REMOTION_DIR/render-full.mjs" \
      --input "$input" \
      --output "$output" \
      --public-dir "$PUBLIC_DIR" \
      --composition "$composition" \
      --gl swangle
  local elapsed=$(( $(date +%s) - t0 ))
  if [[ ! -s "$output" ]]; then
    echo "smoke: ERROR — $label produced no output at $output" >&2
    exit 1
  fi
  local size
  size=$(wc -c <"$output" | tr -d ' ')
  # Decode to raw pixels and md5 — invariant to container/encoder choices.
  local hash
  hash=$(ffmpeg -loglevel error -i "$output" -an -pix_fmt "$pix_fmt" -f md5 - 2>&1 | sed 's/^MD5=//')
  if [[ -z "$hash" ]]; then
    echo "smoke: ERROR — could not hash $label output at $output" >&2
    exit 1
  fi
  OBSERVED_LABELS+=("$label")
  OBSERVED_HASHES+=("$hash")
  echo "smoke: $label OK in ${elapsed}s ($size bytes, hash=$hash)"
}

run_render "overlay"          "PromptlyOverlay"          "$SMOKE_DIR/overlay.json" "$SMOKE_DIR/overlay.mov" "rgba"
run_render "micro-segments"   "PromptlyMicroSegments"    "$SMOKE_DIR/micro.json"   "$SMOKE_DIR/micro.mp4"   "yuv420p"
run_render "blend-captions"   "PromptlyBlendCaptionsOnly" "$SMOKE_DIR/blend.json"   "$SMOKE_DIR/blend.mp4"   "yuv420p"

# ── 8. Visual regression check ─────────────────────────────────────────────
# Compare observed hashes to baselines. A mismatch fails smoke unless
# BASELINE=update, in which case we overwrite the baselines file (review
# the resulting diff before committing).
if [[ "$BASELINE" == "update" ]]; then
  python3 - <<PY
import json
labels = "${OBSERVED_LABELS[@]}".split()
hashes = "${OBSERVED_HASHES[@]}".split()
baselines = dict(zip(labels, hashes))
with open("$BASELINES_FILE", "w") as f:
    json.dump(baselines, f, indent=2)
    f.write("\n")
print(f"smoke: baselines updated at $BASELINES_FILE")
for k, v in baselines.items():
    print(f"smoke:   {k} = {v}")
PY
else
  python3 - <<PY
import json, sys
labels = "${OBSERVED_LABELS[@]}".split()
hashes = "${OBSERVED_HASHES[@]}".split()
observed = dict(zip(labels, hashes))
try:
    with open("$BASELINES_FILE") as f:
        baselines = json.load(f)
except FileNotFoundError:
    print("smoke: ERROR — no baselines file at $BASELINES_FILE")
    print("smoke: run 'BASELINE=update bash scripts/smoke.sh' to create one")
    sys.exit(1)
mismatches = []
for k, v in observed.items():
    expected = baselines.get(k)
    if expected is None:
        mismatches.append((k, "<missing baseline>", v))
    elif expected != v:
        mismatches.append((k, expected, v))
if mismatches:
    print("smoke: ERROR — visual regression(s) detected:")
    for label, expected, actual in mismatches:
        print(f"smoke:   {label}: expected={expected} actual={actual}")
    print("smoke: if these changes are intentional, update with:")
    print("smoke:   BASELINE=update bash scripts/smoke.sh")
    sys.exit(1)
print(f"smoke: visual regression check OK ({len(observed)} hashes match)")
PY
fi

echo "smoke: all compositions rendered successfully"
