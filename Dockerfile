FROM runpod/base:0.6.2-cuda12.2.0

# Install FFmpeg with NVENC support
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir runpod requests

# Copy handler
COPY handler.py /handler.py

# RunPod serverless entry point
CMD ["python3", "-u", "/handler.py"]