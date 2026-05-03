"""Tests for the Ollama API client. Mocks urllib — no running server needed."""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from omon.api import (
    DEFAULT_HOST,
    GenerateResult,
    OllamaError,
    generate,
    get_server_status,
    list_models,
    list_running,
    show_model,
)


def _mock_urlopen(data: dict):
    """Create a patched urlopen that returns JSON data."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return patch("urllib.request.urlopen", return_value=mock_resp)


def _mock_urlopen_error(reason: str = "Connection refused"):
    """Create a patched urlopen that raises URLError."""
    err = urllib.error.URLError(reason)
    return patch("urllib.request.urlopen", side_effect=err)


# ─── GenerateResult properties ───────────────────────────


class TestGenerateResult:
    def test_gen_tok_s(self):
        r = GenerateResult(
            response="hello",
            total_duration_ns=0,
            load_duration_ns=0,
            prompt_eval_count=10,
            prompt_eval_duration_ns=100_000_000,
            eval_count=50,
            eval_duration_ns=1_000_000_000,  # 1 second
        )
        assert r.gen_tok_s == 50.0

    def test_prompt_tok_s(self):
        r = GenerateResult(
            response="",
            total_duration_ns=0,
            load_duration_ns=0,
            prompt_eval_count=100,
            prompt_eval_duration_ns=500_000_000,  # 0.5 seconds
            eval_count=0,
            eval_duration_ns=0,
        )
        assert r.prompt_tok_s == 200.0

    def test_zero_duration(self):
        r = GenerateResult(
            response="",
            total_duration_ns=0,
            load_duration_ns=0,
            prompt_eval_count=0,
            prompt_eval_duration_ns=0,
            eval_count=0,
            eval_duration_ns=0,
        )
        assert r.gen_tok_s == 0.0
        assert r.prompt_tok_s == 0.0

    def test_load_ms(self):
        r = GenerateResult(
            response="",
            total_duration_ns=0,
            load_duration_ns=250_000_000,  # 250ms
            prompt_eval_count=0,
            prompt_eval_duration_ns=0,
            eval_count=0,
            eval_duration_ns=0,
        )
        assert r.load_ms == 250.0

    def test_ttft_ms(self):
        r = GenerateResult(
            response="",
            total_duration_ns=0,
            load_duration_ns=100_000_000,  # 100ms
            prompt_eval_count=0,
            prompt_eval_duration_ns=50_000_000,  # 50ms
            eval_count=0,
            eval_duration_ns=0,
        )
        assert r.ttft_ms == 150.0


# ─── get_server_status ───────────────────────────────────


class TestGetServerStatus:
    def test_running(self):
        with _mock_urlopen({"version": "0.6.2"}):
            status = get_server_status()
        assert status.running is True
        assert status.version == "0.6.2"
        assert status.host == DEFAULT_HOST

    def test_not_running(self):
        with _mock_urlopen_error():
            status = get_server_status()
        assert status.running is False
        assert status.version is None
        assert "Cannot connect" in status.error

    def test_custom_host(self):
        with _mock_urlopen({"version": "0.5.0"}):
            status = get_server_status(host="myhost:11434")
        assert status.host == "myhost:11434"


# ─── list_models ─────────────────────────────────────────


class TestListModels:
    def test_parses_models(self):
        data = {
            "models": [
                {
                    "name": "llama2:7b",
                    "digest": "sha256:abc123def456789",
                    "size": 3_800_000_000,
                    "modified_at": "2026-04-01T12:00:00Z",
                    "details": {
                        "format": "gguf",
                        "family": "llama",
                        "families": ["llama"],
                        "parameter_size": "7B",
                        "quantization_level": "Q4_0",
                    },
                }
            ]
        }
        with _mock_urlopen(data):
            models = list_models()
        assert len(models) == 1
        m = models[0]
        assert m.name == "llama2:7b"
        assert m.size == 3_800_000_000
        assert m.family == "llama"
        assert m.parameter_size == "7B"
        assert m.quantization_level == "Q4_0"
        assert m.digest == "sha256:abc12"  # truncated to 12 chars

    def test_empty_list(self):
        with _mock_urlopen({"models": []}):
            models = list_models()
        assert models == []

    def test_missing_details(self):
        data = {
            "models": [
                {
                    "name": "test:latest",
                    "size": 100,
                }
            ]
        }
        with _mock_urlopen(data):
            models = list_models()
        assert len(models) == 1
        assert models[0].family == ""
        assert models[0].parameter_size == ""

    def test_connection_error(self):
        with _mock_urlopen_error():
            with pytest.raises(OllamaError, match="Cannot connect"):
                list_models()


# ─── show_model ──────────────────────────────────────────


class TestShowModel:
    def test_parses_details(self):
        data = {
            "digest": "sha256:abc123def456789",
            "modified_at": "2026-04-01T12:00:00Z",
            "details": {
                "format": "gguf",
                "family": "llama",
                "families": ["llama"],
                "parameter_size": "7B",
                "quantization_level": "Q4_0",
            },
            "model_info": {
                "general.architecture": "llama",
                "general.parameter_count": 6_738_415_616,
                "llama.context_length": 4096,
            },
            "parameters": "temperature 0.8\ntop_p 0.9",
            "template": "{{ .Prompt }}",
            "license": "MIT License",
            "capabilities": ["completion", "tools"],
        }
        with _mock_urlopen(data):
            det = show_model("llama2:7b")
        assert det.name == "llama2:7b"
        assert det.architecture == "llama"
        assert det.context_length == 4096
        assert det.parameter_count == 6_738_415_616
        assert det.parameters == {"temperature": "0.8", "top_p": "0.9"}
        assert det.capabilities == ["completion", "tools"]
        assert det.license_text == "MIT License"

    def test_context_length_fallback(self):
        # When family doesn't match a prefixed key, fall back to scanning
        data = {
            "details": {"family": "weird"},
            "model_info": {
                "general.architecture": "weird",
                "something.context_length": 8192,
            },
            "parameters": "",
        }
        with _mock_urlopen(data):
            det = show_model("weird:7b")
        assert det.context_length == 8192

    def test_missing_optional_fields(self):
        data = {
            "details": {},
            "model_info": {},
            "parameters": "",
        }
        with _mock_urlopen(data):
            det = show_model("bare:latest")
        assert det.context_length == 0
        assert det.capabilities == []
        assert det.template == ""


# ─── list_running ────────────────────────────────────────


class TestListRunning:
    def test_parses_running(self):
        data = {
            "models": [
                {
                    "name": "llama2:7b",
                    "digest": "sha256:abc123",
                    "size": 4_500_000_000,
                    "size_vram": 4_500_000_000,
                    "context_length": 4096,
                    "expires_at": "2026-04-22T12:00:00Z",
                    "details": {
                        "family": "llama",
                        "parameter_size": "7B",
                        "quantization_level": "Q4_0",
                    },
                }
            ]
        }
        with _mock_urlopen(data):
            running = list_running()
        assert len(running) == 1
        r = running[0]
        assert r.name == "llama2:7b"
        assert r.size == 4_500_000_000
        assert r.context_length == 4096

    def test_empty(self):
        with _mock_urlopen({"models": []}):
            assert list_running() == []


# ─── generate ────────────────────────────────────────────


class TestGenerate:
    def test_returns_metrics(self):
        data = {
            "response": "Hello! I'm an AI assistant.",
            "total_duration": 2_000_000_000,
            "load_duration": 100_000_000,
            "prompt_eval_count": 12,
            "prompt_eval_duration": 200_000_000,
            "eval_count": 8,
            "eval_duration": 500_000_000,
        }
        with _mock_urlopen(data):
            result = generate("llama2:7b", "Hello")
        assert result.response == "Hello! I'm an AI assistant."
        assert result.eval_count == 8
        assert result.gen_tok_s == 16.0  # 8 / 0.5s

    def test_connection_error(self):
        with _mock_urlopen_error():
            with pytest.raises(OllamaError):
                generate("llama2:7b", "Hello")
