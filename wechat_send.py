# -*- coding: utf-8 -*-
"""Send '架构文件格式为.docx' to lucky in WeChat."""
import sys, os, time
from pathlib import Path

for p in [r"D:\Vibecoding_project\android-harness\.venv\Lib\site-packages\nvidia\cudnn\bin",
          r"D:\Vibecoding_project\android-harness\.venv\Lib\site-packages\nvidia\cublas\bin"]:
    if os.path.isdir(p) and p not in os.environ.get("PATH", ""):
        os.environ["PATH"] = p + ";" + os.environ.get("PATH", "")
        os.add_dll_directory(p)

sys.path.insert(0, r"D:\Vibecoding_project\android-harness\.venv\Lib\site-packages")
sys.path.insert(0, r"D:\Vibecoding_project\android-harness\src")

from android_harness.input import tap, type_text
from android_harness.capture import screenshot
from android_harness.ocr import ocr

OUT = Path(r"D:\Vibecoding_project\wechat_test")

MESSAGE = "架构文件格式为.docx"

# ── 1. Verify we're in a chat ──
print("[1] OCR to verify chat...")
r = ocr(min_confidence=0.3, preprocess=True)
lucky_hits = [o for o in r if "lucky" in o["text"].lower() and o["y"] < 300]
print(f"    lucky in title: {bool(lucky_hits)}")

# ── 2. Tap input field ──
print("[2] Tapping input field...")
tap(632, 2665)
time.sleep(1)

# ── 3. Type ──
print(f"[3] Typing '{MESSAGE}'...")
type_text(MESSAGE)
time.sleep(1.5)

screenshot(str(OUT / "v10_typed.png"))
r = ocr(min_confidence=0.3, preprocess=True)
# Find "发送" button
send_btns = [o for o in r if "发送" in o["text"]]
if send_btns:
    s = send_btns[0]
    print(f"    Send button at ({s['x']:.0f},{s['y']:.0f})")
    # ── 4. Tap send ──
    print("[4] Tapping send...")
    tap(s["x"], s["y"])
    time.sleep(2)
else:
    print("    No send button found!")
    # Try fallback positions
    for tx, ty in [(1152, 1639), (1180, 1639)]:
        print(f"    Trying fallback ({tx},{ty})...")
        tap(tx, ty)
        time.sleep(1)
        r2 = ocr(min_confidence=0.3, preprocess=True)
        if any(MESSAGE.startswith(o["text"][:4]) for o in r2 if o["y"] < 1450):
            print("    Sent!")
            break

# ── 5. Verify ──
screenshot(str(OUT / "v10_sent.png"))
r = ocr(min_confidence=0.3, preprocess=True)
sent = [o for o in r if "docx" in o["text"].lower() or "架构" in o["text"]]
print(f"\n[5] Sent check: {len(sent)} matches")
for o in sent:
    print(f"    [{o['x']:.0f},{o['y']:.0f}] '{o['text']}'")
print("Done" if sent else "FAILED")
