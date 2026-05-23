"""MVVM foundation — validates the signal/slot pattern and architectural constraints.

Covers ticket #16 (Step 3).  Threading (QThread per conversation) is Step 4;
these tests confirm the signal/slot mechanism works before building on top of it.
"""

import ast
from pathlib import Path


# ---------------------------------------------------------------------------
# Signal/slot wiring
# ---------------------------------------------------------------------------


def test_status_signal_emitted_and_received(qtbot):
    """BaseViewModel.status_changed reaches a connected lambda slot."""
    from signal_chain.viewmodels.base import BaseViewModel

    vm = BaseViewModel()
    received: list[str] = []
    vm.status_changed.connect(lambda s: received.append(s))

    with qtbot.waitSignal(vm.status_changed, timeout=1000):
        vm.status_changed.emit("ready")

    assert received == ["ready"]


def test_view_slot_receives_signal_value(qtbot):
    """StatusView.on_status_changed slot receives the value emitted by the ViewModel."""
    from signal_chain.viewmodels.base import BaseViewModel
    from signal_chain.views.status import StatusView

    vm = BaseViewModel()
    view = StatusView()
    qtbot.addWidget(view)
    vm.status_changed.connect(view.on_status_changed)

    with qtbot.waitSignal(vm.status_changed, timeout=1000) as blocker:
        vm.status_changed.emit("connected")

    assert blocker.args == ["connected"]
    assert view.status_text == "connected"


# ---------------------------------------------------------------------------
# Architectural constraints
# ---------------------------------------------------------------------------


def test_base_viewmodel_does_not_import_views():
    """BaseViewModel must never import from signal_chain.views (MVVM rule)."""
    base_src = (
        Path(__file__).parent.parent
        / "src"
        / "signal_chain"
        / "viewmodels"
        / "base.py"
    )
    tree = ast.parse(base_src.read_text())

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("signal_chain.views"), (
                f"BaseViewModel imports from views (forbidden by MVVM rules): {node.module}"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("signal_chain.views"), (
                    f"BaseViewModel imports from views (forbidden by MVVM rules): {alias.name}"
                )
