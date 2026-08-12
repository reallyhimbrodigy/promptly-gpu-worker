#!/usr/bin/env python3
"""cert_cpu4_analysis_timing — Zac's deciding experiment (2026-08-04).

SEQUENTIAL run already showed the individual encodes barely scale (fps_normalize
1.22x, proxy 1.06x, 13.4s both at cpu=4 — under the 20s line). But that CANNOT
answer Caveat 1: the cpu=8 completion crash (78.9%->35.7%) was the proxy blowing
its timeout under POOL CONTENTION — many CPU-bound analysis tasks fighting for
the same cores. A sequential test never sees it.

THIS run reproduces the contention: the CPU-bound mega_pool tasks run
CONCURRENTLY in a ThreadPoolExecutor(max_workers=10) — exactly like handler's
mega_pool — on a worst-case 60fps/1080x1920/75s source, at cpu=4 AND cpu=16.

Zac's addition #2: report the PROXY's wall time UNDER CONCURRENCY as its own
number. At 2.8s isolated it needs ~10x contention to breach a 30s timeout; that
factor is the go/no-go for dropping the planner to cpu=4.

Also samples cgroup cpu usage (true cores-in-use, billing-accurate — os.cpu_count
lies about the allocation per cert_core_probe) so we get the PEAK cores the pool
actually uses. If it peaks ~5/16, cpu=6-8 is the safe planner size with margin.

Faithful load = the pool's CPU-bound tasks (network tasks add ~0 CPU): fps
re-encode, proxy, scdet(full decode), exposure(10fps decode), loudness(-vn audio),
face-extract(dense frame decode). Commands verbatim from handler.py. Omits the
cv2-DNN inference on top of face-extract, so this is a LOWER BOUND on contention
(the derived timeout carries headroom for that).

Reuses the worker's exact ffmpeg build. Cost: ~cpu4 ~4min + cpu16 ~2min ≈ ~$0.10.
"""
import modal

try:
    from modal_app import image
except ModuleNotFoundError:
    image = modal.Image.debian_slim()  # container re-import only — NOT the real image

app = modal.App("cert-cpu4-analysis-timing")

_PROXY_X264_THREADS = 48
_X264_ENCODE_THREADS = 48


def _build_source(path):
    import subprocess
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=60:duration=75",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=75",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", path],
        check=True, capture_output=True,
    )


def _sh(cmd):
    import subprocess, time
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True)
    return time.time() - t0, p.returncode


# ---- the pool's CPU-bound tasks, commands verbatim from handler.py ----
def _t_fps_normalize(src):
    return _sh(["ffmpeg", "-y", "-v", "error", "-threads", "0", "-i", src,
                "-vf", "fps=30.000000,format=yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "15",
                "-x264-params", f"threads={_X264_ENCODE_THREADS}",
                "-pix_fmt", "yuv420p", "-color_primaries", "bt709",
                "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
                "-g", "30", "-keyint_min", "30", "-c:a", "aac", "-b:a", "128k",
                "/tmp/norm.mp4"])

def _t_proxy(src):
    return _sh(["ffmpeg", "-y", "-v", "error", "-threads", "0", "-i", src,
                "-vf", "scale=480:-2,fps=18",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
                "-x264-params", f"threads={_PROXY_X264_THREADS}",
                "-c:a", "libopus", "-b:a", "64k", "-ac", "1", "/tmp/proxy.mp4"])

def _t_scdet(src):
    return _sh(["ffmpeg", "-v", "error", "-i", src,
                "-vf", "scdet=threshold=0.30:sc_pass=1,metadata=print:file=-",
                "-an", "-f", "null", "-"])

def _t_exposure(src):
    return _sh(["ffmpeg", "-v", "error", "-i", src,
                "-vf", "fps=10,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
                "-an", "-f", "null", "-"])

def _t_loudness(src):
    return _sh(["ffmpeg", "-v", "error", "-vn", "-i", src, "-t", "60",
                "-af", "astats=metadata=1:reset=0,ametadata=mode=print",
                "-f", "null", "-"])

def _t_face_extract(src):
    # dense face detection decodes frames via ffmpeg then runs cv2 DNN; this is
    # the ffmpeg decode half (the cv2 inference is extra CPU we don't replicate).
    return _sh(["ffmpeg", "-y", "-v", "error", "-i", src,
                "-vf", "fps=6,scale=640:-2", "-f", "image2", "/tmp/f%04d.jpg"])


_POOL = [("fps_normalize", _t_fps_normalize), ("proxy", _t_proxy),
         ("scdet", _t_scdet), ("exposure", _t_exposure),
         ("loudness", _t_loudness), ("face_extract", _t_face_extract)]


def _sample_cores(stop_evt, out):
    """True cores-in-use from cgroup cpu.stat usage_usec (billing-accurate)."""
    import time
    def _usage():
        for p in ("/sys/fs/cgroup/cpu.stat",):  # cgroup v2
            try:
                for line in open(p):
                    if line.startswith("usage_usec"):
                        return int(line.split()[1])
            except Exception:
                pass
        return None
    last_u, last_t = _usage(), time.time()
    while not stop_evt.is_set():
        time.sleep(0.5)
        u, t = _usage(), time.time()
        if u is not None and last_u is not None and t > last_t:
            out.append((u - last_u) / 1e6 / (t - last_t))  # cores used
        last_u, last_t = u, t


def _run_concurrent(cores):
    import os, time, threading
    from concurrent.futures import ThreadPoolExecutor
    src = "/tmp/src60.mp4"
    _build_source(src)
    samples = []
    stop = threading.Event()
    sampler = threading.Thread(target=_sample_cores, args=(stop, samples), daemon=True)
    sampler.start()
    results = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=10) as pool:  # mega_pool shape
        futs = {name: pool.submit(fn, src) for name, fn in _POOL}
        for name, fut in futs.items():
            dt, rc = fut.result()
            results[name] = {"sec": round(dt, 1), "rc": rc}
    block_wall = time.time() - t0
    stop.set(); sampler.join(timeout=2)
    peak_cores = round(max(samples), 1) if samples else None
    mean_cores = round(sum(samples) / len(samples), 1) if samples else None
    return {"modal_cpu": cores, "os_cpu_count": os.cpu_count(),
            "tasks": results, "block_wall_s": round(block_wall, 1),
            "peak_cores": peak_cores, "mean_cores": mean_cores}


@app.function(image=image, cpu=4, timeout=900, memory=8192)
def concurrent_cpu4():
    return _run_concurrent(4)


@app.function(image=image, cpu=16, timeout=900, memory=12288)
def concurrent_cpu16():
    return _run_concurrent(16)


@app.local_entrypoint()
def main():
    f4 = concurrent_cpu4.spawn()
    f16 = concurrent_cpu16.spawn()
    r16 = f16.get()
    r4 = f4.get()
    print("\n======= CONCURRENT mega_pool CONTENTION at cpu=4 vs cpu=16 (Zac Caveat 1) =======")
    for r in (r16, r4):
        print(f"\n[cpu={r['modal_cpu']}]  peak_cores_used={r['peak_cores']}/{r['modal_cpu']} "
              f"(mean={r['mean_cores']}, os.cpu_count={r['os_cpu_count']})  block_wall={r['block_wall_s']}s")
        for name, v in sorted(r["tasks"].items(), key=lambda x: -x[1]["sec"]):
            flag = "" if v["rc"] == 0 else "  <<< FAILED rc=%d" % v["rc"]
            star = "  <<< PROXY (go/no-go)" if name == "proxy" else ""
            print(f"    {name:<16} {v['sec']:>6.1f}s{star}{flag}")
    # the go/no-go: proxy under concurrency vs its 2.8s isolated + the 30s timeout
    p4 = r4["tasks"]["proxy"]["sec"]; p16 = r16["tasks"]["proxy"]["sec"]
    print(f"\n  PROXY under concurrency: cpu16={p16}s  cpu4={p4}s  (isolated cpu4 was 2.8s)")
    print(f"  contention stretch at cpu4: {p4/2.8:.1f}x isolated. Timeout base is 30s.")
    verdict = ("SAFE — proxy has %.0fx margin to the 30s timeout even under full pool contention" % (30.0/p4)
               if p4 < 20 else
               "AT RISK — proxy within %.1fx of the 30s timeout; derived timeout is load-bearing" % (30.0/p4))
    print(f"  VERDICT: {verdict}")
    print(f"  peak cores at cpu=16: {r16['peak_cores']} -> if ~5-8, cpu=6-8 is the safe planner size")
    print("================================================================================\n")
