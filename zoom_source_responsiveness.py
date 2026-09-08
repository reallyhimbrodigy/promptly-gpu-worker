"""MEASURED 2026-09-08 — intrinsic zoom-responsiveness of the v1 fixtures.

    v1 talking_head   26.60 dB   (samples 26.41 26.80 26.81 26.40)
    v1 pet_video      29.79 dB   (samples 29.77 29.77 29.80 29.80)
    ZAC REAL t_head   19.13      from e2d86de, same method
    ZAC REAL car      22.33

Both v1 sources are FAR flatter than real footage — a 1.10x zoom disturbs
pet_video 10.7 dB less than it disturbs Zac's real talking head, and pet_video's
four samples span 0.03 dB, which for 62 KB across 18s means near-static content.

Intrinsic zoom-responsiveness: psnr(source, source seen through a 1.10x zoom).

The SAME method as the table in e2d86de, so the numbers are comparable:
a 1.10x zoom vs the unzoomed same second, median of 4 samples. HIGH means the
zoom barely disturbs the picture — the content cannot show a zoom.
"""
import re, statistics, subprocess, sys

W, H, S = 1080, 1920, 1.10


def psnr_at(src, t):
    cw, ch = W / S, H / S
    x, y = (W - cw) / 2, (H - ch) / 2
    f = (f"[0:v]crop=w={cw:.0f}:h={ch:.0f}:x={x:.0f}:y={y:.0f},"
         f"scale={W}:{H},setsar=1[a];[1:v]setsar=1[b];[a][b]psnr=stats_file=-")
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats",
         "-ss", f"{t:.3f}", "-t", "0.15", "-i", src,
         "-ss", f"{t:.3f}", "-t", "0.15", "-i", src,
         "-lavfi", f, "-f", "null", "-"],
        capture_output=True, text=True, timeout=300)
    v = [float(x) for x in re.findall(r"psnr_avg:([0-9.]+)",
                                      (r.stdout or "") + (r.stderr or ""))]
    return sum(v) / len(v) if v else None


for path, dur in [(a.split("=")[0], float(a.split("=")[1])) for a in sys.argv[1:]]:
    vals = [psnr_at(path, t) for t in (dur * 0.2, dur * 0.4, dur * 0.6, dur * 0.8)]
    got = [v for v in vals if v is not None]
    name = path.rsplit("/", 1)[-1]
    if not got:
        print(f"  {name:34} UNREADABLE — never a pass, never a failure")
        continue
    print(f"  {name:34} median {statistics.median(got):6.2f} dB   "
          f"samples {['%.2f' % v for v in got]}")
