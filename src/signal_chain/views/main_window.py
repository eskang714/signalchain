from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QListWidget, QListWidgetItem, QMainWindow, QSplitter, QStatusBar, QVBoxLayout, QWidget

from signal_chain.views.conversation_list_view import ConversationListView
from signal_chain.views.conversation_view import ConversationView
from signal_chain.views.pedalboard_view import Pedalboard
from signal_chain.viewmodels.pedalboard import PedalboardViewModel


class MainWindow(QMainWindow):
    """Three-panel main application window."""

    settings_requested = pyqtSignal()
    provider_changed = pyqtSignal(str)
    model_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Signal Chain")
        self.resize(1200, 800)

        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        settings_action = toolbar.addAction("⚙ Settings")
        settings_action.triggered.connect(self.settings_requested)

        toolbar.addSeparator()

        self._provider_combo = QComboBox()
        self._provider_combo.setMinimumWidth(120)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_combo_changed)
        toolbar.addWidget(self._provider_combo)

        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(260)
        self._model_combo.currentIndexChanged.connect(self._on_model_combo_changed)
        toolbar.addWidget(self._model_combo)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.conversation_list = ConversationListView()
        self.conversation_list.setMinimumWidth(180)
        self.conversation_list.setMaximumWidth(360)
        splitter.addWidget(self.conversation_list)

        self.conversation_view = ConversationView()
        splitter.addWidget(self.conversation_view)

        self._module_panel = QListWidget()
        self._module_panel.setMinimumWidth(180)
        self._module_panel.setMaximumWidth(360)
        splitter.addWidget(self._module_panel)

        splitter.setSizes([260, 660, 280])
        splitter.setStretchFactor(1, 1)

        self._pedalboard_vm = PedalboardViewModel()
        self.pedalboard = Pedalboard(self._pedalboard_vm.modules)
        self._pedalboard_vm.module_state_changed.connect(
            lambda _mid, _enabled: self.pedalboard.refresh_all()
        )

        central = QWidget()
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(splitter, stretch=1)
        vbox.addWidget(self.pedalboard, stretch=0)
        central.setLayout(vbox)
        self.setCentralWidget(central)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

    def set_modules(self, names: list[str]) -> None:
        """Populate module panel with active global module names."""
        self._module_panel.clear()
        for name in names:
            item = QListWidgetItem(f"✓ {name}")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._module_panel.addItem(item)

    def set_status(self, message: str) -> None:
        self._status_bar.showMessage(message)

    def set_providers(self, providers: list[tuple[str, str]]) -> None:
        """Populate provider combo. providers = list of (name, display_name)."""
        self._provider_combo.blockSignals(True)
        self._provider_combo.clear()
        for name, display in providers:
            self._provider_combo.addItem(display, name)
        self._provider_combo.blockSignals(False)

    def set_models(self, models: list[tuple[str, str]]) -> None:
        """Populate model combo. models = list of (model_id, display_name)."""
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        for model_id, display in models:
            self._model_combo.addItem(display, model_id)
        self._model_combo.blockSignals(False)

    def set_active_provider(self, name: str) -> None:
        """Programmatically select provider without emitting provider_changed."""
        self._provider_combo.blockSignals(True)
        for i in range(self._provider_combo.count()):
            if self._provider_combo.itemData(i) == name:
                self._provider_combo.setCurrentIndex(i)
                break
        self._provider_combo.blockSignals(False)

    def set_active_model(self, model_id: str) -> None:
        """Programmatically select model without emitting model_changed."""
        self._model_combo.blockSignals(True)
        for i in range(self._model_combo.count()):
            if self._model_combo.itemData(i) == model_id:
                self._model_combo.setCurrentIndex(i)
                break
        self._model_combo.blockSignals(False)

    def _on_provider_combo_changed(self, index: int) -> None:
        name = self._provider_combo.itemData(index)
        if name:
            self.provider_changed.emit(name)

    def _on_model_combo_changed(self, index: int) -> None:
        model_id = self._model_combo.itemData(index)
        if model_id:
            self.model_changed.emit(model_id)
