from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum

import psutil


class ResourceTier(Enum):
    BLOCKED = "blocked"
    WILL_SWAP = "will_swap"
    RECOMMENDED = "recommended"
    OPTIMAL = "optimal"


@dataclass
class ModelRequirements:
    size_bytes: int
    required_features: list[str] = field(default_factory=list)
    cpu_cores: list[int] = field(default_factory=list)
    vram_limit_bytes: int | None = None


@dataclass
class CheckResult:
    tier: ResourceTier
    blocked: bool = False
    message: str = ""
    workaround_available: bool = True
    alternatives: list = field(default_factory=list)
    ssd_wear_warning: bool = False
    requires_acknowledgment: bool = False
    tokens_per_sec_estimate: float | None = None


@dataclass
class LoadResult:
    gpu_bytes_allocated: int = 0
    gpu_layers: int = 0
    cpu_layers: int = 0


def _get_cpu_features() -> dict:
    return {}


def _get_available_vram_bytes(device_idx: int = 0) -> int:
    return 0


def _set_process_affinity(pid: int, cores: list[int]) -> None:
    try:
        proc = psutil.Process(pid)
        proc.cpu_affinity(cores)
    except Exception:
        pass


class ResourceManager:
    def check_requirements(self, req: ModelRequirements) -> CheckResult:
        if req.required_features:
            cpu_features = _get_cpu_features()
            missing = [f for f in req.required_features if not cpu_features.get(f, False)]
            if missing:
                feature = missing[0]
                return CheckResult(
                    tier=ResourceTier.BLOCKED,
                    blocked=True,
                    message=(
                        f"CPU lacks required instruction set: {feature}. "
                        f"This model requires {feature} but your CPU does not support it."
                    ),
                    workaround_available=False,
                    alternatives=["Consider a model without AVX-512 requirements."],
                )

        mem = psutil.virtual_memory()
        available = mem.available
        size = req.size_bytes

        if available < size / 2:
            return CheckResult(
                tier=ResourceTier.BLOCKED,
                blocked=True,
                message=(
                    f"Insufficient RAM: ~{size // 1024**3}GB needed, "
                    f"{available // 1024**3}GB available."
                ),
                alternatives=["Try a smaller quantized model (Q4 or Q2)."],
                workaround_available=False,
            )

        if available < size:
            return CheckResult(
                tier=ResourceTier.WILL_SWAP,
                blocked=False,
                ssd_wear_warning=True,
                requires_acknowledgment=True,
                tokens_per_sec_estimate=2.0,
            )

        if available < 2 * size:
            return CheckResult(tier=ResourceTier.RECOMMENDED, blocked=False)

        return CheckResult(tier=ResourceTier.OPTIMAL, blocked=False)

    def load_model(self, model_id: str, requirements: ModelRequirements) -> LoadResult:
        result = self.check_requirements(requirements)
        if result.blocked:
            raise RuntimeError(f"Cannot load '{model_id}': {result.message}")

        if requirements.cpu_cores:
            _set_process_affinity(os.getpid(), requirements.cpu_cores)

        gpu_bytes = 0
        cpu_layers = 0
        if requirements.vram_limit_bytes is not None:
            gpu_bytes = min(requirements.size_bytes, requirements.vram_limit_bytes)
            if gpu_bytes < requirements.size_bytes:
                cpu_layers = 1

        return LoadResult(gpu_bytes_allocated=gpu_bytes, cpu_layers=cpu_layers)
