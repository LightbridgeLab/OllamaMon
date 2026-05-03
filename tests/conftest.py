"""Shared test fixtures."""

from __future__ import annotations

import pytest

from omon.models import (
    DecodedName,
    HardwareInfo,
    MemoryPressure,
    ModelDetails,
    ModelInfo,
    RunningModel,
    ServerStatus,
)


@pytest.fixture
def hw_64gb() -> HardwareInfo:
    """64 GB Apple M4 Max."""
    return HardwareInfo(
        chip="Apple M4 Max",
        total_memory=64 * 1024**3,
        cpu_cores=16,
        os="macOS 15.3",
    )


@pytest.fixture
def hw_8gb() -> HardwareInfo:
    """8 GB machine — constrained."""
    return HardwareInfo(
        chip="Apple M1",
        total_memory=8 * 1024**3,
        cpu_cores=8,
        os="macOS 15.3",
    )


@pytest.fixture
def model_llama2() -> ModelInfo:
    return ModelInfo(
        name="llama2:7b",
        digest="abc123def456",
        size=3_800_000_000,
        modified_at="2026-04-01T12:00:00Z",
        format="gguf",
        family="llama",
        families=["llama"],
        parameter_size="7B",
        quantization_level="Q4_0",
    )


@pytest.fixture
def model_qwen() -> ModelInfo:
    return ModelInfo(
        name="qwen3.5:35b-a3b-coding-nvfp4",
        digest="def456abc789",
        size=21_000_000_000,
        modified_at="2026-04-10T08:30:00Z",
        format="gguf",
        family="qwen2",
        families=["qwen2"],
        parameter_size="35.1B",
        quantization_level="nvfp4",
    )


@pytest.fixture
def details_llama2() -> ModelDetails:
    return ModelDetails(
        name="llama2:7b",
        digest="abc123def456",
        size=3_800_000_000,
        modified_at="2026-04-01T12:00:00Z",
        format="gguf",
        family="llama",
        families=["llama"],
        parameter_size="7B",
        quantization_level="Q4_0",
        architecture="llama",
        context_length=4096,
        parameter_count=6_738_415_616,
        capabilities=["completion"],
        template="{{ .Prompt }}",
        parameters={"temperature": "0.8", "top_p": "0.9"},
        license_text="LLAMA 2 COMMUNITY LICENSE AGREEMENT\nLlama 2 Version Release Date: July 18, 2023",
        requires="",
    )
