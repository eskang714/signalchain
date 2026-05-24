from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = "1.0"
_SCHEMA_NAME = "conversation.v1"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ConversationModel:
    provider: str
    model_id: str


@dataclass
class ConversationMetadata:
    title: str = ""
    tags: list[str] = field(default_factory=list)
    module_usage: dict[str, object] = field(default_factory=dict)


@dataclass
class ConversationMessage:
    id: str
    role: str
    content: str
    timestamp: str


@dataclass
class Conversation:
    conversation_id: str
    version: str
    schema: str
    created: str
    model: ConversationModel
    messages: list[ConversationMessage]
    metadata: ConversationMetadata

    @classmethod
    def create(cls, provider: str, model_id: str) -> Conversation:
        return cls(
            conversation_id=f"conv_{uuid.uuid4().hex[:12]}",
            version=_SCHEMA_VERSION,
            schema=_SCHEMA_NAME,
            created=datetime.now(timezone.utc).isoformat(),
            model=ConversationModel(provider=provider, model_id=model_id),
            messages=[],
            metadata=ConversationMetadata(),
        )

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(
            ConversationMessage(
                id=f"msg_{uuid.uuid4().hex[:8]}",
                role=role,
                content=content,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class ConversationLoader:
    @staticmethod
    def save(conversation: Conversation, directory: Path) -> Path:
        """Serialize a Conversation to JSON inside *directory*. Returns the file path."""
        data = {
            "version": conversation.version,
            "schema": conversation.schema,
            "conversation_id": conversation.conversation_id,
            "created": conversation.created,
            "model": {
                "provider": conversation.model.provider,
                "model_id": conversation.model.model_id,
            },
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                }
                for m in conversation.messages
            ],
            "metadata": {
                "title": conversation.metadata.title,
                "tags": conversation.metadata.tags,
                "module_usage": conversation.metadata.module_usage,
            },
        }
        path = directory / f"{conversation.conversation_id}.json"
        path.write_text(json.dumps(data, indent=2))
        return path

    @staticmethod
    def load(path: Path) -> Conversation:
        """Deserialize a Conversation from a JSON file. Raises on malformed input."""
        return ConversationLoader._from_dict(json.loads(path.read_text()))

    @staticmethod
    def load_all(directory: Path) -> list[Conversation]:
        """Load every valid *.json conversation in *directory*.

        Corrupt or unreadable files are logged and skipped — the app must not
        crash on a bad file (Critical Behavior from CLAUDE.md).
        """
        conversations: list[Conversation] = []
        for path in sorted(directory.glob("*.json")):
            try:
                conversations.append(ConversationLoader.load(path))
            except Exception as exc:
                logger.warning("Skipping corrupt conversation file %s: %s", path, exc)
        return conversations

    @staticmethod
    def search(directory: Path, query: str) -> list[Conversation]:
        """Return conversations whose title or message content contains *query*.

        An empty *query* returns the full list.
        """
        conversations = ConversationLoader.load_all(directory)
        if not query:
            return conversations
        q = query.lower()
        return [
            c for c in conversations
            if q in c.metadata.title.lower()
            or any(q in m.content.lower() for m in c.messages)
        ]

    @staticmethod
    def _from_dict(data: dict) -> Conversation:
        model_raw = data["model"]
        meta_raw = data.get("metadata", {})
        messages = [
            ConversationMessage(
                id=m["id"],
                role=m["role"],
                content=m["content"],
                timestamp=m["timestamp"],
            )
            for m in data.get("messages", [])
        ]
        return Conversation(
            conversation_id=data["conversation_id"],
            version=data["version"],
            schema=data.get("schema", _SCHEMA_NAME),
            created=data["created"],
            model=ConversationModel(
                provider=model_raw["provider"],
                model_id=model_raw["model_id"],
            ),
            messages=messages,
            metadata=ConversationMetadata(
                title=meta_raw.get("title", ""),
                tags=meta_raw.get("tags", []),
                module_usage=meta_raw.get("module_usage", {}),
            ),
        )
