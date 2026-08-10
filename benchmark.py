# -*- coding: utf-8 -*-
"""Benchmark: OCR quality + speed across 5 apps on the phone.

Tests:
  A. Speed: CPU vs GPU (if available)
  B. Accuracy: preprocess on vs off (dark mode inversion)
  C. Coverage: how many text regions per app type
"""
import sys, time, json, os
from pathlib import Path

# Project root detection — works from any working directory
PROJECT_ROOT = Path(__file__).resolve().parent
VENV_SITE = str(PROJECT_ROOT / ".venv" / "Lib" / "site-packages")
SRC_DIR = str(PROJECT_ROOT / "src")

sys.path.insert(0, VENV_SITE)
sys.path.insert(0, SRC_DIR)

# Fix: add nvidia cuDNN DLL paths for PaddlePaddle GPU
_cudnn_bin = PROJECT_ROOT / ".venv" / "Lib" / "site-packages" / "nvidia" / "cudnn" / "bin"
_cublas_bin = PROJECT_ROOT / ".venv" / "Lib" / "site-packages" / "nvidia" / "cublas" / "bin"
for _p in [str(_cudnn_bin), str(_cublas_bin)]:
    if os.path.isdir(_p) and _p not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _p + ";" + os.environ.get("PATH", "")
        os.add_dll_directory(_p)

from android_harness.capture import screenshot
from android_harness.device import device_info, _pick_device, adb
from android_harness.helpers import home, wait as wait_ms
from android_harness.input import keyevent

OUT = PROJECT_ROOT / "benchmark_results"
OUT.mkdir(exist_ok=True)
serial = _pick_device()
info = device_info()


def open_app_pkg(pkg):
    """Open an app by package name. Only allows valid Java-style package names."""
    import re
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_.]*$', pkg):
        raise ValueError(f"Invalid package name: {pkg!r}")
    adb("-s", serial, "shell", "monkey", "-p", pkg,
        "-c", "android.intent.category.LAUNCHER", "1")


def run_test(name, setup_fn, package=None):
    """Run a full OCR test: setup, capture, OCR with/without preprocess."""
    print(f"\n{'='*50}")
    print(f"  {name}")
    print(f"{'='*50}")

    # Navigate to the app
    home()
    wait_ms(0.5)
    if package:
        open_app_pkg(package)
    if setup_fn:
        setup_fn()
    wait_ms(2)

    # Capture screenshot
    img = screenshot(str(OUT / f"{name}_raw.png"))
    raw_size = Path(img).stat().st_size
    print(f"  Screenshot: {raw_size//1024}KB")

    # Test with preprocessing ON
    from android_harness.ocr import ocr, _preprocess_image, _check_gpu

    # Check preprocessing
    pp_img = _preprocess_image(img)
    pp_applied = pp_img != img
    print(f"  Dark mode: {'YES (preprocess active)' if pp_applied else 'NO (light mode)'}")

    # OCR with preprocessing
    t0 = time.time()
    r_pp = ocr(min_confidence=0.3, image_path=img, preprocess=True)
    t_pp = time.time() - t0
    print(f"  OCR +preprocess: {t_pp:.1f}s, {len(r_pp)} regions")

    # OCR without preprocessing
    t0 = time.time()
    r_raw = ocr(min_confidence=0.3, image_path=img, preprocess=False)
    t_raw = time.time() - t0
    print(f"  OCR -preprocess: {t_raw:.1f}s, {len(r_raw)} regions")

    # Show top results
    for r in r_pp[:8]:
        print(f"    [{r['x']:5.0f},{r['y']:5.0f}] {r['confidence']:.2f}  {r['text']}")

    if len(r_pp) > 8:
        print(f"    ... and {len(r_pp)-8} more")

    # Save results
    result = {
        "app": name,
        "dark_mode": pp_applied,
        "raw_size_kb": raw_size // 1024,
        "preprocess": {
            "time_s": round(t_pp, 2),
            "regions": len(r_pp),
            "high_conf": sum(1 for r in r_pp if r["confidence"] >= 0.9),
            "avg_conf": round(sum(r["confidence"] for r in r_pp) / max(len(r_pp), 1), 3),
        },
        "no_preprocess": {
            "time_s": round(t_raw, 2),
            "regions": len(r_raw),
            "high_conf": sum(1 for r in r_raw if r["confidence"] >= 0.9),
            "avg_conf": round(sum(r["confidence"] for r in r_raw) / max(len(r_raw), 1), 3),
        },
    }

    with open(OUT / f"{name}.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


# ── GPU check ──
print("=" * 50)
print("  android-harness Benchmark")
print(f"  Device: {info['width']}x{info['height']} SDK={info['sdk']}")
from android_harness.ocr import _check_gpu
gpu_ok = _check_gpu()
print(f"  GPU: {'YES' if gpu_ok else 'NO (CPU only)'}")


# ── Run tests ──
results = []

# 1. Home Screen (first page, dense icons)
results.append(run_test(
    "01_home_screen",
    setup_fn=lambda: None  # home() already called
))

# 2. Settings (system settings, list-based)
results.append(run_test(
    "02_settings",
    package="com.android.settings",
    setup_fn=lambda: None
))

# 3. WeChat (chat list, text-heavy)
results.append(run_test(
    "03_wechat",
    package="com.tencent.mm",
    setup_fn=None
))

# 4. SMS (messages list)
results.append(run_test(
    "04_sms",
    setup_fn=lambda: adb("-s", serial, "shell", "am", "start",
                         "-a", "android.intent.action.SENDTO",
                         "-d", "sms:10086")
))

# 5. Home Screen page 2 (different layout)
results.append(run_test(
    "05_home_page2",
    setup_fn=lambda: (
        home(),
        wait_ms(0.5),
        adb("-s", serial, "shell", "input", "swipe", "1000", "1390", "200", "1390", "300"),
        wait_ms(1)
    )
))


# ── Summary ──
print(f"\n{'='*60}")
print(f"  BENCHMARK SUMMARY")
print(f"{'='*60}")
print(f"  {'App':<20s} {'Dark':>5s} {'Regions':>8s} {'Time':>6s} {'AvgConf':>7s} {'High%':>6s}")
print(f"  {'-'*55}")

total_regions = 0
total_time = 0
total_high = 0
total_all = 0

for r in results:
    pp = r["preprocess"]
    total_regions += pp["regions"]
    total_time += pp["time_s"]
    total_high += pp["high_conf"]
    total_all += pp["regions"]
    pct = f"{100*pp['high_conf']/max(pp['regions'],1):.0f}%"
    print(f"  {r['app']:<20s} {'YES' if r['dark_mode'] else 'NO':>5s} {pp['regions']:>8d} {pp['time_s']:>5.1f}s {pp['avg_conf']:>6.3f} {pct:>6s}")

print(f"  {'-'*55}")
print(f"  {'TOTAL':<20s} {'':>5s} {total_regions:>8d} {total_time:>5.1f}s {total_high/total_all:.3f} {100*total_high//total_all}%")

# Preprocess comparison
print(f"\n  Preprocessing effect (dark mode apps):")
for r in results:
    if r["dark_mode"]:
        pp = r["preprocess"]
        raw = r["no_preprocess"]
        diff = pp["regions"] - raw["regions"]
        pct = (pp["regions"] / max(raw["regions"], 1) - 1) * 100
        print(f"    {r['app']}: {raw['regions']} -> {pp['regions']} regions ({diff:+d}, {pct:+.0f}%)")

print(f"\n  Full results: {OUT}")
print("=" * 60)
