from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import sys
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QEvent, QFileInfo, QMimeData, QObject, QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QDrag, QFont, QFontMetrics, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QIcon, QTransform
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileIconProvider,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSlider,
    QStackedWidget,
    QScrollArea,
    QStyledItemDelegate,
    QStyle,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from . import __version__
from .models import ChannelState


class Theme:
    BG = "#111318"
    SURFACE = "#1b1f26"
    CARD = "#222833"
    BORDER = "#3b4451"
    TEXT = "#eff3fa"
    TEXT_MUTED = "#aeb7c3"
    ACCENT = "#ff6f86"
    TRACK = "#343d4b"
    TRACK_HOVER = "#404b5a"
    PANEL_ALPHA = 92

    OUTER_PAD = 18
    CONTENT_MAX_WIDTH = 1260
    GAP_8 = 8
    GAP_16 = 16
    GAP_24 = 20

    @classmethod
    def refresh_from_system(cls) -> None:
        # Keep fixed accent for screenshot-matched look.
        _ = cls
        return


class CyberTheme:
    PINK = "#ff2d8a"
    CYAN = "#00f0ff"
    YELLOW = "#fff033"
    BG = "#070912"
    PANEL_BG = "#0a0e1a"
    TEXT = "#dffaff"
    TEXT_DIM = "rgba(223,250,255,0.55)"
    MONO = '"Rajdhani", "Cascadia Code", "Consolas", "Courier New", monospace'

    @staticmethod
    def chamfer_path(w: int, h: int, c: int = 10) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(c, 0)
        path.lineTo(w, 0)
        path.lineTo(w, h - c)
        path.lineTo(w - c, h)
        path.lineTo(0, h)
        path.lineTo(0, c)
        path.closeSubpath()
        return path

    @staticmethod
    def chamfer_all_path(w: int, h: int, c: int = 3) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(c, 0)
        path.lineTo(w - c, 0)
        path.lineTo(w, c)
        path.lineTo(w, h - c)
        path.lineTo(w - c, h)
        path.lineTo(c, h)
        path.lineTo(0, h - c)
        path.lineTo(0, c)
        path.closeSubpath()
        return path


class _MixerPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("flyoutPanel")
        self._cyber = False

    def set_cyber(self, cyber: bool) -> None:
        self._cyber = bool(cyber)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if not self._cyber:
            super().paintEvent(event)
            return
        w, h = self.width(), self.height()
        cut = 12
        outer = CyberTheme.chamfer_path(w, h, cut)
        inner = QTransform().translate(1.5, 1.5).map(CyberTheme.chamfer_path(w - 3, h - 3, cut - 1))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        try:
            grad = QLinearGradient(0, 0, w, h)
            grad.setColorAt(0.0, QColor(CyberTheme.CYAN))
            grad.setColorAt(1.0, QColor(CyberTheme.PINK))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawPath(outer)
            painter.setBrush(QColor(CyberTheme.BG))
            painter.drawPath(inner)
            # scanlines
            scan = QColor(0, 240, 255, 7)
            for y in range(2, h, 3):
                painter.fillRect(QRectF(1.5, y, w - 3, 1), scan)
            # grid dots
            grid = QColor(0, 240, 255, 18)
            for gy in range(12, h - 2, 24):
                for gx in range(12, w - 2, 24):
                    painter.fillRect(QRectF(gx, gy, 1, 1), grid)
        finally:
            painter.end()


class _CyberHudTop(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("cyberHudTop")
        self.setFixedHeight(20)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(6)
        self._dot = QLabel("●")
        self._dot.setObjectName("cyberHudDot")
        layout.addWidget(self._dot)
        rec = QLabel("REC")
        rec.setObjectName("cyberHudRec")
        layout.addWidget(rec)
        title = QLabel("SONAR//MIX_v1")
        title.setObjectName("cyberHudTitle")
        layout.addWidget(title)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("cyberHudSep")
        layout.addWidget(sep, 1)
        sys_ok = QLabel("SYS_OK")
        sys_ok.setObjectName("cyberHudSysOk")
        layout.addWidget(sys_ok)
        bars = QLabel("▮▮▮")
        bars.setObjectName("cyberHudBars")
        layout.addWidget(bars)
        self._blink_on = True
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(560)
        self._blink_timer.timeout.connect(self._tick_blink)
        self._blink_timer.start()

    def _tick_blink(self) -> None:
        self._blink_on = not self._blink_on
        self._dot.setStyleSheet(
            "color: #ff2d8a;" if self._blink_on else "color: rgba(255, 45, 138, 55);"
        )


class _CyberHudBottom(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("cyberHudBottom")
        self.setFixedHeight(18)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(5)
        uplink = QLabel("UPLINK: 127.0.0.1")
        uplink.setObjectName("cyberHudInfo")
        layout.addWidget(uplink)
        for _ in range(2):
            d = QLabel("·")
            d.setObjectName("cyberHudDim")
            layout.addWidget(d)
            info = QLabel("LAT: --ms" if _ == 0 else "CH: 04")
            info.setObjectName("cyberHudInfo")
            layout.addWidget(info)
        layout.addStretch(1)
        diamonds = QLabel("◆  ◆  ◆")
        diamonds.setObjectName("cyberDiamonds")
        layout.addWidget(diamonds)


class _UiDispatcher(QObject):
    invoke = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.invoke.connect(self._run)

    def _run(self, callback: object) -> None:
        if callable(callback):
            callback()


class _AccentPolicy(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class _WindowCompositionAttribData(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


def _hide_from_taskbar(hwnd: int) -> None:
    try:
        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex_style = (ex_style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
    except Exception:
        pass


def _enable_windows_blur(hwnd: int) -> None:
    # Best-effort native blur; safely no-op on unsupported environments.
    try:
        user32 = ctypes.windll.user32
        policy = _AccentPolicy()
        policy.AccentState = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND
        policy.AccentFlags = 2
        policy.GradientColor = 0x401E1F22
        data = _WindowCompositionAttribData()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.cast(ctypes.pointer(policy), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(policy)
        user32.SetWindowCompositionAttribute(wintypes.HWND(hwnd), ctypes.byref(data))
    except Exception:
        return
    # Clip blur to rounded corners (Win11+, safely no-ops on older Windows)
    try:
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = ctypes.c_int(2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(DWMWCP_ROUND),
            ctypes.sizeof(DWMWCP_ROUND),
        )
    except Exception:
        return


class ChipListWidget(QListWidget):
    COLOR_PRESETS = (
        ("Rose", "#ff6f86"),
        ("Mint", "#48efaa"),
        ("Sky", "#4cc2ff"),
        ("Amber", "#ffb24a"),
        ("Violet", "#b48cff"),
        ("Gold", "#f0d35a"),
    )

    def __init__(
        self,
        channel_key: str,
        on_route_app: Callable[[str, str], None],
        on_customize_app: Callable[[str, str | None, str | None], None] | None = None,
    ) -> None:
        super().__init__()
        self._channel_key = channel_key
        self._on_route_app = on_route_app
        self._on_customize_app = on_customize_app
        self.setObjectName("channelChipList")
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setSpacing(3)
        self.setUniformItemSizes(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_chip_menu)
        self._delegate = AppChipDelegate(self)
        self.setItemDelegate(self._delegate)
        self._is_cyber = False

    def set_cyber(self, cyber: bool) -> None:
        self._is_cyber = bool(cyber)
        self._delegate.set_cyber(cyber)
        self._reflow_chip_widths()
        self.viewport().update()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self.itemAt(event.position().toPoint())
            if hit is not None:
                self.setCurrentItem(hit)
        super().mousePressEvent(event)

    def set_apps(self, apps: list[tuple[str, ...]]) -> None:
        self.clear()
        if not apps:
            item = QListWidgetItem("No apps routed")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled & ~Qt.ItemFlag.ItemIsSelectable)
            item.setData(Qt.ItemDataRole.UserRole, "")
            item.setData(Qt.ItemDataRole.UserRole + 3, True)
            item.setSizeHint(self._chip_size_hint("No apps routed"))
            self.addItem(item)
            self._reflow_chip_widths()
            return

        for app in apps:
            process_id = str(app[0]) if len(app) > 0 else ""
            label = str(app[1]) if len(app) > 1 else process_id
            app_key = str(app[2]) if len(app) > 2 else label.lower()
            custom_color = str(app[3]) if len(app) > 3 else ""
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, process_id)
            item.setData(Qt.ItemDataRole.UserRole + 4, app_key)
            item.setData(Qt.ItemDataRole.UserRole + 5, custom_color)
            bg, border = self._chip_colors(label, custom_color)
            item.setData(Qt.ItemDataRole.UserRole + 1, bg)
            item.setData(Qt.ItemDataRole.UserRole + 2, border)
            item.setSizeHint(self._chip_size_hint(label))
            self.addItem(item)
        self._reflow_chip_widths()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._reflow_chip_widths()

    def startDrag(self, supported_actions: Qt.DropActions) -> None:
        item = self.currentItem()
        if not item:
            return
        process_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not process_id:
            return
        mime = QMimeData()
        mime.setText(f"pid:{process_id}")
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().text().strip().startswith("pid:"):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().text().strip().startswith("pid:"):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        text = event.mimeData().text().strip()
        if not text.startswith("pid:"):
            event.ignore()
            return
        process_id = text.split(":", 1)[1].strip()
        if process_id:
            self._on_route_app(process_id, self._channel_key)
            event.acceptProposedAction()
            return
        event.ignore()

    def _show_chip_menu(self, pos: QPoint) -> None:
        if self._on_customize_app is None:
            return
        item = self.itemAt(pos)
        if item is None or bool(item.data(Qt.ItemDataRole.UserRole + 3)):
            return
        app_key = str(item.data(Qt.ItemDataRole.UserRole + 4) or "").strip()
        if not app_key:
            return

        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        color_menu = menu.addMenu("Color")
        color_actions = []
        for name, color in self.COLOR_PRESETS:
            action = color_menu.addAction(self._color_icon(color), name)
            action.setData(color)
            color_actions.append(action)
        custom_color_action = color_menu.addAction("Custom...")
        reset_color_action = color_menu.addAction("Reset color")
        reset_action = menu.addAction("Reset name and color")

        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == rename_action:
            current_name = item.text()
            value, ok = self._prompt_text("Rename app", "Name", current_name)
            if ok:
                self._on_customize_app(app_key, value, None)
            return
        if chosen == custom_color_action:
            current = str(item.data(Qt.ItemDataRole.UserRole + 5) or Theme.ACCENT)
            value, ok = self._prompt_text("Chip color", "Hex color", current)
            if ok:
                color = QColor(value.strip())
                if color.isValid():
                    self._on_customize_app(app_key, None, color.name())
            return
        if chosen == reset_color_action:
            self._on_customize_app(app_key, None, "")
            return
        if chosen == reset_action:
            self._on_customize_app(app_key, None, None)
            return
        if chosen in color_actions:
            self._on_customize_app(app_key, None, str(chosen.data()))

    def _prompt_text(self, title: str, label: str, value: str) -> tuple[str, bool]:
        dialog = QDialog(self.window())
        dialog.setWindowTitle(title)
        dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        dialog.setModal(True)

        shell = QFrame(dialog)
        shell.setObjectName("chipEditor")
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("chipEditorTitle")
        layout.addWidget(title_label)

        input_label = QLabel(label)
        input_label.setObjectName("chipEditorLabel")
        layout.addWidget(input_label)

        edit = QLineEdit(value)
        edit.setObjectName("chipEditorInput")
        edit.selectAll()
        layout.addWidget(edit)

        buttons = QWidget()
        row = QHBoxLayout(buttons)
        row.setContentsMargins(0, 4, 0, 0)
        row.setSpacing(6)
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("chipEditorButton")
        ok = QPushButton("Save")
        ok.setObjectName("chipEditorPrimary")
        row.addWidget(cancel)
        row.addWidget(ok)
        layout.addWidget(buttons)

        root = QVBoxLayout(dialog)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(shell)
        dialog.setStyleSheet(
            f"""
            QFrame#chipEditor {{
                background-color: #141820;
                border: 1px solid rgba(255, 255, 255, 28);
                border-radius: 10px;
            }}
            QLabel#chipEditorTitle {{
                color: {Theme.TEXT};
                font-size: 13px;
                font-weight: 600;
            }}
            QLabel#chipEditorLabel {{
                color: {Theme.TEXT_MUTED};
                font-size: 10px;
            }}
            QLineEdit#chipEditorInput {{
                background-color: rgba(255, 255, 255, 12);
                border: 1px solid rgba(255, 255, 255, 26);
                border-radius: 6px;
                color: {Theme.TEXT};
                min-height: 28px;
                padding: 0 8px;
                selection-background-color: {Theme.ACCENT};
                selection-color: #111318;
            }}
            QPushButton#chipEditorButton,
            QPushButton#chipEditorPrimary {{
                border-radius: 6px;
                min-height: 26px;
                padding: 0 12px;
                font-weight: 600;
            }}
            QPushButton#chipEditorButton {{
                background-color: rgba(255, 255, 255, 10);
                border: 1px solid rgba(255, 255, 255, 18);
                color: {Theme.TEXT_MUTED};
            }}
            QPushButton#chipEditorPrimary {{
                background-color: {Theme.ACCENT};
                border: 1px solid {Theme.ACCENT};
                color: #111318;
            }}
            """
        )

        result: dict[str, object] = {"ok": False}
        ok.clicked.connect(lambda: (result.__setitem__("ok", True), dialog.accept()))
        cancel.clicked.connect(dialog.reject)
        edit.returnPressed.connect(lambda: (result.__setitem__("ok", True), dialog.accept()))

        dialog.setFixedSize(280, 156)
        parent_rect = self.window().frameGeometry() if self.window() is not None else self.frameGeometry()
        dialog.move(parent_rect.center() - QPoint(dialog.width() // 2, dialog.height() // 2))
        accepted = dialog.exec() == QDialog.DialogCode.Accepted and bool(result["ok"])
        return edit.text(), accepted

    @staticmethod
    def _color_icon(color: str) -> QIcon:
        px = QPixmap(16, 16)
        px.fill(Qt.GlobalColor.transparent)
        painter = QPainter(px)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(2, 2, 12, 12), 3, 3)
        finally:
            painter.end()
        return QIcon(px)

    def _chip_size_hint(self, label: str) -> QSize:
        if self._is_cyber:
            for fname in ("Rajdhani", "Cascadia Code", "Consolas", "Courier New"):
                f = QFont(fname, 9)
                m = QFontMetrics(f)
                if m.averageCharWidth() > 3:
                    break
            text_w = m.horizontalAdvance(label.strip().upper())
            max_w = max(64, self.viewport().width() - 10)
            width = min(max_w, max(48, text_w + 16))
        else:
            m = QFontMetrics(QFont("Segoe UI", 9))
            text_w = m.horizontalAdvance(label.strip())
            max_w = max(56, self.viewport().width() - 10)
            width = min(max_w, max(34, text_w + 14))
        return QSize(width, 18)

    def _reflow_chip_widths(self) -> None:
        for i in range(self.count()):
            item = self.item(i)
            if item is None:
                continue
            item.setSizeHint(self._chip_size_hint(item.text()))

    @staticmethod
    def _chip_colors(label: str, custom_color: str = "") -> tuple[QColor, QColor]:
        if custom_color:
            color = QColor(custom_color)
            if color.isValid():
                bg = color.darker(170)
                bg.setAlpha(180)
                border = color.lighter(120)
                border.setAlpha(210)
                return bg, border
        # Deterministic muted color per app name.
        seed = 0
        for ch in label.lower():
            seed = (seed * 131 + ord(ch)) & 0xFFFFFFFF
        hue = seed % 360
        bg = QColor.fromHsv(hue, 48, 56)
        bg.setAlpha(150)
        border = QColor.fromHsv(hue, 58, 82)
        border.setAlpha(180)
        return bg, border


class AppChipDelegate(QStyledItemDelegate):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cyber = False

    def set_cyber(self, cyber: bool) -> None:
        self._cyber = bool(cyber)

    def paint(self, painter: QPainter, option, index) -> None:  # type: ignore[override]
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        is_empty = bool(index.data(Qt.ItemDataRole.UserRole + 3))
        if is_empty:
            painter.save()
            color = QColor(CyberTheme.CYAN) if self._cyber else QColor("#9aa4b2")
            color.setAlpha(100)
            painter.setPen(color)
            if self._cyber:
                font = painter.font()
                font.setFamily("Cascadia Code, Consolas, Courier New")
                font.setPointSize(7)
                painter.setFont(font)
            painter.drawText(option.rect.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignCenter, text)
            painter.restore()
            return

        if self._cyber:
            rect = option.rect.adjusted(1, 2, -1, -2)
            hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
            bg_color = QColor(0, 240, 255, 35 if hover else 15)
            border_color = QColor(CyberTheme.CYAN)
            border_color.setAlpha(160 if hover else 80)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            chip_path = CyberTheme.chamfer_all_path(rect.width(), rect.height(), 3)
            painter.translate(rect.topLeft())
            painter.setPen(QPen(border_color, 1))
            painter.setBrush(bg_color)
            painter.drawPath(chip_path)

            text_rect = QRect(5, 0, rect.width() - 10, rect.height())
            font = painter.font()
            font.setFamily("Rajdhani")
            font.setPointSize(9)
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            tc = QColor(CyberTheme.CYAN)
            tc.setAlpha(220 if hover else 180)
            painter.setPen(tc)
            upper = text.upper()
            elided = painter.fontMetrics().elidedText(upper, Qt.TextElideMode.ElideRight, text_rect.width())
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)
            painter.restore()
            return

        bg = index.data(Qt.ItemDataRole.UserRole + 1)
        border = index.data(Qt.ItemDataRole.UserRole + 2)
        bg_color = bg if isinstance(bg, QColor) else QColor("#212b37")
        border_color = border if isinstance(border, QColor) else QColor("#2a3442")

        rect = option.rect.adjusted(1, 2, -1, -2)
        radius = 5
        if option.state & QStyle.StateFlag.State_MouseOver:
            bg_color = bg_color.lighter(110)
            border_color = border_color.lighter(120)
        if option.state & QStyle.StateFlag.State_Selected:
            border_color = border_color.lighter(130)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(bg_color)
        painter.drawRoundedRect(rect, radius, radius)

        text_rect = rect.adjusted(6, 0, -6, 0)
        painter.setPen(QColor("#e8eef7"))
        elided = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)
        painter.restore()


class ChipContainer(QFrame):
    def __init__(
        self,
        channel_key: str,
        on_route_app: Callable[[str, str], None],
        on_customize_app: Callable[[str, str | None, str | None], None] | None = None,
        height: int = 110,
    ) -> None:
        super().__init__()
        self._channel_key = channel_key
        self._on_route_app = on_route_app
        self._apps: list[tuple[str, ...]] = []
        self.setObjectName("chipContainer")
        self.setAcceptDrops(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 4)
        root.setSpacing(0)

        self._chips = ChipListWidget(channel_key, on_route_app, on_customize_app)
        self._chips.setMinimumHeight(height)
        self._chips.setMaximumHeight(height)
        root.addWidget(self._chips)

    def set_apps(self, apps: list[tuple[str, ...]]) -> None:
        self._apps = list(apps)
        self._chips.set_apps(self._apps)

    def set_cyber(self, cyber: bool) -> None:
        self._chips.set_cyber(cyber)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().text().strip().startswith("pid:"):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().text().strip().startswith("pid:"):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        text = event.mimeData().text().strip()
        if not text.startswith("pid:"):
            event.ignore()
            return
        process_id = text.split(":", 1)[1].strip()
        if process_id:
            self._on_route_app(process_id, self._channel_key)
            event.acceptProposedAction()
            return
        event.ignore()


class ConsoleSlider(QSlider):
    def __init__(self) -> None:
        super().__init__(Qt.Orientation.Horizontal)
        self.setObjectName("consoleSlider")
        self.setRange(0, 100)
        self.setSingleStep(1)
        self.setPageStep(5)
        self.setFixedHeight(18)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setProperty("hovered", False)
        self.setProperty("active", False)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._set_state("hovered", True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._set_state("hovered", False)
        self._set_state("active", False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self._set_state("active", True)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._set_state("active", False)
        super().mouseReleaseEvent(event)

    def _set_state(self, key: str, value: bool) -> None:
        if self.property(key) == value:
            return
        self.setProperty(key, value)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class ConsoleMuteSwitch(QPushButton):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("consoleMuteSwitch")
        self.setAccessibleName("Mute toggle")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(38, 24)
        self.setText("")
        self._cyber = False

    def set_cyber(self, cyber: bool) -> None:
        self._cyber = bool(cyber)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        _ = event
        muted = self.isChecked()
        if self._cyber:
            accent = QColor(CyberTheme.CYAN)
            track = QColor(0, 240, 255, 28) if not muted else QColor(255, 255, 255, 18)
            border = QColor(0, 240, 255, 130) if not muted else QColor(255, 255, 255, 34)
            knob = accent if not muted else QColor("#1a1f2e")
        else:
            accent = QColor(Theme.ACCENT)
            track = QColor(255, 111, 134, 34) if not muted else QColor(255, 255, 255, 18)
            border = QColor(255, 111, 134, 150) if not muted else QColor(255, 255, 255, 34)
            knob = accent if not muted else QColor("#3a3f4d")

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
            painter.setPen(QPen(border, 1))
            painter.setBrush(track)
            painter.drawRoundedRect(rect, 12, 12)

            diameter = 16
            x = 4 if muted else self.width() - diameter - 4
            y = (self.height() - diameter) / 2
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(knob)
            painter.drawEllipse(QRectF(x, y, diameter, diameter))
        finally:
            painter.end()


class VUMeter(QWidget):
    def __init__(self, bars: int = 18, master: bool = False) -> None:
        super().__init__()
        self._bars = bars
        self._level = 0
        self._display_level = 0
        self._muted = False
        self._master = master
        self._cyber = False
        self.setFixedHeight(6 if master else 5)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_meter(self, level: int, muted: bool = False) -> None:
        _ = level
        self._muted = bool(muted)
        self._level = 0
        self._display_level = 0
        self.update()

    def set_peak(self, level: float, muted: bool = False) -> None:
        self._muted = bool(muted)
        self._level = max(0, min(100, int(round(float(level) * 100))))
        self._display_level = 0 if self._muted else self._level
        self.update()

    def set_bars(self, bars: int) -> None:
        self._bars = max(8, int(bars))
        self.update()

    def set_cyber(self, cyber: bool) -> None:
        self._cyber = bool(cyber)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            gap = 2
            if self._bars <= 0:
                return
            bar_w = max(1.0, (self.width() - gap * (self._bars - 1)) / self._bars)
            filled = round((0 if self._muted else self._display_level) / 100 * self._bars)
            for i in range(self._bars):
                on = i < filled
                hot = i >= self._bars - 3
                warm = i >= self._bars - 6
                if self._cyber:
                    if not on:
                        color = QColor(0, 240, 255, 22)
                    elif hot:
                        color = QColor(CyberTheme.PINK)
                    elif warm:
                        color = QColor(CyberTheme.YELLOW)
                    else:
                        color = QColor(CyberTheme.CYAN)
                else:
                    if not on:
                        color = QColor(255, 255, 255, 16)
                    elif hot:
                        color = QColor("#ff5470")
                    elif warm:
                        color = QColor("#ffb24a")
                    else:
                        color = QColor("#48efaa")
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                x = i * (bar_w + gap)
                painter.drawRoundedRect(QRectF(x, 0, bar_w, self.height()), 1.5, 1.5)
        finally:
            painter.end()


class FlyoutChannelStrip(QFrame):
    SWITCHABLE_CHANNELS = {"game", "chatRender", "media"}
    CHANNEL_INDEX = {"master": 0, "game": 1, "chatRender": 2, "media": 3}
    CHANNEL_TAG = {"master": "CORE", "game": "GAME", "chatRender": "CHAT", "media": "MEDIA"}

    def __init__(
        self,
        channel: ChannelState,
        on_volume_change: Callable[[str, int], None],
        on_toggle_mute: Callable[[str], None],
        on_device_select: Callable[[str, str], None],
        on_route_app: Callable[[str, str], None],
        on_customize_app: Callable[[str, str | None, str | None], None] | None = None,
    ) -> None:
        super().__init__()
        self._channel_key = channel.key
        self._is_master = channel.key not in self.SWITCHABLE_CHANNELS
        self._on_volume_change = on_volume_change
        self._on_toggle_mute = on_toggle_mute
        self._on_device_select = on_device_select
        self._on_route_app = on_route_app
        self._on_customize_app = on_customize_app
        self._display_to_device_id: dict[str, str] = {}
        self._shared_output_mode = False
        self._compact = False
        self._muted = bool(channel.muted)
        self._assigned_apps: list[tuple[str, str]] = []
        self._is_cyber = False

        self.setObjectName("flyoutStrip")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setProperty("master", self._is_master)
        self.setProperty("muted", self._muted)
        self.setAcceptDrops(True)

        body = QHBoxLayout(self)
        body.setContentsMargins(10 if self._is_master else 9, 10 if self._is_master else 8, 10, 10 if self._is_master else 8)
        body.setSpacing(10)
        self._body = body

        self._accent_bar = QWidget()
        self._accent_bar.setObjectName("consoleAccentBar")
        self._accent_bar.setFixedWidth(3)
        body.addWidget(self._accent_bar)

        self._master_icon = QLabel()
        self._master_icon.setObjectName("consoleMasterIcon")
        self._master_icon.setFixedSize(32, 32)
        self._master_icon.setPixmap(FlyoutChannelStrip._build_master_icon().pixmap(18, 18))
        self._master_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(self._master_icon)

        self._mute_button = ConsoleMuteSwitch()
        self._mute_button.clicked.connect(self._on_mute_clicked)
        body.addWidget(self._mute_button, 0, Qt.AlignmentFlag.AlignVCenter)

        label_col = QWidget()
        self._label_col = label_col
        label_layout = QVBoxLayout(label_col)
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(1)
        label_col.setFixedWidth(86 if self._is_master else 96)

        self._cyber_ch_label = QLabel()
        self._cyber_ch_label.setObjectName("cyberChLabel")
        self._cyber_ch_label.hide()
        label_layout.addWidget(self._cyber_ch_label)

        self._title_label = QLabel("Master" if self._is_master else channel.label)
        self._title_label.setObjectName("flyoutCardTitle")
        label_layout.addWidget(self._title_label)

        self._device_combo = QComboBox()
        self._device_combo.setObjectName("consoleDeviceCombo")
        self._device_combo.currentTextChanged.connect(self._on_device_changed)
        label_layout.addWidget(self._device_combo)

        self._bus_label = QLabel("SYSTEM BUS")
        self._bus_label.setObjectName("consoleBusLabel")
        label_layout.addWidget(self._bus_label)
        body.addWidget(label_col)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(3)

        self._slider = ConsoleSlider()
        self._slider.setProperty("master", self._is_master)
        self._slider.setValue(channel.volume)
        self._slider.valueChanged.connect(self._on_slider_change)
        center_layout.addWidget(self._slider)

        self._meter = VUMeter(bars=24 if self._is_master else 18, master=self._is_master)
        center_layout.addWidget(self._meter)

        self._apps_section = ChipContainer(
            self._channel_key,
            self._on_route_app,
            on_customize_app=self._on_customize_app,
            height=28,
        )
        self._apps_section.setMinimumHeight(28)
        self._apps_section.setMaximumHeight(34)
        center_layout.addWidget(self._apps_section)
        body.addWidget(center, 1)

        val_col = QWidget()
        val_layout = QVBoxLayout(val_col)
        val_layout.setContentsMargins(0, 0, 0, 0)
        val_layout.setSpacing(0)
        self._val_col = val_col
        self._val_label_default_w = 48 if self._is_master else 42
        self._value_label = QLabel(f"{channel.volume}%")
        self._value_label.setObjectName("flyoutValueLabel")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._value_label.setFixedWidth(self._val_label_default_w)
        val_layout.addWidget(self._value_label)
        self._hex_label = QLabel("")
        self._hex_label.setObjectName("cyberHexLabel")
        self._hex_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._hex_label.setFixedWidth(self._val_label_default_w)
        self._hex_label.hide()
        val_layout.addWidget(self._hex_label)
        body.addWidget(val_col)

        self.set_muted(channel.muted)
        if self._is_master:
            self._mute_button.hide()
            self._device_combo.setEnabled(False)
            self._device_combo.clear()
            self._device_combo.hide()
            self._apps_section.setVisible(False)
            self._bus_label.show()
        else:
            self._accent_bar.hide()
            self._master_icon.hide()
            self._bus_label.hide()
            self._device_combo.setEnabled(False)
            self._device_combo.addItem("Loading")
        self.set_compact(False)

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)
        self.setProperty("muted", self._muted)
        self.style().unpolish(self)
        self.style().polish(self)
        self._mute_button.blockSignals(True)
        self._mute_button.setChecked(self._muted)
        self._mute_button.setText("")
        self._mute_button.setToolTip("Unmute" if self._muted else "Mute")
        self._mute_button.blockSignals(False)
        self._meter.set_meter(self._meter_level(self._slider.value()), muted=self._muted and not self._is_master)
        self._value_label.setProperty("muted", self._muted)
        self._value_label.style().unpolish(self._value_label)
        self._value_label.style().polish(self._value_label)
        if self._is_cyber and not self._is_master:
            v = self._slider.value()
            self._hex_label.setText("MUTED" if self._muted else f"0x{v:02X}")
            self._apply_cyber_glow()
        self.update()

    def set_device_choices(
        self,
        options: list[tuple[str, str]],
        current_device_id: str | None,
        editable: bool = True,
        disabled_reason: str | None = None,
        linked: bool = False,
    ) -> None:
        if self._channel_key not in self.SWITCHABLE_CHANNELS:
            return
        self._display_to_device_id = {self._format_device_name(name): dev_id for dev_id, name in options}
        labels = list(self._display_to_device_id.keys())

        self._device_combo.blockSignals(True)
        self._device_combo.clear()
        if not labels:
            self._device_combo.addItem("No device")
            self._device_combo.setEnabled(False)
        else:
            self._device_combo.addItems(labels)
            selected = next((self._format_device_name(name) for dev_id, name in options if dev_id == current_device_id), labels[0])
            self._device_combo.setCurrentText(selected)
            if editable:
                tip = selected
                if disabled_reason:
                    tip = f"{selected}\n{disabled_reason}"
                self._device_combo.setToolTip(tip)
                self._device_combo.setEnabled(True)
            else:
                reason = disabled_reason or "Source linked in Sonar. Change from another channel."
                self._device_combo.setToolTip(f"{selected}\n{reason}")
                self._device_combo.setEnabled(False)
        self._device_combo.blockSignals(False)

    def set_assigned_apps(self, apps: list[tuple[str, str]]) -> None:
        self._assigned_apps = list(apps)
        self._apps_section.set_apps(self._assigned_apps[:3])
        self._apps_section.setVisible(
            (not self._compact) and (self._channel_key in self.SWITCHABLE_CHANNELS) and bool(self._assigned_apps)
        )
        self._apply_console_height()

    def set_volume_value(self, value: int) -> None:
        value = max(0, min(100, int(value)))
        self._slider.blockSignals(True)
        self._slider.setValue(value)
        self._slider.blockSignals(False)
        if self._is_cyber:
            self._value_label.setText(str(value).zfill(3))
            self._hex_label.setText("/100 dB" if self._is_master else f"0x{value:02X}")
        else:
            self._value_label.setText(f"{value}%")
        self._meter.set_meter(self._meter_level(value), muted=self._muted and not self._is_master)

    def set_audio_level(self, level: float) -> None:
        self._meter.set_peak(level, muted=self._muted and not self._is_master)

    def _on_slider_change(self, value: int) -> None:
        if self._is_cyber:
            self._value_label.setText(str(value).zfill(3))
            self._hex_label.setText("/100 dB" if self._is_master else f"0x{value:02X}")
        else:
            self._value_label.setText(f"{value}%")
        self._meter.set_meter(self._meter_level(value), muted=self._muted and not self._is_master)
        self._on_volume_change(self._channel_key, int(value))

    def _on_mute_clicked(self) -> None:
        self._on_toggle_mute(self._channel_key)

    def _on_device_changed(self, text: str) -> None:
        self._device_combo.setToolTip(text)
        device_id = self._display_to_device_id.get(text)
        if device_id:
            self._on_device_select(self._channel_key, device_id)

    @staticmethod
    def _build_master_icon() -> QIcon:
        for svg_path in (
            Path(__file__).resolve().parent / "assets" / "app-icon.svg",
            Path(__file__).resolve().parent / "assets" / "app-icon.png",
        ):
            if svg_path.exists():
                icon = QIcon(str(svg_path))
                if not icon.isNull():
                    return icon
        return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if self._channel_key in self.SWITCHABLE_CHANNELS and event.mimeData().text().strip().startswith("pid:"):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._channel_key in self.SWITCHABLE_CHANNELS and event.mimeData().text().strip().startswith("pid:"):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        text = event.mimeData().text().strip()
        if self._channel_key not in self.SWITCHABLE_CHANNELS or not text.startswith("pid:"):
            event.ignore()
            return
        process_id = text.split(":", 1)[1].strip()
        if process_id:
            self._on_route_app(process_id, self._channel_key)
            event.acceptProposedAction()
            return
        event.ignore()

    def set_cyber(self, cyber: bool) -> None:
        self._is_cyber = bool(cyber)
        self._meter.set_cyber(cyber)
        self._mute_button.set_cyber(cyber)
        self._apps_section.set_cyber(cyber)
        idx = self.CHANNEL_INDEX.get(self._channel_key, 0)
        self._cyber_ch_label.setText(f"[ CH.{idx:02d} ]")
        self._cyber_ch_label.setVisible(cyber)
        if self._is_master:
            self._master_icon.setVisible(not cyber and not self._compact)
        # Widen label column to fit the monospace CH tag
        self._label_col.setFixedWidth((96 if self._is_master else 96) if cyber else (86 if self._is_master else 96))
        v = self._slider.value()
        cyber_w = 58 if self._is_master else 52
        val_w = cyber_w if cyber else self._val_label_default_w
        self._value_label.setFixedWidth(val_w)
        self._hex_label.setFixedWidth(val_w)
        if cyber:
            self._value_label.setText(str(v).zfill(3))
            self._hex_label.setText("/100 dB" if self._is_master else ("MUTED" if self._muted else f"0x{v:02X}"))
            fs = "22px" if self._is_master else "17px"
            self._value_label.setStyleSheet(f"font-size: {fs}; font-weight: 700; color: #ffffff;")
            self._hex_label.setStyleSheet("font-size: 7px;")
        else:
            self._value_label.setText(f"{v}%")
            self._value_label.setStyleSheet("")
            self._hex_label.setStyleSheet("")
        self._hex_label.setVisible(cyber)
        self._apply_cyber_glow()
        self._apply_console_height()
        self.update()

    def _apply_cyber_glow(self) -> None:
        if not self._is_cyber:
            self._value_label.setGraphicsEffect(None)
            self._title_label.setGraphicsEffect(None)
            return
        val_color = CyberTheme.PINK if (self._is_master or self._muted) else CyberTheme.CYAN
        val_radius = 14 if self._is_master else 10
        title_color = CyberTheme.PINK if (self._is_master or self._muted) else CyberTheme.CYAN
        for widget, color, radius in (
            (self._value_label, val_color, val_radius),
            (self._title_label, title_color, 8),
        ):
            fx = QGraphicsDropShadowEffect()
            fx.setColor(QColor(color))
            fx.setBlurRadius(radius)
            fx.setOffset(0, 0)
            widget.setGraphicsEffect(fx)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if not self._is_cyber:
            super().paintEvent(event)
            return
        w, h = self.width(), self.height()
        cut = 9 if self._is_master else 6
        muted = self._muted
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        try:
            path = CyberTheme.chamfer_path(w, h, cut)
            if self._is_master:
                bg = QColor(255, 45, 138, 15)
            elif muted:
                bg = QColor(255, 45, 138, 22)
            else:
                bg = QColor(0, 240, 255, 10)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg)
            painter.drawPath(path)
            border_c = QColor(255, 45, 138, 85) if (self._is_master or muted) else QColor(0, 240, 255, 55)
            painter.setPen(QPen(border_c, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(QTransform().translate(0.5, 0.5).map(CyberTheme.chamfer_path(w - 1, h - 1, cut)))
            if self._is_master:
                painter.setPen(QPen(QColor(255, 45, 138, 200), 1.5))
                s = 10
                painter.drawLine(4, 4 + s, 4, 4)
                painter.drawLine(4, 4, 4 + s, 4)
                painter.drawLine(w - 4 - s, h - 4, w - 4, h - 4)
                painter.drawLine(w - 4, h - 4, w - 4, h - 4 - s)
        finally:
            painter.end()

    def set_compact(self, compact: bool) -> None:
        self._compact = bool(compact)
        self.setMinimumWidth(0)
        self.setMaximumWidth(16777215)
        self._body.setContentsMargins(9 if self._compact else 10, 7 if self._compact else 10, 9, 7 if self._compact else 10)
        self._meter.set_bars(18 if self._compact else (24 if self._is_master else 18))
        show_details = (not self._compact) and (self._channel_key in self.SWITCHABLE_CHANNELS)
        self._apps_section.setVisible(show_details and bool(self._assigned_apps))
        if self._is_master:
            self._accent_bar.setVisible(not self._compact)
            self._master_icon.setVisible(not self._compact and not self._is_cyber)
            self._mute_button.hide()
            self._device_combo.hide()
            self._bus_label.setVisible(not self._compact)
        else:
            self._mute_button.setVisible(not self._compact)
            self._device_combo.setVisible((not self._compact) and (not self._shared_output_mode))
        self._title_label.setStyleSheet("font-size: 12px;" if self._compact else "")
        self._apply_console_height()

    def set_shared_output_mode(self, enabled: bool) -> None:
        self._shared_output_mode = bool(enabled)
        if self._channel_key not in self.SWITCHABLE_CHANNELS:
            return
        self._device_combo.setVisible((not self._compact) and (not self._shared_output_mode))

    def _meter_level(self, volume: int) -> int:
        if self._is_master:
            return min(95, int(volume) + 8)
        seed = 0
        for ch in f"{self._channel_key}{volume}":
            seed = (seed * 131 + ord(ch)) & 0xFFFFFFFF
        return int(((seed % 65) + 25) * (max(0, min(100, int(volume))) / 100))

    def _apply_console_height(self) -> None:
        if self._compact:
            height = 72 if self._is_cyber else 58
        elif self._is_master:
            height = 92 if self._is_cyber else 78
        elif self._assigned_apps:
            height = 108 if self._is_cyber else 94
        else:
            height = 86 if self._is_cyber else 72
        self.setFixedHeight(height)

    @staticmethod
    def _format_device_name(name: str) -> str:
        text = str(name).strip()
        if "(" in text:
            text = text.split("(", 1)[0].strip()
        return text or str(name)


class _DraggableHeader(QWidget):
    def __init__(self, parent_window: QWidget, on_close: Callable[[], None]) -> None:
        super().__init__(parent_window)
        self._parent_window = parent_window
        self._drag_pos: QPoint | None = None
        self.setObjectName("flyoutHeader")
        self.setFixedHeight(28)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 2, 0)
        layout.setSpacing(4)
        title = QLabel("SoundDeck")
        title.setObjectName("flyoutHeaderTitle")
        layout.addWidget(title)
        layout.addStretch(1)
        close_btn = QPushButton("×")
        close_btn.setObjectName("flyoutCloseBtn")
        close_btn.setFixedSize(22, 22)
        close_btn.clicked.connect(on_close)
        layout.addWidget(close_btn)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and not self._locked():
            self._drag_pos = event.globalPosition().toPoint() - self._parent_window.frameGeometry().topLeft()
            setattr(self._parent_window, "_user_dragging", True)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._parent_window.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def _locked(self) -> bool:
        return bool(getattr(self._parent_window, "_position_locked", False))

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._drag_pos = None
        setattr(self._parent_window, "_user_dragging", False)
        super().mouseReleaseEvent(event)


_APP_ICON_CACHE: dict[str, QPixmap] = {}
_ICON_PROVIDER: QFileIconProvider | None = None


def _app_icon_pixmap(exe_path: str, size: int = 24) -> QPixmap:
    """Extract (and cache) an application's icon from its executable path."""
    global _ICON_PROVIDER
    key = f"{exe_path}|{size}"
    cached = _APP_ICON_CACHE.get(key)
    if cached is not None:
        return cached
    pixmap = QPixmap()
    if exe_path:
        try:
            if _ICON_PROVIDER is None:
                _ICON_PROVIDER = QFileIconProvider()
            icon = _ICON_PROVIDER.icon(QFileInfo(exe_path))
            if not icon.isNull():
                pixmap = icon.pixmap(size, size)
        except Exception:
            pixmap = QPixmap()
    _APP_ICON_CACHE[key] = pixmap
    return pixmap


def _tinted_pixmap(pixmap: QPixmap, color: str) -> QPixmap:
    """Return a monochrome silhouette of ``pixmap`` filled with ``color``.

    Keeps the icon's alpha shape but recolors it — used to make app icons match
    the cyber HUD's cyan palette.
    """
    if pixmap.isNull():
        return pixmap
    out = QPixmap(pixmap.size())
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    try:
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(out.rect(), QColor(color))
    finally:
        painter.end()
    return out


class AppVolumeRow(QFrame):
    """One per-app strip (icon + name + slider + VU meter + value + mute)."""

    def __init__(
        self,
        app,
        on_volume,
        on_mute,
        cyber: bool = False,
        is_mic: bool = False,
        on_hide: Callable[[str, str], None] | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("appVolumeRow")
        self._pid = int(app.pid)
        self._on_volume = on_volume
        self._on_mute = on_mute
        self._on_hide = on_hide
        self._muted = bool(app.muted)
        self._full_name = str(app.name)
        self._exe_path = str(getattr(app, "exe_path", ""))
        self._key = str(getattr(app, "key", ""))
        self._is_mic = bool(is_mic)
        self._cyber = bool(cyber)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(11, 8, 11, 8)
        layout.setSpacing(11)

        self._icon = QLabel()
        self._icon.setObjectName("appRowIcon")
        self._icon.setFixedSize(30, 30)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_icon()
        layout.addWidget(self._icon)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(5)

        self._name = QLabel(self._full_name)
        self._name.setObjectName("appRowName")
        self._name.setToolTip(self._full_name)
        center_layout.addWidget(self._name)

        self._slider = ConsoleSlider()
        self._slider.setValue(int(app.volume))
        self._slider.valueChanged.connect(self._changed)
        center_layout.addWidget(self._slider)

        self._meter = VUMeter(bars=20, master=False)
        self._meter.set_cyber(cyber)
        center_layout.addWidget(self._meter)
        layout.addWidget(center, 1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        self._value = QLabel(f"{int(app.volume)}%")
        self._value.setObjectName("appRowValue")
        self._value.setFixedWidth(44)
        self._value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right_layout.addWidget(self._value)
        self._mute = QPushButton()
        self._mute.setObjectName("appRowMute")
        self._mute.setFixedSize(30, 24)
        self._mute.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute.clicked.connect(self._mute_clicked)
        right_layout.addWidget(self._mute, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(right)

        self._elide()
        self._sync_mute()

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        # The mic strip reuses this row but is not an app, so it cannot be hidden.
        if self._on_hide is None or self._is_mic or not self._key:
            return
        menu = QMenu(self)
        hide_action = menu.addAction(f"Hide {self._full_name}")
        if menu.exec(event.globalPos()) == hide_action:
            self._on_hide(self._key, self._full_name)

    def _apply_icon(self) -> None:
        if self._is_mic:
            self._icon.setText("🎙")
            color = "rgba(0,240,255,220)" if self._cyber else "rgba(255,255,255,150)"
            self._icon.setStyleSheet(f"color: {color}; font-size: 16px;")
            return
        pixmap = _app_icon_pixmap(self._exe_path, 26)
        if pixmap.isNull():
            self._icon.setText("♪")
            self._icon.setStyleSheet("color: rgba(255,255,255,90); font-size: 15px;")
            return
        self._icon.setStyleSheet("")
        self._icon.setPixmap(pixmap)

    def _elide(self) -> None:
        fm = self._name.fontMetrics()
        width = self._name.width() or 150
        self._name.setText(fm.elidedText(self._full_name, Qt.TextElideMode.ElideRight, width))

    def _changed(self, value: int) -> None:
        self._value.setText(f"{int(value)}%")
        if self._on_volume:
            self._on_volume(self._pid, int(value))

    def _mute_clicked(self) -> None:
        if self._on_mute:
            self._on_mute(self._pid)

    def _sync_mute(self) -> None:
        self._mute.setText("🔇" if self._muted else "🔊")
        self.setProperty("muted", self._muted)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_level(self, peak: float) -> None:
        self._meter.set_peak(peak, muted=self._muted)

    def set_cyber(self, cyber: bool) -> None:
        self._cyber = bool(cyber)
        self._meter.set_cyber(self._cyber)
        self._apply_icon()

    def update_from(self, app) -> None:
        if app.name != self._full_name:
            self._full_name = str(app.name)
            self._name.setToolTip(self._full_name)
            self._elide()
        if not self._slider.hasFocus() and int(app.volume) != self._slider.value():
            self._slider.blockSignals(True)
            self._slider.setValue(int(app.volume))
            self._slider.blockSignals(False)
            self._value.setText(f"{int(app.volume)}%")
        if bool(app.muted) != self._muted:
            self._muted = bool(app.muted)
            self._sync_mute()

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)
        self._sync_mute()


class _MicDescriptor:
    """Lightweight app-like descriptor so the mic reuses AppVolumeRow."""

    def __init__(self, volume: int, muted: bool) -> None:
        self.pid = -1
        self.name = "Microphone"
        self.exe_path = ""
        self.volume = int(volume)
        self.muted = bool(muted)


class FlyoutMixerWindow(QWidget):
    def __init__(
        self,
        on_refresh: Callable[[], None],
        on_volume_change: Callable[[str, int], None],
        on_toggle_mute: Callable[[str], None],
        on_device_select: Callable[[str, str], None],
        on_route_app: Callable[[str, str], None],
        on_customize_app: Callable[[str, str | None, str | None], None] | None = None,
        on_show: Callable[[], None] | None = None,
        on_hide: Callable[[], None] | None = None,
        on_app_volume_change: Callable[[int, int], None] | None = None,
        on_app_toggle_mute: Callable[[int], None] | None = None,
        on_mic_volume_change: Callable[[int], None] | None = None,
        on_mic_toggle_mute: Callable[[], None] | None = None,
        on_hide_app: Callable[[str, str], None] | None = None,
        on_unhide_app: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(None)
        # Set before any window ops below: setWindowTitle/setWindowFlags can fire
        # changeEvent, which reads these flags.
        self._close_on_outside = False
        self._position_locked = False
        self.setWindowTitle("SoundDeck Flyout")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedWidth(500)

        self._on_refresh = on_refresh
        self._on_volume_change = on_volume_change
        self._on_toggle_mute = on_toggle_mute
        self._on_device_select = on_device_select
        self._on_route_app = on_route_app
        self._on_customize_app = on_customize_app
        self._on_show = on_show
        self._on_hide = on_hide
        self._on_app_volume_change = on_app_volume_change
        self._on_app_toggle_mute = on_app_toggle_mute
        self._on_hide_app = on_hide_app
        self._on_unhide_app = on_unhide_app
        self._hidden_apps: list[tuple[str, str]] = []
        self._on_mic_volume_change = on_mic_volume_change
        self._on_mic_toggle_mute = on_mic_toggle_mute

        self._mic_row: AppVolumeRow | None = None
        self._app_rows: dict[int, AppVolumeRow] = {}
        # When True the flyout keeps its bottom edge fixed and grows upward on
        # height changes (it is anchored above the tray), instead of clipping down.
        self._grow_upward = True
        # Set while the user is dragging the header, so auto-reposition stays out of the way.
        self._user_dragging = False
        self._cards: dict[str, FlyoutChannelStrip] = {}
        self._channel_apps: dict[str, list[tuple[str, str]]] = {"game": [], "chatRender": [], "media": []}
        self._pid_label: dict[str, str] = {}
        self._shared_display_to_device_id: dict[str, str] = {}
        self._shared_source_channel_key = "game"
        self._win_output_display_to_id: dict[str, str] = {}
        self._win_output_sig: tuple | None = None
        self._compact_mode = False
        self._cyber_mode = False
        self._dispatcher = _UiDispatcher()

        self._build_ui()
        self._apply_theme()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        hwnd = int(self.winId())
        _enable_windows_blur(hwnd)
        _hide_from_taskbar(hwnd)
        if self._on_show:
            self._on_show()

    def set_close_on_outside(self, enabled: bool) -> None:
        self._close_on_outside = bool(enabled)

    def set_position_locked(self, locked: bool) -> None:
        self._position_locked = bool(locked)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(0)

        self._panel = _MixerPanel()
        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(6)

        panel_layout.addWidget(_DraggableHeader(parent_window=self, on_close=self.hide))

        self._hud_top = _CyberHudTop()
        self._hud_top.hide()
        panel_layout.addWidget(self._hud_top)

        self._shared_row = QWidget()
        self._shared_row.setObjectName("sharedSourceRow")
        shared_layout = QHBoxLayout(self._shared_row)
        shared_layout.setContentsMargins(2, 0, 2, 0)
        shared_layout.setSpacing(6)
        self._shared_label = QLabel("SOURCE")
        self._shared_label.setObjectName("sharedSourceLabel")
        self._shared_label.hide()
        self._shared_combo = QComboBox()
        self._shared_combo.setObjectName("deviceCombo")
        self._shared_combo.setMinimumWidth(220)
        self._shared_combo.currentTextChanged.connect(self._on_shared_device_changed)
        self._shared_battery_label = QLabel("")
        self._shared_battery_label.setObjectName("sharedBatteryLabel")
        self._shared_battery_label.hide()
        shared_layout.addWidget(self._shared_label)
        shared_layout.addWidget(self._shared_combo, 1)
        shared_layout.addWidget(self._shared_battery_label)
        self._shared_row.hide()
        panel_layout.addWidget(self._shared_row)

        # Windows-mode default output selector (shown only when Sonar is unavailable).
        self._win_output_host = QWidget()
        self._win_output_host.setAutoFillBackground(False)
        win_out_layout = QVBoxLayout(self._win_output_host)
        win_out_layout.setContentsMargins(0, 0, 0, 2)
        win_out_layout.setSpacing(3)
        self._win_output_label = QLabel("OUTPUT DEVICE")
        self._win_output_label.setObjectName("flyoutAppsLabel")
        win_out_layout.addWidget(self._win_output_label)
        self._win_output_combo = QComboBox()
        self._win_output_combo.setObjectName("deviceCombo")
        self._win_output_combo.currentTextChanged.connect(self._on_win_output_changed)
        win_out_layout.addWidget(self._win_output_combo)
        self._win_output_host.hide()
        panel_layout.addWidget(self._win_output_host)

        cards_host = QWidget()
        cards_host.setAutoFillBackground(False)
        self._cards_layout = QVBoxLayout(cards_host)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(5)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._cards_scroll = QScrollArea()
        self._cards_scroll.setObjectName("flyoutCardsScroll")
        self._cards_scroll.setWidgetResizable(True)
        self._cards_scroll.setWidget(cards_host)
        self._cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cards_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._cards_scroll.setAutoFillBackground(False)
        self._cards_scroll.viewport().setAutoFillBackground(False)
        panel_layout.addWidget(self._cards_scroll)

        # Microphone section (Sonar-independent) — its own labelled block below master.
        self._mic_host = QWidget()
        self._mic_host.setAutoFillBackground(False)
        self._mic_host_layout = QVBoxLayout(self._mic_host)
        self._mic_host_layout.setContentsMargins(0, 5, 0, 0)
        self._mic_host_layout.setSpacing(3)
        self._mic_section_label = QLabel("MICROPHONE")
        self._mic_section_label.setObjectName("flyoutAppsLabel")
        self._mic_host_layout.addWidget(self._mic_section_label)
        self._mic_host.hide()
        panel_layout.addWidget(self._mic_host)

        # Per-app mixer. Right-clicking the header is the way back for anything
        # hidden from it, so the label says so once something is.
        self._apps_section_label = QLabel("APPS")
        self._apps_section_label.setObjectName("flyoutAppsLabel")
        self._apps_section_label.setContentsMargins(0, 5, 0, 0)
        self._apps_section_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._apps_section_label.customContextMenuRequested.connect(self._show_hidden_apps_menu)
        self._apps_section_label.hide()
        panel_layout.addWidget(self._apps_section_label)

        apps_host = QWidget()
        apps_host.setAutoFillBackground(False)
        self._apps_layout = QVBoxLayout(apps_host)
        self._apps_layout.setContentsMargins(0, 2, 0, 0)
        self._apps_layout.setSpacing(4)
        self._apps_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._apps_scroll = QScrollArea()
        self._apps_scroll.setObjectName("flyoutAppsScroll")
        self._apps_scroll.setWidgetResizable(True)
        self._apps_scroll.setWidget(apps_host)
        self._apps_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._apps_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._apps_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._apps_scroll.setAutoFillBackground(False)
        self._apps_scroll.viewport().setAutoFillBackground(False)
        self._apps_scroll.hide()
        panel_layout.addWidget(self._apps_scroll)

        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("flyoutStatusLabel")
        self._status_label.setFont(QFont("Segoe UI", 8))
        panel_layout.addWidget(self._status_label)
        self._status_label.hide()

        self._hud_bottom = _CyberHudBottom()
        self._hud_bottom.hide()
        panel_layout.addWidget(self._hud_bottom)

        root.addWidget(self._panel)


    def _apply_theme(self) -> None:
        Theme.refresh_from_system()
        self.setStyleSheet(
            f"""
            QWidget {{
                font-family: "Segoe UI Variable", "Segoe UI";
            }}
            QFrame#flyoutPanel {{
                background-color: #10131b;
                border: 1px solid rgba(255, 255, 255, 16);
                border-radius: 14px;
            }}
            QFrame#flyoutStrip {{
                background-color: rgba(255, 255, 255, 7);
                border: 1px solid rgba(255, 255, 255, 15);
                border-radius: 8px;
            }}
            QFrame#flyoutStrip[master="true"] {{
                background-color: rgba(255, 255, 255, 8);
                border-radius: 10px;
            }}
            QFrame#flyoutStrip[muted="true"] {{
                background-color: rgba(255, 111, 134, 20);
                border: 1px solid rgba(255, 111, 134, 68);
            }}
            QWidget#consoleAccentBar {{
                background-color: {Theme.ACCENT};
                border-radius: 1px;
            }}
            QLabel#consoleMasterIcon {{
                background-color: {Theme.ACCENT};
                border-radius: 8px;
            }}
            QWidget#sharedSourceRow {{
                background: transparent;
                border: none;
            }}
            QLabel#sharedSourceLabel {{
                color: {Theme.TEXT_MUTED};
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.4px;
                padding-left: 4px;
            }}
            QComboBox#deviceCombo {{
                background-color: rgba(24, 29, 40, 238);
                border: 1px solid rgba(255, 255, 255, 34);
                border-radius: 8px;
                color: {Theme.TEXT};
                min-height: 24px;
                padding: 0 10px;
            }}
            QComboBox#deviceCombo:hover {{
                background-color: rgba(32, 38, 52, 245);
            }}
            QComboBox#deviceCombo::drop-down {{
                width: 0px;
                border: none;
            }}
            QComboBox#deviceCombo::down-arrow {{
                image: none;
                width: 0px;
                height: 0px;
            }}
            QLabel#flyoutCardTitle {{
                color: {Theme.TEXT};
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 0.3px;
            }}
            QLabel#flyoutValueLabel {{
                color: {Theme.TEXT};
                font-size: 16px;
                font-weight: 400;
            }}
            QLabel#flyoutValueLabel[muted="true"] {{ color: {Theme.ACCENT}; }}
            QFrame#appVolumeRow {{
                background-color: rgba(255, 255, 255, 7);
                border: 1px solid rgba(255, 255, 255, 14);
                border-radius: 7px;
            }}
            QFrame#appVolumeRow[muted="true"] {{
                background-color: rgba(255, 111, 134, 18);
                border: 1px solid rgba(255, 111, 134, 60);
            }}
            QLabel#appRowName {{
                color: {Theme.TEXT};
                font-size: 11px;
                font-weight: 500;
            }}
            QLabel#appRowValue {{
                color: {Theme.TEXT_MUTED};
                font-size: 11px;
            }}
            QPushButton#appRowMute {{
                background-color: rgba(255, 255, 255, 10);
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 5px;
                font-size: 12px;
                padding: 0px;
            }}
            QPushButton#appRowMute:hover {{
                background-color: rgba(255, 255, 255, 22);
            }}
            QLabel#flyoutAppsLabel {{
                color: {Theme.TEXT_MUTED};
                font-size: 8px;
                font-weight: 600;
                letter-spacing: 0.8px;
                padding-top: 0px;
                padding-bottom: 0px;
            }}
            QLabel#flyoutStatusLabel {{
                color: {Theme.TEXT_MUTED};
                padding-left: 2px;
            }}
            QLabel#consoleBusLabel {{
                color: rgba(238, 241, 247, 135);
                font-size: 9px;
                letter-spacing: 0.6px;
            }}
            QComboBox#consoleDeviceCombo {{
                background-color: transparent;
                border: none;
                color: rgba(238, 241, 247, 135);
                font-size: 9px;
                padding: 0px 8px 0px 0px;
                min-height: 14px;
                max-height: 16px;
            }}
            QComboBox#consoleDeviceCombo::drop-down {{
                width: 0px;
                border: none;
            }}
            QComboBox#consoleDeviceCombo::down-arrow {{
                image: none;
                width: 0px;
                height: 0px;
            }}
            QComboBox QAbstractItemView {{
                background-color: rgb(20, 24, 34);
                border: 1px solid rgba(255, 255, 255, 54);
                border-radius: 10px;
                color: {Theme.TEXT};
                outline: none;
                padding: 3px;
                selection-background-color: rgba(255, 111, 134, 45);
                selection-color: {Theme.TEXT};
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 30px;
                padding: 0 10px;
                border-radius: 6px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: rgba(255, 255, 255, 16);
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: rgba(255, 111, 134, 50);
            }}
            QSlider#consoleSlider {{
                min-height: 18px;
                max-height: 18px;
            }}
            QSlider#consoleSlider::groove:horizontal {{
                background: rgba(255, 255, 255, 16);
                height: 5px;
                border-radius: 2px;
            }}
            QSlider#consoleSlider::sub-page:horizontal {{
                background: {Theme.ACCENT};
                border-radius: 2px;
            }}
            QSlider#consoleSlider[master="true"]::sub-page:horizontal {{
                background: {Theme.ACCENT};
            }}
            QSlider#consoleSlider::add-page:horizontal {{
                background: rgba(255, 255, 255, 16);
                border-radius: 2px;
            }}
            QSlider#consoleSlider::handle:horizontal {{
                background: #ffffff;
                border: none;
                width: 10px;
                height: 10px;
                margin: -3px 0;
                border-radius: 5px;
            }}
            QSlider#consoleSlider[hovered="true"]::handle:horizontal {{
                background: #ffffff;
                border: none;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
            QSlider#consoleSlider[active="true"]::handle:horizontal {{
                background: #ffffff;
                border: none;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
            QFrame#chipContainer {{
                background-color: transparent;
                border: none;
            }}
            QListWidget#channelChipList {{
                background: transparent;
                border: none;
                outline: none;
                padding: 0px;
                color: {Theme.TEXT_MUTED};
                font-size: 9px;
            }}
            QListWidget#channelChipList::item {{ padding: 0px; }}
            QWidget#flyoutHeader {{
                background: transparent;
                border: none;
            }}
            QLabel#flyoutHeaderTitle {{
                color: {Theme.TEXT_MUTED};
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }}
            QPushButton#flyoutCloseBtn {{
                background: transparent;
                border: none;
                color: rgba(174, 183, 195, 100);
                font-size: 18px;
                border-radius: 5px;
                padding: 0;
            }}
            QPushButton#flyoutCloseBtn:hover {{
                background: rgba(255, 111, 134, 18);
                color: #ff6f86;
            }}
            QScrollArea#flyoutCardsScroll {{
                background: transparent;
                border: none;
            }}
            QScrollArea#flyoutCardsScroll > QWidget {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 5px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255, 255, 255, 35);
                border-radius: 2px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(255, 255, 255, 55);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QWidget#cyberHudTop, QWidget#cyberHudBottom {{
                background: transparent;
            }}
            QLabel#cyberHudDot {{
                color: {CyberTheme.PINK};
                font-family: {CyberTheme.MONO};
                font-size: 9px;
            }}
            QLabel#cyberHudRec {{
                color: {CyberTheme.PINK};
                font-family: {CyberTheme.MONO};
                font-size: 8px;
                font-weight: 700;
                letter-spacing: 2px;
            }}
            QLabel#cyberHudTitle {{
                color: {CyberTheme.CYAN};
                font-family: {CyberTheme.MONO};
                font-size: 8px;
                font-weight: 700;
                letter-spacing: 2px;
            }}
            QFrame#cyberHudSep {{
                border: none;
                border-top: 1px solid rgba(0, 240, 255, 40);
                max-height: 1px;
            }}
            QLabel#cyberHudSysOk {{
                color: rgba(223, 250, 255, 0.55);
                font-family: {CyberTheme.MONO};
                font-size: 8px;
                letter-spacing: 1px;
            }}
            QLabel#cyberHudBars {{
                color: {CyberTheme.CYAN};
                font-size: 8px;
            }}
            QLabel#cyberHudInfo {{
                color: rgba(223, 250, 255, 0.45);
                font-family: {CyberTheme.MONO};
                font-size: 7px;
                letter-spacing: 1px;
            }}
            QLabel#cyberHudDim {{
                color: rgba(223, 250, 255, 0.25);
                font-size: 8px;
            }}
            QLabel#cyberDiamonds {{
                color: {CyberTheme.PINK};
                font-size: 8px;
            }}
            QLabel#cyberChLabel {{
                color: {CyberTheme.CYAN};
                font-family: {CyberTheme.MONO};
                font-size: 7px;
                letter-spacing: 1px;
            }}
            QLabel#cyberHexLabel {{
                color: {CyberTheme.PINK};
                font-family: {CyberTheme.MONO};
                font-size: 7px;
                letter-spacing: 1px;
            }}
            """
        )

    def dispatch(self, callback: Callable[[], None]) -> None:
        self._dispatcher.invoke.emit(callback)

    def set_channels(self, channels: list[ChannelState]) -> None:
        incoming_keys = [c.key for c in channels]
        existing_keys = list(self._cards.keys())
        if existing_keys and set(existing_keys) == set(incoming_keys):
            for channel in channels:
                card = self._cards.get(channel.key)
                if not card:
                    continue
                card.set_volume_value(channel.volume)
                card.set_muted(channel.muted)
            return

        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._cards.clear()
        for channel in channels:
            card = FlyoutChannelStrip(
                channel=channel,
                on_volume_change=self._on_volume_change,
                on_toggle_mute=self._on_toggle_mute,
                on_device_select=self._on_device_select,
                on_route_app=self._handle_route_drop,
                on_customize_app=self._on_customize_app,
            )
            card.set_compact(self._compact_mode)
            card.set_cyber(self._cyber_mode)
            self._cards_layout.addWidget(card)
            self._cards[channel.key] = card
        self._apply_window_height()

    def set_device_choices(
        self,
        channel_key: str,
        options: list[tuple[str, str]],
        current_device_id: str | None,
        editable: bool = True,
        disabled_reason: str | None = None,
        linked: bool = False,
    ) -> None:
        card = self._cards.get(channel_key)
        if card:
            card.set_device_choices(
                options,
                current_device_id,
                editable=editable,
                disabled_reason=disabled_reason,
                linked=linked,
            )

    def set_shared_device_choices(
        self,
        options: list[tuple[str, str]],
        current_device_id: str | None,
        channel_key: str = "game",
    ) -> None:
        self._shared_source_channel_key = channel_key
        if not options:
            self._shared_display_to_device_id.clear()
            self._shared_combo.blockSignals(True)
            self._shared_combo.clear()
            self._shared_combo.blockSignals(False)
            self._shared_row.hide()
            for card in self._cards.values():
                card.set_shared_output_mode(False)
            self._apply_window_height()
            return

        normalized = [(dev_id, self._format_source_name(name)) for dev_id, name in options]
        self._shared_display_to_device_id = {name: dev_id for dev_id, name in normalized}
        labels = [name for _, name in normalized]
        selected = next((name for dev_id, name in normalized if dev_id == current_device_id), labels[0])
        self._shared_combo.blockSignals(True)
        self._shared_combo.clear()
        self._shared_combo.addItems(labels)
        self._shared_combo.setCurrentText(selected)
        self._shared_combo.setToolTip(selected)
        self._shared_combo.setEnabled(True)
        self._shared_combo.blockSignals(False)
        self._shared_row.show()
        self._update_shared_battery()
        for card in self._cards.values():
            card.set_shared_output_mode(True)
        self._apply_window_height()

    def _on_shared_device_changed(self, text: str) -> None:
        self._shared_combo.setToolTip(text)
        self._update_shared_battery()
        device_id = self._shared_display_to_device_id.get(text)
        if device_id:
            self._on_device_select(self._shared_source_channel_key, device_id)

    def set_windows_output_devices(
        self,
        options: list[tuple[str, str]],
        current_device_id: str | None,
    ) -> None:
        """Populate the Windows default-output selector. Empty list hides it.

        A signature guard skips rebuilds when nothing changed, so the periodic
        refresh does not fight the user (e.g. close an open dropdown).
        """
        sig = (tuple(options), current_device_id)
        if not options:
            self._win_output_sig = None
            self._win_output_display_to_id.clear()
            self._win_output_combo.blockSignals(True)
            self._win_output_combo.clear()
            self._win_output_combo.blockSignals(False)
            if not self._win_output_host.isHidden():
                self._win_output_host.hide()
                self._apply_window_height()
            return
        if sig == self._win_output_sig and not self._win_output_host.isHidden():
            return
        self._win_output_sig = sig

        normalized = [(dev_id, self._format_source_name(name)) for dev_id, name in options]
        self._win_output_display_to_id = {name: dev_id for dev_id, name in normalized}
        labels = [name for _, name in normalized]
        selected = next((name for dev_id, name in normalized if dev_id == current_device_id), labels[0])
        self._win_output_combo.blockSignals(True)
        self._win_output_combo.clear()
        self._win_output_combo.addItems(labels)
        self._win_output_combo.setCurrentText(selected)
        self._win_output_combo.setToolTip(selected)
        self._win_output_combo.blockSignals(False)
        was_hidden = self._win_output_host.isHidden()
        self._win_output_host.show()
        if was_hidden:
            self._apply_window_height()

    def _on_win_output_changed(self, text: str) -> None:
        self._win_output_combo.setToolTip(text)
        device_id = self._win_output_display_to_id.get(text)
        if device_id:
            self._on_device_select("windows-output", device_id)

    @staticmethod
    def _format_source_name(name: str) -> str:
        text = " ".join(str(name).replace("_", " ").split())
        if not text:
            return name
        if "(" in text and ")" in text:
            return text
        preserved = {"USB", "DAC", "HDMI", "SPDIF", "AUX", "BT", "TV", "PC"}
        out: list[str] = []
        for token in text.split(" "):
            upper = token.upper()
            if upper in preserved:
                out.append(upper)
            elif any(ch.isdigit() for ch in token):
                out.append(token)
            else:
                out.append(token.capitalize())
        return " ".join(out)

    def set_status(self, status: str) -> None:
        self._status_label.setText(status)

    def set_compact(self, compact: bool) -> None:
        self._compact_mode = bool(compact)
        if self._compact_mode:
            self.setFixedWidth(390)
            self._shared_combo.setMinimumWidth(180)
        else:
            self.setFixedWidth(500)
            self._shared_combo.setMinimumWidth(220)
        for card in self._cards.values():
            card.set_compact(self._compact_mode)
        self._apply_window_height()

    def set_cyber_mode(self, cyber: bool) -> None:
        self._cyber_mode = bool(cyber)
        self._panel.set_cyber(self._cyber_mode)
        self._hud_top.setVisible(self._cyber_mode)
        self._hud_bottom.setVisible(self._cyber_mode)
        if self._cyber_mode:
            self._apply_cyber_theme()
        else:
            self._apply_theme()
        for card in self._cards.values():
            card.set_cyber(self._cyber_mode)
        for row in self._app_rows.values():
            row.set_cyber(self._cyber_mode)
        if self._mic_row is not None:
            self._mic_row.set_cyber(self._cyber_mode)
        self._apply_window_height()

    def _apply_cyber_theme(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget {{
                font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
            }}
            QFrame#flyoutPanel {{
                background-color: {CyberTheme.BG};
                border: 1px solid {CyberTheme.CYAN};
                border-radius: 4px;
            }}
            QFrame#flyoutStrip {{
                background-color: rgba(0, 240, 255, 10);
                border: 1px solid rgba(0, 240, 255, 50);
                border-radius: 2px;
            }}
            QFrame#flyoutStrip[master="true"] {{
                background-color: rgba(0, 240, 255, 12);
                border: 1px solid rgba(0, 240, 255, 70);
                border-radius: 2px;
            }}
            QFrame#flyoutStrip[muted="true"] {{
                background-color: rgba(255, 45, 138, 22);
                border: 1px solid rgba(255, 45, 138, 80);
            }}
            QWidget#consoleAccentBar {{
                background-color: {CyberTheme.CYAN};
                border-radius: 0px;
            }}
            QLabel#consoleMasterIcon {{
                background-color: {CyberTheme.CYAN};
                border-radius: 0px;
            }}
            QWidget#sharedSourceRow {{
                background: transparent;
                border: none;
            }}
            QLabel#sharedSourceLabel {{
                color: {CyberTheme.CYAN};
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 1px;
                padding-left: 4px;
            }}
            QComboBox#deviceCombo {{
                background-color: rgba(0, 240, 255, 12);
                border: 1px solid rgba(0, 240, 255, 80);
                border-radius: 2px;
                color: {CyberTheme.CYAN};
                min-height: 24px;
                padding: 0 10px;
            }}
            QComboBox#deviceCombo:hover {{
                background-color: rgba(0, 240, 255, 22);
            }}
            QComboBox#deviceCombo::drop-down {{
                width: 0px;
                border: none;
            }}
            QComboBox#deviceCombo::down-arrow {{
                image: none;
                width: 0px;
                height: 0px;
            }}
            QLabel#flyoutCardTitle {{
                color: {CyberTheme.CYAN};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
            QLabel#flyoutValueLabel {{
                color: {CyberTheme.TEXT};
                font-size: 15px;
                font-weight: 400;
            }}
            QLabel#flyoutValueLabel[muted="true"] {{ color: {CyberTheme.PINK}; }}
            QFrame#appVolumeRow {{
                background-color: rgba(0, 240, 255, 12);
                border: 1px solid rgba(0, 240, 255, 45);
                border-radius: 2px;
            }}
            QFrame#appVolumeRow[muted="true"] {{
                background-color: rgba(255, 45, 120, 22);
                border: 1px solid {CyberTheme.PINK};
            }}
            QLabel#appRowName {{
                color: {CyberTheme.TEXT};
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }}
            QLabel#appRowValue {{
                color: rgba(0, 240, 255, 200);
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton#appRowMute {{
                background-color: rgba(0, 240, 255, 16);
                border: 1px solid rgba(0, 240, 255, 60);
                border-radius: 2px;
                font-size: 12px;
                padding: 0px;
            }}
            QPushButton#appRowMute:hover {{
                background-color: rgba(0, 240, 255, 34);
            }}
            QLabel#flyoutAppsLabel {{
                color: rgba(0, 240, 255, 140);
                font-size: 8px;
                font-weight: 600;
                letter-spacing: 1px;
            }}
            QLabel#flyoutStatusLabel {{
                color: rgba(0, 240, 255, 140);
                padding-left: 2px;
            }}
            QLabel#consoleBusLabel {{
                color: rgba(0, 240, 255, 110);
                font-size: 9px;
                letter-spacing: 1px;
            }}
            QComboBox#consoleDeviceCombo {{
                background-color: transparent;
                border: none;
                color: rgba(0, 240, 255, 110);
                font-size: 9px;
                padding: 0px 8px 0px 0px;
                min-height: 14px;
                max-height: 16px;
            }}
            QComboBox#consoleDeviceCombo::drop-down {{
                width: 0px;
                border: none;
            }}
            QComboBox#consoleDeviceCombo::down-arrow {{
                image: none;
                width: 0px;
                height: 0px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {CyberTheme.BG};
                border: 1px solid {CyberTheme.CYAN};
                border-radius: 2px;
                color: {CyberTheme.TEXT};
                outline: none;
                padding: 3px;
                selection-background-color: rgba(0, 240, 255, 40);
                selection-color: {CyberTheme.CYAN};
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 30px;
                padding: 0 10px;
                border-radius: 0px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: rgba(0, 240, 255, 18);
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: rgba(0, 240, 255, 40);
            }}
            QSlider#consoleSlider {{
                min-height: 18px;
                max-height: 18px;
            }}
            QSlider#consoleSlider::groove:horizontal {{
                background: rgba(0, 240, 255, 18);
                height: 5px;
                border-radius: 0px;
            }}
            QSlider#consoleSlider::sub-page:horizontal {{
                background: {CyberTheme.CYAN};
                border-radius: 0px;
            }}
            QSlider#consoleSlider[master="true"]::sub-page:horizontal {{
                background: {CyberTheme.CYAN};
            }}
            QSlider#consoleSlider::add-page:horizontal {{
                background: rgba(0, 240, 255, 18);
                border-radius: 0px;
            }}
            QSlider#consoleSlider::handle:horizontal {{
                background: {CyberTheme.CYAN};
                border: none;
                width: 8px;
                height: 8px;
                margin: -2px 0;
                border-radius: 0px;
            }}
            QSlider#consoleSlider[hovered="true"]::handle:horizontal {{
                background: {CyberTheme.CYAN};
                border: none;
                width: 10px;
                height: 10px;
                margin: -3px 0;
                border-radius: 0px;
            }}
            QSlider#consoleSlider[active="true"]::handle:horizontal {{
                background: #ffffff;
                border: none;
                width: 10px;
                height: 10px;
                margin: -3px 0;
                border-radius: 0px;
            }}
            QFrame#chipContainer {{
                background-color: transparent;
                border: none;
            }}
            QListWidget#channelChipList {{
                background: transparent;
                border: none;
                outline: none;
                padding: 0px;
                color: rgba(0, 240, 255, 160);
                font-size: 8px;
            }}
            QListWidget#channelChipList::item {{ padding: 0px; }}
            QWidget#flyoutHeader {{
                background: transparent;
                border: none;
            }}
            QLabel#flyoutHeaderTitle {{
                color: rgba(0, 240, 255, 140);
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.5px;
            }}
            QPushButton#flyoutCloseBtn {{
                background: transparent;
                border: none;
                color: rgba(0, 240, 255, 100);
                font-size: 18px;
                border-radius: 0px;
                padding: 0;
            }}
            QPushButton#flyoutCloseBtn:hover {{
                background: rgba(255, 45, 138, 22);
                color: {CyberTheme.PINK};
            }}
            QScrollArea#flyoutCardsScroll {{
                background: transparent;
                border: none;
            }}
            QScrollArea#flyoutCardsScroll > QWidget {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 4px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(0, 240, 255, 60);
                border-radius: 2px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(0, 240, 255, 100);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            """
        )

    def _apply_window_height(self) -> None:
        MAX_SCROLL_H = 430
        rows = list(self._cards.values())
        if rows:
            rows_h = sum(card.height() for card in rows) + max(0, len(rows) - 1) * 5
        else:
            rows_h = 58 if self._compact_mode else 74
        self._cards_scroll.setFixedHeight(min(rows_h, MAX_SCROLL_H))
        # Apps section: cap the scroll at 5 rows; past that it scrolls.
        app_rows = list(self._app_rows.values())
        if not self._apps_scroll.isHidden() and app_rows:
            gap = 4
            row_h = app_rows[0].sizeHint().height()
            total_h = sum(r.sizeHint().height() for r in app_rows) + max(0, len(app_rows) - 1) * gap
            max_visible = 5
            cap_h = max_visible * row_h + (max_visible - 1) * gap
            self._apps_scroll.setFixedHeight(min(total_h, cap_h) + 2)
        # Both scroll areas are now fixed-height, so the layout knows exactly how
        # much height every section needs — ask it instead of summing constants.
        # activate() first: the panel only recomputes its layout when the event
        # loop next runs, so without this the answer can still describe the rows
        # as they were before this refresh added or removed any.
        self._panel.layout().activate()
        new_height = self.layout().minimumSize().height()
        old_geo = self.geometry()
        height_changed = new_height != old_geo.height()
        self.setFixedHeight(new_height)
        # Keep the bottom edge anchored (grow upward) so the panel doesn't clip
        # off the bottom of the screen. Only when the height actually changed, and
        # never while the user is dragging the window, so it doesn't fight them.
        if height_changed and self.isVisible() and self._grow_upward and not self._user_dragging:
            bottom = old_geo.y() + old_geo.height()
            new_y = bottom - new_height
            screen = QGuiApplication.screenAt(old_geo.center()) or QGuiApplication.primaryScreen()
            if screen is not None:
                new_y = max(screen.availableGeometry().top() + 6, new_y)
            self.move(old_geo.x(), new_y)

    def set_battery(self, percent: int | None, charging: bool = False, headset_name: str = "") -> None:
        self._last_battery = (percent, charging, headset_name)
        self._update_shared_battery()

    def _update_shared_battery(self) -> None:
        percent, charging, headset_name = getattr(self, "_last_battery", (None, False, ""))
        selected = self._shared_combo.currentText()
        # Show only when the selected device matches the headset
        matches = headset_name and any(
            w in selected.lower()
            for w in headset_name.lower().split()
            if len(w) > 3
        )
        if not matches or percent is None or self._shared_row.isHidden():
            self._shared_battery_label.hide()
            return
        text = f"⚡ {percent}%" if charging else f"{percent}%"
        if percent < 25:
            color = "#ff4d4d"
        elif percent < 50:
            color = "#ffaa33"
        else:
            color = "#48efaa"
        self._shared_battery_label.setText(text)
        self._shared_battery_label.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {color};"
        )
        self._shared_battery_label.show()

    def set_logs_visible(self, visible: bool) -> None:
        self._status_label.setVisible(bool(visible))
        self._apply_window_height()

    def _refresh_apps_visibility(self) -> None:
        visible = bool(self._app_rows)
        self._apps_scroll.setVisible(visible)
        self._apps_section_label.setVisible(visible)

    def set_hidden_apps(self, hidden: list[tuple[str, str]]) -> None:
        """[(app key, label)] currently kept out of the mixer."""
        self._hidden_apps = list(hidden)
        # Hiding an app removes its row, so the header is the only thing left to
        # advertise the way back — otherwise the app is simply gone with no clue.
        count = len(self._hidden_apps)
        self._apps_section_label.setText(f"APPS · {count} HIDDEN" if count else "APPS")
        self._apps_section_label.setToolTip(
            "Right-click to restore hidden apps" if count else ""
        )

    def _show_hidden_apps_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        if not self._hidden_apps:
            empty = menu.addAction("No hidden apps")
            empty.setEnabled(False)
            menu.exec(self._apps_section_label.mapToGlobal(pos))
            return

        actions = {}
        for key, label in self._hidden_apps:
            actions[menu.addAction(f"Show {label}")] = key
        menu.addSeparator()
        show_all = menu.addAction("Show all")

        chosen = menu.exec(self._apps_section_label.mapToGlobal(pos))
        if chosen is None or self._on_unhide_app is None:
            return
        if chosen == show_all:
            for _, key in actions.items():
                self._on_unhide_app(key)
            return
        if chosen in actions:
            self._on_unhide_app(actions[chosen])

    def set_app_volumes(self, apps: list) -> None:
        """Populate the Sonar-independent per-app mixer. Empty list clears the apps."""
        if not apps:
            if self._app_rows:
                for row in self._app_rows.values():
                    self._apps_layout.removeWidget(row)
                    row.deleteLater()
                self._app_rows.clear()
                self._refresh_apps_visibility()
                self._apply_window_height()
            return

        incoming = {int(a.pid): a for a in apps}
        for pid in list(self._app_rows.keys()):
            if pid not in incoming:
                row = self._app_rows.pop(pid)
                self._apps_layout.removeWidget(row)
                row.deleteLater()
        for app in apps:
            pid = int(app.pid)
            row = self._app_rows.get(pid)
            if row is None:
                row = AppVolumeRow(
                    app,
                    self._on_app_volume_change,
                    self._on_app_toggle_mute,
                    cyber=self._cyber_mode,
                    on_hide=self._on_hide_app,
                )
                self._app_rows[pid] = row
                self._apps_layout.addWidget(row)
            else:
                row.update_from(app)
        self._refresh_apps_visibility()
        self._apply_window_height()

    def set_mic(self, state) -> None:
        """state = (volume:int, muted:bool) to show the mic section, or None to hide it."""
        if state is None:
            if self._mic_row is not None:
                self._mic_host_layout.removeWidget(self._mic_row)
                self._mic_row.deleteLater()
                self._mic_row = None
                self._mic_host.hide()
                self._apply_window_height()
            return
        desc = _MicDescriptor(volume=int(state[0]), muted=bool(state[1]))
        if self._mic_row is None:
            self._mic_row = AppVolumeRow(
                desc,
                lambda _pid, v: self._on_mic_volume_change(v) if self._on_mic_volume_change else None,
                lambda _pid: self._on_mic_toggle_mute() if self._on_mic_toggle_mute else None,
                cyber=self._cyber_mode,
                is_mic=True,
            )
            self._mic_host_layout.addWidget(self._mic_row)
            self._mic_host.show()
            self._apply_window_height()
        else:
            self._mic_row.update_from(desc)

    def set_app_levels(self, by_pid: dict) -> None:
        if not self._app_rows:
            return
        for pid, row in self._app_rows.items():
            row.set_level(float(by_pid.get(pid, 0.0)))

    def update_app_mute(self, pid: int, muted: bool) -> None:
        row = self._app_rows.get(int(pid))
        if row:
            row.set_muted(bool(muted))

    def update_mic_mute(self, muted: bool) -> None:
        if self._mic_row is not None:
            self._mic_row.set_muted(bool(muted))

    def set_app_sessions(self, sessions: list[tuple[str, str]]) -> None:
        self._pid_label = {pid: label for pid, label in sessions}

    def set_channel_apps(self, channel_apps: dict[str, list[tuple[str, ...]]]) -> None:
        self._channel_apps = {k: list(v) for k, v in channel_apps.items()}
        for key, apps in self._channel_apps.items():
            card = self._cards.get(key)
            if card:
                card.set_assigned_apps(apps)
        self._apply_window_height()

    def set_channel_levels(self, levels: dict[str, float]) -> None:
        for key, level in levels.items():
            card = self._cards.get(key)
            if card:
                card.set_audio_level(level)

    def _handle_route_drop(self, process_id: str, target_channel: str) -> None:
        pid = process_id.strip()
        if not pid:
            return
        self._move_app_locally(pid, target_channel)
        self._on_route_app(pid, target_channel)

    def _move_app_locally(self, process_id: str, target_channel: str) -> None:
        label = self._pid_label.get(process_id, f"pid:{process_id}")
        moving: tuple[str, ...] | None = None
        for key in ("game", "chatRender", "media"):
            kept: list[tuple[str, ...]] = []
            for item in self._channel_apps.get(key, []):
                if item and item[0] == process_id:
                    moving = item
                    continue
                kept.append(item)
            self._channel_apps[key] = kept
        if moving is None:
            moving = (process_id, label, label.lower(), "")
        self._channel_apps.setdefault(target_channel, []).append(moving)

        for key in ("game", "chatRender", "media"):
            card = self._cards.get(key)
            if card:
                card.set_assigned_apps(self._channel_apps.get(key, []))

    def is_visible(self) -> bool:
        return self.isVisible()

    def update_mute_state(self, channel_key: str, muted: bool) -> None:
        card = self._cards.get(channel_key)
        if card:
            card.set_muted(muted)

    def show_near(self, tray_rect: QRect | None) -> None:
        # Qt measures a widget only once its window is shown; anything built while
        # the flyout was closed (an app row from a background refresh, the mic
        # section) counts as empty until then. Measuring before show() therefore
        # reports a height far too short and the sections pile up on each other.
        # So show first — transparent, so nothing flashes at the stale position —
        # then measure, place, and reveal.
        self.setWindowOpacity(0.0)
        self.show()
        self._apply_window_height()
        if tray_rect is None or tray_rect.isNull():
            self._grow_upward = True
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                x = geo.right() - self.width() - 12
                y = geo.bottom() - self.height() - 12
                self.move(x, y)
        else:
            center = tray_rect.center()
            screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                x = tray_rect.right() - self.width()
                x = max(geo.left() + 6, min(x, geo.right() - self.width() - 6))
                y = tray_rect.top() - self.height() - 6
                if y < geo.top() + 6:
                    # No room above the tray — open below it and grow downward.
                    y = tray_rect.bottom() + 6
                    self._grow_upward = False
                else:
                    self._grow_upward = True
                y = max(geo.top() + 6, min(y, geo.bottom() - self.height() - 6))
                self.move(x, y)

        self.setWindowOpacity(1.0)
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def toggle_near(self, tray_rect: QRect | None) -> None:
        if self.isVisible():
            self.hide()
            return
        self.show_near(tray_rect)

    def nativeEvent(self, event_type, message) -> tuple:  # type: ignore[override]
        """Return HTCLIENT for all hit-tests to prevent transparent-area click-through."""
        if event_type == b"windows_generic_MSG":
            try:
                import ctypes.wintypes as wt
                msg = ctypes.cast(int(message), ctypes.POINTER(wt.MSG)).contents
                if msg.message == 0x0084:  # WM_NCHITTEST → HTCLIENT
                    return True, 1
            except Exception:
                pass
        return super().nativeEvent(event_type, message)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event) -> None:  # type: ignore[override]
        super().hideEvent(event)
        if self._on_hide:
            self._on_hide()

    def changeEvent(self, event) -> None:  # type: ignore[override]
        super().changeEvent(event)
        # Optional click-outside-to-close: hide when the window loses activation.
        if (
            self._close_on_outside
            and event.type() == QEvent.Type.ActivationChange
            and not self.isActiveWindow()
            and self.isVisible()
        ):
            self.hide()


class SettingsWindow(QDialog):
    def __init__(
        self,
        on_toggle_startup: Callable[[bool], None],
        on_toggle_compact: Callable[[bool], None],
        on_toggle_logs: Callable[[bool], None],
        config_path: str,
        on_toggle_cyber: Callable[[bool], None] | None = None,
        on_toggle_close_outside: Callable[[bool], None] | None = None,
        on_toggle_lock_position: Callable[[bool], None] | None = None,
    ) -> None:
        super().__init__(None)
        self._on_toggle_startup = on_toggle_startup
        self._on_toggle_compact = on_toggle_compact
        self._on_toggle_logs = on_toggle_logs
        self._on_toggle_cyber = on_toggle_cyber
        self._on_toggle_close_outside = on_toggle_close_outside
        self._on_toggle_lock_position = on_toggle_lock_position
        self._tab_buttons: dict[str, QPushButton] = {}
        self._cyber_theme = True
        self.setWindowTitle("SoundDeck Settings")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(600, 540)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("settingsShell")
        root.addWidget(shell)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        title_bar = QWidget()
        title_bar.setObjectName("settingsTitleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(14, 0, 6, 0)
        title_layout.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(FlyoutChannelStrip._build_master_icon().pixmap(16, 16))
        title_layout.addWidget(icon)
        title = QLabel("SoundDeck · Settings")
        title.setObjectName("settingsTitle")
        title_layout.addWidget(title)
        title_layout.addStretch(1)
        close = QPushButton("x")
        close.setObjectName("settingsClose")
        close.clicked.connect(self.close)
        title_layout.addWidget(close)
        shell_layout.addWidget(title_bar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        shell_layout.addWidget(body, 1)

        sidebar = QWidget()
        sidebar.setObjectName("settingsSidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)
        sidebar_layout.setSpacing(2)
        body_layout.addWidget(sidebar)

        self._stack = QStackedWidget()
        self._stack.setObjectName("settingsStack")
        body_layout.addWidget(self._stack, 1)

        self._startup = self._check("Launch at Windows startup", self._on_toggle_startup)
        self._compact = self._check("Use compact flyout", self._on_toggle_compact)
        self._logs = self._check("Show status line", self._on_toggle_logs)
        self._cyber = self._check("Cyberpunk theme", self._on_toggle_cyber or (lambda _: None))
        self._close_outside = self._check("Close on click outside", self._on_toggle_close_outside or (lambda _: None))
        self._lock_pos = self._check("Lock window position", self._on_toggle_lock_position or (lambda _: None))

        pages = [
            ("general", "General", self._general_page()),
            ("about", "About", self._about_page(config_path)),
        ]
        for index, (key, label, page) in enumerate(pages):
            button = QPushButton(label)
            button.setObjectName("settingsTab")
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, i=index, k=key: self._select_tab(i, k))
            sidebar_layout.addWidget(button)
            self._tab_buttons[key] = button
            self._stack.addWidget(page)
        sidebar_layout.addStretch(1)
        version = QLabel(f"v{__version__}")
        version.setObjectName("settingsVersion")
        sidebar_layout.addWidget(version)
        self._select_tab(0, "general")
        self._apply_settings_theme()

    def set_states(
        self,
        startup: bool,
        compact: bool,
        logs: bool,
        cyber: bool = False,
        close_outside: bool = False,
        lock_position: bool = False,
    ) -> None:
        for widget, value in (
            (self._startup, startup),
            (self._compact, compact),
            (self._logs, logs),
            (self._cyber, cyber),
            (self._close_outside, close_outside),
            (self._lock_pos, lock_position),
        ):
            widget.blockSignals(True)
            widget.setChecked(value)
            widget.blockSignals(False)
        if bool(cyber) != self._cyber_theme:
            self._cyber_theme = bool(cyber)
            self._apply_settings_theme()

    def show_window(self) -> None:
        _enable_windows_blur(int(self.winId()))
        self.show()
        self.raise_()
        self.activateWindow()

    def _general_page(self) -> QWidget:
        page = self._page("General")
        lay = page.layout()
        lay.addWidget(self._section("APPEARANCE"))
        lay.addWidget(self._row("Cyberpunk theme", "Neon glow aesthetic with angular HUD elements.", self._cyber))
        lay.addWidget(self._row("Compact view", "Use the smaller tray flyout layout.", self._compact))
        lay.addWidget(self._section("BEHAVIOR"))
        lay.addWidget(self._row("Close on click outside", "Hide the flyout when you click anywhere outside it.", self._close_outside))
        lay.addWidget(self._row("Lock window position", "Disable dragging the flyout by its title bar.", self._lock_pos))
        lay.addWidget(self._row("Status line", "Show connection and action messages under the mixer.", self._logs))
        lay.addWidget(self._section("SYSTEM"))
        lay.addWidget(self._row("Launch at Windows startup", "Start SoundDeck minimized to the tray on sign-in.", self._startup))
        lay.addStretch(1)
        return page

    def _section(self, text: str) -> QWidget:
        label = QLabel(text)
        label.setObjectName("settingsSectionLabel")
        return label

    def _about_page(self, config_path: str) -> QWidget:
        page = self._page("About")
        text = QLabel(
            "SoundDeck\n"
            "A compact tray mixer for Windows, with optional SteelSeries Sonar integration.\n\n"
            "When Sonar is running: full Game / Chat / Media channel mixer.\n"
            "When it isn't: Windows master, microphone, and a per-app volume mixer.\n\n"
            "Powered by Windows Core Audio (pycaw) and, when present, the Sonar local API.\n\n"
            f"Config:\n{config_path}"
        )
        text.setObjectName("settingsBodyText")
        text.setWordWrap(True)
        page.layout().addWidget(text)
        page.layout().addStretch(1)
        return page

    def _page(self, title: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(0)
        heading = QLabel(title)
        heading.setObjectName("settingsHeading")
        layout.addWidget(heading)
        return page

    def _row(self, label: str, hint: str, control: QWidget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(16)
        copy = QWidget()
        copy_layout = QVBoxLayout(copy)
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(2)
        title = QLabel(label)
        title.setObjectName("settingsRowTitle")
        sub = QLabel(hint)
        sub.setObjectName("settingsRowHint")
        sub.setWordWrap(True)
        copy_layout.addWidget(title)
        copy_layout.addWidget(sub)
        layout.addWidget(copy, 1)
        layout.addWidget(control)
        return row

    def _info_card(self, title: str, body: str) -> QWidget:
        card = QFrame()
        card.setObjectName("settingsInfoCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        heading = QLabel(title)
        heading.setObjectName("settingsRowTitle")
        text = QLabel(body)
        text.setObjectName("settingsRowHint")
        text.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(text)
        return card

    def _check(self, label: str, callback: Callable[[bool], None]) -> QCheckBox:
        box = QCheckBox()
        box.setObjectName("settingsToggle")
        box.setAccessibleName(label)
        box.setFixedSize(22, 22)
        box.toggled.connect(callback)
        return box

    def _select_tab(self, index: int, key: str) -> None:
        self._stack.setCurrentIndex(index)
        for tab_key, button in self._tab_buttons.items():
            button.setChecked(tab_key == key)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        drag_pos = getattr(self, "_drag_pos", None)
        if drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def _apply_settings_theme(self) -> None:
        self.setStyleSheet(self._cyber_settings_qss() if self._cyber_theme else self._standard_settings_qss())

    def _standard_settings_qss(self) -> str:
        return f"""
            QFrame#settingsShell {{
                background-color: rgba(18, 22, 32, 230);
                border: 1px solid rgba(255, 255, 255, 22);
                border-radius: 14px;
            }}
            QWidget#settingsTitleBar {{
                border-bottom: 1px solid rgba(255, 255, 255, 12);
                min-height: 34px;
                max-height: 34px;
            }}
            QLabel#settingsTitle {{
                color: {Theme.TEXT};
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#settingsClose {{
                background: transparent;
                border: none;
                color: {Theme.TEXT_MUTED};
                min-width: 40px;
                min-height: 28px;
                font-size: 14px;
            }}
            QPushButton#settingsClose:hover {{
                background-color: rgba(255, 111, 134, 70);
                color: {Theme.TEXT};
            }}
            QWidget#settingsSidebar {{
                border-right: 1px solid rgba(255, 255, 255, 12);
                min-width: 150px;
                max-width: 150px;
            }}
            QPushButton#settingsTab {{
                background: transparent;
                border: none;
                border-radius: 7px;
                color: {Theme.TEXT_MUTED};
                min-height: 34px;
                padding: 0 10px;
                text-align: left;
                font-weight: 600;
            }}
            QPushButton#settingsTab:checked {{
                background-color: rgba(255, 255, 255, 16);
                color: {Theme.TEXT};
                border-left: 2px solid {Theme.ACCENT};
            }}
            QLabel#settingsVersion,
            QLabel#settingsRowHint,
            QLabel#settingsBodyText {{
                color: {Theme.TEXT_MUTED};
                font-size: 11px;
            }}
            QLabel#settingsSectionLabel {{
                color: {Theme.TEXT_MUTED};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.4px;
                padding: 14px 0 2px 0;
            }}
            QLabel#settingsHeading {{
                color: {Theme.TEXT};
                font-size: 18px;
                font-weight: 700;
                padding-bottom: 6px;
            }}
            QLabel#settingsRowTitle {{
                color: {Theme.TEXT};
                font-size: 13px;
                font-weight: 600;
            }}
            QCheckBox#settingsToggle {{
                color: {Theme.TEXT};
                spacing: 0px;
            }}
            QCheckBox#settingsToggle::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                background-color: rgba(255,255,255,10);
                border: 1px solid rgba(255,255,255,42);
            }}
            QCheckBox#settingsToggle::indicator:checked {{
                background-color: {Theme.ACCENT};
                border: 1px solid {Theme.ACCENT};
            }}
            QCheckBox#settingsToggle::indicator:hover {{
                border: 1px solid rgba(255,255,255,70);
            }}
            """

    def _cyber_settings_qss(self) -> str:
        return f"""
            QWidget {{
                font-family: "Rajdhani", "Cascadia Code", "Consolas", "Courier New", monospace;
            }}
            QFrame#settingsShell {{
                background-color: {CyberTheme.PANEL_BG};
                border: 1px solid {CyberTheme.CYAN};
                border-radius: 3px;
            }}
            QWidget#settingsTitleBar {{
                border-bottom: 1px solid rgba(0, 240, 255, 60);
                min-height: 34px;
                max-height: 34px;
            }}
            QLabel#settingsTitle {{
                color: {CyberTheme.CYAN};
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 1.5px;
            }}
            QPushButton#settingsClose {{
                background: transparent;
                border: none;
                color: rgba(223, 250, 255, 150);
                min-width: 40px;
                min-height: 28px;
                font-size: 14px;
            }}
            QPushButton#settingsClose:hover {{
                background-color: rgba(255, 45, 138, 120);
                color: {CyberTheme.TEXT};
            }}
            QWidget#settingsSidebar {{
                border-right: 1px solid rgba(0, 240, 255, 60);
                min-width: 150px;
                max-width: 150px;
            }}
            QPushButton#settingsTab {{
                background: transparent;
                border: none;
                border-radius: 2px;
                color: rgba(223, 250, 255, 130);
                min-height: 34px;
                padding: 0 10px;
                text-align: left;
                font-weight: 600;
                letter-spacing: 1px;
            }}
            QPushButton#settingsTab:checked {{
                background-color: rgba(0, 240, 255, 26);
                color: {CyberTheme.CYAN};
                border-left: 2px solid {CyberTheme.CYAN};
            }}
            QLabel#settingsVersion {{
                color: rgba(0, 240, 255, 150);
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 1px;
            }}
            QLabel#settingsRowHint,
            QLabel#settingsBodyText {{
                color: rgba(223, 250, 255, 120);
                font-size: 11px;
            }}
            QLabel#settingsSectionLabel {{
                color: {CyberTheme.CYAN};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 2px;
                padding: 14px 0 2px 0;
            }}
            QLabel#settingsHeading {{
                color: {CyberTheme.TEXT};
                font-size: 17px;
                font-weight: 700;
                letter-spacing: 1.5px;
                padding-bottom: 6px;
            }}
            QLabel#settingsRowTitle {{
                color: {CyberTheme.TEXT};
                font-size: 13px;
                font-weight: 600;
            }}
            QCheckBox#settingsToggle {{
                color: {CyberTheme.TEXT};
                spacing: 0px;
            }}
            QCheckBox#settingsToggle::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 2px;
                background-color: rgba(0, 240, 255, 14);
                border: 1px solid rgba(0, 240, 255, 90);
            }}
            QCheckBox#settingsToggle::indicator:checked {{
                background-color: {CyberTheme.CYAN};
                border: 1px solid {CyberTheme.CYAN};
            }}
            QCheckBox#settingsToggle::indicator:hover {{
                border: 1px solid {CyberTheme.CYAN};
            }}
            """
