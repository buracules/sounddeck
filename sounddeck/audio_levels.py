from __future__ import annotations

import threading
from dataclasses import dataclass
from time import monotonic

from .audio_sessions import AudioSessionRegistry


@dataclass
class AudioLevels:
    master: float = 0.0
    by_pid: dict[int, float] | None = None


class AudioLevelClient:
    """
    Best-effort Windows Core Audio peak reader.

    Uses pycaw when available. If the optional dependency is missing or the
    audio stack is unavailable, callers get silent levels instead of failures.
    """

    def __init__(self, registry: AudioSessionRegistry | None = None) -> None:
        self._available = False
        self._audio_utilities = None
        self._meter_interface = None
        self._clsctx_all = None
        self._cast = None
        self._pointer = None
        self._sessions = registry or AudioSessionRegistry()
        self._local = threading.local()
        self._load()

    @property
    def available(self) -> bool:
        return self._available

    def read_levels(self) -> AudioLevels:
        if not self._available:
            return AudioLevels(by_pid={})

        by_pid = self._read_session_peaks()
        master = self._read_master_peak()
        if master <= 0.0 and by_pid:
            master = max(by_pid.values(), default=0.0)
        return AudioLevels(master=master, by_pid=by_pid)

    def _load(self) -> None:
        try:
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
        except Exception:
            return

        self._audio_utilities = AudioUtilities
        self._meter_interface = IAudioMeterInformation
        self._clsctx_all = CLSCTX_ALL
        self._cast = cast
        self._pointer = POINTER
        self._available = True

    def _read_master_peak(self) -> float:
        meter = self._master_meter()
        if meter is None:
            return 0.0
        try:
            return self._clamp(meter.GetPeakValue())
        except Exception:
            # The endpoint went away underneath us; re-resolve on the next poll.
            self._sessions.invalidate()
            return 0.0

    def _master_meter(self):
        """
        The default endpoint's meter. Re-resolving it costs ~12ms — most of a
        poll — so it is kept for as long as the registry's endpoints are: dropped
        at once when we change the default output ourselves, and otherwise re-read
        on the same interval, which is what catches a default changed in Windows.
        """
        cached = getattr(self._local, "meter", None)
        generation = self._sessions.generation
        if cached is not None:
            meter, cached_generation, built_at = cached
            fresh = monotonic() - built_at < self._sessions.REBUILD_INTERVAL_SECONDS
            if cached_generation == generation and fresh:
                return meter
        meter = None
        device = self._sessions.default_render_device()
        if device is not None:
            try:
                interface = device.Activate(self._meter_interface._iid_, self._clsctx_all, None)
                meter = self._cast(interface, self._pointer(self._meter_interface))
            except Exception:
                meter = None
        self._local.meter = (meter, generation, monotonic())
        return meter

    def _read_session_peaks(self) -> dict[int, float]:
        if self._sessions.available:
            return self._read_all_device_peaks()
        return self._read_default_device_peaks()

    def _read_all_device_peaks(self) -> dict[int, float]:
        out: dict[int, float] = {}
        for control in self._sessions.session_controls():
            try:
                pid = int(control.GetProcessId())
                if pid <= 0:
                    continue
                peak = self._clamp(
                    control.QueryInterface(self._meter_interface).GetPeakValue()
                )
                # One app can play on several endpoints; loudest wins.
                out[pid] = max(out.get(pid, 0.0), peak)
            except Exception:
                continue
        return out

    def _read_default_device_peaks(self) -> dict[int, float]:
        out: dict[int, float] = {}
        try:
            sessions = self._audio_utilities.GetAllSessions()
        except Exception:
            return out
        for session in sessions:
            try:
                process = getattr(session, "Process", None)
                pid = int(getattr(process, "pid", 0) or 0)
                if pid <= 0:
                    continue
                meter = session._ctl.QueryInterface(self._meter_interface)
                peak = self._clamp(meter.GetPeakValue())
                out[pid] = max(out.get(pid, 0.0), peak)
            except Exception:
                continue
        return out

    @staticmethod
    def _clamp(value: float) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return 0.0
