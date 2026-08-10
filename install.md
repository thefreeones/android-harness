# android-harness install

Use once. For phone work, read `SKILL.md`.

## Requirements

- Windows, macOS, or Linux with ADB installed.
- Python 3.10+.
- Android phone with **USB debugging** enabled:
  - Settings → About Phone → tap "Build number" 7 times → Developer options
  - Settings → Developer options → USB debugging → ON
  - Connect via USB → approve the "Allow USB debugging?" prompt on the phone.

## Fast Path

```bash
git clone https://github.com/ShawnPana/android-harness ~/.android-harness
cd ~/.android-harness

# Install ADB if you don't have it:
# Windows: download from https://developer.android.com/tools/releases/platform-tools
# macOS: brew install android-platform-tools
# Linux: apt install adb

# Install android-harness
pip install -e . --no-deps
pip install paddlepaddle paddleocr

# Register as an agent skill (Claude Code / Codex)
mkdir -p ~/.claude/skills/android-harness
android-harness skill > ~/.claude/skills/android-harness/SKILL.md

# Verify the whole chain
android-harness --doctor

# Quick test
android-harness <<'PY'
print(screen_size())
PY
```

If `screen_size()` prints your phone's resolution, you're done.

`~/.android-harness` is the canonical home — a hidden folder in your home
directory (like `~/.oh-my-zsh` or `~/.nvm`), so the code, `helpers.py`,
`SKILL.md`, and your `agent-workspace/` always live at a path the agent knows,
on any machine.

## ADB Path

android-harness discovers ADB automatically from:
1. `D:/android-platform-tools/platform-tools/adb.exe` (Windows)
2. `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe` (Android Studio)
3. `adb` on PATH

If your ADB is elsewhere, set the environment variable:
```bash
export AH_ADB_PATH="/path/to/adb"
```

## Chinese Input

`adb shell input text` only supports ASCII. For Chinese/Unicode input,
android-harness automatically switches to ADBKeyboard when it detects
non-ASCII characters in `type_text()`.

### Setup (one-time)

1. Download [ADBKeyboard.apk](https://github.com/senzhk/ADBKeyBoard/raw/master/ADBKeyboard.apk):
   ```bash
   curl -L -o ADBKeyboard.apk \
     https://github.com/senzhk/ADBKeyBoard/raw/master/ADBKeyboard.apk
   ```

2. Install and enable on the phone:
   ```bash
   adb install ADBKeyboard.apk
   adb shell ime enable com.android.adbkeyboard/.AdbIME
   ```

3. Verify:
   ```bash
   adb shell pm list packages adbkeyboard
   # → package:com.android.adbkeyboard
   ```

### How it works

When `type_text("你好世界")` is called:
1. Detects non-ASCII → triggers ADBKeyboard path
2. Switches IME to ADBKeyboard
3. Broadcasts the text via `ADB_INPUT_TEXT` intent
4. Restores the original IME

The entire flow is transparent — `type_text()` handles ASCII and Chinese
the same way. Just make sure a text field is focused (tapped) first.

### Troubleshooting

- **Chinese text doesn't appear**: A text field must be focused (keyboard
  visible) before calling `type_text()`. Verify with `tap_text("搜索")`
  first, then `type_text("你好")`.
- **Broadcast returns error**: ADBKeyboard may not be enabled. Re-run
  `adb shell ime enable com.android.adbkeyboard/.AdbIME`.
- **Keyboard doesn't restore**: On some devices, the IME restore may lag.
  The original IME is always restored after each `type_text()` call.

## If It Fails

`--doctor` walks the ladder in order: ADB binary → device connection →
screen info → screenshot capture → OCR. Fix the first FAIL; later checks
depend on earlier ones.

Common cases:

- **No device detected**: USB cable might be charge-only. Try a data cable.
- **Device unauthorized**: Unlock the phone and approve the USB debugging
  prompt.
- **Screenshot is black/empty**: The device may have a secure flag set
  (banking apps, DRM content). Switch to a normal app screen.
- **OCR fails**: PaddleOCR model download may have failed. Check your
  network and retry.
