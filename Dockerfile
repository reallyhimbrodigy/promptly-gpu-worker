FROM runpod/base:0.6.2-cuda12.2.0

RUN apt-get update && apt-get install -y --no-install-recommends xz-utils && rm -rf /var/lib/apt/lists/*

RUN rm -f /usr/bin/ffmpeg /usr/bin/ffprobe \
    && curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o /tmp/ffmpeg.tar.xz \
    && tar -xf /tmp/ffmpeg.tar.xz -C /tmp \
    && cp /tmp/ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ffmpeg \
    && cp /tmp/ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ffprobe \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe \
    && ln -s /usr/local/bin/ffmpeg /usr/bin/ffmpeg \
    && ln -s /usr/local/bin/ffprobe /usr/bin/ffprobe \
    && rm -rf /tmp/ffmpeg* \
    && ffmpeg -version | head -1

RUN python3 -m pip install runpod requests

COPY handler.py /handler.py

CMD ["python3", "-u", "/handler.py"]
