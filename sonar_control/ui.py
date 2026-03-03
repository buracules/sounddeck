from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import sys

from PySide6.QtCore import QEvent, QMimeData, QObject, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QFont, QFontMetrics, QGuiApplication, QPainter, QPen, QPixmap, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSlider,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionComboBox,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from .models import ChannelState


class Theme:
    BG = "#0b0f14"
    SURFACE = "#111722"
    CARD = "#131922"
    BORDER = "#1f2630"
    TEXT = "#e8eef7"
    TEXT_MUTED = "#9aa4b2"
    ACCENT = "#ffd400"
    TRACK = "#2a313d"
    TRACK_HOVER = "#333d4b"

    OUTER_PAD = 18
    CONTENT_MAX_WIDTH = 1260
    GAP_8 = 8
    GAP_16 = 16
    GAP_24 = 20


class _UiDispatcher(QObject):
    invoke = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.invoke.connect(self._run)

    def _run(self, callback: object) -> None:
        if callable(callback):
            callback()


class ModernSlider(QSlider):
    def __init__(self) -> None:
        super().__init__(Qt.Orientation.Vertical)
        self.setObjectName("modernSlider")
        self.setRange(0, 100)
        self.setSingleStep(1)
        self.setPageStep(5)
        self.setMinimumHeight(176)
        self.setMaximumHeight(280)
        self.setFixedWidth(44)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
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


class IconDeviceCombo(QComboBox):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("deviceComboCompact")
        self.setFixedWidth(34)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(1)
        self.setIconSize(QSize(16, 16))
        self._source_icon = self.build_source_icon()

    def showPopup(self) -> None:  # type: ignore[override]
        metrics = QFontMetrics(self.font())
        longest = 0
        for i in range(self.count()):
            longest = max(longest, metrics.horizontalAdvance(self.itemText(i)))
        # Ensure popup shows full output names even with icon-only collapsed control.
        popup_width = max(280, longest + 56)
        if self.view() is not None:
            self.view().setMinimumWidth(popup_width)
        super().showPopup()

    def source_icon(self) -> QIcon:
        return self._source_icon

    def paintEvent(self, event) -> None:  # type: ignore[override]
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        opt.currentText = ""
        opt.currentIcon = QIcon()
        painter = QPainter(self)
        try:
            self.style().drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt, painter, self)
            pm = self._source_icon.pixmap(14, 14)
            # Force a consistent white glyph tint regardless of source SVG color.
            tinted = QPixmap(pm.size())
            tinted.fill(Qt.GlobalColor.transparent)
            tp = QPainter(tinted)
            try:
                tp.drawPixmap(0, 0, pm)
                tp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                tp.fillRect(tinted.rect(), QColor("#e8eef7"))
            finally:
                tp.end()
            x = (self.width() - pm.width()) // 2
            y = (self.height() - pm.height()) // 2
            painter.drawPixmap(max(0, x), max(0, y), tinted)
        finally:
            painter.end()

    @staticmethod
    def build_source_icon() -> QIcon:
        candidates = [Path(__file__).resolve().parent / "assets" / "sound-source.svg"]
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(str(meipass)) / "sonar_control" / "assets" / "sound-source.svg")

        for svg_path in candidates:
            if svg_path.exists():
                icon = QIcon(str(svg_path))
                if not icon.isNull():
                    return icon

        size = 18
        px = QPixmap(size, size)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            c = QColor("#d7deea")
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(3, 7, 4, 4, 1.5, 1.5)
            p.drawPolygon([QPoint(7, 7), QPoint(10, 5), QPoint(10, 13), QPoint(7, 11)])
            pen = QPen(c, 1.4)
            p.setPen(pen)
            p.drawArc(9, 5, 6, 8, -35 * 16, 70 * 16)
            p.drawArc(10, 3, 8, 12, -35 * 16, 70 * 16)
        finally:
            p.end()
        return QIcon(px)


class ChipListWidget(QListWidget):
    def __init__(self, channel_key: str, on_route_app: Callable[[str, str], None]) -> None:
        super().__init__()
        self._channel_key = channel_key
        self._on_route_app = on_route_app
        self.setObjectName("channelChipList")
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setSpacing(4)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setItemDelegate(AppChipDelegate(self))

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self.itemAt(event.position().toPoint())
            if hit is not None:
                self.setCurrentItem(hit)
        super().mousePressEvent(event)

    def set_apps(self, apps: list[tuple[str, str]]) -> None:
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

        for process_id, label in apps:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, process_id)
            bg, border = self._chip_colors(label)
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

    def _chip_size_hint(self, label: str) -> QSize:
        metrics = QFontMetrics(QFont("Segoe UI", 9))
        text_w = metrics.horizontalAdvance(label.strip())
        max_w = max(64, self.viewport().width() - 8)
        width = min(max_w, max(40, text_w + 18))
        return QSize(width, 24)

    def _reflow_chip_widths(self) -> None:
        for i in range(self.count()):
            item = self.item(i)
            if item is None:
                continue
            item.setSizeHint(self._chip_size_hint(item.text()))

    @staticmethod
    def _chip_colors(label: str) -> tuple[QColor, QColor]:
        # Deterministic muted color per app name.
        seed = 0
        for ch in label.lower():
            seed = (seed * 131 + ord(ch)) & 0xFFFFFFFF
        hue = seed % 360
        bg = QColor.fromHsv(hue, 80, 55)
        border = QColor.fromHsv(hue, 95, 80)
        return bg, border


class AppChipDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index) -> None:  # type: ignore[override]
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        is_empty = bool(index.data(Qt.ItemDataRole.UserRole + 3))
        if is_empty:
            painter.save()
            painter.setPen(QColor("#9aa4b2"))
            painter.drawText(option.rect.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignCenter, text)
            painter.restore()
            return

        bg = index.data(Qt.ItemDataRole.UserRole + 1)
        border = index.data(Qt.ItemDataRole.UserRole + 2)
        bg_color = bg if isinstance(bg, QColor) else QColor("#212b37")
        border_color = border if isinstance(border, QColor) else QColor("#2a3442")

        rect = option.rect.adjusted(1, 2, -1, -2)
        radius = 10
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

        text_rect = rect.adjusted(8, 0, -6, 0)
        painter.setPen(QColor("#e8eef7"))
        elided = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)
        painter.restore()


class ChipContainer(QFrame):
    def __init__(self, channel_key: str, on_route_app: Callable[[str, str], None], height: int = 110) -> None:
        super().__init__()
        self._channel_key = channel_key
        self._on_route_app = on_route_app
        self._apps: list[tuple[str, str]] = []
        self.setObjectName("chipContainer")
        self.setAcceptDrops(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 4)
        root.setSpacing(0)

        self._chips = ChipListWidget(channel_key, on_route_app)
        self._chips.setMinimumHeight(height)
        self._chips.setMaximumHeight(height)
        root.addWidget(self._chips)

    def set_apps(self, apps: list[tuple[str, str]]) -> None:
        self._apps = list(apps)
        self._chips.set_apps(self._apps)

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


class ChannelCard(QFrame):
    SWITCHABLE_CHANNELS = {"game", "chatRender", "media"}

    def __init__(
        self,
        channel: ChannelState,
        on_volume_change: Callable[[str, int], None],
        on_toggle_mute: Callable[[str], None],
        on_toggle_all_mute: Callable[[], None],
        on_device_select: Callable[[str, str], None],
        on_route_app: Callable[[str, str], None],
        on_refresh_all: Callable[[], None],
        on_toggle_mode: Callable[[], None],
        compact: bool = False,
    ) -> None:
        super().__init__()
        self._channel_key = channel.key
        self._on_volume_change = on_volume_change
        self._on_toggle_mute = on_toggle_mute
        self._on_toggle_all_mute = on_toggle_all_mute
        self._on_device_select = on_device_select
        self._on_route_app = on_route_app
        self._on_refresh_all = on_refresh_all
        self._on_toggle_mode = on_toggle_mode
        self._compact = compact
        self._master_refresh_button = channel.key == "master"
        self._speaker_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)
        self._display_to_device_id: dict[str, str] = {}

        self.setObjectName("channelCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumWidth(150 if compact else 220)
        self.setMaximumWidth(180 if compact else 250)
        self.setMinimumHeight(320 if compact else 540)
        self.setProperty("dropHover", False)

        body = QVBoxLayout(self)
        body.setContentsMargins(10 if compact else 14, 10 if compact else 14, 10 if compact else 14, 10 if compact else 14)
        body.setSpacing(6 if compact else 8)

        title = QLabel(channel.label.upper())
        title.setObjectName("cardTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(title)

        self._device_combo = IconDeviceCombo() if compact else QComboBox()
        if not compact:
            self._device_combo.setObjectName("deviceCombo")
        self._device_combo.currentTextChanged.connect(self._on_device_changed)
        body.addWidget(self._device_combo)

        self._value_label = QLabel(f"{channel.volume}%")
        self._value_label.setObjectName("valueLabel")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(self._value_label)

        fader_wrap = QFrame()
        fader_wrap.setObjectName("faderWrap")
        fader_layout = QVBoxLayout(fader_wrap)
        fader_layout.setContentsMargins(0, 8, 0, 8)
        fader_layout.setSpacing(0)
        self._slider = ModernSlider()
        if compact:
            self._slider.setMinimumHeight(140)
            self._slider.setMaximumHeight(180)
        self._slider.setValue(channel.volume)
        self._slider.valueChanged.connect(self._on_slider_change)
        fader_layout.addWidget(self._slider, 0, Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(fader_wrap, 1)

        apps_label = QLabel("CURRENT APPS")
        apps_label.setObjectName("appsLabel")
        apps_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        body.addWidget(apps_label)

        self._apps_list = ChipContainer(self._channel_key, self._on_route_app)
        body.addWidget(self._apps_list)

        self._mute_button = QPushButton()
        self._mute_button.setObjectName("muteToggle")
        self._mute_button.setCheckable(True)
        self._mute_button.clicked.connect(self._on_mute_clicked)
        body.addWidget(self._mute_button)

        self._secondary_button = QPushButton()
        self._secondary_button.setObjectName("ghostButton")
        self._secondary_button.hide()
        body.addWidget(self._secondary_button)

        self._mode_button = QPushButton()
        self._mode_button.setObjectName("ghostButton")
        self._mode_button.hide()
        body.addWidget(self._mode_button)

        self.set_muted(channel.muted)
        if compact:
            apps_label.hide()
            self._apps_list.hide()
        if channel.key == "master":
            self._device_combo.hide()
            apps_label.hide()
            self._apps_list.hide()
            body.setStretchFactor(fader_wrap, 10 if compact else 12)
            self._slider.setMinimumHeight(250 if compact else 420)
            self._slider.setMaximumHeight(360 if compact else 640)
            self._mute_button.setCheckable(False)
            self._mute_button.setChecked(False)
            self._mute_button.setText("REFRESH ALL")
            self._mute_button.clicked.disconnect()
            self._mute_button.clicked.connect(self._on_refresh_all)
            self._mode_button.setText("FULL" if compact else "COMPACT")
            self._mode_button.clicked.connect(self._on_toggle_mode)
            self._mode_button.show()
            if not compact:
                self._secondary_button.setText("MUTE ALL")
                self._secondary_button.clicked.connect(self._on_toggle_all_mute)
                self._secondary_button.show()
        elif channel.key not in self.SWITCHABLE_CHANNELS:
            self._device_combo.setEnabled(False)
            self._device_combo.addItem("Not routable")
            self._apps_list.setEnabled(False)
            self._apps_list.set_apps([("", "Not routable")])
        else:
            self._device_combo.setEnabled(False)
            self._device_combo.addItem("Loading devices...")
            self._apps_list.set_apps([])
            if compact:
                self._mute_button.hide()

    def set_muted(self, muted: bool) -> None:
        if self._master_refresh_button:
            self._mute_button.blockSignals(True)
            self._mute_button.setCheckable(False)
            self._mute_button.setChecked(False)
            self._mute_button.setText("REFRESH ALL")
            self._mute_button.blockSignals(False)
            return
        self._mute_button.blockSignals(True)
        self._mute_button.setChecked(muted)
        self._mute_button.setText("MUTED" if muted else "LIVE")
        self._mute_button.blockSignals(False)

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

        self._display_to_device_id = {name: dev_id for dev_id, name in options}
        labels = list(self._display_to_device_id.keys())

        self._device_combo.blockSignals(True)
        self._device_combo.clear()
        if not labels:
            if self._compact:
                self._device_combo.addItem("No active device")
            else:
                self._device_combo.addItem("No active device")
            self._device_combo.setEnabled(False)
        else:
            if self._compact:
                self._device_combo.addItems(labels)
            else:
                self._device_combo.addItems(labels)
            selected = next((name for dev_id, name in options if dev_id == current_device_id), labels[0])
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

    def _on_slider_change(self, value: int) -> None:
        self._value_label.setText(f"{value}%")
        self._on_volume_change(self._channel_key, int(value))

    def _on_mute_clicked(self) -> None:
        self._on_toggle_mute(self._channel_key)

    def _on_device_changed(self, text: str) -> None:
        self._device_combo.setToolTip(text)
        device_id = self._display_to_device_id.get(text)
        if device_id:
            self._on_device_select(self._channel_key, device_id)

    def set_assigned_apps(self, apps: list[tuple[str, str]]) -> None:
        self._apps_list.set_apps(apps)

    def set_volume_value(self, value: int) -> None:
        value = max(0, min(100, int(value)))
        self._slider.blockSignals(True)
        self._slider.setValue(value)
        self._slider.blockSignals(False)
        self._value_label.setText(f"{value}%")


class FlyoutChannelStrip(QFrame):
    SWITCHABLE_CHANNELS = {"game", "chatRender", "media"}

    def __init__(
        self,
        channel: ChannelState,
        on_volume_change: Callable[[str, int], None],
        on_toggle_mute: Callable[[str], None],
        on_device_select: Callable[[str, str], None],
        on_route_app: Callable[[str, str], None],
    ) -> None:
        super().__init__()
        self._channel_key = channel.key
        self._on_volume_change = on_volume_change
        self._on_toggle_mute = on_toggle_mute
        self._on_device_select = on_device_select
        self._on_route_app = on_route_app
        self._display_to_device_id: dict[str, str] = {}
        self._shared_output_mode = False

        self.setObjectName("flyoutStrip")
        self.setFrameShape(QFrame.Shape.NoFrame)
        if channel.key == "master":
            self.setMinimumWidth(128)
            self.setMaximumWidth(146)
        else:
            self.setMinimumWidth(150)
            self.setMaximumWidth(172)
        self.setFixedHeight(432)

        body = QVBoxLayout(self)
        body.setContentsMargins(7, 8, 7, 4)
        body.setSpacing(3)

        title = QLabel(channel.label.upper())
        title.setObjectName("flyoutCardTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(title)

        self._device_combo = IconDeviceCombo()
        self._source_icon = self._device_combo.source_icon()
        self._device_combo.currentTextChanged.connect(self._on_device_changed)
        body.addWidget(self._device_combo, 0, Qt.AlignmentFlag.AlignHCenter)

        self._value_label = QLabel(f"{channel.volume}%")
        self._value_label.setObjectName("flyoutValueLabel")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(self._value_label)

        self._slider = ModernSlider()
        self._slider.setMinimumHeight(176)
        self._slider.setMaximumHeight(248)
        self._slider.setProperty("master", channel.key not in self.SWITCHABLE_CHANNELS)
        self._slider.setValue(channel.volume)
        self._slider.valueChanged.connect(self._on_slider_change)
        body.addWidget(self._slider, 1, Qt.AlignmentFlag.AlignHCenter)
        body.setStretchFactor(self._slider, 1)
        self._post_slider_gap = QWidget()
        self._post_slider_gap.setFixedHeight(0)
        body.addWidget(self._post_slider_gap)

        self._apps_section = QWidget()
        apps_layout = QVBoxLayout(self._apps_section)
        apps_layout.setContentsMargins(2, 0, 2, 0)
        apps_layout.setSpacing(0)

        self._apps_list = ChipContainer(self._channel_key, self._on_route_app, height=74)
        self._apps_list.setMinimumHeight(66)
        self._apps_list.setMaximumHeight(82)
        apps_layout.addWidget(self._apps_list)

        body.addWidget(self._apps_section)
        self._pre_button_gap = QWidget()
        self._pre_button_gap.setFixedHeight(8)
        body.addWidget(self._pre_button_gap)

        self._mute_button = QPushButton()
        self._mute_button.setObjectName("flyoutMuteButton")
        self._mute_button.setCheckable(True)
        self._mute_button.clicked.connect(self._on_mute_clicked)
        body.addWidget(self._mute_button)

        self.set_muted(channel.muted)
        if channel.key not in self.SWITCHABLE_CHANNELS:
            body.setContentsMargins(7, 8, 7, 4)
            self._device_combo.hide()
            self._apps_section.hide()
            self._slider.setMinimumHeight(232)
            self._slider.setMaximumHeight(380)
            self._post_slider_gap.setFixedHeight(8)
            self._pre_button_gap.setFixedHeight(0)
        else:
            self._post_slider_gap.setFixedHeight(6)
            self._pre_button_gap.setFixedHeight(8)
            self._device_combo.setEnabled(False)
            self._device_combo.addItem("Loading")

    def set_muted(self, muted: bool) -> None:
        self._mute_button.blockSignals(True)
        self._mute_button.setChecked(muted)
        self._mute_button.setText("MUTE" if muted else "LIVE")
        self._mute_button.blockSignals(False)

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
        self._display_to_device_id = {name: dev_id for dev_id, name in options}
        labels = list(self._display_to_device_id.keys())

        self._device_combo.blockSignals(True)
        self._device_combo.clear()
        if not labels:
            self._device_combo.addItem("No device")
            self._device_combo.setEnabled(False)
        else:
            self._device_combo.addItems(labels)
            selected = next((name for dev_id, name in options if dev_id == current_device_id), labels[0])
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
        self._apps_list.set_apps(apps)

    def set_volume_value(self, value: int) -> None:
        value = max(0, min(100, int(value)))
        self._slider.blockSignals(True)
        self._slider.setValue(value)
        self._slider.blockSignals(False)
        self._value_label.setText(f"{value}%")

    def _on_slider_change(self, value: int) -> None:
        self._value_label.setText(f"{value}%")
        self._on_volume_change(self._channel_key, int(value))

    def _on_mute_clicked(self) -> None:
        self._on_toggle_mute(self._channel_key)

    def _on_device_changed(self, text: str) -> None:
        self._device_combo.setToolTip(text)
        device_id = self._display_to_device_id.get(text)
        if device_id:
            self._on_device_select(self._channel_key, device_id)

    def set_compact(self, compact: bool) -> None:
        _ = compact
        # Single flyout mode; keep stable geometry.
        self._slider.setMinimumHeight(120)
        self._slider.setMaximumHeight(170)

    def set_shared_output_mode(self, enabled: bool) -> None:
        self._shared_output_mode = bool(enabled)
        if self._channel_key not in self.SWITCHABLE_CHANNELS:
            return
        self._device_combo.setVisible(not self._shared_output_mode)


class FlyoutMixerWindow(QWidget):
    def __init__(
        self,
        on_refresh: Callable[[], None],
        on_volume_change: Callable[[str, int], None],
        on_toggle_mute: Callable[[str], None],
        on_device_select: Callable[[str, str], None],
        on_route_app: Callable[[str, str], None],
    ) -> None:
        super().__init__(None)
        self.setWindowTitle("Sonar Mixer Flyout")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(720)
        self.setMaximumWidth(780)

        self._on_refresh = on_refresh
        self._on_volume_change = on_volume_change
        self._on_toggle_mute = on_toggle_mute
        self._on_device_select = on_device_select
        self._on_route_app = on_route_app

        self._cards: dict[str, FlyoutChannelStrip] = {}
        self._channel_apps: dict[str, list[tuple[str, str]]] = {"game": [], "chatRender": [], "media": []}
        self._pid_label: dict[str, str] = {}
        self._shared_display_to_device_id: dict[str, str] = {}
        self._shared_source_channel_key = "game"
        self._dispatcher = _UiDispatcher()
        self._outside_filter_installed = False

        self._build_ui()
        self._apply_theme()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(0)

        self._panel = QFrame()
        self._panel.setObjectName("flyoutPanel")
        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        panel_layout.setSpacing(6)

        self._shared_row = QWidget()
        self._shared_row.setObjectName("sharedSourceRow")
        shared_layout = QHBoxLayout(self._shared_row)
        shared_layout.setContentsMargins(2, 0, 2, 0)
        shared_layout.setSpacing(6)
        self._shared_label = QLabel("SOURCE")
        self._shared_label.setObjectName("sharedSourceLabel")
        self._shared_combo = QComboBox()
        self._shared_combo.setObjectName("deviceCombo")
        self._shared_combo.setMinimumWidth(300)
        self._shared_combo.currentTextChanged.connect(self._on_shared_device_changed)
        shared_layout.addWidget(self._shared_label)
        shared_layout.addWidget(self._shared_combo, 1)
        self._shared_row.hide()
        panel_layout.addWidget(self._shared_row)

        cards_host = QWidget()
        self._cards_layout = QHBoxLayout(cards_host)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(6)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        panel_layout.addWidget(cards_host)

        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("flyoutStatusLabel")
        self._status_label.setFont(QFont("Segoe UI", 8))
        panel_layout.addWidget(self._status_label)
        self._status_label.hide()
        root.addWidget(self._panel)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 180))
        self._panel.setGraphicsEffect(shadow)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            f"""
            QFrame#flyoutPanel {{
                background-color: rgba(20, 24, 30, 232);
                border: 1px solid rgba(80, 90, 105, 150);
                border-radius: 14px;
            }}
            QFrame#flyoutStrip {{
                background-color: rgba(34, 39, 48, 210);
                border: 1px solid rgba(70, 78, 92, 170);
                border-radius: 10px;
            }}
            QWidget#sharedSourceRow {{
                background: transparent;
            }}
            QLabel#sharedSourceLabel {{
                color: {Theme.TEXT_MUTED};
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 1px;
                padding-left: 2px;
            }}
            QComboBox#deviceCombo {{
                background-color: rgba(35, 41, 51, 220);
                border: 1px solid rgba(86, 95, 112, 190);
                border-radius: 6px;
                color: {Theme.TEXT};
                min-height: 24px;
                padding: 0 8px;
            }}
            QLabel#flyoutCardTitle {{
                color: {Theme.TEXT};
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 1px;
            }}
            QLabel#flyoutValueLabel {{
                color: {Theme.ACCENT};
                font-size: 18px;
                font-weight: 700;
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
            QPushButton#flyoutMuteButton {{
                background-color: rgba(58, 64, 76, 232);
                border: 1px solid rgba(98, 109, 128, 210);
                border-radius: 6px;
                color: {Theme.TEXT};
                min-height: 24px;
                font-size: 9px;
                font-weight: 600;
            }}
            QPushButton#flyoutMuteButton:hover {{
                background-color: rgba(70, 76, 90, 236);
                border: 1px solid rgba(118, 130, 151, 220);
            }}
            QPushButton#flyoutMuteButton:checked {{
                background-color: {Theme.ACCENT};
                border-color: {Theme.ACCENT};
                color: #11151d;
            }}
            QComboBox#deviceComboCompact {{
                background-color: rgba(35, 41, 51, 220);
                border: 1px solid rgba(86, 95, 112, 190);
                border-radius: 6px;
                color: transparent;
                min-height: 24px;
                min-width: 34px;
                max-width: 34px;
                padding-left: 8px;
                padding-right: 0px;
            }}
            QComboBox#deviceComboCompact::drop-down {{
                width: 0px;
                border: none;
            }}
            QComboBox#deviceComboCompact::down-arrow {{
                image: none;
                width: 0px;
                height: 0px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #171c24;
                border: 1px solid #2d3644;
                color: {Theme.TEXT};
                selection-background-color: #2a3342;
                selection-color: {Theme.TEXT};
            }}
            QSlider#modernSlider {{
                min-width: 34px;
                max-width: 34px;
                min-height: 176px;
                max-height: 248px;
            }}
            QSlider#modernSlider[master="true"] {{
                min-height: 232px;
                max-height: 380px;
            }}
            QSlider#modernSlider::groove:vertical {{
                background: #364152;
                width: 12px;
                border-radius: 6px;
            }}
            QSlider#modernSlider::sub-page:vertical {{
                background: #3f4a5c;
                border-radius: 6px;
            }}
            QSlider#modernSlider::add-page:vertical {{
                background: #ffd400;
                border-radius: 6px;
            }}
            QSlider#modernSlider::handle:vertical {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:0.55 #f2f5fc, stop:1 #dbe2ef);
                border: 2px solid #d8c355;
                width: 18px;
                height: 18px;
                margin: 0 -8px;
                border-radius: 9px;
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
            )
            self._cards_layout.addWidget(card, 1)
            self._cards[channel.key] = card

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
        for card in self._cards.values():
            card.set_shared_output_mode(True)

    def _on_shared_device_changed(self, text: str) -> None:
        self._shared_combo.setToolTip(text)
        device_id = self._shared_display_to_device_id.get(text)
        if device_id:
            self._on_device_select(self._shared_source_channel_key, device_id)

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

    def set_logs_visible(self, visible: bool) -> None:
        self._status_label.setVisible(bool(visible))

    def set_app_sessions(self, sessions: list[tuple[str, str]]) -> None:
        self._pid_label = {pid: label for pid, label in sessions}

    def set_channel_apps(self, channel_apps: dict[str, list[tuple[str, str]]]) -> None:
        self._channel_apps = {k: list(v) for k, v in channel_apps.items()}
        for key, apps in self._channel_apps.items():
            card = self._cards.get(key)
            if card:
                card.set_assigned_apps(apps)

    def _handle_route_drop(self, process_id: str, target_channel: str) -> None:
        pid = process_id.strip()
        if not pid:
            return
        self._move_app_locally(pid, target_channel)
        self._on_route_app(pid, target_channel)

    def _move_app_locally(self, process_id: str, target_channel: str) -> None:
        label = self._pid_label.get(process_id, f"pid:{process_id}")
        for key in ("game", "chatRender", "media"):
            self._channel_apps[key] = [item for item in self._channel_apps.get(key, []) if item[0] != process_id]
        self._channel_apps.setdefault(target_channel, []).append((process_id, label))

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
        self.adjustSize()
        if tray_rect is None or tray_rect.isNull():
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
                    y = tray_rect.bottom() + 6
                y = max(geo.top() + 6, min(y, geo.bottom() - self.height() - 6))
                self.move(x, y)

        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self._install_outside_filter()

    def toggle_near(self, tray_rect: QRect | None) -> None:
        if self.isVisible():
            self.hide()
            return
        self.show_near(tray_rect)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event) -> None:  # type: ignore[override]
        super().hideEvent(event)
        self._remove_outside_filter()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is QApplication.instance() and self.isVisible():
            popup = QApplication.activePopupWidget()
            if popup is not None:
                return super().eventFilter(watched, event)
            if event.type() == QEvent.Type.MouseButtonPress:
                pos = event.globalPosition().toPoint()  # type: ignore[attr-defined]
                if not self.frameGeometry().contains(pos):
                    self.hide()
        return super().eventFilter(watched, event)

    def _install_outside_filter(self) -> None:
        app = QApplication.instance()
        if app is None or self._outside_filter_installed:
            return
        app.installEventFilter(self)
        self._outside_filter_installed = True

    def _remove_outside_filter(self) -> None:
        app = QApplication.instance()
        if app is None or not self._outside_filter_installed:
            return
        app.removeEventFilter(self)
        self._outside_filter_installed = False

class ControlWindow(QMainWindow):
    def __init__(
        self,
        on_refresh: Callable[[], None],
        on_volume_change: Callable[[str, int], None],
        on_toggle_mute: Callable[[str], None],
        on_toggle_all_mute: Callable[[], None],
        on_device_select: Callable[[str, str], None],
        on_route_app: Callable[[str, str], None],
        compact_mode: bool = True,
    ) -> None:
        super().__init__()
        self._compact_mode = compact_mode
        self.setWindowTitle("Sonar Mixer")

        self._on_refresh = on_refresh
        self._on_volume_change = on_volume_change
        self._on_toggle_mute = on_toggle_mute
        self._on_toggle_all_mute = on_toggle_all_mute
        self._on_device_select = on_device_select
        self._on_route_app = on_route_app
        self._cards: dict[str, ChannelCard] = {}
        self._channel_apps: dict[str, list[tuple[str, str]]] = {"game": [], "chatRender": [], "media": []}
        self._pid_label: dict[str, str] = {}
        self._last_channels: list[ChannelState] = []
        self._device_cache: dict[str, tuple[list[tuple[str, str]], str | None, bool, str | None]] = {}
        self._force_rebuild = False
        self._dispatcher = _UiDispatcher()

        self._build_ui()
        self._apply_window_mode()
        self._apply_theme()

    def dispatch(self, callback: Callable[[], None]) -> None:
        self._dispatcher.invoke.emit(callback)

    def set_channels(self, channels: list[ChannelState]) -> None:
        self._last_channels = list(channels)
        incoming_keys = [c.key for c in channels]
        existing_keys = list(self._cards.keys())

        if not self._force_rebuild and existing_keys and set(existing_keys) == set(incoming_keys):
            for channel in channels:
                card = self._cards.get(channel.key)
                if not card:
                    continue
                card.set_volume_value(channel.volume)
                card.set_muted(channel.muted)
            return

        self._force_rebuild = False
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._cards.clear()
        self._cards_layout.addStretch(1)
        for channel in channels:
            card = ChannelCard(
                channel=channel,
                on_volume_change=self._on_volume_change,
                on_toggle_mute=self._on_toggle_mute,
                on_toggle_all_mute=self._on_toggle_all_mute,
                on_device_select=self._on_device_select,
                on_route_app=self._handle_route_drop,
                on_refresh_all=self._on_refresh,
                on_toggle_mode=self._toggle_mode,
                compact=self._compact_mode,
            )
            self._cards_layout.addWidget(card, 0)
            self._cards[channel.key] = card
        self._cards_layout.addStretch(1)

        # Re-apply cached device choices and channel apps after rebuild.
        for key, (options, current, linked, reason) in self._device_cache.items():
            self.set_device_choices(key, options, current, linked=linked, disabled_reason=reason)
        self.set_channel_apps(self._channel_apps)

    def set_device_choices(
        self,
        channel_key: str,
        options: list[tuple[str, str]],
        current_device_id: str | None,
        editable: bool = True,
        disabled_reason: str | None = None,
        linked: bool = False,
    ) -> None:
        self._device_cache[channel_key] = (list(options), current_device_id, linked, disabled_reason)
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
        _ = options
        _ = current_device_id
        _ = channel_key

    def set_status(self, status: str) -> None:
        self._status_label.setText(status)

    def set_logs_visible(self, visible: bool) -> None:
        _ = visible

    def set_logs_visible(self, visible: bool) -> None:
        self._status_label.setVisible(bool(visible))

    def set_app_sessions(self, sessions: list[tuple[str, str]]) -> None:
        self._pid_label = {pid: label for pid, label in sessions}

    def set_channel_apps(self, channel_apps: dict[str, list[tuple[str, str]]]) -> None:
        self._channel_apps = self._normalize_channel_apps(channel_apps)
        for key, apps in channel_apps.items():
            card = self._cards.get(key)
            if card:
                card.set_assigned_apps(self._channel_apps.get(key, []))

    def _handle_route_drop(self, process_id: str, target_channel: str) -> None:
        pid = process_id.strip()
        if not pid:
            return
        self._move_app_locally(pid, target_channel)
        self._on_route_app(pid, target_channel)

    def _move_app_locally(self, process_id: str, target_channel: str) -> None:
        label = self._pid_label.get(process_id, f"pid:{process_id}")

        for key in ("game", "chatRender", "media"):
            current = self._channel_apps.get(key, [])
            self._channel_apps[key] = [
                item for item in current if item[0] != process_id and item[1].strip().lower() != label.strip().lower()
            ]

        target = self._channel_apps.setdefault(target_channel, [])
        if not any(item[0] == process_id or item[1].strip().lower() == label.strip().lower() for item in target):
            target.append((process_id, label))

        for key in ("game", "chatRender", "media"):
            card = self._cards.get(key)
            if card:
                card.set_assigned_apps(self._channel_apps.get(key, []))

    @staticmethod
    def _normalize_channel_apps(channel_apps: dict[str, list[tuple[str, str]]]) -> dict[str, list[tuple[str, str]]]:
        normalized: dict[str, list[tuple[str, str]]] = {}
        for key in ("game", "chatRender", "media"):
            out: list[tuple[str, str]] = []
            seen_pid: set[str] = set()
            seen_label: set[str] = set()
            for pid, label in channel_apps.get(key, []):
                p = str(pid).strip()
                l = str(label).strip()
                if not p or not l:
                    continue
                lk = l.lower()
                if p in seen_pid or lk in seen_label:
                    continue
                seen_pid.add(p)
                seen_label.add(lk)
                out.append((p, l))
            normalized[key] = out
        return normalized

    def is_visible(self) -> bool:
        return self.isVisible()

    def update_mute_state(self, channel_key: str, muted: bool) -> None:
        card = self._cards.get(channel_key)
        if card:
            card.set_muted(muted)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)

        center_layout = QHBoxLayout(root)
        center_layout.setContentsMargins(Theme.OUTER_PAD, Theme.OUTER_PAD, Theme.OUTER_PAD, Theme.OUTER_PAD)
        center_layout.setSpacing(0)
        center_layout.addStretch(1)

        content = QWidget()
        content.setObjectName("contentRoot")
        content.setMaximumWidth(Theme.CONTENT_MAX_WIDTH)
        content_col = QVBoxLayout(content)
        content_col.setContentsMargins(0, 0, 0, 0)
        content_col.setSpacing(8)
        center_layout.addWidget(content, 1)
        center_layout.addStretch(1)

        cards_host = QWidget()
        cards_host.setObjectName("cardsHost")
        self._cards_layout = QHBoxLayout(cards_host)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(4)
        content_col.addWidget(cards_host, 1)

        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setFont(QFont("Segoe UI", 9))
        content_col.addWidget(self._status_label)

    def _apply_window_mode(self) -> None:
        if self._compact_mode:
            self.setFixedSize(700, 490)
        else:
            self.setFixedSize(960, 760)

    def _toggle_mode(self) -> None:
        self._compact_mode = not self._compact_mode
        self._apply_window_mode()
        self._force_rebuild = True
        if self._last_channels:
            self.set_channels(self._last_channels)
        self._apply_theme()

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget#appRoot {{
                background-color: #1f1f1f;
                color: {Theme.TEXT};
            }}
            QWidget#cardsHost {{
                background: transparent;
                border: none;
            }}
            QLabel#appTitle {{
                color: #f0f0f0;
                letter-spacing: 0.6px;
            }}
            QLabel#appSubtitle {{
                color: {Theme.TEXT_MUTED};
                padding-top: 6px;
            }}
            QLabel#statusLabel {{
                color: {Theme.TEXT_MUTED};
                padding-left: 4px;
            }}
            QLabel#sectionTitle {{
                color: {Theme.TEXT_MUTED};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1.0px;
            }}
            QLabel#sectionSubtitle {{
                color: {Theme.TEXT_MUTED};
                font-size: 10px;
                padding-bottom: 2px;
            }}
            QLabel#routeLabel {{
                color: {Theme.TEXT_MUTED};
                font-size: 10px;
                padding-right: 4px;
            }}
            QFrame#channelCard {{
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
            }}
            QFrame#faderWrap {{
                background-color: transparent;
                border: none;
            }}
            QLabel#cardTitle {{
                color: #d4dbe6;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 1.4px;
            }}
            QLabel#appsLabel {{
                color: {Theme.TEXT_MUTED};
                font-size: 9px;
                font-weight: 600;
                letter-spacing: 1.1px;
                padding-top: 2px;
            }}
            QLabel#valueLabel {{
                color: {Theme.ACCENT};
                font-size: 20px;
                font-weight: 700;
                padding-bottom: 2px;
            }}
            QPushButton#ghostButton,
            QPushButton#muteToggle {{
                background-color: #313131;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                color: {Theme.TEXT};
                font-size: 10px;
                font-weight: 600;
                min-height: 30px;
                padding: 0 12px;
            }}
            QPushButton#ghostButton:hover,
            QPushButton#muteToggle:hover {{
                border: 1px solid #3a4658;
                background-color: #202a38;
            }}
            QPushButton#muteToggle:checked {{
                background-color: {Theme.ACCENT};
                border: 1px solid {Theme.ACCENT};
                color: #11151d;
            }}
            QPushButton#primaryButton {{
                background-color: {Theme.ACCENT};
                border: 1px solid {Theme.ACCENT};
                border-radius: 11px;
                color: #10141c;
                font-size: 11px;
                font-weight: 700;
                min-height: 36px;
                min-width: 100px;
            }}
            QPushButton#primaryButton:hover {{
                background-color: #ffe049;
                border: 1px solid #ffe049;
            }}
            QPushButton#primaryButton:disabled {{
                background-color: #2a313d;
                border: 1px solid #2a313d;
                color: #7c8796;
            }}
            QComboBox#deviceCombo,
            QComboBox#sessionCombo,
            QComboBox#roleCombo {{
                background-color: #252525;
                border: 1px solid #454545;
                border-radius: 6px;
                color: {Theme.TEXT};
                min-height: 30px;
                padding: 0 8px;
            }}
            QComboBox#deviceCombo:hover,
            QComboBox#sessionCombo:hover,
            QComboBox#roleCombo:hover {{
                border: 1px solid #3a4658;
            }}
            QComboBox#deviceComboCompact {{
                background-color: #252525;
                border: 1px solid #454545;
                border-radius: 6px;
                color: transparent;
                min-height: 30px;
                min-width: 40px;
                max-width: 40px;
                padding: 0px;
            }}
            QComboBox#deviceComboCompact:hover {{
                border: 1px solid #5c5c5c;
            }}
            QComboBox#deviceComboCompact:focus {{
                border: 1px solid {Theme.ACCENT};
            }}
            QComboBox#deviceCombo:focus,
            QComboBox#sessionCombo:focus,
            QComboBox#roleCombo:focus {{
                border: 1px solid {Theme.ACCENT};
            }}
            QComboBox#deviceCombo QLineEdit {{
                background: transparent;
                border: none;
                color: {Theme.TEXT};
                padding-left: 0px;
                selection-background-color: transparent;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 26px;
            }}
            QComboBox#deviceComboCompact::drop-down {{
                width: 0px;
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: #151c26;
                border: 1px solid {Theme.BORDER};
                color: {Theme.TEXT};
                selection-background-color: {Theme.ACCENT};
                selection-color: #11151d;
            }}
            QFrame#chipContainer {{
                background-color: #1f2732;
                border: 1px solid #334051;
                border-radius: 8px;
            }}
            QLabel#chipEmptyLabel {{
                color: {Theme.TEXT_MUTED};
                font-size: 10px;
                padding: 8px 4px;
            }}
            QListWidget#channelChipList {{
                background: transparent;
                border: none;
                outline: none;
                padding: 2px;
                color: {Theme.TEXT};
                font-size: 10px;
            }}
            QListWidget#channelChipList::item {{ padding: 0px; }}
            QSlider#modernSlider {{
                min-width: 44px;
                max-width: 44px;
                min-height: 140px;
                max-height: 640px;
            }}
            QSlider#modernSlider::groove:vertical {{
                background: #1e2733;
                width: 16px;
                border-radius: 8px;
            }}
            QSlider#modernSlider[hovered="true"]::groove:vertical {{
                background: {Theme.TRACK_HOVER};
            }}
            QSlider#modernSlider::sub-page:vertical {{
                background: {Theme.ACCENT};
                border-radius: 8px;
            }}
            QSlider#modernSlider::add-page:vertical {{
                background: #1e2733;
                border-radius: 8px;
            }}
            QSlider#modernSlider::handle:vertical {{
                background: #f4f7ff;
                border: 2px solid {Theme.ACCENT};
                width: 22px;
                height: 22px;
                margin: 0 -11px;
                border-radius: 11px;
            }}
            QSlider#modernSlider[active="true"]::handle:vertical {{
                background: #ffffff;
                border: 2px solid #ffe34f;
            }}
            """
        )
