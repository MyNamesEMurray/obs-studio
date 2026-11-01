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
