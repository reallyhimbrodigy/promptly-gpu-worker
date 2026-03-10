FROM runpod/base:0.6.2-cuda12.2.0

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install \
    runpod \
    requests \
    anthropic \
    google-generativeai \
    deepgram-sdk \
    httpx \
    aubio \
    numpy

COPY handler.py .
COPY src/assets/sounds/ /assets/sounds/
COPY src/assets/fonts/  /assets/fonts/
CMD python3 -u /handler.py
