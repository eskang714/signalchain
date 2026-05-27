from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QMainWindow, QSplitter, QStatusBar, QWidget

from signal_chain.views.conversation_list_view import ConversationListView
from signal_chain.views.conversation_view import ConversationView


class MainWindow(QMainWindow):
    """Three-panel main application window."""

    settings_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Signal Chain")
        self.resize(1200, 800)

        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        settings_action = toolbar.addAction("⚙ Settings")
        settings_action.triggered.connect(self.settings_requested)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.conversation_list = ConversationListView()
        self.conversation_list.setMinimumWidth(180)
        self.conversation_list.setMaximumWidth(360)
        splitter.addWidget(self.conversation_list)

        self.conversation_view = ConversationView()
        splitter.addWidget(self.conversation_view)

        placeholder = QLabel("Module panel\n— coming soon —")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setMinimumWidth(180)
        placeholder.setMaximumWidth(360)
        splitter.addWidget(placeholder)

        splitter.setSizes([260, 660, 280])
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

    def set_status(self, message: str) -> None:
        self._status_bar.showMessage(message)
