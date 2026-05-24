"""
Shared fixtures for the Signal Chain acceptance test suite.
"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_config(tmp_path: Path) -> Path:
    """Valid config.yaml pointing to temp directories that exist."""
    conversation_dir = tmp_path / "conversations"
    output_dir = tmp_path / "output"
    conversation_dir.mkdir()
    output_dir.mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.dump(
            {
                "conversation_dir": str(conversation_dir),
                "output_dir": str(output_dir),
            }
        )
    )
    return config_path


@pytest.fixture()
def invalid_config(tmp_path: Path) -> Path:
    """Config.yaml that references a conversations directory that does not exist."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.dump(
            {
                "conversation_dir": str(tmp_path / "conversations"),  # intentionally missing
                "output_dir": str(output_dir),
            }
        )
    )
    return config_path


# ---------------------------------------------------------------------------
# Provider mocks
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_ollama():
    """
    Mock for the Ollama HTTP service.

    Patches the ollama client used by OllamaProvider so tests never need a
    running Ollama process.  Returns the mock object so individual tests can
    configure call-specific behaviour (e.g. override generate side effects).
    """
    models = [
        SimpleNamespace(model="llama3:8b", size=4_800_000_000),
        SimpleNamespace(model="mistral:7b", size=4_100_000_000),
        SimpleNamespace(model="phi3:mini",  size=2_200_000_000),
    ]

    client = MagicMock()
    client.list.return_value = SimpleNamespace(models=models)
    client.generate.return_value = iter(
        [{"response": tok, "done": False} for tok in ["Hello", " ", "world"]]
        + [{"response": "", "done": True}]
    )

    with patch("ollama.Client", return_value=client):
        yield client


@pytest.fixture()
def mock_claude_api():
    """
    Mock for the Anthropic Claude API client.

    Patches anthropic.Anthropic so tests never make real API calls.  Returns
    the mock so individual tests can configure stream chunks or error states.
    """
    chunks = ["Hello", " ", "from", " ", "Claude"]

    stream_mock = MagicMock()
    stream_mock.__enter__ = MagicMock(return_value=stream_mock)
    stream_mock.__exit__ = MagicMock(return_value=False)
    stream_mock.__iter__ = MagicMock(
        return_value=iter(
            [
                MagicMock(type="content_block_delta", delta=MagicMock(text=tok))
                for tok in chunks
            ]
        )
    )

    client = MagicMock()
    client.messages.stream.return_value = stream_mock

    with patch("anthropic.Anthropic", return_value=client):
        yield client


# ---------------------------------------------------------------------------
# Conversation fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_conversation(tmp_path: Path) -> Path:
    """
    A well-formed conversation file with 20 alternating user/assistant messages.

    Returns the path to the JSON file so tests can load it via the real
    conversation loader.
    """
    messages = []
    for i in range(20):
        role = "user" if i % 2 == 0 else "assistant"
        messages.append(
            {
                "id": f"msg_{i:03d}",
                "role": role,
                "content": f"Message number {i} from {role}.",
                "timestamp": f"2026-05-22T10:{i:02d}:00Z",
            }
        )

    conversation = {
        "version": "1.0",
        "schema": "conversation.v1",
        "conversation_id": "test-conversation-001",
        "created": "2026-05-22T10:00:00Z",
        "model": {"provider": "claude", "model_id": "claude-sonnet-4-6"},
        "messages": messages,
        "metadata": {"title": "Sample conversation", "tags": [], "module_usage": {}},
    }

    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir(exist_ok=True)
    conv_file = conv_dir / "sample_conversation.json"
    conv_file.write_text(json.dumps(conversation, indent=2))
    return conv_file


@pytest.fixture()
def large_conversation(tmp_path: Path) -> Path:
    """
    A well-formed conversation file with 1000 messages for scale tests (TC-14).

    Message content is varied so search tests have something to match against.
    """
    messages = [
        {
            "id": f"msg_{i:04d}",
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Scale test message number {i}. " + ("filler text " * 4),
            "timestamp": f"2026-05-22T{i // 3600:02d}:{(i % 3600) // 60:02d}:{i % 60:02d}Z",
        }
        for i in range(1000)
    ]

    conversation = {
        "version": "1.0",
        "schema": "conversation.v1",
        "conversation_id": "large-conversation-001",
        "created": "2026-05-22T00:00:00Z",
        "model": {"provider": "ollama", "model_id": "llama3:8b"},
        "messages": messages,
        "metadata": {"title": "Large scale test conversation", "tags": [], "module_usage": {}},
    }

    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir(exist_ok=True)
    conv_file = conv_dir / "large_conversation.json"
    conv_file.write_text(json.dumps(conversation))
    return conv_file


@pytest.fixture()
def corrupt_conversation_file(tmp_path: Path) -> Path:
    """
    A malformed JSON file inside a conversations directory.

    The file exists on disk but cannot be parsed.  Used to verify the loader
    skips corrupt files without crashing.
    """
    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir(exist_ok=True)
    corrupt_file = conv_dir / "corrupt_conversation.json"
    corrupt_file.write_text("{this is not valid JSON: [[[")
    return corrupt_file
