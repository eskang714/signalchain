from PyQt6.QtCore import QObject, pyqtSignal


class BaseViewModel(QObject):
    """Base class for all Signal Chain ViewModels.

    Subclasses add their own signals and business logic.
    This module must never import from signal_chain.views.
    """

    status_changed = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
