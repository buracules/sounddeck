from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    window_visible: bool = True


def _config_path() -> Path:
    base = Path.home() / "AppData" / "Roaming" / "AudioSwitcher" / "SonarControlPanel"
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.json"


def load_config() -> AppConfig:
    path = _config_path()
    if not path.exists():
        cfg = AppConfig()
        save_config(cfg)
        return cfg

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AppConfig(window_visible=bool(data.get("window_visible", True)))
    except Exception:
        return AppConfig()


def save_config(config: AppConfig) -> None:
    path = _config_path()
    payload = {"window_visible": config.window_visible}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def config_file_path() -> Path:
    return _config_path()
