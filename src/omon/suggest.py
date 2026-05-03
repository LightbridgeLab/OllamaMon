"""Model recommendation engine. Suggestions, cleanup, and update checking."""

from __future__ import annotations

import importlib.resources
import json
from dataclasses import dataclass, field

from omon.models import HardwareInfo, ModelInfo

# Rough bytes-per-parameter by quantization level (for size estimation)
_BYTES_PER_PARAM = {
    "q2": 0.3,
    "iq1": 0.2,
    "iq2": 0.3,
    "q3": 0.45,
    "iq3": 0.45,
    "q4": 0.55,
    "iq4": 0.55,
    "nvfp4": 0.55,
    "q5": 0.7,
    "q6": 0.8,
    "q8": 1.0,
    "fp16": 2.0,
    "bf16": 2.0,
    "fp32": 4.0,
}

# Common model sizes (in billions of parameters) for popular families
_COMMON_SIZES = [0.5, 1, 1.5, 3, 7, 8, 13, 14, 27, 32, 34, 70, 72]

# Valid task types
TASK_TYPES = ["general", "coding", "math", "vision", "chat", "embedding", "thinking", "tools"]


def _load_model_map() -> dict[str, dict]:
    ref = importlib.resources.files("omon.data").joinpath("model_map.json")
    data = json.loads(ref.read_text(encoding="utf-8"))
    return data.get("models", {})


def estimate_model_size_gb(param_billions: float, quant: str = "q4") -> float:
    """Estimate model file size in GB given parameter count and quantization."""
    quant_lower = quant.lower()
    bpp = _BYTES_PER_PARAM.get("q4", 0.55)  # default
    for prefix, val in _BYTES_PER_PARAM.items():
        if quant_lower.startswith(prefix):
            bpp = val
            break
    return param_billions * bpp * 1e9 / (1024**3)


def max_comfortable_model_gb(hw: HardwareInfo) -> float:
    """75% of total RAM — leaves room for OS and apps."""
    return hw.total_memory * 0.75 / (1024**3)


def max_feasible_model_gb(hw: HardwareInfo) -> float:
    """90% of total RAM — will cause memory pressure."""
    return hw.total_memory * 0.90 / (1024**3)


# ─── Hardware profile ──────────────────────────────────────


@dataclass
class HardwareProfile:
    hw: HardwareInfo
    comfortable_gb: float
    maximum_gb: float
    # Estimated max parameters by quantization
    param_estimates: dict[str, int]  # {"Q4": 96, "Q8": 48, "FP16": 24}
    loaded_gb: float


def build_hardware_profile(hw: HardwareInfo, loaded_bytes: int = 0) -> HardwareProfile:
    comfortable = max_comfortable_model_gb(hw)
    maximum = max_feasible_model_gb(hw)
    ram_gb = hw.total_memory / (1024**3)

    estimates = {}
    for label, bpp in [("Q2", 0.3), ("Q4", 0.55), ("Q8", 1.0), ("FP16", 2.0)]:
        max_params_b = (comfortable * (1024**3)) / (bpp * 1e9)
        estimates[label] = int(max_params_b)

    return HardwareProfile(
        hw=hw,
        comfortable_gb=comfortable,
        maximum_gb=maximum,
        param_estimates=estimates,
        loaded_gb=loaded_bytes / (1024**3),
    )


# ─── Model suggestions ────────────────────────────────────


@dataclass
class ModelSuggestion:
    family: str  # model_map key, e.g. "qwen2.5-coder"
    description: str
    publisher: str
    license: str
    tasks: list[str]
    installed: bool
    installed_name: str | None
    bench_tok_s: float | None  # from benchmarks, if available
    size_estimates: list[dict]  # [{"params": "7B", "q4_gb": 3.5, "fits": True}, ...]
    successor_of: str | None  # if this is a successor to an installed model
    notes: str | None


def get_suggestions(
    task: str,
    hw: HardwareInfo,
    installed: list[ModelInfo],
    benchmarks: dict[str, float] | None = None,
) -> list[ModelSuggestion]:
    """Get model suggestions for a task, filtered by hardware capability."""
    model_map = _load_model_map()
    comfortable_gb = max_comfortable_model_gb(hw)
    installed_families = {m.name.split(":")[0] for m in installed}
    installed_by_family = {m.name.split(":")[0]: m.name for m in installed}

    # Find which installed models have successors
    successor_targets: dict[str, str] = {}  # successor_family -> installed_family
    for family_key, entry in model_map.items():
        if family_key in installed_families:
            succ = entry.get("successor")
            if succ:
                successor_targets[succ] = family_key

    suggestions = []
    for family_key, entry in model_map.items():
        tasks = entry.get("tasks", [])
        if task.lower() not in [t.lower() for t in tasks]:
            continue

        is_installed = family_key in installed_families
        bench_speed = None
        if benchmarks:
            # Check if any installed variant has benchmarks
            for iname, speed in benchmarks.items():
                if iname.split(":")[0] == family_key:
                    bench_speed = speed
                    break

        # Estimate sizes for common parameter counts
        size_estimates = []
        for params_b in _COMMON_SIZES:
            q4_gb = estimate_model_size_gb(params_b, "q4")
            if q4_gb <= comfortable_gb * 1.5:  # include slightly-too-large for context
                fits = q4_gb <= comfortable_gb
                size_estimates.append({
                    "params": f"{params_b}B" if params_b >= 1 else f"{params_b*1000:.0f}M",
                    "q4_gb": round(q4_gb, 1),
                    "fits": fits,
                })

        # Only suggest if at least one size fits
        if not any(e["fits"] for e in size_estimates):
            continue

        succ_of = successor_targets.get(family_key)

        suggestions.append(ModelSuggestion(
            family=family_key,
            description=entry.get("description", ""),
            publisher=entry.get("publisher", ""),
            license=entry.get("license", ""),
            tasks=tasks,
            installed=is_installed,
            installed_name=installed_by_family.get(family_key),
            bench_tok_s=bench_speed,
            size_estimates=size_estimates,
            successor_of=succ_of,
            notes=entry.get("notes"),
        ))

    # Sort: installed first, then successors, then by name
    suggestions.sort(key=lambda s: (not s.installed, not s.successor_of, s.family))
    return suggestions


# ─── Update checking ───────────────────────────────────────


@dataclass
class ModelUpdate:
    model: str  # installed model name
    successor: str  # successor family name
    successor_description: str
    successor_license: str


def check_updates(installed: list[ModelInfo]) -> list[ModelUpdate]:
    """Check installed models against model_map successor info."""
    model_map = _load_model_map()
    updates = []

    for m in installed:
        family = m.name.split(":")[0]
        entry = model_map.get(family, {})
        successor = entry.get("successor")
        if successor and successor in model_map:
            succ_entry = model_map[successor]
            updates.append(ModelUpdate(
                model=m.name,
                successor=successor,
                successor_description=succ_entry.get("description", ""),
                successor_license=succ_entry.get("license", ""),
            ))

    return updates


# ─── Cleanup suggestions ──────────────────────────────────


@dataclass
class CleanupSuggestion:
    model: str
    size: int
    reasons: list[str]
    last_seen: str | None
    successor: str | None


def get_cleanup_suggestions(
    installed: list[ModelInfo],
    last_seen: dict[str, str],
    stale_days: int = 30,
) -> list[CleanupSuggestion]:
    """Suggest models to remove based on staleness and successors."""
    model_map = _load_model_map()
    suggestions = []

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    for m in installed:
        reasons = []
        family = m.name.split(":")[0]
        entry = model_map.get(family, {})
        successor = entry.get("successor")
        seen = last_seen.get(m.name)

        # Check staleness
        if seen:
            try:
                seen_dt = datetime.fromisoformat(seen)
                if seen_dt.tzinfo is None:
                    seen_dt = seen_dt.replace(tzinfo=timezone.utc)
                days_ago = (now - seen_dt).days
                if days_ago > stale_days:
                    reasons.append(f"Not used in {days_ago} days")
            except ValueError:
                pass
        else:
            reasons.append("Never used (no recorded activity)")

        # Check for successor
        if successor:
            reasons.append(f"Successor available: {successor}")

        # Check for old/superseded note
        notes = entry.get("notes", "")
        if "superseded" in notes.lower():
            reasons.append("Marked as superseded by newer models")

        if reasons:
            suggestions.append(CleanupSuggestion(
                model=m.name,
                size=m.size,
                reasons=reasons,
                last_seen=seen,
                successor=successor,
            ))

    # Sort by size descending (biggest savings first)
    suggestions.sort(key=lambda s: s.size, reverse=True)
    return suggestions
