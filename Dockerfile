FROM python:3.10-slim

WORKDIR /app

# Install FFmpeg (standard package - we'll use libx264 with more CPU/RAM available)
# Note: For NVENC GPU encoding, we would need nvidia/cuda base + custom FFmpeg build.
# RunPod's 24GB GPU instances have plenty of RAM, so even CPU encoding won't OOM here.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy handler
COPY handler.py .

CMD ["python", "-u", "handler.py"]