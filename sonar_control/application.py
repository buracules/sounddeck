from __future__ import annotations

import sys
import threading
from datetime import datetime
from time import monotonic

from PySide6.QtWidgets import QApplication

from .audio_levels import AudioLevelClient
from .audio_routing import AudioRoutingClient
from .config import AppConfig, config_file_path, load_config, save_config
from .notifications import Notifier
from .sonar_api_switcher import DeviceSelection, SonarApiSwitcher
from .sonar_client import SonarClient
from .startup import is_startup_enabled, set_startup_enabled
from .tray import TrayController
from .ui import FlyoutMixerWindow, SettingsWindow


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
        self._compact_mode = bool(getattr(self._config, "compact_mode", compact_mode))
        self._cyber_mode = bool(getattr(self._config, "cyber_mode", False))
        self._notifier = Notifier()
        self._client = SonarClient()
        self._api_switcher = SonarApiSwitcher()
        self._routing = AudioRoutingClient()
        self._levels = AudioLevelClient()
        self._qapp = QApplication.instance() or QApplication(sys.argv)
        self._load_bundled_fonts()

        self._window = FlyoutMixerWindow(
            on_refresh=self.refresh_channels,
            on_volume_change=self.set_volume,
            on_toggle_mute=self.toggle_mute,
            on_device_select=self.select_device,
            on_route_app=self.route_app_beta,
            on_customize_app=self.customize_app,
        )

        self._pending_volume_jobs: dict[str, threading.Timer] = {}
        self._volume_job_lock = threading.Lock()
        self._app_activity_lock = threading.Lock()
        self._app_last_active: dict[str, float] = {}
        self._level_lock = threading.Lock()
        self._channel_level_pids: dict[str, list[int]] = {"game": [], "chatRender": [], "media": []}
        self._show_logs = False
        self._alive = True
        self._settings = SettingsWindow(
            on_toggle_startup=self.toggle_startup_with_windows,
            on_toggle_compact=self.toggle_compact_mode,
            on_toggle_logs=self.toggle_logs_visibility,
            config_path=str(config_file_path()),
            on_toggle_cyber=self.toggle_cyber_mode,
        )

        self._tray = TrayController(
            on_toggle=self.toggle_window,
            on_refresh=self.refresh_channels,
            on_settings=self.show_settings,
            on_toggle_compact=self.toggle_compact_mode,
            compact_mode=self._compact_mode,
            on_toggle_logs=self.toggle_logs_visibility,
            show_logs=self._show_logs,
            on_toggle_startup=self.toggle_startup_with_windows,
            startup_enabled=is_startup_enabled(),
            on_exit=self.exit_app,
            on_toggle_cyber=self.toggle_cyber_mode,
            cyber_mode=self._cyber_mode,
        )
        self._window.set_compact(self._compact_mode)
        self._window.set_logs_visible(self._show_logs)
        if self._cyber_mode:
            self._window.set_cyber_mode(True)
        self._window.hide()
        self._settings.set_states(is_startup_enabled(), self._compact_mode, self._show_logs, self._cyber_mode)

    @staticmethod
    def _load_bundled_fonts() -> None:
        from pathlib import Path
        from PySide6.QtGui import QFontDatabase
        assets = Path(__file__).resolve().parent / "assets"
        for ttf in assets.glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(ttf))

    def run(self) -> None:
        self._tray.start()
        self.refresh_channels(show_toast=False)
        self._start_level_polling()
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
                channel_apps: dict[str, list[tuple[str, str, str, str]]] = {"game": [], "chatRender": [], "media": []}
                best_by_app: dict[str, tuple[int, str, str, str, str, str]] = {}
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
                    app_key = self._app_identity(s.process_name, s.display_name, s.process_id)
                    if not app_key:
                        continue
                    default_label = self._alias_app_label(s.process_name, s.display_name, s.process_id)
                    app_label, app_color = self._apply_app_override(app_key, default_label)
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
                        best_by_app[app_key] = (rank, pid, app_label, s.role, app_key, app_color)

                with self._app_activity_lock:
                    cutoff = now - (self.INACTIVE_RETENTION_SECONDS * 10)
                    self._app_last_active = {k: t for k, t in self._app_last_active.items() if t >= cutoff}

                for _, pid, app_label, role, app_key, app_color in sorted(best_by_app.values(), key=lambda v: v[2].lower()):
                    channel_apps[role].append((pid, app_label, app_key, app_color))
                    pid_label[pid] = app_label
                with self._level_lock:
                    self._channel_level_pids = {
                        role: [int(item[0]) for item in apps if str(item[0]).isdigit()]
                        for role, apps in channel_apps.items()
                    }
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
        stream_to_channels: dict[str, list[str]] = {}
        for key in self.SWITCHABLE_CHANNELS:
            selection = selections.get(key)
            if not selection:
                continue
            stream_to_channels.setdefault(selection.stream_id, []).append(key)

        for key, selection in selections.items():
            if selection is None:
                self._window.set_device_choices(key, [], None)
                continue
            options = [(opt.id, opt.name) for opt in selection.options]
            linked = stream_to_channels.get(selection.stream_id, [])
            reason: str | None = None
            if len(linked) > 1:
                reason = f"Source linked in Sonar ({selection.stream_id}); channels move together."
            self._window.set_device_choices(
                key,
                options,
                selection.current_device_id,
                editable=True,
                disabled_reason=reason,
                linked=len(linked) > 1,
            )

        shared_channels = [key for key in ("game", "chatRender", "media") if selections.get(key) is not None]
        shared_stream_ids = {selections[key].stream_id for key in shared_channels if selections.get(key) is not None}
        if len(shared_channels) == 3 and len(shared_stream_ids) == 1:
            base = selections.get("game")
            if base is not None:
                self._window.set_shared_device_choices(
                    options=[(opt.id, opt.name) for opt in base.options],
                    current_device_id=base.current_device_id,
                    channel_key="game",
                )
                return
        self._window.set_shared_device_choices([], None, channel_key="game")

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

    def show_settings(self) -> None:
        self._window.dispatch(lambda: self._settings.set_states(is_startup_enabled(), self._compact_mode, self._show_logs, self._cyber_mode))
        self._window.dispatch(self._settings.show_window)

    def toggle_startup_with_windows(self, enabled: bool) -> None:
        def work() -> None:
            try:
                set_startup_enabled(enabled)
                actual = is_startup_enabled()
                self._window.dispatch(lambda: self._tray.set_startup_checked(actual))
                self._window.dispatch(lambda: self._settings.set_states(actual, self._compact_mode, self._show_logs, self._cyber_mode))
                state = "enabled" if actual else "disabled"
                self._window.dispatch(lambda: self._window.set_status(self._status(f"startup {state}")))
                self._notifier.show("Sonar", f"Start with Windows {state}")
            except Exception as exc:
                msg = f"Startup toggle error: {exc}"
                self._window.dispatch(lambda m=msg: self._window.set_status(self._status(m)))
                self._window.dispatch(lambda: self._tray.set_startup_checked(is_startup_enabled()))
                self._window.dispatch(lambda: self._settings.set_states(is_startup_enabled(), self._compact_mode, self._show_logs, self._cyber_mode))

        threading.Thread(target=work, daemon=True).start()

    def customize_app(self, app_key: str, name: str | None, color: str | None) -> None:
        key = app_key.strip().lower()
        if not key:
            return
        overrides = dict(self._config.app_overrides or {})
        current = dict(overrides.get(key, {}))
        if name is None and color is None:
            overrides.pop(key, None)
        else:
            if name is not None:
                cleaned = " ".join(name.strip().split())
                if cleaned:
                    current["name"] = cleaned
                else:
                    current.pop("name", None)
            if color is not None:
                cleaned_color = color.strip()
                if cleaned_color:
                    current["color"] = cleaned_color
                else:
                    current.pop("color", None)
            if current:
                overrides[key] = current
            else:
                overrides.pop(key, None)
        self._config.app_overrides = overrides
        save_config(self._config)
        self.refresh_channels(show_toast=False)

    def _start_level_polling(self) -> None:
        if not self._levels.available:
            return

        def work() -> None:
            while self._alive:
                try:
                    levels = self._levels.read_levels()
                    by_pid = levels.by_pid or {}
                    with self._level_lock:
                        channel_pids = {k: list(v) for k, v in self._channel_level_pids.items()}
                    channel_levels = {
                        "master": levels.master,
                        "game": self._aggregate_pid_levels(channel_pids.get("game", []), by_pid),
                        "chatRender": self._aggregate_pid_levels(channel_pids.get("chatRender", []), by_pid),
                        "media": self._aggregate_pid_levels(channel_pids.get("media", []), by_pid),
                    }
                    self._window.dispatch(lambda lv=channel_levels: self._window.set_channel_levels(lv))
                except Exception:
                    pass
                threading.Event().wait(0.08)

        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _aggregate_pid_levels(pids: list[int], by_pid: dict[int, float]) -> float:
        if not pids:
            return 0.0
        return max((by_pid.get(pid, 0.0) for pid in pids), default=0.0)

    def toggle_logs_visibility(self, enabled: bool) -> None:
        self._show_logs = bool(enabled)
        self._window.dispatch(lambda: self._window.set_logs_visible(self._show_logs))
        self._tray.set_show_logs_checked(self._show_logs)
        self._settings.set_states(is_startup_enabled(), self._compact_mode, self._show_logs, self._cyber_mode)

    def toggle_compact_mode(self, enabled: bool) -> None:
        self._compact_mode = bool(enabled)
        self._window.dispatch(lambda: self._window.set_compact(self._compact_mode))
        self._tray.set_compact_checked(self._compact_mode)
        self._settings.set_states(is_startup_enabled(), self._compact_mode, self._show_logs, self._cyber_mode)
        self._config.compact_mode = self._compact_mode
        save_config(self._config)

    def toggle_cyber_mode(self, enabled: bool) -> None:
        self._cyber_mode = bool(enabled)
        self._window.dispatch(lambda: self._window.set_cyber_mode(self._cyber_mode))
        self._tray.set_cyber_checked(self._cyber_mode)
        self._config.cyber_mode = self._cyber_mode
        save_config(self._config)

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
            self._settings.close()
            self._qapp.quit()

        self._window.dispatch(do_exit)

    @staticmethod
    def _status(message: str) -> str:
        now = datetime.now().strftime("%H:%M:%S")
        return f"[{now}] {message}"

    @staticmethod
    def _log_channel_apps(channel_apps: dict[str, list[tuple[str, ...]]]) -> None:
        def labels(role: str) -> str:
            items = [item[1] for item in channel_apps.get(role, []) if len(item) > 1]
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

    @staticmethod
    def _app_identity(process_name: str, display_name: str, process_id: int) -> str:
        raw = (process_name or display_name).strip()
        if raw:
            return raw.lower()
        return f"pid:{process_id}"

    def _apply_app_override(self, app_key: str, default_label: str) -> tuple[str, str]:
        overrides = self._config.app_overrides or {}
        override = overrides.get(app_key, {})
        name = override.get("name") if isinstance(override, dict) else None
        color = override.get("color") if isinstance(override, dict) else None
        label = name.strip() if isinstance(name, str) and name.strip() else default_label
        chip_color = color.strip() if isinstance(color, str) and color.strip() else ""
        return label, chip_color
