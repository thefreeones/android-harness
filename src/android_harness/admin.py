"""Doctor — diagnose the full android-harness chain."""

import sys

from .device import adb, list_devices, device_info, connection_state, _find_adb
from .capture import screenshot


def run_doctor():
    """Walk the ladder: ADB → device → capture → OCR. Return exit code."""
    ok, fail = 0, 0

    def check(label, test, detail=""):
        nonlocal ok, fail
        try:
            result = test()
            if result is False or result is None:
                print(f"[FAIL] {label}")
                if detail:
                    print(f"       {detail}")
                fail += 1
                return False
            print(f"[ OK ] {label}")
            ok += 1
            return True
        except Exception as e:
            print(f"[FAIL] {label} — {e}")
            if detail:
                print(f"       {detail}")
            fail += 1
            return False

    print("android-harness doctor")
    print("=" * 50)

    # 1. ADB binary
    adb_path = None
    try:
        adb_path = _find_adb()
        r = adb("version")
        ver = r.stdout.split("\n")[0].strip()
        print(f"[ OK ] ADB: {ver}")
        print(f"       Path: {adb_path}")
        ok += 1
    except Exception as e:
        print(f"[FAIL] ADB not found — {e}")
        print("       Install: https://developer.android.com/tools/releases/platform-tools")
        fail += 1
        return 1

    # 2. Connected devices
    def _check_devices():
        devices = list_devices()
        if not devices:
            return False
        return any(st == "device" for _, st in devices)

    state = connection_state()
    detail = ""
    if state == "disconnected":
        detail = "No device detected. Connect USB and enable USB debugging."
    elif state == "unauthorized":
        detail = "Device found but not authorized. Unlock phone and approve the prompt."
    elif state == "offline":
        detail = "Device is offline. Check the USB connection."

    check(f"Device ({state})", _check_devices, detail)
    if state != "device":
        return 1

    # 3. Screen info
    def _check_info():
        info = device_info()
        return info["width"] > 0 and info["height"] > 0

    try:
        info = device_info()
        print(f"[ OK ] Screen: {info['width']}x{info['height']}, "
              f"density={info['density']}, SDK={info['sdk']}")
        ok += 1
    except Exception as e:
        print(f"[FAIL] Screen info — {e}")
        fail += 1

    # 4. Screenshot capture
    def _check_capture():
        path = screenshot()
        from pathlib import Path
        return Path(path).stat().st_size > 500

    check("Screenshot", _check_capture,
          "Screencap failed. Check USB debugging permission.")

    # 5. OCR (lazy-load PaddleOCR)
    print("[ .. ] OCR (loading PaddleOCR model, this may take a moment...)")
    try:
        from .ocr import ocr
        results = ocr(min_confidence=0.1)
        sample = [r["text"] for r in results[:5]]
        print(f"[ OK ] OCR: {len(results)} text regions detected")
        print(f"       Sample: {sample}")
        ok += 1
    except Exception as e:
        print(f"[FAIL] OCR — {e}")
        fail += 1

    # 5. Chinese input (ADBKeyboard)
    try:
        r = adb("shell", "pm", "list", "packages", "adbkeyboard")
        if "adbkeyboard" in r.stdout:
            print(f"[ OK ] ADBKeyboard installed (Chinese input ready)")
        else:
            print(f"[ .. ] ADBKeyboard not installed — Chinese input unavailable")
            print(f"       Install: see install.md#chinese-input")
        ok += 1
    except Exception as e:
        print(f"[ .. ] ADBKeyboard check skipped — {e}")
        ok += 1

    # Summary
    print("=" * 50)
    total = ok + fail
    print(f"Results: {ok}/{total} passed, {fail} failed")
    return 0 if fail == 0 else 1
