from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import sys
from time import monotonic

from PySide6.QtCore import QObject, QRect, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayController(QObject):
    def __init__(
        self,
        on_toggle: Callable[[], None],
        on_refresh: Callable[[], None],
        on_settings: Callable[[], None],
        on_toggle_compact: Callable[[bool], None],
        compact_mode: bool,
        on_toggle_logs: Callable[[bool], None],
        show_logs: bool,
        on_toggle_startup: Callable[[bool], None],
        startup_enabled: bool,
        on_exit: Callable[[], None],
        on_toggle_cyber: Callable[[bool], None] | None = None,
        cyber_mode: bool = False,
    ) -> None:
        super().__init__()
        self._on_toggle = on_toggle
        self._on_refresh = on_refresh
        self._on_settings = on_settings
        self._on_toggle_compact = on_toggle_compact
        self._on_toggle_logs = on_toggle_logs
        self._on_toggle_startup = on_toggle_startup
        self._on_toggle_cyber = on_toggle_cyber
        self._on_exit = on_exit

        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(self._build_icon())
        self._tray.setToolTip("Sonar Mixer")
        self._tray.activated.connect(self._on_activated)
        self._last_trigger_at = 0.0

        menu = QMenu()
        menu.setObjectName("trayMenu")
        menu.setStyleSheet(
            """
            QMenu#trayMenu {
                background-color: rgb(18, 22, 32);
                border: 1px solid rgba(255, 255, 255, 24);
                border-radius: 10px;
                padding: 6px;
                color: #eef2f8;
            }
            QMenu#trayMenu::item {
                min-height: 26px;
                padding: 5px 28px 5px 28px;
                border-radius: 5px;
            }
            QMenu#trayMenu::item:selected {
                background-color: rgba(255, 255, 255, 20);
            }
            QMenu#trayMenu::item:checked {
                color: #ff6f86;
            }
            QMenu#trayMenu::separator {
                height: 1px;
                background: rgba(255, 255, 255, 14);
                margin: 5px 8px;
            }
            """
        )
        title_action = QAction(self._build_icon(), "Sonar Mixer", menu)
        title_action.setEnabled(False)
        menu.addAction(title_action)
        connected_action = QAction(self._action_icon("#48efaa"), "Connected", menu)
        connected_action.setEnabled(False)
        menu.addAction(connected_action)
        menu.addSeparator()

        open_action = QAction(self._action_icon("#ff6f86"), "Open mixer", menu)
        open_action.triggered.connect(self._on_toggle)
        menu.addAction(open_action)

        refresh_action = QAction(self._action_icon("#4cc2ff"), "Refresh devices", menu)
        refresh_action.triggered.connect(self._on_refresh)
        menu.addAction(refresh_action)

        menu.addSeparator()

        self._startup_action = QAction(self._action_icon("#48efaa"), "Start with Windows", menu)
        self._startup_action.setCheckable(True)
        self._startup_action.setChecked(startup_enabled)
        self._startup_action.toggled.connect(self._on_toggle_startup)
        menu.addAction(self._startup_action)

        self._compact_action = QAction(self._action_icon("#ffb24a"), "Compact view", menu)
        self._compact_action.setCheckable(True)
        self._compact_action.setChecked(compact_mode)
        self._compact_action.toggled.connect(self._on_toggle_compact)
        menu.addAction(self._compact_action)

        self._show_logs_action = QAction(self._action_icon("#b48cff"), "Show status line", menu)
        self._show_logs_action.setCheckable(True)
        self._show_logs_action.setChecked(show_logs)
        self._show_logs_action.toggled.connect(self._on_toggle_logs)
        menu.addAction(self._show_logs_action)

        self._cyber_action = QAction(self._action_icon("#00f0ff"), "Cyber theme", menu)
        self._cyber_action.setCheckable(True)
        self._cyber_action.setChecked(cyber_mode)
        if on_toggle_cyber:
            self._cyber_action.toggled.connect(on_toggle_cyber)
        menu.addAction(self._cyber_action)

        menu.addSeparator()

        settings_action = QAction(self._action_icon("#eef2f8"), "Settings...", menu)
        settings_action.triggered.connect(self._on_settings)
        menu.addAction(settings_action)

        quit_action = QAction(self._action_icon("#9aa4b2"), "Quit", menu)
        quit_action.triggered.connect(self._on_exit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)

    def start(self) -> None:
        self._tray.show()

    def stop(self) -> None:
        self._tray.hide()

    def geometry(self) -> QRect:
        return self._tray.geometry()

    def set_startup_checked(self, enabled: bool) -> None:
        self._startup_action.blockSignals(True)
        self._startup_action.setChecked(enabled)
        self._startup_action.blockSignals(False)

    def set_show_logs_checked(self, enabled: bool) -> None:
        self._show_logs_action.blockSignals(True)
        self._show_logs_action.setChecked(enabled)
        self._show_logs_action.blockSignals(False)

    def set_compact_checked(self, enabled: bool) -> None:
        self._compact_action.blockSignals(True)
        self._compact_action.setChecked(enabled)
        self._compact_action.blockSignals(False)

    def set_cyber_checked(self, enabled: bool) -> None:
        self._cyber_action.blockSignals(True)
        self._cyber_action.setChecked(enabled)
        self._cyber_action.blockSignals(False)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._last_trigger_at = monotonic()
            self._on_refresh()
            self._on_toggle()
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            # Let Qt show context menu.
            return
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # Some platforms emit Trigger then DoubleClick for a double tap.
            # Ignore the second signal so the flyout does not toggle twice.
            if monotonic() - self._last_trigger_at < 0.35:
                return
            self._on_refresh()
            self._on_toggle()

    @staticmethod
    def _build_icon() -> QIcon:
        for asset in TrayController._asset_candidates():
            tinted = TrayController._tinted_icon(asset, QColor("#e8eef7"), 32)
            if not tinted.isNull():
                return tinted

        size = 32
        px = QPixmap(size, size)
        px.fill(Qt.GlobalColor.transparent)

        painter = QPainter(px)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#2a2f3a"))
            painter.drawRoundedRect(2, 2, 28, 28, 7, 7)

            painter.setBrush(QColor("#ffd400"))
            painter.drawRoundedRect(7, 9, 18, 3, 1, 1)
            painter.drawRoundedRect(7, 15, 14, 3, 1, 1)
            painter.drawRoundedRect(7, 21, 10, 3, 1, 1)
        finally:
            painter.end()

        return QIcon(px)

    @staticmethod
    def _asset_candidates() -> list[Path]:
        candidates: list[Path] = []
        local_assets = Path(__file__).resolve().parent / "assets"
        candidates.append(local_assets / "tray-icon.svg")
        candidates.append(local_assets / "tray-icon.png")
        candidates.append(local_assets / "app-icon.svg")
        candidates.append(local_assets / "app-icon.png")

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bundled_assets = Path(str(meipass)) / "sonar_control" / "assets"
            candidates.append(bundled_assets / "tray-icon.svg")
            candidates.append(bundled_assets / "tray-icon.png")
            candidates.append(bundled_assets / "app-icon.svg")
            candidates.append(bundled_assets / "app-icon.png")
        return candidates

    @staticmethod
    def _tinted_icon(path: Path, color: QColor, size: int) -> QIcon:
        if not path.exists():
            return QIcon()

        base_icon = QIcon(str(path))
        if base_icon.isNull():
            return QIcon()

        base = base_icon.pixmap(size, size)
        if base.isNull():
            return QIcon()

        out = QPixmap(base.size())
        out.fill(Qt.GlobalColor.transparent)
        painter = QPainter(out)
        try:
            painter.drawPixmap(0, 0, base)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(out.rect(), color)
        finally:
            painter.end()
        return QIcon(out)

    @staticmethod
    def _action_icon(color: str) -> QIcon:
        size = 16
        px = QPixmap(size, size)
        px.fill(Qt.GlobalColor.transparent)
        painter = QPainter(px)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            c = QColor(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(c)
            painter.drawRoundedRect(3, 3, 10, 10, 3, 3)
        finally:
            painter.end()
        return QIcon(px)

