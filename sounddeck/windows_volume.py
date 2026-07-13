from __future__ import annotations

from .models import ChannelState


class WindowsVolume:
    """Windows default audio endpoint volume control via pycaw."""

    def __init__(self) -> None:
        self._ctrl = None
        self._load()

    @property
    def available(self) -> bool:
        return self._ctrl is not None

    def _load(self) -> None:
        try:
            from pycaw.pycaw import AudioUtilities
            self._ctrl = AudioUtilities.GetSpeakers().EndpointVolume
        except Exception:
            pass

    def reload(self) -> None:
        """Re-acquire the current default render endpoint.

        The endpoint control is bound at construction time, so after the default
        output device changes this must be called for the master strip to drive
        the newly selected device.
        """
        self._ctrl = None
        self._load()

    def get_state(self) -> ChannelState:
        try:
            vol = int(round(self._ctrl.GetMasterVolumeLevelScalar() * 100))
            muted = bool(self._ctrl.GetMute())
            return ChannelState(key="master", label="Master", volume=vol, muted=muted)
        except Exception:
            return ChannelState(key="master", label="Master", volume=50, muted=False)

    def set_volume(self, value: int) -> None:
        try:
            self._ctrl.SetMasterVolumeLevelScalar(max(0.0, min(1.0, value / 100.0)), None)
        except Exception:
            pass

    def toggle_mute(self) -> bool:
        try:
            target = not bool(self._ctrl.GetMute())
            self._ctrl.SetMute(target, None)
            return target
        except Exception:
            return False


class WindowsOutputDevices:
    """Enumerate and switch the Windows default render (output) endpoint via pycaw.

    Used in the Sonar-independent (Windows) mode to let the user pick which
    playback device the system routes audio to. All COM work happens inside a
    single call so it stays on one thread (comtypes initialises COM per-thread);
    callers may invoke from a worker.
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
            from pycaw.pycaw import AudioUtilities  # noqa: F401
        except Exception:
            return
        self._utils = AudioUtilities
        self._available = True

    def list_devices(self) -> list[tuple[str, str]]:
        """Active render endpoints as ``(device_id, friendly_name)`` pairs."""
        if not self._available:
            return []
        try:
            from pycaw.constants import DEVICE_STATE, EDataFlow
            devices = self._utils.GetAllDevices(
                EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value
            )
        except Exception:
            return []
        out: list[tuple[str, str]] = []
        for dev in devices:
            try:
                dev_id = str(getattr(dev, "id", "") or "")
                name = str(getattr(dev, "FriendlyName", "") or "").strip()
                if dev_id and name:
                    out.append((dev_id, name))
            except Exception:
                continue
        out.sort(key=lambda d: d[1].lower())
        return out

    def get_default_id(self) -> str | None:
        """Device id of the current default (multimedia) render endpoint."""
        if not self._available:
            return None
        try:
            speakers = self._utils.GetSpeakers()
            return (str(getattr(speakers, "id", "") or "") or None)
        except Exception:
            return None

    def set_default(self, device_id: str) -> str:
        """Make ``device_id`` the default output for all roles; return its name."""
        if not self._available:
            raise RuntimeError("Audio device control unavailable")
        from pycaw.constants import ERole
        roles = [ERole.eConsole, ERole.eMultimedia, ERole.eCommunications]
        self._utils.SetDefaultDevice(device_id, roles)
        for dev_id, name in self.list_devices():
            if dev_id == device_id:
                return name
        return device_id


class WindowsMic:
    """Default capture (microphone) endpoint volume/mute via pycaw."""

    def __init__(self) -> None:
        self._ctrl = None
        self._load()

    @property
    def available(self) -> bool:
        return self._ctrl is not None

    def _load(self) -> None:
        try:
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            mic = AudioUtilities.GetMicrophone()
            interface = mic.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self._ctrl = cast(interface, POINTER(IAudioEndpointVolume))
        except Exception:
            self._ctrl = None

    def get_state(self) -> tuple[int, bool] | None:
        try:
            vol = int(round(self._ctrl.GetMasterVolumeLevelScalar() * 100))
            muted = bool(self._ctrl.GetMute())
            return vol, muted
        except Exception:
            return None

    def set_volume(self, value: int) -> None:
        try:
            self._ctrl.SetMasterVolumeLevelScalar(max(0.0, min(1.0, value / 100.0)), None)
        except Exception:
            pass

    def set_mute(self, muted: bool) -> None:
        try:
            self._ctrl.SetMute(bool(muted), None)
        except Exception:
            pass

    def toggle_mute(self) -> bool:
        try:
            target = not bool(self._ctrl.GetMute())
            self._ctrl.SetMute(target, None)
            return target
        except Exception:
            return False
