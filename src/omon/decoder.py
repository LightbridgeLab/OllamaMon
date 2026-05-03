"""Model name decoder. Translates cryptic tags into human-readable descriptions."""

from __future__ import annotations

import importlib.resources
import json
import re

from omon.models import DecodedName, ModelDetails, ModelInfo

_tag_dict: dict | None = None
_model_map: dict | None = None


def _load_tag_dictionary() -> dict:
    global _tag_dict
    if _tag_dict is None:
        ref = importlib.resources.files("omon.data").joinpath("tag_dictionary.json")
        _tag_dict = json.loads(ref.read_text(encoding="utf-8"))
    return _tag_dict


def _load_model_map() -> dict:
    global _model_map
    if _model_map is None:
        ref = importlib.resources.files("omon.data").joinpath("model_map.json")
        data = json.loads(ref.read_text(encoding="utf-8"))
        _model_map = data.get("models", {})
    return _model_map


# Regex patterns
_PARAM_SIZE_RE = re.compile(r"^(\d+(?:\.\d+)?)b$", re.IGNORECASE)
_ACTIVE_PARAMS_RE = re.compile(r"^a(\d+(?:\.\d+)?)b$", re.IGNORECASE)
_CONTEXT_RE = re.compile(r"^(\d+)k$", re.IGNORECASE)
_VERSION_RE = re.compile(r"^v\d+(?:\.\d+)*$", re.IGNORECASE)


def _extract_family_key(name: str) -> str:
    """Extract the family portion before the colon for model_map lookup.

    'qwen3.5:35b-a3b-coding-nvfp4' -> 'qwen3.5'
    'deepseek-coder-v2:7b' -> 'deepseek-coder-v2'
    """
    return name.split(":")[0] if ":" in name else name


def _humanize_family(family_key: str) -> str:
    """Best-effort humanization of the family key."""
    # model_map has curated names via description
    # This function handles the raw key for display
    parts = family_key.replace("-", " ").replace("_", " ").split()
    return " ".join(p.capitalize() for p in parts)


def _classify_fragment(
    fragment: str,
    tag_dict: dict,
) -> tuple[str, str | None]:
    """Classify a single tag fragment. Returns (category, value)."""
    lower = fragment.lower()

    # Parameter size: 7b, 35b, 0.5b
    m = _PARAM_SIZE_RE.match(fragment)
    if m:
        return "param_size", m.group(1) + "B"

    # Active params (MoE): a3b
    m = _ACTIVE_PARAMS_RE.match(fragment)
    if m:
        return "active_params", m.group(1) + "B"

    # Quantization: check tag dictionary
    quants = tag_dict.get("quantizations", {})
    if lower in quants:
        return "quantization", lower

    # Fine-tune tags
    fine_tunes = tag_dict.get("fine_tunes", {})
    if lower in fine_tunes:
        return "fine_tune", lower

    # Size variants
    size_variants = tag_dict.get("size_variants", {})
    if lower in size_variants:
        return "size_variant", lower

    # Context suffix: 128k, 32k
    m = _CONTEXT_RE.match(fragment)
    if m:
        return "context", fragment.lower()

    # Version tags: v0.1, v2
    if _VERSION_RE.match(fragment):
        return "version", fragment

    return "unknown", fragment


def _extract_license_short(license_text: str) -> str | None:
    """Extract a short license identifier from the full text."""
    if not license_text:
        return None
    first_line = license_text.strip().splitlines()[0].strip()

    # Common patterns
    lower = license_text.lower()
    if "apache license" in lower and "2.0" in lower:
        return "Apache-2.0"
    if "mit license" in lower or lower.strip().startswith("mit"):
        return "MIT"
    if "llama 3.3 community" in lower:
        return "Llama 3.3 Community"
    if "llama 3.2 community" in lower:
        return "Llama 3.2 Community"
    if "llama 3.1 community" in lower:
        return "Llama 3.1 Community"
    if "llama 3 community" in lower:
        return "Llama 3 Community"
    if "llama 2 community" in lower:
        return "Llama 2 Community"
    if "gemma terms" in lower or "gemma use policy" in lower:
        return "Gemma"
    if "cc-by-nc" in lower:
        return "CC-BY-NC-4.0"
    if "cc-by-sa" in lower:
        return "CC-BY-SA-4.0"
    if "gnu" in lower and "gpl" in lower:
        return "GPL"
    if "bigcode" in lower and "openrail" in lower:
        return "BigCode OpenRAIL-M"

    # If first line is short, use it as-is
    if len(first_line) < 60:
        return first_line
    return "Custom License"


def decode_model_name(
    name: str,
    info: ModelInfo | None = None,
    details: ModelDetails | None = None,
) -> DecodedName:
    """Decode a model name into a human-readable DecodedName."""
    tag_dict = _load_tag_dictionary()
    model_map = _load_model_map()

    family_key = _extract_family_key(name)
    map_entry = model_map.get(family_key, {})

    # Family display name
    family_name = _humanize_family(family_key)
    if map_entry:
        # Use the publisher + family for a nicer name
        family_name = _humanize_family(family_key)

    # Parse the tag part (after the colon)
    tag = name.split(":", 1)[1] if ":" in name else ""
    fragments = tag.split("-") if tag else []

    param_size = None
    active_params = None
    quant_key = None
    fine_tunes = []
    context_hint = None
    size_variant = None
    unknown_parts = []

    for frag in fragments:
        if not frag:
            continue
        category, value = _classify_fragment(frag, tag_dict)
        if category == "param_size":
            param_size = value
        elif category == "active_params":
            active_params = value
        elif category == "quantization":
            quant_key = value
        elif category == "fine_tune":
            ft_desc = tag_dict["fine_tunes"].get(value, value)
            fine_tunes.append(ft_desc)
        elif category == "size_variant":
            size_variant = tag_dict["size_variants"].get(value, value)
        elif category == "context":
            context_hint = value.upper()
        elif category == "version":
            pass  # Version tags are informational, part of the name already
        elif category == "unknown":
            unknown_parts.append(value)

    # Cross-reference with API data
    if info and not param_size and info.parameter_size:
        param_size = info.parameter_size
    if details and not param_size and details.parameter_size:
        param_size = details.parameter_size

    # Quantization display
    quant_display = None
    quant_desc = None
    if quant_key:
        q = tag_dict["quantizations"].get(quant_key, {})
        quant_display = q.get("name", quant_key.upper())
        quant_desc = q.get("description")
    elif info and info.quantization_level:
        ql = info.quantization_level.lower()
        q = tag_dict["quantizations"].get(ql, {})
        quant_display = q.get("name", info.quantization_level)
        quant_desc = q.get("description")

    # Capabilities from API
    capabilities = []
    if details:
        capabilities = [c for c in details.capabilities if c != "completion"]

    # License
    license_short = None
    if details and details.license_text:
        license_short = _extract_license_short(details.license_text)
    elif map_entry:
        license_short = map_entry.get("license")

    # Check for MoE architecture hint from family
    if details and "moe" in details.architecture.lower() and not active_params:
        # Could try to extract from architecture name but don't guess
        pass

    return DecodedName(
        raw_name=name,
        family_name=family_name,
        description=map_entry.get("description"),
        parameter_count=param_size,
        active_params=active_params,
        quantization=quant_display,
        quantization_description=quant_desc,
        fine_tunes=fine_tunes,
        context_hint=context_hint,
        size_variant=size_variant,
        capabilities=capabilities,
        license_short=license_short,
        successor=map_entry.get("successor"),
        publisher=map_entry.get("publisher"),
        unknown_parts=unknown_parts,
    )
