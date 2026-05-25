from __future__ import annotations

from typing import ClassVar

from PyQt6.QtCore import QThread, pyqtSignal

from signal_chain.providers.base import BaseProvider, GenerationConfig, Message
from signal_chain.viewmodels.base import BaseViewModel


class _GenerationThread(QThread):
    """QThread subclass: streams provider tokens in run(), emits them to the main thread.

    Signals are emitted from inside run() (the new OS thread) while the QThread
    object's affinity is the creating (main) thread.  Qt therefore delivers them
    as queued connections — the main-thread event loop picks them up
    asynchronously, keeping the UI non-blocking.
    """

    token = pyqtSignal(str)
    generation_finished = pyqtSignal()
    generation_error = pyqtSignal(str)

    def __init__(
        self,
        provider: BaseProvider,
        messages: list[Message],
        config: GenerationConfig,
    ) -> None:
        super().__init__()
        self._provider = provider
        self._messages = messages
        self._config = config

    def run(self) -> None:
        try:
            for tok in self._provider.generate_stream(self._messages, self._config):
                self.token.emit(tok)
            self.generation_finished.emit()
        except Exception as exc:
            self.generation_error.emit(str(exc))


class ConversationViewModel(BaseViewModel):
    """Manages one conversation; streams tokens from a provider via a dedicated QThread."""

    token_received = pyqtSignal(str)
    generation_complete = pyqtSignal()
    generation_error = pyqtSignal(str)
    generation_started = pyqtSignal()
    retry_available = pyqtSignal()
    module_error = pyqtSignal(str)
    countdown_tick = pyqtSignal(int)

    # Holds strong Python references to all running threads.
    # Without this, a test that ends before generation completes would drop the
    # last Python reference to the QThread, triggering GC of a running thread
    # and an OS-level abort (SIGABRT).
    _live_threads: ClassVar[set[_GenerationThread]] = set()

    def __init__(self, provider: BaseProvider) -> None:
        super().__init__()
        self._provider = provider
        self.is_generating: bool = False
        self.response_text: str = ""
        self.error_state: str = ""
        self._thread: _GenerationThread | None = None
        self._last_text: str | None = None

    def send_message(self, text: str) -> str:
        if self.is_generating:
            return "queued"
        self._last_text = text
        self._start_generation([Message(role="user", content=text)], GenerationConfig())
        return "sent"

    def retry_last_message(self) -> str:
        if self._last_text is None or self.is_generating:
            return "queued"
        self._start_generation(
            [Message(role="user", content=self._last_text)], GenerationConfig()
        )
        return "sent"

    def _start_generation(
        self, messages: list[Message], config: GenerationConfig
    ) -> None:
        self.response_text = ""
        self.error_state = ""
        self.is_generating = True
        self.generation_started.emit()

        thread = _GenerationThread(self._provider, messages, config)
        ConversationViewModel._live_threads.add(thread)

        thread.token.connect(self._on_token)
        thread.generation_finished.connect(self._on_complete)
        thread.generation_error.connect(self._on_error)

        self._thread = thread
        thread.start()

    def _on_token(self, tok: str) -> None:
        self.response_text += tok
        self.token_received.emit(tok)

    def _on_complete(self) -> None:
        self.is_generating = False
        self._cleanup_thread()
        self.generation_complete.emit()

    def _on_error(self, message: str) -> None:
        self.error_state = message
        self.is_generating = False
        self._cleanup_thread()
        self.retry_available.emit()
        self.generation_error.emit(message)

    def _cleanup_thread(self) -> None:
        if self._thread is not None:
            # run() has already returned by the time this queued slot fires;
            # quit() is a no-op (no event loop), wait() returns immediately.
            self._thread.quit()
            self._thread.wait()
            ConversationViewModel._live_threads.discard(self._thread)
        self._thread = None
