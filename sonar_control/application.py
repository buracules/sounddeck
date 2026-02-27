from __future__ import annotations

import sys
import subprocess
import threading
from datetime import datetime
from time import monotonic

from PySide6.QtWidgets import QApplication

from .audio_routing import AudioRoutingClient
from .config import AppConfig, config_file_path, load_config, save_config
from .notifications import Notifier
from .sonar_api_switcher import DeviceSelection, SonarApiSwitcher
from .sonar_client import SonarClient
from .tray import TrayController
from .ui import FlyoutMixerWindow


class SonarControlApplication:
    SWITCHABLE_CHANNELS = ("game", "chatRender", "media")
    INACTIVE_RETENTION_SECONDS = 30.0
    DEBUG_LOGS = False
    APP_ALIASES = {
        "gw2-64": "Guild Wars 2",
        "gw2-32": "Guild Wars 2",
        "gw2": "Guild Wars 2",
        "amplibraryagent": "Apple Music",
    }

    def __init__(self, compact_mode: bool = True) -> None:
        self._config: AppConfig = load_config()
        self._notifier = Notifier()
        self._client = SonarClient()
        self._api_switcher = SonarApiSwitcher()
        self._routing = AudioRoutingClient()
        self._qapp = QApplication.instance() or QApplication(sys.argv)

        self._window = FlyoutMixerWindow(
            on_refresh=self.refresh_channels,
            on_volume_change=self.set_volume,
            on_toggle_mute=self.toggle_mute,
            on_device_select=self.select_device,
            on_route_app=self.route_app_beta,
        )

        self._pending_volume_jobs: dict[str, threading.Timer] = {}
        self._volume_job_lock = threading.Lock()
        self._app_activity_lock = threading.Lock()
        self._app_last_active: dict[str, float] = {}
        self._alive = True

        self._tray = TrayController(
            on_toggle=self.toggle_window,
            on_refresh=self.refresh_channels,
            on_exit=self.exit_app,
        )
        self._window.hide()

    def run(self) -> None:
        self._tray.start()
        self.refresh_channels(show_toast=False)
        self._qapp.exec()

    def refresh_channels(self, show_toast: bool = False) -> None:
        def work() -> None:
            try:
                channels = self._client.get_channels()
                selections: dict[str, DeviceSelection | None] = {}
                for key in self.SWITCHABLE_CHANNELS:
                    try:
                        selections[key] = self._api_switcher.get_selection(key)
                    except Exception:
                        selections[key] = None
                sessions = self._routing.list_sessions()
                channel_apps: dict[str, list[tuple[str, str]]] = {"game": [], "chatRender": [], "media": []}
                best_by_app: dict[str, tuple[int, str, str, str]] = {}
                pid_label: dict[str, str] = {}
                now = monotonic()
                for s in sessions:
                    if s.process_id <= 0:
                        continue
                    if s.role not in channel_apps:
                        continue
                    if s.state.strip().lower() == "expired":
                        continue
                    pid = str(s.process_id)
                    app_label = self._alias_app_label(s.process_name, s.display_name, s.process_id)
                    app_key = app_label.lower()
                    if not app_key:
                        continue
                    state_key = s.state.strip().lower()
                    with self._app_activity_lock:
                        if state_key == "active":
                            self._app_last_active[app_key] = now
                        last_active = self._app_last_active.get(app_key)
                    if state_key == "inactive":
                        if last_active is None or now - last_active > self.INACTIVE_RETENTION_SECONDS:
                            continue
                    rank = self._session_rank(s.state, s.role)
                    current = best_by_app.get(app_key)
                    if current is None or rank > current[0]:
                        best_by_app[app_key] = (rank, pid, app_label, s.role)

                with self._app_activity_lock:
                    cutoff = now - (self.INACTIVE_RETENTION_SECONDS * 10)
                    self._app_last_active = {k: t for k, t in self._app_last_active.items() if t >= cutoff}

                for _, pid, app_label, role in sorted(best_by_app.values(), key=lambda v: v[2].lower()):
                    channel_apps[role].append((pid, app_label))
                    pid_label[pid] = app_label
                session_options = list(pid_label.items())
                if self.DEBUG_LOGS:
                    self._log_channel_apps(channel_apps)
                self._window.dispatch(lambda: self._window.set_channels(channels))
                self._window.dispatch(lambda s=selections: self._apply_device_selections(s))
                self._window.dispatch(lambda opts=session_options: self._window.set_app_sessions(opts))
                self._window.dispatch(lambda apps=channel_apps: self._window.set_channel_apps(apps))
                self._window.dispatch(lambda: self._window.set_status(self._status("Connected")))
                if show_toast:
                    self._notifier.show("Sonar", "Channel data refreshed")
            except Exception as exc:
                msg = f"Error: {exc}"
                self._window.dispatch(lambda m=msg: self._window.set_status(self._status(m)))

        threading.Thread(target=work, daemon=True).start()

    def set_volume(self, channel_key: str, value: int) -> None:
        with self._volume_job_lock:
            pending = self._pending_volume_jobs.pop(channel_key, None)
            if pending:
                pending.cancel()
            timer = threading.Timer(0.12, lambda: self._set_volume_now(channel_key, value))
            timer.daemon = True
            self._pending_volume_jobs[channel_key] = timer
            timer.start()

    def _set_volume_now(self, channel_key: str, value: int) -> None:
        with self._volume_job_lock:
            self._pending_volume_jobs.pop(channel_key, None)

        def work() -> None:
            try:
                self._client.set_volume(channel_key, value)
                self._window.dispatch(lambda: self._window.set_status(self._status(f"{channel_key} volume {value}%")))
                # Keep slider interaction local and smooth. A full refresh here can cause
                # unrelated channels to jump while dragging (especially on master).
                # Channel/state refresh remains available via explicit refresh actions.
            except Exception as exc:
                msg = f"Volume error: {exc}"
                self._window.dispatch(lambda m=msg: self._window.set_status(self._status(m)))

        threading.Thread(target=work, daemon=True).start()

    def toggle_mute(self, channel_key: str) -> None:
        def work() -> None:
            try:
                muted = self._client.toggle_muted(channel_key)
                self._window.dispatch(lambda: self._window.update_mute_state(channel_key, muted))
                self._window.dispatch(
                    lambda: self._window.set_status(self._status(f"{channel_key} {'muted' if muted else 'unmuted'}"))
                )
                self._notifier.show("Sonar", f"{channel_key} {'muted' if muted else 'unmuted'}")
            except Exception as exc:
                msg = f"Mute error: {exc}"
                self._window.dispatch(lambda m=msg: self._window.set_status(self._status(m)))

        threading.Thread(target=work, daemon=True).start()

    def select_device(self, channel_key: str, device_id: str) -> None:
        def work() -> None:
            try:
                result = self._api_switcher.set_device(channel_key, device_id)
                self._window.dispatch(
                    lambda: self._window.set_status(self._status(f"{channel_key}: {result.device_name} (API:{result.stream_id})"))
                )
                self._notifier.show("Sonar", f"{channel_key} -> {result.device_name}")
                self.refresh_channels(show_toast=False)
            except Exception as exc:
                msg = f"Switch error: {exc}"
                self._window.dispatch(lambda m=msg: self._window.set_status(self._status(m)))

        threading.Thread(target=work, daemon=True).start()

    def _apply_device_selections(self, selections: dict[str, DeviceSelection | None]) -> None:
        for key, selection in selections.items():
            if selection is None:
                self._window.set_device_choices(key, [], None)
                continue
            options = [(opt.id, opt.name) for opt in selection.options]
            self._window.set_device_choices(key, options, selection.current_device_id)

    def route_app_beta(self, session_id: str, target_role: str) -> None:
        def work() -> None:
            try:
                process_id = int(session_id)
                if self.DEBUG_LOGS:
                    print(f"[route] request pid={process_id} -> {target_role}")
                self._routing.route_process(process_id, target_role)
                self._window.dispatch(lambda: self._window.set_status(self._status(f"pid {process_id} -> {target_role}")))
                self._notifier.show("Sonar", f"App routed to {target_role}")
                # Sonar routing state propagates asynchronously; refresh after a short delay
                # so UI does not snap back to stale role assignments.
                threading.Timer(1.2, lambda: self.refresh_channels(show_toast=False)).start()
            except Exception as exc:
                msg = f"Route failed: {exc}"
                if self.DEBUG_LOGS:
                    print(f"[route] failed pid={session_id} -> {target_role}: {exc}")
                self._window.dispatch(lambda m=msg: self._window.set_status(self._status(m)))

        threading.Thread(target=work, daemon=True).start()

    def toggle_window(self) -> None:
        self._window.dispatch(self._toggle_window_main)

    def _toggle_window_main(self) -> None:
        self._window.toggle_near(self._tray.geometry())

    def exit_app(self) -> None:
        if not self._alive:
            return
        self._alive = False

        def do_exit() -> None:
            with self._volume_job_lock:
                for timer in self._pending_volume_jobs.values():
                    timer.cancel()
                self._pending_volume_jobs.clear()
            self._tray.stop()
            self._window.close()
            self._qapp.quit()

        self._window.dispatch(do_exit)

    @staticmethod
    def _status(message: str) -> str:
        now = datetime.now().strftime("%H:%M:%S")
        return f"[{now}] {message}"

    @staticmethod
    def _log_channel_apps(channel_apps: dict[str, list[tuple[str, str]]]) -> None:
        def labels(role: str) -> str:
            items = [label for _, label in channel_apps.get(role, [])]
            return ", ".join(items) if items else "-"

        print(
            "[routes] "
            f"game=[{labels('game')}] "
            f"chat=[{labels('chatRender')}] "
            f"media=[{labels('media')}]"
        )

    @staticmethod
    def _session_rank(state: str, role: str) -> int:
        state_key = state.strip().lower()
        state_score = {"active": 300, "inactive": 200, "expired": 100}.get(state_key, 50)
        role_score = {"game": 30, "chatRender": 20, "media": 10}.get(role, 0)
        return state_score + role_score

    @classmethod
    def _alias_app_label(cls, process_name: str, display_name: str, process_id: int) -> str:
        raw = (process_name or display_name).strip()
        if not raw:
            return f"App {process_id}"
        key = raw.lower()
        if key in cls.APP_ALIASES:
            return cls.APP_ALIASES[key]
        return raw
