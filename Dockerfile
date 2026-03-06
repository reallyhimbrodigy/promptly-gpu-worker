FROM runpod/base:0.6.2-cuda12.2.0
RUN apt-get update \
    && apt-get install -y --no-install-recommends xz-utils \
    && rm -rf /var/lib/apt/lists/*
RUN rm -f /usr/bin/ffmpeg /usr/bin/ffprobe \
    && curl -L https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.0-latest-linux64-gpl-8.0.tar.xz -o /tmp/ffmpeg.tar.xz \
    && tar -xf /tmp/ffmpeg.tar.xz -C /tmp \
    && ls /tmp/ \
    && cp /tmp/ffmpeg-n8.0*/bin/ffmpeg /usr/local/bin/ffmpeg \
    && cp /tmp/ffmpeg-n8.0*/bin/ffprobe /usr/local/bin/ffprobe \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe \
    && ln -sf /usr/local/bin/ffmpeg /usr/bin/ffmpeg \
    && ln -sf /usr/local/bin/ffprobe /usr/bin/ffprobe \
    && rm -rf /tmp/ffmpeg* \
    && echo "=== FFmpeg Version ===" \
    && ffmpeg -version | head -3 \
    && echo "=== drawtext filter ===" \
    && ffmpeg -filters 2>&1 | grep drawtext \
    && echo "=== xfade filter ===" \
    && ffmpeg -filters 2>&1 | grep xfade \
    && echo "=== subtitles filter ===" \
    && ffmpeg -filters 2>&1 | grep subtitles \
    && echo "=== All checks passed ==="
RUN python3 -m pip install runpod requests
COPY handler.py /handler.py
CMD ["python3", "-u", "/handler.py"]
