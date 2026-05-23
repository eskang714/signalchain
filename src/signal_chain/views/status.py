from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class StatusView(QWidget):
    """Minimal status display widget.

    Connects to BaseViewModel.status_changed via on_status_changed().
    Contains zero business logic.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = QLabel("")
        layout = QVBoxLayout()
        layout.addWidget(self._label)
        self.setLayout(layout)

    @property
    def status_text(self) -> str:
        return self._label.text()

    def on_status_changed(self, status: str) -> None:
        self._label.setText(status)
