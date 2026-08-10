"""High-level phone control primitives.

These are pre-imported into every android-harness script. Agent-editable
helpers in agent-workspace/agent_helpers.py are auto-loaded at import time
and extend this namespace.

All coordinates are Android native screen points.
"""

import hashlib
import time
from pathlib import Path

from .device import device_info, connection_state, _pick_device
from .capture import screenshot
from .ocr import ocr, find_text
from .input import tap, long_press, swipe, scroll, type_text, press, keyevent

# --- session / state ---


def screen_size():
    """(width, height) of the phone screen in native pixels."""
    info = device_info()
    return info["width"], info["height"]


def ensure_device():
    """Return device serial if connected and authorized, else raise."""
    return _pick_device()


def wait(seconds=1.0):
    """Sleep for seconds."""
    time.sleep(seconds)


def wait_stable(timeout=6.0, interval=0.5, settle=2):
    """Wait until `settle` consecutive captures are pixel-identical.

    Useful after taps to wait for animations to finish before OCR.
    """
    prev, same = None, 0
    deadline = time.time() + timeout
    while time.time() < deadline:
        path = screenshot()
        digest = hashlib.md5(Path(path).read_bytes()).hexdigest()
        same = same + 1 if digest == prev else 0
        if same >= settle - 1:
            return True
        prev = digest
        time.sleep(interval)
    return False


# --- reading the screen ---


def tap_text(query, index=0, exact=False, min_confidence=0.3):
    """Find text on screen and tap its center.

    Raises with what IS visible on failure, so the agent can read the
    exception and retry with a different query.
    """
    hits = find_text(query, exact=exact, min_confidence=min_confidence)
    if not hits:
        visible = [o["text"] for o in ocr(min_confidence=0.2)][:30]
        raise RuntimeError(
            f"No visible text matches {query!r}. Saw: {visible}")
    hit = hits[index]
    tap(hit["x"], hit["y"])
    return hit


# --- navigation ---


def home():
    """Go to the Home Screen."""
    keyevent("home")
    time.sleep(0.8)


def back():
    """Press Back."""
    keyevent("back")
    time.sleep(0.5)


def app_switcher():
    """Open the app switcher / recent apps."""
    keyevent("app_switch")
    time.sleep(0.8)


def open_app(name, package=None):
    """Open an app by launching its package via `monkey`, or via UI search.

    If package is provided, uses `am start`. Otherwise, goes Home →
    tries to find and tap the app icon via OCR, which is less reliable
    but doesn't require knowing the package name.
    """
    from .device import adb
    serial = _pick_device()

    if package:
        adb("-s", serial, "shell",
            "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
        wait_stable()
        return

    # UI fallback: Home Screen → OCR → tap icon
    home()
    time.sleep(0.5)
    hits = find_text(name, min_confidence=0.3)
    if hits:
        hit = hits[0]
        # Icons are typically above their labels on the home screen
        tap(hit["x"], max(0, hit["y"] - 40))
        wait_stable()
    else:
        raise RuntimeError(
            f"Could not find '{name}' on screen. Try providing the Android "
            f"package name: open_app('{name}', package='com.example.app')")


# --- scrolling through lists ---
#
# End-of-list is decided by whether the SCREEN MOVED, never by whether
# the caller's parser found new items. A dense list or a missed OCR row
# must not read as "done" — only the pixels going still means the end.


def _content_texts(min_conf=0.3, top_frac=0.08, bottom_frac=0.93):
    """OCR of the scrollable content area, excluding status bar and nav bar."""
    img = screenshot()
    w, h = screen_size()
    top = int(h * top_frac)
    bot = int(h * bottom_frac)
    return [o for o in ocr(min_confidence=min_conf, image_path=img)
            if top < o["y"] < bot]


def _text_set(boxes):
    """Frozenset of (text, y_bucket) for dedup and movement detection."""
    result = set()
    for o in boxes:
        if o["text"].strip():
            bucket = int(o["y"] // 30) * 30  # bucket y to handle pixel jitter
            result.add((o["text"].strip(), bucket))
    return frozenset(result)


def _overlap(a, b):
    """Jaccard overlap of two text sets. ~1.0 = same screen, low = moved."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def scroll_screen(direction="up", amount=500, settle=2.5, moved_thresh=0.5):
    """One scroll gesture, then wait for the screen to settle.

    Returns: {moved, overlap, before, after, boxes}
      - `boxes` is the settled content OCR, ready to parse.
      - `moved` is False when overlap >= moved_thresh: the list didn't advance.
    """
    if direction not in ("up", "down"):
        raise ValueError(f"direction must be 'up' or 'down', got {direction!r}")

    img_before = screenshot()
    before = _text_set(_content_texts(min_conf=0.3))
    scroll(direction=direction, amount=amount)
    time.sleep(0.4)

    prev_boxes, prev = None, None
    deadline = time.time() + settle
    while time.time() < deadline:
        img = screenshot()
        boxes = _content_texts(min_conf=0.3, image_path=img)
        cur = _text_set(boxes)
        if cur == prev:                 # two identical captures = settled
            break
        prev, prev_boxes = cur, boxes
        time.sleep(0.35)

    after = prev or frozenset()
    return {
        "moved": _overlap(before, after) < moved_thresh,
        "overlap": round(_overlap(before, after), 3),
        "before": before,
        "after": after,
        "boxes": prev_boxes or [],
    }


def scroll_until(done, direction="up", amount=500, max_scrolls=60, settle=2.5):
    """Scroll until `done(boxes)` is truthy or the list stops moving.

    `done` receives the current content OCR (list of boxes) and returns
    a truthy value to stop; that value is returned. Returns None if the
    end of the list is reached first.
    """
    boxes = _content_texts()
    hit = done(boxes)
    if hit:
        return hit

    stale = 0
    for _ in range(max_scrolls):
        res = scroll_screen(direction, amount, settle)
        hit = done(res["boxes"])
        if hit:
            return hit
        if res["moved"]:
            stale = 0
        else:
            stale += 1
            if stale >= 2:              # confirmed still after retry
                return None
            time.sleep(0.8)

    return None


def scroll_collect(extract=None, key=None, direction="up", amount=500,
                   max_scrolls=400, end_after=3, settle=2.5, on_progress=None):
    """Scroll a list top-to-bottom, extracting and de-duping items each screen,
    until the list reaches its true end.

    Args:
        extract(boxes) -> list of items for the current screen.
            Default returns each content text line.
        key(item) -> hashable de-dup key. Default: the item itself.
        Stops after `end_after` consecutive non-moving scrolls, or `max_scrolls`.

    Returns: {items, stop, scrolls}
      - `stop` is 'reached-end' or 'max-scrolls'.
    """
    extract = extract or (
        lambda boxes: [o["text"].strip() for o in boxes if o["text"].strip()])
    key = key or (lambda x: x)

    seen, order = set(), []

    def ingest(boxes):
        new = 0
        for item in extract(boxes):
            k = key(item)
            if k in seen:
                continue
            seen.add(k)
            order.append(item)
            new += 1
        return new

    ingest(_content_texts())
    stale = 0
    for i in range(1, max_scrolls + 1):
        res = scroll_screen(direction, amount, settle)
        new = ingest(res["boxes"])
        if on_progress:
            on_progress(i, len(order), new, res["moved"], res["overlap"])
        if res["moved"]:
            stale = 0
        else:
            stale += 1
            if stale >= end_after:
                return {"items": order, "stop": "reached-end", "scrolls": i}
            time.sleep(0.8)

    return {"items": order, "stop": "max-scrolls", "scrolls": max_scrolls}
