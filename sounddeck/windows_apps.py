from __future__ import annotations

import os
from dataclasses import dataclass

from .audio_sessions import AudioSessionRegistry

_SYSTEM_ROOT = os.path.normcase(os.environ.get("SystemRoot", r"C:\Windows"))


@dataclass
class AppVolume:
    pid: int
    name: str
    volume: int   # 0-100
    muted: bool
    exe_path: str = ""   # for extracting the app icon
    key: str = ""        # stable across restarts; see app_key()


def app_key(exe_path: str, name: str) -> str:
    """
    Identifies an app across restarts, for settings that have to outlive it.

    The executable's filename, because a pid is different on every launch and a
    session's display name is whatever the app feels like reporting (Spotify
    reports the track it is playing). Falls back to the display name when the
    path is unreadable, which is the best that is left.
    """
    if exe_path:
        return os.path.basename(exe_path).lower()
    return name.strip().lower()


class WindowsAppVolumes:
    """
    Per-application volume/mute via Windows Core Audio sessions (pycaw).

    Every process holding an audio session becomes one row, driving that app's
    own ``ISimpleAudioVolume``. No virtual audio driver is needed, so this works
    whether or not Sonar is running — and when Sonar is running its channels are
    just more endpoints, which is why sessions come from the registry (all live
    render endpoints) rather than the default endpoint alone.

    An app may hold a session on several endpoints at once; a write has to reach
    every one of them or the app's volume only half-changes.

    All COM work happens inside a single call so it stays on one thread
    (comtypes initialises COM per-thread); callers may invoke from a worker.
    """

    _STATE_EXPIRED = 2

    def __init__(self, registry: AudioSessionRegistry | None = None) -> None:
        self._sessions = registry or AudioSessionRegistry()
        self._simple_volume = None
        self._psutil = None
        self._load()

    @property
    def available(self) -> bool:
        return self._simple_volume is not None and self._sessions.available

    def _load(self) -> None:
        try:
            import psutil
            from pycaw.pycaw import ISimpleAudioVolume
        except Exception:
            return
        self._simple_volume = ISimpleAudioVolume
        self._psutil = psutil

    def list_apps(self) -> list[AppVolume]:
        if not self.available:
            return []

        by_pid: dict[int, AppVolume] = {}
        for control in self._sessions.session_controls():
            try:
                pid = int(control.GetProcessId())
                # pid 0 is the system-sounds session — not an app.
                if pid <= 0 or pid in by_pid:
                    continue
                # A closed app's session lingers as "Expired" until Windows
                # releases it — skip those so closed apps drop out of the list.
                if int(control.GetState()) == self._STATE_EXPIRED:
                    continue
                name, exe_path = self._identify(control, pid)
                if name is None:
                    continue      # process is gone
                if self._is_windows_component(exe_path):
                    continue
                volume = control.QueryInterface(self._simple_volume)
                by_pid[pid] = AppVolume(
                    pid=pid,
                    name=name,
                    volume=int(round(self._clamp01(volume.GetMasterVolume()) * 100)),
                    muted=bool(volume.GetMute()),
                    exe_path=exe_path,
                    key=app_key(exe_path, name),
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

        def flip(volume) -> None:
            nonlocal target
            if target is None:
                target = not bool(volume.GetMute())
            volume.SetMute(target, None)

        self._apply(pid, flip)
        return bool(target)

    def _apply(self, pid: int, fn) -> None:
        if not self.available:
            return
        for volume in self._volumes_of(pid):
            try:
                fn(volume)
            except Exception:
                continue

    def _volumes_of(self, pid: int) -> list:
        out: list = []
        for control in self._sessions.session_controls():
            try:
                if int(control.GetProcessId()) != pid:
                    continue
                out.append(control.QueryInterface(self._simple_volume))
            except Exception:
                continue
        return out

    @staticmethod
    def _is_windows_component(exe_path: str) -> bool:
        """
        Windows' own shell processes hold audio sessions but are not something
        anyone wants a volume slider for — ShellExperienceHost sits in the list
        permanently once it makes a sound. They live under the Windows directory
        and installed apps never do, so location decides it: no list of process
        names to keep up to date as Windows adds or renames its own.
        """
        if not exe_path:
            # No read access to the path — can't tell, so leave it in view.
            return False
        try:
            return os.path.commonpath(
                [os.path.normcase(os.path.abspath(exe_path)), _SYSTEM_ROOT]
            ) == _SYSTEM_ROOT
        except ValueError:
            return False      # different drive, so definitely not under Windows

    def _identify(self, control, pid: int) -> tuple[str | None, str]:
        """(display name, exe path) for ``pid``, or (None, "") if it is gone."""
        process = None
        try:
            process = self._psutil.Process(pid)
        except Exception:
            return None, ""

        exe_path = ""
        try:
            exe_path = str(process.exe() or "")
        except Exception:
            exe_path = ""

        # Prefer the friendly session DisplayName, unless it is empty or a raw
        # resource pointer (e.g. "@%SystemRoot%\\..."), then fall back to the exe.
        display = ""
        try:
            display = str(control.GetDisplayName() or "").strip()
        except Exception:
            display = ""
        if display and not display.startswith("@"):
            return display, exe_path

        name = ""
        try:
            name = str(process.name() or "")
        except Exception:
            name = ""
        if name:
            if name.lower().endswith(".exe"):
                name = name[:-4]
            return name, exe_path
        return f"PID {pid}", exe_path

    @staticmethod
    def _clamp01(value: float) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return 0.0
