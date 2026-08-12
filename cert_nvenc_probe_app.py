"""NVENC PROVE-OR-DISPROVE (Zac 2026-08-02). Two GPU containers: DEFAULT caps vs
NVIDIA_DRIVER_CAPABILITIES=video,compute,utility. Captures raw stderr for
nvidia-smi, the encoder list, the build config, the driver-lib presence, and a
real h264_nvenc test encode. Answers: raw error, does libnvidia-encode.so exist,
can Modal set the capability, yes/no on NVENC. Cheap (T4, ~5 min each).

  modal run cert_nvenc_probe_app.py"""
import modal

app = modal.App("cert-nvenc-probe")

# ffmpeg from apt (debian). Two images: one default, one with the video capability.
_base = modal.Image.debian_slim().apt_install("ffmpeg")
image_default = _base
image_videocap = _base.env({"NVIDIA_DRIVER_CAPABILITIES": "video,compute,utility"})

_CMDS = [
    "echo NVIDIA_DRIVER_CAPABILITIES=$NVIDIA_DRIVER_CAPABILITIES",
    "nvidia-smi",
    "ls -la /usr/lib/x86_64-linux-gnu/ | grep -iE 'nvidia-encode|nvcuvid' || echo 'NO libnvidia-encode/nvcuvid in /usr/lib/x86_64-linux-gnu'",
    "find / -name 'libnvidia-encode.so*' 2>/dev/null || echo 'libnvidia-encode.so NOT FOUND anywhere'",
    "ffmpeg -hide_banner -encoders 2>&1 | grep -i nvenc || echo 'no nvenc encoder listed'",
    "ffmpeg -hide_banner -buildconf 2>&1 | grep -iE 'nvenc|cuda|nvcodec' || echo 'ffmpeg build has NO nvenc/cuda flags'",
    "ffmpeg -hide_banner -y -f lavfi -i testsrc2=duration=5:size=1920x1080:rate=30 -c:v h264_nvenc -preset p4 /tmp/out.mp4 2>&1 | tail -25",
    "echo '--- encode rc above; file size: ---'; ls -la /tmp/out.mp4 2>/dev/null || echo 'no output file'",
]


def _probe():
    import subprocess
    out = []
    for cmd in _CMDS:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        out.append(f"$ {cmd}\n{(r.stdout or '').strip()}\n{(r.stderr or '').strip()}\n[rc={r.returncode}]")
    return "\n\n".join(out)


@app.function(image=image_default, gpu="T4", timeout=300)
def probe_default():
    return _probe()


@app.function(image=image_videocap, gpu="T4", timeout=300)
def probe_videocap():
    return _probe()


@app.local_entrypoint()
def main():
    print("\n" + "=" * 70 + "\n### ARM A: DEFAULT NVIDIA_DRIVER_CAPABILITIES (T4)\n" + "=" * 70)
    print(probe_default.remote())
    print("\n" + "=" * 70 + "\n### ARM B: NVIDIA_DRIVER_CAPABILITIES=video,compute,utility (T4)\n" + "=" * 70)
    print(probe_videocap.remote())
