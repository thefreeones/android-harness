---
name: android-harness
description: "Control the user's Android phone through ADB: open apps, tap, type, swipe, read the screen."
---

# android-harness

Direct Android control via ADB — screenshots + PaddleOCR for eyes,
`adb shell input` for hands. For task-specific edits, use
`agent-workspace/agent_helpers.py`. For setup or permission problems, read
`install.md`.

## When Not to Use

If the task is doable on the computer or the web — a website, an API, an app
with a web equivalent — do it there and leave the phone alone. Use
android-harness only when the task genuinely needs the phone: Android-only
apps, things tied to the user's phone number or 2FA, testing how something
looks on the device.

## Usage

```bash
android-harness <<'PY'
print(screen_size())
PY
```

- Invoke as `android-harness`. Use heredocs for multi-line commands.
- Helpers are pre-imported. All coordinates are Android native screen points.
- `ensure_device()` verifies a device is connected and authorized.

## Screen Workflow

- Prefer `ocr()` over eyeballing screenshots: every visible string comes back
  with a tap-ready center point — `[{text, confidence, x, y, w, h}]`. Filter
  in Python before printing.
- Tap by label: `tap_text("Weather")`. On failure it raises with what IS
  visible, so read the exception before retrying.
- Icons without labels: `screenshot()`, view the image, compute the point,
  then `tap(x, y)`.
- **Verify after every action**: `wait_stable()` then `ocr()`/`screenshot()`.
  There is no DOM to assert against; the capture is the ground truth.
- Navigation: `home()`, `back()`, `app_switcher()`,
  `open_app("Weather", package="com.example.app")`, `swipe(...)`,
  `scroll()`, `type_text("...")`, `press("enter")`,
  `long_press(x, y)`.
- **Scrolling a list**: use `scroll_collect(extract, key=...)` to walk a list
  to its true end, de-duping as it goes — it returns `{items, stop, scrolls}`
  where `stop` is `'reached-end'` or `'max-scrolls'`. Use `scroll_until(done)`
  to stop when a predicate on the visible OCR is met. Both decide "done" from
  whether the **screen actually moved**, not from whether your parser found
  new rows — a dense screen or a missed OCR line will not end the scroll
  early. Each step settles first so lazy-loaded content arrives before the
  movement check. `scroll_screen()` is the single-step primitive if you need
  it.

## Consent

This is the user's real phone. Stop and ask before anything outward-facing or
hard to reverse: sending a message, posting, purchasing, deleting, changing
settings. Navigating and reading for the user's own task is fine, but don't
linger in personal content (Messages, Photos, Mail) beyond what the task needs.

## Connection is the user's job

The harness never connects the phone for you. Connecting via USB and approving
the USB debugging prompt is a physical action only the user can do.

`ensure_device()` gates every task on this: if no authorized device is found it
raises a clear message. When you hit that:

- **STOP and relay the message. Ask the user to connect their phone.**
- **Never** loop-poll waiting for the connection — the only fix is the user
  plugging in and approving. Retry once *after they confirm they've done it*,
  not before.

## Gotchas

- **Screenshot speed**: `adb exec-out screencap` takes ~1–1.5 seconds, slower
  than iPhone Mirroring's ~100ms capture. Budget for this in automation loops.
- **Chinese input**: `type_text()` auto-detects non-ASCII and uses
  ADBKeyboard broadcast. Requires one-time APK install (see install.md).
- **OCR accuracy with dark mode**: PaddleOCR handles Chinese well but dark
  backgrounds can reduce accuracy. If OCR misses text, try switching to light
  mode or using `screenshot()` + a vision-capable model.
- **Home-Screen icon taps**: The tappable icon is above its text label.
  `open_app()` does this automatically, but if you call `tap_text()`, note
  that you may need to tap ~40px above the text center.
- **No multi-touch**: `adb shell input` does not support multi-touch gestures
  (pinch, two-finger scroll).
