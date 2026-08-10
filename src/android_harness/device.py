"""ADB device discovery and state management.

All coordinates use Android native screen points — the same space
`screencap` and `input tap` use. No coordinate conversion needed.
"""

import os
import subprocess
from pathlib import Path

# --- ADB path discovery ---

_ADB_CANDIDATES = [
    # Common install locations
    "D:/android-platform-tools/platform-tools/adb.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
    os.path.expandvars(r"%ProgramFiles%\platform-tools\adb.exe"),
    # PATH fallback
    "adb",
]

ADB_PATH = None


def _find_adb():
    global ADB_PATH
    if ADB_PATH:
        return ADB_PATH
    for candidate in _ADB_CANDIDATES:
        try:
            r = subprocess.run(
                [candidate, "version"], capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if r.returncode == 0 and b"Android Debug Bridge" in r.stdout:
                ADB_PATH = candidate
                return ADB_PATH
        except Exception:
            continue
    raise RuntimeError(
        "ADB not found. Install Android Platform Tools and add to PATH, "
        "or set AH_ADB_PATH to the full adb.exe path.")


def set_adb_path(path):
    """Override the ADB path. Call before any other function."""
    global ADB_PATH
    ADB_PATH = path


def adb(*args, binary=False):
    """Run an adb command, return CompletedProcess.

    Set binary=True for commands that output raw bytes (screencap).
    """
    exe = _find_adb()
    cmd = [exe] + list(args)
    return subprocess.run(
        cmd, capture_output=True, text=not binary, timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


# --- device state ---


def list_devices():
    """Return [(serial, state), ...] for all connected devices."""
    r = adb("devices")
    devices = []
    for line in r.stdout.strip().split("\n")[1:]:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append((parts[0], parts[1]))
    return devices


def _pick_device():
    """Pick the first 'device'-state device, or raise."""
    devices = [(s, st) for s, st in list_devices() if st == "device"]
    if not devices:
        all_devs = list_devices()
        if not all_devs:
            raise RuntimeError(
                "No Android device connected. Connect via USB and enable "
                "USB debugging, then retry.")
        raise RuntimeError(
            f"No authorized device. Device states: {all_devs}. "
            "Unlock the phone and approve the USB debugging prompt.")
    return devices[0][0]


def device_info():
    """{serial, width, height, density, sdk} or raise if no device."""
    serial = _pick_device()
    size = adb("-s", serial, "shell", "wm", "size")
    density = adb("-s", serial, "shell", "wm", "density")
    sdk = adb("-s", serial, "shell", "getprop", "ro.build.version.sdk")

    w, h = 0, 0
    for part in size.stdout.strip().split():
        if "x" in part:
            w_str, h_str = part.split("x")
            w, h = int(w_str), int(h_str)

    d = 0
    for part in density.stdout.strip().split():
        try:
            d = int(part)
        except ValueError:
            pass

    s = sdk.stdout.strip()

    return {
        "serial": serial,
        "width": w,
        "height": h,
        "density": d,
        "sdk": int(s) if s.isdigit() else 0,
    }


def connection_state():
    """'device' | 'unauthorized' | 'offline' | 'disconnected'."""
    try:
        devices = list_devices()
        if not devices:
            return "disconnected"
        for _, state in devices:
            if state == "device":
                return "device"
            if state == "unauthorized":
                return "unauthorized"
        return "offline"
    except Exception:
        return "disconnected"
