from __future__ import annotations

from dataclasses import dataclass


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

    def __init__(self) -> None:
        self._available = False
        self._multi_device = False
        self._audio_utilities = None
        self._meter_interface = None
        self._clsctx_all = None
        self._cast = None
        self._pointer = None
        self._session_mgr_interface = None
        self._session_ctrl2_interface = None
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

        # Multi-device: read sessions from all Sonar virtual endpoints.
        try:
            from pycaw.pycaw import IAudioSessionManager2, IAudioSessionControl2
            self._session_mgr_interface = IAudioSessionManager2
            self._session_ctrl2_interface = IAudioSessionControl2
            self._multi_device = True
        except Exception:
            pass

    def _read_master_peak(self) -> float:
        try:
            speakers = self._audio_utilities.GetSpeakers()
            interface = speakers.Activate(self._meter_interface._iid_, self._clsctx_all, None)
            meter = self._cast(interface, self._pointer(self._meter_interface))
            return self._clamp(meter.GetPeakValue())
        except Exception:
            return 0.0

    def _read_session_peaks(self) -> dict[int, float]:
        if self._multi_device:
            return self._read_all_device_peaks()
        return self._read_default_device_peaks()

    def _read_all_device_peaks(self) -> dict[int, float]:
        out: dict[int, float] = {}
        try:
            devices = self._audio_utilities.GetAllDevices()
            for device in devices:
                try:
                    # QueryInterface properly AddRefs — avoids double-Release from cast()
                    manager = device._dev.Activate(
                        self._session_mgr_interface._iid_,
                        self._clsctx_all,
                        None,
                    ).QueryInterface(self._session_mgr_interface)
                    session_enum = manager.GetSessionEnumerator()
                    for j in range(session_enum.GetCount()):
                        try:
                            ctrl2 = session_enum.GetSession(j).QueryInterface(
                                self._session_ctrl2_interface
                            )
                            pid = int(ctrl2.GetProcessId())
                            if pid <= 0:
                                continue
                            peak = self._clamp(
                                ctrl2.QueryInterface(self._meter_interface).GetPeakValue()
                            )
                            out[pid] = max(out.get(pid, 0.0), peak)
                        except Exception:
                            continue
                except Exception:
                    continue
        except Exception:
            pass
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
