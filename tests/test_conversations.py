"""
Acceptance tests – Conversation Management
TC-11: New Conversation
TC-12: Conversation Persistence
TC-13: Conversation Search
TC-14: Conversation Scale – 1000 Messages

Target modules (not yet implemented):
  signal_chain.models.conversation.Conversation
  signal_chain.models.conversation.ConversationLoader

FLAG TC-11 (partial): "model selection dialog appears grouped by provider" is a
  ViewModel/View concern.  It requires a running QApplication and a populated
  provider registry — not testable at the model/persistence layer in isolation.
  Tests below cover the underlying conversation creation contract (required fields,
  blank message list, persistence) only.
  Options:
    A) Add ViewModel-layer tests once ConversationListViewModel exists
    B) Accept provider grouping is covered by manual acceptance testing
  Recommendation: Option A — defer to ViewModel test file once that class exists.
  Waiting for human decision.

FLAG TC-14 (partial): "conversation list renders without freeze" is a PyQt6 widget
  rendering assertion that cannot be made in a headless pytest run without a live
  UI under load.  Tests below verify model-layer load time (< 3 s) and search
  time (< 2 s) instead, which are the objectively measurable sub-requirements.
  Options:
    A) Accept that freeze-free rendering is verified by the threading tests (TC-15/16)
       which already confirm the UI thread stays responsive.
    B) Add a Qt-rendered stress test if a GUI-under-load harness is added later.
  Recommendation: Option A.  Waiting for human decision.

Schema note: conftest.sample_conversation uses a simplified schema (flat fields:
  id, version, title, model as string, created_at, messages).
  Signal_Chain_Project_Brief.md describes a richer schema (nested model object,
  metadata wrapper, conversation_id, created).  Builder must resolve before
  implementing the loader; tests below use the conftest schema as the working
  contract and will be updated once the schema is locked.
"""
import json
import time
from pathlib import Path

import pytest

_xfail = pytest.mark.xfail(
    reason="conversation persistence not yet implemented - TDD red phase",
    strict=True,
)


# ---------------------------------------------------------------------------
# TC-11: New Conversation
# ---------------------------------------------------------------------------

class TestTC11NewConversation:
    """Creating a new conversation produces a valid blank object that can be persisted."""

    @_xfail
    def test_new_conversation_has_required_schema_fields(self):
        from signal_chain.models.conversation import Conversation

        conv = Conversation.create(model="claude-sonnet-4-6")

        assert conv.id, "New conversation must have a non-empty id"
        assert conv.version, "New conversation must have a version field"
        assert conv.model, "New conversation must record the model it was created with"

    @_xfail
    def test_new_conversation_version_is_1_0(self):
        from signal_chain.models.conversation import Conversation

        conv = Conversation.create(model="claude-sonnet-4-6")

        assert conv.version == "1.0", (
            "Version field must be '1.0' — required for the migration framework"
        )

    @_xfail
    def test_new_conversation_starts_with_no_messages(self):
        from signal_chain.models.conversation import Conversation

        conv = Conversation.create(model="llama3:8b")

        assert conv.messages == [], (
            "A newly created conversation must have an empty message list"
        )

    @_xfail
    def test_new_conversation_ids_are_unique(self):
        from signal_chain.models.conversation import Conversation

        conv_a = Conversation.create(model="llama3:8b")
        conv_b = Conversation.create(model="llama3:8b")

        assert conv_a.id != conv_b.id, (
            "Each new conversation must receive a distinct id"
        )

    @_xfail
    def test_saved_conversation_appears_in_load_all(self, tmp_path):
        from signal_chain.models.conversation import Conversation, ConversationLoader

        conv_dir = tmp_path / "conversations"
        conv_dir.mkdir()

        conv = Conversation.create(model="claude-sonnet-4-6")
        ConversationLoader.save(conv, conv_dir)

        loaded = ConversationLoader.load_all(conv_dir)
        loaded_ids = [c.id for c in loaded]

        assert conv.id in loaded_ids, (
            "A conversation saved via ConversationLoader.save() must appear in load_all()"
        )


# ---------------------------------------------------------------------------
# TC-12: Conversation Persistence
# ---------------------------------------------------------------------------

class TestTC12ConversationPersistence:
    """Conversations survive a save → reload cycle with all fields intact."""

    @_xfail
    def test_saved_json_contains_version_field(self, tmp_path):
        from signal_chain.models.conversation import Conversation, ConversationLoader

        conv_dir = tmp_path / "conversations"
        conv_dir.mkdir()

        conv = Conversation.create(model="claude-sonnet-4-6")
        saved_path = ConversationLoader.save(conv, conv_dir)

        raw = json.loads(saved_path.read_text())
        assert "version" in raw, (
            "Saved JSON must contain a 'version' field — required by the data versioning contract"
        )

    @_xfail
    def test_messages_intact_after_save_and_reload(self, tmp_path):
        from signal_chain.models.conversation import Conversation, ConversationLoader

        conv_dir = tmp_path / "conversations"
        conv_dir.mkdir()

        conv = Conversation.create(model="claude-sonnet-4-6")
        conv.add_message(role="user", content="What is the capital of France?")
        conv.add_message(role="assistant", content="The capital of France is Paris.")
        ConversationLoader.save(conv, conv_dir)

        reloaded = ConversationLoader.load_all(conv_dir)[0]

        assert len(reloaded.messages) == 2, (
            "Message count must be preserved across save/reload"
        )
        assert reloaded.messages[0].content == "What is the capital of France?", (
            "First message content must be preserved across save/reload"
        )
        assert reloaded.messages[1].content == "The capital of France is Paris.", (
            "Second message content must be preserved across save/reload"
        )

    @_xfail
    def test_model_selection_preserved_after_reload(self, tmp_path):
        from signal_chain.models.conversation import Conversation, ConversationLoader

        conv_dir = tmp_path / "conversations"
        conv_dir.mkdir()

        conv = Conversation.create(model="mistral:7b")
        ConversationLoader.save(conv, conv_dir)

        reloaded = ConversationLoader.load_all(conv_dir)[0]

        assert reloaded.model == "mistral:7b", (
            "Model selection must be preserved across application restarts"
        )

    @_xfail
    def test_load_from_sample_conversation_fixture(self, sample_conversation):
        """Loader must handle a well-formed conversation file produced by conftest."""
        from signal_chain.models.conversation import ConversationLoader

        conv = ConversationLoader.load(sample_conversation)

        assert conv.id == "test-conversation-001"
        assert conv.version == "1.0"
        assert len(conv.messages) == 20, (
            "All 20 messages from the fixture must be loaded"
        )

    @_xfail
    def test_message_roles_preserved_after_reload(self, sample_conversation):
        from signal_chain.models.conversation import ConversationLoader

        conv = ConversationLoader.load(sample_conversation)

        roles = [m.role for m in conv.messages]
        # Fixture produces alternating user/assistant starting with user
        assert roles[0] == "user"
        assert roles[1] == "assistant"
        assert all(r in ("user", "assistant") for r in roles), (
            "All message roles must survive the save/load cycle unchanged"
        )


# ---------------------------------------------------------------------------
# TC-13: Conversation Search
# ---------------------------------------------------------------------------

class TestTC13ConversationSearch:
    """Search filters by content/title; clearing returns the full list."""

    def _make_conversation_file(self, conv_dir: Path, conv_id: str, title: str, content: str) -> None:
        """Write a minimal conversation JSON for search tests."""
        data = {
            "version": "1.0",
            "id": conv_id,
            "title": title,
            "model": "llama3:8b",
            "created_at": "2026-05-22T10:00:00Z",
            "messages": [
                {"id": "msg_000", "role": "user", "content": content, "timestamp": "2026-05-22T10:00:00Z"},
            ],
        }
        (conv_dir / f"{conv_id}.json").write_text(json.dumps(data))

    @_xfail
    def test_search_returns_only_matching_conversations(self, tmp_path):
        from signal_chain.models.conversation import ConversationLoader

        conv_dir = tmp_path / "conversations"
        conv_dir.mkdir()
        self._make_conversation_file(conv_dir, "conv-001", "Python Tutorial", "How do I use list comprehensions?")
        self._make_conversation_file(conv_dir, "conv-002", "Recipe Discussion", "What is a good pasta recipe?")
        self._make_conversation_file(conv_dir, "conv-003", "Travel Plans", "Best places to visit in Japan?")

        results = ConversationLoader.search(conv_dir, "Python")

        assert len(results) == 1, (
            f"Search for 'Python' must return exactly 1 conversation, got {len(results)}"
        )
        assert results[0].id == "conv-001", (
            "Search must return the conversation whose title matches the query"
        )

    @_xfail
    def test_search_matches_message_content(self, tmp_path):
        from signal_chain.models.conversation import ConversationLoader

        conv_dir = tmp_path / "conversations"
        conv_dir.mkdir()
        self._make_conversation_file(conv_dir, "conv-001", "Untitled", "Tell me about photosynthesis.")
        self._make_conversation_file(conv_dir, "conv-002", "Untitled", "What is the speed of light?")

        results = ConversationLoader.search(conv_dir, "photosynthesis")

        assert len(results) == 1
        assert results[0].id == "conv-001", (
            "Search must match against message content, not just title"
        )

    @_xfail
    def test_search_with_no_match_returns_empty_list(self, tmp_path):
        from signal_chain.models.conversation import ConversationLoader

        conv_dir = tmp_path / "conversations"
        conv_dir.mkdir()
        self._make_conversation_file(conv_dir, "conv-001", "Python Tutorial", "List comprehensions.")

        results = ConversationLoader.search(conv_dir, "xyzzy_no_match")

        assert results == [], (
            "Search with no matching conversations must return an empty list, not raise"
        )

    @_xfail
    def test_empty_query_returns_all_conversations(self, tmp_path):
        from signal_chain.models.conversation import ConversationLoader

        conv_dir = tmp_path / "conversations"
        conv_dir.mkdir()
        self._make_conversation_file(conv_dir, "conv-001", "Python Tutorial", "List comprehensions.")
        self._make_conversation_file(conv_dir, "conv-002", "Recipe Discussion", "Pasta recipe.")
        self._make_conversation_file(conv_dir, "conv-003", "Travel Plans", "Japan tourism.")

        results = ConversationLoader.search(conv_dir, "")

        assert len(results) == 3, (
            "Clearing the search (empty query) must restore the full conversation list"
        )


# ---------------------------------------------------------------------------
# TC-14: Conversation Scale – 1000 Messages
# ---------------------------------------------------------------------------

class TestTC14ConversationScale:
    """Model-layer load and search over a 1000-message conversation must complete within time bounds."""

    @_xfail
    def test_large_conversation_loads_without_error(self, large_conversation):
        from signal_chain.models.conversation import ConversationLoader

        conv = ConversationLoader.load(large_conversation)

        assert len(conv.messages) == 1000, (
            "All 1000 messages must load without error or truncation"
        )

    @_xfail
    def test_large_conversation_load_completes_under_3_seconds(self, large_conversation):
        from signal_chain.models.conversation import ConversationLoader

        start = time.monotonic()
        ConversationLoader.load(large_conversation)
        elapsed = time.monotonic() - start

        assert elapsed < 3.0, (
            f"Loading a 1000-message conversation must complete in under 3 s; took {elapsed:.2f} s"
        )

    @_xfail
    def test_search_over_large_conversation_completes_under_2_seconds(self, large_conversation):
        from signal_chain.models.conversation import ConversationLoader

        conv_dir = large_conversation.parent

        start = time.monotonic()
        ConversationLoader.search(conv_dir, "Scale test message number 500")
        elapsed = time.monotonic() - start

        assert elapsed < 2.0, (
            f"Search over a 1000-message conversation must complete in under 2 s; took {elapsed:.2f} s"
        )
