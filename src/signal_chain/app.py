from __future__ import annotations

import sys
from pathlib import Path

import yaml
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from signal_chain.models.config import AppConfig
from signal_chain.models.conversation import Conversation, ConversationLoader
from signal_chain.models.settings import SettingsManager
from signal_chain.modules.pedal_markdownOutput import pedal_markdownOutput
from signal_chain.modules.network_gateway import NetworkGateway
from signal_chain.providers.claude import ClaudeProvider
from signal_chain.providers.gemini_provider import GeminiProvider
from signal_chain.providers.groq_provider import GroqProvider
from signal_chain.providers.ollama import OllamaProvider
from signal_chain.providers.openrouter import OpenRouterProvider
from signal_chain.viewmodels.conversation import ConversationViewModel
from signal_chain.viewmodels.startup import StartupViewModel
from signal_chain.views.main_window import MainWindow
from signal_chain.views.settings_dialog import SettingsDialog
from signal_chain.views.startup_wizard import StartupWizard

_CONFIG_PATH = Path.home() / ".config" / "signalchain" / "config.yaml"
_SETTINGS_PATH = Path.home() / ".config" / "signalchain" / "settings.yaml"


class Application:
    def __init__(self, argv: list[str], provider: object | None = None) -> None:
        self._qt_app = QApplication(argv)
        self._startup_vm = StartupViewModel()
        self._provider_override = provider
        self._main_window: MainWindow | None = None
        self._vm: ConversationViewModel | None = None
        self._conversation: Conversation | None = None
        self._conv_dir: Path | None = None
        self._settings: SettingsManager | None = None
        # list of (name, display_name, provider_instance) for available providers
        self._available_providers: list[tuple[str, str, object]] = []
        self._active_provider_inst: object | None = None

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

        settings = SettingsManager.load(_SETTINGS_PATH)
        self._settings = settings

        # Provider and model setup
        if self._provider_override:
            provider = self._provider_override
            self._active_provider_inst = provider
            model_id = ""
            try:
                models = provider.list_models()  # type: ignore[union-attr]
                if models:
                    model_id = models[0].id
                    provider.load_model(model_id)  # type: ignore[union-attr]
            except Exception:
                pass
        else:
            self._available_providers = self._get_available_providers()
            provider, model_id = self._select_initial_provider_and_model()
            self._active_provider_inst = provider

        if provider is None:
            QMessageBox.warning(
                None,
                "Provider Not Available",
                "No provider is currently available. Configure an API key or start Ollama.\n\n"
                "You can still view saved conversations.",
            )
            provider = OllamaProvider(base_url=settings.get_ollama_url())

        # Main window — created before VM so its pedalboard_vm can seed the gateway
        self._main_window = MainWindow()

        # ViewModel — gateway reads live pedalboard state at authorize() time
        gateway = NetworkGateway(self._main_window._pedalboard_vm)
        self._vm = ConversationViewModel(provider=provider, gateway=gateway)  # type: ignore[arg-type]
        active_name = next(
            (n for n, _, p in self._available_providers if p is provider), "ollama"
        )
        self._conversation = Conversation.create(provider=active_name, model_id=model_id)
        self._vm.set_conversation(self._conversation)

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
        self._main_window.conversation_list.search_requested.connect(self._on_search_requested)
        self._main_window.conversation_list.rename_requested.connect(self._on_rename_requested)
        self._main_window.conversation_list.delete_requested.connect(self._on_delete_requested)
        self._main_window.settings_requested.connect(self._on_settings_requested)
        self._main_window.conversation_view.export_requested.connect(self._on_export_requested)

        # Provider/model dropdowns (skip in override/test mode)
        if not self._provider_override:
            self._populate_provider_dropdowns(active_name, model_id)
            self._main_window.provider_changed.connect(self._on_provider_changed)
            self._main_window.model_changed.connect(self._on_model_changed)

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
        if not self._conversation.metadata.title:
            user_msgs = [m for m in self._conversation.messages if m.role == "user"]
            if user_msgs:
                self._conversation.metadata.title = user_msgs[0].content[:50]
        try:
            ConversationLoader.save(self._conversation, self._conv_dir)
            self._refresh_conversation_list()
        except Exception:
            pass

    def _on_new_chat(self) -> None:
        if self._vm is None:
            return
        self._conversation = Conversation.create(provider="ollama", model_id="")
        if self._vm is not None:
            self._vm.set_conversation(self._conversation)
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
                if self._vm is not None:
                    self._vm.set_conversation(conv)
                self._main_window.conversation_view.show_conversation(
                    [(m.role, m.content) for m in conv.messages]
                )
                return

    def _refresh_conversation_list(self) -> None:
        if self._main_window is None or self._conv_dir is None:
            return
        items = [
            (conv.conversation_id, conv.metadata.title or conv.conversation_id, conv.created)
            for conv in ConversationLoader.load_all(self._conv_dir)
        ]
        self._main_window.conversation_list.load_conversations(items)

    def _on_search_requested(self, query: str) -> None:
        if self._conv_dir is None or self._main_window is None:
            return
        if query:
            convs = ConversationLoader.search(self._conv_dir, query)
        else:
            convs = ConversationLoader.load_all(self._conv_dir)
        items = [
            (c.conversation_id, c.metadata.title or c.conversation_id, c.created)
            for c in convs
        ]
        self._main_window.conversation_list.load_conversations(items)

    def _on_rename_requested(self, conv_id: str, new_title: str) -> None:
        if self._conv_dir is None:
            return
        for path in self._conv_dir.glob("*.json"):
            try:
                conv = ConversationLoader.load(path)
            except Exception:
                continue
            if conv.conversation_id == conv_id:
                conv.metadata.title = new_title
                ConversationLoader.save(conv, self._conv_dir)
                break
        self._refresh_conversation_list()

    def _on_delete_requested(self, conv_id: str) -> None:
        if self._conv_dir is not None:
            ConversationLoader.delete(conv_id, self._conv_dir)
            self._refresh_conversation_list()

    def _on_export_requested(self) -> None:
        if self._conversation is None:
            return
        parts = []
        for m in self._conversation.messages:
            prefix = "You" if m.role == "user" else "Assistant"
            parts.append(f"## {prefix}\n\n{m.content}")
        content = "\n\n---\n\n".join(parts)
        if not content:
            return
        config = AppConfig.from_yaml(_CONFIG_PATH)
        module = pedal_markdownOutput(output_dir=config.output_dir)
        module.initialize()
        result = module.execute(
            "write_file",
            {"filename": f"{self._conversation.conversation_id}.md", "content": content},
        )
        path = result.get("file_path", "")
        if self._main_window and path:
            self._main_window.set_status(f"Exported to {path}")

    # ------------------------------------------------------------------
    # Provider management
    # ------------------------------------------------------------------

    def _get_available_providers(self) -> list[tuple[str, str, object]]:
        """Return (name, display, instance) for each provider that validates."""
        result: list[tuple[str, str, object]] = []
        or_p = OpenRouterProvider()
        if or_p.validate_config():
            result.append(("openrouter", "OpenRouter", or_p))
        claude_p = ClaudeProvider()
        if claude_p.validate_config():
            result.append(("claude", "Claude", claude_p))
        groq_p = GroqProvider()
        if groq_p.validate_config():
            result.append(("groq", "Groq", groq_p))
        gemini_p = GeminiProvider()
        if gemini_p.validate_config():
            result.append(("gemini", "Gemini", gemini_p))
        url = self._settings.get_ollama_url() if self._settings else None
        ollama_p = OllamaProvider(base_url=url)
        if ollama_p.validate_config():
            result.append(("ollama", "Ollama", ollama_p))
        return result

    def _select_initial_provider_and_model(self) -> tuple[object | None, str]:
        """Pick provider and model based on saved preferences or first available."""
        if not self._available_providers:
            return None, ""
        saved_name = self._settings.get_active_provider() if self._settings else ""
        provider = next(
            (p for n, _, p in self._available_providers if n == saved_name),
            self._available_providers[0][2],
        )
        model_id = ""
        try:
            models = provider.list_models()  # type: ignore[union-attr]
            if models:
                saved_model = self._settings.get_active_model() if self._settings else ""
                model_id = (
                    saved_model
                    if any(m.id == saved_model for m in models)
                    else models[0].id
                )
                provider.load_model(model_id)  # type: ignore[union-attr]
        except Exception:
            pass
        return provider, model_id

    def _populate_provider_dropdowns(self, active_name: str, active_model: str) -> None:
        if self._main_window is None:
            return
        provider_items = [(n, d) for n, d, _ in self._available_providers]
        self._main_window.set_providers(provider_items)
        if active_name:
            self._main_window.set_active_provider(active_name)
        model_items: list[tuple[str, str]] = []
        provider = next(
            (p for n, _, p in self._available_providers if n == active_name), None
        )
        if provider is not None:
            try:
                model_items = [
                    (m.id, m.name)
                    for m in provider.list_models()  # type: ignore[union-attr]
                ]
            except Exception:
                pass
        self._main_window.set_models(model_items)
        if active_model:
            self._main_window.set_active_model(active_model)

    def _on_provider_changed(self, name: str) -> None:
        provider = next(
            (p for n, _, p in self._available_providers if n == name), None
        )
        if provider is None:
            return
        self._active_provider_inst = provider
        model_id = ""
        model_items: list[tuple[str, str]] = []
        try:
            models = provider.list_models()  # type: ignore[union-attr]
            if models:
                saved = self._settings.get_active_model() if self._settings else ""
                model_id = (
                    saved if any(m.id == saved for m in models) else models[0].id
                )
                provider.load_model(model_id)  # type: ignore[union-attr]
                model_items = [(m.id, m.name) for m in models]
        except Exception:
            pass
        if self._main_window is not None:
            self._main_window.set_models(model_items)
            if model_id:
                self._main_window.set_active_model(model_id)
        if self._vm is not None:
            self._vm.set_provider(provider)
        if self._settings is not None:
            self._settings.set_active_provider(name)
            self._settings.set_active_model(model_id)
            try:
                self._settings.save()
            except Exception:
                pass

    def _on_model_changed(self, model_id: str) -> None:
        if self._active_provider_inst is not None and model_id:
            try:
                self._active_provider_inst.load_model(model_id)  # type: ignore[union-attr]
            except Exception:
                pass
        if self._settings is not None:
            self._settings.set_active_model(model_id)
            try:
                self._settings.save()
            except Exception:
                pass

    def _refresh_providers(self) -> None:
        """Re-check available providers and repopulate dropdowns (e.g. after settings save)."""
        if self._main_window is None or self._settings is None:
            return
        self._available_providers = self._get_available_providers()
        active_name = self._settings.get_active_provider()
        if not any(n == active_name for n, _, _ in self._available_providers):
            active_name = self._available_providers[0][0] if self._available_providers else ""
        provider, model_id = self._select_initial_provider_and_model()
        if provider is not None:
            self._active_provider_inst = provider
            if self._vm is not None:
                self._vm.set_provider(provider)
        self._populate_provider_dropdowns(active_name, model_id)

    def _on_settings_requested(self) -> None:
        if self._settings is None or self._main_window is None:
            return
        dialog = SettingsDialog(self._settings, parent=self._main_window)
        dialog.exec()
        if not self._provider_override:
            self._refresh_providers()

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
