from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ModelRef:
    provider: str
    model_id: str


@dataclass
class ConversationMessage:
    id: str
    role: str
    content: str
    timestamp: str


@dataclass
class ConversationMetadata:
    title: str
    tags: list
    module_usage: dict


@dataclass
class Conversation:
    conversation_id: str
    version: str
    schema: str
    created: str
    model: ModelRef
    messages: list[ConversationMessage]
    metadata: ConversationMetadata

    @classmethod
    def create(cls, provider: str, model_id: str) -> Conversation:
        return cls(
            conversation_id=f"conv_{uuid.uuid4().hex}",
            version="1.0",
            schema="conversation.v1",
            created=datetime.now(timezone.utc).isoformat(),
            model=ModelRef(provider=provider, model_id=model_id),
            messages=[],
            metadata=ConversationMetadata(title="", tags=[], module_usage={}),
        )

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(
            ConversationMessage(
                id=f"msg_{len(self.messages):04d}",
                role=role,
                content=content,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )


class ConversationLoader:
    @staticmethod
    def save(conv: Conversation, directory: Path) -> Path:
        data = {
            "version": conv.version,
            "schema": conv.schema,
            "conversation_id": conv.conversation_id,
            "created": conv.created,
            "model": {
                "provider": conv.model.provider,
                "model_id": conv.model.model_id,
            },
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                }
                for m in conv.messages
            ],
            "metadata": {
                "title": conv.metadata.title,
                "tags": conv.metadata.tags,
                "module_usage": conv.metadata.module_usage,
            },
        }
        path = directory / f"{conv.conversation_id}.json"
        path.write_text(json.dumps(data, indent=2))
        return path

    @staticmethod
    def load(path: Path) -> Conversation:
        data = json.loads(path.read_text())
        return ConversationLoader._from_dict(data)

    @staticmethod
    def _from_dict(data: dict) -> Conversation:
        model = ModelRef(**data["model"])
        messages = [ConversationMessage(**m) for m in data.get("messages", [])]
        raw_meta = data.get("metadata", {})
        metadata = ConversationMetadata(
            title=raw_meta.get("title", ""),
            tags=raw_meta.get("tags", []),
            module_usage=raw_meta.get("module_usage", {}),
        )
        return Conversation(
            conversation_id=data["conversation_id"],
            version=data["version"],
            schema=data["schema"],
            created=data["created"],
            model=model,
            messages=messages,
            metadata=metadata,
        )

    @staticmethod
    def load_all(directory: Path) -> list[Conversation]:
        result = []
        for path in sorted(directory.glob("*.json")):
            try:
                result.append(ConversationLoader.load(path))
            except Exception:
                logger.warning("Skipping corrupt conversation file: %s", path)
        return result

    @staticmethod
    def search(directory: Path, query: str) -> list[Conversation]:
        conversations = ConversationLoader.load_all(directory)
        if not query:
            return conversations
        q = query.lower()
        return [
            c
            for c in conversations
            if q in c.metadata.title.lower()
            or any(q in m.content.lower() for m in c.messages)
        ]
