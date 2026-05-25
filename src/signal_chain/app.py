from __future__ import annotations

import sys
from pathlib import Path

import yaml
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from signal_chain.models.config import AppConfig
from signal_chain.models.conversation import Conversation, ConversationLoader
from signal_chain.providers.ollama import OllamaProvider
from signal_chain.viewmodels.conversation import ConversationViewModel
from signal_chain.viewmodels.startup import StartupViewModel
from signal_chain.views.main_window import MainWindow
from signal_chain.views.startup_wizard import StartupWizard

_CONFIG_PATH = Path.home() / ".config" / "signalchain" / "config.yaml"


class Application:
    def __init__(self, argv: list[str], provider: object | None = None) -> None:
        self._qt_app = QApplication(argv)
        self._startup_vm = StartupViewModel()
        self._provider_override = provider
        self._main_window: MainWindow | None = None
        self._vm: ConversationViewModel | None = None
        self._conversation: Conversation | None = None
        self._conv_dir: Path | None = None

    def run(self) -> int:
        self._startup_vm.wizard_required.connect(self._on_wizard_required)
        self._startup_vm.main_ready.connect(self._on_main_ready)
        self._startup_vm.fix_dialog_required.connect(self._on_fix_dialog)
        self._startup_vm.disk_warning.connect(self._on_disk_warning)

        self._startup_vm.startup(_CONFIG_PATH)

        if not self._startup_vm.is_main_ready:
            return 0

        return self._qt_app.exec()

    # ------------------------------------------------------------------
    # Startup signal handlers
    # ------------------------------------------------------------------

    def _on_wizard_required(self) -> None:
        wizard = StartupWizard()
        if wizard.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
        assert wizard.conversation_dir is not None
        assert wizard.output_dir is not None
        self._write_config(wizard.conversation_dir, wizard.output_dir)
        self._startup_vm.startup(_CONFIG_PATH)

    def _on_fix_dialog(self) -> None:
        missing = "\n".join(str(p) for p in self._startup_vm.missing_paths)
        result = QMessageBox.question(
            None,
            "Missing Directories",
            f"These directories are missing:\n{missing}\n\nCreate them now?",
        )
        if result == QMessageBox.StandardButton.Yes:
            self._startup_vm.create_missing_directories()

    def _on_disk_warning(self, free_mb: int) -> None:
        QMessageBox.warning(
            None,
            "Low Disk Space",
            f"Only {free_mb} MB free. Signal Chain may not be able to save conversations.",
        )

    def _on_main_ready(self) -> None:
        if self._main_window is not None:
            return  # already wired (can be called twice if wizard → startup retry)

        config = AppConfig.from_yaml(_CONFIG_PATH)
        self._conv_dir = config.conversation_dir

        # Provider setup
        provider = self._provider_override or OllamaProvider()
        model_id = ""
        if not provider.validate_config():
            QMessageBox.warning(
                None,
                "Ollama Not Running",
                "Ollama is not running. Start Ollama and restart Signal Chain.\n\n"
                "You can still view saved conversations.",
            )
        else:
            try:
                models = provider.list_models()
                if models:
                    model_id = models[0].id
                    provider.load_model(model_id)
            except Exception:
                pass

        # ViewModel
        self._vm = ConversationViewModel(provider=provider)
        self._conversation = Conversation.create(provider="ollama", model_id=model_id)

        # Main window
        self._main_window = MainWindow()
        self._main_window.conversation_view.set_viewmodel(self._vm)

        # Status bar wiring
        self._vm.generation_started.connect(
            lambda: self._main_window.set_status("Generating…")  # type: ignore[union-attr]
        )
        self._vm.generation_complete.connect(
            lambda: self._main_window.set_status("Ready")  # type: ignore[union-attr]
        )
        self._vm.generation_error.connect(
            lambda msg: self._main_window.set_status(f"Error: {msg}")  # type: ignore[union-attr]
        )

        # Message tracking for persistence
        self._main_window.conversation_view.message_submitted.connect(
            self._on_message_submitted
        )
        self._vm.generation_complete.connect(self._on_generation_complete)

        # Conversation list
        self._refresh_conversation_list()
        self._main_window.conversation_list.new_chat_requested.connect(self._on_new_chat)
        self._main_window.conversation_list.conversation_selected.connect(
            self._on_conversation_selected
        )

        self._main_window.show()

    # ------------------------------------------------------------------
    # Conversation lifecycle
    # ------------------------------------------------------------------

    def _on_message_submitted(self, text: str) -> None:
        if self._conversation is not None:
            self._conversation.add_message(role="user", content=text)

    def _on_generation_complete(self) -> None:
        if self._conversation is None or self._vm is None or self._conv_dir is None:
            return
        if self._vm.response_text:
            self._conversation.add_message(role="assistant", content=self._vm.response_text)
        try:
            ConversationLoader.save(self._conversation, self._conv_dir)
            self._refresh_conversation_list()
        except Exception:
            pass

    def _on_new_chat(self) -> None:
        if self._vm is None:
            return
        self._conversation = Conversation.create(provider="ollama", model_id="")
        if self._main_window is not None:
            self._main_window.conversation_view.clear_display()

    def _on_conversation_selected(self, conv_id: str) -> None:
        if self._conv_dir is None or self._main_window is None:
            return
        for path in sorted(self._conv_dir.glob("*.json")):
            try:
                conv = ConversationLoader.load(path)
            except Exception:
                continue
            if conv.conversation_id == conv_id:
                self._conversation = conv
                self._main_window.conversation_view.show_conversation(
                    [(m.role, m.content) for m in conv.messages]
                )
                return

    def _refresh_conversation_list(self) -> None:
        if self._main_window is None or self._conv_dir is None:
            return
        items = []
        for conv in ConversationLoader.load_all(self._conv_dir):
            title = conv.metadata.title or conv.conversation_id
            items.append((conv.conversation_id, title))
        self._main_window.conversation_list.load_conversations(items)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_config(conv_dir: Path, out_dir: Path) -> None:
        conv_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CONFIG_PATH.write_text(
            yaml.dump(
                {"conversation_dir": str(conv_dir), "output_dir": str(out_dir)},
                default_flow_style=False,
            )
        )
