from __future__ import annotations

from PyQt6.QtCore import Qt, QLineF, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from signal_chain.viewmodels.pedalboard import PedalModule

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


class PedalWidget(QWidget):
    """Renders one pedal enclosure using the mockup spec (pedal_all_six.svg).

    All measurements are multiples of u = widget_width / 16.
    Height is always 2 × width to maintain the 1:2 stompbox ratio.
    LED reflects module.led_on (functional); ON footswitch reflects module.enabled.
    Controls are visual-only — not interactive in this ticket.
    """

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
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMinimumWidth(80)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return width * 2

    def sizeHint(self):  # type: ignore[override]
        from PyQt6.QtCore import QSize
        return QSize(128, 256)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        try:
            self._paint(p)
        finally:
            p.end()

    def _paint(self, p: QPainter) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        u = w / 16.0  # base unit

        # --- Enclosure ---
        enc_rect = QRectF(0, 0, 16 * u, 32 * u)
        p.setBrush(self._body_color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(enc_rect, 1.5 * u, 1.5 * u)

        # --- Config plate (inset 1u from sides, top margin 1u) ---
        plate_rect = QRectF(u, u, 14 * u, 16 * u)
        p.setBrush(self._plate_color)
        p.drawRoundedRect(plate_rect, 0.5 * u, 0.5 * u)

        # Content inside plate: 1u internal padding
        cx = 2 * u          # content x
        cy = 2 * u          # content y (plate top + 1u plate padding)
        cw = 12 * u         # content width

        # --- Header row (2u tall) ---
        led_r = 0.45 * u
        led_cx = cx + led_r
        led_cy = cy + u
        led_color = self._accent_color if self._module.led_on else QColor(60, 60, 60)
        p.setBrush(led_color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(led_cx - led_r, led_cy - led_r, 2 * led_r, 2 * led_r))

        # Title
        title_x = cx + 1.2 * u
        title_rect = QRectF(title_x, cy, cw - 1.2 * u - 3.5 * u, 2 * u)
        font = QFont()
        font.setPixelSize(max(6, int(1.1 * u)))
        font.setBold(True)
        p.setFont(font)
        p.setPen(self._accent_color)
        p.drawText(title_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._module.title)

        # GLOBAL badge (right-aligned)
        badge_rect = QRectF(cx + cw - 3.5 * u, cy, 3.5 * u, 2 * u)
        badge_font = QFont()
        badge_font.setPixelSize(max(5, int(0.7 * u)))
        p.setFont(badge_font)
        p.setPen(self._muted_color)
        p.drawText(badge_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   "GLOBAL")

        # --- Slider rows (3 × 2.5u) ---
        slider_font = QFont()
        slider_font.setPixelSize(max(5, int(0.85 * u)))
        p.setFont(slider_font)

        for i, ctrl in enumerate(self._module.controls):
            row_y = cy + 2 * u + i * 2.5 * u
            row_h = 2.5 * u
            mid_y = row_y + row_h / 2

            # Label
            label_rect = QRectF(cx, row_y, 3.5 * u, row_h)
            p.setPen(self._dark_text)
            p.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       str(ctrl["label"]))

            # Track (center area)
            track_x0 = cx + 3.8 * u
            track_x1 = cx + cw - 2.2 * u
            track_w = track_x1 - track_x0
            p.setPen(QPen(self._muted_color, max(1, int(0.15 * u))))
            p.drawLine(QLineF(track_x0, mid_y, track_x1, mid_y))

            # Handle at center (value indicator tick)
            handle_x = track_x0 + track_w * 0.5
            handle_h = 0.8 * u
            p.setPen(QPen(self._accent_color, max(1, int(0.2 * u))))
            p.drawLine(
                int(handle_x), int(mid_y - handle_h / 2),
                int(handle_x), int(mid_y + handle_h / 2),
            )

            # Value (right)
            val_rect = QRectF(cx + cw - 2.0 * u, row_y, 2.0 * u, row_h)
            p.setPen(self._dark_text)
            p.drawText(val_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       str(ctrl["value"]))

        # --- OUTPUT / INPUT row (1.5u, below sliders) ---
        io_y = cy + 2 * u + 3 * 2.5 * u
        io_rect_l = QRectF(cx, io_y, cw / 2, 1.5 * u)
        io_rect_r = QRectF(cx + cw / 2, io_y, cw / 2, 1.5 * u)
        io_font = QFont()
        io_font.setPixelSize(max(5, int(0.7 * u)))
        p.setFont(io_font)
        p.setPen(self._muted_color)
        p.drawText(io_rect_l, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   "← OUTPUT")
        p.drawText(io_rect_r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   "INPUT →")

        # --- Body (16u × 14u, starts at y=17u) ---
        body_y = 17 * u

        # Full module name
        name_font = QFont()
        name_font.setPixelSize(max(5, int(0.9 * u)))
        p.setFont(name_font)
        p.setPen(self._dark_text)
        name_rect = QRectF(0, body_y + 0.5 * u, 16 * u, 1.5 * u)
        p.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter,
                   _FULL_NAMES.get(self._module.module_id, self._module.title))

        # ON footswitch (rounded rect, ~12u × 5u, centered)
        sw_w = 12 * u
        sw_h = 5 * u
        sw_x = (16 * u - sw_w) / 2
        sw_y = body_y + 2.5 * u
        sw_rect = QRectF(sw_x, sw_y, sw_w, sw_h)
        sw_color = self._accent_color if self._module.enabled else QColor(50, 50, 50)
        p.setBrush(sw_color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(sw_rect, u, u)

        # "ON" text inside footswitch
        on_font = QFont()
        on_font.setPixelSize(max(8, int(2 * u)))
        on_font.setBold(True)
        p.setFont(on_font)
        p.setPen(self._white if self._module.enabled else self._muted_color)
        p.drawText(sw_rect, Qt.AlignmentFlag.AlignCenter, "ON")

        # SIGNAL-CHAIN footer
        footer_rect = QRectF(0, 30 * u, 16 * u, 1.5 * u)
        footer_font = QFont()
        footer_font.setPixelSize(max(4, int(0.65 * u)))
        footer_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        p.setFont(footer_font)
        p.setPen(self._muted_color)
        p.drawText(footer_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter,
                   "SIGNAL-CHAIN")

    def update_from_module(self) -> None:
        """Trigger a repaint when module state has changed."""
        self.update()


class Pedalboard(QWidget):
    """Horizontal strip of six PedalWidgets docked at the bottom of the window.

    Each pedal maintains a 1:2 aspect ratio; the strip height scales with pedal width.
    """

    def __init__(
        self, modules: list[PedalModule], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self._pedals: list[PedalWidget] = []
        for module in modules:
            pedal = PedalWidget(module)
            self._pedals.append(pedal)
            layout.addWidget(pedal)
        self.setLayout(layout)
        # Approximate height: at ~120px per pedal, height = 240px
        self.setMinimumHeight(160)
        self.setMaximumHeight(300)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setSizePolicy(policy)

    def refresh_all(self) -> None:
        """Repaint all pedals (e.g. after a module state change)."""
        for pedal in self._pedals:
            pedal.update()
