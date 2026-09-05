#!/usr/bin/env bash
# Deterministic fixture generation. Re-running yields the same bytes.
# Requires ffmpeg; drawtext is deliberately unused (not in every build).
set -euo pipefail
OUT="${1:-/tmp/fixtures}"; mkdir -p "$OUT"
ffmpeg -v error -y -f lavfi -i "life=size=1080x1920:rate=30:mold=10:ratio=0.1:death_color=#101040:life_color=#40c0ff:seed=42" \
  -f lavfi -i "aevalsrc=0.4*sin(2*PI*220*t)*(1+0.5*sin(2*PI*2*t)):s=44100" \
  -t 20 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac -shortest "$OUT/music.mp4"
ffmpeg -v error -y -f lavfi -i "color=c=#1e1e1e:s=1080x1920:r=30" -f lavfi -i "anullsrc=r=44100:cl=mono" \
  -vf "drawbox=x=0:y=0:w=1080:h=120:color=#2d2d2d@1:t=fill,drawbox=x=60:y='240+mod(t*22\,360)':w=600:h=16:color=#569cd6@1:t=fill,drawbox=x=60:y='320+mod(t*22\,360)':w=840:h=16:color=#9cdcfe@1:t=fill,drawbox=x=60:y='400+mod(t*22\,360)':w=480:h=16:color=#ce9178@1:t=fill,drawbox=x='120+mod(t*40\,400)':y='1400+80*sin(t)':w=24:h=36:color=#ffffff@1:t=fill" \
  -t 20 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac -shortest "$OUT/screen_recording.mp4"
ffmpeg -v error -y -f lavfi -i "gradients=s=1080x1920:r=30:c0=#2b1055:c1=#7597de:seed=7" -f lavfi -i "anullsrc=r=44100:cl=mono" \
  -vf "zoompan=z='min(zoom+0.0009,1.35)':d=450:s=1080x1920:fps=30" \
  -t 15 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac -shortest "$OUT/product_shot.mp4"
ffmpeg -v error -y -f lavfi -i "color=c=#f0e6d2:s=1080x1920:r=30" -f lavfi -i "anullsrc=r=44100:cl=mono" \
  -vf "drawbox=x='540+440*sin(3.1*t)*cos(1.7*t)':y='960+760*sin(2.3*t)':w=180:h=180:color=#8b4513@1:t=fill" \
  -t 18 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac -shortest "$OUT/pet_video.mp4"
echo "built 4 generated fixtures in $OUT (talking_head comes from ab-sources/talking-head-v1)"
