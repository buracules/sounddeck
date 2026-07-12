from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    compact_mode: bool = True
    cyber_mode: bool = True
    close_on_outside: bool = False
    lock_position: bool = False
    app_overrides: dict[str, dict[str, str]] | None = None


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
        app_overrides = data.get("app_overrides")
        if not isinstance(app_overrides, dict):
            app_overrides = {}
        return AppConfig(
            compact_mode=bool(data.get("compact_mode", True)),
            cyber_mode=bool(data.get("cyber_mode", True)),
            close_on_outside=bool(data.get("close_on_outside", False)),
            lock_position=bool(data.get("lock_position", False)),
            app_overrides={
                str(key): {str(k): str(v) for k, v in value.items() if isinstance(v, str)}
                for key, value in app_overrides.items()
                if isinstance(value, dict)
            },
        )
    except Exception:
        return AppConfig()


def save_config(config: AppConfig) -> None:
    path = _config_path()
    payload = {
        "compact_mode": config.compact_mode,
        "cyber_mode": config.cyber_mode,
        "close_on_outside": config.close_on_outside,
        "lock_position": config.lock_position,
        "app_overrides": config.app_overrides or {},
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def config_file_path() -> Path:
    return _config_path()
