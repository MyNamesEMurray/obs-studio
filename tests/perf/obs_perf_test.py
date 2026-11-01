import argparse
import csv
import json
import os
import subprocess
import sys
import time


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height:packet=pts_time", "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    pts = sorted(float(p["pts_time"]) for p in data["packets"] if "pts_time" in p)
    s = data["streams"][0]
    return analyze(pts, s["width"], s["height"])


def analyze(pts, width, height):
    n = len(pts)
    span = pts[-1] - pts[0] if n > 1 else 0
    gaps = [b - a for a, b in zip(pts, pts[1:])]
    return {
        "res": f"{width}x{height}",
        "frames": n,
        "fps": round((n - 1) / span, 2) if span else 0,
        "max_gap_ms": round(max(gaps) * 1000, 1) if gaps else 0,
    }


def check(name, got, want_fps, want_res, tol, fails):
    if want_res and got["res"] != want_res:
        fails.append(f"{name}: res {got['res']} != {want_res}")
    if want_fps and abs(got["fps"] - want_fps) > want_fps * tol:
        fails.append(f"{name}: fps {got['fps']} != {want_fps} (+/-{tol:.0%})")


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--host", default="localhost")
    a.add_argument("--port", type=int, default=4455)
    a.add_argument("--password", default=os.environ.get("OBS_WS_PASSWORD", ""))
    a.add_argument("--seconds", type=int, default=60)
    a.add_argument("--label", default="run")
    a.add_argument("--rtmp", default="rtmp://127.0.0.1:1935/live/test")
    a.add_argument("--rec-fps", type=float)
    a.add_argument("--rec-res")
    a.add_argument("--stream-fps", type=float)
    a.add_argument("--stream-res")
    a.add_argument("--tol", type=float, default=0.05)
    a.add_argument("--max-skipped-pct", type=float, default=1.0)
    a.add_argument("--out-dir", default=".")
    a.add_argument("--csv", default="perf_results.csv")
    args = a.parse_args()

    import obsws_python as obs

    stream_file = os.path.join(args.out_dir, f"{args.label}_stream.flv")
    sink = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-listen", "1", "-i", args.rtmp,
                             "-c", "copy", stream_file])
    time.sleep(2)

    cl = obs.ReqClient(host=args.host, port=args.port, password=args.password, timeout=10)
    base = cl.get_stats()
    cl.start_stream()
    cl.start_record()

    cpu, render_ms, fps = [], [], []
    for _ in range(args.seconds):
        time.sleep(1)
        s = cl.get_stats()
        cpu.append(s.cpu_usage)
        render_ms.append(s.average_frame_render_time)
        fps.append(s.active_fps)

    end = cl.get_stats()
    rec_path = cl.stop_record().output_path
    cl.stop_stream()
    sink.wait(timeout=30)

    out_total = end.output_total_frames - base.output_total_frames
    out_skip = end.output_skipped_frames - base.output_skipped_frames
    rnd_total = end.render_total_frames - base.render_total_frames
    rnd_skip = end.render_skipped_frames - base.render_skipped_frames

    rec = probe(rec_path)
    stream = probe(stream_file)
    row = {
        "label": args.label,
        "obs_cpu_avg_pct": round(sum(cpu) / len(cpu), 2),
        "obs_cpu_max_pct": round(max(cpu), 2),
        "render_ms_avg": round(sum(render_ms) / len(render_ms), 3),
        "render_ms_max": round(max(render_ms), 3),
        "active_fps_avg": round(sum(fps) / len(fps), 2),
        "render_skipped_pct": round(100 * rnd_skip / max(rnd_total, 1), 3),
        "output_skipped_pct": round(100 * out_skip / max(out_total, 1), 3),
        "rec_fps": rec["fps"], "rec_res": rec["res"], "rec_max_gap_ms": rec["max_gap_ms"],
        "stream_fps": stream["fps"], "stream_res": stream["res"], "stream_max_gap_ms": stream["max_gap_ms"],
    }

    fails = []
    check("record", rec, args.rec_fps, args.rec_res, args.tol, fails)
    check("stream", stream, args.stream_fps, args.stream_res, args.tol, fails)
    if row["render_skipped_pct"] > args.max_skipped_pct:
        fails.append(f"render skipped {row['render_skipped_pct']}% > {args.max_skipped_pct}%")
    if row["output_skipped_pct"] > args.max_skipped_pct:
        fails.append(f"output skipped {row['output_skipped_pct']}% > {args.max_skipped_pct}%")

    new = not os.path.exists(args.csv)
    with open(args.csv, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)

    print(json.dumps(row, indent=2))
    for f in fails:
        print("FAIL:", f)
    print("PASS" if not fails else "FAILED")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
