#!/bin/bash
# Extract frames from a video or TikTok URL for Claude to review
# Usage: ./video_frames.sh <video_path_or_url> [fps] [output_dir]
#   fps: frames per second to extract (default: 7)
#   output_dir: where to save frames (default: /tmp/video_frames)

INPUT="$1"
FPS="${2:-7}"
OUT="${3:-/tmp/video_frames}"

if [ -z "$INPUT" ]; then
    echo "Usage: ./video_frames.sh <video_path_or_url> [fps] [output_dir]"
    echo "  Supports: local files, TikTok URLs, YouTube URLs, etc."
    echo "  fps=7 (default) → 7 frames/sec"
    exit 1
fi

rm -rf "$OUT"
mkdir -p "$OUT"

# If input looks like a URL, download it first
if [[ "$INPUT" == http* ]]; then
    echo "Downloading video from URL..."
    VIDEO="$OUT/source_video.mp4"
    yt-dlp -f "best[ext=mp4]/best" -o "$VIDEO" "$INPUT" 2>&1
    if [ $? -ne 0 ] || [ ! -f "$VIDEO" ]; then
        echo "ERROR: Failed to download video"
        exit 1
    fi
    echo "Downloaded to $VIDEO"
else
    VIDEO="$INPUT"
fi

# Get video duration
DURATION=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$VIDEO" 2>/dev/null)
EXPECTED=$(echo "$DURATION $FPS" | awk '{printf "%d", $1 * $2}')
echo ""
echo "Video: $VIDEO"
echo "Duration: ${DURATION}s"
echo "Extracting at ${FPS} fps → ~${EXPECTED} frames"
echo "Output: $OUT"
echo ""

ffmpeg -i "$VIDEO" -vf "fps=$FPS" -q:v 2 "$OUT/frame_%04d.jpg" -y -loglevel warning

COUNT=$(ls "$OUT"/frame_*.jpg 2>/dev/null | wc -l | tr -d ' ')
echo "Done! Extracted $COUNT frames to $OUT/"
