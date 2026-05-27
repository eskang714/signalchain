from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from signal_chain.models.settings import SettingsManager


class SettingsDialog(QDialog):
    """Modal settings dialog for API key and Ollama URL configuration."""

    def __init__(
        self, settings: SettingsManager, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(440, 200)

        form = QFormLayout()

        self._openrouter_key_input = QLineEdit()
        self._openrouter_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._openrouter_key_input.setPlaceholderText("sk-or-... (get free key at openrouter.ai)")
        try:
            or_key = settings.get_api_key("openrouter") or ""
        except Exception:
            or_key = ""
        self._openrouter_key_input.setText(or_key)
        form.addRow("OpenRouter API Key", self._openrouter_key_input)

        self._groq_key_input = QLineEdit()
        self._groq_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._groq_key_input.setPlaceholderText("gsk_... (get free key at console.groq.com)")
        try:
            groq_key = settings.get_api_key("groq") or ""
        except Exception:
            groq_key = ""
        self._groq_key_input.setText(groq_key)
        form.addRow("Groq API Key", self._groq_key_input)

        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText("sk-ant-...")
        try:
            current_key = settings.get_api_key("claude") or ""
        except Exception:
            current_key = ""
        self._api_key_input.setText(current_key)
        form.addRow("Claude API Key", self._api_key_input)

        self._ollama_url_input = QLineEdit()
        self._ollama_url_input.setPlaceholderText("http://localhost:11434")
        self._ollama_url_input.setText(settings.get_ollama_url())
        form.addRow("Ollama URL", self._ollama_url_input)

        self._status_label = QLabel("")

        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self._on_save)
        cancel_btn.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self._status_label)
        layout.addLayout(btn_row)
        self.setLayout(layout)

    def _on_save(self) -> None:
        or_key = self._openrouter_key_input.text().strip()
        if or_key:
            try:
                self._settings.set_api_key("openrouter", or_key)
            except Exception:
                pass

        groq_key = self._groq_key_input.text().strip()
        if groq_key:
            try:
                self._settings.set_api_key("groq", groq_key)
            except Exception:
                pass

        api_key = self._api_key_input.text().strip()
        if api_key:
            try:
                self._settings.set_api_key("claude", api_key)
            except Exception:
                pass

        ollama_url = self._ollama_url_input.text().strip()
        if ollama_url:
            self._settings.set_ollama_url(ollama_url)

        try:
            self._settings.save()
        except Exception:
            pass

        self._status_label.setText("Settings saved. Restart to apply.")
