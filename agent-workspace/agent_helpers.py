"""Agent-editable phone helpers.

Add task-specific primitives here. Core helpers from android_harness.helpers
load this file at import time; anything defined here is available in
android-harness scripts alongside the core helpers.
"""

from android_harness.helpers import (
    find_text, tap, swipe, wait_stable, wait
)


def tap_icon(label, index=0, offset_y=-40):
    """Tap a Home-Screen app icon by its label.

    Home-Screen icon labels are NOT tappable — the actual icon hitbox
    is above the text. Default offset of -40px works on 1264x2780 screens.
    """
    hits = find_text(label, min_confidence=0.3)
    if not hits:
        raise RuntimeError(f"No label matching {label!r} on screen")
    h = hits[index]
    tap(h["x"], max(0, h["y"] + offset_y))
    return h


def find_and_tap_app(name, max_swipes=3):
    """Swipe through Home Screen pages to find an app icon and tap it.

    Returns True if found and tapped, False if exhausted all pages.

    Args:
        name: App label text (e.g. '设置', '微信').
        max_swipes: Maximum Home Screen pages to check.
    """
    for i in range(max_swipes):
        try:
            tap_icon(name)
            wait_stable()
            return True
        except RuntimeError:
            pass  # not on this page, swipe to next

        if i < max_swipes - 1:
            # Swipe left: finger from right to left
            swipe(1000, 1390, 100, 1390, 300)
            wait(1.0)
            wait_stable()

    return False
