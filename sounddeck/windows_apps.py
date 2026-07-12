from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppVolume:
    pid: int
    name: str
    volume: int   # 0-100
    muted: bool
    exe_path: str = ""   # for extracting the app icon


class WindowsAppVolumes:
    """
    Per-application volume/mute via Windows Core Audio sessions (pycaw).

    Used as the Sonar-independent mixer: every process that has an audio session
    on the default render endpoint becomes one row. No virtual audio driver is
    needed — this drives each app's own ``ISimpleAudioVolume`` directly.

    All COM work happens inside a single call so it stays on one thread
    (comtypes initialises COM per-thread); callers may invoke from a worker.
    """

    def __init__(self) -> None:
        self._available = False
        self._utils = None
        self._load()

    @property
    def available(self) -> bool:
        return self._available

    def _load(self) -> None:
        try:
            from pycaw.pycaw import AudioUtilities
        except Exception:
            return
        self._utils = AudioUtilities
        self._available = True

    def list_apps(self) -> list[AppVolume]:
        if not self._available:
            return []
        try:
            sessions = self._utils.GetAllSessions()
        except Exception:
            return []

        by_pid: dict[int, AppVolume] = {}
        for session in sessions:
            try:
                volume = session.SimpleAudioVolume
                if volume is None:
                    continue
                process = getattr(session, "Process", None)
                pid = int(getattr(process, "pid", 0) or 0)
                if pid <= 0:
                    # System sounds session (pid 0) — skip; it isn't an app.
                    continue
                if pid in by_pid:
                    continue
                name = self._display_name(session, process, pid)
                level = int(round(self._clamp01(volume.GetMasterVolume()) * 100))
                muted = bool(volume.GetMute())
                exe_path = ""
                if process is not None:
                    try:
                        exe_path = str(process.exe() or "")
                    except Exception:
                        exe_path = ""
                by_pid[pid] = AppVolume(
                    pid=pid, name=name, volume=level, muted=muted, exe_path=exe_path
                )
            except Exception:
                continue
        return sorted(by_pid.values(), key=lambda a: a.name.lower())

    def set_volume(self, pid: int, value: int) -> None:
        scalar = self._clamp01(value / 100.0)
        self._apply(pid, lambda vol: vol.SetMasterVolume(scalar, None))

    def set_mute(self, pid: int, muted: bool) -> None:
        self._apply(pid, lambda vol: vol.SetMute(bool(muted), None))

    def toggle_mute(self, pid: int) -> bool:
        """Flip mute for every session of ``pid``; returns the new muted state."""
        target: bool | None = None
        if not self._available:
            return False
        try:
            sessions = self._utils.GetAllSessions()
        except Exception:
            return False
        for session in sessions:
            try:
                if int(getattr(getattr(session, "Process", None), "pid", 0) or 0) != pid:
                    continue
                volume = session.SimpleAudioVolume
                if volume is None:
                    continue
                if target is None:
                    target = not bool(volume.GetMute())
                volume.SetMute(target, None)
            except Exception:
                continue
        return bool(target)

    def _apply(self, pid: int, fn) -> None:
        if not self._available:
            return
        try:
            sessions = self._utils.GetAllSessions()
        except Exception:
            return
        for session in sessions:
            try:
                if int(getattr(getattr(session, "Process", None), "pid", 0) or 0) != pid:
                    continue
                volume = session.SimpleAudioVolume
                if volume is not None:
                    fn(volume)
            except Exception:
                continue

    @staticmethod
    def _display_name(session, process, pid: int) -> str:
        # Prefer the friendly session DisplayName, unless it is empty or a raw
        # resource pointer (e.g. "@%SystemRoot%\\..."), then fall back to the exe name.
        display = ""
        try:
            display = str(getattr(session, "DisplayName", "") or "").strip()
        except Exception:
            display = ""
        if display and not display.startswith("@"):
            return display
        name = ""
        if process is not None:
            try:
                name = str(process.name() or "")
            except Exception:
                name = ""
        if name:
            if name.lower().endswith(".exe"):
                name = name[:-4]
            return name
        return f"PID {pid}"

    @staticmethod
    def _clamp01(value: float) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return 0.0
