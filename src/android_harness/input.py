"""Touch and key input via ADB.

All coordinates are Android native screen points — the same space
that screencap outputs and ocr() returns. No conversion needed.

Unlike phone-harness which must fight macOS window focus, ADB input
injection works regardless of what's on the PC screen.
"""

import time
import shlex

from .device import adb, _pick_device


def _dev_args():
    """Return [-s, serial] for the active device."""
    return ["-s", _pick_device()]


# --- touch ---

def tap(x, y):
    """Tap at screen coordinates (x, y)."""
    adb(*_dev_args(), "shell", "input", "tap", str(int(x)), str(int(y)))


def long_press(x, y, duration=800):
    """Long-press at (x, y) for duration milliseconds."""
    adb(*_dev_args(), "shell", "input", "swipe",
        str(int(x)), str(int(y)),
        str(int(x)), str(int(y)),
        str(int(duration)))


def swipe(x1, y1, x2, y2, duration=300):
    """Touch-drag from (x1, y1) to (x2, y2) — what Android sees as a swipe.

    duration: milliseconds. Faster = momentum flick; slower = drag.
    """
    adb(*_dev_args(), "shell", "input", "swipe",
        str(int(x1)), str(int(y1)),
        str(int(x2)), str(int(y2)),
        str(int(duration)))


# --- key events ---

_KEYCODES = {
    "home": 3,
    "back": 4,
    "call": 5,
    "endcall": 6,
    "volume_up": 24,
    "volume_down": 25,
    "power": 26,
    "camera": 27,
    "clear": 28,
    "enter": 66,
    "del": 67,
    "backspace": 67,
    "tab": 61,
    "space": 62,
    "menu": 82,
    "search": 84,
    "app_switch": 187,
    "paste": 279,
    "copy": 278,
    "cut": 277,
}


def keyevent(code):
    """Send a keyevent by name or code.

    Examples:
        keyevent("home")       # → KEYCODE_HOME (3)
        keyevent("back")       # → KEYCODE_BACK (4)
        keyevent("app_switch") # → KEYCODE_APP_SWITCH (187)
        keyevent(3)            # raw keycode
    """
    if isinstance(code, str):
        code = code.lower()
        if code not in _KEYCODES:
            raise ValueError(
                f"Unknown key '{code}'. Known: {list(_KEYCODES.keys())}")
        code = _KEYCODES[code]
    adb(*_dev_args(), "shell", "input", "keyevent", str(code))


def press(key):
    """keyevent alias — matches phone-harness naming."""
    keyevent(key)


# --- text ---

# ADBKeyboard IME for Chinese/Unicode input
_ADBKEYBOARD_IME = "com.android.adbkeyboard/.AdbIME"
_ORIGINAL_IME = None  # cached original IME


def _get_original_ime():
    """Get and cache the user's original IME for restore after ADBKeyboard."""
    global _ORIGINAL_IME
    if _ORIGINAL_IME is None:
        r = adb(*_dev_args(), "shell", "settings", "get", "secure",
               "default_input_method")
        _ORIGINAL_IME = r.stdout.strip()
        if not _ORIGINAL_IME:
            _ORIGINAL_IME = "com.sohu.inputmethod.sogouoem/.SogouIME"
    return _ORIGINAL_IME


def _adbk_available():
    """Check if ADBKeyboard is installed on the device."""
    r = adb(*_dev_args(), "shell", "pm", "list", "packages", "adbkeyboard")
    return "adbkeyboard" in r.stdout


def type_text(text):
    """Type text into the currently focused field.

    For ASCII text: uses `adb shell input text` (fast, reliable).
    For Chinese/Unicode: switches to ADBKeyboard IME, broadcasts the text,
    then restores the original IME.

    PREREQUISITE for Chinese: ADBKeyboard must be installed on the device.
    See install.md for setup instructions. Falls back to ASCII-only mode
    with a warning if ADBKeyboard is not installed.

    IMPORTANT: A text field must be focused (tapped) before calling this.
    """
    if not text:
        return

    # ASCII-only path: fast, no IME switching needed
    if text.isascii():
        # shlex.quote prevents shell metacharacters (*, ;, $, etc.)
        # from being interpreted by the device shell
        safe = shlex.quote(text)
        adb(*_dev_args(), "shell", "input", "text", safe)
        return

    # Non-ASCII path: requires ADBKeyboard
    if not _adbk_available():
        raise RuntimeError(
            "Chinese/Unicode text requires ADBKeyboard. "
            "Install with: adb install ADBKeyboard.apk\n"
            "Then: adb shell ime enable com.android.adbkeyboard/.AdbIME\n"
            "See install.md for details.")

    original = _get_original_ime()

    # 1. Switch to ADBKeyboard
    adb(*_dev_args(), "shell", "ime", "set", _ADBKEYBOARD_IME)
    import time
    time.sleep(0.5)  # Wait for IME to connect to the InputConnection

    # 2. Broadcast the text (ADBKeyboard receives and commits it)
    # Use shlex.quote to prevent shell injection via $(), backticks, etc.
    safe_text = shlex.quote(text)
    adb(*_dev_args(), "shell", "am", "broadcast", "-a", "ADB_INPUT_TEXT",
        "--es", "msg", safe_text)
    time.sleep(0.5)  # Wait for text to be committed

    # 3. Restore original IME
    adb(*_dev_args(), "shell", "ime", "set", original)


# --- scroll ---

def scroll(direction="down", amount=500):
    """Scroll by touch-drag in the center of the screen.

    direction: 'up' (finger up, content up) | 'down' (finger down, content down)
    amount: pixels to drag.

    For the more sophisticated scroll_collect / scroll_until, see helpers.py.
    """
    from .device import device_info
    info = device_info()
    cx, cy = info["width"] // 2, info["height"] // 2

    if direction == "up":
        swipe(cx, cy + amount // 2, cx, cy - amount // 2)
    elif direction == "down":
        swipe(cx, cy - amount // 2, cx, cy + amount // 2)
    else:
        raise ValueError(f"direction must be 'up' or 'down', got {direction!r}")
