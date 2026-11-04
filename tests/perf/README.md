# OBS perf test

Drives a running OBS over obs-websocket: streams to a local RTMP sink (ffmpeg) and records at the same time, then checks fps, resolution, skipped frames and logs CPU and render time to a CSV.

## One-time setup
1. `pip install obsws-python`. Put `ffmpeg` and `ffprobe` on PATH.
2. In OBS: Tools > WebSocket Server Settings, enable the server and set a password.
3. Settings > Stream: Custom service, server `rtmp://127.0.0.1:1935/live`, key `test`.
4. Pick the output config to test (encoders, rescale, half-rate checkbox, canvas fps).
5. Add a moving source to the scene (game capture, or a looping video).

## Run
```
set OBS_WS_PASSWORD=yourpass
python obs_perf_test.py --label halfrate --seconds 60 --rec-fps 120 --rec-res 2560x1440 --stream-fps 60 --stream-res 1920x1080
```
Exit code 1 and `FAIL:` lines when a check misses. Each run appends one row to `perf_results.csv`. Run once per config (two encoders, half-rate shared, baseline) and compare rows.

`python test_analyze.py` checks the fps math without OBS.

## Regression check: half-rate on a shared encoder
Use one encoder for stream and recording, set it to 1 non-reference B-frame (x264 custom options `bframes=1 b-adapt=0 b-pyramid=none`, or NVENC B-frames 1 with B-ref mode off), set Settings > Advanced > Network > "Stream frame rate" to "1/2 of output", then run:
```
python obs_perf_test.py --label shared_half --rec-fps 120 --stream-fps 60 --tol 0.02
```
It fails if the stream is not 60 fps or the recording is not 120 fps. Run it again after any change to `rtmp-stream.c`, `flv-mux.c` or the output code in the frontend. OBS also logs a warning at 300 video packets when the share of dropped packets is not about 50%.

## Compare a recording with the half-rate stream
`pip install numpy`, then:
```
python compare_rates.py REC.mkv STREAM.flv --seconds 10 --out compare.mp4
```
Writes a side-by-side clip (120 fps recording left, 60 fps stream right) plus a 0.25x slow-motion copy. It aligns the two files by matching a high-motion second, so the scene must be moving. Windows only as written: it expects `arial.ttf` in the current folder.

## Encoder advisor
`python encoder_advisor.py` benchmarks every encoder ffmpeg can use on this PC (x264, x265, SVT-AV1, NVENC, QuickSync, AMF), scores each with VMAF against a lossless reference, and prints the best choice that encodes fast enough for live use, with the matching OBS encoder id. Pass `--input yourclip.mp4` with real game footage for meaningful scores; without it a synthetic test pattern is used. Needs an ffmpeg build with libvmaf. Options: `--mode stream|record|both`, `--seconds`, `--record-res/fps/bitrate`, `--stream-res/fps/bitrate`.
