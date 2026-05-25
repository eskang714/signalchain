from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class StartupWizard(QDialog):
    """First-run dialog: collects conversation directory path, writes nothing itself."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Signal Chain — First Run Setup")
        self.setMinimumWidth(500)

        self.conversation_dir: Path | None = None
        self.output_dir: Path | None = None

        default = str(Path.home() / "Documents" / "SignalChain")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Welcome to Signal Chain.\n\nChoose a folder to store your conversations:"))

        path_row = QHBoxLayout()
        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText(default)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path_input)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        layout.addWidget(QLabel("(An 'output' subfolder will be created automatically.)"))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Conversation Folder")
        if path:
            self._path_input.setText(path)

    def _on_ok(self) -> None:
        text = self._path_input.text().strip()
        if not text:
            text = self._path_input.placeholderText()
        if not text:
            QMessageBox.warning(self, "Required", "Please enter a folder path.")
            return
        self.conversation_dir = Path(text)
        self.output_dir = self.conversation_dir / "output"
        self.accept()
