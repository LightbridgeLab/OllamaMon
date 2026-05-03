"""Tests for the model name decoder."""

from __future__ import annotations

import pytest

from omon.decoder import (
    _classify_fragment,
    _extract_family_key,
    _extract_license_short,
    _humanize_family,
    _load_tag_dictionary,
    decode_model_name,
)
from omon.models import ModelDetails, ModelInfo


# ─── Helpers ──────────────────────────────────────────────


@pytest.fixture
def tag_dict():
    return _load_tag_dictionary()


# ─── _extract_family_key ─────────────────────────────────


class TestExtractFamilyKey:
    def test_with_colon(self):
        assert _extract_family_key("qwen3.5:35b-a3b-coding-nvfp4") == "qwen3.5"

    def test_without_colon(self):
        assert _extract_family_key("llama2") == "llama2"

    def test_multiple_colons(self):
        # Only split on first colon
        assert _extract_family_key("a:b:c") == "a"

    def test_colon_at_end(self):
        assert _extract_family_key("model:") == "model"


# ─── _humanize_family ────────────────────────────────────


class TestHumanizeFamily:
    def test_simple(self):
        assert _humanize_family("llama2") == "Llama2"

    def test_hyphenated(self):
        assert _humanize_family("deepseek-coder-v2") == "Deepseek Coder V2"

    def test_underscored(self):
        assert _humanize_family("all_minilm") == "All Minilm"

    def test_dotted(self):
        # Dots are not split on — they're part of version strings
        assert _humanize_family("qwen3.5") == "Qwen3.5"


# ─── _classify_fragment ──────────────────────────────────


class TestClassifyFragment:
    def test_param_size_integer(self, tag_dict):
        assert _classify_fragment("7b", tag_dict) == ("param_size", "7B")

    def test_param_size_decimal(self, tag_dict):
        assert _classify_fragment("35b", tag_dict) == ("param_size", "35B")

    def test_param_size_sub_one(self, tag_dict):
        assert _classify_fragment("0.5b", tag_dict) == ("param_size", "0.5B")

    def test_active_params(self, tag_dict):
        assert _classify_fragment("a3b", tag_dict) == ("active_params", "3B")

    def test_quantization_q4_0(self, tag_dict):
        assert _classify_fragment("q4_0", tag_dict) == ("quantization", "q4_0")

    def test_quantization_nvfp4(self, tag_dict):
        assert _classify_fragment("nvfp4", tag_dict) == ("quantization", "nvfp4")

    def test_quantization_fp16(self, tag_dict):
        assert _classify_fragment("fp16", tag_dict) == ("quantization", "fp16")

    def test_fine_tune_coding(self, tag_dict):
        assert _classify_fragment("coding", tag_dict) == ("fine_tune", "coding")

    def test_fine_tune_instruct(self, tag_dict):
        assert _classify_fragment("instruct", tag_dict) == ("fine_tune", "instruct")

    def test_size_variant(self, tag_dict):
        assert _classify_fragment("small", tag_dict) == ("size_variant", "small")

    def test_context_suffix(self, tag_dict):
        assert _classify_fragment("128k", tag_dict) == ("context", "128k")

    def test_version_tag(self, tag_dict):
        assert _classify_fragment("v0.1", tag_dict) == ("version", "v0.1")

    def test_version_simple(self, tag_dict):
        assert _classify_fragment("v2", tag_dict) == ("version", "v2")

    def test_unknown(self, tag_dict):
        assert _classify_fragment("xyzzy", tag_dict) == ("unknown", "xyzzy")

    def test_case_insensitive_param(self, tag_dict):
        assert _classify_fragment("7B", tag_dict) == ("param_size", "7B")

    def test_case_insensitive_quant(self, tag_dict):
        # Quant lookup is lowercased
        assert _classify_fragment("FP16", tag_dict) == ("quantization", "fp16")


# ─── _extract_license_short ──────────────────────────────


class TestExtractLicenseShort:
    def test_apache_2(self):
        assert _extract_license_short("Apache License Version 2.0") == "Apache-2.0"

    def test_mit(self):
        assert _extract_license_short("MIT License\nCopyright ...") == "MIT"

    def test_mit_bare(self):
        assert _extract_license_short("mit") == "MIT"

    def test_llama2_community(self):
        text = "LLAMA 2 COMMUNITY LICENSE AGREEMENT\nLlama 2 Version Release Date: July 18, 2023"
        assert _extract_license_short(text) == "Llama 2 Community"

    def test_llama3_community(self):
        assert _extract_license_short("META LLAMA 3 COMMUNITY LICENSE AGREEMENT") == "Llama 3 Community"

    def test_llama31_community(self):
        assert _extract_license_short("Llama 3.1 Community License Agreement") == "Llama 3.1 Community"

    def test_gemma(self):
        assert _extract_license_short("Gemma Terms of Use\n...") == "Gemma"

    def test_cc_by_nc(self):
        assert _extract_license_short("CC-BY-NC-4.0 stuff") == "CC-BY-NC-4.0"

    def test_short_first_line(self):
        assert _extract_license_short("Qwen License") == "Qwen License"

    def test_long_text_falls_back(self):
        text = "A" * 100 + "\n" + "more license text"
        assert _extract_license_short(text) == "Custom License"

    def test_empty(self):
        assert _extract_license_short("") is None


# ─── decode_model_name (integration) ─────────────────────


class TestDecodeModelName:
    def test_llama2_7b(self):
        d = decode_model_name("llama2:7b")
        assert d.raw_name == "llama2:7b"
        assert d.family_name == "Llama2"
        assert d.parameter_count == "7B"
        assert d.unknown_parts == []

    def test_qwen_complex_tag(self):
        d = decode_model_name("qwen3.5:35b-a3b-coding-nvfp4")
        assert d.parameter_count == "35B"
        assert d.active_params == "3B"
        assert d.quantization == "NVIDIA FP4"
        assert any("Code" in ft for ft in d.fine_tunes)

    def test_no_tag(self):
        d = decode_model_name("llama2")
        assert d.family_name == "Llama2"
        assert d.parameter_count is None
        assert d.quantization is None

    def test_param_from_api_fallback(self):
        info = ModelInfo(
            name="mystery:latest",
            digest="aaa",
            size=1000,
            modified_at="",
            format="gguf",
            family="mystery",
            families=[],
            parameter_size="13B",
            quantization_level="Q4_0",
        )
        d = decode_model_name("mystery:latest", info=info)
        # "latest" is unknown, but param_size falls back to API
        assert d.parameter_count == "13B"

    def test_quant_from_api_fallback(self):
        info = ModelInfo(
            name="mystery:latest",
            digest="aaa",
            size=1000,
            modified_at="",
            format="gguf",
            family="mystery",
            families=[],
            parameter_size="",
            quantization_level="Q4_K_M",
        )
        d = decode_model_name("mystery:latest", info=info)
        assert d.quantization == "Q4_K_M"

    def test_capabilities_from_details(self):
        details = ModelDetails(
            name="test:7b",
            digest="x",
            size=0,
            modified_at="",
            format="gguf",
            family="test",
            families=[],
            parameter_size="7B",
            quantization_level="",
            architecture="llama",
            context_length=4096,
            parameter_count=0,
            capabilities=["completion", "vision", "tools"],
            template="",
            parameters={},
            license_text="Apache License Version 2.0",
            requires="",
        )
        d = decode_model_name("test:7b", details=details)
        # "completion" is filtered out
        assert "vision" in d.capabilities
        assert "tools" in d.capabilities
        assert "completion" not in d.capabilities
        assert d.license_short == "Apache-2.0"

    def test_successor_from_model_map(self):
        d = decode_model_name("llama2:7b")
        assert d.successor == "llama3.3"

    def test_context_hint(self):
        d = decode_model_name("model:7b-128k")
        assert d.context_hint == "128K"

    def test_unknown_parts_preserved(self):
        d = decode_model_name("model:7b-xyzzy-q4_0")
        assert "xyzzy" in d.unknown_parts
