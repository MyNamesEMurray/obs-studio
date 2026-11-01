from obs_perf_test import analyze

r = analyze([i / 120 for i in range(1201)], 2560, 1440)
assert r["fps"] == 120.0 and r["res"] == "2560x1440" and r["frames"] == 1201, r
r = analyze([i / 60 for i in range(601)], 1920, 1080)
assert r["fps"] == 60.0 and abs(r["max_gap_ms"] - 16.7) < 0.1, r
print("ok")
