from __future__ import annotations

from typing import Any

from .models import ChannelState


class SonarClient:
    CHANNELS = [
        ("master", "Master"),
        ("game", "Game"),
        ("chatRender", "Chat"),
        ("media", "Media"),
    ]

    def __init__(self) -> None:
        self._api: Any = None
        self._connected = False

    def connect(self) -> None:
        if self._connected:
            return

        try:
            from steelseries_sonar_py import Sonar  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "Failed to import steelseries-sonar-py module. Run: pip install -r requirements.txt"
            ) from exc

        try:
            self._api = Sonar()
        except Exception as exc:
            raise RuntimeError(f"Failed to connect to Sonar API: {exc}") from exc

        self._connected = True

    def _ensure(self) -> Any:
        if not self._connected:
            self.connect()
        return self._api

    def get_channels(self) -> list[ChannelState]:
        api = self._ensure()
        raw = api.get_volume_data()
        channels: list[ChannelState] = []

        for key, label in self.CHANNELS:
            value = self._extract_channel(raw, key)
            volume = self._extract_volume_percent(value)
            muted = self._extract_muted(value)
            channels.append(ChannelState(key=key, label=label, volume=volume, muted=muted))

        return channels

    def set_volume(self, channel_key: str, volume_percent: int) -> None:
        api = self._ensure()
        volume = max(0.0, min(1.0, volume_percent / 100.0))
        api.set_volume(channel_key, volume)

    def set_muted(self, channel_key: str, muted: bool) -> None:
        api = self._ensure()
        api.mute_channel(channel_key, muted)

    def toggle_muted(self, channel_key: str) -> bool:
        channels = self.get_channels()
        current = next((c for c in channels if c.key == channel_key), None)
        target = not current.muted if current else True
        self.set_muted(channel_key, target)
        return target

    @staticmethod
    def _extract_channel(raw: Any, channel_key: str) -> Any:
        # Actual Sonar payload shape:
        # {"masters": {"classic": {...}}, "devices": {"game": {"classic": {...}}}}
        if isinstance(raw, dict):
            if channel_key == "master":
                masters = raw.get("masters")
                if isinstance(masters, dict):
                    classic = masters.get("classic")
                    if isinstance(classic, dict):
                        return classic

            devices = raw.get("devices")
            if isinstance(devices, dict):
                channel_data = devices.get(channel_key)
                if isinstance(channel_data, dict):
                    classic = channel_data.get("classic")
                    if isinstance(classic, dict):
                        return classic
                    return channel_data

            if channel_key in raw:
                return raw[channel_key]

            lower_map = {str(k).lower(): v for k, v in raw.items()}
            return lower_map.get(channel_key.lower(), {})

        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    name = str(item.get("channel") or item.get("name") or "").lower()
                    if name == channel_key.lower():
                        return item

        return {}

    @staticmethod
    def _extract_volume_percent(channel_value: Any) -> int:
        if isinstance(channel_value, dict):
            for candidate in ("Volume", "volume", "level", "value"):
                if candidate in channel_value:
                    raw_volume = channel_value[candidate]
                    if isinstance(raw_volume, (float, int)):
                        if raw_volume <= 1.0:
                            return int(round(raw_volume * 100))
                        return int(round(max(0, min(100, raw_volume))))

        if isinstance(channel_value, (float, int)):
            if channel_value <= 1.0:
                return int(round(channel_value * 100))
            return int(round(max(0, min(100, channel_value))))

        return 50

    @staticmethod
    def _extract_muted(channel_value: Any) -> bool:
        if isinstance(channel_value, dict):
            for candidate in ("Mute", "mute", "muted", "isMuted"):
                if candidate in channel_value:
                    return bool(channel_value[candidate])
        return False
