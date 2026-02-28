from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QRect, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayController(QObject):
    def __init__(
        self,
        on_toggle: Callable[[], None],
        on_refresh: Callable[[], None],
        on_toggle_startup: Callable[[bool], None],
        startup_enabled: bool,
        on_exit: Callable[[], None],
    ) -> None:
        super().__init__()
        self._on_toggle = on_toggle
        self._on_refresh = on_refresh
        self._on_toggle_startup = on_toggle_startup
        self._on_exit = on_exit

        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(self._build_icon())
        self._tray.setToolTip("Sonar Mixer")
        self._tray.activated.connect(self._on_activated)

        menu = QMenu()
        refresh_action = QAction("Refresh", menu)
        refresh_action.triggered.connect(self._on_refresh)
        menu.addAction(refresh_action)

        self._startup_action = QAction("Start with Windows", menu)
        self._startup_action.setCheckable(True)
        self._startup_action.setChecked(startup_enabled)
        self._startup_action.toggled.connect(self._on_toggle_startup)
        menu.addAction(self._startup_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
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

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._on_refresh()
            self._on_toggle()
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            # Let Qt show context menu.
            return
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
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
        candidates.append(local_assets / "app-icon.svg")
        candidates.append(local_assets / "app-icon.png")

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bundled_assets = Path(str(meipass)) / "sonar_control" / "assets"
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

