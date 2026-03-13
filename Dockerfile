FROM runpod/base:0.6.2-cuda12.2.0

RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    pkg-config \
    python3-dev \
    libaubio-dev \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswresample-dev \
    libsndfile1-dev \
    libsamplerate0-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install \
    numpy \
    && python3 -m pip install --no-build-isolation \
    aubio \
    && python3 -m pip install \
    requests \
    anthropic \
    google-generativeai \
    deepgram-sdk \
    httpx

COPY handler.py .
COPY src/assets/sounds/ /assets/sounds/
COPY src/assets/fonts/ /assets/fonts/
COPY src/assets/music/ /assets/music/
CMD python3 -u /handler.py
