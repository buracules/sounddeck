from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class BatteryInfo:
    percent: int    # 0-100
    charging: bool  # True if USB charging detected


class HeadsetBattery:
    """
    Best-effort SteelSeries Arctis battery reader via HID.

    Sends the 0xb0 status command on the vendor-specific (0xffc0) interface.
    Response byte[2] = battery 0-100, byte[3] = 0 when charging (empirical).
    Falls back silently if hidapi is not installed or no device found.
    """

    STEELSERIES_VID = 0x1038
    _CMD = b"\x00\xb0" + b"\x00" * 62

    def __init__(self) -> None:
        self._available = False
        self._path: bytes | None = None
        self._device_name: str = ""
        self._load()

    @property
    def available(self) -> bool:
        return self._available

    @property
    def device_name(self) -> str:
        return self._device_name

    def matches_display_name(self, display_name: str) -> bool:
        """Return True if display_name (Sonar device combo text) looks like this headset."""
        if not self._device_name or not display_name:
            return False
        needle = self._device_name.lower()
        hay = display_name.lower()
        # Check whole name or any significant word (skip generic words)
        if needle in hay:
            return True
        skip = {"the", "a", "an", "gen", "edition"}
        for word in needle.split():
            if len(word) > 3 and word not in skip and word in hay:
                return True
        return False

    def read(self) -> BatteryInfo | None:
        if not self._available or self._path is None:
            return None
        try:
            import hid as _hid
            dev = _hid.device()
            dev.open_path(self._path)
            dev.set_nonblocking(1)
            try:
                dev.write(self._CMD)
                time.sleep(0.12)
                resp = dev.read(64)
            finally:
                dev.close()
            if not resp or len(resp) < 5 or resp[0] != 0xb0:
                return None
            pct = max(0, min(100, int(resp[2])))
            charging = resp[3] == 1
            return BatteryInfo(percent=pct, charging=charging)
        except Exception:
            return None

    def _load(self) -> None:
        try:
            import hid as _hid
        except ImportError:
            return
        try:
            devs = [
                d for d in _hid.enumerate(self.STEELSERIES_VID)
                if d["usage_page"] == 0xFFC0
            ]
            if devs:
                self._path = devs[0]["path"]
                self._device_name = devs[0].get("product_string", "")
                self._available = True
        except Exception:
            pass
