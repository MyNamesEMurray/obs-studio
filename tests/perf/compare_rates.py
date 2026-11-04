import argparse
import subprocess
import sys

import numpy as np

W, H = 64, 36


def gray_frames(path, seconds, fps, skip=0.0):
    out = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(skip), "-t", str(seconds), "-i", path,
         "-vf", f"fps={fps},scale={W}:{H},format=gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True).stdout
    a = np.frombuffer(out, np.uint8).reshape(-1, H, W).astype(np.float32)
    a -= a.mean(axis=(1, 2), keepdims=True)
    a /= a.std(axis=(1, 2), keepdims=True) + 1e-6
    return a


def find_offset(rec, stream, span=20.0):
    r = gray_frames(rec, span, 60)
    s = gray_frames(stream, span + 6, 60)
    motion = np.array([np.abs(r[i + 1] - r[i]).mean() for i in range(len(r) - 1)])
    win = 60
    start = int(np.argmax([motion[i:i + win].sum() for i in range(len(motion) - win)]))
    seg = r[start:start + win]
    best = (1e9, 0)
    for k in range(0, len(s) - win):
        d = float(np.abs(s[k:k + win] - seg).mean())
        if d < best[0]:
            best = (d, k)
    return (best[1] - start) / 60.0, best[0]


def main():
    a = argparse.ArgumentParser()
    a.add_argument("rec")
    a.add_argument("stream")
    a.add_argument("--seconds", type=float, default=10)
    a.add_argument("--out", default="compare_120_vs_60.mp4")
    a.add_argument("--slow", type=float, default=0.25)
    args = a.parse_args()

    off, err = find_offset(args.rec, args.stream)
    print(f"stream started {off:.3f}s before the recording (match error {err:.1f})")
    if err > 0.5:
        print("warning: weak alignment, clips may not line up", file=sys.stderr)

    lab = "drawtext=fontfile=arial.ttf:text='{}':fontcolor=white:fontsize=36:box=1:boxcolor=black@0.6:x=20:y=20"
    cnt = "drawtext=fontfile=arial.ttf:text='%{{n}}':fontcolor=yellow:fontsize=30:box=1:boxcolor=black@0.6:x=20:y=h-50"
    fc = (
        f"[0:v]fps=120,scale=1280:720,{lab.format('120 fps recording')},{cnt.format()}[l];"
        f"[1:v]fps=120,scale=1280:720,{lab.format('60 fps stream (half rate)')}[r];"
        "[l][r]hstack=inputs=2,format=yuv420p@@[v]"
    )
    fc = fc.replace("%{{n}}", "%{n}")
    fc_fast = fc.replace("@@", "")
    fc_slow = fc.replace("@@", f",setpts=PTS/{args.slow}")
    enc = ["-c:v", "libx264", "-preset", "fast", "-crf", "18"]
    inputs = ["ffmpeg", "-nostdin", "-y", "-v", "error",
              "-ss", "0", "-t", str(args.seconds), "-i", args.rec,
              "-ss", f"{max(off, 0):.3f}", "-t", str(args.seconds), "-i", args.stream]
    slow = args.out.replace(".mp4", f"_slow{args.slow}x.mp4")
    subprocess.run(inputs + ["-filter_complex", fc_fast, "-map", "[v]"] + enc + [args.out], check=True)
    subprocess.run(inputs + ["-filter_complex", fc_slow, "-map", "[v]"] + enc + [slow], check=True)
    print(args.out)
    print(slow)


main()
