from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelInfo:
    """Basic model info from /api/tags."""
    name: str
    digest: str
    size: int  # bytes on disk
    modified_at: str
    format: str  # "gguf", "safetensors"
    family: str
    families: list[str]
    parameter_size: str  # "7B", "35.1B", or ""
    quantization_level: str  # "Q4_0", "nvfp4", or ""


@dataclass
class ModelDetails:
    """Extended model info from /api/show."""
    name: str
    digest: str
    size: int
    modified_at: str
    format: str
    family: str
    families: list[str]
    parameter_size: str
    quantization_level: str
    # Extended fields from /api/show
    architecture: str
    context_length: int
    parameter_count: int
    capabilities: list[str]
    template: str
    parameters: dict[str, str]
    license_text: str
    requires: str  # minimum ollama version, e.g. "0.19.0"


@dataclass
class RunningModel:
    """A currently loaded model from /api/ps."""
    name: str
    digest: str
    size: int  # memory footprint (bytes)
    size_vram: int
    context_length: int
    expires_at: str
    family: str
    parameter_size: str
    quantization_level: str


@dataclass
class DecodedName:
    """Human-readable interpretation of a model name/tag."""
    raw_name: str
    family_name: str  # "Qwen 3.5", "Llama 2"
    description: str | None  # from model_map.json
    parameter_count: str | None  # "35.1B params"
    active_params: str | None  # "3B active" (MoE only)
    quantization: str | None  # "NVIDIA FP4", "Q4_0"
    quantization_description: str | None  # "4-bit floating point..."
    fine_tunes: list[str]  # ["Coding fine-tune"]
    context_hint: str | None  # "128K" (from tag, not API)
    size_variant: str | None  # "medium"
    capabilities: list[str]  # ["vision", "thinking", "tools"]
    license_short: str | None  # "Apache-2.0"
    successor: str | None  # "llama3.3"
    publisher: str | None  # "Meta"
    unknown_parts: list[str] = field(default_factory=list)


@dataclass
class HardwareInfo:
    """Local hardware profile."""
    chip: str  # "Apple M4 Max"
    total_memory: int  # bytes
    cpu_cores: int
    os: str  # "macOS 15.x", "Linux 6.x"


@dataclass
class MemoryPressure:
    """Current memory pressure state."""
    level: str  # "normal", "warn", "critical", "unknown"
    memory_total: int  # bytes
    memory_used: int  # bytes
    memory_free: int  # bytes
    swap_used: int  # bytes
    swap_total: int  # bytes


@dataclass
class ServerStatus:
    """Ollama server status."""
    running: bool
    version: str | None
    host: str  # "localhost:11434"
    error: str | None = None
