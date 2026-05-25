"""
Acceptance tests – Context Window Management
TC-28: Recent Messages Limit
TC-29: Token Limit Truncation

Target module (not yet implemented):
  signal_chain.models.context.ContextWindowManager

Behavior contract (from Signal_Chain_Project_Brief.md):
  - Recent N messages always included (default 20, configurable 10-50)
  - Token counting before send; buffer 1000 tokens reserved for response
  - Per-provider limits: Claude 180,000 tokens; Local/Ollama 4,096 tokens
  - When tokens exceed the effective limit, oldest messages are dropped first

Token counting in tests:
  ContextWindowManager accepts an injectable token_counter callable so tests
  never import tiktoken or a real tokenizer.  The injectable counter defaults
  to the real tokenizer at runtime; tests pass a character-count stub so token
  budgets are precise and deterministic.
"""
import pytest

from signal_chain.providers.base import Message

_xfail = pytest.mark.xfail(
    reason="context window not yet implemented — TDD red phase", strict=True
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _messages(n: int, *, char_count: int = 10) -> list[Message]:
    """n alternating user/assistant messages, each with content of char_count characters."""
    return [
        Message(
            role="user" if i % 2 == 0 else "assistant",
            content=("M" * char_count) + f"_{i}",
        )
        for i in range(n)
    ]


def _char_counter(text: str) -> int:
    """Token counter stub: returns character length. Keeps arithmetic simple in tests."""
    return len(text)


# ---------------------------------------------------------------------------
# TC-28: Recent Messages Limit
# ---------------------------------------------------------------------------

class TestTC28RecentMessagesLimit:
    """Only the most recent N messages are forwarded to the provider on each send."""

    @_xfail
    def test_only_most_recent_n_messages_sent(self):
        from signal_chain.models.context import ContextWindowManager

        msgs = _messages(50)
        mgr = ContextWindowManager(window_size=20, token_limit=999_999)
        result = mgr.prepare_messages(msgs)

        assert len(result) == 20, (
            "With 50 messages and window_size=20, exactly 20 messages must be returned"
        )

    @_xfail
    def test_returned_messages_are_the_newest(self):
        from signal_chain.models.context import ContextWindowManager

        msgs = _messages(50)
        mgr = ContextWindowManager(window_size=20, token_limit=999_999)
        result = mgr.prepare_messages(msgs)

        assert result == msgs[-20:], (
            "The 20 returned messages must be the newest 20, not the oldest 20"
        )

    @_xfail
    def test_all_messages_returned_when_fewer_than_window(self):
        from signal_chain.models.context import ContextWindowManager

        msgs = _messages(10)
        mgr = ContextWindowManager(window_size=20, token_limit=999_999)
        result = mgr.prepare_messages(msgs)

        assert len(result) == 10, (
            "When there are fewer messages than window_size, all messages must be returned"
        )

    @_xfail
    def test_window_size_is_configurable(self):
        from signal_chain.models.context import ContextWindowManager

        msgs = _messages(30)
        mgr = ContextWindowManager(window_size=10, token_limit=999_999)
        result = mgr.prepare_messages(msgs)

        assert len(result) == 10, (
            "window_size=10 must limit output to the 10 most recent messages"
        )

    @_xfail
    def test_default_window_size_is_20(self):
        from signal_chain.models.context import ContextWindowManager

        msgs = _messages(50)
        mgr = ContextWindowManager(token_limit=999_999)
        result = mgr.prepare_messages(msgs)

        assert len(result) == 20, (
            "Default window_size must be 20 per the project brief"
        )

    @_xfail
    def test_total_tokens_do_not_exceed_provider_limit(self):
        from signal_chain.models.context import ContextWindowManager

        # Each message content is 50 chars → 50 "tokens" via char counter.
        # 20 messages × 50 = 1000 tokens.  Limit = 800, buffer = 0.
        # Effective budget = 800.  Expect no more than 800 tokens total.
        msgs = _messages(50, char_count=50)
        mgr = ContextWindowManager(
            window_size=20,
            token_limit=800,
            response_buffer=0,
            token_counter=_char_counter,
        )
        result = mgr.prepare_messages(msgs)

        total = sum(_char_counter(m.content) for m in result)
        assert total <= 800, (
            f"Total tokens in prepared messages must not exceed token_limit=800, got {total}"
        )


# ---------------------------------------------------------------------------
# TC-29: Token Limit Truncation
# ---------------------------------------------------------------------------

class TestTC29TokenLimitTruncation:
    """When token budget is tight, oldest messages are dropped silently."""

    @_xfail
    def test_oldest_messages_truncated_when_token_limit_exceeded(self):
        from signal_chain.models.context import ContextWindowManager

        # Each message content: "M" * 100 + "_N" ≈ 102 chars ≈ 102 "tokens".
        # 10 messages × 102 ≈ 1020 tokens.
        # token_limit=500, response_buffer=0 → effective budget=500.
        # Floor(500 / 102) = 4 messages fit.
        # Newest 4 (indices 6–9) must be present; oldest (indices 0–5) must be absent.
        msgs = _messages(10, char_count=100)
        mgr = ContextWindowManager(
            window_size=20,
            token_limit=500,
            response_buffer=0,
            token_counter=_char_counter,
        )
        result = mgr.prepare_messages(msgs)

        assert msgs[-1] in result, "The newest message must survive truncation"
        assert msgs[0] not in result, "The oldest message must be the first dropped"

    @_xfail
    def test_newest_message_always_preserved(self):
        from signal_chain.models.context import ContextWindowManager

        # Extremely tight budget — only the last message fits.
        # Content is exactly 50 chars; limit=50, buffer=0.
        msgs = _messages(10, char_count=50)
        mgr = ContextWindowManager(
            window_size=20,
            token_limit=50,
            response_buffer=0,
            token_counter=_char_counter,
        )
        result = mgr.prepare_messages(msgs)

        # The last (newest) message content starts with "M"*50 → 52 chars.
        # If the implementation is lenient about the last message, it should still
        # be included.  The invariant: result is never empty, newest is always kept.
        assert len(result) >= 1, "prepare_messages must never return an empty list"
        assert result[-1] == msgs[-1], "The newest message must always be the last entry"

    @_xfail
    def test_no_exception_when_truncation_required(self):
        from signal_chain.models.context import ContextWindowManager

        # More tokens than the limit — must not raise.
        msgs = _messages(20, char_count=200)
        mgr = ContextWindowManager(
            window_size=20,
            token_limit=100,
            response_buffer=0,
            token_counter=_char_counter,
        )
        try:
            mgr.prepare_messages(msgs)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(
                f"prepare_messages must not raise when truncation is needed, got {exc!r}"
            )

    @_xfail
    def test_response_buffer_reserved_from_token_limit(self):
        from signal_chain.models.context import ContextWindowManager

        # Content: "M" * 100 + "_N" ≈ 102 chars each.
        # 10 messages × 102 ≈ 1020 tokens.
        # token_limit=500, response_buffer=200 → effective budget = 300.
        # Without buffer: floor(500/102) = 4 fit.
        # With buffer:    floor(300/102) = 2 fit.
        # Verifies the buffer actually shrinks the available window.
        msgs = _messages(10, char_count=100)

        mgr_no_buffer = ContextWindowManager(
            window_size=20, token_limit=500, response_buffer=0,
            token_counter=_char_counter,
        )
        mgr_with_buffer = ContextWindowManager(
            window_size=20, token_limit=500, response_buffer=200,
            token_counter=_char_counter,
        )

        result_no_buffer = mgr_no_buffer.prepare_messages(msgs)
        result_with_buffer = mgr_with_buffer.prepare_messages(msgs)

        assert len(result_with_buffer) < len(result_no_buffer), (
            "response_buffer must reduce the number of messages forwarded to the model"
        )
        total_with_buffer = sum(_char_counter(m.content) for m in result_with_buffer)
        assert total_with_buffer <= 300, (
            f"Tokens in prepared messages must fit within token_limit - response_buffer = 300, "
            f"got {total_with_buffer}"
        )

    @_xfail
    def test_default_response_buffer_is_1000(self):
        from signal_chain.models.context import ContextWindowManager

        # Two managers with the same token_limit but one uses default buffer.
        # If the default buffer is 1000, the default manager should pass fewer
        # messages than a manager with buffer=0 when the token budget is tight.
        msgs = _messages(30, char_count=100)
        mgr_default = ContextWindowManager(
            window_size=30, token_limit=5000, token_counter=_char_counter,
        )
        mgr_no_buffer = ContextWindowManager(
            window_size=30, token_limit=5000, response_buffer=0,
            token_counter=_char_counter,
        )

        result_default = mgr_default.prepare_messages(msgs)
        mgr_no_buffer.prepare_messages(msgs)  # establishes baseline; we assert on default only

        # With default buffer=1000: effective = 4000 → ~39 msgs, but only 30 exist
        # With no buffer:           effective = 5000 → all 30 fit
        # The total tokens for default should be ≤ 4000.
        total_default = sum(_char_counter(m.content) for m in result_default)
        assert total_default <= 4000, (
            "Default response_buffer must be 1000 — prepared messages must fit in 5000-1000=4000 tokens"
        )

    @_xfail
    def test_provider_limit_claude_is_180k(self):
        from signal_chain.models.context import ContextWindowManager

        assert ContextWindowManager.PROVIDER_LIMITS["claude"] == 180_000, (
            "Claude provider token limit must be 180,000 per the project brief"
        )

    @_xfail
    def test_provider_limit_ollama_is_4096(self):
        from signal_chain.models.context import ContextWindowManager

        assert ContextWindowManager.PROVIDER_LIMITS["ollama"] == 4_096, (
            "Ollama/local provider token limit must be 4,096 per the project brief"
        )
