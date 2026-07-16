from __future__ import annotations

import threading
from time import monotonic


class AudioSessionRegistry:
    """
    Every application audio session, across all the render endpoints in use.

    Sonar gives each of its channels a virtual endpoint and spreads apps over
    them, so the default endpoint alone never sees the whole picture — each
    active render device has to be walked.

    Doing that from scratch costs ~330ms, almost all of it spent enumerating the
    ~47 endpoints Windows remembers (nearly every one unplugged, disabled or
    absent) just to find the two or three that are live. That is far too slow for
    a peak meter polled every 80ms. So the endpoints are resolved once and their
    session managers reused; each call only re-reads the session list off them,
    which costs about a millisecond. Endpoints are re-resolved periodically, and
    on demand via invalidate(), so devices coming and going are still picked up.

    COM interface pointers belong to the thread that created them and the callers
    here span several threads (the meter poll, each refresh worker), so the cache
    is thread-local: every thread pays the resolve once and then runs cheap.
    """

    REBUILD_INTERVAL_SECONDS = 10.0

    def __init__(self) -> None:
        self._local = threading.local()
        self._generation = 0
        self._generation_lock = threading.Lock()
        self._audio_utilities = None
        self._device_state = None
        self._data_flow = None
        self._control_interface = None
        self._manager_interface = None
        self._clsctx_all = None
        self._load()

    @property
    def available(self) -> bool:
        return self._audio_utilities is not None

    @property
    def generation(self) -> int:
        """Bumped by invalidate(); callers caching their own endpoint-derived COM
        objects can key them on this to drop them at the same time."""
        with self._generation_lock:
            return self._generation

    def _load(self) -> None:
        try:
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import (
                AudioUtilities,
                DEVICE_STATE,
                EDataFlow,
                IAudioSessionControl2,
                IAudioSessionManager2,
            )
        except Exception:
            return
        self._device_state = DEVICE_STATE
        self._data_flow = EDataFlow
        self._control_interface = IAudioSessionControl2
        self._manager_interface = IAudioSessionManager2
        self._clsctx_all = CLSCTX_ALL
        self._audio_utilities = AudioUtilities      # last: it gates available

    def invalidate(self) -> None:
        """Drop the cached endpoints on every thread — call when they may have changed."""
        with self._generation_lock:
            self._generation += 1

    def _ensure_com(self) -> None:
        """
        comtypes initialises COM on the thread that imports it and nowhere else,
        but the callers here include a fresh refresh worker per cycle. On those,
        COM calls fail with "CoInitialize has not been called" — which would
        surface, silently, as an empty app list. So each thread initialises once;
        Windows tears the apartment down when the thread ends.
        """
        if getattr(self._local, "com_ready", False):
            return
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass
        self._local.com_ready = True

    def session_controls(self) -> list:
        """
        An ``IAudioSessionControl2`` for every app session on the live render
        endpoints. One app can hold sessions on several of them, so callers that
        act on a process must handle each session rather than only the first.
        """
        if not self.available:
            return []
        self._ensure_com()
        out: list = []
        for manager in self._session_managers():
            try:
                enumerator = manager.GetSessionEnumerator()
                for index in range(enumerator.GetCount()):
                    try:
                        out.append(
                            enumerator.GetSession(index).QueryInterface(self._control_interface)
                        )
                    except Exception:
                        continue
            except Exception:
                continue
        return out

    def default_render_device(self):
        """
        The current default render endpoint, or None. Resolving it is as slow as
        the endpoint walk above, so it is cached on the same terms.
        """
        if not self.available:
            return None
        self._ensure_com()
        cached = getattr(self._local, "default_device", None)
        if cached is not None:
            device, cached_generation, built_at = cached
            if cached_generation == self.generation and monotonic() - built_at < self.REBUILD_INTERVAL_SECONDS:
                return device
        try:
            device = self._audio_utilities.GetSpeakers()
        except Exception:
            device = None
        self._local.default_device = (device, self.generation, monotonic())
        return device

    def _session_managers(self) -> list:
        with self._generation_lock:
            generation = self._generation
        cached = getattr(self._local, "cache", None)
        if cached is not None:
            managers, cached_generation, built_at = cached
            fresh = monotonic() - built_at < self.REBUILD_INTERVAL_SECONDS
            if cached_generation == generation and fresh:
                return managers
        managers = self._build_session_managers()
        self._local.cache = (managers, generation, monotonic())
        return managers

    def _build_session_managers(self) -> list:
        managers: list = []
        if not self.available:
            return managers
        try:
            enumerator = self._audio_utilities.GetDeviceEnumerator()
            # Only the live render endpoints: asking Windows for all of them is
            # what made this slow, and the rest have no sessions to offer anyway.
            devices = enumerator.EnumAudioEndpoints(
                self._data_flow.eRender.value, self._device_state.ACTIVE.value
            )
            count = devices.GetCount()
        except Exception:
            return managers
        for index in range(count):
            try:
                device = devices.Item(index)
                # QueryInterface AddRefs properly, where cast() would double-Release.
                managers.append(
                    device.Activate(self._manager_interface._iid_, self._clsctx_all, None)
                    .QueryInterface(self._manager_interface)
                )
            except Exception:
                continue
        return managers
