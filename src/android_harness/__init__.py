"""Android control via ADB.

Core helpers live here. Agent-editable helpers live in
AH_AGENT_WORKSPACE/agent_helpers.py (defaults to <repo>/agent-workspace).
"""

from .device import (
    adb, set_adb_path,
    list_devices, device_info, connection_state,
    ADB_PATH,
)
from .capture import screenshot
from .ocr import ocr, find_text
from .input import tap, long_press, swipe, scroll, type_text, press, keyevent
from . import admin

# Agent-editable helpers — auto-loaded at import time
import importlib.util
import os
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CORE_DIR.parent.parent
AGENT_WORKSPACE = Path(
    os.environ.get("AH_AGENT_WORKSPACE", REPO_ROOT / "agent-workspace"))


def _load_agent_helpers():
    p = AGENT_WORKSPACE / "agent_helpers.py"
    if not p.exists():
        return
    spec = importlib.util.spec_from_file_location(
        "android_harness_agent_helpers", p)
    if not spec or not spec.loader:
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, value in vars(module).items():
        if not name.startswith("_"):
            globals()[name] = value


_load_agent_helpers()
