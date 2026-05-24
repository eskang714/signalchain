from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass
class Message:
    role: str
    content: str


@dataclass
class GenerationConfig:
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class ModelInfo:
    id: str
    name: str


class BaseProvider(ABC):
    @abstractmethod
    def list_models(self) -> list[ModelInfo]: ...

    @abstractmethod
    def load_model(self, model_id: str) -> None: ...

    @abstractmethod
    def validate_config(self) -> bool: ...

    @abstractmethod
    def generate_stream(
        self, messages: list[Message], config: GenerationConfig
    ) -> Iterator[str]: ...

    def unload_model(self) -> None:
        pass

    def estimate_memory_usage(self, model_id: str) -> int:
        return 0
