"""
Acceptance tests – Resource Management
TC-23: Architecture Incompatibility - Hard Block
TC-24: Minimum Requirements Block - Insufficient RAM
TC-25: Swap Warning - Orange Tier
TC-26: CPU Core Affinity Enforcement
TC-27: VRAM Limit Enforcement

Target module (not yet implemented):
  signal_chain.resources.manager — ResourceManager, ResourceTier, ModelRequirements

Hardware mocking strategy:
  - psutil.virtual_memory(): mocked via monkeypatch (psutil is installed)
  - CPU feature detection: mocked via signal_chain.resources.manager._get_cpu_features
  - VRAM queries: mocked via signal_chain.resources.manager._get_available_vram_bytes
    (avoids pynvml dependency in CI — pynvml not yet installed)
  - Process affinity: mocked via signal_chain.resources.manager._set_process_affinity
    (avoids needing a real running model process)

xfail policy:
  - All tests XFAIL — ResourceManager not yet implemented; ImportError triggers xfail.

FLAG TC-25 (partial): "user must check all acknowledgment boxes to proceed" is a View
  interaction assertion not testable in a headless pytest run.
  Options:
    A) Accept that requires_acknowledgment=True in the check result covers the intent;
       defer dialog rendering to a widget test.
    B) Add a pytest-qt dialog test once the orange-tier dialog is built.
  Recommendation: Option A. Waiting for human decision.

FLAG TC-27 (partial): "this is reflected in the UI resource display" is a View
  rendering assertion.
  Options:
    A) Accept that load_result.gpu_layers and cpu_layers cover the intent.
    B) Add a widget test for the resource panel once it renders per-model allocation.
  Recommendation: Option A. Waiting for human decision.
"""
from unittest.mock import MagicMock

import pytest

_8GB = 8 * 1024 ** 3
_6GB = 6 * 1024 ** 3
_4GB = 4 * 1024 ** 3
_3GB = 3 * 1024 ** 3


# ---------------------------------------------------------------------------
# TC-23: Architecture Incompatibility - Hard Block
# ---------------------------------------------------------------------------

class TestTC23ArchitectureIncompatibilityHardBlock:
    """Model requiring AVX-512 is hard-blocked on a CPU that only supports base x86-64."""

    def test_model_blocked_when_cpu_lacks_required_feature(self, monkeypatch):
        from signal_chain.resources.manager import (
            ModelRequirements,
            ResourceManager,
            ResourceTier,
        )

        monkeypatch.setattr(
            "signal_chain.resources.manager._get_cpu_features",
            lambda: {"avx": True, "avx2": True, "avx512": False},
        )

        manager = ResourceManager()
        reqs = ModelRequirements(size_bytes=_8GB, required_features=["avx512"])
        result = manager.check_requirements(reqs)

        assert result.tier == ResourceTier.BLOCKED, (
            "A model requiring AVX-512 must be BLOCKED on a CPU without AVX-512 support"
        )
        assert result.blocked is True

    def test_incompatibility_message_names_the_missing_cpu_feature(self, monkeypatch):
        from signal_chain.resources.manager import ModelRequirements, ResourceManager

        monkeypatch.setattr(
            "signal_chain.resources.manager._get_cpu_features",
            lambda: {"avx": True, "avx2": True, "avx512": False},
        )

        manager = ResourceManager()
        reqs = ModelRequirements(size_bytes=_8GB, required_features=["avx512"])
        result = manager.check_requirements(reqs)

        assert result.message, "block result must include a non-empty message"
        assert any(
            kw in result.message.lower() for kw in ("avx512", "avx-512", "instruction")
        ), "incompatibility message must reference the missing CPU feature"

    def test_no_workaround_offered_for_architecture_incompatibility(self, monkeypatch):
        from signal_chain.resources.manager import ModelRequirements, ResourceManager

        monkeypatch.setattr(
            "signal_chain.resources.manager._get_cpu_features",
            lambda: {"avx512": False},
        )

        manager = ResourceManager()
        reqs = ModelRequirements(size_bytes=_8GB, required_features=["avx512"])
        result = manager.check_requirements(reqs)

        assert result.workaround_available is False, (
            "Architecture incompatibility is a hard block — no workaround must be offered"
        )

    def test_alternative_models_suggested_for_architecture_block(self, monkeypatch):
        from signal_chain.resources.manager import ModelRequirements, ResourceManager

        monkeypatch.setattr(
            "signal_chain.resources.manager._get_cpu_features",
            lambda: {"avx512": False},
        )

        manager = ResourceManager()
        reqs = ModelRequirements(size_bytes=_8GB, required_features=["avx512"])
        result = manager.check_requirements(reqs)

        assert isinstance(result.alternatives, list), (
            "check_requirements result must include an 'alternatives' list"
        )
        assert len(result.alternatives) > 0, (
            "At least one compatible alternative must be suggested for an architecture block"
        )


# ---------------------------------------------------------------------------
# TC-24: Minimum Requirements Block - Insufficient RAM
# ---------------------------------------------------------------------------

class TestTC24MinimumRequirementsBlock:
    """Model needs 8GB RAM; only 3GB available — tier is BLOCKED, model does not load."""

    def test_blocked_tier_when_available_ram_far_below_model_size(self, monkeypatch):
        from signal_chain.resources.manager import (
            ModelRequirements,
            ResourceManager,
            ResourceTier,
        )

        monkeypatch.setattr(
            "psutil.virtual_memory",
            lambda: MagicMock(available=_3GB, total=_8GB),
        )

        manager = ResourceManager()
        result = manager.check_requirements(ModelRequirements(size_bytes=_8GB))

        assert result.tier == ResourceTier.BLOCKED, (
            "Model needing 8GB when only 3GB is available must receive BLOCKED tier"
        )

    def test_load_raises_when_requirements_are_blocked(self, monkeypatch):
        from signal_chain.resources.manager import ModelRequirements, ResourceManager

        monkeypatch.setattr(
            "psutil.virtual_memory",
            lambda: MagicMock(available=_3GB, total=_8GB),
        )

        manager = ResourceManager()
        reqs = ModelRequirements(size_bytes=_8GB)

        with pytest.raises(Exception):
            manager.load_model("test-model", requirements=reqs)

    def test_blocked_result_includes_alternatives_list(self, monkeypatch):
        from signal_chain.resources.manager import ModelRequirements, ResourceManager

        monkeypatch.setattr(
            "psutil.virtual_memory",
            lambda: MagicMock(available=_3GB, total=_8GB),
        )

        manager = ResourceManager()
        result = manager.check_requirements(ModelRequirements(size_bytes=_8GB))

        assert isinstance(result.alternatives, list), (
            "BLOCKED result must include a list of smaller compatible alternatives"
        )

    def test_check_requirements_returns_result_without_raising(self, monkeypatch):
        from signal_chain.resources.manager import ModelRequirements, ResourceManager

        monkeypatch.setattr(
            "psutil.virtual_memory",
            lambda: MagicMock(available=_3GB, total=_8GB),
        )

        manager = ResourceManager()
        result = manager.check_requirements(ModelRequirements(size_bytes=_8GB))

        assert result is not None, (
            "check_requirements must return a result object and not raise, "
            "even when the load would be blocked"
        )


# ---------------------------------------------------------------------------
# TC-25: Swap Warning - Orange Tier
# ---------------------------------------------------------------------------

class TestTC25SwapWarningOrangeTier:
    """Model needs 6GB; only 4GB available — WILL_SWAP tier with SSD warning and acknowledgment gate."""

    def test_will_swap_tier_when_available_ram_below_model_size(self, monkeypatch):
        from signal_chain.resources.manager import (
            ModelRequirements,
            ResourceManager,
            ResourceTier,
        )

        monkeypatch.setattr(
            "psutil.virtual_memory",
            lambda: MagicMock(available=_4GB, total=16 * 1024 ** 3),
        )

        manager = ResourceManager()
        result = manager.check_requirements(ModelRequirements(size_bytes=_6GB))

        assert result.tier == ResourceTier.WILL_SWAP, (
            "Model needing 6GB when 4GB is available must receive WILL_SWAP (orange) tier"
        )

    def test_will_swap_result_sets_ssd_wear_warning(self, monkeypatch):
        from signal_chain.resources.manager import ModelRequirements, ResourceManager

        monkeypatch.setattr(
            "psutil.virtual_memory",
            lambda: MagicMock(available=_4GB, total=16 * 1024 ** 3),
        )

        manager = ResourceManager()
        result = manager.check_requirements(ModelRequirements(size_bytes=_6GB))

        assert result.ssd_wear_warning is True, (
            "WILL_SWAP result must set ssd_wear_warning=True — heavy swapping can "
            "degrade a consumer SSD (~600 TBW) in weeks at ~10GB/min write rate"
        )

    def test_will_swap_result_requires_acknowledgment_before_load(self, monkeypatch):
        from signal_chain.resources.manager import ModelRequirements, ResourceManager

        monkeypatch.setattr(
            "psutil.virtual_memory",
            lambda: MagicMock(available=_4GB, total=16 * 1024 ** 3),
        )

        manager = ResourceManager()
        result = manager.check_requirements(ModelRequirements(size_bytes=_6GB))

        assert result.requires_acknowledgment is True, (
            "WILL_SWAP tier must gate loading behind user acknowledgment "
            "(spec: user checks 3 acknowledgment boxes including SSD wear warning)"
        )

    def test_will_swap_result_includes_tokens_per_sec_estimate(self, monkeypatch):
        from signal_chain.resources.manager import ModelRequirements, ResourceManager

        monkeypatch.setattr(
            "psutil.virtual_memory",
            lambda: MagicMock(available=_4GB, total=16 * 1024 ** 3),
        )

        manager = ResourceManager()
        result = manager.check_requirements(ModelRequirements(size_bytes=_6GB))

        assert result.tokens_per_sec_estimate is not None, (
            "WILL_SWAP result must include a tokens/sec performance estimate "
            "so the warning dialog can show expected throughput"
        )
        assert result.tokens_per_sec_estimate > 0, (
            "Performance estimate must be a positive number"
        )


# ---------------------------------------------------------------------------
# TC-26: CPU Core Affinity Enforcement
# ---------------------------------------------------------------------------

class TestTC26CpuCoreAffinityEnforcement:
    """When cpu_cores=[0,1,2,3] is configured, the ResourceManager restricts the process to those cores."""

    def test_affinity_set_to_configured_cores_on_load(self, monkeypatch):
        from signal_chain.resources.manager import ModelRequirements, ResourceManager

        affinity_calls: list[list[int]] = []

        monkeypatch.setattr(
            "psutil.virtual_memory",
            lambda: MagicMock(available=64 * 1024 ** 3, total=64 * 1024 ** 3),
        )
        monkeypatch.setattr(
            "signal_chain.resources.manager._set_process_affinity",
            lambda pid, cores: affinity_calls.append(cores),
        )

        manager = ResourceManager()
        reqs = ModelRequirements(size_bytes=_4GB, cpu_cores=[0, 1, 2, 3])
        manager.load_model("test-model", requirements=reqs)

        assert len(affinity_calls) >= 1, (
            "_set_process_affinity must be called at least once when cpu_cores are configured"
        )
        assert affinity_calls[0] == [0, 1, 2, 3], (
            "cpu_affinity must be set to exactly the configured cores [0, 1, 2, 3]"
        )

    def test_affinity_not_changed_when_no_cores_configured(self, monkeypatch):
        from signal_chain.resources.manager import ModelRequirements, ResourceManager

        affinity_calls: list[list[int]] = []

        monkeypatch.setattr(
            "psutil.virtual_memory",
            lambda: MagicMock(available=64 * 1024 ** 3, total=64 * 1024 ** 3),
        )
        monkeypatch.setattr(
            "signal_chain.resources.manager._set_process_affinity",
            lambda pid, cores: affinity_calls.append(cores),
        )

        manager = ResourceManager()
        reqs = ModelRequirements(size_bytes=_4GB)  # no cpu_cores specified
        manager.load_model("test-model", requirements=reqs)

        assert affinity_calls == [], (
            "_set_process_affinity must not be called when no cpu_cores are configured"
        )


# ---------------------------------------------------------------------------
# TC-27: VRAM Limit Enforcement
# ---------------------------------------------------------------------------

class TestTC27VramLimitEnforcement:
    """GPU allocation stays within vram_limit_bytes; layers that don't fit fall back to CPU."""

    def test_gpu_allocation_does_not_exceed_configured_vram_limit(self, monkeypatch):
        from signal_chain.resources.manager import ModelRequirements, ResourceManager

        monkeypatch.setattr(
            "psutil.virtual_memory",
            lambda: MagicMock(available=16 * 1024 ** 3, total=16 * 1024 ** 3),
        )
        monkeypatch.setattr(
            "signal_chain.resources.manager._get_available_vram_bytes",
            lambda device_idx=0: _8GB,
        )

        manager = ResourceManager()
        reqs = ModelRequirements(
            size_bytes=_8GB,
            vram_limit_bytes=_4GB,
        )
        load_result = manager.load_model("test-model", requirements=reqs)

        assert load_result.gpu_bytes_allocated <= _4GB, (
            "GPU allocation must not exceed the configured vram_limit_bytes (4GB) "
            "even when the full model requires 8GB of GPU memory"
        )

    def test_layers_exceeding_vram_limit_fall_back_to_cpu(self, monkeypatch):
        from signal_chain.resources.manager import ModelRequirements, ResourceManager

        monkeypatch.setattr(
            "psutil.virtual_memory",
            lambda: MagicMock(available=16 * 1024 ** 3, total=16 * 1024 ** 3),
        )
        monkeypatch.setattr(
            "signal_chain.resources.manager._get_available_vram_bytes",
            lambda device_idx=0: _8GB,
        )

        manager = ResourceManager()
        reqs = ModelRequirements(size_bytes=_8GB, vram_limit_bytes=_4GB)
        load_result = manager.load_model("test-model", requirements=reqs)

        assert load_result.cpu_layers > 0, (
            "When the model exceeds the VRAM limit, remaining layers must fall back to CPU; "
            "load_result.cpu_layers must be > 0"
        )
