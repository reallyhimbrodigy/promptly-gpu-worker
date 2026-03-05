FROM runpod/base:0.6.2-cuda12.2.0

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install runpod requests

COPY handler.py /handler.py

CMD ["python3", "-u", "/handler.py"]
