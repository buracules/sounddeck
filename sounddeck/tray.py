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
        self._tray.setToolTip("SoundDeck")
        self._tray.activated.connect(self._on_activated)
        self._last_trigger_at = 0.0

        menu = QMenu()
        menu.setObjectName("trayMenu")
        menu.setStyleSheet(
            """
            QMenu#trayMenu {
                background-color: rgb(10, 14, 26);
                border: 1px solid rgba(0, 240, 255, 120);
                border-radius: 4px;
                padding: 6px;
                color: #dffaff;
                font-family: "Rajdhani", "Cascadia Code", "Consolas", monospace;
            }
            QMenu#trayMenu::item {
                min-height: 26px;
                padding: 6px 26px 6px 26px;
                border-radius: 2px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }
            QMenu#trayMenu::item:selected {
                background-color: rgba(0, 240, 255, 32);
                color: #00f0ff;
            }
            QMenu#trayMenu::separator {
                height: 1px;
                background: rgba(0, 240, 255, 45);
                margin: 5px 8px;
            }
            """
        )

        open_action = QAction(self._action_icon("#00f0ff"), "Open mixer", menu)
        open_action.triggered.connect(self._on_toggle)
        menu.addAction(open_action)

        refresh_action = QAction(self._action_icon("#00f0ff"), "Refresh devices", menu)
        refresh_action.triggered.connect(self._on_refresh)
        menu.addAction(refresh_action)

        menu.addSeparator()

        settings_action = QAction(self._action_icon("#dffaff"), "Settings", menu)
        settings_action.triggered.connect(self._on_settings)
        menu.addAction(settings_action)

        quit_action = QAction(self._action_icon("#ff2d8a"), "Quit", menu)
        quit_action.triggered.connect(self._on_exit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)

    def start(self) -> None:
        self._tray.show()

    def stop(self) -> None:
        self._tray.hide()

    def geometry(self) -> QRect:
        return self._tray.geometry()

    # Toggle state now lives in the Settings window; these remain as no-ops so
    # the application can call them unconditionally.
    def set_startup_checked(self, enabled: bool) -> None:
        return

    def set_show_logs_checked(self, enabled: bool) -> None:
        return

    def set_compact_checked(self, enabled: bool) -> None:
        return

    def set_cyber_checked(self, enabled: bool) -> None:
        return

    def set_battery(self, percent: int | None, charging: bool, device_name: str = "") -> None:
        if percent is None:
            self._tray.setToolTip("SoundDeck")
            self._tray.setIcon(self._build_icon())
            return
        suffix = " — charging" if charging else ""
        name_line = f"{device_name}\n" if device_name else ""
        self._tray.setToolTip(f"SoundDeck\n{name_line}Battery: {percent}%{suffix}")
        self._tray.setIcon(self._build_battery_icon(percent, charging))

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
    def _build_battery_icon(percent: int, charging: bool) -> QIcon:
        base = TrayController._build_icon().pixmap(32, 32)
        out = QPixmap(32, 32)
        out.fill(Qt.GlobalColor.transparent)
        painter = QPainter(out)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            painter.drawPixmap(0, 0, base)

            # Battery badge — bottom-right, medium size
            bx, by, bw, bh = 14, 22, 16, 9
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(10, 13, 20, 220))
            painter.drawRoundedRect(bx - 2, by - 2, bw + 6, bh + 4, 3, 3)

            # Battery body
            painter.setBrush(QColor(38, 46, 60))
            painter.drawRoundedRect(bx, by, bw, bh, 2, 2)
            # Terminal nub (right side)
            painter.drawRoundedRect(bx + bw, by + 3, 2, bh - 6, 1, 1)

            if charging:
                fill_color = QColor("#4cc2ff")
            elif percent <= 20:
                fill_color = QColor("#ff6f86")
            elif percent <= 50:
                fill_color = QColor("#ffb24a")
            else:
                fill_color = QColor("#48efaa")

            fill_w = max(1, int((bw - 2) * percent / 100))
            painter.setBrush(fill_color)
            painter.drawRoundedRect(bx + 1, by + 1, fill_w, bh - 2, 1, 1)

            # Coloured terminal nub
            painter.drawRoundedRect(bx + bw, by + 3, 2, bh - 6, 1, 1)
        finally:
            painter.end()
        return QIcon(out)

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
            bundled_assets = Path(str(meipass)) / "sounddeck" / "assets"
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

