"""Screen capture via ADB screencap.

Captures the phone's framebuffer directly — coordinates are native screen
points, no window offset or scaling needed (unlike phone-harness).
"""

import os
import tempfile
import time
from pathlib import Path

from .device import adb, _pick_device

TMP = Path(tempfile.gettempdir()) / "android-harness"
TMP.mkdir(exist_ok=True)


def screenshot(path=None, retries=2):
    """Capture the phone screen as a PNG. Returns the file path.

    Args:
        path: Optional save path. Defaults to a temp file.
        retries: Number of retries on failure.

    Returns:
        str: Path to the captured PNG file.
    """
    path = str(path or TMP / "screen.png")
    serial = _pick_device()
    last_err = None

    for _ in range(retries + 1):
        try:
            # adb exec-out screencap -p outputs raw PNG bytes to stdout
            r = adb("-s", serial, "exec-out", "screencap", "-p", binary=True)
            if r.returncode != 0 or len(r.stdout) < 500:
                last_err = (r.stderr or b"").decode(errors="replace").strip() or "empty capture"
                time.sleep(0.5)
                continue

            # Write binary PNG
            with open(path, "wb") as f:
                f.write(r.stdout)

            if Path(path).stat().st_size < 500:
                last_err = "capture too small (likely failed)"
                time.sleep(0.5)
                continue

            return path

        except Exception as e:
            last_err = str(e)
            time.sleep(0.5)

    raise RuntimeError(
        f"Screenshot failed after {retries + 1} tries: {last_err}")
