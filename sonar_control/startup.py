from __future__ import annotations

import sys
from pathlib import Path

if sys.platform == "win32":
    import winreg


RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "SonarMixer"


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable)
        return f'"{exe_path}"'

    script = Path(__file__).resolve().parent.parent / "app.py"
    python_exe = Path(sys.executable)
    return f'"{python_exe}" "{script}"'


def is_startup_enabled() -> bool:
    if sys.platform != "win32":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE_NAME)
            return str(value).strip() == launch_command()
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_startup_enabled(enabled: bool) -> None:
    if sys.platform != "win32":
        return

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, launch_command())
            return
        try:
            winreg.DeleteValue(key, RUN_VALUE_NAME)
        except FileNotFoundError:
            return
