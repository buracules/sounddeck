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
