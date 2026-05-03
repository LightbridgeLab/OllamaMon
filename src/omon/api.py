"""Ollama HTTP API client. All Ollama communication goes through this module."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from omon.models import ModelDetails, ModelInfo, RunningModel, ServerStatus

DEFAULT_HOST = "localhost:11434"


class OllamaError(Exception):
    """Error communicating with Ollama."""


@dataclass
class GenerateResult:
    """Metrics from a single generate call."""
    response: str
    total_duration_ns: int
    load_duration_ns: int
    prompt_eval_count: int
    prompt_eval_duration_ns: int
    eval_count: int
    eval_duration_ns: int

    @property
    def gen_tok_s(self) -> float:
        if self.eval_duration_ns <= 0:
            return 0.0
        return self.eval_count / (self.eval_duration_ns / 1e9)

    @property
    def prompt_tok_s(self) -> float:
        if self.prompt_eval_duration_ns <= 0:
            return 0.0
        return self.prompt_eval_count / (self.prompt_eval_duration_ns / 1e9)

    @property
    def load_ms(self) -> float:
        return self.load_duration_ns / 1e6

    @property
    def ttft_ms(self) -> float:
        """Time to first token: load + prompt eval."""
        return (self.load_duration_ns + self.prompt_eval_duration_ns) / 1e6


def _url(host: str, path: str) -> str:
    return f"http://{host}{path}"


def _get(host: str, path: str) -> Any:
    try:
        with urllib.request.urlopen(_url(host, path), timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        raise OllamaError(f"Cannot connect to Ollama at {host}: {e.reason}") from e
    except TimeoutError as e:
        raise OllamaError(f"Timeout connecting to Ollama at {host}") from e


def _post(host: str, path: str, body: dict, timeout: int = 10) -> Any:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        _url(host, path),
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        raise OllamaError(f"Cannot connect to Ollama at {host}: {e.reason}") from e
    except TimeoutError as e:
        raise OllamaError(f"Timeout connecting to Ollama at {host}") from e


def get_server_status(host: str = DEFAULT_HOST) -> ServerStatus:
    try:
        data = _get(host, "/api/version")
        return ServerStatus(
            running=True,
            version=data.get("version"),
            host=host,
        )
    except OllamaError as e:
        return ServerStatus(running=False, version=None, host=host, error=str(e))


def list_models(host: str = DEFAULT_HOST) -> list[ModelInfo]:
    data = _get(host, "/api/tags")
    results = []
    for m in data.get("models", []):
        details = m.get("details", {})
        results.append(ModelInfo(
            name=m["name"],
            digest=m.get("digest", "")[:12],
            size=m.get("size", 0),
            modified_at=m.get("modified_at", ""),
            format=details.get("format", ""),
            family=details.get("family", ""),
            families=details.get("families") or [],
            parameter_size=details.get("parameter_size", ""),
            quantization_level=details.get("quantization_level", ""),
        ))
    return results


def show_model(name: str, host: str = DEFAULT_HOST) -> ModelDetails:
    data = _post(host, "/api/show", {"name": name})
    details = data.get("details", {})
    model_info = data.get("model_info", {})

    # Extract architecture-prefixed fields
    arch = details.get("family", "") or model_info.get("general.architecture", "")
    context_length = model_info.get(f"{arch}.context_length", 0)
    if not context_length:
        # Try common architecture names
        for key, val in model_info.items():
            if key.endswith(".context_length"):
                context_length = val
                break

    param_count = model_info.get("general.parameter_count", 0)

    # Parse parameters string into dict
    params = {}
    for line in data.get("parameters", "").strip().splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            params[parts[0]] = parts[1]

    # Extract a short license (first line or SPDX-like identifier)
    license_text = data.get("license", "")

    return ModelDetails(
        name=name,
        digest=data.get("digest", "")[:12],
        size=0,  # not in /api/show, caller fills from list
        modified_at=data.get("modified_at", ""),
        format=details.get("format", ""),
        family=details.get("family", "") or arch,
        families=details.get("families") or [],
        parameter_size=details.get("parameter_size", ""),
        quantization_level=details.get("quantization_level", ""),
        architecture=arch,
        context_length=context_length,
        parameter_count=param_count,
        capabilities=data.get("capabilities") or [],
        template=data.get("template", ""),
        parameters=params,
        license_text=license_text,
        requires=data.get("requires", ""),
    )


def list_running(host: str = DEFAULT_HOST) -> list[RunningModel]:
    data = _get(host, "/api/ps")
    results = []
    for m in data.get("models", []):
        details = m.get("details", {})
        results.append(RunningModel(
            name=m["name"],
            digest=m.get("digest", "")[:12],
            size=m.get("size", 0),
            size_vram=m.get("size_vram", 0),
            context_length=m.get("context_length", 0),
            expires_at=m.get("expires_at", ""),
            family=details.get("family", ""),
            parameter_size=details.get("parameter_size", ""),
            quantization_level=details.get("quantization_level", ""),
        ))
    return results


def generate(
    model: str,
    prompt: str,
    num_predict: int = 100,
    host: str = DEFAULT_HOST,
) -> GenerateResult:
    """Run a non-streaming generate and return timing metrics."""
    data = _post(
        host,
        "/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": num_predict},
        },
        timeout=300,  # generous timeout for large models
    )
    return GenerateResult(
        response=data.get("response", ""),
        total_duration_ns=data.get("total_duration", 0),
        load_duration_ns=data.get("load_duration", 0),
        prompt_eval_count=data.get("prompt_eval_count", 0),
        prompt_eval_duration_ns=data.get("prompt_eval_duration", 0),
        eval_count=data.get("eval_count", 0),
        eval_duration_ns=data.get("eval_duration", 0),
    )


def unload_model(model: str, host: str = DEFAULT_HOST) -> None:
    """Unload a model from memory by setting keep_alive to 0."""
    _post(
        host,
        "/api/generate",
        {"model": model, "prompt": "", "keep_alive": 0, "stream": False},
        timeout=30,
    )
