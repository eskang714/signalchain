"""
Acceptance tests – conversation_history global module
Ticket #66

Target (not yet implemented):
  signal_chain.modules.conversation_history.ConversationHistoryModule

Interface contract locked for the builder:
  module.execute("add_message",   {"role": str, "content": str}, caller_module=None)
    → dict
  module.execute("get_history",   {}, caller_module=None)
    → {"history": list[{"role": str, "content": str}]}
  module.execute("clear_history", {}, caller_module=None)
    → {"cleared": True}

Module filesystem location (for registry discovery):
  src/signal_chain/modules/global/conversation_history/module.json
    {"name": "conversation_history"}

Python import location (same pattern as connected_accounts.py):
  signal_chain.modules.conversation_history.ConversationHistoryModule

xfail policy:
  - test_registry_scan_*: xfail via assertion failure — global/conversation_history/
    directory does not yet exist on disk; ModuleRegistry.scan() returns no such module.
  - All other tests: xfail via ImportError — ConversationHistoryModule not yet
    implemented; import inside test body triggers xfail before assertion is reached.
"""
from pathlib import Path


class TestConversationHistoryModule:
    """ConversationHistoryModule: required global module, always enabled, stateful history store."""

    # ------------------------------------------------------------------
    # A. Module discovery
    # ------------------------------------------------------------------

    def test_registry_scan_includes_conversation_history_as_global(self, tmp_path):
        """ModuleRegistry.scan() must return conversation_history with is_global=True."""
        import signal_chain.modules as _mods_pkg
        from signal_chain.modules.registry import ModuleRegistry

        global_dir = Path(_mods_pkg.__file__).parent / "global"
        user_dir = tmp_path / "user"
        user_dir.mkdir()

        registry = ModuleRegistry(user_dir=user_dir, global_dir=global_dir)
        records = registry.scan()

        global_names = {r.name for r in records if r.is_global}
        assert "conversation_history" in global_names, (
            "ModuleRegistry.scan() must include 'conversation_history' "
            "in the global modules list (requires global/conversation_history/module.json)"
        )

    # ------------------------------------------------------------------
    # B. add_message + get_history round-trip
    # ------------------------------------------------------------------

    def test_add_message_then_get_history_round_trip(self):
        """Single add_message followed by get_history returns that message."""
        from signal_chain.modules.conversation_history import ConversationHistoryModule

        module = ConversationHistoryModule()
        module.initialize()
        module.execute("add_message", {"role": "user", "content": "hello"})
        result = module.execute("get_history", {})

        assert "history" in result, "get_history must return a dict with a 'history' key"
        assert len(result["history"]) == 1, (
            "get_history must return exactly the one message that was added"
        )
        msg = result["history"][0]
        assert msg["role"] == "user", "returned message must preserve the role"
        assert msg["content"] == "hello", "returned message must preserve the content"

    # ------------------------------------------------------------------
    # C. History is stateful across calls
    # ------------------------------------------------------------------

    def test_history_is_stateful_across_multiple_add_calls(self):
        """Three add_message calls → get_history returns all three in insertion order."""
        from signal_chain.modules.conversation_history import ConversationHistoryModule

        module = ConversationHistoryModule()
        module.initialize()
        module.execute("add_message", {"role": "user",      "content": "first"})
        module.execute("add_message", {"role": "assistant", "content": "second"})
        module.execute("add_message", {"role": "user",      "content": "third"})

        result = module.execute("get_history", {})
        history = result["history"]

        assert len(history) == 3, (
            "get_history must return all added messages (got {})".format(len(history))
        )
        assert history[0]["content"] == "first"
        assert history[1]["content"] == "second"
        assert history[2]["content"] == "third"

    # ------------------------------------------------------------------
    # D. clear_history() empties the history and signals success
    # ------------------------------------------------------------------

    def test_clear_history_empties_history_and_returns_cleared_true(self):
        """clear_history resets the store; subsequent get_history returns []."""
        from signal_chain.modules.conversation_history import ConversationHistoryModule

        module = ConversationHistoryModule()
        module.initialize()
        module.execute("add_message", {"role": "user", "content": "before clear"})

        clear_result = module.execute("clear_history", {})
        assert clear_result.get("cleared") is True, (
            "execute('clear_history') must return {'cleared': True}"
        )

        history_result = module.execute("get_history", {})
        assert history_result["history"] == [], (
            "get_history must return [] immediately after clear_history"
        )

    # ------------------------------------------------------------------
    # E. Cannot be disabled — global modules are always on
    # ------------------------------------------------------------------

    def test_global_module_cannot_be_disabled_via_registry(self, tmp_path):
        """registry.disable('conversation_history') is a no-op; module stays enabled."""
        from signal_chain.modules.conversation_history import ConversationHistoryModule  # noqa: F401

        import signal_chain.modules as _mods_pkg
        from signal_chain.modules.registry import ModuleRegistry

        global_dir = Path(_mods_pkg.__file__).parent / "global"
        user_dir = tmp_path / "user"
        user_dir.mkdir()

        registry = ModuleRegistry(user_dir=user_dir, global_dir=global_dir)
        registry.disable("conversation_history")
        records = registry.scan()

        conv_hist = next(
            (r for r in records if r.name == "conversation_history"), None
        )
        assert conv_hist is not None, (
            "conversation_history must still appear in scan results after disable() is called"
        )
        assert conv_hist.enabled is True, (
            "Global module 'conversation_history' must remain enabled — "
            "disable() must be a no-op for global modules"
        )
        assert conv_hist.can_enable is False, (
            "can_enable must be False for a global module (it cannot be toggled off)"
        )

    # ------------------------------------------------------------------
    # F. caller_module accepted without isolation error
    # ------------------------------------------------------------------

    def test_execute_accepts_caller_module_without_error(self):
        """Global modules accept calls from any caller_module without isolation errors."""
        from signal_chain.modules.conversation_history import ConversationHistoryModule

        module = ConversationHistoryModule()
        module.initialize()
        module.execute("add_message", {"role": "user", "content": "msg"})
        result = module.execute("get_history", {}, caller_module="markdown_output")

        assert "history" in result, (
            "execute('get_history', caller_module='markdown_output') must succeed — "
            "global modules are accessible from any other module"
        )
