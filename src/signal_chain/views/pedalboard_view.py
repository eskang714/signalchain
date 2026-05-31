from __future__ import annotations

from PyQt6.QtCore import Qt, QLineF, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from signal_chain.viewmodels.pedalboard import LedStatus, PedalModule, PedalboardViewModel

# Per-module color palette: (body_hex, plate_hex, accent_hex)
_COLORS: dict[str, tuple[str, str, str]] = {
    "conv_history": ("#1a3a5c", "#0c1e36", "#7ab8e8"),
    "connected":    ("#3a1a1a", "#1e0808", "#e88a8a"),
    "markdown":     ("#2a2800", "#141200", "#e0d800"),
    "web_access":   ("#1a3020", "#0a1a10", "#4ab880"),
    "file_access":  ("#1a2a3a", "#0a1820", "#4a8ab0"),
    "clock":        ("#2a1a3a", "#1a0a28", "#8a4ab0"),
}

_FULL_NAMES: dict[str, str] = {
    "conv_history": "Conversation History",
    "connected":    "Connected Accounts",
    "markdown":     "Markdown Output",
    "web_access":   "Web Access",
    "file_access":  "File Access",
    "clock":        "Clock",
}

_LED_COLORS: dict[LedStatus, QColor] = {
    LedStatus.NO_CONNECTION: QColor(40, 40, 40),    # gray  — no API connection
    LedStatus.CONNECTED_OFF: QColor(200, 40, 40),   # red   — connected, footswitch off
    LedStatus.CONNECTED_ON:  QColor(0, 200, 80),    # green — connected, footswitch on
}


def _ctrl_range(ctrl: dict) -> tuple[float, float]:
    """Return (min, max) for a control's slider.

    FLAG: spec does not define per-control ranges. Using [0, max(100, default*2)]
    for positive defaults, [0, 100] for zero-default controls. Local UI only.
    """
    default = ctrl["default"]
    if isinstance(default, (int, float)) and default > 0:
        return 0.0, max(100.0, float(default) * 2)
    return 0.0, 100.0


def _handle_frac(ctrl: dict) -> float:
    """Return handle position in [0, 1] from current value."""
    lo, hi = _ctrl_range(ctrl)
    if hi == lo:
        return 0.0
    return max(0.0, min(1.0, (float(ctrl["value"]) - lo) / (hi - lo)))


def _value_from_frac(ctrl: dict, frac: float) -> int | float:
    """Convert a [0, 1] fraction back to a value in the control's range."""
    lo, hi = _ctrl_range(ctrl)
    val = lo + max(0.0, min(1.0, frac)) * (hi - lo)
    if isinstance(ctrl["default"], int):
        return int(round(val))
    return val


class PedalWidget(QWidget):
    """Renders one pedal enclosure using the mockup spec (pedal_all_six.svg).

    All measurements are multiples of u = widget_width / 16.
    Height is always 2 × width to maintain the 1:2 stompbox ratio.
    LED: green when functional, dark gray when not functional.
    Footswitch: clickable — emits toggle_requested(module_id).
    Sliders: draggable — update ctrl["value"] in place and repaint.
    """

    toggle_requested = pyqtSignal(str)

    def __init__(self, module: PedalModule, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._module = module
        colors = _COLORS.get(module.module_id, ("#2a2a2a", "#1a1a1a", "#aaaaaa"))
        self._body_color = QColor(colors[0])
        self._plate_color = QColor(colors[1])
        self._accent_color = QColor(colors[2])
        self._muted_color = QColor(180, 180, 180, 120)
        self._white = QColor(255, 255, 255)
        self._dark_text = QColor(220, 220, 220)

        self._dragging_ctrl: int | None = None   # index into module.controls
        self._sw_pressed: bool = False

        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMinimumWidth(80)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    # ------------------------------------------------------------------
    # Geometry helpers — all return pixel coords for the current widget size
    # ------------------------------------------------------------------

    def _u(self) -> float:
        return self.width() / 16.0

    def _slider_track(self, u: float) -> tuple[float, float]:
        """Return (track_x0, track_x1) — shared by all three slider rows."""
        cx = 2 * u
        cw = 12 * u
        return cx + 3.8 * u, cx + cw - 2.2 * u

    def _slider_mid_y(self, u: float, i: int) -> float:
        cy = 2 * u
        return cy + 2 * u + i * 2.5 * u + 1.25 * u

    def _sw_rect(self, u: float) -> QRectF:
        body_y = 17 * u
        sw_w = 12 * u
        sw_x = (16 * u - sw_w) / 2
        return QRectF(sw_x, body_y + 2.5 * u, sw_w, 5 * u)

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return width * 2

    def sizeHint(self):  # type: ignore[override]
        from PyQt6.QtCore import QSize
        return QSize(128, 256)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        u = self._u()
        pos = event.position() if hasattr(event, "position") else QPointF(event.x(), event.y())
        mx, my = pos.x(), pos.y()

        # Check footswitch
        if self._sw_rect(u).contains(QPointF(mx, my)):
            self._sw_pressed = True
            self.update()
            return

        # Check slider rows
        track_x0, track_x1 = self._slider_track(u)
        for i in range(len(self._module.controls)):
            row_y = 2 * u + 2 * u + i * 2.5 * u
            row_y_end = row_y + 2.5 * u
            if row_y <= my <= row_y_end and track_x0 - u <= mx <= track_x1 + u:
                self._dragging_ctrl = i
                self._update_ctrl_from_x(i, mx, track_x0, track_x1)
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._dragging_ctrl is None:
            super().mouseMoveEvent(event)
            return
        u = self._u()
        pos = event.position() if hasattr(event, "position") else QPointF(event.x(), event.y())
        track_x0, track_x1 = self._slider_track(u)
        self._update_ctrl_from_x(self._dragging_ctrl, pos.x(), track_x0, track_x1)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._sw_pressed:
            self._sw_pressed = False
            self.toggle_requested.emit(self._module.module_id)
            self.update()
            return
        if self._dragging_ctrl is not None:
            self._dragging_ctrl = None
        super().mouseReleaseEvent(event)

    def _update_ctrl_from_x(
        self, ctrl_idx: int, mx: float, track_x0: float, track_x1: float
    ) -> None:
        track_w = track_x1 - track_x0
        if track_w <= 0:
            return
        frac = (mx - track_x0) / track_w
        ctrl = self._module.controls[ctrl_idx]
        ctrl["value"] = _value_from_frac(ctrl, frac)
        self.update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        try:
            self._paint(p)
        finally:
            p.end()

    def _paint(self, p: QPainter) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        u = self._u()

        # --- Enclosure ---
        p.setBrush(self._body_color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(0, 0, 16 * u, 32 * u), 1.5 * u, 1.5 * u)

        # --- Config plate (inset 1u from sides, top margin 1u) ---
        p.setBrush(self._plate_color)
        p.drawRoundedRect(QRectF(u, u, 14 * u, 16 * u), 0.5 * u, 0.5 * u)

        cx = 2 * u   # content x (plate x + 1u padding)
        cy = 2 * u   # content y (plate y + 1u padding)
        cw = 12 * u  # content width

        # --- Header row (2u tall) ---
        led_r = 0.45 * u
        led_cx = cx + led_r
        led_cy = cy + u
        p.setBrush(_LED_COLORS[self._module.led_status])
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(led_cx - led_r, led_cy - led_r, 2 * led_r, 2 * led_r))

        # Title
        font = QFont()
        font.setPixelSize(max(6, int(1.1 * u)))
        font.setBold(True)
        p.setFont(font)
        p.setPen(self._accent_color)
        p.drawText(
            QRectF(cx + 1.2 * u, cy, cw - 4.7 * u, 2 * u),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._module.title,
        )

        # GLOBAL badge
        badge_font = QFont()
        badge_font.setPixelSize(max(5, int(0.7 * u)))
        p.setFont(badge_font)
        p.setPen(self._muted_color)
        p.drawText(
            QRectF(cx + cw - 3.5 * u, cy, 3.5 * u, 2 * u),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            "GLOBAL",
        )

        # --- Slider rows (3 × 2.5u) ---
        slider_font = QFont()
        slider_font.setPixelSize(max(5, int(0.85 * u)))
        p.setFont(slider_font)

        track_x0, track_x1 = self._slider_track(u)
        track_w = track_x1 - track_x0

        for i, ctrl in enumerate(self._module.controls):
            row_y = cy + 2 * u + i * 2.5 * u
            row_h = 2.5 * u
            mid_y = row_y + row_h / 2

            # Label
            p.setPen(self._dark_text)
            p.drawText(
                QRectF(cx, row_y, 3.5 * u, row_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                str(ctrl["label"]),
            )

            # Track
            p.setPen(QPen(self._muted_color, max(1, int(0.15 * u))))
            p.drawLine(QLineF(track_x0, mid_y, track_x1, mid_y))

            # Handle — positioned at current value
            handle_x = track_x0 + _handle_frac(ctrl) * track_w
            handle_h = 0.8 * u
            p.setPen(QPen(self._accent_color, max(1, int(0.2 * u))))
            p.drawLine(
                QLineF(handle_x, mid_y - handle_h / 2, handle_x, mid_y + handle_h / 2)
            )

            # Value readout
            p.setPen(self._dark_text)
            p.drawText(
                QRectF(cx + cw - 2.0 * u, row_y, 2.0 * u, row_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                str(ctrl["value"]),
            )

        # --- OUTPUT / INPUT row ---
        io_y = cy + 2 * u + 3 * 2.5 * u
        io_font = QFont()
        io_font.setPixelSize(max(5, int(0.7 * u)))
        p.setFont(io_font)
        p.setPen(self._muted_color)
        p.drawText(
            QRectF(cx, io_y, cw / 2, 1.5 * u),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "← OUTPUT",
        )
        p.drawText(
            QRectF(cx + cw / 2, io_y, cw / 2, 1.5 * u),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            "INPUT →",
        )

        # --- Body (starts at y=17u) ---
        body_y = 17 * u

        # Full module name
        name_font = QFont()
        name_font.setPixelSize(max(5, int(0.9 * u)))
        p.setFont(name_font)
        p.setPen(self._dark_text)
        p.drawText(
            QRectF(0, body_y + 0.5 * u, 16 * u, 1.5 * u),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter,
            _FULL_NAMES.get(self._module.module_id, self._module.title),
        )

        # ON footswitch
        sw_rect = self._sw_rect(u)
        if self._sw_pressed:
            # Depression: slightly darker
            sw_color = self._accent_color.darker(130) if self._module.enabled else QColor(30, 30, 30)
        else:
            sw_color = self._accent_color if self._module.enabled else QColor(50, 50, 50)
        p.setBrush(sw_color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(sw_rect, u, u)

        on_font = QFont()
        on_font.setPixelSize(max(8, int(2 * u)))
        on_font.setBold(True)
        p.setFont(on_font)
        p.setPen(self._white if self._module.enabled else self._muted_color)
        p.drawText(sw_rect, Qt.AlignmentFlag.AlignCenter, "ON")

        # SIGNAL-CHAIN footer
        footer_font = QFont()
        footer_font.setPixelSize(max(4, int(0.65 * u)))
        footer_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        p.setFont(footer_font)
        p.setPen(self._muted_color)
        p.drawText(
            QRectF(0, 30 * u, 16 * u, 1.5 * u),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter,
            "SIGNAL-CHAIN",
        )

    def update_from_module(self) -> None:
        """Trigger a repaint when module state has changed externally."""
        self.update()


class Pedalboard(QWidget):
    """Horizontal strip of six PedalWidgets docked at the bottom of the window."""

    def __init__(
        self, vm: PedalboardViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self._pedals: list[PedalWidget] = []
        for module in vm.modules:
            pedal = PedalWidget(module)
            pedal.toggle_requested.connect(vm.toggle_module)
            self._pedals.append(pedal)
            layout.addWidget(pedal)
        self.setLayout(layout)
        vm.module_state_changed.connect(lambda _mid, _en: self.refresh_all())
        self.setMinimumHeight(160)
        self.setMaximumHeight(300)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setSizePolicy(policy)

    def refresh_all(self) -> None:
        for pedal in self._pedals:
            pedal.update()
