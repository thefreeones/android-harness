# android-harness

**AI Agent 的 Android 手操控层**——截屏当眼，ADB 当手。

让电脑端的 AI Agent（Claude Code、Hermes、Codex 等）直接操控 Android 手机：打开应用、点击界面、中文输入、滑动浏览、截图 OCR 感知。

```
pip install android-harness
android-harness --doctor
```

## 为什么需要

很多 AI 自动化场景绕不开手机：微信发消息、App 验证、移动端界面测试。agent 在电脑上跑，但任务卡在手机屏幕上。

android-harness 在二者之间架一座桥——Agent 说「找微信里的某某发个消息」，剩下的 OCR 定位、点击、打字、发送都由 harness 完成。

## 核心能力

| 能力 | 实现 | 备注 |
|------|------|------|
| 截图 | `adb screencap` + PNG 拉取 | ~1.5s/帧 |
| OCR 感知 | PaddleOCR PP-OCRv4 + **GPU 加速** | 热身后 ~1.4s，含暗色 UI 反色预处理 |
| 点击 | ADB `input tap` | 坐标映射无窗口偏移 |
| 中文输入 | **ADBKeyboard** + IME 自动切换 | 非 ASCII 自动切 IME + 广播 + 恢复 |
| 滑动/按键 | ADB `input swipe` / `keyevent` | — |
| 打开应用 | `monkey` 包名启动 | 绕过启动器图标 |
| 自检 | `--doctor` | 6 步硬件/权限检查 |

## 快速开始

```bash
# 安装
git clone https://github.com/thefreeones/android-harness.git
cd android-harness
uv venv .venv
uv pip install -e . "paddlepaddle<3.0" "paddleocr<3.0"

# 自检
python -m android_harness --doctor

# 一键启动
ah.bat                             # Windows
```

**中文输入前置步骤：** 安装 ADBKeyboard APK 到手机（仅一次）→ `adb shell ime enable com.android.adbkeyboard/.AdbIME`

## 使用示例

```python
from android_harness import ocr, tap, type_text, open_app, screenshot

# 打开微信
open_app("微信", package="com.tencent.mm")

# OCR 感知屏幕
results = ocr(min_confidence=0.5)
# → [{"text": "文件传输助手", "x": 400, "y": 822, "confidence": 1.0}, ...]

# 找到文字并点击
for r in results:
    if "文件传输助手" in r["text"]:
        tap(r["x"], r["y"])
        break

# 点击输入框，打字并发送
tap(632, 2665)                     # 点击输入框
type_text("你好")                    # 中文输入
tap(1152, 1639)                     # 点击发送
```

完整 E2E 模板见 [`wechat_send.py`](wechat_send.py)。

## Benchmark

5 应用 OCR 量化测试（1264×2780, GPU, dark mode）：

| App | 耗时 | 检测区域 | 高置信率 | 预处理收益 |
|-----|------|----------|----------|-----------|
| 微信设置 | 1.4s | 22 | 86% | **+22%** |
| 短信 | 1.8s | 34 | 82% | +6% |
| 主屏幕 | 1.4s | 24 | 92% | 壁纸自动跳过 |
| QQ（待补） | — | — | — | — |
| 浏览器（待补） | — | — | — | — |

## 技术架构

```
┌──────────────┐     ┌─────────────────┐     ┌───────────┐
│  Agent (PC)  │────▶│ android-harness  │────▶│  Android  │
│              │     │  ├─ OCR (GPU)    │ ADB │  真机     │
│              │◀────│  ├─ Input        │◀────│           │
└──────────────┘     │  ├─ Capture      │     └───────────┘
                     │  └─ Device       │
                     └─────────────────┘
```

- **传输层**：ADB（USB/WiFi），不依赖 scrcpy 做操作
- **OCR 后端**：PaddleOCR 2.x + PP-OCRv4，GPU 推理（RTX4070 验证）
- **中文输入**：ADBKeyboard IME 广播机制
- **坐标系统**：Android 原生屏幕空间，零窗口偏移

## 兼容性

| | 已验证 | 预期兼容 |
|---|--------|----------|
| 手机 | realme ColorOS Android 15 | Android 10+ |
| PC | Windows 10/11 | Linux, macOS |
| GPU | NVIDIA RTX 4070 + CUDA 11 | PaddlePaddle 支持的 GPU |

## 局限性

- **截图延迟**：ADB screencap ~1.5s，比 iPhone Mirroring 的 ~100ms 慢一个数量级
- **无多点触控**：`adb shell input` 不支持 pinch、双指滚动等手势
- **单设备**：V1 未实现多设备并发
- **依赖 ADBKeyboard**：中文输入需要单独安装 APK

## 致谢

本项目受 [ShawnPana/phone-harness](https://github.com/ShawnPana/phone-harness) 启发——phone-harness 展示了「截屏 + OCR + HID 事件」的完整范式，在 macOS 上通过 iPhone Mirroring 实现。android-harness 将这一思路迁移到 Android 平台，采用 ADB + PaddleOCR 的技术路线，服务于 Windows 生态的 AI Agent。

## License

MIT
